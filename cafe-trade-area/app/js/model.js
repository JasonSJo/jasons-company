/* 상권 분석 모델 — analysis/common.py 의 1:1 포팅.
   상수와 공식이 파이썬과 같아야 콘솔과 CLI 결과가 어긋나지 않는다.
   analysis/tests/test_parity.py 가 두 구현을 같은 입력으로 돌려 대조한다.
   여기를 고치면 common.py 도 같이 고쳐야 한다(그 반대도 마찬가지). */
const M = (() => {

  // ── 점수 배점(합 100) ──
  const WEIGHTS = { 배후수요: 30, 유동인구: 25, 경쟁: 20, 접근성: 15, 비용: 10 };
  const WEIGHT_KEYS = Object.keys(WEIGHTS);

  const DEMAND_FULL = 30000;
  const TRAFFIC_FULL = 40000;

  const RIVAL_BRANDS = ['메가', '컴포즈', '빽다방', '더벤티', '감성커피', '매머드', '폴바셋'];
  const ANCHOR_BRANDS = ['스타벅스', '투썸', '커피빈', '블루보틀'];

  const GRADES = [[80, 'A', '즉시 출점 검토'], [65, 'B', '조건부 추천'], [50, 'C', '보류·재협상']];
  const EARTH_R = 6371000;

  // ── 매출 파라미터 ──
  const MARKET_TRAFFIC_RATE = 0.045;
  const MARKET_RESIDENT_RATE = 0.05;
  const MARKET_WORKER_RATE = 0.12;
  const LOC_MULT_MIN = 0.70;
  const LOC_MULT_SPAN = 1.10;
  const SHARE_CAP = 0.25;
  const TURN_HOURS = 1.5;
  const SEAT_UTIL = 0.55;
  const TAKEOUT_RATIO = 0.45;

  const DEFAULTS = {
    객단가_원: 5200, 영업일수: 30, 영업시간: 13, 좌석수_기본: 24,
    테이크아웃_비중: TAKEOUT_RATIO, 반경_m: 500,
    변동비: { 재료비율: 0.35, 카드수수료율: 0.022, 로열티율: 0.03, 광고분담금율: 0.01 },
    고정비: { 최소인건비_월_만원: 620, 인건비율: 0.20, 수도광열_월_만원: 85, 소모품_월_만원: 45, 기타_월_만원: 40 },
    초기투자: { 인테리어_평당_만원: 250, 장비_만원: 4500, 가맹비_만원: 1000, 교육비_만원: 300 },
  };

  // ── 유틸 (common.to_f / to_i / is_yes 와 동일 규칙) ──
  const f = (v, d = 0) => {
    if (v === null || v === undefined) return d;
    const s = String(v).replace(/[^0-9.\-]/g, '');
    if (s === '' || s === '-' || s === '.' || s === '-.') return d;
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : d;
  };
  const i = (v, d = 0) => Math.trunc(f(v, d));
  const yes = v => ['Y', 'YES', '예', 'O', 'TRUE', '1', '있음'].includes(String(v).trim().toUpperCase());
  /* 반올림 — common.py 의 r2 와 완전히 같은 규칙(0.5 는 절대값이 커지는 쪽).
     Math.round 를 그대로 쓰면 파이썬의 은행가 반올림과 0.1 씩 어긋난다. */
  const r2 = (v, n = 1) => {
    const p = 10 ** n;
    const x = v * p;
    const r = Math.floor(Math.abs(x) + 0.5 + 1e-9);
    return (x < 0 ? -r : r) / p;
  };
  const ri = v => r2(v, 0);

  function haversine(lat1, lon1, lat2, lon2) {
    const rad = Math.PI / 180;
    const p1 = lat1 * rad, p2 = lat2 * rad;
    const dp = p2 - p1, dl = (lon2 - lon1) * rad;
    const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    return 2 * EARTH_R * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  function grade(total) {
    for (const [cut, g, label] of GRADES) if (total >= cut) return [g, label];
    return ['D', '부적합'];
  }

  /* 브랜드 설정 병합 — 콘솔이 일부 값만 들고 있어도 파이썬 기본값과 같아지도록. */
  function withDefaults(brand) {
    const b = Object.assign({}, DEFAULTS, brand || {});
    for (const k of ['변동비', '고정비', '초기투자']) {
      b[k] = Object.assign({}, DEFAULTS[k], (brand && brand[k]) || {});
    }
    return b;
  }

  // ── 반경 내 경쟁 집계 ──
  function competition(site, pois, radius) {
    const lat = f(site.위도), lon = f(site.경도);
    let cafes = 0, rivals = 0, anchors = 0, own = 0, nearestOwn = null;

    if (lat && lon && pois && pois.length) {
      for (const p of pois) {
        const plat = f(p.위도), plon = f(p.경도);
        if (!plat || !plon) continue;
        const d = haversine(lat, lon, plat, plon);
        if (d > radius) continue;
        const kind = String(p.분류 || '').trim();
        const brand = String(p.브랜드 || p.상호 || '');
        if (kind === '자사점') {
          own += 1;
          nearestOwn = nearestOwn === null ? d : Math.min(nearestOwn, d);
        } else if (kind === '카페') {
          cafes += 1;
          if (RIVAL_BRANDS.some(b => brand.includes(b))) rivals += 1;
          else if (ANCHOR_BRANDS.some(b => brand.includes(b))) anchors += 1;
        }
      }
    }
    // 현장 조사값과 수집값 중 큰 쪽 — 경쟁 과소평가를 막는다
    cafes = Math.max(cafes, i(site.카페수_500m));
    rivals = Math.max(rivals, i(site.동일포지션_경쟁수));

    if (lat && lon && pois && pois.length && nearestOwn === null) {
      for (const p of pois) {
        if (String(p.분류 || '').trim() !== '자사점') continue;
        const plat = f(p.위도), plon = f(p.경도);
        if (!plat || !plon) continue;
        const d = haversine(lat, lon, plat, plon);
        nearestOwn = nearestOwn === null ? d : Math.min(nearestOwn, d);
      }
    }
    return {
      카페수: cafes, 동일포지션: rivals, 앵커브랜드: anchors, 자사점수: own,
      자사점_최근접_m: nearestOwn === null ? null : ri(nearestOwn),
    };
  }

  // ── 항목별 점수 ──
  function scoreDemand(s) {
    const idx = f(s.주거인구_500m) * 0.5 + f(s.직장인구_500m) * 1.0
      + f(s.아파트세대수) * 0.8 + f(s.대학_학원수) * 300 + f(s.오피스빌딩수) * 150;
    return [r2(Math.min(WEIGHTS.배후수요, WEIGHTS.배후수요 * idx / DEMAND_FULL)),
      `배후수요지수 ${ri(idx).toLocaleString()}`];
  }

  function scoreTraffic(s) {
    const eff = f(s.유동인구_일평균) + f(s.지하철_일평균승하차) * 0.3;
    return [r2(Math.min(WEIGHTS.유동인구, WEIGHTS.유동인구 * eff / TRAFFIC_FULL)),
      `유효유동 ${ri(eff).toLocaleString()}명/일`];
  }

  function peoplePerCafe(s, c) {
    return (f(s.주거인구_500m) + f(s.직장인구_500m)) / Math.max(1, c.카페수);
  }

  function scoreCompetition(s, c) {
    const ppc = peoplePerCafe(s, c);
    let base = 1.0;
    for (const [cut, pts] of [[2000, 20], [1500, 16], [1000, 12], [700, 8], [400, 4]]) {
      if (ppc >= cut) { base = pts; break; }
    }
    base -= Math.min(6, c.동일포지션 * 1.5);
    base += Math.min(2, c.앵커브랜드 * 1.0);
    let note = `카페1개당 배후인구 ${ri(ppc).toLocaleString()}명 · 동일포지션 ${c.동일포지션}곳`;
    if (c.자사점_최근접_m !== null && c.자사점_최근접_m < 500) {
      base -= 5;
      note += ` · ⚠ 자사점 ${c.자사점_최근접_m}m (자기잠식)`;
    }
    return [r2(Math.max(0, Math.min(WEIGHTS.경쟁, base))), note];
  }

  function scoreAccess(s) {
    let pts = 0; const why = [];
    const w = f(s.지하철_도보분, 99);
    for (const [cut, p] of [[3, 6], [5, 5], [7, 4], [10, 2.5], [15, 1]]) {
      if (w <= cut) { pts += p; why.push(`역 도보 ${ri(w)}분`); break; }
    }
    if (yes(s.코너여부)) { pts += 3; why.push('코너'); }
    if (i(s.층, 1) === 1) { pts += 3; why.push('1층'); }
    const front = f(s.전면길이_m);
    if (front >= 8) { pts += 2; why.push(`전면 ${ri(front)}m`); }
    else if (front >= 5) pts += 1;
    if (i(s.주차가능대수) >= 3) { pts += 1; why.push('주차'); }
    return [r2(Math.min(WEIGHTS.접근성, pts)), why.join(' · ') || '접근성 열위'];
  }

  function rentPerPyeong(s) {
    const area = f(s.전용면적_평);
    return area ? f(s.월임대료_만원) / area : 0;
  }

  function scoreCost(s) {
    const rpp = rentPerPyeong(s);
    if (rpp <= 0) return [0, '임대료 정보 없음'];
    for (const [cut, pts] of [[10, 10], [15, 8], [20, 6], [25, 4], [35, 2]]) {
      if (rpp <= cut) return [pts, `평당 임대료 ${r2(rpp, 1).toFixed(1)}만원`];
    }
    return [0, `평당 임대료 ${r2(rpp, 1).toFixed(1)}만원 (과다)`];
  }

  function scoreSite(site, pois, radius = 500) {
    const c = competition(site, pois, radius);
    const [d, n1] = scoreDemand(site), [t, n2] = scoreTraffic(site);
    const [k, n3] = scoreCompetition(site, c), [a, n4] = scoreAccess(site);
    const [co, n5] = scoreCost(site);
    const 항목 = { 배후수요: d, 유동인구: t, 경쟁: k, 접근성: a, 비용: co };
    const total = r2(d + t + k + a + co);
    const [g, label] = grade(total);
    return {
      후보지명: String(site.후보지명 || '').trim(), 주소: String(site.주소 || '').trim(),
      총점: total, 등급: g, 등급설명: label, 항목, 경쟁: c, 근거: [n1, n2, n3, n4, n5],
    };
  }

  // ── 매출 추정 ──
  const marketDemand = s => f(s.유동인구_일평균) * MARKET_TRAFFIC_RATE
    + f(s.주거인구_500m) * MARKET_RESIDENT_RATE + f(s.직장인구_500m) * MARKET_WORKER_RATE;

  const locationMultiplier = sc => LOC_MULT_MIN + LOC_MULT_SPAN * (sc.항목.접근성 / WEIGHTS.접근성);

  const marketShare = sc => Math.min(SHARE_CAP, locationMultiplier(sc) / Math.max(1, sc.경쟁.카페수 + 1));

  function estimateRevenue(site, sc, brand) {
    const b = withDefaults(brand);
    const ticket = f(b.객단가_원, 5000), days = f(b.영업일수, 30), hours = f(b.영업시간, 13);
    const seats = i(site.좌석수) || i(b.좌석수_기본, 24);

    const demand = marketDemand(site), share = marketShare(sc);
    const raw = demand * share;

    const takeout = f(b.테이크아웃_비중, TAKEOUT_RATIO);
    const seatCap = seats * (hours / TURN_HOURS) * SEAT_UTIL;
    const capped = Math.min(raw * (1 - takeout), seatCap) + raw * takeout;

    return {
      상권수요_일객수: r2(demand), 점유율: r2(share, 4), 입지배수: r2(locationMultiplier(sc), 3),
      경쟁카페수: sc.경쟁.카페수, 일객수_이론: r2(raw), 일객수_추정: r2(capped),
      좌석상한_일객수: r2(seatCap), 테이크아웃_비중: r2(takeout, 3),
      좌석제약: raw * (1 - takeout) > seatCap, 객단가_원: ri(ticket),
      일매출_만원: r2(capped * ticket / 10000), 월매출_만원: r2(capped * ticket * days / 10000),
    };
  }

  // ── 손익 · 투자회수 ──
  function variableRate(brand) {
    const v = withDefaults(brand).변동비;
    return f(v.재료비율, 0.35) + f(v.카드수수료율, 0.022) + f(v.로열티율, 0.03) + f(v.광고분담금율, 0.01);
  }

  function estimatePnl(site, rev, brand) {
    const b = withDefaults(brand), fx = b.고정비, iv = b.초기투자;
    const sales = rev.월매출_만원, vr = variableRate(b);

    const rent = f(site.월임대료_만원), mgmt = f(site.관리비_만원);
    const otherFixed = rent + mgmt + f(fx.수도광열_월_만원, 85) + f(fx.소모품_월_만원, 45) + f(fx.기타_월_만원, 40);
    const baseLabor = f(fx.최소인건비_월_만원, 620), laborRate = f(fx.인건비율, 0.20);
    const labor = Math.max(baseLabor, sales * laborRate);
    const fixed = otherFixed + labor;

    const contribution = sales * (1 - vr);
    const profit = contribution - fixed;

    // BEP: 최소인건비 구간과 인건비율 구간 중 실제로 성립하는 해
    let bep = Infinity;
    if (vr < 1) {
      const low = (baseLabor + otherFixed) / (1 - vr);
      if (laborRate <= 0 || low * laborRate <= baseLabor) bep = low;
      else if (1 - vr - laborRate > 0) bep = otherFixed / (1 - vr - laborRate);
    }

    const area = f(site.전용면적_평), deposit = f(site.보증금_만원);
    const interior = f(site.인테리어_만원) || area * f(iv.인테리어_평당_만원, 250);
    const sunk = interior + f(site.권리금_만원) + f(iv.장비_만원, 4500)
      + f(iv.가맹비_만원, 1000) + f(iv.교육비_만원, 300);

    return {
      월매출_만원: r2(sales), 변동비율: r2(vr, 4), 변동비_만원: r2(sales * vr),
      공헌이익_만원: r2(contribution), 인건비_만원: r2(labor), 임대료_만원: r2(rent + mgmt),
      고정비_만원: r2(fixed), 영업이익_만원: r2(profit),
      영업이익률: sales ? r2(profit / sales, 4) : 0,
      BEP월매출_만원: Number.isFinite(bep) ? r2(bep) : null,
      BEP달성률: Number.isFinite(bep) && bep ? r2(sales / bep, 3) : 0,
      초기투자_만원: r2(deposit + sunk), 회수대상투자_만원: r2(sunk), 보증금_만원: r2(deposit),
      투자회수_개월: profit > 0 ? r2(sunk / profit) : null,
    };
  }

  function risks(site, sc, rev, pnl) {
    const out = [];
    if (pnl.BEP월매출_만원 === null) {
      out.push('⛔ 구조적 적자 — 변동비+인건비율이 100% 이상이라 어떤 매출에서도 흑자 불가');
    } else if (pnl.BEP달성률 < 1.0) {
      out.push(`⛔ BEP 미달 — 추정 월매출이 손익분기(${ri(pnl.BEP월매출_만원).toLocaleString()}만원)의 ${ri(pnl.BEP달성률 * 100)}% 수준`);
    } else if (pnl.BEP달성률 < 1.15) {
      out.push('⚠ BEP 여유 15% 미만 — 매출 변동에 취약');
    }
    if (pnl.투자회수_개월 === null) out.push('⛔ 영업이익 적자 — 투자회수 불가');
    else if (pnl.투자회수_개월 > 36) out.push(`⚠ 투자회수 ${ri(pnl.투자회수_개월)}개월 (36개월 초과)`);
    const near = sc.경쟁.자사점_최근접_m;
    if (near !== null && near < 500) out.push(`⚠ 자사 기존점 ${near}m — 자기잠식 검토 필요`);
    if (sc.경쟁.동일포지션 >= 3) out.push(`⚠ 동일포지션 경쟁 ${sc.경쟁.동일포지션}곳 — 가격경쟁 심화 구간`);
    if (rev.좌석제약) out.push('ℹ 좌석 처리능력이 상한 — 매장 확장/테이크아웃 동선 검토 시 상향 여지');
    if (sc.항목.비용 <= 2) out.push('⚠ 평당 임대료 과다 — 임대조건 재협상 전제');
    return out;
  }

  function analyze(site, pois, brand) {
    const b = withDefaults(brand);
    const sc = scoreSite(site, pois, f(b.반경_m, 500));
    const rev = estimateRevenue(site, sc, b);
    const pnl = estimatePnl(site, rev, b);
    return Object.assign({}, sc, { 매출추정: rev, 손익: pnl, 리스크: risks(site, sc, rev, pnl) });
  }

  /* 심의 결론 — build_report.py 의 verdict() 와 같다.
     점수가 높아도 손익이 안 나오면 반려다. */
  function verdict(r) {
    const p = r.손익;
    if (p.투자회수_개월 === null || p.BEP달성률 < 1.0)
      return ['반려', '추정 손익 기준 적자 구간입니다. 임대조건 재협상 또는 후보 제외를 권고합니다.'];
    if (r.등급 === 'A' && p.투자회수_개월 <= 30)
      return ['출점 추천', '상권·손익 모두 기준을 충족합니다. 계약 조건 확정 후 진행하십시오.'];
    if (p.투자회수_개월 <= 36 && r.총점 >= 65)
      return ['조건부 추천', '임대조건·초기투자 축소를 전제로 진행 가능합니다.'];
    return ['보류', '회수기간 또는 상권 점수가 기준에 미달합니다. 조건 개선 시 재심의하십시오.'];
  }

  return {
    WEIGHTS, WEIGHT_KEYS, DEFAULTS, RIVAL_BRANDS, ANCHOR_BRANDS,
    f, i, yes, r2, ri, haversine, grade, withDefaults, competition, scoreSite,
    marketDemand, locationMultiplier, marketShare,
    estimateRevenue, variableRate, estimatePnl, risks, analyze, verdict, rentPerPyeong,
  };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = M;
