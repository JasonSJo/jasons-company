# jasons-company

소상공인·프랜차이즈 대상 사업 자산 저장소. 사업 라인마다 실행 가능한 시스템과 웹앱이 함께 들어 있다.

## 사업 라인

### 1. 업종 전문 콘텐츠 대행 — [content-agency/](content-agency/)
랜딩페이지 · 콘텐츠 생산 자동화 · 영업 자산 · 운영 문서.
운영 콘솔 웹앱은 **[content-agency/app/](content-agency/app/)** (타깃·캘린더·검수·리포트, 설치 불필요).
시작은 **[content-agency/QUICKSTART.md](content-agency/QUICKSTART.md)** 부터.

### 2. 카페 프랜차이즈 상권 조사·분석 — [cafe-trade-area/](cafe-trade-area/)
출점 후보지를 100점으로 채점하고 매출·손익·투자회수를 추정해 출점 여부를 심의하는 시스템.
파이썬 파이프라인(**[analysis/](cafe-trade-area/analysis/)**)과 상권 분석 콘솔 웹앱
(**[app/](cafe-trade-area/app/)**)이 **같은 모델**을 쓰며, 대조 테스트로 어긋남을 막습니다.
시작은 **[cafe-trade-area/QUICKSTART.md](cafe-trade-area/QUICKSTART.md)** 부터.

## 배포
`.github/workflows/deploy-pages.yml` 가 `content-agency/` 를 사이트 루트로,
`cafe-trade-area/app/` 를 `/cafe-trade-area/app/` 로 GitHub Pages 에 배포한다.
활성화: **Settings → Pages → Source: GitHub Actions** (한 번), 이후 `main` push 시 자동 배포.

| 주소 | 내용 |
|---|---|
| `https://jasonsjo.github.io/jasons-company/` | 콘텐츠 대행 랜딩페이지 |
| `.../app/` | 콘텐츠 대행 운영 콘솔 |
| `.../cafe-trade-area/` | 상권 분석 소개 페이지 |
| `.../cafe-trade-area/app/` | 상권 분석 콘솔 |

## 테스트
```
cd cafe-trade-area/analysis && python3 -m unittest discover -s tests -t .
```

## 연락처
- 카카오톡 오픈채팅: https://open.kakao.com/o/sZ71xB5d
- 이메일: ceo-jason@jasons-consulting.com
