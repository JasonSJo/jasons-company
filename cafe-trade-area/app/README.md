# 상권 분석 콘솔 (웹앱)

`analysis/` 의 파이썬 도구를 **브라우저 한 화면**으로 묶은 콘솔입니다.
빌드·서버·계정이 필요 없습니다. `app/index.html` 을 더블클릭하면 바로 동작합니다.

## 탭

| 탭 | 하는 일 | 대응하는 CLI |
|---|---|---|
| **대시보드** | 등급 분포·진행 단계·심의 통과 현황, QUICKSTART 순서대로 다음 액션 | — |
| **후보지** | CSV 가져오기 → 100점 채점·정렬, 항목별 점수와 리스크, 진행 단계 관리 | `score_sites.py` |
| **상권 지도** | 후보지를 원점에 둔 경쟁 분포도 (동일포지션·앵커·자사점 색 구분) | — |
| **손익 시뮬** | 객단가·임대료·좌석·원가율을 슬라이더로 움직여 손익·BEP·회수기간 즉시 확인 | `estimate_revenue.py` |
| **리포트** | 후보지별 제출용 상권조사 리포트(.md) 생성·내려받기 | `build_report.py` |
| **브랜드 설정** | 객단가·변동비·고정비·초기투자 파라미터, `brand.yaml` 로 내보내기 | `brand.yaml` |

## 지도에 API 키가 필요 없는 이유

외부 지도 타일을 쓰지 않습니다. 후보지를 원점(0,0)에 놓고 주변 POI 를 실제 거리(m)로
배치한 **로컬 평면도**를 SVG 로 직접 그립니다. 500m 규모에서는 평면 근사로 충분하고,
네트워크·키·요금이 전혀 없으며 `file://` 로 열어도 그대로 뜹니다.

## CLI 와 이어 쓰기

콘솔은 파이프라인을 대체하지 않고 **입출력을 주고받습니다.**

```
[콘솔] 후보지 입력/편집 → CSV 내보내기 (후보지.csv)
        ↓
python score_sites.py --sites 후보지.csv --pois output/pois.csv --brand brand.yaml
        ↓
python collect_pois.py --live …  →  output/pois.csv
        ↓
[콘솔] POI CSV 가져오기 → 경쟁 집계·지도에 즉시 반영

[콘솔] 브랜드 설정 → brand.yaml 내려받기 → analysis/ 에 두고 --brand brand.yaml
```

점수 가중치·매출 공식·손익 구조·반올림 규칙까지 `analysis/common.py` 와 **같은 값**을 씁니다.
`analysis/tests/test_parity.py` 가 두 구현을 같은 입력으로 돌려 모든 수치와 리포트 본문을
대조하므로, 콘솔에서 본 숫자와 CLI 리포트가 어긋나지 않습니다.

## 데이터 저장

- 모든 데이터는 **이 브라우저의 localStorage 에만** 저장됩니다. 서버 전송·계정 없음.
- 기기·브라우저가 바뀌면 따라가지 않습니다. **백업 내보내기 → 복원** 으로 옮기세요.
- 브라우저 데이터 삭제 시 함께 지워집니다. 잃으면 안 되는 건 주기적으로 백업하세요.
- 콘솔 자체는 공개 배포되지만(`noindex`), **거기 담긴 데이터는 각자의 브라우저에만** 있습니다.

## 처음이라면

우측 상단 **데모 데이터** 버튼을 누르면 `analysis/*.example.*` 와 같은 값이 채워집니다
(후보지 6곳 · POI 36건 · 브랜드 파라미터). 전체 흐름을 눌러본 뒤 **전체 초기화** 로 비우고
실제 데이터를 넣으세요.

## 파일

```
app/
├── index.html      # 화면 골격(탭 6개)
├── styles.css      # content-agency/app 과 같은 디자인 토큰
└── js/
    ├── util.js       # CSV 파싱·파일 입출력·포맷
    ├── model.js      # ★ analysis/common.py 의 1:1 포팅 (점수·매출·손익)
    ├── demo.js       # 예시 CSV/YAML 에서 구운 데모 데이터 (gen_demo.js 로 재생성)
    ├── gen_demo.js   #   ↑ 생성기: node app/js/gen_demo.js
    ├── store.js      # localStorage 상태 저장소
    ├── sites.js      # 후보지 목록·상세·편집
    ├── map.js        # 상권 지도(SVG)
    ├── sim.js        # 손익 시뮬레이터
    ├── report.js     # 상권조사 리포트 (build_report.py 와 같은 마크다운)
    └── app.js        # 탭·대시보드·브랜드 설정·백업
```

의존성 없는 순수 HTML/CSS/JS 입니다. 빌드 단계가 없어 `file://` 로 열어도 동작합니다.
