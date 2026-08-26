/* 타깃·영업 파이프라인 — automation/score_prospects.py 의 점수 로직을 그대로 옮겼다. */
var Prospects = (function () {
  "use strict";

  var CSV_COLUMNS = ["상호", "업종", "지역", "연락처", "플레이스_리뷰수", "답글여부", "SNS_최근게시_경과일", "신규오픈_개월", "웹사이트"];
  var NEGATIVE = ["N", "NO", "아니오", "X", "없음", ""];

  // CSV 한 행 → 내부 레코드
  function fromRow(r) {
    return {
      id: U.uid(),
      name: (r["상호"] || "").trim(),
      industry: (r["업종"] || "").trim(),
      region: (r["지역"] || "").trim(),
      contact: (r["연락처"] || "").trim(),
      reviews: U.toInt(r["플레이스_리뷰수"], 999),
      replies: (r["답글여부"] || "").trim(),
      snsDays: U.toInt(r["SNS_최근게시_경과일"], 0),
      openedMonths: U.toInt(r["신규오픈_개월"], 99),
      website: (r["웹사이트"] || "").trim(),
      stage: "미접촉",
      memo: "",
      updated: new Date().toISOString()
    };
  }

  function toRow(p) {
    return {
      "상호": p.name, "업종": p.industry, "지역": p.region, "연락처": p.contact,
      "플레이스_리뷰수": p.reviews, "답글여부": p.replies,
      "SNS_최근게시_경과일": p.snsDays, "신규오픈_개월": p.openedMonths, "웹사이트": p.website
    };
  }

  // 니즈 점수 = 전환 가능성. score_prospects.py 의 score() 와 동일한 가중치.
  function score(p) {
    var pts = 0, why = [];
    if (U.toInt(p.reviews, 999) < 20) { pts += 2; why.push("리뷰 적음"); }
    if (NEGATIVE.indexOf(String(p.replies).trim().toUpperCase()) >= 0) { pts += 2; why.push("답글 없음"); }
    if (U.toInt(p.snsDays, 0) > 30) { pts += 2; why.push("SNS 방치"); }
    var opened = U.toInt(p.openedMonths, 99);
    if (opened > 0 && opened <= 6) { pts += 2; why.push("신규 오픈"); }
    if (NEGATIVE.indexOf(String(p.website).trim().toUpperCase()) >= 0) { pts += 1; why.push("웹 없음"); }
    return { pts: pts, why: why };
  }

  function tier(pts) {
    if (pts >= 6) return { label: "🔥 최우선", cls: "b-hot" };
    if (pts >= 4) return { label: "⭐ 우선", cls: "b-warm" };
    return { label: "일반", cls: "b-cold" };
  }

  /* ── 필터·정렬 ─────────────────────────── */
  function visible() {
    var s = Store.get();
    var q = (U.$("#p-q").value || "").trim().toLowerCase();
    var ind = U.$("#p-industry").value;
    var stage = U.$("#p-stage").value;
    var sort = U.$("#p-sort").value;

    var rows = s.prospects.filter(function (p) {
      if (ind && p.industry !== ind) return false;
      if (stage && p.stage !== stage) return false;
      if (q) {
        var hay = (p.name + " " + p.region + " " + p.contact).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });

    rows.sort(function (a, b) {
      if (sort === "name") return a.name.localeCompare(b.name, "ko");
      if (sort === "stage") return Store.STAGES.indexOf(a.stage) - Store.STAGES.indexOf(b.stage);
      if (sort === "updated") return String(b.updated).localeCompare(String(a.updated));
      return score(b).pts - score(a).pts || a.name.localeCompare(b.name, "ko");
    });
    return rows;
  }

  /* ── 렌더 ─────────────────────────── */
  function render() {
    var s = Store.get();
    var host = U.$("#p-list");

    if (!s.prospects.length) {
      host.innerHTML = '<div class="card"><div class="empty"><b>아직 타깃이 없습니다</b>' +
        'CSV 를 가져오거나 직접 추가해 보세요. 형식은 <code>automation/타겟리스트.example.csv</code> 와 같습니다.<br>' +
        '헤더: <code>' + CSV_COLUMNS.join(",") + '</code></div></div>';
      U.$("#p-summary").textContent = "";
      return;
    }

    var rows = visible();
    var head = '<tr><th>#</th><th>상호</th><th>업종·지역</th><th>연락처</th>' +
      '<th class="num">점수</th><th>등급</th><th>근거</th><th>단계</th><th>메모</th><th></th></tr>';

    var body = rows.map(function (p, i) {
      var sc = score(p), t = tier(sc.pts);
      var stageOpts = Store.STAGES.map(function (st) {
        return '<option' + (st === p.stage ? " selected" : "") + '>' + U.esc(st) + "</option>";
      }).join("");
      return '<tr data-id="' + p.id + '">' +
        "<td>" + (i + 1) + "</td>" +
        '<td><b>' + U.esc(p.name) + "</b></td>" +
        "<td>" + U.esc(p.industry) + (p.region ? " · " + U.esc(p.region) : "") + "</td>" +
        "<td>" + U.esc(p.contact) + "</td>" +
        '<td class="num"><b>' + sc.pts + "</b></td>" +
        '<td><span class="badge ' + t.cls + '">' + t.label + "</span></td>" +
        '<td class="why">' + (sc.why.join(", ") || "-") + "</td>" +
        '<td><select data-act="stage">' + stageOpts + "</select></td>" +
        '<td><input data-act="memo" value="' + U.esc(p.memo) + '" placeholder="다음 액션·통화 메모"/></td>' +
        '<td><button class="sm ghost danger" data-act="del" title="삭제">삭제</button></td>' +
        "</tr>";
    }).join("");

    host.innerHTML = '<div class="tablewrap"><table><thead>' + head + "</thead><tbody>" +
      (body || '<tr><td colspan="10"><div class="empty">조건에 맞는 타깃이 없습니다.</div></td></tr>') +
      "</tbody></table></div>";

    var hot = s.prospects.filter(function (p) { return score(p).pts >= 6; }).length;
    U.$("#p-summary").innerHTML = "전체 " + s.prospects.length + "곳 · 표시 " + rows.length +
      "곳 · 🔥 최우선 <b>" + hot + "</b>곳 — 상단부터 접촉하면 같은 노력으로 계약 확률이 올라갑니다.";
  }

  /* ── 이벤트 ─────────────────────────── */
  function update(id, patch, quiet) {
    (quiet ? Store.quiet : Store.commit)(function (s) {
      var p = s.prospects.filter(function (x) { return x.id === id; })[0];
      if (!p) return;
      Object.assign(p, patch, { updated: new Date().toISOString() });
    });
  }

  function importCSV(text) {
    var objs = U.csvToObjects(text);
    if (!objs.length) { U.toast("CSV 에 데이터가 없습니다."); return; }
    if (!("상호" in objs[0])) {
      U.toast("헤더를 확인하세요: " + CSV_COLUMNS.join(","));
      return;
    }
    var existing = {};
    Store.get().prospects.forEach(function (p) { existing[p.name] = p; });

    var added = 0, merged = 0;
    Store.commit(function (s) {
      objs.forEach(function (r) {
        var rec = fromRow(r);
        if (!rec.name) return;
        var prev = existing[rec.name];
        if (prev) {
          // 이미 있는 곳은 지표만 갱신하고 단계·메모는 지키다.
          Object.assign(prev, rec, { id: prev.id, stage: prev.stage, memo: prev.memo, updated: new Date().toISOString() });
          merged++;
        } else {
          s.prospects.push(rec);
          existing[rec.name] = rec;
          added++;
        }
      });
    });
    U.toast("가져오기 완료 — 신규 " + added + "곳, 갱신 " + merged + "곳");
  }

  function exportCSV() {
    var s = Store.get();
    if (!s.prospects.length) { U.toast("내보낼 타깃이 없습니다."); return; }
    var rows = s.prospects.map(function (p) {
      var r = toRow(p);
      r["단계"] = p.stage;
      r["메모"] = p.memo;
      r["점수"] = score(p).pts;
      return r;
    });
    U.download("prospects.csv", U.objectsToCSV(rows, CSV_COLUMNS.concat(["점수", "단계", "메모"])), "text/csv");
    U.toast("prospects.csv (타겟리스트) 를 내려받았습니다.");
  }

  // score_prospects.py 가 만드는 output/타겟_우선순위.md 와 같은 형식.
  function exportMarkdown() {
    var s = Store.get();
    if (!s.prospects.length) { U.toast("내보낼 타깃이 없습니다."); return; }
    var ranked = s.prospects.slice().sort(function (a, b) { return score(b).pts - score(a).pts; });
    var lines = [
      "# 타깃 우선순위 (니즈 점수 높은 순)", "",
      "총 " + ranked.length + "곳 · 점수 = 콘텐츠 니즈 = 전환 가능성. 상단부터 접촉 권장.", "",
      "| 순위 | 상호 | 업종 | 지역 | 연락처 | 점수 | 등급 | 단계 | 근거 |",
      "|---:|---|---|---|---|---:|---|---|---|"
    ];
    ranked.forEach(function (p, i) {
      var sc = score(p);
      lines.push("| " + (i + 1) + " | " + p.name + " | " + p.industry + " | " + p.region + " | " +
        p.contact + " | " + sc.pts + " | " + tier(sc.pts).label + " | " + p.stage + " | " +
        (sc.why.join(", ") || "-") + " |");
    });
    U.download("prospects_priority.md", lines.join("\n") + "\n", "text/markdown");
    U.toast("prospects_priority.md (타깃 우선순위) 를 내려받았습니다.");
  }

  function addBlank() {
    var name = prompt("상호를 입력하세요");
    if (!name) return;
    Store.commit(function (s) {
      var rec = fromRow({ 상호: name, 업종: Store.get().business.industry || "요식업" });
      rec.reviews = 0; rec.replies = "N"; rec.snsDays = 0; rec.openedMonths = 99; rec.website = "N";
      s.prospects.unshift(rec);
    });
    U.toast(name + " 추가됨 — 표에서 단계·메모를 채우세요.");
  }

  function bind() {
    ["#p-q", "#p-industry", "#p-stage", "#p-sort"].forEach(function (sel) {
      U.$(sel).addEventListener("input", render);
      U.$(sel).addEventListener("change", render);
    });
    U.$("#p-add").addEventListener("click", addBlank);
    U.$("#p-import").addEventListener("click", function () {
      U.pickFile(".csv,text/csv", importCSV);
    });
    U.$("#p-export-csv").addEventListener("click", exportCSV);
    U.$("#p-export-md").addEventListener("click", exportMarkdown);

    U.$("#p-list").addEventListener("change", function (e) {
      var tr = e.target.closest("tr");
      if (!tr) return;
      var act = e.target.getAttribute("data-act");
      if (act === "stage") update(tr.dataset.id, { stage: e.target.value });
      if (act === "memo") update(tr.dataset.id, { memo: e.target.value }, true);
    });
    U.$("#p-list").addEventListener("click", function (e) {
      if (e.target.getAttribute("data-act") !== "del") return;
      var tr = e.target.closest("tr");
      var id = tr.dataset.id;
      var p = Store.get().prospects.filter(function (x) { return x.id === id; })[0];
      if (!p || !confirm("'" + p.name + "' 을(를) 삭제할까요?")) return;
      Store.commit(function (s) {
        s.prospects = s.prospects.filter(function (x) { return x.id !== id; });
      });
    });

    // 필터 셀렉트 채우기
    U.$("#p-industry").innerHTML = '<option value="">전체 업종</option>' +
      Store.INDUSTRIES.map(function (i) { return "<option>" + i + "</option>"; }).join("");
    U.$("#p-stage").innerHTML = '<option value="">전체 단계</option>' +
      Store.STAGES.map(function (s) { return "<option>" + s + "</option>"; }).join("");
  }

  return {
    CSV_COLUMNS: CSV_COLUMNS,
    fromRow: fromRow, score: score, tier: tier,
    render: render, bind: bind
  };
})();
