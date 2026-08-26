/* 상권 지도 — 외부 지도 API 없이 SVG 로 그린다.
   후보지를 원점에 놓고 주변 POI 를 실제 거리(m)로 배치한 로컬 평면도다.
   타일·키·네트워크가 없어 file:// 로 열어도 그대로 뜬다. */
const TAMap = (() => {

  const KIND = {
    자사점: ['map-own', '자사 기존점'],
    카페: ['map-cafe', '카페'],
    지하철: ['map-etc', '지하철역'],
    학교: ['map-etc', '학교'],
    병원: ['map-etc', '병원'],
    마트: ['map-etc', '마트'],
  };

  /* 위경도 → 후보지 기준 로컬 평면좌표(m). 500m 규모에서는 이 근사로 충분하다. */
  function project(lat0, lon0, lat, lon) {
    const mPerDegLat = 110540;
    const mPerDegLon = 111320 * Math.cos(lat0 * Math.PI / 180);
    return { x: (lon - lon0) * mPerDegLon, y: -(lat - lat0) * mPerDegLat };
  }

  function classify(p) {
    const kind = String(p.분류 || '').trim();
    if (kind === '자사점') return ['map-own', '자사점'];
    if (kind !== '카페') return KIND[kind] || ['map-etc', kind || '기타'];
    const b = String(p.브랜드 || p.상호 || '');
    if (M.RIVAL_BRANDS.some(x => b.includes(x))) return ['map-rival', '동일포지션'];
    if (M.ANCHOR_BRANDS.some(x => b.includes(x))) return ['map-anchor', '앵커 브랜드'];
    return ['map-cafe', '일반 카페'];
  }

  function render(el, site, pois, radius) {
    const lat0 = M.f(site.위도), lon0 = M.f(site.경도);
    if (!lat0 || !lon0) {
      el.innerHTML = `<div class="empty"><b>좌표가 없어 지도를 그릴 수 없습니다</b>
        후보지의 위도·경도를 입력하면 반경 내 경쟁 분포가 여기 표시됩니다.</div>`;
      return;
    }

    const view = radius * 1.45;            // 표시 반경(m)
    const SZ = 560, C = SZ / 2;
    const s = C / view;                     // m → px
    const px = m => m * s;

    const near = (pois || []).map(p => {
      const lat = M.f(p.위도), lon = M.f(p.경도);
      if (!lat || !lon) return null;
      const q = project(lat0, lon0, lat, lon);
      const d = Math.hypot(q.x, q.y);
      return d <= view ? { p, q, d } : null;
    }).filter(Boolean).sort((a, b) => b.d - a.d);   // 먼 것부터 그려 가까운 게 위로

    const rings = `<circle cx="${C}" cy="${C}" r="${px(radius)}" fill="var(--brand)" opacity=".045"/>`
      + [radius / 2, radius].map(r =>
        `<circle class="map-ring" cx="${C}" cy="${C}" r="${px(r)}"/>
         <text class="map-lbl" x="${C + 3}" y="${C - px(r) - 4}">${r}m</text>`).join('');

    const grid = [0.25, 0.5, 0.75].flatMap(t => [
      `<line class="map-grid" x1="0" y1="${SZ * t}" x2="${SZ}" y2="${SZ * t}" opacity=".35"/>`,
      `<line class="map-grid" x1="${SZ * t}" y1="0" x2="${SZ * t}" y2="${SZ}" opacity=".35"/>`]).join('');

    const dots = near.map(({ p, q, d }) => {
      const [cls, label] = classify(p);
      const r = cls === 'map-own' ? 6 : cls === 'map-rival' ? 5.5 : 4.5;
      return `<circle class="${cls}" cx="${C + px(q.x)}" cy="${C + px(q.y)}" r="${r}">
        <title>${U.esc(p.상호 || '')} · ${label} · ${Math.round(d)}m</title></circle>`;
    }).join('');

    /* 가장 가까운 경쟁 4곳만 이름을 붙이고, 위아래로 번갈아 띄워 글자가 겹치지 않게 한다.
       후보지 자체는 패널 제목에 이미 있으므로 지도에는 마커만 둔다. */
    const labels = near.filter(n => ['map-rival', 'map-own', 'map-anchor'].includes(classify(n.p)[0]))
      .filter(n => n.d > radius * 0.22)   // 마커에 겹칠 만큼 가까우면 이름표 생략(툴팁으로 확인)
      .sort((a, b) => a.d - b.d).slice(0, 4)
      .map(({ p, q }, idx) => {
        const x = C + px(q.x), y = C + px(q.y) + (idx % 2 ? 15 : -9);
        const anchor = x > SZ * 0.7 ? 'end' : 'start';
        const dx = anchor === 'end' ? -8 : 8;
        const name = String(p.상호 || '');
        const short = name.length > 12 ? name.slice(0, 11) + '…' : name;
        return `<text class="map-lbl" x="${x + dx}" y="${y}" text-anchor="${anchor}">${U.esc(short)}</text>`;
      }).join('');

    const counts = near.reduce((acc, n) => {
      const k = classify(n.p)[1];
      acc[k] = (acc[k] || 0) + 1;
      return acc;
    }, {});

    el.innerHTML = `<div class="mapwrap">
      <svg viewBox="0 0 ${SZ} ${SZ}" role="img"
           aria-label="${U.esc(site.후보지명 || '후보지')} 반경 ${radius}m 경쟁 분포도">
        ${grid}${rings}${dots}
        <circle class="map-site" cx="${C}" cy="${C}" r="8"/>
        <circle cx="${C}" cy="${C}" r="12" fill="none" stroke="var(--brand)" stroke-width="2" opacity=".5">
          <title>${U.esc(site.후보지명 || '후보지')} (후보지)</title></circle>
        ${labels}
      </svg>
      <div class="map-legend">
        <span><i style="background:var(--brand)"></i>후보지</span>
        <span><i style="background:var(--no)"></i>동일포지션 ${counts['동일포지션'] || 0}</span>
        <span><i style="background:var(--hold)"></i>앵커 ${counts['앵커 브랜드'] || 0}</span>
        <span><i style="background:var(--fg-mute)"></i>일반 카페 ${counts['일반 카페'] || 0}</span>
        <span><i style="background:var(--accent)"></i>자사점 ${counts['자사점'] || 0}</span>
      </div></div>
      <p class="hint">점 위에 마우스를 올리면 상호와 거리가 나옵니다. 좌표가 있는 POI 만 표시되며,
        점수 계산은 현장 조사 카페수(<code>카페수_500m</code>)와 비교해 <b>큰 쪽</b>을 씁니다.</p>`;
  }

  return { render, project, classify };
})();
