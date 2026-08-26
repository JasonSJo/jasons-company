/* 파이썬 모델(common.py)과 웹앱 모델(app/js/model.js)의 대조용 러너.
   같은 CSV·YAML 입력으로 model.js 를 돌려 JSON 을 stdout 으로 뱉는다.
   test_parity.py 가 이 출력을 파이썬 결과와 비교한다.

   사용: node parity_runner.js <sites.csv> [pois.csv] [brand.json]
         node parity_runner.js --report <조사일> <sites.csv> [pois.csv] [brand.json]
           → 후보지별 리포트 마크다운({후보지명: md})을 뱉는다. */
const fs = require('fs');
const path = require('path');
const APP = path.resolve(__dirname, '..', '..', 'app', 'js');
const U = require(path.join(APP, 'util.js'));
const M = require(path.join(APP, 'model.js'));

const argv = process.argv.slice(2);
const reportMode = argv[0] === '--report';
const reportDate = reportMode ? argv[1] : null;
const [sitesPath, poisPath, brandPath] = reportMode ? argv.slice(2) : argv;
const read = p => U.parseCSV(fs.readFileSync(p, 'utf-8'));
const sites = read(sitesPath);
const pois = poisPath && fs.existsSync(poisPath) ? read(poisPath) : [];
const brand = brandPath && fs.existsSync(brandPath)
  ? JSON.parse(fs.readFileSync(brandPath, 'utf-8')) : {};

// report.js 는 브라우저 전역(U·M)을 전제로 하므로 전역에 올려준다
globalThis.U = U;
globalThis.M = M;

if (reportMode) {
  const Report = require(path.join(APP, 'report.js'));
  const md = {};
  for (const s of sites) {
    const name = (s.후보지명 || '').trim();
    if (name) md[name] = Report.markdown(s, pois, brand, reportDate);
  }
  process.stdout.write(JSON.stringify(md));
  process.exit(0);
}

const out = sites
  .filter(s => (s.후보지명 || '').trim())
  .map(s => {
    const r = M.analyze(s, pois, brand);
    return {
      후보지명: r.후보지명, 총점: r.총점, 등급: r.등급, 항목: r.항목, 경쟁: r.경쟁,
      매출추정: r.매출추정, 손익: r.손익, 리스크: r.리스크, 결론: M.verdict(r)[0],
    };
  });
process.stdout.write(JSON.stringify(out, null, 2));
