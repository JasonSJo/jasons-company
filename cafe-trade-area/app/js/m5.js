/* M5 판정 산술 — analysis/m5_verdict.py 의 포팅.
   콘솔이 다시 구현하는 유일한 모듈이다. M1~M4 는 등시선·격자인구·회귀표본이
   있어야 하므로 브라우저에서 재현하지 않고 파이프라인 산출(심의결과.json)을 읽는다.
   여기만 두 벌이므로 analysis/tests/test_m5_parity.py 가 두 구현을 대조한다. */
const M5 = (() => {

  // 명세 고정값 — config.py 와 같아야 한다
  const 부결_마진 = 0.15, 보류_마진 = 0.30, 보류_점수 = 70.0, 보류_중첩 = 0.30;
  const FATAL = [
    ['근저당_과다', '등기부상 근저당 과다 또는 선순위 권리로 보증금 회수 불확실'],
    ['임대인_불일치', '임대인이 실소유자와 불일치 (전대차 구조·자기거래 정황)'],
    ['소송_계류', '소송·명도 분쟁 계류 중인 물건'],
    ['인허가_불가', '용도지역·정화조 용량 등으로 휴게음식점 인허가 불가'],
  ];
  const TRUE_SET = ['Y', 'YES', '예', 'O', 'TRUE', '1', '해당'];

  const f = (v, d = 0) => {
    if (v === null || v === undefined) return d;
    const s = String(v).replace(/[^0-9.\-]/g, '');
    if (s === '' || s === '-' || s === '.' || s === '-.') return d;
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : d;
  };
  const flagged = v => TRUE_SET.includes(String(v).trim().toUpperCase());

  /* 표기 반올림 — common.nf 와 같은 규칙(0.5 는 절대값이 커지는 쪽).
     toLocaleString 에 그냥 맡기면 파이썬의 은행가 반올림과 마지막 자리가 갈린다. */
  const r2 = (v, n = 0) => {
    const p = 10 ** n, x = v * p;
    const r = Math.floor(Math.abs(x) + 0.5 + 1e-9);
    return (x < 0 ? -r : r) / p;
  };
  const nf = (v, n = 0) => r2(v, n).toLocaleString('en-US',
    { minimumFractionDigits: n, maximumFractionDigits: n });
  const pf = (v, n = 0) => nf(v * 100, n) + '%';

  const fatalFlags = site => FATAL.filter(([k]) => flagged(site[k])).map(([, d]) => d);
  const unchecked = site => FATAL.filter(([k]) => String(site[k] ?? '').trim() === '').map(([, d]) => d);

  function variableRate(settings) {
    const v = ((settings || {}).운영 || {}).변동비 || {};
    return f(v.원재료율) + f(v.로열티율) + f(v.광고분담금율) + f(v.기타변동비율);
  }

  function fixedCost(site, settings) {
    const fx = ((settings || {}).운영 || {}).고정비 || {};
    const rent = f(site.월임대료_만원), mgmt = f(site.관리비_만원);
    const labor = f(fx.고정인건비_월_만원), etc = f(fx.기타_월_만원);
    return { 임대료: rent, 관리비: mgmt, 고정인건비: labor, 기타: etc, F: rent + mgmt + labor + etc };
  }

  function cannibalization(overlaps, kappa) {
    const rows = (overlaps || []).map(o => ({ ...o, 잠식액_만원: o.overlap * f(o.월매출_만원) * kappa }));
    return {
      'κ': kappa,
      최대_overlap: rows.reduce((m, r) => Math.max(m, r.overlap), 0),
      잠식액_합_만원: rows.reduce((s, r) => s + r.잠식액_만원, 0),
      상세: rows.slice().sort((a, b) => b.overlap - a.overlap),
    };
  }

  /* 명세의 3단 분기. 치명 플래그는 점수·매출과 무관하게 단독으로 부결시킨다. */
  function judge(site, revenue, settings, S, overlaps, kappa, sPoolMax) {
    const v = variableRate(settings);
    const fc = fixedCost(site, settings);
    const bep = v < 1 ? fc.F / (1 - v) : null;

    const rMed = revenue.월매출_중앙, rLow = revenue.월매출_하한;
    const margin = (bep !== null && rMed) ? (rMed - bep) / rMed : null;
    const marginLow = (bep !== null && rLow) ? (rLow - bep) / rLow : null;

    const can = cannibalization(overlaps, kappa);
    const overlap = can.최대_overlap;
    const fatal = fatalFlags(site);
    const unchk = unchecked(site);

    const reasons = [];
    fatal.forEach(x => reasons.push(`치명: ${x}`));
    if (bep === null) reasons.push('변동비율이 100% 이상 — 어떤 매출에서도 흑자 불가');
    if (margin !== null && margin < 부결_마진) {
      reasons.push(`margin ${pf(margin, 1)} < ${pf(부결_마진)}`);
    }

    let verdict;
    if (fatal.length || bep === null || (margin !== null && margin < 부결_마진)) {
      verdict = '부결';
    } else {
      const hold = [];
      if (margin === null) hold.push('매출 추정 실패 — margin 계산 불가');
      else {
        if (margin < 보류_마진) {
          hold.push(`margin ${pf(margin, 1)} < ${pf(보류_마진)}`);
        }
        if (marginLow !== null && marginLow < 0) {
          hold.push(`하한 시나리오 적자 (margin_low ${pf(marginLow, 1)})`);
        }
      }
      if (S < 보류_점수) hold.push(`S ${nf(S, 1)} < ${nf(보류_점수)}`);
      if (overlap > 보류_중첩) {
        hold.push(`자사 상권 중첩 ${pf(overlap)} > ${pf(보류_중첩)}`);
      }
      verdict = hold.length ? '보류' : '통과';
      hold.forEach(x => reasons.push(x));
    }

    // 문구와 순서까지 m5_verdict.py 와 같아야 한다 (tests/test_m5_parity.py 가 글자 단위로 대조)
    const notes = [];
    if (sPoolMax !== null && sPoolMax !== undefined && sPoolMax < 보류_점수) {
      notes.push(`⛔ S 게이트 축퇴 — 풀 전체 S 최댓값이 ${nf(sPoolMax, 1)} 로 임계값 ` +
        `${nf(보류_점수)} 에 못 미칩니다. S 는 풀 내 min-max 정규화라 모든 지표에서 ` +
        `동시에 1등이어야 100 에 닿습니다. 지금 조건에서는 'S < 70' 이 모든 후보지에 ` +
        `무조건 걸려 변별력이 없습니다. 임계값을 포트폴리오 기준(예: 기준점포 S)으로 ` +
        `재설정하거나 정규화 방식을 바꾸는 결정이 필요합니다.`);
    }
    if (verdict === '통과' && unchk.length) {
      notes.push(`⛔ 치명 항목 ${unchk.length}건이 미확인 상태입니다 — ` +
        `등기·임대인·소송·인허가 실사를 마치기 전의 '통과'는 잠정입니다.`);
    }
    if (can.잠식액_합_만원 > 0) {
      notes.push(`자사 기존점 잠식 추정 ${nf(can.잠식액_합_만원)}만원/월 ` +
        `(κ=${kappa} 미검증) — 신규 매출에서 차감해 순증을 보십시오.`);
    }

    return {
      판정: verdict, 사유: reasons, 비고: notes,
      치명플래그: fatal, 치명_미확인: unchk,
      변동비율: v, 고정비: fc, BEP_만원: bep,
      margin, margin_low: marginLow, S, 카니발: can,
      순증_월매출_만원: rMed ? rMed - can.잠식액_합_만원 : null,
    };
  }

  return { judge, variableRate, fixedCost, cannibalization, fatalFlags, unchecked, f,
           상수: { 부결_마진, 보류_마진, 보류_점수, 보류_중첩 } };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = M5;
