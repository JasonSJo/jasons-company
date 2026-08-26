/* 앱 셸 — 탭 전환, 대시보드 집계, 백업/복원. */
(function () {
  "use strict";

  var TABS = ["dash", "prospects", "calendar", "review", "report"];
  var current = "dash";

  /* ── 탭 ─────────────────────────── */
  function show(tab) {
    if (TABS.indexOf(tab) < 0) tab = "dash";
    current = tab;
    TABS.forEach(function (t) {
      U.$("#panel-" + t).classList.toggle("hide", t !== tab);
    });
    U.$$(".tab").forEach(function (b) {
      b.setAttribute("aria-selected", String(b.dataset.tab === tab));
    });
    if (location.hash.slice(1) !== tab) history.replaceState(null, "", "#" + tab);
    renderCurrent();
  }

  function renderCurrent() {
    if (current === "dash") renderDash();
    else if (current === "prospects") Prospects.render();
    else if (current === "calendar") Calendar.render();
    else if (current === "review") Review.render();
    else if (current === "report") Report.render();
  }

  /* ── 대시보드 ─────────────────────────── */
  function stageCounts() {
    var c = {};
    Store.STAGES.forEach(function (st) { c[st] = 0; });
    Store.get().prospects.forEach(function (p) { c[p.stage] = (c[p.stage] || 0) + 1; });
    return c;
  }

  function calendarStats() {
    var cal = Store.get().calendar;
    var month = U.monthKey(U.today());
    var inMonth = cal.filter(function (it) { return U.monthKey(it.date) === month; });
    return {
      total: cal.length,
      month: inMonth.length,
      monthDone: inMonth.filter(function (it) { return it.done; }).length,
      overdue: cal.filter(function (it) { return !it.done && it.date < U.today(); }).length
    };
  }

  function renderDash() {
    var s = Store.get();
    var hot = s.prospects.filter(function (p) { return Prospects.score(p).pts >= 6; }).length;
    var sc = stageCounts();
    var cal = calendarStats();
    var rc = Review.counts();
    var contracted = sc["계약"] || 0;

    U.$("#kpis").innerHTML = [
      kpi("타깃", s.prospects.length, "곳", "🔥 최우선 " + hot + "곳 — 상단부터 접촉"),
      kpi("진행 중 상담·제안", (sc["상담"] || 0) + (sc["제안"] || 0), "건",
        "콜드 접촉 " + (sc["콜드 접촉"] || 0) + "곳 대기"),
      kpi("계약", contracted, "곳", contracted ? "납품 파이프라인 가동" : "STEP 3 영업이 매출의 관문"),
      kpi("이번 달 발행", cal.monthDone + "/" + cal.month, "건",
        cal.overdue ? "⚠️ 기한 지난 미발행 " + cal.overdue + "건" : "일정대로 진행 중")
    ].join("");

    U.$("#pipe").innerHTML = Store.STAGES.map(function (st) {
      return '<div class="step"><b>' + (sc[st] || 0) + "</b><span>" + st + "</span></div>";
    }).join("");

    /* 다음 액션 — QUICKSTART 의 STEP 순서를 그대로 따른다 */
    var actions = [
      {
        done: s.prospects.length >= 20,
        title: "타깃 20~30곳 수집",
        sub: "현재 " + s.prospects.length + "곳. 한 업종·한 지역에 집중해야 사례가 쌓입니다.",
        tab: "prospects", cta: "타깃 관리"
      },
      {
        done: hot > 0 && (sc["콜드 접촉"] || 0) + (sc["상담"] || 0) + (sc["제안"] || 0) + contracted > 0,
        title: "🔥 최우선 타깃부터 콜드 아웃리치",
        sub: hot ? "최우선 " + hot + "곳 대기 — ops/영업-아웃리치-키트.md 스크립트 사용" : "타깃을 먼저 채우세요.",
        tab: "prospects", cta: "접촉 시작"
      },
      {
        done: s.calendar.length > 0,
        title: "샘플·납품용 콘텐츠 캘린더 생성",
        sub: s.calendar.length ? s.calendar.length + "건 생성됨 · YAML 로 내보내 generate_content.py 에 투입" : "업체 프로필을 채우고 30일 캘린더를 만드세요.",
        tab: "calendar", cta: "캘린더"
      },
      {
        done: s.review.items.length > 0 && rc.검수대기 === 0,
        title: "생성된 초안 검수·승인",
        sub: s.review.items.length
          ? "대기 " + rc.검수대기 + "건" + (rc.high ? " · ⛔ HIGH 규제 검출 " + rc.high + "건 수정 필요" : "")
          : "generate_content.py 실행 후 manifest.json 을 불러오세요.",
        tab: "review", cta: "검수"
      },
      {
        done: s.metrics.length > 0,
        title: "월간 성과 리포트 발송",
        sub: s.metrics.length ? "지표 " + s.metrics.length + "건 입력됨 — 리포트를 내려받아 클라이언트에 발송" : "계약 후 매월 성과 리포트가 재계약을 만듭니다.",
        tab: "report", cta: "리포트"
      }
    ];

    U.$("#next-actions").innerHTML = actions.map(function (a, i) {
      return '<div class="todo' + (a.done ? " done" : "") + '">' +
        '<div class="n">' + (a.done ? "✓" : i + 1) + "</div>" +
        '<div><div class="t">' + U.esc(a.title) + '</div><div class="s">' + U.esc(a.sub) + "</div></div>" +
        '<button class="sm go" data-go="' + a.tab + '">' + a.cta + "</button></div>";
    }).join("");

    /* 이번 주 발행 예정 */
    var from = U.today(), to = U.iso(U.addDays(new Date(), 7));
    var week = s.calendar.filter(function (it) { return it.date >= from && it.date <= to; });
    U.$("#week-ahead").innerHTML = week.length ? week.map(function (it) {
      return '<div class="todo"><div class="n">' + it.date.slice(5).replace("-", "/") + "</div>" +
        '<div><div class="t">' + U.esc(it.topic) + "</div>" +
        '<div class="s">' + U.esc(Calendar.CHANNEL_LABEL[it.channel] || it.channel) +
        (it.brand ? " · " + U.esc(it.brand) : "") + (it.done ? " · 완료" : "") + "</div></div></div>";
    }).join("") : '<div class="empty" style="padding:24px 0">앞으로 7일간 예정된 발행이 없습니다.</div>';
  }

  function kpi(label, value, unit, desc) {
    return '<div class="kpi"><div class="k">' + U.esc(label) + "</div>" +
      '<div class="v">' + U.esc(value) + (unit ? "<small>" + U.esc(unit) + "</small>" : "") + "</div>" +
      '<div class="d">' + U.esc(desc) + "</div></div>";
  }

  /* ── 탭 배지 ─────────────────────────── */
  function renderPills() {
    var s = Store.get();
    var rc = Review.counts();
    setPill("#pill-prospects", s.prospects.length);
    setPill("#pill-calendar", s.calendar.filter(function (it) { return !it.done; }).length);
    setPill("#pill-review", rc.검수대기);
  }
  function setPill(sel, n) {
    var el = U.$(sel);
    el.textContent = n;
    el.classList.toggle("hide", !n);
  }

  /* ── 전역 액션 ─────────────────────────── */
  function bindGlobal() {
    U.$$(".tab").forEach(function (b) {
      b.addEventListener("click", function () { show(b.dataset.tab); });
    });
    document.addEventListener("click", function (e) {
      var go = e.target.getAttribute && e.target.getAttribute("data-go");
      if (go) show(go);
    });
    window.addEventListener("hashchange", function () { show(location.hash.slice(1)); });

    U.$("#btn-demo").addEventListener("click", function () {
      if (Store.get().prospects.length && !confirm("현재 데이터를 데모 데이터로 덮어씁니다. 계속할까요?")) return;
      Store.loadDemo();
      Calendar.fillForm();
      U.toast("데모 데이터를 불러왔습니다.");
    });

    U.$("#btn-backup").addEventListener("click", function () {
      U.download("console-backup-" + U.today() + ".json", Store.exportBackup(), "application/json");
      U.toast("백업 파일을 내려받았습니다.");
    });

    U.$("#btn-restore").addEventListener("click", function () {
      U.pickFile(".json,application/json", function (text) {
        try {
          Store.importBackup(text);
          Calendar.fillForm();
          U.toast("복원 완료.");
        } catch (e) { U.toast("복원 실패: " + e.message); }
      });
    });

    U.$("#btn-reset").addEventListener("click", function () {
      if (!confirm("이 브라우저에 저장된 모든 운영 데이터를 지웁니다.\n되돌릴 수 없습니다. 계속할까요?")) return;
      Store.reset();
      Calendar.fillForm();
      U.toast("초기화했습니다.");
    });
  }

  /* ── 시작 ─────────────────────────── */
  Store.load();
  Store.subscribe(function () { renderPills(); renderCurrent(); });

  bindGlobal();
  Prospects.bind();
  Calendar.bind();
  Review.bind();
  Report.bind();

  if (!U.$("#c-start").value) U.$("#c-start").value = U.today();
  if (!U.$("#m-month").value) U.$("#m-month").value = U.monthKey(U.today());

  renderPills();
  show(location.hash.slice(1) || "dash");
})();
