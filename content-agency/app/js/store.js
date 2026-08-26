/* 상태 저장소 — 전역 네임스페이스 Store.
   모든 데이터는 브라우저 localStorage 에만 남는다(서버 전송 없음). */
var Store = (function () {
  "use strict";

  var KEY = "contenthada.console.v1";
  var LEGACY_REVIEW_KEY = "review-status";   // automation/review.html 이 쓰던 키

  var STAGES = ["미접촉", "콜드 접촉", "상담", "제안", "계약", "보류"];
  var INDUSTRIES = ["요식업", "병의원", "뷰티", "전문서비스"];
  var REVIEW_STATES = ["검수대기", "승인", "보류", "반려"];

  function blank() {
    return {
      v: 1,
      prospects: [],
      business: {
        industry: "요식업", brand: "", region: "", keyword: "",
        situation: "", symptom: "", strengths: "", target: "", menus: []
      },
      calendar: [],
      calendarMeta: { start: "", days: 30, generatedAt: "" },
      review: { items: [], status: {}, loadedFrom: "" },
      metrics: [],
      reportMeta: { brand: "", month: "", editor: "" }
    };
  }

  var state = blank();
  var listeners = [];

  function load() {
    var raw = null;
    try { raw = localStorage.getItem(KEY); } catch (e) { /* 사생활 보호 모드 등 */ }
    if (raw) {
      try {
        var parsed = JSON.parse(raw);
        state = Object.assign(blank(), parsed);
        state.business = Object.assign(blank().business, parsed.business || {});
        state.review = Object.assign(blank().review, parsed.review || {});
        state.calendarMeta = Object.assign(blank().calendarMeta, parsed.calendarMeta || {});
        state.reportMeta = Object.assign(blank().reportMeta, parsed.reportMeta || {});
      } catch (e) { state = blank(); }
    }
    // review.html 에서 이미 판정한 승인 상태가 있으면 이어받는다.
    try {
      var legacy = JSON.parse(localStorage.getItem(LEGACY_REVIEW_KEY) || "{}");
      Object.keys(legacy).forEach(function (slug) {
        if (!state.review.status[slug]) state.review.status[slug] = legacy[slug];
      });
    } catch (e) { /* 무시 */ }
    return state;
  }

  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (e) {
      U.toast("저장 실패 — 브라우저 저장 공간을 확인하세요.");
    }
  }

  // 변경 → 저장 → 구독자에게 알림.
  function commit(fn) {
    if (fn) fn(state);
    save();
    listeners.forEach(function (l) { l(state); });
  }

  // 입력 중인 텍스트 필드가 재렌더로 포커스를 잃지 않도록, 저장만 하고 알리지 않는다.
  function quiet(fn) {
    if (fn) fn(state);
    save();
  }

  function subscribe(fn) { listeners.push(fn); }
  function get() { return state; }

  function reset() {
    state = blank();
    try { localStorage.removeItem(KEY); } catch (e) { /* 무시 */ }
    commit();
  }

  function exportBackup() {
    return JSON.stringify(state, null, 2);
  }

  function importBackup(text) {
    var parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== "object") throw new Error("형식 오류");
    state = Object.assign(blank(), parsed);
    state.business = Object.assign(blank().business, parsed.business || {});
    state.review = Object.assign(blank().review, parsed.review || {});
    commit();
  }

  /* ── 데모 데이터 (automation/*.example.* 와 동일한 값) ── */
  var DEMO_TARGETS = [
    { 상호: "성수 파스타랩", 업종: "요식업", 지역: "성수동", 연락처: "insta:@pastalab", 플레이스_리뷰수: "12", 답글여부: "N", SNS_최근게시_경과일: "45", 신규오픈_개월: "4", 웹사이트: "N" },
    { 상호: "연남 미소치과", 업종: "병의원", 지역: "연남동", 연락처: "02-000-0000", 플레이스_리뷰수: "8", 답글여부: "N", SNS_최근게시_경과일: "90", 신규오픈_개월: "12", 웹사이트: "Y" },
    { 상호: "라운드헤어", 업종: "뷰티", 지역: "연남동", 연락처: "insta:@roundhair", 플레이스_리뷰수: "35", 답글여부: "Y", SNS_최근게시_경과일: "20", 신규오픈_개월: "24", 웹사이트: "N" },
    { 상호: "강남 든든세무", 업종: "전문서비스", 지역: "강남", 연락처: "mail:tax@x.kr", 플레이스_리뷰수: "3", 답글여부: "N", SNS_최근게시_경과일: "120", 신규오픈_개월: "3", 웹사이트: "N" },
    { 상호: "판교 브런치하우스", 업종: "요식업", 지역: "판교", 연락처: "insta:@brunch", 플레이스_리뷰수: "52", 답글여부: "Y", SNS_최근게시_경과일: "10", 신규오픈_개월: "18", 웹사이트: "Y" },
    { 상호: "망원 왁싱스튜디오", 업종: "뷰티", 지역: "망원동", 연락처: "insta:@waxing", 플레이스_리뷰수: "15", 답글여부: "N", SNS_최근게시_경과일: "60", 신규오픈_개월: "5", 웹사이트: "N" }
  ];

  var DEMO_METRICS = [
    { channel: "블로그", metric: "검색 유입", this_month: 4200, last_month: 1350 },
    { channel: "블로그", metric: "상위노출 키워드", this_month: 8, last_month: 3 },
    { channel: "인스타", metric: "콘텐츠 도달", this_month: 42000, last_month: 18000 },
    { channel: "인스타", metric: "저장 수", this_month: 890, last_month: 410 },
    { channel: "플레이스", metric: "예약 문의", this_month: 63, last_month: 20 },
    { channel: "플레이스", metric: "신규 리뷰", this_month: 27, last_month: 12 },
    { channel: "전체", metric: "상담/예약 전환", this_month: 47, last_month: 19 }
  ];

  function loadDemo() {
    commit(function (s) {
      s.prospects = DEMO_TARGETS.map(function (r) { return Prospects.fromRow(r); });
      s.prospects[0].stage = "제안";
      s.prospects[1].stage = "콜드 접촉";
      s.prospects[3].stage = "상담";
      s.business = {
        industry: "요식업", brand: "성수 파스타랩", region: "성수동", keyword: "성수동 파스타",
        situation: "데이트", symptom: "", strengths: "생면 파스타, 예약제 소규모 다이닝, 시즌 메뉴",
        target: "20~30대 데이트·모임 고객",
        menus: ["트러플 파스타", "라구 파스타", "시즌 리조또", "하우스 와인"]
      };
      s.metrics = DEMO_METRICS.map(function (m) { return Object.assign({ id: U.uid() }, m); });
      s.reportMeta = { brand: "성수 파스타랩", month: U.monthKey(U.today()), editor: "담당 에디터" };
      s.calendar = Calendar.build(s.business, 30, U.today());
      s.calendarMeta = { start: U.today(), days: 30, generatedAt: new Date().toISOString() };
    });
  }

  return {
    STAGES: STAGES, INDUSTRIES: INDUSTRIES, REVIEW_STATES: REVIEW_STATES,
    load: load, get: get, commit: commit, quiet: quiet, subscribe: subscribe, reset: reset,
    exportBackup: exportBackup, importBackup: importBackup, loadDemo: loadDemo
  };
})();
