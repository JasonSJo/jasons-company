# jasons-company

소상공인·프랜차이즈 대상 사업 자산 저장소. 사이트 현관은 저장소 루트의
**[index.html](index.html)** (회사 메인 안내)이다.

## 사업 라인

### 1. 업종 전문 콘텐츠 대행 — [content-agency/](content-agency/)
랜딩페이지 · 콘텐츠 생산 자동화 · 영업 자산 · 운영 문서.
운영 콘솔 웹앱은 **[content-agency/app/](content-agency/app/)** (타깃·캘린더·검수·리포트, 설치 불필요).
시작은 **[content-agency/QUICKSTART.md](content-agency/QUICKSTART.md)** 부터.

### 2. 점포개발 상권분석 — 스스닷컴 · [store-scout](https://github.com/JasonSJo/store-scout) ↗
**이 저장소에 없다.** 별도 사업이고 `store-scout.com` 으로 나가므로 자기 저장소를
가진다. 알고리즘(M1~M6)·SaaS·공개 페이지(소개·데이터 입력·고객 상담)가 모두 그쪽에
있다.

> 전에는 `cafe-trade-area/` 로 여기 있었다. 한 저장소의 GitHub Pages 는 커스텀
> 도메인을 하나만 갖는데, 여기에 `store-scout.com` 을 붙이면 콘텐츠하다까지 그
> 도메인 아래로 들어간다. 그래서 갈랐다.

## 배포
`.github/workflows/deploy-pages.yml` 가 저장소 루트 `index.html` 을 사이트 현관으로,
콘텐츠 대행을 그 아래 경로로 GitHub Pages 에 배포한다.
활성화: **Settings → Pages → Source: GitHub Actions** (한 번), 이후 `main` push 시 자동 배포.

| 주소 | 내용 |
|---|---|
| `https://jasonsjo.github.io/jasons-company/` | **회사 메인 안내** |
| `.../content-agency/` | 콘텐츠 대행 랜딩페이지 |
| `.../content-agency/app/` | 콘텐츠 대행 운영 콘솔 |

스스닷컴 주소는 store-scout 저장소의 Pages 로 나간다(그쪽 README 참고).

## 연락처
- 카카오톡 오픈채팅: https://open.kakao.com/o/sZ71xB5d
- 이메일: ceo-jason@jasons-consulting.com
