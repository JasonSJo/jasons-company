/* 상권분석 데이터 입력 — 후보지 실사 결과를 받아 파이프라인 입력 CSV 로 내보낸다.

   여기서 하지 않는 것: 판정·매출 추정. 그건 파이프라인(analysis/)과 사내 심의
   콘솔의 일이다. 이 페이지는 **입력만** 다루므로 공개해도 되는 화면이다.

   저장은 이 브라우저의 localStorage 에만 한다. 서버 전송 없음. */
(() => {
  'use strict';

  const KEY = 'cafe-trade-area/후보지입력/v1';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.prototype.slice.call((r || document).querySelectorAll(s));
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let sites = load();
  let cur = 0;

  /* ── 저장 ─────────────────────────────── */
  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      const v = raw ? JSON.parse(raw) : null;
      if (Array.isArray(v) && v.length) return v;
    } catch (e) { /* 시크릿 모드 등 */ }
    return [blank()];
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(sites)); }
    catch (e) { toast('브라우저에 저장하지 못했습니다(시크릿 모드일 수 있습니다). 화면은 계속 씁니다.'); }
  }
  function blank() {
    const o = {};
    FIELDS.COLUMNS.forEach(k => { o[k] = ''; });
    return o;
  }
  // 아무것도 안 적힌 행은 '덜 채운 후보지'가 아니라 아직 쓰지 않은 빈 칸이다.
  // 이걸 구분하지 않으면 첫 화면의 빈 행이 영원히 내보내기를 막는다.
  const isEmpty = site => FIELDS.COLUMNS.every(k => String(site[k] ?? '').trim() === '');

  function toast(msg) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove('on'), 2800);
  }

  /* ── 검증 ─────────────────────────────── */
  // 한 항목의 문제. 반환값이 있으면 그 문구가 필드 아래 붙는다.
  function fieldError(site, k) {
    const m = FIELDS.meta(k);
    const v = String(site[k] ?? '').trim();
    if (m.필수 && v === '') return '필수 항목입니다';
    if (v === '') return '';
    if (m.종류 === 'num') {
      const n = Number(v.replace(/,/g, ''));
      if (!Number.isFinite(n)) return '숫자를 넣어 주세요';
      if (m.최소 !== undefined && n < m.최소) return `${m.최소} 이상`;
      if (m.최대 !== undefined && n > m.최대) return `${m.최대} 이하`;
    }
    if (m.종류 === 'select' && m.선택 && !m.선택.some(([val]) => val === v)) {
      return '목록에서 고르세요';
    }
    return '';
  }

  function siteErrors(site) {
    return FIELDS.keys().map(k => [k, fieldError(site, k)]).filter(([, e]) => e);
  }
  // 실사를 마치지 않은 치명 항목 — 통과 판정을 잠정으로 만든다
  const unchecked = site => FIELDS.FATAL.filter(k => String(site[k] ?? '').trim() === '');
  const flagged = site => FIELDS.FATAL.filter(k => String(site[k] ?? '').trim().toUpperCase() === 'Y');

  function status(site) {
    if (isEmpty(site)) return { cls: 'hold', 글: '작성 전' };
    if (!String(site.후보지명 || '').trim()) return { cls: 'bad', 글: '이름 없음' };
    if (siteErrors(site).length) return { cls: 'bad', 글: '입력 필요' };
    if (unchecked(site).length) return { cls: 'hold', 글: `미확인 ${unchecked(site).length}` };
    return { cls: 'ready', 글: '준비됨' };
  }

  // 이름이 겹치면 파이프라인이 두 후보지를 구분하지 못한다
  function duplicateNames() {
    const seen = {}, dup = [];
    sites.forEach(s => {
      const n = String(s.후보지명 || '').trim();
      if (!n) return;
      if (seen[n]) { if (dup.indexOf(n) < 0) dup.push(n); } else seen[n] = true;
    });
    return dup;
  }

  /* ── 목록 ─────────────────────────────── */
  function renderList() {
    $('#slist').innerHTML = sites.map((s, i) => {
      const st = status(s);
      const nm = String(s.후보지명 || '').trim() || '(이름 없음)';
      return `<li class="${i === cur ? 'on' : ''}"><button type="button" data-pick="${i}">
        <span class="nm">${esc(nm)}</span>
        <span class="st ${st.cls}">${st.글}</span></button></li>`;
    }).join('');
    $('#count').textContent = sites.length;
  }

  /* ── 폼 ─────────────────────────────── */
  function control(site, k) {
    const m = FIELDS.meta(k);
    const v = site[k] ?? '';
    const bad = fieldError(site, k) ? ' bad' : '';
    if (m.종류 === 'flag') {
      const opts = [['Y', '해당'], ['N', '해당 없음'], ['', '미확인']];
      return `<select class="${bad.trim()}" data-k="${k}">${opts.map(([val, lb]) =>
        `<option value="${val}"${String(v) === val ? ' selected' : ''}>${lb}</option>`).join('')}</select>`;
    }
    if (m.종류 === 'select') {
      return `<select class="${bad.trim()}" data-k="${k}">
        <option value="">— 선택 —</option>${(m.선택 || []).map(([val, lb]) =>
        `<option value="${val}"${String(v) === val ? ' selected' : ''}>${lb}</option>`).join('')}</select>`;
    }
    if (m.종류 === 'num') {
      return `<input type="number" class="${bad.trim()}" data-k="${k}" value="${esc(v)}"
        min="${m.최소 ?? ''}" max="${m.최대 ?? ''}" step="${m.증분 ?? 'any'}" inputmode="decimal"/>`;
    }
    return `<input type="text" class="${bad.trim()}" data-k="${k}" value="${esc(v)}"/>`;
  }

  function field(site, k) {
    const m = FIELDS.meta(k);
    const err = fieldError(site, k);
    const wide = (k === '비고' || k === '주소') ? ' wide' : '';
    const modCls = m.모듈 === '—' ? ' none' : '';
    return `<div class="f${wide}">
      <label for="">${esc(m.라벨)}
        ${m.필수 ? '<span class="req">필수</span>' : ''}
        <span class="mod${modCls}">${esc(m.모듈)}</span></label>
      ${control(site, k)}
      ${err ? `<span class="err">${esc(err)}</span>` : `<span class="help">${esc(m.설명)}</span>`}
    </div>`;
  }

  /* ── 위치 블록 ─────────────────────────────
     주소 하나로 후보지명·좌표를 채운다. 좌표를 손으로 찍게 하면 오타 한 자리에
     상권이 통째로 어긋나므로, 검색 결과에서 고르게 하고 직접 입력은 열지 않는다.
     (좌표를 지도에서 복사해 온 경우만 붙여넣기로 받는다) */
  function placeBlock(site, g) {
    const 주소 = String(site.주소 || '').trim();
    const 위도 = String(site.위도 || '').trim();
    const 경도 = String(site.경도 || '').trim();
    const 이름 = String(site.후보지명 || '').trim();
    const 좌표있음 = !!(위도 && 경도);
    const ls = PLACE.links(site);

    return `<fieldset class="place">
      <legend>${esc(g.이름)}</legend>
      <p class="note">${g.설명}</p>

      <div class="searchrow">
        <input type="search" id="q" placeholder="주소 또는 상호로 검색 — 예: 성동구 연무장길 42"
          autocomplete="off" enterkeyhint="search"/>
        <button class="primary" type="button" id="go">검색</button>
        <button type="button" id="post" title="키 없이 주소만 고릅니다">주소만 고르기</button>
      </div>
      <div id="hits" class="hits hide"></div>
      ${PLACE.hasKey() ? '' : `<p class="keyhint">카카오 JS 키가 없어 <b>주소만</b> 고를 수 있습니다 —
        좌표는 지도에서 복사해 붙여넣으세요. <button type="button" class="sm ghost" id="keyopen">키 넣기</button></p>`}
      <div id="keybox" class="keybox hide">
        <label>카카오맵 JS 키 <small>(도메인 제한으로 보호되므로 이 브라우저에만 저장됩니다)</small></label>
        <div class="searchrow">
          <input type="text" id="keyin" value="${esc(PLACE.getKey())}" placeholder="JavaScript 키"/>
          <button class="primary" type="button" id="keysave">저장</button>
        </div>
      </div>

      <div class="picked ${주소 ? '' : 'empty'}">
        ${주소 ? `
          <div class="row"><span class="lb">주소</span><b>${esc(주소)}</b></div>
          <div class="row"><span class="lb">후보지명</span>
            <input type="text" data-k="후보지명" value="${esc(이름)}" placeholder="심의표에 쓸 이름"/>
            ${이름 ? '' : '<button class="sm" type="button" id="namesug">주소에서 제안</button>'}</div>
          ${(String(site.우편번호 || '').trim() || String(site.법정동코드 || '').trim()) ? `
          <div class="row"><span class="lb">우편번호</span>
            <b class="mono">${esc(String(site.우편번호 || '').trim() || '—')}</b>
            ${String(site.법정동코드 || '').trim() ? `<span class="lawd">법정동 ${esc(site.법정동코드)}
              · 실거래가 지역코드 <b class="mono">${esc(PLACE.lawdCode(site.법정동코드))}</b></span>` : ''}
          </div>` : ''}
          <div class="row"><span class="lb">좌표</span>
            ${좌표있음
              ? `<b class="mono">${esc(위도)}, ${esc(경도)}</b>
                 <button class="sm ghost" type="button" id="coredit">고치기</button>`
              : `<span class="miss">없음 — 지도에서 복사해 붙여넣으세요</span>
                 <button class="sm" type="button" id="coredit">좌표 붙여넣기</button>`}
          </div>
          <div id="corbox" class="hide">
            <div class="searchrow">
              <input type="text" id="corin" placeholder="37.5445, 127.0557"/>
              <button class="primary" type="button" id="corsave">적용</button>
            </div>
            <p class="note" style="margin:6px 0 0">네이버지도에서 해당 위치를 우클릭 →
              좌표를 복사해 그대로 붙여넣으면 됩니다.</p>
          </div>
        ` : '<div class="miss">위에서 주소를 검색해 위치를 확정하세요.</div>'}
      </div>

      ${ls.length ? `<div class="svc">
        <div class="svc-h">이 위치 확인</div>
        <div class="svc-b">${ls.map(l => `<a href="${esc(l.href)}" target="_blank" rel="noopener noreferrer">
          <span class="nm">${esc(l.이름)}</span><span class="ds">${esc(l.설명)}</span></a>`).join('')}</div>
        <p class="note" style="margin:9px 0 0">각 사이트를 새 탭에서 엽니다 —
          데이터를 자동으로 가져오지는 않습니다(공개 API 가 없습니다).</p>
      </div>` : ''}
    </fieldset>`;
  }

  function wirePlace(site) {
    const el = $('#pane');
    const b = (id, fn) => { const x = el.querySelector(id); if (x) x.onclick = fn; };
    const q = el.querySelector('#q');

    function apply(hit) {
      const s2 = sites[cur];
      s2.주소 = hit.주소 || '';
      // 장소 검색은 이 둘을 주지 않는다 — 이미 있는 값을 빈 값으로 덮지 않는다
      if (hit.우편번호) s2.우편번호 = hit.우편번호;
      if (hit.법정동코드) s2.법정동코드 = hit.법정동코드;
      if (!String(s2.후보지명 || '').trim()) s2.후보지명 = PLACE.suggestName(hit);
      if (Number.isFinite(hit.위도) && Number.isFinite(hit.경도)) {
        s2.위도 = String(hit.위도); s2.경도 = String(hit.경도);
      }
      save(); render();
      toast(hit.위도 ? '위치를 확정했습니다' : '주소를 넣었습니다 — 좌표는 붙여넣어 주세요');
    }

    function runSearch() {
      const text = (q && q.value || '').trim();
      if (!text) { toast('주소나 상호를 입력하세요.'); return; }
      if (!PLACE.hasKey()) { toast('카카오 JS 키가 없습니다 — 주소만 고르기를 쓰세요.'); return; }
      const box = el.querySelector('#hits');
      box.classList.remove('hide');
      box.innerHTML = '<div class="hit-empty">찾는 중…</div>';
      PLACE.search(text).then(hits => {
        if (!hits.length) { box.innerHTML = '<div class="hit-empty">결과가 없습니다.</div>'; return; }
        box.innerHTML = hits.map((h, i) => `<button type="button" data-hit="${i}">
          <span class="nm">${esc(h.이름 || h.주소)}</span>
          <span class="ad">${esc(h.주소)}</span>
          <span class="src">${esc(h.출처)}</span></button>`).join('');
        box.querySelectorAll('[data-hit]').forEach(btn => {
          btn.onclick = () => apply(hits[Number(btn.dataset.hit)]);
        });
      }).catch(e => {
        box.innerHTML = `<div class="hit-empty">검색 실패 — ${esc(e.message)}</div>`;
      });
    }

    if (q) q.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); runSearch(); } };
    b('#go', runSearch);
    b('#post', () => PLACE.openPostcode().then(apply).catch(e => {
      if (e.message !== '취소') toast(e.message);
    }));
    b('#keyopen', () => el.querySelector('#keybox').classList.remove('hide'));
    b('#keysave', () => {
      PLACE.setKey(el.querySelector('#keyin').value);
      toast(PLACE.hasKey() ? '키를 저장했습니다 — 이제 검색하면 좌표까지 채워집니다' : '키를 지웠습니다');
      render();
    });
    b('#namesug', () => {
      const s2 = sites[cur];
      s2.후보지명 = PLACE.suggestName({ 이름: '', 주소: s2.주소 });
      save(); render();
      toast('주소에서 이름을 지었습니다 — 필요하면 고치세요');
    });
    b('#coredit', () => {
      const box = el.querySelector('#corbox');
      box.classList.toggle('hide');
      const inp = el.querySelector('#corin');
      if (inp && !box.classList.contains('hide')) inp.focus();
    });
    b('#corsave', () => {
      const v = PLACE.parseCoords(el.querySelector('#corin').value);
      if (!v) { toast('좌표를 읽지 못했습니다 — 예: 37.5445, 127.0557'); return; }
      sites[cur].위도 = String(v.위도);
      sites[cur].경도 = String(v.경도);
      save(); render();
      toast('좌표를 넣었습니다');
    });
  }

  function renderForm() {
    const site = sites[cur];
    const nm = String(site.후보지명 || '').trim() || '(이름 없음)';
    $('#pane').innerHTML = `
      <div class="pane-head">
        <div><h2>${esc(nm)}</h2>
          <div class="sub">${esc(String(site.주소 || '').trim() || '주소 미입력')}</div></div>
        <div class="acts">
          <button class="sm" type="button" id="dup">복제</button>
          <button class="sm ghost danger" type="button" id="del">삭제</button>
        </div>
      </div>
      ${FIELDS.GROUPS.map(g => {
        const manual = g.항목.map(([k]) => k).filter(k => !FIELDS.meta(k).자동);
        // 위치 묶음은 주소 검색 블록이 대신한다
        if (!manual.length) return placeBlock(site, g);
        return `<fieldset>
          <legend>${esc(g.이름)}</legend>
          ${g.설명 ? `<p class="note">${g.설명}</p>` : ''}
          <div class="grid">${manual.map(k => field(site, k)).join('')}</div>
        </fieldset>`;
      }).join('')}`;

    $$('#pane [data-k]').forEach(el => {
      el.onchange = () => {
        sites[cur][el.dataset.k] = el.value;
        save();
        render();
      };
    });
    wirePlace(site);
    $('#dup').onclick = () => {
      const copy = Object.assign({}, sites[cur]);
      copy.후보지명 = (copy.후보지명 || '후보지') + ' 사본';
      sites.splice(cur + 1, 0, copy);
      cur += 1;
      save(); render();
      toast('복제했습니다 — 이름을 바꿔 주세요');
    };
    $('#del').onclick = () => {
      const nm2 = String(sites[cur].후보지명 || '').trim() || '(이름 없음)';
      if (!confirm(`'${nm2}' 을(를) 목록에서 지웁니다. 계속할까요?`)) return;
      sites.splice(cur, 1);
      if (!sites.length) sites = [blank()];
      cur = Math.min(cur, sites.length - 1);
      save(); render();
    };
  }

  /* ── 준비 상태 ─────────────────────────────── */
  function renderReady() {
    const named = sites.filter(s => String(s.후보지명 || '').trim());
    const started = sites.filter(s => !isEmpty(s));   // 손을 댄 행만 검사 대상
    const broken = started.filter(s => siteErrors(s).length || !String(s.후보지명 || '').trim());
    const dup = duplicateNames();
    const holds = named.filter(s => unchecked(s).length);
    const hits = named.filter(s => flagged(s).length);

    let cls = 'ok', head = `후보지 ${named.length}곳 — 내보낼 수 있습니다`;
    const items = [];

    if (!named.length) {
      cls = 'bad'; head = '아직 내보낼 후보지가 없습니다';
      items.push('후보지명을 넣으면 목록에 잡힙니다.');
    }
    if (broken.length) {
      cls = 'bad'; head = `입력이 덜 된 후보지 ${broken.length}곳`;
      broken.forEach(s => {
        const nm = String(s.후보지명 || '').trim() || '(이름 없음)';
        const es = siteErrors(s);
        const what = es.length ? es.map(([k]) => FIELDS.meta(k).라벨).join(', ') : '후보지명';
        items.push(`<b>${esc(nm)}</b> — ${esc(what)}`);
      });
    }
    if (dup.length) {
      cls = 'bad'; head = '후보지 이름이 겹칩니다';
      items.push(`겹치는 이름: <b>${dup.map(esc).join(', ')}</b> — 파이프라인이 두 후보지를 구분하지 못합니다.`);
    }
    if (cls !== 'bad' && holds.length) {
      cls = 'warn'; head = `치명 항목 미확인 — ${holds.length}곳`;
      holds.forEach(s => items.push(
        `<b>${esc(s.후보지명)}</b> — ${unchecked(s).map(k => FIELDS.meta(k).라벨).join(', ')}
         <span class="who">실사 전이라면 그대로 두십시오. '해당 없음'으로 적으면 확인하지 않은 위험이 통과로 흘러갑니다.</span>`));
    }
    if (hits.length) {
      items.push(`치명 항목 해당: <b>${hits.map(s => esc(s.후보지명)).join(', ')}</b> — 점수·매출과 무관하게 단독 부결됩니다.`);
    }
    if (cls === 'ok' && !items.length) {
      items.push('모든 필수 항목이 채워졌고 치명 항목도 확인됐습니다.');
    }

    $('#ready').className = `ready-box ${cls}`;
    $('#ready').innerHTML = `<h3>${esc(head)}</h3><ul>${items.map(x => `<li>${x}</li>`).join('')}</ul>`;
    $('#export').disabled = !named.length || broken.length > 0 || dup.length > 0;
  }

  /* ── CSV ─────────────────────────────── */
  function toCSV() {
    const cell = v => {
      const s = String(v == null ? '' : v).trim();
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const rows = sites.filter(s => String(s.후보지명 || '').trim());
    const lines = [FIELDS.COLUMNS.join(',')];
    rows.forEach(s => lines.push(FIELDS.COLUMNS.map(k => cell(s[k])).join(',')));
    return lines.join('\n') + '\n';
  }

  // 따옴표·줄바꿈을 포함한 필드를 처리하는 최소 파서
  function parseCSV(text) {
    const rows = []; let row = [], f = '', q = false;
    text = String(text).replace(/^﻿/, '').replace(/\r\n?/g, '\n');
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; }
        else f += c;
      } else if (c === '"') q = true;
      else if (c === ',') { row.push(f); f = ''; }
      else if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; }
      else f += c;
    }
    if (f !== '' || row.length) { row.push(f); rows.push(row); }
    return rows.filter(r => r.some(c => String(c).trim() !== ''));
  }

  function importCSV(text) {
    const rows = parseCSV(text);
    if (rows.length < 2) { toast('CSV 에 후보지 행이 없습니다.'); return; }
    const head = rows[0].map(h => String(h).trim());
    if (head.indexOf('후보지명') < 0) {
      toast('후보지 CSV 가 아닙니다 — 첫 줄에 후보지명 열이 있어야 합니다.');
      return;
    }
    const unknown = head.filter(h => h && FIELDS.COLUMNS.indexOf(h) < 0);
    const loaded = rows.slice(1).map(r => {
      const o = blank();
      head.forEach((h, i) => { if (FIELDS.COLUMNS.indexOf(h) >= 0) o[h] = String(r[i] ?? '').trim(); });
      return o;
    });
    sites = loaded;
    cur = 0;
    save(); render();
    toast(`후보지 ${loaded.length}곳을 불러왔습니다` +
      (unknown.length ? ` (모르는 열 ${unknown.length}개는 버렸습니다: ${unknown.join(', ')})` : ''));
  }

  function download(name, text) {
    // CSV 는 BOM 을 붙인다 — 엑셀 한글 깨짐 방지.
    // 파이프라인은 utf-8-sig 로 읽으므로 BOM 이 있어도 그대로 파싱된다.
    const blob = new Blob(['﻿' + text], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function pickFile(cb) {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = '.csv,text/csv';
    inp.onchange = () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      const fr = new FileReader();
      fr.onload = () => cb(String(fr.result));
      fr.onerror = () => toast('파일을 읽지 못했습니다.');
      fr.readAsText(f, 'utf-8');
    };
    inp.click();
  }

  /* ── 예시 ─────────────────────────────── */
  const SAMPLE = {
    후보지명: '성수 연무장길', 주소: '서울 성동구 연무장길 42',
    위도: '37.5445', 경도: '127.0557', 전용면적_평: '16', 좌석수: '34', 층: '1',
    코너여부: 'Y', 전면폭_m: '6.9', 주차가능대수: '0', 정차가능: 'N',
    도로변: 'A', 방향적합: 'Y', 보증금_만원: '4700', 월임대료_만원: '262',
    관리비_만원: '25', 권리금_만원: '7900', 계약조건점수: '2', 잔존율_R: '',
    근저당_과다: 'N', 임대인_불일치: 'N', 소송_계류: 'N', 인허가_불가: 'N',
    비고: 'mixed 상권',
  };

  /* ── 렌더 ─────────────────────────────── */
  function render() { renderList(); renderForm(); renderReady(); }

  function init() {
    $('#slist').addEventListener('click', e => {
      const b = e.target.closest('[data-pick]');
      if (!b) return;
      cur = Number(b.dataset.pick);
      render();
      if (window.matchMedia('(max-width:880px)').matches) {
        $('#pane').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
    // 지금 보고 있는 칸이 비어 있으면 새 행을 만들지 않고 그 칸을 쓴다
    function slot(row) {
      if (isEmpty(sites[cur])) sites[cur] = row;
      else { sites.push(row); cur = sites.length - 1; }
    }
    $('#add').onclick = () => {
      slot(blank());
      save(); render();
      const first = $('#pane [data-k="후보지명"]');
      if (first) first.focus();
    };
    $('#sample').onclick = () => {
      slot(Object.assign({}, SAMPLE));
      save(); render();
      toast('예시 후보지를 넣었습니다 — 값을 바꿔 쓰세요');
    };
    $('#import').onclick = () => pickFile(importCSV);
    $('#export').onclick = () => {
      download('sites.csv', toCSV());
      toast('sites.csv (후보지) 를 내려받았습니다 — analysis/ 에 두고 파이프라인을 돌리세요');
    };
    $('#clear').onclick = () => {
      if (!confirm('입력한 후보지를 모두 지웁니다. 되돌릴 수 없습니다. 계속할까요?')) return;
      sites = [blank()]; cur = 0;
      try { localStorage.removeItem(KEY); } catch (e) { /* 무시 */ }
      render();
      toast('비웠습니다');
    };
    render();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
