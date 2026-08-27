# jasons-company

소상공인·프랜차이즈 대상 사업 자산 저장소. 사업 라인마다 실행 가능한 시스템과 웹앱이 함께 들어 있다.
사이트 현관은 저장소 루트의 **[index.html](index.html)** (회사 메인 안내)이다.

## 사업 라인

### 1. 업종 전문 콘텐츠 대행 — [content-agency/](content-agency/)
랜딩페이지 · 콘텐츠 생산 자동화 · 영업 자산 · 운영 문서.
운영 콘솔 웹앱은 **[content-agency/app/](content-agency/app/)** (타깃·캘린더·검수·리포트, 설치 불필요).
시작은 **[content-agency/QUICKSTART.md](content-agency/QUICKSTART.md)** 부터.

### 2. 커피 프랜차이즈 상권분석 — [cafe-trade-area/](cafe-trade-area/)
「점포개발 심의 알고리즘 v1.0」 구현. 등시선으로 상권을 획정하고(M1), 격자 인구를
면적 가중 교차하고(M2), Huff 로 경쟁을 배분하고(M3), 매출을 예측구간으로 추정하고(M4),
부결 트리거로 판정하고(M5), 실적으로 계수를 교정합니다(M6).
파이프라인(**[analysis/](cafe-trade-area/analysis/)**), 후보지 데이터 입력 웹앱
(**[input/](cafe-trade-area/input/)** — 실사 결과 → 후보지 CSV, 공개), 사내 심의 콘솔
(**[app/](cafe-trade-area/app/)**). 시작은
**[cafe-trade-area/QUICKSTART.md](cafe-trade-area/QUICKSTART.md)** 부터.

> **사내 한정 · 대외 배포 금지.** 산출물은 내부 의사결정 자료이며, 가맹희망자 제공용
> 예상매출액 산정서와 수치를 혼용해서는 안 됩니다. 입력 페이지(`input/`)는 입력만
> 다루므로 공개하지만, 판정·매출 추정을 보여주는 심의 콘솔(`app/`)은 배포하지 않습니다.

## 배포
`.github/workflows/deploy-pages.yml` 가 저장소 루트 `index.html` 을 사이트 현관으로,
두 사업을 각자 경로 아래로 GitHub Pages 에 배포한다.
**심의 콘솔(`cafe-trade-area/app/`)은 사내 한정 자료라 배포하지 않는다** — 그 경로에는
안내 페이지(`.github/pages/심의콘솔-안내.html`)만 올라가고, 콘솔은 저장소를 받아 로컬로 연다.
활성화: **Settings → Pages → Source: GitHub Actions** (한 번), 이후 `main` push 시 자동 배포.

| 주소 | 내용 |
|---|---|
| `https://jasonsjo.github.io/jasons-company/` | **회사 메인 안내** |
| `.../content-agency/` | 콘텐츠 대행 랜딩페이지 |
| `.../content-agency/app/` | 콘텐츠 대행 운영 콘솔 |
| `.../cafe-trade-area/` | 상권분석 알고리즘 소개 |
| `.../cafe-trade-area/input/` | **상권분석 데이터 입력** — 후보지 실사 결과 → 후보지 CSV |
| `.../cafe-trade-area/app/` | 안내 페이지 — 심의 콘솔은 배포하지 않음(사내 한정) |

> 루트가 회사 메인으로 바뀌었습니다. 콘텐츠 대행 랜딩페이지는 `/content-agency/` 입니다 —
> 기존 주소로 들어와도 404 가 아니라 메인에서 한 번 더 눌러 들어갑니다.

## 테스트
```
cd cafe-trade-area/analysis && python3 -m unittest discover -s tests -t .
```

## 연락처
- 카카오톡 오픈채팅: https://open.kakao.com/o/sZ71xB5d
- 이메일: ceo-jason@jasons-consulting.com
