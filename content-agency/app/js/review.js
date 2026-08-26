/* 콘텐츠 검수 — automation/review.html 을 대체하고,
   compliance_check.py 의 규제 금지어 규칙을 초안에 자동 적용한다. */
var Review = (function () {
  "use strict";

  // [정규식, 심각도, 설명, 근거] — HIGH=발행 차단 권장, WARN=검토 권장
  var RULES = [
    // 공통 최상급·보장 (표시광고법)
    [/1위|국내\s*1위|업계\s*1위/, "HIGH", "객관적 근거 없는 '1위'", "표시광고법"],
    [/최고(의|급)?|최상(의)?|최강/, "WARN", "최상급 표현", "표시광고법"],
    [/유일(한|무이)|단\s*하나의/, "WARN", "'유일' 배타적 표현", "표시광고법"],
    [/100\s*%|백\s*퍼센트/, "HIGH", "'100%' 단정", "표시광고법"],
    [/무조건|절대(적)?|반드시/, "WARN", "단정·절대 표현", "표시광고법"],
    [/보장(합니다|해\s*드립니다|됩니다)?/, "WARN", "'보장' 표현(맥락 확인)", "표시광고법"],
    // 의료 (의료법·의료광고)
    [/완치|완벽(하게|한)?\s*(치료|개선)?/, "HIGH", "치료효과 단정('완치/완벽')", "의료법"],
    [/부작용(이)?\s*(전혀\s*)?(없|無)/, "HIGH", "'부작용 없음' 단정", "의료법"],
    [/평생|영구(적)?/, "WARN", "'평생/영구' 지속효과 단정", "의료법"],
    [/즉시\s*효과|바로\s*효과/, "WARN", "즉효성 단정", "의료법"],
    [/명의|신의\s*손/, "WARN", "과장된 의료인 표현", "의료법"],
    [/세계\s*최초|국내\s*최초/, "WARN", "근거 필요한 '최초'", "의료법·표시광고법"],
    // 법률·세무 (변호사법·세무사법)
    [/승소\s*(보장|확정)|반드시\s*승소|무조건\s*승소/, "HIGH", "승소 보장 표현", "변호사법"],
    [/100\s*%\s*환급|환급\s*보장|무조건\s*환급/, "HIGH", "환급 보장 표현", "세무사법"]
  ];

  // 발행 카피가 아닌 내부 메모(HTML 주석·검수 체크박스)는 건너뛴다.
  function scan(text) {
    var hits = [];
    String(text || "").split("\n").forEach(function (line, i) {
      var stripped = line.trim();
      if (stripped.indexOf("<!--") === 0) return;
      if (/^- \[[ xX]\]/.test(stripped)) return;
      RULES.forEach(function (r) {
        var m = r[0].exec(line);
        if (m) hits.push({ line: i + 1, sev: r[1], term: m[0], desc: r[2], law: r[3], ctx: stripped.slice(0, 80) });
      });
    });
    return hits;
  }

  // dry-run 항목의 preview 는 발행 카피가 아니라 조립된 프롬프트다.
  // 프롬프트에는 가드레일 설명("'완치' 금지" 등)이 들어 있어 그대로 스캔하면 오탐이 된다.
  function scanItem(it) {
    if (it && it.mode === "dry-run") return [];
    return scan(it ? it.preview : "");
  }

  function severityOf(hits) {
    if (hits.some(function (h) { return h.sev === "HIGH"; })) return "high";
    return hits.length ? "warn" : "clean";
  }

  /* ── 데이터 로드 ─────────────────────────── */
  function loadItems(data, source) {
    if (!Array.isArray(data)) throw new Error("최상위가 항목 배열이어야 합니다.");
    Store.commit(function (s) {
      s.review.items = data.map(function (it) {
        return {
          slug: it.slug || U.uid(),
          file: it.file || "",
          industry: it.industry || "",
          channel: it.channel || "",
          topic: it.topic || "(제목 없음)",
          brand: it.brand || "",
          mode: it.mode || "",
          preview: it.preview || ""
        };
      });
      s.review.loadedFrom = source || "";
      // manifest 의 초기 상태는 검수대기. 기존 판정은 유지한다.
      s.review.items.forEach(function (it) {
        if (!s.review.status[it.slug]) {
          var orig = data.filter(function (d) { return d.slug === it.slug; })[0];
          s.review.status[it.slug] = (orig && orig.status) || "검수대기";
        }
      });
    });
    U.toast("불러오기 완료 — " + data.length + "건");
  }

  function openFile() {
    U.pickFile(".json,application/json", function (text, name) {
      try { loadItems(JSON.parse(text), name); }
      catch (e) { U.toast("JSON 파싱 실패: " + e.message); }
    });
  }

  // 로컬 서버(python -m http.server)로 열었을 때만 동작한다.
  function fetchOutput() {
    var paths = ["../automation/output/manifest.json", "output/manifest.json"];
    (function next(i) {
      if (i >= paths.length) {
        U.toast("manifest.json 을 찾지 못했습니다. 파일 열기를 사용하세요.");
        return;
      }
      fetch(paths[i])
        .then(function (r) { if (!r.ok) throw new Error("404"); return r.json(); })
        .then(function (d) { loadItems(d, paths[i]); })
        .catch(function () { next(i + 1); });
    })(0);
  }

  /* ── 렌더 ─────────────────────────── */
  function statusClass(st) {
    return { "승인": "b-ok", "보류": "b-hold", "반려": "b-no" }[st] || "b-wait";
  }

  function counts() {
    var s = Store.get(), c = { 검수대기: 0, 승인: 0, 보류: 0, 반려: 0, high: 0 };
    s.review.items.forEach(function (it) {
      var st = s.review.status[it.slug] || "검수대기";
      c[st] = (c[st] || 0) + 1;
      if (severityOf(scanItem(it)) === "high") c.high++;
    });
    return c;
  }

  function render() {
    var s = Store.get(), host = U.$("#r-list");
    if (!s.review.items.length) {
      host.innerHTML = '<div class="card"><div class="empty"><b>불러온 초안이 없습니다</b>' +
        '<code>cd content-agency/automation &amp;&amp; python generate_content.py</code> 실행 후 생기는 ' +
        "<code>output/manifest.json</code> 을 열어 주세요.</div></div>";
      U.$("#r-summary").textContent = "불러온 항목이 없습니다.";
      return;
    }

    var fSt = U.$("#r-filter").value;
    var fFlag = U.$("#r-flag").value;
    var q = (U.$("#r-q").value || "").trim().toLowerCase();

    var rows = s.review.items.filter(function (it) {
      var st = s.review.status[it.slug] || "검수대기";
      if (fSt && st !== fSt) return false;
      var sev = severityOf(scanItem(it));
      if (fFlag === "high" && sev !== "high") return false;
      if (fFlag === "any" && sev === "clean") return false;
      if (fFlag === "clean" && sev !== "clean") return false;
      if (q && (it.topic + " " + it.brand).toLowerCase().indexOf(q) < 0) return false;
      return true;
    });

    host.innerHTML = rows.length ? rows.map(function (it) {
      var st = s.review.status[it.slug] || "검수대기";
      var hits = scanItem(it);
      var flags = hits.map(function (h) {
        return '<div class="flag' + (h.sev === "HIGH" ? " high" : "") + '">' +
          (h.sev === "HIGH" ? "⛔" : "⚠️") + " L" + h.line + " [" + h.sev + "] '" + U.esc(h.term) + "' — " +
          U.esc(h.desc) + " (" + U.esc(h.law) + ")" +
          '<span class="ctx">…' + U.esc(h.ctx) + "…</span></div>";
      }).join("");
      var blocked = hits.some(function (h) { return h.sev === "HIGH"; });

      return '<div class="rv" data-slug="' + U.esc(it.slug) + '">' +
        '<div class="row"><div>' +
          '<div class="tags">' +
            (it.industry ? '<span class="tag">' + U.esc(it.industry) + "</span>" : "") +
            (it.channel ? '<span class="tag">' + U.esc(Calendar.CHANNEL_LABEL[it.channel] || it.channel) + "</span>" : "") +
            (it.brand ? '<span class="tag">' + U.esc(it.brand) + "</span>" : "") +
            (it.mode ? '<span class="tag">' + U.esc(it.mode) + "</span>" : "") +
          "</div><h4>" + U.esc(it.topic) + "</h4></div>" +
          '<span class="badge ' + statusClass(st) + '">' + st + "</span>" +
        "</div>" +
        "<pre>" + U.esc(it.preview || "(미리보기 없음)") + "</pre>" +
        (flags ? '<div class="flags">' + flags + "</div>" : "") +
        (it.mode === "dry-run" ? '<p class="hint">dry-run 초안(프롬프트)이라 규제 스캔을 건너뜁니다. ' +
          "실제 콘텐츠는 <code>--live</code> 생성 후 검수하세요.</p>" : "") +
        '<div class="acts">' +
          '<button class="sm" data-act="승인"' + (blocked ? ' title="⛔ HIGH 위반을 먼저 수정하세요"' : "") + ">승인</button>" +
          '<button class="sm" data-act="보류">보류</button>' +
          '<button class="sm" data-act="반려">반려</button>' +
          '<button class="sm ghost" data-act="검수대기">되돌리기</button>' +
        "</div></div>";
    }).join("") : '<div class="card"><div class="empty">조건에 맞는 항목이 없습니다.</div></div>';

    var c = counts();
    U.$("#r-summary").innerHTML =
      "대기 " + c.검수대기 + " · <b style='color:var(--ok)'>승인 " + c.승인 + "</b> · " +
      "<b style='color:var(--hold)'>보류 " + c.보류 + "</b> · <b style='color:var(--no)'>반려 " + c.반려 + "</b>" +
      (c.high ? " · ⛔ HIGH 검출 <b style='color:var(--no)'>" + c.high + "건</b> (발행 전 수정 필요)" : " · 규제 검출 없음") +
      (s.review.loadedFrom ? " · 출처 <code>" + U.esc(s.review.loadedFrom) + "</code>" : "");
  }

  function setStatus(slug, st) {
    var it = Store.get().review.items.filter(function (x) { return x.slug === slug; })[0];
    if (st === "승인" && it) {
      var hits = scanItem(it);
      if (hits.some(function (h) { return h.sev === "HIGH"; }) &&
        !confirm("⛔ HIGH 규제 위반이 검출된 초안입니다.\n행정처분·과태료 리스크가 있습니다.\n그래도 승인할까요?")) return;
    }
    Store.commit(function (s) { s.review.status[slug] = st; });
  }

  function exportApproved() {
    var s = Store.get();
    var approved = s.review.items.filter(function (it) {
      return (s.review.status[it.slug] || "") === "승인";
    }).map(function (it) {
      return Object.assign({}, it, { status: "승인" });
    });
    if (!approved.length) { U.toast("승인된 항목이 없습니다."); return; }
    U.download("approved.json", JSON.stringify(approved, null, 2), "application/json");
    U.toast("approved.json 저장 — automation/output/ 에 넣고 publish.py 를 실행하세요.");
  }

  function bind() {
    U.$("#r-open").addEventListener("click", openFile);
    U.$("#r-fetch").addEventListener("click", fetchOutput);
    U.$("#r-export").addEventListener("click", exportApproved);
    ["#r-filter", "#r-flag", "#r-q"].forEach(function (sel) {
      U.$(sel).addEventListener("input", render);
      U.$(sel).addEventListener("change", render);
    });
    U.$("#r-list").addEventListener("click", function (e) {
      var act = e.target.getAttribute("data-act");
      if (!act) return;
      var card = e.target.closest(".rv");
      if (card) setStatus(card.dataset.slug, act);
    });
  }

  return { scan: scan, scanItem: scanItem, severityOf: severityOf, counts: counts, render: render, bind: bind };
})();
