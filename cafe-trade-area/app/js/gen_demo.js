/* 데모 데이터 생성기 — analysis 의 예시 CSV 를 그대로 js/demo.js 로 굳힌다.
   웹앱은 file:// 로도 열려야 해서 CSV 를 fetch 할 수 없다. 그래서 굽는다.
   CSV 를 고쳤다면:  node app/js/gen_demo.js
   (analysis/tests/test_demo_sync.py 가 어긋남을 잡아준다) */
const fs = require('fs');
const path = require('path');
const U = require(path.join(__dirname, 'util.js'));

const A = path.resolve(__dirname, '..', '..', 'analysis');
const sites = U.parseCSV(fs.readFileSync(path.join(A, '후보지.example.csv'), 'utf-8'));
const pois = U.parseCSV(fs.readFileSync(path.join(A, 'pois.example.csv'), 'utf-8'));

/* brand.example.yaml 을 읽는다. 이 파일은 스칼라와 1단계 중첩만 쓰므로
   YAML 파서 없이 이 최소 리더로 충분하다(주석·빈 줄 무시). */
function readSimpleYaml(file) {
  const out = {};
  let group = null;
  for (const raw of fs.readFileSync(file, 'utf-8').split(/\r?\n/)) {
    const line = raw.replace(/#.*$/, '').trimEnd();
    if (!line.trim()) continue;
    const m = line.match(/^(\s*)([^:]+):\s*(.*)$/);
    if (!m) continue;
    const [, indent, key, val] = m;
    if (indent.length === 0) {
      if (val === '') { group = key.trim(); out[group] = {}; }
      else { group = null; out[key.trim()] = val === '' ? '' : (isNaN(Number(val)) ? val : Number(val)); }
    } else if (group) {
      out[group][key.trim()] = isNaN(Number(val)) ? val : Number(val);
    }
  }
  return out;
}
const brand = readSimpleYaml(path.join(A, 'brand.example.yaml'));

const out = `/* 데모 데이터 — analysis/후보지.example.csv · pois.example.csv 에서 생성됨.
   직접 고치지 말고 CSV 를 고친 뒤 \`node app/js/gen_demo.js\` 로 다시 구우세요. */
const DEMO_SITES = ${JSON.stringify(sites, null, 2)};

const DEMO_POIS = ${JSON.stringify(pois, null, 2)};

const DEMO_BRAND = ${JSON.stringify(brand, null, 2)};

if (typeof module !== 'undefined' && module.exports) module.exports = { DEMO_SITES, DEMO_POIS, DEMO_BRAND };
`;
fs.writeFileSync(path.join(__dirname, 'demo.js'), out, 'utf-8');
console.log(`demo.js 생성 — 후보지 ${sites.length}곳 · POI ${pois.length}건 · 브랜드 ${brand.브랜드}`);
