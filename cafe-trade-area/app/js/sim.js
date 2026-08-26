/* 손익 시뮬레이터 — 슬라이더를 움직이면 손익·BEP·회수기간이 즉시 다시 계산된다.
   estimate_revenue.py 와 같은 모델·같은 민감도 축을 쓴다. */
const Sim = (() => {

  /* 슬라이더 정의: [키, 라벨, min, max, step, 포맷] */
  const KNOBS = [
    ['ticket', '객단가', 3000, 9000, 100, v => `${U.num(v, 0)}원`],
    ['rent', '월임대료', 0, 1500, 10, v => `${U.num(v, 0)}만원`],
    ['seats', '좌석수', 0, 80, 1, v => `${v}석`],
    ['cogs', '재료비율', 0.20, 0.55, 0.005, v => U.pct(v)],
    ['labor', '인건비율', 0.08, 0.40, 0.005, v => U.pct(v)],
    ['boost', '매출 보정 (집객 가정)', 0.50, 1.50, 0.01, v => `×${v.toFixed(2)}`],
  ];

  let knobs = null;   // 현재 슬라이더 값 (후보지를 바꾸면 초기화)
  let forId = null;

  function baseline(site, brand) {
    return {
      ticket: M.f(brand.객단가_원, 5200),
      rent: M.f(site.월임대료_만원),
      seats: M.i(site.좌석수) || M.i(brand.좌석수_기본, 24),
      cogs: M.f(brand.변동비.재료비율, 0.35),
      labor: M.f(brand.고정비.인건비율, 0.20),
      boost: 1,
    };
  }

  /* 슬라이더 값을 반영한 (site, brand) 사본으로 재계산. 원본 데이터는 건드리지 않는다. */
  function compute(site, pois, brand, k) {
    const s = Object.assign({}, site, { 월임대료_만원: k.rent, 좌석수: k.seats });
    const b = M.withDefaults(Object.assign({}, brand, {
      객단가_원: k.ticket,
      변동비: Object.assign({}, brand.변동비, { 재료비율: k.cogs }),
      고정비: Object.assign({}, brand.고정비, { 인건비율: k.labor }),
    }));
    const sc = M.scoreSite(s, pois, M.f(b.반경_m, 500));
    const rev = M.estimateRevenue(s, sc, b);
    if (k.boost !== 1) {
      for (const key of ['일객수_추정', '일매출_만원', '월매출_만원']) rev[key] *= k.boost;
    }
    return { s, b, sc, rev, pnl: M.estimatePnl(s, rev, b) };
  }

  function pnlRows(p) {
    const line = (label, val, cls = '') =>
      `<div class="pl ${cls}"><span>${label}</span><span class="n">${U.num(val, 0)}</span></div>`;
    const other = p.고정비_만원 - p.인건비_만원 - p.임대료_만원;
    return line('매출', p.월매출_만원)
      + line(`(−) 변동비 · ${U.pct(p.변동비율)}`, -p.변동비_만원, 'sub')
      + line('공헌이익', p.공헌이익_만원, 'sub')
      + line('(−) 인건비', -p.인건비_만원, 'sub')
      + line('(−) 임대료·관리비', -p.임대료_만원, 'sub')
      + line('(−) 기타 고정비', -other, 'sub')
      + `<div class="pl total ${p.영업이익_만원 < 0 ? 'neg' : 'pos'}">
          <span>영업이익 (월, 만원)</span>
          <span class="n">${U.num(p.영업이익_만원, 0)} · ${U.pct(p.영업이익률)}</span></div>`;
  }

  /* 민감도 — CLI(estimate_revenue.py)와 같은 세 축, 같은 ±20% 구간. */
  const STEPS = [-0.2, -0.1, 0, 0.1, 0.2];
  function sensitivity(site, pois, brand, k) {
    const axes = [['매출 (객단가·집객)', 'boost'], ['임대료', 'rent'], ['재료비율', 'cogs']];
    const head = `<tr><th>변수 \\ 변동</th>${STEPS.map(d =>
      `<th class="num">${d ? (d > 0 ? '+' : '') + Math.round(d * 100) + '%' : '기준'}</th>`).join('')}</tr>`;
    const body = axes.map(([label, key]) => {
      const cells = STEPS.map(d => {
        const k2 = Object.assign({}, k, { [key]: k[key] * (1 + d) });
        const v = compute(site, pois, brand, k2).pnl.영업이익_만원;
        const style = v < 0 ? 'color:var(--no);font-weight:700' : d === 0 ? 'font-weight:800' : '';
        return `<td class="num" style="${style}">${U.num(v, 0)}</td>`;
      }).join('');
      return `<tr><td>${label}</td>${cells}</tr>`;
    }).join('');
    return `<div class="tablewrap"><table style="min-width:520px">
      <thead>${head}</thead><tbody>${body}</tbody></table></div>`;
  }

  function render() {
    const el = document.getElementById('sim-body');
    const site = S.current();
    if (!site) {
      el.innerHTML = `<div class="empty"><b>후보지를 먼저 추가하세요</b>
        후보지 탭에서 CSV 를 가져오거나 <b>데모 데이터</b> 를 눌러보세요.</div>`;
      return;
    }
    const brand = S.brand(), pois = S.get().pois;
    if (forId !== site.id || !knobs) { knobs = baseline(site, brand); forId = site.id; }

    const { sc, rev, pnl } = compute(site, pois, brand, knobs);
    const bepPct = Math.max(0, Math.min(140, (pnl.BEP달성률 || 0) * 100));
    const need = pnl.BEP월매출_만원
      ? pnl.BEP월매출_만원 * 10000 / rev.객단가_원 / M.f(brand.영업일수, 30) : null;

    el.innerHTML = `
      <div class="grid g2">
        <div class="card">
          <h3>가정 (${U.esc(site.후보지명 || '후보지')})</h3>
          <div class="sliders">${KNOBS.map(([k, lb, mn, mx, st, fmt]) => `
            <div class="slider">
              <span class="lb">${lb}</span><span class="out" id="out-${k}">${fmt(knobs[k])}</span>
              <input type="range" id="kn-${k}" min="${mn}" max="${mx}" step="${st}" value="${knobs[k]}"/>
            </div>`).join('')}</div>
          <p class="hint">슬라이더는 <b>가정만</b> 바꿉니다. 저장된 후보지 데이터는 그대로입니다.
            <button class="sm ghost" id="sim-reset" style="margin-left:6px">기준값으로</button></p>
        </div>

        <div class="card">
          <h3>추정 손익 (월)</h3>
          ${pnlRows(pnl)}
          <div style="margin-top:14px">
            <div style="display:flex;justify-content:space-between;font-size:12.5px;color:var(--fg-soft);font-weight:700">
              <span>손익분기 달성률</span><span>${U.pct(pnl.BEP달성률, 0)}</span></div>
            <div class="bepbar"><div class="fill ${pnl.BEP달성률 < 1 ? 'under' : ''}" style="width:${bepPct / 1.4}%"></div></div>
            <p class="hint" style="margin-top:2px">
              ${pnl.BEP월매출_만원 === null
                ? '변동비+인건비율이 100% 이상이라 어떤 매출에서도 흑자가 나지 않습니다.'
                : `BEP 월매출 <b>${U.won(pnl.BEP월매출_만원)}</b> = 하루 <b>${U.num(need, 0)}명</b>
                   (현재 추정 ${U.num(rev.일객수_추정, 0)}명)`}
            </p>
          </div>
          <div class="grid g2" style="margin-top:12px">
            <div class="kpi"><div class="k">투자회수</div>
              <div class="v">${pnl.투자회수_개월 === null ? '—' : U.num(pnl.투자회수_개월, 0)}<small>개월</small></div>
              <div class="d">회수대상 ${U.won(pnl.회수대상투자_만원)}</div></div>
            <div class="kpi"><div class="k">점유율</div>
              <div class="v">${U.pct(rev.점유율, 2)}</div>
              <div class="d">상권수요 ${U.num(rev.상권수요_일객수, 0)}명 ÷ 카페 ${rev.경쟁카페수}곳 × ${rev.입지배수}</div></div>
          </div>
        </div>
      </div>

      <div class="card" style="margin-top:14px">
        <h3>민감도 — 영업이익 (만원/월)</h3>
        ${sensitivity(site, pois, brand, knobs)}
        <p class="hint">한 변수만 ±20% 흔들었을 때의 영업이익입니다. 빨간 값은 적자 구간입니다.</p>
      </div>

      <div class="card" style="margin-top:14px">
        <h3>리스크</h3>
        ${Sites.riskList(M.risks(site, sc, rev, pnl))}
      </div>`;

    KNOBS.forEach(([k, , , , , fmt]) => {
      const input = document.getElementById(`kn-${k}`);
      input.oninput = () => {
        knobs[k] = parseFloat(input.value);
        document.getElementById(`out-${k}`).textContent = fmt(knobs[k]);
      };
      // 드래그가 끝난 뒤에만 전체를 다시 그린다(끌 때마다 리렌더하면 손잡이를 놓친다)
      input.onchange = render;
    });
    document.getElementById('sim-reset').onclick = () => { knobs = null; render(); };
  }

  return { render, invalidate: () => { knobs = null; forId = null; }, compute, baseline };
})();
