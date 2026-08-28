# store-scout.com 붙이기

스스닷컴은 콘텐츠하다와 **별도 사업**이다. 지금은 두 사이트가 한 저장소의 GitHub Pages
하나로 나가고 있고, 주소는 이렇다:

    회사 현관     https://jasonsjo.github.io/jasons-company/
    콘텐츠하다     https://jasonsjo.github.io/jasons-company/content-agency/
    스스닷컴       https://jasonsjo.github.io/jasons-company/cafe-trade-area/

## 왜 아직 CNAME 을 두지 않았나

**한 저장소의 Pages 는 커스텀 도메인을 하나만 갖는다.** 지금 이 저장소에 CNAME 을 두면
회사 사이트가 통째로 그 도메인으로 옮겨간다 — 콘텐츠하다까지 store-scout.com 아래로
들어간다. 그건 분리가 아니라 반대다. 그래서 파일을 미리 만들지 않고, 배포 워크플로우는
이 문서가 있는지만 확인한다.

## 도메인을 살 때 할 일

세 갈래가 있다. 지금 시점에서는 ①이 가장 작다.

### ① 스스닷컴 공개 페이지를 새 공개 저장소로 옮긴다 (권장)

    store-scout-web (공개)
      /              스스닷컴 소개  ← cafe-trade-area/index.html
      /input/        후보지 데이터 입력
      /consult/      고객 상담
      CNAME          store-scout.com

옮길 것: `cafe-trade-area/{index.html,input,consult,shared}`
남길 것: `cafe-trade-area/{analysis,app,docs}` — 파이프라인 소스와 사내 콘솔은
        공개 사이트가 아니다. 지금 저장소에 그대로 둔다.

옮긴 뒤 이 저장소에서 할 일:
  - `deploy-pages.yml` 의 `cafe-trade-area` 복사 단계를 지운다
  - 회사 홈(`index.html`)의 스스닷컴 카드 `href` 를 `https://store-scout.com` 으로 바꾼다
  - 상담 페이지 외부 전송 금지 가드를 새 저장소 워크플로우로 함께 옮긴다 ← **빠뜨리지 말 것**

### ② SaaS(store-scout)에 도메인을 붙이고 공개 페이지는 그 앞에 둔다

`store-scout` 은 비공개 저장소라 Pages 를 쓸 수 없다. 대신 앱을 띄운 곳
(fly.io 등)에 `store-scout.com` 을 붙이고, 소개·입력·상담을 그 앱의 정적 경로로
서비스한다. 앱과 공개 페이지가 한 도메인에 있게 되므로 상담 페이지의
'서버로 안 보낸다' 는 약속을 **배포 가드로 다시 세워야 한다** — 지금 그 가드는
GitHub Pages 워크플로우에만 있다.

### ③ 이 저장소를 스스닷컴 전용으로 바꾼다

회사 현관과 콘텐츠하다를 다른 곳으로 옮기고 여기에 CNAME 을 둔다. 지금 구조와
반대 방향이라 권하지 않는다.

## 어느 쪽이든 확인할 것

- [ ] 상담 페이지에 외부 전송 코드가 없는가 (`fetch|XMLHttpRequest|sendBeacon|WebSocket`)
- [ ] 심의 콘솔(`cafe-trade-area/app/`)이 배포 산출물에 섞이지 않았는가 — 사내 한정이다
- [ ] 카카오 지도 JS 키의 도메인 등록에 새 도메인을 추가했는가
      (등록 안 하면 지도가 '검색 결과 없음' 처럼 보인다 — 실제로 겪었다)
