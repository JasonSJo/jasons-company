/* 콘텐츠 캘린더 — automation/build_calendar.py 의 토픽 공식·주간 리듬을 그대로 옮겼다. */
var Calendar = (function () {
  "use strict";

  // {kw}=핵심키워드, {region}=지역, {menu}=대표 항목
  var TOPIC_TEMPLATES = {
    "요식업": {
      blog: ["{region} {menu} 맛집", "{region} {situation} 좋은 곳", "{menu} 제대로 즐기는 법"],
      reels: ["{menu} 30초 소개", "{region} 웨이팅 그래도 가는 이유"],
      review: ["최근 리뷰 답글 일괄 처리"]
    },
    "병의원": {
      blog: ["{menu} 과정 단계별 정리", "{symptom} 확인할 3가지", "{menu} 후 관리 가이드"],
      reels: ["{menu} 궁금증 Q&A", "{symptom} 이럴 땐 내원하세요"],
      review: ["상담 후기 답글 정리"]
    },
    "뷰티": {
      blog: ["{menu} 시술 정보", "{region} {menu} 추천", "여름 {menu} 관리 팁"],
      reels: ["{menu} 전후 비교", "홈케어 3가지 루틴"],
      review: ["예약 고객 리뷰 답글"]
    },
    "전문서비스": {
      blog: ["{menu} 절차 정리", "{kw} 자주 묻는 질문", "{menu} 사례로 보는 핵심"],
      reels: ["{kw} 놓치기 쉬운 포인트"],
      review: ["상담 신청 응대 정리"]
    }
  };

  // 주간 발행 리듬 (파이썬 weekday: 0=월 … 6=일)
  var WEEKLY_RHYTHM = [[0, "blog"], [2, "reels"], [3, "blog"], [4, "review"], [5, "blog"]];
  var CHANNEL_LABEL = { blog: "블로그", reels: "릴스", review: "리뷰 답글" };
  var DOW = ["월", "화", "수", "목", "금", "토", "일"];

  // JS 요일(0=일)을 파이썬 요일(0=월)로 맞춘다.
  function pyWeekday(d) { return (d.getDay() + 6) % 7; }

  function fmt(tpl, biz, menu) {
    return tpl.replace(/\{region\}/g, biz.region || "")
      .replace(/\{menu\}/g, menu)
      .replace(/\{kw\}/g, biz.keyword || menu)
      .replace(/\{situation\}/g, biz.situation || "모임")
      .replace(/\{symptom\}/g, biz.symptom || "증상")
      .trim();
  }

  function build(biz, days, startISO) {
    var templates = TOPIC_TEMPLATES[biz.industry];
    if (!templates) throw new Error("지원하지 않는 업종: " + biz.industry);
    var menus = (biz.menus && biz.menus.length) ? biz.menus : [biz.keyword || "대표 항목"];

    var items = [], mi = 0, ti = { blog: 0, reels: 0, review: 0 };
    var start = U.parseISO(startISO);
    for (var offset = 0; offset < days; offset++) {
      var day = U.addDays(start, offset);
      for (var k = 0; k < WEEKLY_RHYTHM.length; k++) {
        var wd = WEEKLY_RHYTHM[k][0], channel = WEEKLY_RHYTHM[k][1];
        if (pyWeekday(day) !== wd) continue;
        var pool = templates[channel];
        var menu = menus[mi % menus.length];
        var topic = fmt(pool[ti[channel] % pool.length], biz, menu);
        ti[channel]++;
        mi++;
        items.push({
          date: U.iso(day),
          industry: biz.industry,
          channel: channel,
          brand: biz.brand || "",
          region: biz.region || "",
          strengths: biz.strengths || "",
          target: biz.target || "",
          topic: topic,
          done: false
        });
      }
    }
    return items;
  }

  /* ── 프로필 폼 ─────────────────────────── */
  var FIELDS = {
    "#b-industry": "industry", "#b-brand": "brand", "#b-region": "region",
    "#b-keyword": "keyword", "#b-situation": "situation", "#b-symptom": "symptom",
    "#b-strengths": "strengths", "#b-target": "target"
  };

  function fillForm() {
    var b = Store.get().business;
    Object.keys(FIELDS).forEach(function (sel) { U.$(sel).value = b[FIELDS[sel]] || ""; });
    U.$("#b-menus").value = (b.menus || []).join(", ");
    var meta = Store.get().calendarMeta;
    U.$("#c-start").value = meta.start || U.today();
    U.$("#c-days").value = meta.days || 30;
  }

  function readForm() {
    var b = {};
    Object.keys(FIELDS).forEach(function (sel) { b[FIELDS[sel]] = U.$(sel).value.trim(); });
    b.menus = U.$("#b-menus").value.split(",").map(function (m) { return m.trim(); })
      .filter(function (m) { return m; });
    return b;
  }

  function persistForm() {
    Store.commit(function (s) { s.business = readForm(); });
  }

  /* ── 생성 ─────────────────────────── */
  function rebuild() {
    var biz = readForm();
    if (!biz.brand) { U.toast("상호를 입력하세요."); U.$("#b-brand").focus(); return; }
    var days = Math.max(7, Math.min(120, U.toInt(U.$("#c-days").value, 30)));
    var start = U.$("#c-start").value || U.today();

    // 이미 완료 표시한 항목은 재생성 후에도 유지한다.
    var doneKeys = {};
    Store.get().calendar.forEach(function (it) {
      if (it.done) doneKeys[it.date + "|" + it.topic] = true;
    });

    var items;
    try { items = build(biz, days, start); }
    catch (e) { U.toast(e.message); return; }
    items.forEach(function (it) { it.done = !!doneKeys[it.date + "|" + it.topic]; });

    Store.commit(function (s) {
      s.business = biz;
      s.calendar = items;
      s.calendarMeta = { start: start, days: days, generatedAt: new Date().toISOString() };
    });
    view.month = U.monthKey(start);
    U.toast("캘린더 생성 완료 — " + items.length + "건");
  }

  /* ── 렌더 ─────────────────────────── */
  var view = { month: "" };

  function monthsInCalendar() {
    var seen = {};
    Store.get().calendar.forEach(function (it) { seen[U.monthKey(it.date)] = true; });
    return Object.keys(seen).sort();
  }

  function render() {
    var s = Store.get();
    var host = U.$("#c-view");
    if (!s.calendar.length) {
      host.innerHTML = '<div class="card"><div class="empty"><b>캘린더가 아직 없습니다</b>' +
        "업체 프로필을 채우고 <b>캘린더 생성</b>을 누르세요. 업종별 토픽 공식에 따라 발행일이 배정됩니다.</div></div>";
      return;
    }

    var months = monthsInCalendar();
    if (months.indexOf(view.month) < 0) view.month = months[0];
    var idx = months.indexOf(view.month);

    var byDate = {};
    s.calendar.forEach(function (it) { (byDate[it.date] = byDate[it.date] || []).push(it); });

    var y = U.toInt(view.month.slice(0, 4)), m = U.toInt(view.month.slice(5, 7));
    var first = new Date(y, m - 1, 1);
    var lead = pyWeekday(first);                  // 월요일 시작 그리드
    var daysInMonth = new Date(y, m, 0).getDate();
    var todayISO = U.today();

    var cells = [];
    for (var i = 0; i < lead; i++) cells.push('<div class="day mute"></div>');
    for (var d = 1; d <= daysInMonth; d++) {
      var dateISO = view.month + "-" + String(d).padStart(2, "0");
      var evs = (byDate[dateISO] || []).map(function (it) {
        var i2 = s.calendar.indexOf(it);
        return '<button class="ev ' + it.channel + (it.done ? " done" : "") + '" data-i="' + i2 +
          '" title="' + U.esc(CHANNEL_LABEL[it.channel] + " · " + it.topic) + ' (클릭: 완료 표시)">' +
          U.esc(it.topic) + "</button>";
      }).join("");
      cells.push('<div class="day' + (dateISO === todayISO ? " today" : "") + '">' +
        '<div class="dn">' + d + "</div>" + evs + "</div>");
    }

    var counts = { blog: 0, reels: 0, review: 0 }, done = 0;
    s.calendar.forEach(function (it) { counts[it.channel]++; if (it.done) done++; });

    host.innerHTML =
      '<div class="card">' +
        '<div class="panel-head" style="margin-bottom:12px">' +
          "<div><h3>" + y + "년 " + m + "월</h3>" +
            '<p class="hint" style="margin:2px 0 0">전체 ' + s.calendar.length + "건 · 블로그 " + counts.blog +
            " · 릴스 " + counts.reels + " · 리뷰 " + counts.review + " · 완료 " + done + "건</p></div>" +
          '<div class="acts">' +
            '<button class="sm" id="c-prev"' + (idx <= 0 ? " disabled" : "") + ">← 이전 달</button>" +
            '<button class="sm" id="c-next"' + (idx >= months.length - 1 ? " disabled" : "") + ">다음 달 →</button>" +
          "</div>" +
        "</div>" +
        '<div class="cal">' + DOW.map(function (w) { return '<div class="dow">' + w + "</div>"; }).join("") +
          cells.join("") + "</div>" +
        '<p class="hint">항목을 클릭하면 발행 완료로 표시됩니다. ' +
          '<span class="tag">블로그</span> <span class="tag">릴스</span> <span class="tag">리뷰 답글</span></p>' +
      "</div>";

    U.$("#c-prev").addEventListener("click", function () { view.month = months[idx - 1]; render(); });
    U.$("#c-next").addEventListener("click", function () { view.month = months[idx + 1]; render(); });
  }

  function onEventClick(e) {
    var btn = e.target.closest(".ev");
    if (!btn) return;
    var i = U.toInt(btn.dataset.i, -1);
    if (i < 0) return;
    Store.commit(function (s) {
      if (s.calendar[i]) s.calendar[i].done = !s.calendar[i].done;
    });
  }

  /* ── 내보내기 ─────────────────────────── */
  var YAML_KEYS = ["date", "industry", "channel", "brand", "region", "strengths", "target", "topic"];

  function exportYAML() {
    var s = Store.get();
    if (!s.calendar.length) { U.toast("먼저 캘린더를 생성하세요."); return; }
    var header = "# " + (s.business.brand || "") + " · " + s.business.industry + " · " +
      s.calendarMeta.start + "부터 " + s.calendarMeta.days + "일 · 운영 콘솔 생성 " + s.calendar.length + "건\n";
    U.download("content_calendar.generated.yaml", header + U.toYamlList(s.calendar, YAML_KEYS), "text/yaml");
    U.toast("YAML 저장 — python generate_content.py --calendar 로 이어서 실행하세요.");
  }

  function exportCSV() {
    var s = Store.get();
    if (!s.calendar.length) { U.toast("먼저 캘린더를 생성하세요."); return; }
    var rows = s.calendar.map(function (it) {
      return {
        "발행일": it.date, "채널": CHANNEL_LABEL[it.channel] || it.channel,
        "업종": it.industry, "상호": it.brand, "토픽": it.topic, "완료": it.done ? "Y" : "N"
      };
    });
    U.download("content_calendar.csv", U.objectsToCSV(rows, ["발행일", "채널", "업종", "상호", "토픽", "완료"]), "text/csv");
    U.toast("content_calendar.csv (콘텐츠 캘린더) 를 내려받았습니다.");
  }

  function bind() {
    fillForm();
    Object.keys(FIELDS).concat(["#b-menus"]).forEach(function (sel) {
      U.$(sel).addEventListener("change", persistForm);
    });
    U.$("#c-build").addEventListener("click", rebuild);
    U.$("#c-view").addEventListener("click", onEventClick);   // 위임: 재렌더에도 한 번만 등록
    U.$("#c-export-yaml").addEventListener("click", exportYAML);
    U.$("#c-export-csv").addEventListener("click", exportCSV);
  }

  return {
    CHANNEL_LABEL: CHANNEL_LABEL,
    build: build, render: render, bind: bind, fillForm: fillForm
  };
})();
