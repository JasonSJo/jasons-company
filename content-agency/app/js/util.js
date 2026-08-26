/* 공통 유틸 — 전역 네임스페이스 U.
   file:// 로 열어도 동작하도록 ES 모듈 대신 클래식 스크립트를 사용한다. */
var U = (function () {
  "use strict";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m];
    });
  }

  function toast(msg) {
    var t = $("#toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.add("on");
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.remove("on"); }, 2400);
  }

  /* ── 숫자 ─────────────────────────── */
  function toInt(v, dflt) {
    var n = parseInt(String(v == null ? "" : v).replace(/,/g, "").trim(), 10);
    return isNaN(n) ? (dflt === undefined ? 0 : dflt) : n;
  }
  function toNum(v) {
    var n = parseFloat(String(v == null ? "" : v).replace(/,/g, "").trim());
    return isNaN(n) ? 0 : n;
  }
  function comma(n) { return Number(n || 0).toLocaleString("ko-KR"); }

  /* ── 날짜 ─────────────────────────── */
  function iso(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function today() { return iso(new Date()); }
  function parseISO(s) {
    var p = String(s || "").split("-");
    return new Date(toInt(p[0], 1970), toInt(p[1], 1) - 1, toInt(p[2], 1));
  }
  function addDays(d, n) { var c = new Date(d.getTime()); c.setDate(c.getDate() + n); return c; }
  function monthKey(s) { return String(s || "").slice(0, 7); }

  /* ── CSV ─────────────────────────── */
  // 따옴표·줄바꿈을 포함한 필드를 처리하는 최소 파서.
  function parseCSV(text) {
    var rows = [], row = [], field = "", inQuotes = false;
    text = String(text).replace(/^﻿/, "").replace(/\r\n?/g, "\n");
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (inQuotes) {
        if (c === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; }
          else inQuotes = false;
        } else field += c;
      } else if (c === '"') inQuotes = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
      else field += c;
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (c) { return String(c).trim() !== ""; }); });
  }

  // 첫 행을 헤더로 보고 객체 배열을 만든다.
  function csvToObjects(text) {
    var rows = parseCSV(text);
    if (!rows.length) return [];
    var head = rows[0].map(function (h) { return String(h).trim(); });
    return rows.slice(1).map(function (r) {
      var o = {};
      head.forEach(function (h, i) { o[h] = (r[i] == null ? "" : String(r[i]).trim()); });
      return o;
    });
  }

  function csvCell(v) {
    var s = String(v == null ? "" : v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function objectsToCSV(rows, columns) {
    var lines = [columns.map(csvCell).join(",")];
    rows.forEach(function (r) {
      lines.push(columns.map(function (c) { return csvCell(r[c]); }).join(","));
    });
    return lines.join("\n") + "\n";
  }

  /* ── 파일 입출력 ─────────────────────────── */
  // CSV 만 BOM 을 붙인다(엑셀 한글 깨짐 방지).
  // JSON·YAML 에 BOM 이 들어가면 파이썬 파이프라인이 파싱에 실패한다.
  function download(filename, text, mime) {
    var needsBOM = /csv/.test(mime || "") || /\.csv$/i.test(filename);
    var blob = new Blob([(needsBOM ? "\ufeff" : "") + text], { type: (mime || "text/plain") + ";charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }

  // 숨겨진 input[type=file] 하나를 재사용해 파일을 읽는다.
  function pickFile(accept, onText) {
    var inp = $("#filepick");
    inp.value = "";
    inp.accept = accept || "";
    inp.onchange = function () {
      var f = inp.files && inp.files[0];
      if (!f) return;
      var fr = new FileReader();
      fr.onload = function () { onText(String(fr.result), f.name); };
      fr.onerror = function () { toast("파일을 읽지 못했습니다."); };
      fr.readAsText(f, "utf-8");
    };
    inp.click();
  }

  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text)
        .then(function () { toast("클립보드에 복사했습니다."); })
        .catch(function () { toast("복사 실패 — 직접 선택해 복사하세요."); });
    }
    toast("이 브라우저에서는 복사를 지원하지 않습니다.");
    return Promise.resolve();
  }

  function uid() {
    return "id" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  /* ── YAML(내보내기 전용 최소 직렬화) ─────────────────────────── */
  function yamlScalar(v) {
    if (v == null) return '""';
    var s = String(v);
    if (s === "") return '""';
    // 콜론·따옴표·선행 특수문자가 있으면 따옴표로 감싼다.
    if (/[:#\-\[\]{}&*!|>%@`,"']/.test(s) || /^\s|\s$/.test(s) || /^\d+$/.test(s)) {
      return '"' + s.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
    }
    return s;
  }
  // 평평한 객체의 배열만 다룬다(캘린더 항목 형태).
  function toYamlList(items, keys) {
    return items.map(function (it) {
      return keys.map(function (k, i) {
        return (i === 0 ? "- " : "  ") + k + ": " + yamlScalar(it[k]);
      }).join("\n");
    }).join("\n") + "\n";
  }

  return {
    $: $, $$: $$, esc: esc, toast: toast,
    toInt: toInt, toNum: toNum, comma: comma,
    iso: iso, today: today, parseISO: parseISO, addDays: addDays, monthKey: monthKey,
    parseCSV: parseCSV, csvToObjects: csvToObjects, objectsToCSV: objectsToCSV,
    download: download, pickFile: pickFile, copy: copy, uid: uid, toYamlList: toYamlList
  };
})();
