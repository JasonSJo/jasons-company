/* 상태 저장소 — 이 브라우저의 localStorage 에만 남는다. 서버 전송·계정 없음. */
const S = (() => {
  const KEY = 'cafe-trade-area/v1';

  const EMPTY = {
    sites: [],      // 후보지 (CSV 컬럼과 같은 키 + id/메모/상태)
    pois: [],       // 경쟁·시설 POI
    brand: {},      // 브랜드 파라미터 (비면 model.DEFAULTS)
    selected: null, // 상세/시뮬에서 보고 있는 후보지 id
    updated: null,
  };

  let state = load();

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return structuredClone(EMPTY);
      return Object.assign(structuredClone(EMPTY), JSON.parse(raw));
    } catch (e) {
      console.warn('저장된 데이터를 읽지 못했습니다. 빈 상태로 시작합니다.', e);
      return structuredClone(EMPTY);
    }
  }

  function save() {
    state.updated = new Date().toISOString();
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (e) {
      // 시크릿 모드·용량 초과 등 — 화면은 계속 동작하되 사용자에게 알린다
      U.toast('브라우저에 저장하지 못했습니다. 백업 내보내기를 사용하세요.');
      console.warn(e);
    }
  }

  const get = () => state;
  const sites = () => state.sites;
  const brand = () => M.withDefaults(state.brand);

  function setBrand(patch) {
    state.brand = Object.assign({}, state.brand, patch);
    save();
  }

  /* CSV 한 행 → 후보지 레코드. 알 수 없는 컬럼도 그대로 보존해 내보내기에서 살린다. */
  function addSite(row) {
    const s = Object.assign({}, row);
    s.id = s.id || U.uid();
    s.상태 = s.상태 || '검토';
    s.메모 = s.메모 || '';
    state.sites.push(s);
    return s;
  }

  function importSites(rows, { replace = false } = {}) {
    if (replace) state.sites = [];
    const before = state.sites.length;
    rows.filter(r => (r.후보지명 || '').trim()).forEach(addSite);
    save();
    return state.sites.length - before;
  }

  function importPois(rows, { replace = true } = {}) {
    const clean = rows.filter(r => (r.상호 || '').trim());
    state.pois = replace ? clean : state.pois.concat(clean);
    save();
    return clean.length;
  }

  const find = id => state.sites.find(s => s.id === id) || null;

  function update(id, patch) {
    const s = find(id);
    if (!s) return null;
    Object.assign(s, patch);
    save();
    return s;
  }

  function remove(id) {
    state.sites = state.sites.filter(s => s.id !== id);
    if (state.selected === id) state.selected = null;
    save();
  }

  function select(id) { state.selected = id; save(); }

  /* 선택된 후보지 — 없으면 점수 1위를 자동 선택한다. */
  function current() {
    return find(state.selected) || analyzed()[0]?.site || state.sites[0] || null;
  }

  /* 모든 후보지를 분석해 총점 내림차순으로. 화면 대부분이 이 결과를 쓴다. */
  function analyzed() {
    const b = brand();
    return state.sites
      .map(site => ({ site, r: M.analyze(site, state.pois, b) }))
      .sort((a, c) => c.r.총점 - a.r.총점 || c.r.손익.영업이익_만원 - a.r.손익.영업이익_만원);
  }

  function reset() { state = structuredClone(EMPTY); save(); }

  const exportAll = () => JSON.stringify(
    { app: 'cafe-trade-area', version: 1, exported: new Date().toISOString(), state }, null, 2);

  function restore(text) {
    const parsed = JSON.parse(text);
    const next = parsed.state || parsed;
    if (!next || !Array.isArray(next.sites)) throw new Error('형식이 올바르지 않습니다');
    state = Object.assign(structuredClone(EMPTY), next);
    save();
  }

  /* 데모 데이터 — analysis/후보지.example.csv · pois.example.csv 와 같은 값.
     처음 열었을 때 전체 흐름을 눌러볼 수 있게 한다. */
  function demo() {
    state = structuredClone(EMPTY);
    DEMO_SITES.forEach(addSite);
    state.pois = DEMO_POIS.slice();
    state.brand = structuredClone(DEMO_BRAND);
    save();
  }

  return {
    get, sites, brand, setBrand, addSite, importSites, importPois, find, update, remove,
    select, current, analyzed, reset, exportAll, restore, demo,
  };
})();
