/* 월간 성과 리포트 — automation/report.py 와 같은 형식의 마크다운을 만든다. */
var Report = (function () {
  "use strict";

  var CSV_COLUMNS = ["channel", "metric", "this_month", "last_month"];

  function pct(cur, prev) {
    if (!prev) return cur ? "신규" : "-";
    var d = (cur - prev) / prev * 100;
    return (d >= 0 ? "+" : "") + d.toFixed(0) + "%";
  }

  function deltaClass(cur, prev) {
    if (!prev) return "flat";
    if (cur > prev) return "up";
    if (cur < prev) return "down";
    return "flat";
  }

  /* ── 마크다운 생성 ─────────────────────────── */
  function markdown() {
    var s = Store.get(), meta = s.reportMeta;
    var brand = meta.brand || "(상호)";
    var month = meta.month || "YYYY-MM";
    var editor = meta.editor || "담당 에디터";

    var lines = [
      "# 월간 성과 리포트 — " + brand,
      "> " + month + " · 담당 " + editor, "",
      "## 1. 한눈에 보기", "",
      "| 채널 | 지표 | 이번 달 | 지난 달 | 증감 |",
      "|---|---|---:|---:|---:|"
    ];

    var improved = [];
    s.metrics.forEach(function (r) {
      var cur = U.toNum(r.this_month), prev = U.toNum(r.last_month);
      lines.push("| " + (r.channel || "") + " | " + (r.metric || "") + " | " +
        U.comma(cur) + " | " + U.comma(prev) + " | " + pct(cur, prev) + " |");
      if (prev && cur > prev) improved.push({ metric: r.metric, change: pct(cur, prev), rate: (cur - prev) / prev });
    });

    lines.push("", "## 2. 핵심 요약", "");
    if (improved.length) {
      var top = improved.sort(function (a, b) { return b.rate - a.rate; }).slice(0, 3);
      lines.push("이번 달 개선 지표: " + top.map(function (t) {
        return t.metric + "(" + t.change + ")";
      }).join(", ") + ".");
    } else {
      lines.push("이번 달은 기반 데이터를 쌓는 단계로, 다음 달 성장 폭 확대가 기대됩니다.");
    }

    lines.push(
      "", "## 3. 다음 달 전략 제안", "",
      "- [ ] 개선 지표 채널에 콘텐츠 비중 확대",
      "- [ ] 성과 낮은 키워드 교체 및 A/B 테스트",
      "- [ ] 시즌 이슈 콘텐츠 선제 기획", "",
      "## 4. 논의 필요 (미팅 안건)", "",
      "- 예산·채널 확장 등 비용 발생 항목은 클라이언트 승인 필요 💳", ""
    );
    return lines.join("\n");
  }

  /* ── 렌더 ─────────────────────────── */
  function render() {
    var s = Store.get();

    U.$("#m-brand").value = s.reportMeta.brand || "";
    U.$("#m-month").value = s.reportMeta.month || "";
    U.$("#m-editor").value = s.reportMeta.editor || "";

    var host = U.$("#m-table");
    if (!s.metrics.length) {
      host.innerHTML = '<div class="card"><div class="empty"><b>지표가 없습니다</b>' +
        "<b>지표 추가</b>로 직접 입력하거나, <code>automation/metrics.example.csv</code> 형식의 CSV 를 가져오세요.<br>" +
        "헤더: <code>" + CSV_COLUMNS.join(",") + "</code></div></div>";
      U.$("#m-preview").textContent = markdown();
      return;
    }

    var body = s.metrics.map(function (r) {
      var cur = U.toNum(r.this_month), prev = U.toNum(r.last_month);
      return '<tr data-id="' + r.id + '">' +
        '<td><input data-f="channel" value="' + U.esc(r.channel) + '"/></td>' +
        '<td><input data-f="metric" value="' + U.esc(r.metric) + '"/></td>' +
        '<td class="num"><input data-f="this_month" type="number" value="' + U.esc(r.this_month) + '"/></td>' +
        '<td class="num"><input data-f="last_month" type="number" value="' + U.esc(r.last_month) + '"/></td>' +
        '<td class="num"><span class="delta ' + deltaClass(cur, prev) + '">' + pct(cur, prev) + "</span></td>" +
        '<td><button class="sm ghost danger" data-act="del">삭제</button></td></tr>';
    }).join("");

    host.innerHTML = '<div class="tablewrap"><table><thead><tr>' +
      "<th>채널</th><th>지표</th><th class=\"num\">이번 달</th><th class=\"num\">지난 달</th><th class=\"num\">증감</th><th></th>" +
      "</tr></thead><tbody>" + body + "</tbody></table></div>";

    U.$("#m-preview").textContent = markdown();
  }

  // 표 전체를 다시 그리지 않고 해당 행의 증감과 미리보기만 갱신한다.
  function refreshRow(tr) {
    var r = Store.get().metrics.filter(function (x) { return x.id === tr.dataset.id; })[0];
    if (!r) return;
    var cur = U.toNum(r.this_month), prev = U.toNum(r.last_month);
    var cell = tr.querySelector(".delta");
    if (cell) {
      cell.textContent = pct(cur, prev);
      cell.className = "delta " + deltaClass(cur, prev);
    }
    U.$("#m-preview").textContent = markdown();
  }

  /* ── 조작 ─────────────────────────── */
  function addRow() {
    Store.commit(function (s) {
      s.metrics.push({ id: U.uid(), channel: "", metric: "", this_month: 0, last_month: 0 });
    });
  }

  function importCSV(text) {
    var objs = U.csvToObjects(text);
    if (!objs.length) { U.toast("CSV 에 데이터가 없습니다."); return; }
    if (!("metric" in objs[0])) { U.toast("헤더를 확인하세요: " + CSV_COLUMNS.join(",")); return; }
    Store.commit(function (s) {
      s.metrics = objs.map(function (o) {
        return {
          id: U.uid(), channel: o.channel || "", metric: o.metric || "",
          this_month: U.toNum(o.this_month), last_month: U.toNum(o.last_month)
        };
      });
    });
    U.toast("지표 " + objs.length + "건을 가져왔습니다.");
  }

  function bind() {
    ["#m-brand", "#m-month", "#m-editor"].forEach(function (sel) {
      U.$(sel).addEventListener("change", function () {
        Store.commit(function (s) {
          s.reportMeta = {
            brand: U.$("#m-brand").value.trim(),
            month: U.$("#m-month").value,
            editor: U.$("#m-editor").value.trim()
          };
        });
      });
    });

    U.$("#m-add").addEventListener("click", addRow);
    U.$("#m-import").addEventListener("click", function () { U.pickFile(".csv,text/csv", importCSV); });
    U.$("#m-copy").addEventListener("click", function () { U.copy(markdown()); });
    U.$("#m-download").addEventListener("click", function () {
      U.download("monthly_report.md", markdown(), "text/markdown");
      U.toast("monthly_report.md (월간 리포트) 를 내려받았습니다.");
    });

    U.$("#m-table").addEventListener("change", function (e) {
      var f = e.target.getAttribute("data-f");
      if (!f) return;
      var tr = e.target.closest("tr");
      Store.quiet(function (s) {
        var r = s.metrics.filter(function (x) { return x.id === tr.dataset.id; })[0];
        if (!r) return;
        r[f] = (f === "this_month" || f === "last_month") ? U.toNum(e.target.value) : e.target.value;
      });
      refreshRow(tr);
    });
    U.$("#m-table").addEventListener("click", function (e) {
      if (e.target.getAttribute("data-act") !== "del") return;
      var tr = e.target.closest("tr");
      Store.commit(function (s) {
        s.metrics = s.metrics.filter(function (x) { return x.id !== tr.dataset.id; });
      });
    });
  }

  return { markdown: markdown, render: render, bind: bind };
})();
