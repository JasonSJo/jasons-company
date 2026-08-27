# 운영 콘솔 (웹앱)

`automation/` 의 파이썬 도구들과 `ops/` 의 영업 흐름을 **브라우저 한 화면**으로 묶은 운영 콘솔입니다.
빌드 도구·서버·계정이 필요 없습니다. `app/index.html` 을 더블클릭하거나, 배포된
`https://jasonsjo.github.io/jasons-company/content-agency/app/` 로 접속하면 바로 동작합니다.

## 무엇을 하나

| 탭 | 하는 일 | 대응하는 기존 도구 |
|---|---|---|
| **대시보드** | 파이프라인·발행·검수 현황 집계, QUICKSTART 순서대로 "다음 액션" 제시 | — |
| **타깃·영업** | 타깃 CSV 가져오기 → 니즈 점수 자동 산출·정렬, 접촉 단계·메모 관리 | `automation/score_prospects.py` |
| **콘텐츠 캘린더** | 업체 프로필 → 발행 캘린더 자동 생성, 월간 그리드에서 발행 완료 체크 | `automation/build_calendar.py` |
| **검수** | `manifest.json` 불러와 승인·보류·반려, 규제 금지어 자동 검출 | `automation/review.html` + `compliance_check.py` |
| **월간 리포트** | 채널별 지표 입력 → 마크다운 리포트 생성 | `automation/report.py` |

점수 가중치·토픽 공식·주간 발행 리듬·규제 규칙은 모두 위 파이썬 스크립트와 **같은 값**을 씁니다.
콘솔에서 계산한 결과와 CLI 로 돌린 결과가 어긋나지 않습니다.

## 파이썬 파이프라인과 이어 쓰기

콘솔은 파이프라인을 대체하지 않고 **입출력을 주고받습니다.**

```
[콘솔] 캘린더 생성 → YAML 내보내기 (content_calendar.generated.yaml)
        ↓
python generate_content.py --calendar content_calendar.generated.yaml     # dry-run 무료 / --live 유료
        ↓  output/manifest.json
[콘솔] 검수 탭에서 불러오기 → 승인 → approved.json 내보내기
        ↓  automation/output/ 에 넣고
python publish.py                                                          # 채널별 발행 패키지
        ↓  게시(사람)
[콘솔] 월간 리포트 탭 → monthly_report.md 발송
```

타깃도 양방향입니다. `타겟리스트.example.csv` 형식을 그대로 가져오고,
`prospects.csv` 로 내보내면 `python score_prospects.py --csv prospects.csv` 에 바로 넣을 수 있습니다.

## 데이터 저장

- 모든 데이터는 **이 브라우저의 localStorage 에만** 저장됩니다. 서버로 전송되지 않고, 계정도 없습니다.
- 기기·브라우저가 바뀌면 데이터가 따라가지 않습니다. **백업 내보내기 → 복원**으로 옮기세요.
- 브라우저 데이터 삭제 시 함께 지워집니다. 계약 정보처럼 잃으면 안 되는 것은 주기적으로 백업하세요.
- 콘솔 자체는 GitHub Pages 로 공개 배포되지만(`noindex`), **거기에 담긴 데이터는 각자의 브라우저에만** 있습니다.

## 열기

```
# 1) 그냥 열기 — 대부분의 기능이 그대로 동작
open content-agency/app/index.html

# 2) 로컬 서버로 열기 — 검수 탭의 "output/ 에서 불러오기" 버튼까지 동작
cd content-agency && python3 -m http.server 8000
#  → http://localhost:8000/app/
```

파일을 직접 고르는 방식(`manifest.json 열기`)은 두 경우 모두 동작합니다.

## 파일

```
app/
├── index.html      # 화면 골격(탭 5개)
├── styles.css      # 랜딩페이지와 동일한 디자인 토큰
└── js/
    ├── util.js       # CSV/YAML·파일 입출력·날짜 유틸
    ├── store.js      # localStorage 상태 저장소 + 데모 데이터
    ├── prospects.js  # 니즈 점수화 (score_prospects.py 포팅)
    ├── calendar.js   # 캘린더 생성 (build_calendar.py 포팅)
    ├── review.js     # 검수 큐 + 규제 검출 (compliance_check.py 포팅)
    ├── report.js     # 월간 리포트 (report.py 포팅)
    └── app.js        # 탭 전환·대시보드 집계·백업/복원
```

의존성 없는 순수 HTML/CSS/JS 입니다. 빌드 단계가 없어 `file://` 로 열어도 동작합니다.

## 처음이라면

우측 상단 **데모 데이터** 버튼을 누르면 `automation/*.example.*` 와 같은 값이 채워집니다.
전체 흐름을 눌러본 뒤 **전체 초기화**로 비우고 실제 데이터를 넣으세요.
