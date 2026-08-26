/* 후보지 탭 — 목록·점수·편집. 계산은 전부 model.js(=common.py) 가 한다. */
const Sites = (() => {

  /* 후보지 편집 폼에 노출할 필드. [키, 라벨, 입력타입] */
  const FIELDS = [
    ['후보지명', '후보지명', 'text'], ['주소', '주소', 'text'],
    ['위도', '위도', 'number'], ['경도', '경도', 'number'],
    ['전용면적_평', '전용면적(평)', 'number'], ['좌석수', '좌석수', 'number'],
    ['층', '층', 'number'], ['코너여부', '코너(Y/N)', 'text'],
    ['전면길이_m', '전면길이(m)', 'number'], ['주차가능대수', '주차(대)', 'number'],
    ['보증금_만원', '보증금(만원)', 'number'], ['월임대료_만원', '월임대료(만원)', 'number'],
    ['관리비_만원', '관리비(만원)', 'number'], ['권리금_만원', '권리금(만원)', 'number'],
    ['지하철역명', '최근접역', 'text'], ['지하철_도보분', '역 도보(분)', 'number'],
    ['지하철_일평균승하차', '역 일평균 승하차', 'number'],
    ['주거인구_500m', '주거인구(반경)', 'number'], ['직장인구_500m', '직장인구(반경)', 'number'],
    ['유동인구_일평균', '유동인구(일평균)', 'number'], ['아파트세대수', '아파트 세대수', 'number'],
    ['대학_학원수', '대학·학원 수', 'number'], ['오피스빌딩수', '오피스빌딩 수', 'number'],
    ['카페수_500m', '반경 내 카페수(조사)', 'number'],
    ['동일포지션_경쟁수', '동일포지션 경쟁수', 'number'],
  ];

  const STAGES = ['검토', '실사예정', '실사완료', '협상중', '계약', '제외'];

  const gradeChip = r => `<span class="grade ${r.등급}">${r.등급}</span>`;

  function miniBar(pts, full) {
    const pc = Math.max(0, Math.min(100, pts / full * 100));
    const cls = pc >= 70 ? 'hi' : pc >= 40 ? 'mid' : 'lo';
    return `<span class="sbar"><span class="track"><span class="fill ${cls}" style="width:${pc}%"></span></span></span>`;
  }

  function scoreRows(r) {
    return M.WEIGHT_KEYS.map((k, i) => {
      const pts = r.항목[k], w = M.WEIGHTS[k];
      const pc = Math.max(0, Math.min(100, pts / w * 100));
      const cls = pc >= 70 ? 'hi' : pc >= 40 ? 'mid' : 'lo';
      return `<div class="row"><span class="lb">${k}</span>
        <span class="sbar">
          <span class="track"><span class="fill ${cls}" style="width:${pc}%"></span></span>
          <span class="val">${pts} / ${w}</span>
        </span></div>
        <div class="row"><span></span><span class="why">${U.esc(r.근거[i])}</span></div>`;
    }).join('');
  }

  function riskList(list) {
    if (!list.length) return '<div class="risk">특이 리스크 없음</div>';
    return list.map(x => {
      const cls = x.startsWith('⛔') ? 'high' : x.startsWith('⚠') ? 'warn' : '';
      return `<div class="risk ${cls}">${U.esc(x)}</div>`;
    }).join('');
  }

  function renderTable() {
    const rows = S.analyzed();
    const el = document.getElementById('s-table');
    if (!rows.length) {
      el.innerHTML = `<div class="empty"><b>후보지가 없습니다</b>
        CSV 를 가져오거나 직접 추가하세요. 처음이라면 상단 <b>데모 데이터</b> 버튼을 눌러보세요.</div>`;
      return;
    }
    const q = (document.getElementById('s-q').value || '').trim();
    const stage = document.getElementById('s-stage').value;
    const cur = S.get().selected;

    const body = rows.filter(({ site, r }) =>
      (!q || (r.후보지명 + r.주소).includes(q)) && (!stage || (site.상태 || '검토') === stage)
    ).map(({ site, r }) => {
      const p = r.손익, [v] = M.verdict(r);
      const vc = v === '출점 추천' ? 'b-ok' : v === '반려' ? 'b-no' : v === '조건부 추천' ? 'b-warm' : 'b-wait';
      return `<tr data-id="${site.id}" class="${site.id === cur ? 'sel' : ''}">
        <td><div class="gradeline">${gradeChip(r)}<div>
          <b>${U.esc(r.후보지명)}</b><div class="why">${U.esc(r.주소 || '주소 미입력')}</div>
        </div></div></td>
        <td class="num"><b>${r.총점}</b></td>
        <td style="min-width:120px">${miniBar(r.총점, 100)}</td>
        <td class="num">${U.num(p.월매출_만원, 0)}</td>
        <td class="num ${p.영업이익_만원 < 0 ? 'neg' : ''}"
            style="${p.영업이익_만원 < 0 ? 'color:var(--no);font-weight:700' : ''}">${U.num(p.영업이익_만원, 0)}</td>
        <td class="num">${p.투자회수_개월 === null ? '—' : U.num(p.투자회수_개월, 0)}</td>
        <td><span class="badge ${vc}">${v}</span></td>
        <td><select class="s-stage" data-id="${site.id}">${
          STAGES.map(s => `<option ${(site.상태 || '검토') === s ? 'selected' : ''}>${s}</option>`).join('')
        }</select></td>
        <td><button class="sm s-open" data-id="${site.id}">열기</button></td>
      </tr>`;
    }).join('');

    el.innerHTML = `<div class="tablewrap"><table>
      <thead><tr>
        <th>후보지</th><th class="num">총점</th><th></th>
        <th class="num">월매출(만)</th><th class="num">영업이익(만)</th><th class="num">회수(개월)</th>
        <th>심의</th><th>단계</th><th></th>
      </tr></thead><tbody>${body || ''}</tbody></table></div>`;
    if (!body) el.innerHTML += '<p class="hint">조건에 맞는 후보지가 없습니다.</p>';

    el.querySelectorAll('.s-open').forEach(b => b.onclick = () => { S.select(b.dataset.id); App.render(); });
    el.querySelectorAll('.s-stage').forEach(sel => sel.onchange = () => {
      S.update(sel.dataset.id, { 상태: sel.value });
      App.render();
    });
  }

  function renderDetail() {
    const el = document.getElementById('s-detail');
    const site = S.current();
    if (!site) { el.innerHTML = ''; return; }
    const r = M.analyze(site, S.get().pois, S.brand());
    const p = r.손익, rev = r.매출추정, c = r.경쟁;
    const [v, note] = M.verdict(r);

    el.innerHTML = `
      <div class="card">
        <div class="panel-head" style="margin-bottom:12px">
          <div><h3 style="font-size:17px">${U.esc(r.후보지명)}</h3>
            <p style="margin-top:2px">${U.esc(r.주소 || '주소 미입력')}</p></div>
          <div class="acts">
            <button class="sm" id="s-edit">편집</button>
            <button class="sm" id="s-sim">손익 시뮬</button>
            <button class="sm danger" id="s-del">삭제</button>
          </div>
        </div>
        <div class="grid g4">
          <div class="kpi"><div class="k">종합점수</div>
            <div class="v">${r.총점}<small>/100</small></div>
            <div class="d">${r.등급}등급 · ${r.등급설명}</div></div>
          <div class="kpi"><div class="k">추정 월매출</div>
            <div class="v">${U.num(p.월매출_만원, 0)}<small>만원</small></div>
            <div class="d">하루 ${U.num(rev.일객수_추정, 0)}명 × ${U.num(rev.객단가_원, 0)}원</div></div>
          <div class="kpi"><div class="k">영업이익</div>
            <div class="v" style="color:${p.영업이익_만원 < 0 ? 'var(--no)' : 'var(--ok)'}">${U.num(p.영업이익_만원, 0)}<small>만원</small></div>
            <div class="d">${U.pct(p.영업이익률)} · BEP ${U.pct(p.BEP달성률, 0)}</div></div>
          <div class="kpi"><div class="k">투자회수</div>
            <div class="v">${p.투자회수_개월 === null ? '—' : U.num(p.투자회수_개월, 0)}<small>개월</small></div>
            <div class="d">투자 ${U.num(p.초기투자_만원, 0)}만원</div></div>
        </div>
        <div class="grid g2" style="margin-top:14px">
          <div class="card"><h3>점수 상세</h3><div class="scores">${scoreRows(r)}</div></div>
          <div class="card"><h3>심의 결론 · 리스크</h3>
            <p style="margin:0 0 4px"><b style="font-size:16px">${v}</b></p>
            <p class="hint" style="margin-top:0">${U.esc(note)}</p>
            <div class="risks">${riskList(r.리스크)}</div>
            <p class="hint">반경 내 카페 ${c.카페수}곳 · 동일포지션 ${c.동일포지션} · 앵커 ${c.앵커브랜드}
              ${c.자사점_최근접_m === null ? '' : ` · 자사점 최근접 ${U.num(c.자사점_최근접_m, 0)}m`}</p>
          </div>
        </div>
      </div>`;

    document.getElementById('s-edit').onclick = () => openForm(site);
    document.getElementById('s-sim').onclick = () => App.go('sim');
    document.getElementById('s-del').onclick = () => {
      if (!confirm(`'${site.후보지명}' 후보지를 삭제할까요? 되돌릴 수 없습니다.`)) return;
      S.remove(site.id); U.toast('삭제했습니다'); App.render();
    };
  }

  /* 추가/편집 폼 — 같은 화면 안에서 연다(별도 라우팅 없음). */
  function openForm(site) {
    const el = document.getElementById('s-form');
    const s = site || {};
    el.classList.remove('hide');
    el.innerHTML = `<div class="card"><h3>${site ? '후보지 편집' : '후보지 추가'}</h3>
      <div class="grid g4">${FIELDS.map(([k, lb, t]) =>
        `<label class="field"><span>${lb}</span>
          <input data-k="${k}" type="${t}" ${t === 'number' ? 'step="any"' : ''} value="${U.esc(s[k] ?? '')}"/></label>`
      ).join('')}</div>
      <label class="field"><span>메모</span><textarea data-k="메모">${U.esc(s.메모 || '')}</textarea></label>
      <div class="acts" style="display:flex;gap:8px">
        <button class="primary" id="f-save">저장</button>
        <button class="ghost" id="f-cancel">취소</button>
      </div></div>`;
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    document.getElementById('f-cancel').onclick = () => { el.classList.add('hide'); el.innerHTML = ''; };
    document.getElementById('f-save').onclick = () => {
      const patch = {};
      el.querySelectorAll('[data-k]').forEach(i => { patch[i.dataset.k] = i.value.trim(); });
      if (!patch.후보지명) { U.toast('후보지명은 필수입니다'); return; }
      if (site) S.update(site.id, patch);
      else { const added = S.addSite(patch); S.select(added.id); }
      el.classList.add('hide'); el.innerHTML = '';
      U.toast(site ? '저장했습니다' : '후보지를 추가했습니다');
      App.render();
    };
  }

  /* 내보내기 — analysis/ 의 CSV 형식 그대로라 score_sites.py 에 바로 넣을 수 있다. */
  function exportCSV() {
    const rows = S.sites();
    if (!rows.length) { U.toast('내보낼 후보지가 없습니다'); return; }
    const head = ['후보지명', ...FIELDS.map(f => f[0]).filter(k => k !== '후보지명'), '상태', '메모'];
    U.download('후보지.csv', U.toCSV(rows, head), 'text/csv');
    U.toast('후보지.csv 를 내려받았습니다');
  }

  function init() {
    document.getElementById('s-add').onclick = () => openForm(null);
    document.getElementById('s-import').onclick = () => U.pickFile('.csv,text/csv', text => {
      const rows = U.parseCSV(text);
      const n = S.importSites(rows);
      U.toast(`후보지 ${n}곳을 가져왔습니다`);
      App.render();
    });
    document.getElementById('s-import-poi').onclick = () => U.pickFile('.csv,text/csv', text => {
      const n = S.importPois(U.parseCSV(text));
      U.toast(`POI ${n}건을 가져왔습니다`);
      App.render();
    });
    document.getElementById('s-export').onclick = exportCSV;
    document.getElementById('s-q').oninput = renderTable;
    document.getElementById('s-stage').innerHTML =
      '<option value="">전체</option>' + STAGES.map(s => `<option>${s}</option>`).join('');
    document.getElementById('s-stage').onchange = renderTable;
  }

  return { init, render: () => { renderTable(); renderDetail(); }, scoreRows, riskList, gradeChip, STAGES };
})();
