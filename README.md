# jasons-company

소상공인·프랜차이즈 대상 사업 자산 저장소. 사업 라인마다 실행 가능한 시스템과 웹앱이 함께 들어 있다.

## 사업 라인

### 1. 업종 전문 콘텐츠 대행 — [content-agency/](content-agency/)
랜딩페이지 · 콘텐츠 생산 자동화 · 영업 자산 · 운영 문서.
운영 콘솔 웹앱은 **[content-agency/app/](content-agency/app/)** (타깃·캘린더·검수·리포트, 설치 불필요).
시작은 **[content-agency/QUICKSTART.md](content-agency/QUICKSTART.md)** 부터.

### 2. 커피 프랜차이즈 상권분석 — [cafe-trade-area/](cafe-trade-area/)
「점포개발 심의 알고리즘 v1.0」 구현. 등시선으로 상권을 획정하고(M1), 격자 인구를
면적 가중 교차하고(M2), Huff 로 경쟁을 배분하고(M3), 매출을 예측구간으로 추정하고(M4),
부결 트리거로 판정하고(M5), 실적으로 계수를 교정합니다(M6).
파이프라인(**[analysis/](cafe-trade-area/analysis/)**)과 사내 심의 콘솔
(**[app/](cafe-trade-area/app/)**). 시작은
**[cafe-trade-area/QUICKSTART.md](cafe-trade-area/QUICKSTART.md)** 부터.

> **사내 한정 · 대외 배포 금지.** 산출물은 내부 의사결정 자료이며, 가맹희망자 제공용
> 예상매출액 산정서와 수치를 혼용해서는 안 됩니다.

## 배포
`.github/workflows/deploy-pages.yml` 가 `content-agency/` 를 사이트 루트로,
`cafe-trade-area/app/` 를 `/cafe-trade-area/app/` 로 GitHub Pages 에 배포한다.
활성화: **Settings → Pages → Source: GitHub Actions** (한 번), 이후 `main` push 시 자동 배포.

| 주소 | 내용 |
|---|---|
| `https://jasonsjo.github.io/jasons-company/` | 콘텐츠 대행 랜딩페이지 |
| `.../app/` | 콘텐츠 대행 운영 콘솔 |
| `.../cafe-trade-area/` | 상권분석 알고리즘 소개 |
| `.../cafe-trade-area/app/` | 심의 콘솔 (사내) |

## 테스트
```
cd cafe-trade-area/analysis && python3 -m unittest discover -s tests -t .
```

## 연락처
- 카카오톡 오픈채팅: https://open.kakao.com/o/sZ71xB5d
- 이메일: ceo-jason@jasons-consulting.com
