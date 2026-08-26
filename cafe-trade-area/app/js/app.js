/* 콘솔 — 파이프라인 산출(심의결과.json)을 읽어 심의 자료로 보여주고,
   M5 판정 산술만 브라우저에서 다시 계산한다.

   여기서 하지 않는 것: M1 등시선·M2 격자교차·M3 Huff·M4 회귀.
   그 넷은 OSM 보행 네트워크·통계청 격자·기존점 실적이 있어야 하며,
   브라우저에서 흉내내면 CLI 와 다른 숫자를 내는 것이 유일한 결과다. */
const App = (() => {
  const TABS = ['status', 'sites', 'sim', 'data'];
  let tab = 'status';
  let picked = null;
  let knobs = null;

  const V = { 통과: 'ok', 보류: 'hold', 부결: 'no' };
  const MARK = { 통과: '○', 보류: '△', 부결: '✕' };

  const settings = () => S.settings();
  const gov = () => (settings().거버넌스 || {});

  // ── 심의 현황 ─────────────────────────────
  function renderStatus() {
    const el = document.getElementById('p-status');
    if (!S.has()) { el.innerHTML = empty(); wireEmpty(); return; }
    const d = S.get(), rows = S.sites();
    const cnt = { 통과: 0, 보류: 0, 부결: 0 };
    rows.forEach(r => cnt[r.판정.판정]++);
    const m = d.모델 || {};
    const modeA = d.모드 === 'A' && m.표본수;

    el.innerHTML = `
      ${banner()}
      <div class="grid g4">
        <div class="kpi"><div class="k">후보지</div><div class="v">${rows.length}<small>곳</small></div>
          <div class="d">심의 대상</div></div>
        <div class="kpi"><div class="k">통과 / 보류 / 부결</div>
          <div class="v">${cnt.통과} <small>/</small> ${cnt.보류} <small>/</small> ${cnt.부결}</div>
          <div class="d">M5 3단 판정</div></div>
        <div class="kpi"><div class="k">추정 모드</div><div class="v">${d.모드}</div>
          <div class="d">${modeA ? `회귀 · 표본 ${m.표본수}` : '앵커링 · 표본 15개 미만'}</div></div>
        <div class="kpi"><div class="k">${modeA ? '모델 MAPE' : '예측구간'}</div>
          <div class="v">${modeA ? U.pct((m.CV || {}).MAPE || 0, 1) : '±' + U.pct(0.25, 0)}</div>
          <div class="d">${modeA ? `${(m.CV || {}).방식 || ''} · R² ${U.num(m.R2, 3)}` : '미검증 가정값'}</div></div>
      </div>

      <div class="card" style="margin-top:14px">
        <h3>판정</h3>
        <div class="tablewrap"><table>
          <thead><tr><th>판정</th><th>후보지</th><th class="num">S</th><th class="num">월매출(중앙)</th>
            <th class="num">BEP</th><th class="num">margin</th><th class="num">중첩</th><th>사유</th></tr></thead>
          <tbody>${rows.map(rowHtml).join('')}</tbody>
        </table></div>
      </div>

      ${warnCard()}`;
    wireOpen();
  }

  const banner = () => `<div class="gov">
      <b>${U.esc(gov().문서등급 || '사내 한정 · 대외 배포 금지')}</b>
      <span>${U.esc((gov().고지 || '').trim())}</span></div>`;

  function rowHtml(r) {
    const j = r.판정, p = r.매출 || {};
    return `<tr data-open="${U.esc(r.이름)}">
      <td><span class="vd ${V[j.판정]}">${MARK[j.판정]} ${j.판정}</span></td>
      <td><b>${U.esc(r.이름)}</b><div class="why">${U.esc(r.입력.주소 || '')}</div></td>
      <td class="num">${U.num(r.S, 1)}</td>
      <td class="num">${U.num(p.월매출_중앙, 0)}</td>
      <td class="num">${U.num(j.BEP_만원, 0)}</td>
      <td class="num ${(j.margin ?? 0) < 0.15 ? 'neg' : ''}">${U.pct(j.margin || 0, 1)}</td>
      <td class="num">${U.pct(j.카니발.최대_overlap, 0)}</td>
      <td class="why">${U.esc(j.사유.join('; ') || '—')}</td>
    </tr>`;
  }

  function warnCard() {
    const w = S.warnings();
    if (!w.length) return '';
    return `<div class="card" style="margin-top:14px"><h3>데이터 경고 ${w.length}건</h3>
      <p class="hint" style="margin-top:0">어떤 입력이 비어 있는지가 판정의 신뢰도를 정합니다.</p>
      <div class="risks">${w.map(x => `<div class="risk ${x.경고.startsWith('⛔') ? 'high' : 'warn'}">
        ${U.esc(x.경고)}<span class="who">${U.esc(x.대상.join(' · '))}</span></div>`).join('')}</div></div>`;
  }

  // ── 후보지 상세 ───────────────────────────
  function renderSites() {
    const el = document.getElementById('p-sites');
    if (!S.has()) { el.innerHTML = empty(); wireEmpty(); return; }
    const r = S.find(picked);
    const j = r.판정, p = r.매출 || {}, a = r.상권, d = r.수요, c = r.경쟁;

    el.innerHTML = `
      ${banner()}
      <div class="panel-head">
        <div><h3>${U.esc(r.이름)}</h3><p>${U.esc(r.입력.주소 || '')}</p></div>
        <div class="acts"><label class="field" style="margin:0;min-width:230px"><span>후보지</span>
          <select id="pick">${S.sites().map(x =>
            `<option ${x.이름 === r.이름 ? 'selected' : ''}>${U.esc(x.이름)}</option>`).join('')}</select>
        </label></div>
      </div>

      <div class="verdictbox ${V[j.판정]}">
        <b>${MARK[j.판정]} ${j.판정}</b>
        <div>${j.사유.length ? j.사유.map(U.esc).join(' · ') : '부결·보류 조건에 해당하지 않습니다'}</div>
      </div>

      <div class="grid g2" style="margin-top:14px">
        <div class="card"><h3>M1 상권 · M2 수요</h3>
          ${kv([
            ['P10 면적', `${U.num(a.P10_면적_m2 / 10000, 1)}ha`],
            ['잔존율 R', U.num(a.R, 2)],
            ['등시선 출처', a.출처],
            ['H (배후 세대)', U.num(d.H, 0)],
            ['W (직장인구)', U.num(d.W, 0)],
            ['D_am', U.num(d.D_am, 0)],
            ['D_am_adj', `<b>${U.num(d.D_am_adj, 0)}</b> (같은편 ${U.num(d.D_am_같은편, 0)} + 반대편 ${U.num(d.D_am_반대편, 0)} × ${d.횡단저항})`],
            ['D_all', U.num(d.D_all, 0)],
          ])}</div>
        <div class="card"><h3>M3 경쟁 · M4 매출</h3>
          ${kv([
            ['Huff 점유율 S', `<b>${U.pct(c.S, 2)}</b>`],
            ['λ (거리 마찰)', `${c.λ} <span class="tagx">미검증</span>`],
            ['반경 내 경쟁', `${c.반경내_경쟁}곳 (동일가격대 ${c.동일가격대_수} · 저가형 ${c.저가형_수})`],
            ['추정 모드', p.모드 || '—'],
            ['월매출 하한', U.num(p.월매출_하한, 0)],
            ['월매출 중앙', `<b>${U.num(p.월매출_중앙, 0)}만원</b> — 심의 기준값`],
            ['월매출 상한', U.num(p.월매출_상한, 0)],
          ])}</div>
      </div>

      <div class="grid g2" style="margin-top:14px">
        <div class="card"><h3>M5 판정</h3>
          ${kv([
            ['고정비 F', `${U.num(j.고정비.F, 0)}만원`],
            ['변동비율 v', U.pct(j.변동비율, 1)],
            ['BEP', `${U.num(j.BEP_만원, 0)}만원`],
            ['margin', U.pct(j.margin || 0, 1)],
            ['margin_low', U.pct(j.margin_low || 0, 1)],
            ['S', `${U.num(j.S, 1)} / 100`],
            ['최대 중첩', U.pct(j.카니발.최대_overlap, 0)],
            ['잠식 추정', `${U.num(j.카니발.잠식액_합_만원, 0)}만원/월 (κ=${j.카니발['κ']})`],
            ['순증 월매출', `${U.num(j.순증_월매출_만원, 0)}만원`],
          ])}</div>
        <div class="card"><h3>치명 플래그 · 비고</h3>
          <div class="risks">
            ${j.치명플래그.length
              ? j.치명플래그.map(x => `<div class="risk high">⛔ ${U.esc(x)}</div>`).join('')
              : '<div class="risk">치명 플래그 해당 없음</div>'}
            ${j.치명_미확인.map(x => `<div class="risk warn">미확인 — ${U.esc(x)}</div>`).join('')}
            ${j.비고.map(x => `<div class="risk ${x.startsWith('⛔') ? 'high' : ''}">${U.esc(x)}</div>`).join('')}
            ${(r.경고 || []).map(x => `<div class="risk ${x.startsWith('⛔') ? 'high' : 'warn'}">${U.esc(x)}</div>`).join('')}
          </div>
          <h3 style="margin-top:16px">S 배점</h3>
          ${kv(Object.entries(r.S_축 || {}).map(([k, v]) => [k, U.num(v, 1)]))}
          <p class="hint">실증 회귀가 아닌 임의 배점입니다. 후보지 간 상대 비교로만 쓰십시오.</p>
        </div>
      </div>`;

    document.getElementById('pick').onchange = e => { picked = e.target.value; render(); };
  }

  const kv = pairs => `<div class="kv">${pairs.map(([k, v]) =>
    `<div><span>${U.esc(k)}</span><b>${v}</b></div>`).join('')}</div>`;

  // ── 손익 시뮬 (M5 재계산) ──────────────────
  const KNOBS = [
    ['rent', '월임대료', 0, 1500, 10, v => `${U.num(v, 0)}만원`],
    ['sales', '월매출(중앙)', 500, 12000, 50, v => `${U.num(v, 0)}만원`],
    ['lowRatio', '하한/중앙 비율', 0.5, 1.0, 0.01, v => v.toFixed(2)],
    ['cogs', '원재료율', 0.2, 0.55, 0.005, v => U.pct(v, 1)],
    ['labor', '고정인건비', 0, 1500, 10, v => `${U.num(v, 0)}만원`],
  ];

  function baseKnobs(r) {
    const st = settings(), fx = ((st.운영 || {}).고정비) || {}, vb = ((st.운영 || {}).변동비) || {};
    const p = r.매출 || {};
    return {
      rent: M5.f(r.입력.월임대료_만원),
      sales: p.월매출_중앙 || 0,
      lowRatio: p.월매출_중앙 ? (p.월매출_하한 / p.월매출_중앙) : 0.8,
      cogs: M5.f(vb.원재료율, 0.35),
      labor: M5.f(fx.고정인건비_월_만원, 620),
    };
  }

  function simJudge(r, k) {
    const st = settings();
    const site = { ...r.입력, 월임대료_만원: k.rent };
    const cfg = {
      운영: {
        변동비: { ...((st.운영 || {}).변동비 || {}), 원재료율: k.cogs },
        고정비: { ...((st.운영 || {}).고정비 || {}), 고정인건비_월_만원: k.labor },
      },
    };
    const rev = { 월매출_중앙: k.sales, 월매출_하한: k.sales * k.lowRatio };
    const ov = (r.판정.카니발.상세 || []).map(x => ({ ...x }));
    return M5.judge(site, rev, cfg, r.S, ov, S.kappa(), r.S_풀최대);
  }

  function renderSim() {
    const el = document.getElementById('p-sim');
    if (!S.has()) { el.innerHTML = empty(); wireEmpty(); return; }
    const r = S.find(picked);
    if (!knobs || knobs._for !== r.이름) knobs = { ...baseKnobs(r), _for: r.이름 };
    const j = simJudge(r, knobs);
    const base = r.판정;

    el.innerHTML = `
      ${banner()}
      <div class="panel-head">
        <div><h3>손익 시뮬레이션 — ${U.esc(r.이름)}</h3>
          <p>M5 판정 산술만 다시 계산합니다. 상권·수요·경쟁(M1~M3)은 파이프라인 값을 그대로 씁니다.</p></div>
        <div class="acts"><button class="sm ghost" id="sim-reset">기준값으로</button></div>
      </div>
      <div class="grid g2">
        <div class="card"><h3>협상 가정</h3>
          <div class="sliders">${KNOBS.map(([k, lb, mn, mx, st, fmt]) => `
            <div class="slider"><span class="lb">${lb}</span>
              <span class="out" id="o-${k}">${fmt(knobs[k])}</span>
              <input type="range" id="k-${k}" min="${mn}" max="${mx}" step="${st}" value="${knobs[k]}"/>
            </div>`).join('')}</div>
          <p class="hint">가정만 바꿉니다. 저장된 심의결과는 그대로입니다.</p>
        </div>
        <div class="card"><h3>재판정</h3>
          <div class="verdictbox ${V[j.판정]}" style="margin:0 0 12px">
            <b>${MARK[j.판정]} ${j.판정}</b>
            <div>${j.사유.length ? j.사유.map(U.esc).join(' · ') : '조건 충족'}</div>
          </div>
          ${kv([
            ['고정비 F', `${U.num(j.고정비.F, 0)}만원`],
            ['변동비율 v', U.pct(j.변동비율, 1)],
            ['BEP', `${U.num(j.BEP_만원, 0)}만원`],
            ['margin', `${U.pct(j.margin || 0, 1)} <span class="delta">(기준 ${U.pct(base.margin || 0, 1)})</span>`],
            ['margin_low', U.pct(j.margin_low || 0, 1)],
          ])}
          <p class="hint">임대료가 얼마까지 버티는지 확인한 뒤 협상 카드로 쓰십시오.
            치명 플래그는 슬라이더로 사라지지 않습니다.</p>
        </div>
      </div>`;

    KNOBS.forEach(([k, , , , , fmt]) => {
      const inp = document.getElementById(`k-${k}`);
      inp.oninput = () => { knobs[k] = parseFloat(inp.value);
                            document.getElementById(`o-${k}`).textContent = fmt(knobs[k]); };
      inp.onchange = renderSim;
    });
    document.getElementById('sim-reset').onclick = () => { knobs = null; renderSim(); };
  }

  // ── 데이터·계수 ───────────────────────────
  const UNVALIDATED = [
    ['거리마찰_람다', 2.2, 'Huff 거리 마찰계수 — 실적으로 반드시 캘리브레이션'],
    ['횡단저항', 0.3, '반대편 유동인구의 유효 반영률 — 실측 캘리브레이션 필요'],
    ['잠식계수_카파', 0.5, '중첩 상권 내 자사 점포 간 수요 분할률'],
    ['보행우회계수', 1.3, '보행 네트워크 거리 미확보 시 직선거리에 곱하는 우회율'],
    ['흡인력_좌석지수', 0.5, 'A = 좌석수^0.5 × 브랜드가중'],
    ['경사_배제_퍼센트', 10.0, '이 경사를 넘는 링크는 barrier 처리'],
    ['ModeB_예측구간_폭', 0.25, 'Mode B 는 잔차 표본이 없어 구간을 만들 수 없다'],
  ];

  function renderData() {
    const d = S.get();
    document.getElementById('p-data').innerHTML = `
      ${banner()}
      <div class="card"><h3>불러오기</h3>
        <p class="hint" style="margin-top:0">이 콘솔은 파이프라인이 만든
          <code>analysis/output/심의결과.json</code> 을 읽습니다.
          모델을 다시 계산하지 않으므로 CLI 와 숫자가 어긋나지 않습니다.</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="primary" id="btn-file">심의결과.json 열기</button>
          <button id="btn-fetch">output/ 에서 불러오기</button>
          <button class="ghost" id="btn-demo2">예시 결과</button>
          <button class="ghost danger" id="btn-clear">비우기</button>
        </div>
        ${d ? `<p class="hint">현재: 후보지 ${d.후보지.length}곳 · 모드 ${d.모드} · 생성 ${U.esc(d.생성 || '')}</p>` : ''}
      </div>

      <div class="card"><h3>미검증 계수</h3>
        <p class="hint" style="margin-top:0">실증 근거가 아닌 실무 판단 초기값입니다.
          M6 사후 보정 루프(<code>calibrate.py</code>)로 순차 교정해야 합니다.</p>
        <div class="tablewrap"><table><thead><tr><th>계수</th><th class="num">값</th><th>설명</th></tr></thead>
          <tbody>${UNVALIDATED.map(([k, v, w]) =>
            `<tr><td><code>${k}</code></td><td class="num">${v}</td><td class="why">${U.esc(w)}</td></tr>`).join('')}
          </tbody></table></div>
      </div>

      <div class="card"><h3>콘솔이 계산하지 않는 것</h3>
        <p class="hint" style="margin-top:0">M1 등시선 · M2 격자 교차 · M3 Huff · M4 회귀는
          OSM 보행 네트워크, 통계청 격자 인구, 기존점 실적이 있어야 합니다. 브라우저에서
          흉내내면 CLI 와 다른 숫자를 내는 것이 유일한 결과이므로 재현하지 않습니다.
          콘솔이 다시 계산하는 것은 <b>M5 판정 산술</b>뿐이며,
          <code>analysis/tests/test_m5_parity.py</code> 가 두 구현을 대조합니다.</p>
      </div>`;
    wireLoaders();
  }

  // ── 공통 ─────────────────────────────────
  const empty = () => `${banner()}<div class="empty"><b>심의결과가 없습니다</b>
    <code>cd analysis && python3 review_sites.py</code> 로 만든
    <code>output/심의결과.json</code> 을 불러오세요.
    <div style="margin-top:16px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
      <button class="primary" id="e-file">파일 열기</button>
      <button id="e-fetch">output/ 에서 불러오기</button>
      <button class="ghost" id="e-demo">예시 결과 보기</button>
    </div></div>`;

  function loadFile() {
    U.pickFile('.json,application/json', text => {
      try { S.set(JSON.parse(text)); U.toast('심의결과를 불러왔습니다'); render(); }
      catch (e) { U.toast(`불러오기 실패: ${e.message}`); }
    });
  }

  async function loadFetch() {
    try {
      const res = await fetch('../analysis/output/심의결과.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      S.set(await res.json());
      U.toast('output/ 에서 불러왔습니다');
      render();
    } catch (e) {
      U.toast('불러오지 못했습니다. file:// 로 열었다면 "파일 열기"를 쓰세요.');
    }
  }

  function wireEmpty() {
    const b = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
    b('e-file', loadFile); b('e-fetch', loadFetch);
    b('e-demo', () => { S.demo(); U.toast('예시 결과를 넣었습니다'); render(); });
  }

  function wireLoaders() {
    const b = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
    b('btn-file', loadFile); b('btn-fetch', loadFetch);
    b('btn-demo2', () => { S.demo(); U.toast('예시 결과를 넣었습니다'); render(); });
    b('btn-clear', () => {
      if (!confirm('불러온 심의결과를 비웁니다. 계속할까요?')) return;
      S.clear(); knobs = null; U.toast('비웠습니다'); render();
    });
  }

  function wireOpen() {
    document.querySelectorAll('[data-open]').forEach(tr => tr.onclick = () => {
      picked = tr.dataset.open; go('sites');
    });
  }

  function go(next) {
    if (!TABS.includes(next)) return;
    tab = next;
    document.querySelectorAll('.tab').forEach(b =>
      b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
    TABS.forEach(t => document.getElementById(`p-${t}`).classList.toggle('hide', t !== tab));
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function render() {
    document.getElementById('pill-sites').textContent = S.sites().length;
    if (tab === 'status') renderStatus();
    else if (tab === 'sites') renderSites();
    else if (tab === 'sim') renderSim();
    else renderData();
  }

  function init() {
    document.querySelectorAll('.tab').forEach(b => b.onclick = () => go(b.dataset.tab));
    document.getElementById('btn-demo').onclick = () => {
      S.demo(); knobs = null; U.toast('예시 결과를 넣었습니다'); go('status');
    };
    go('status');
  }

  return { init, go, render };
})();

document.addEventListener('DOMContentLoaded', App.init);
