/* 탭 전환·대시보드·브랜드 설정·백업. 화면 전체의 진입점. */
const App = (() => {
  const TABS = ['dash', 'sites', 'map', 'sim', 'report', 'settings'];
  let tab = 'dash';

  // ── 대시보드 ──────────────────────────────
  function renderDash() {
    const rows = S.analyzed();
    const kpi = document.getElementById('kpis');
    if (!rows.length) {
      kpi.innerHTML = '';
      document.getElementById('dash-body').innerHTML =
        `<div class="empty"><b>아직 후보지가 없습니다</b>
          상단 <b>데모 데이터</b> 로 전체 흐름을 먼저 눌러보거나,
          <b>후보지</b> 탭에서 CSV 를 가져오세요.</div>`;
      return;
    }
    const best = rows[0];
    const pass = rows.filter(({ r }) => ['출점 추천', '조건부 추천'].includes(M.verdict(r)[0]));
    const paybacks = rows.map(({ r }) => r.손익.투자회수_개월).filter(v => v !== null);
    const medPay = paybacks.length
      ? paybacks.slice().sort((a, b) => a - b)[Math.floor(paybacks.length / 2)] : null;

    kpi.innerHTML = `
      <div class="kpi"><div class="k">후보지</div><div class="v">${rows.length}<small>곳</small></div>
        <div class="d">POI ${S.get().pois.length}건 반영</div></div>
      <div class="kpi"><div class="k">심의 통과</div><div class="v">${pass.length}<small>곳</small></div>
        <div class="d">추천 + 조건부 추천</div></div>
      <div class="kpi"><div class="k">최고 점수</div><div class="v">${best.r.총점}<small>점</small></div>
        <div class="d">${U.esc(best.r.후보지명)} · ${best.r.등급}등급</div></div>
      <div class="kpi"><div class="k">투자회수 중앙값</div>
        <div class="v">${medPay === null ? '—' : U.num(medPay, 0)}<small>개월</small></div>
        <div class="d">흑자 후보지 ${paybacks.length}곳 기준</div></div>`;

    const byGrade = ['A', 'B', 'C', 'D'].map(g => ({
      g, n: rows.filter(({ r }) => r.등급 === g).length,
    }));
    const byStage = Sites.STAGES.map(s => ({
      s, n: S.sites().filter(x => (x.상태 || '검토') === s).length,
    }));

    document.getElementById('dash-body').innerHTML = `
      <div class="card"><h3>등급 분포</h3><div class="pipe">${
        byGrade.map(({ g, n }) => `<div class="step">
          <b><span class="grade ${g}" style="display:inline-grid;vertical-align:-4px">${g}</span> ${n}</b>
          <span>${g === 'A' ? '즉시 검토' : g === 'B' ? '조건부' : g === 'C' ? '보류' : '부적합'}</span>
        </div>`).join('')}</div></div>

      <div class="card"><h3>진행 단계</h3><div class="pipe">${
        byStage.map(({ s, n }) => `<div class="step"><b>${n}</b><span>${s}</span></div>`).join('')
      }</div></div>

      <div class="grid g2" style="margin-top:14px">
        <div class="card"><h3>다음 액션</h3><div id="next-actions"></div></div>
        <div class="card"><h3>상위 후보지</h3>${
          rows.slice(0, 5).map(({ site, r }) => {
            const [v] = M.verdict(r);
            return `<div class="todo">
              <span class="n">${r.총점}</span>
              <div><div class="t">${U.esc(r.후보지명)}</div>
                <div class="s">${v} · 월 ${U.won(r.손익.월매출_만원)} · 영업이익 ${U.won(r.손익.영업이익_만원)}</div></div>
              <button class="sm go" data-open="${site.id}">열기</button></div>`;
          }).join('')
        }</div>
      </div>`;

    // QUICKSTART 순서를 그대로 따르는 다음 액션 — 이미 한 일은 지운다
    const done = {
      sites: rows.length > 0,
      pois: S.get().pois.length > 0,
      brand: Object.keys(S.get().brand).length > 0,
      survey: S.sites().some(x => ['실사완료', '협상중', '계약'].includes(x.상태)),
      close: S.sites().some(x => x.상태 === '계약'),
    };
    const steps = [
      ['후보지 수집', '20~30곳을 CSV 로 올리거나 직접 추가', done.sites, 'sites'],
      ['경쟁 POI 수집', '반경 내 카페 목록 — collect_pois.py --live 또는 CSV 가져오기', done.pois, 'sites'],
      ['브랜드 파라미터 확정', '객단가·원가율·초기투자를 실제 값으로', done.brand, 'settings'],
      ['상위 후보지 현장 실사', '주차·동선·간판 가시성은 사람이 봐야 한다', done.survey, 'sites'],
      ['임대조건 협상 → 출점 결정', '민감도에서 임대료가 얼마까지 버티는지 확인', done.close, 'sim'],
    ];
    document.getElementById('next-actions').innerHTML = steps.map(([t, s, ok, go], i) =>
      `<div class="todo ${ok ? 'done' : ''}"><span class="n">${ok ? '✓' : i + 1}</span>
        <div><div class="t">${t}</div><div class="s">${s}</div></div>
        <button class="sm go" data-go="${go}">이동</button></div>`).join('');

    document.querySelectorAll('[data-go]').forEach(b => b.onclick = () => go(b.dataset.go));
    document.querySelectorAll('[data-open]').forEach(b => b.onclick = () => {
      S.select(b.dataset.open); go('sites');
    });
  }

  // ── 상권 지도 탭 ───────────────────────────
  function renderMap() {
    const el = document.getElementById('map-body');
    const site = S.current();
    if (!site) {
      el.innerHTML = `<div class="empty"><b>후보지를 먼저 추가하세요</b></div>`;
      return;
    }
    const rows = S.analyzed();
    el.innerHTML = `
      <div class="panel-head">
        <div><h3>${U.esc(site.후보지명 || '후보지')}</h3>
          <p>후보지를 원점에 두고 반경 내 경쟁을 실제 거리로 배치한 평면도입니다.</p></div>
        <div class="acts"><label class="field" style="margin:0;min-width:200px">
          <span>후보지 선택</span>
          <select id="map-pick">${rows.map(({ site: s, r }) =>
            `<option value="${s.id}" ${s.id === site.id ? 'selected' : ''}>${U.esc(r.후보지명)} (${r.등급} ${r.총점})</option>`
          ).join('')}</select></label></div>
      </div>
      <div id="map-canvas"></div>`;
    TAMap.render(document.getElementById('map-canvas'), site, S.get().pois, M.f(S.brand().반경_m, 500));
    document.getElementById('map-pick').onchange = e => { S.select(e.target.value); render(); };
  }

  // ── 브랜드 설정 탭 ─────────────────────────
  const SETTINGS = [
    ['브랜드', '브랜드명', 'text', null],
    ['객단가_원', '객단가(원)', 'number', null],
    ['영업일수', '월 영업일수', 'number', null],
    ['영업시간', '일 영업시간', 'number', null],
    ['좌석수_기본', '기본 좌석수', 'number', null],
    ['테이크아웃_비중', '테이크아웃 비중(0~1)', 'number', null],
    ['반경_m', '상권 반경(m)', 'number', null],
    ['재료비율', '재료비율(0~1)', 'number', '변동비'],
    ['카드수수료율', '카드수수료율', 'number', '변동비'],
    ['로열티율', '로열티율', 'number', '변동비'],
    ['광고분담금율', '광고분담금율', 'number', '변동비'],
    ['최소인건비_월_만원', '최소 인건비(만원/월)', 'number', '고정비'],
    ['인건비율', '인건비율(매출 대비)', 'number', '고정비'],
    ['수도광열_월_만원', '수도광열(만원/월)', 'number', '고정비'],
    ['소모품_월_만원', '소모품(만원/월)', 'number', '고정비'],
    ['기타_월_만원', '기타 고정비(만원/월)', 'number', '고정비'],
    ['인테리어_평당_만원', '인테리어(만원/평)', 'number', '초기투자'],
    ['장비_만원', '장비(만원)', 'number', '초기투자'],
    ['가맹비_만원', '가맹비(만원)', 'number', '초기투자'],
    ['교육비_만원', '교육비(만원)', 'number', '초기투자'],
  ];

  function renderSettings() {
    const b = S.brand();
    const val = (k, grp) => (grp ? b[grp][k] : b[k]) ?? '';
    const groups = [null, '변동비', '고정비', '초기투자'];
    const titles = { null: '기본', 변동비: '변동비 (매출 비례)', 고정비: '고정비 (월)', 초기투자: '초기투자' };

    document.getElementById('set-body').innerHTML = groups.map(g => `
      <div class="card"><h3>${titles[g]}</h3><div class="grid g4">${
        SETTINGS.filter(([, , , grp]) => grp === g).map(([k, lb, t, grp]) =>
          `<label class="field"><span>${lb}</span>
            <input data-k="${k}" data-g="${grp || ''}" type="${t}" step="any" value="${U.esc(val(k, grp))}"/></label>`
        ).join('')}</div></div>`).join('')
      + `<div class="card"><h3>YAML 내보내기</h3>
          <p class="hint" style="margin-top:0">여기서 정한 값을 <code>analysis/brand.yaml</code> 로 저장하면
            CLI(<code>score_sites.py --brand brand.yaml</code>)가 같은 기준으로 계산합니다.</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="primary" id="set-save">저장</button>
            <button id="set-yaml">brand.yaml 내려받기</button>
            <button class="ghost danger" id="set-default">기본값으로</button>
          </div></div>`;

    document.getElementById('set-save').onclick = () => {
      const patch = {}, sub = { 변동비: {}, 고정비: {}, 초기투자: {} };
      document.querySelectorAll('#set-body [data-k]').forEach(i => {
        const raw = i.value.trim();
        if (raw === '') return;
        const v = i.type === 'number' ? parseFloat(raw) : raw;
        if (i.dataset.g) sub[i.dataset.g][i.dataset.k] = v; else patch[i.dataset.k] = v;
      });
      S.setBrand(Object.assign(patch, sub));
      Sim.invalidate();
      U.toast('브랜드 설정을 저장했습니다');
      render();
    };
    document.getElementById('set-default').onclick = () => {
      if (!confirm('브랜드 설정을 기본값으로 되돌릴까요?')) return;
      S.get().brand = {};
      S.setBrand({});
      Sim.invalidate();
      render();
    };
    document.getElementById('set-yaml').onclick = () => {
      U.download('brand.yaml', toYaml(S.brand()), 'text/yaml');
      U.toast('brand.yaml 을 내려받았습니다');
    };
  }

  /* 최소 YAML 직렬화 — 브랜드 설정은 문자열·숫자·1단계 중첩뿐이라 이걸로 충분하다. */
  function toYaml(o) {
    const line = (k, v) => `${k}: ${typeof v === 'string' ? v : v}`;
    const out = ['# 상권 분석 콘솔에서 내보낸 브랜드 파라미터',
      '# analysis/ 에 두고: python score_sites.py --brand brand.yaml'];
    for (const [k, v] of Object.entries(o)) {
      if (v && typeof v === 'object') {
        out.push(`${k}:`);
        for (const [k2, v2] of Object.entries(v)) out.push(`  ${line(k2, v2)}`);
      } else out.push(line(k, v));
    }
    return out.join('\n') + '\n';
  }

  // ── 탭 ───────────────────────────────────
  function go(next) {
    if (!TABS.includes(next)) return;
    tab = next;
    document.querySelectorAll('.tab').forEach(b =>
      b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
    TABS.forEach(t => document.getElementById(`panel-${t}`).classList.toggle('hide', t !== tab));
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function render() {
    document.getElementById('pill-sites').textContent = S.sites().length;
    const cur = S.current();
    document.getElementById('pill-map').textContent = S.get().pois.length;
    if (tab === 'dash') renderDash();
    else if (tab === 'sites') Sites.render();
    else if (tab === 'map') renderMap();
    else if (tab === 'sim') Sim.render();
    else if (tab === 'report') Report.render();
    else if (tab === 'settings') renderSettings();
    const label = document.getElementById('cur-site');
    if (label) label.textContent = cur ? cur.후보지명 : '—';
  }

  function init() {
    document.querySelectorAll('.tab').forEach(b => b.onclick = () => go(b.dataset.tab));
    Sites.init();

    document.getElementById('btn-demo').onclick = () => {
      if (S.sites().length && !confirm('현재 데이터를 지우고 데모 데이터를 넣을까요?')) return;
      S.demo(); Sim.invalidate(); U.toast('데모 데이터를 넣었습니다'); go('dash');
    };
    document.getElementById('btn-backup').onclick = () => {
      U.download(`상권분석_백업_${U.today()}.json`, S.exportAll(), 'application/json');
      U.toast('백업 파일을 내려받았습니다');
    };
    document.getElementById('btn-restore').onclick = () => U.pickFile('.json,application/json', text => {
      try {
        S.restore(text); Sim.invalidate(); U.toast('복원했습니다'); go('dash');
      } catch (e) {
        U.toast(`복원 실패: ${e.message}`);
      }
    });
    document.getElementById('btn-reset').onclick = () => {
      if (!confirm('모든 후보지·POI·설정을 지웁니다. 되돌릴 수 없습니다. 계속할까요?')) return;
      S.reset(); Sim.invalidate(); U.toast('초기화했습니다'); go('dash');
    };

    go('dash');
  }

  return { init, go, render };
})();

document.addEventListener('DOMContentLoaded', App.init);
