/**
 * 리드 수집 백엔드 — Google Apps Script (무료)
 *
 * 리드-수집-폼.html 이 POST 하는 문의를 구글 시트에 한 줄씩 저장하고,
 * 담당자에게 이메일 알림을 보낸다. 서버·비용 없이 구글 계정만으로 동작.
 *
 * ── 배포 방법 ──
 * 1. https://sheets.google.com 에서 새 스프레드시트 생성 → 확장프로그램 → Apps Script
 * 2. 이 파일 내용을 붙여넣고 아래 NOTIFY_EMAIL 을 본인 이메일로 수정
 * 3. 배포 → 새 배포 → 유형: 웹 앱
 *      - 실행 사용자: 나
 *      - 액세스 권한: 모든 사용자
 * 4. 나온 웹앱 URL(.../exec)을 리드-수집-폼.html 의 LEAD_ENDPOINT 에 붙여넣기
 */

var NOTIFY_EMAIL = "ceo-jason@jasons-consulting.com";   // 문의 알림 받을 이메일
var SHEET_NAME = "leads";

function doPost(e) {
  try {
    var lead = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);

    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["접수시각", "상호", "업종", "담당자", "연락처", "채널", "필요사항"]);
    }
    sheet.appendRow([
      lead.ts || new Date().toISOString(),
      lead.biz || "", lead.industry || "", lead.name || "",
      lead.contact || "", lead.channel || "", lead.goal || ""
    ]);

    if (NOTIFY_EMAIL && NOTIFY_EMAIL.indexOf("example.com") === -1) {
      MailApp.sendEmail(
        NOTIFY_EMAIL,
        "[신규 리드] " + (lead.biz || "무명") + " · " + (lead.industry || ""),
        "담당자: " + (lead.name || "") + "\n연락처: " + (lead.contact || "") +
        "\n채널: " + (lead.channel || "") + "\n필요사항: " + (lead.goal || "")
      );
    }
    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doGet() {
  return json_({ ok: true, service: "content-agency lead backend" });
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
