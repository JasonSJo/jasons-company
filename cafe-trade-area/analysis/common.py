#!/usr/bin/env python3
"""
카페 프랜차이즈 상권 분석 — 공통 모델

점수화·매출추정·손익 계산의 '단일 진실 원천'. CLI 스크립트(score_sites.py,
estimate_revenue.py, build_report.py)와 웹앱(app/js/model.js)이 **같은 상수와
같은 공식**을 쓴다. 여기 값을 바꾸면 CLI 결과가 바뀌므로, 웹앱 model.js 의
동일 상수도 함께 바꿔야 한다 (tests/test_parity.py 가 어긋남을 잡아준다).

금액 단위는 한국 관행대로 **만원**, 객단가만 **원**을 쓴다.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

# ── 점수 배점(합 100) ──────────────────────────────────────────────
WEIGHTS = {"배후수요": 30, "유동인구": 25, "경쟁": 20, "접근성": 15, "비용": 10}

# 정규화 기준값 — 이 값에 도달하면 만점
DEMAND_FULL = 30000.0   # 가중 배후수요 지수 만점 기준
TRAFFIC_FULL = 40000.0  # 일평균 유동인구(+역세권 보정) 만점 기준

# 동일 포지션(저가·테이크아웃 중심) 경쟁 브랜드 — 직접 잠식
RIVAL_BRANDS = ["메가", "컴포즈", "빽다방", "더벤티", "감성커피", "매머드", "폴바셋"]
# 집객 효과가 있는 앵커 브랜드 — 과밀이 아니면 오히려 가점
ANCHOR_BRANDS = ["스타벅스", "투썸", "커피빈", "블루보틀"]

GRADES = [(80, "A", "즉시 출점 검토"), (65, "B", "조건부 추천"), (50, "C", "보류·재협상")]

EARTH_R = 6371000.0  # m

# 브랜드 설정 기본값 — brand.yaml 이 일부만 채워도 여기 값으로 메운다.
# app/js/model.js 의 DEFAULTS 와 **같은 값**이어야 한다(tests/test_parity.py 가 대조).
DEFAULTS = {
    "객단가_원": 5200, "영업일수": 30, "영업시간": 13, "좌석수_기본": 24,
    "테이크아웃_비중": 0.45, "반경_m": 500,
    "변동비": {"재료비율": 0.35, "카드수수료율": 0.022, "로열티율": 0.03, "광고분담금율": 0.01},
    "고정비": {"최소인건비_월_만원": 620, "인건비율": 0.20, "수도광열_월_만원": 85,
             "소모품_월_만원": 45, "기타_월_만원": 40},
    "초기투자": {"인테리어_평당_만원": 250, "장비_만원": 4500, "가맹비_만원": 1000, "교육비_만원": 300},
}


def with_defaults(brand: dict | None) -> dict:
    """브랜드 설정에 기본값을 채워 넣는다(중첩 딕셔너리도 항목 단위로 병합)."""
    b = {**DEFAULTS, **(brand or {})}
    for k in ("변동비", "고정비", "초기투자"):
        b[k] = {**DEFAULTS[k], **((brand or {}).get(k) or {})}
    return b


# ── 유틸 ─────────────────────────────────────────────────────────
def r2(v: float, n: int = 1) -> float:
    """반올림 — 0.5 는 항상 절대값이 커지는 쪽으로 올린다.

    파이썬 기본 ri() 는 은행가 반올림이라 0.45 를 0.4 로 내리는데, JS Math.round
    는 0.5 로 올린다. 그대로 두면 콘솔과 CLI 의 점수가 0.1 씩 어긋난다.
    app/js/model.js 의 r2 와 부동소수점 연산 순서까지 동일하게 맞춘 구현이다.
    """
    p = 10 ** n
    x = v * p
    r = math.floor(abs(x) + 0.5 + 1e-9)
    return (-r if x < 0 else r) / p


def ri(v: float) -> int:
    """정수 반올림(표시용). r2 와 같은 규칙."""
    return int(r2(v, 0))


def n1(v) -> str:
    """소수 한 자리 수치를 JS Number 표기와 같게 만든다 — 30.0→'30', 19.6→'19.6'.

    리포트 본문에서 파이썬은 '30.0', 자바스크립트는 '30' 을 찍어 같은 리포트가
    글자 단위로 갈리는 것을 막는다(tests/test_parity.py 가 대조).
    """
    if v is None:
        return "—"
    return (f"{v:.1f}".rstrip("0").rstrip(".")) or "0"


def nf(v, d: int = 0) -> str:
    """천단위 콤마 + 소수 d 자리. 반올림은 r2 규칙(=JS 와 동일)을 먼저 적용한다.

    파이썬의 f-string 포맷은 은행가 반올림이라 2,452.5 를 '2,452' 로 찍는데
    JS toLocaleString 은 '2,453' 을 찍는다. 먼저 r2 로 굳혀 그 차이를 없앤다.
    """
    return f"{r2(v, d):,.{d}f}"


def to_f(v, default=0.0) -> float:
    """'1,234' · '12평' · None 처럼 지저분한 CSV 값도 숫자로 읽는다."""
    if v is None:
        return default
    s = re.sub(r"[^0-9.\-]", "", str(v))
    if s in ("", "-", ".", "-."):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def to_i(v, default=0) -> int:
    return int(to_f(v, default))


def is_yes(v) -> bool:
    return str(v).strip().upper() in ("Y", "YES", "예", "O", "TRUE", "1", "있음")


def haversine(lat1, lon1, lat2, lon2) -> float:
    """두 좌표 사이 거리(m). POI 반경 필터링에 쓴다."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(a)))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path: Path, obj) -> Path:
    return write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def grade(total: float) -> tuple[str, str]:
    for cut, g, label in GRADES:
        if total >= cut:
            return g, label
    return "D", "부적합"


# ── 반경 내 경쟁 집계 ──────────────────────────────────────────────
def competition(site: dict, pois: list[dict], radius_m: float) -> dict:
    """후보지 반경 안의 카페·자사점·앵커 집계.

    POI(수집)와 CSV(현장조사) 둘 다 보고 카페 수는 큰 쪽을 채택한다.
    브랜드 구성(동일포지션·앵커)과 자사점 거리는 좌표가 있어야 나온다.
    """
    lat, lon = to_f(site.get("위도")), to_f(site.get("경도"))
    cafes, rivals, anchors, own, nearest_own = 0, 0, 0, 0, None

    if lat and lon and pois:
        for p in pois:
            plat, plon = to_f(p.get("위도")), to_f(p.get("경도"))
            if not plat or not plon:
                continue
            d = haversine(lat, lon, plat, plon)
            if d > radius_m:
                continue
            kind = str(p.get("분류", "")).strip()
            brand = str(p.get("브랜드", "") or p.get("상호", ""))
            if kind == "자사점":
                own += 1
                nearest_own = d if nearest_own is None else min(nearest_own, d)
            elif kind == "카페":
                cafes += 1
                if any(b in brand for b in RIVAL_BRANDS):
                    rivals += 1
                elif any(b in brand for b in ANCHOR_BRANDS):
                    anchors += 1
    # 현장 조사값(CSV)과 수집값(POI) 중 **큰 쪽**을 쓴다.
    # POI 수집은 누락되기 쉬운데, 경쟁을 과소평가하면 매출이 부풀려지기 때문이다.
    cafes = max(cafes, to_i(site.get("카페수_500m")))
    rivals = max(rivals, to_i(site.get("동일포지션_경쟁수")))

    # 자사점은 카니발라이제이션 판단용 — 반경 밖이라도 가장 가까운 거리는 본다
    if lat and lon and pois and nearest_own is None:
        for p in pois:
            if str(p.get("분류", "")).strip() != "자사점":
                continue
            plat, plon = to_f(p.get("위도")), to_f(p.get("경도"))
            if plat and plon:
                d = haversine(lat, lon, plat, plon)
                nearest_own = d if nearest_own is None else min(nearest_own, d)

    return {
        "카페수": cafes, "동일포지션": rivals, "앵커브랜드": anchors,
        "자사점수": own, "자사점_최근접_m": None if nearest_own is None else ri(nearest_own),
    }


# ── 항목별 점수 ───────────────────────────────────────────────────
def score_demand(site: dict) -> tuple[float, str]:
    """배후수요: 주거보다 직장·학원 인구의 카페 소비 빈도가 높아 가중치를 더 준다."""
    idx = (to_f(site.get("주거인구_500m")) * 0.5
           + to_f(site.get("직장인구_500m")) * 1.0
           + to_f(site.get("아파트세대수")) * 0.8
           + to_f(site.get("대학_학원수")) * 300
           + to_f(site.get("오피스빌딩수")) * 150)
    pts = min(WEIGHTS["배후수요"], WEIGHTS["배후수요"] * idx / DEMAND_FULL)
    return r2(pts, 1), f"배후수요지수 {ri(idx):,}"


def score_traffic(site: dict) -> tuple[float, str]:
    """유동인구: 역 승하차는 그 자체가 유동이 아니라 유입원이라 0.3 만 반영."""
    eff = to_f(site.get("유동인구_일평균")) + to_f(site.get("지하철_일평균승하차")) * 0.3
    pts = min(WEIGHTS["유동인구"], WEIGHTS["유동인구"] * eff / TRAFFIC_FULL)
    return r2(pts, 1), f"유효유동 {ri(eff):,}명/일"


def people_per_cafe(site: dict, comp: dict) -> float:
    """카페 1개당 배후인구 — 상권 포화도의 핵심 지표."""
    pop = to_f(site.get("주거인구_500m")) + to_f(site.get("직장인구_500m"))
    return pop / max(1, comp["카페수"])


def score_competition(site: dict, comp: dict) -> tuple[float, str]:
    ppc = people_per_cafe(site, comp)
    for cut, pts in ((2000, 20), (1500, 16), (1000, 12), (700, 8), (400, 4)):
        if ppc >= cut:
            base = pts
            break
    else:
        base = 1.0
    base -= min(6.0, comp["동일포지션"] * 1.5)   # 같은 포지션은 직접 잠식
    base += min(2.0, comp["앵커브랜드"] * 1.0)   # 앵커는 집객 — 소폭 가점
    near = comp.get("자사점_최근접_m")
    note = f"카페1개당 배후인구 {ri(ppc):,}명 · 동일포지션 {comp['동일포지션']}곳"
    if near is not None and near < 500:
        base -= 5
        note += f" · ⚠ 자사점 {near}m (자기잠식)"
    return r2(max(0.0, min(float(WEIGHTS["경쟁"]), base)), 1), note


def score_access(site: dict) -> tuple[float, str]:
    pts, why = 0.0, []
    w = to_f(site.get("지하철_도보분"), 99)
    for cut, p in ((3, 6), (5, 5), (7, 4), (10, 2.5), (15, 1)):
        if w <= cut:
            pts += p
            why.append(f"역 도보 {ri(w)}분")
            break
    if is_yes(site.get("코너여부")):
        pts += 3; why.append("코너")
    if to_i(site.get("층"), 1) == 1:
        pts += 3; why.append("1층")
    front = to_f(site.get("전면길이_m"))
    if front >= 8:
        pts += 2; why.append(f"전면 {ri(front)}m")
    elif front >= 5:
        pts += 1
    if to_i(site.get("주차가능대수")) >= 3:
        pts += 1; why.append("주차")
    return r2(min(float(WEIGHTS["접근성"]), pts), 1), " · ".join(why) or "접근성 열위"


def rent_per_pyeong(site: dict) -> float:
    area = to_f(site.get("전용면적_평"))
    return to_f(site.get("월임대료_만원")) / area if area else 0.0


def score_cost(site: dict) -> tuple[float, str]:
    rpp = rent_per_pyeong(site)
    if rpp <= 0:
        return 0.0, "임대료 정보 없음"
    for cut, pts in ((10, 10), (15, 8), (20, 6), (25, 4), (35, 2)):
        if rpp <= cut:
            return float(pts), f"평당 임대료 {nf(rpp, 1)}만원"
    return 0.0, f"평당 임대료 {nf(rpp, 1)}만원 (과다)"


def score_site(site: dict, pois: list[dict], radius_m: float = 500) -> dict:
    comp = competition(site, pois, radius_m)
    parts = {}
    parts["배후수요"], n1 = score_demand(site)
    parts["유동인구"], n2 = score_traffic(site)
    parts["경쟁"], n3 = score_competition(site, comp)
    parts["접근성"], n4 = score_access(site)
    parts["비용"], n5 = score_cost(site)
    total = r2(sum(parts.values()), 1)
    g, label = grade(total)
    return {
        "후보지명": site.get("후보지명", "").strip(),
        "주소": site.get("주소", "").strip(),
        "총점": total, "등급": g, "등급설명": label,
        "항목": parts, "경쟁": comp,
        "근거": [n1, n2, n3, n4, n5],
    }


# ── 매출 추정 ─────────────────────────────────────────────────────
# 「유동인구 × 유입률」 한 방으로 추정하면 유동에 이미 포함된 직장·주거 인구를
# 이중 계상해 매출이 부풀려진다. 그래서 두 단계로 나눈다.
#   1) 상권 전체의 하루 카페 이용객 수(시장 수요)를 구하고
#   2) 그 시장을 반경 내 카페들이 나눠 갖는다고 보고 자사 점유율을 곱한다.
# 점유율은 균등분할(1/카페수)에서 출발해 입지 품질로 배수를 준다.
MARKET_TRAFFIC_RATE = 0.045   # 유동인구 중 하루에 카페를 이용하는 비율
MARKET_RESIDENT_RATE = 0.05   # 배후 주거인구의 하루 카페 이용률
MARKET_WORKER_RATE = 0.12     # 배후 직장인구의 하루 카페 이용률(주거의 2.4배)
LOC_MULT_MIN = 0.70           # 입지 배수 하한(접근성 0점일 때)
LOC_MULT_SPAN = 1.10          # 입지 배수 폭 → 최고 입지는 균등분할의 1.8배
SHARE_CAP = 0.25              # 경쟁이 거의 없어도 한 매장이 상권을 다 먹지는 않는다
TURN_HOURS = 1.5              # 좌석 1회전 소요시간
SEAT_UTIL = 0.55              # 평균 좌석 가동률
TAKEOUT_RATIO = 0.45          # 테이크아웃 비중 — 이 몫은 좌석 제약을 받지 않는다


def market_demand(site: dict) -> float:
    """상권(반경 내) 전체의 하루 카페 이용객 수."""
    return (to_f(site.get("유동인구_일평균")) * MARKET_TRAFFIC_RATE
            + to_f(site.get("주거인구_500m")) * MARKET_RESIDENT_RATE
            + to_f(site.get("직장인구_500m")) * MARKET_WORKER_RATE)


def location_multiplier(scored: dict) -> float:
    """같은 상권이라도 코너·1층·역세권이면 균등분할보다 더 가져간다."""
    acc = scored["항목"]["접근성"] / WEIGHTS["접근성"]      # 0~1
    return LOC_MULT_MIN + LOC_MULT_SPAN * acc


def market_share(scored: dict) -> float:
    """자사 점유율 = 균등분할 × 입지 배수 (상한 SHARE_CAP)."""
    cafes = max(1, scored["경쟁"]["카페수"] + 1)   # 자사 매장 자신을 포함해 나눈다
    return min(SHARE_CAP, location_multiplier(scored) / cafes)


def estimate_revenue(site: dict, scored: dict, brand: dict) -> dict:
    """시장수요 × 점유율 = 일객수. 좌석 처리능력으로 매장 이용객에 상한을 씌운다."""
    b = with_defaults(brand)
    ticket = to_f(b.get("객단가_원"), 5000)
    days = to_f(b.get("영업일수"), 30)
    hours = to_f(b.get("영업시간"), 13)
    seats = to_i(site.get("좌석수")) or to_i(b.get("좌석수_기본"), 24)

    demand = market_demand(site)
    share = market_share(scored)
    raw = demand * share

    # 좌석 상한은 '매장 이용객'에만 걸린다. 테이크아웃은 좌석과 무관하게 처리된다.
    takeout = to_f(b.get("테이크아웃_비중"), TAKEOUT_RATIO)
    seat_cap = seats * (hours / TURN_HOURS) * SEAT_UTIL   # 매장 이용객 물리적 상한
    dine_in = min(raw * (1 - takeout), seat_cap)
    capped = dine_in + raw * takeout

    monthly = capped * ticket * days / 10000.0            # 만원
    return {
        "상권수요_일객수": r2(demand, 1),
        "점유율": r2(share, 4),
        "입지배수": r2(location_multiplier(scored), 3),
        "경쟁카페수": scored["경쟁"]["카페수"],
        "일객수_이론": r2(raw, 1),
        "일객수_추정": r2(capped, 1),
        "좌석상한_일객수": r2(seat_cap, 1),
        "테이크아웃_비중": r2(takeout, 3),
        "좌석제약": raw * (1 - takeout) > seat_cap,
        "객단가_원": ri(ticket),
        "일매출_만원": r2(capped * ticket / 10000.0, 1),
        "월매출_만원": r2(monthly, 1),
    }


# ── 손익 · 투자회수 ────────────────────────────────────────────────
def variable_rate(brand: dict) -> float:
    v = with_defaults(brand)["변동비"]
    return (to_f(v.get("재료비율"), 0.35) + to_f(v.get("카드수수료율"), 0.022)
            + to_f(v.get("로열티율"), 0.03) + to_f(v.get("광고분담금율"), 0.01))


def estimate_pnl(site: dict, rev: dict, brand: dict) -> dict:
    """월 손익 + BEP + 투자회수기간.

    인건비는 고정비가 아니다 — 매출이 오르면 사람을 더 써야 한다. 그래서
    max(최소 인건비, 매출×인건비율) 로 잡고, BEP 도 이 구간을 나눠서 푼다.
    보증금은 폐점 시 회수되는 돈이라 투자회수기간 계산에서 뺀다.
    """
    b = with_defaults(brand)
    f, i = b["고정비"], b["초기투자"]
    sales = rev["월매출_만원"]
    vr = variable_rate(b)

    rent = to_f(site.get("월임대료_만원"))
    mgmt = to_f(site.get("관리비_만원"))
    other_fixed = (rent + mgmt
                   + to_f(f.get("수도광열_월_만원"), 85)
                   + to_f(f.get("소모품_월_만원"), 45)
                   + to_f(f.get("기타_월_만원"), 40))
    base_labor = to_f(f.get("최소인건비_월_만원"), 620)
    labor_rate = to_f(f.get("인건비율"), 0.20)
    labor = max(base_labor, sales * labor_rate)
    fixed = other_fixed + labor

    contribution = sales * (1 - vr)
    profit = contribution - fixed

    # BEP: 최소인건비 구간과 인건비율 구간 중 실제로 성립하는 해를 고른다
    bep = float("inf")
    if vr < 1:
        low = (base_labor + other_fixed) / (1 - vr)
        if labor_rate <= 0 or low * labor_rate <= base_labor:
            bep = low
        elif (1 - vr - labor_rate) > 0:
            bep = other_fixed / (1 - vr - labor_rate)

    area = to_f(site.get("전용면적_평"))
    deposit = to_f(site.get("보증금_만원"))
    interior = to_f(site.get("인테리어_만원")) or area * to_f(i.get("인테리어_평당_만원"), 250)
    sunk = (interior + to_f(site.get("권리금_만원")) + to_f(i.get("장비_만원"), 4500)
            + to_f(i.get("가맹비_만원"), 1000) + to_f(i.get("교육비_만원"), 300))
    invest = deposit + sunk

    payback = r2(sunk / profit, 1) if profit > 0 else None
    return {
        "월매출_만원": r2(sales, 1),
        "변동비율": r2(vr, 4),
        "변동비_만원": r2(sales * vr, 1),
        "공헌이익_만원": r2(contribution, 1),
        "인건비_만원": r2(labor, 1),
        "임대료_만원": r2(rent + mgmt, 1),
        "고정비_만원": r2(fixed, 1),
        "영업이익_만원": r2(profit, 1),
        "영업이익률": r2(profit / sales, 4) if sales else 0.0,
        "BEP월매출_만원": r2(bep, 1) if bep != float("inf") else None,
        "BEP달성률": r2(sales / bep, 3) if bep and bep != float("inf") else 0.0,
        "초기투자_만원": r2(invest, 1),
        "회수대상투자_만원": r2(sunk, 1),
        "보증금_만원": r2(deposit, 1),
        "투자회수_개월": payback,
    }


def analyze(site: dict, pois: list[dict], brand: dict) -> dict:
    """후보지 1곳 전체 분석: 점수 → 매출 → 손익 → 리스크."""
    b = with_defaults(brand)
    scored = score_site(site, pois, to_f(b.get("반경_m"), 500))
    rev = estimate_revenue(site, scored, b)
    pnl = estimate_pnl(site, rev, b)
    return {**scored, "매출추정": rev, "손익": pnl, "리스크": risks(site, scored, rev, pnl)}


def risks(site: dict, scored: dict, rev: dict, pnl: dict) -> list[str]:
    """점수가 좋아도 손익이 안 나오는 자리를 걸러내는 경고들."""
    out = []
    if pnl["BEP월매출_만원"] is None:
        out.append("⛔ 구조적 적자 — 변동비+인건비율이 100% 이상이라 어떤 매출에서도 흑자 불가")
    elif pnl["BEP달성률"] < 1.0:
        out.append(f"⛔ BEP 미달 — 추정 월매출이 손익분기({nf(pnl['BEP월매출_만원'])}만원)의 "
                   f"{ri(pnl['BEP달성률'] * 100)}% 수준")
    elif pnl["BEP달성률"] < 1.15:
        out.append("⚠ BEP 여유 15% 미만 — 매출 변동에 취약")
    if pnl["투자회수_개월"] is None:
        out.append("⛔ 영업이익 적자 — 투자회수 불가")
    elif pnl["투자회수_개월"] > 36:
        out.append(f"⚠ 투자회수 {ri(pnl['투자회수_개월'])}개월 (36개월 초과)")
    near = scored["경쟁"].get("자사점_최근접_m")
    if near is not None and near < 500:
        out.append(f"⚠ 자사 기존점 {near}m — 자기잠식 검토 필요")
    if scored["경쟁"]["동일포지션"] >= 3:
        out.append(f"⚠ 동일포지션 경쟁 {scored['경쟁']['동일포지션']}곳 — 가격경쟁 심화 구간")
    if rev["좌석제약"]:
        out.append("ℹ 좌석 처리능력이 상한 — 매장 확장/테이크아웃 동선 검토 시 상향 여지")
    if scored["항목"]["비용"] <= 2:
        out.append("⚠ 평당 임대료 과다 — 임대조건 재협상 전제")
    return out
