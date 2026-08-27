#!/usr/bin/env python3
"""
M2 · 수요 변수 산출

100m 격자 인구를 등시선 폴리곤과 **면적 가중 교차**해 배후 수요를 뽑고,
유동인구는 출근 진행 방향과 후보지의 도로 좌·우 위치로 나눠 보정한다.

    H     = Σ(격자세대수   × 격자∩P10 면적비)
    W     = Σ(격자직장인구 × 격자∩P10 면적비)
    D_am  = Σ(07~10시 유동인구, P5 기준)
    D_all = Σ(전시간대 유동인구, P5 기준)
            영역 단위 대용 데이터는 P5 면적비로 안분한 뒤 더한다(아래 참조).

    D_am_adj = D_am_같은편 + (D_am_반대편 × 0.3)

횡단저항 0.3 은 **미검증 실무 판단값**이다(config.횡단저항). M6 가 교정한다.

입력 파일
  격자인구.csv  격자ID,중심위도,중심경도,한변_m,세대수,직장인구
  유동인구.csv  지점ID,위도,경도,도로변,시간대,인원,출처,단위면적_m2
                시간대 ∈ {오전, 전체}
                도로변은 후보지 CSV 의 `도로변` 과 같은 라벨 체계여야 한다(A/B 등).

실측이 아닌 대용 데이터
    명세가 요구하는 것은 **07~09시 현장 통행량 실측 카운트**다. 그러나 실측은 사람이
    현장에 서 있어야 나오는 값이라, 그 전에는 행정동 생활인구·상권 길단위인구 같은
    **영역 단위** 공공데이터로 대신할 수밖에 없다. 영역 값을 지점 값처럼 그대로 더하면
    D_am 이 수십 배로 부풀어 모든 후보지가 통과한다.

    그래서 영역 단위 행은 `단위면적_m2` 를 함께 싣고, P5 면적비로 **안분**한다.

        지점_인원 = 영역_인원 × (P5면적 ÷ 단위면적) × 유동_안분_집중계수

    이것은 균등분포 가정이다 — 실제 통행량은 간선도로변에 몰린다. 집중계수의 기본값은
    1.0(보정 없음)이고 미검증 계수다. 안분이 한 건이라도 일어나면 그 사실이 경고로 남고,
    실측으로 바뀌기 전까지 사라지지 않는다.

    `단위면적_m2` 가 비어 있으면 **점 실측**으로 보고 그대로 더한다. 영역 데이터인데
    면적을 모르면 안분할 수 없으므로 그 행은 **버린다** — 추측한 면적으로 나눈 값은
    근거가 아니다.
"""
from __future__ import annotations

import geo
from common import read_csv, to_f
from config import c

AM, ALL = "오전", "전체"


def _cells_in(poly, cells, lat0, lon0):
    """폴리곤과 겹치는 격자칸만 훑는다. bbox 로 1차 거른 뒤 부분표본으로 포함률을 잰다."""
    x0, y0, x1, y1 = geo.bbox(poly)
    for row in cells:
        clat, clon = to_f(row.get("중심위도")), to_f(row.get("중심경도"))
        if not clat or not clon:
            continue
        size = to_f(row.get("한변_m"), 100.0) or 100.0
        cx, cy = geo.project(lat0, lon0, clat, clon)
        h = size / 2
        if cx + h < x0 or cx - h > x1 or cy + h < y0 or cy - h > y1:
            continue
        frac = geo.cell_coverage(cx, cy, size, poly)
        if frac > 0:
            yield row, frac


def residents_workers(area: dict, cells: list[dict]) -> dict:
    """P10 안의 배후 주거세대 H 와 직장인구 W."""
    H = W = 0.0
    used = 0
    for row, frac in _cells_in(area["P10"], cells, area["위도"], area["경도"]):
        H += to_f(row.get("세대수")) * frac
        W += to_f(row.get("직장인구")) * frac
        used += 1
    return {"H": H, "W": W, "격자_사용": used}


def foot_traffic(area: dict, points: list[dict], site_side: str) -> dict:
    """P5 안의 유동인구. 오전은 도로 좌·우로 나눠 횡단저항을 적용한다."""
    lat0, lon0 = area["위도"], area["경도"]
    p5 = area["P5"]
    same = opp = 0.0
    d_all = 0.0
    side_seen = set()
    unknown_side = 0
    안분 = 0            # 영역 단위 값을 면적비로 나눠 쓴 행 수
    면적미상 = 0        # 영역 값인데 단위면적이 없어 버린 행 수
    출처 = set()
    p5_area = geo.shoelace_area(p5)

    for row in points:
        lat, lon = to_f(row.get("위도")), to_f(row.get("경도"))
        if not lat or not lon:
            continue
        x, y = geo.project(lat0, lon0, lat, lon)
        if not geo.point_in_poly(x, y, p5):
            continue
        n = to_f(row.get("인원"))
        출처.add(str(row.get("출처", "") or "실측").strip() or "실측")

        # 영역 단위 대용 데이터 — P5 면적비로 안분한다
        unit_area = to_f(row.get("단위면적_m2"))
        src = str(row.get("출처", "")).strip()
        if unit_area > 0:
            if p5_area <= 0:
                continue
            ratio = min(1.0, p5_area / unit_area)
            n *= ratio * c("유동_안분_집중계수")
            안분 += 1
        elif src and src != "실측":
            # 영역 값인데 면적을 모른다 — 추측한 면적으로 나눈 값은 근거가 아니다
            면적미상 += 1
            continue

        band = str(row.get("시간대", "")).strip()
        if band == ALL:
            d_all += n
            continue
        if band != AM:
            continue
        side = str(row.get("도로변", "")).strip()
        side_seen.add(side)
        if not side or not site_side:
            unknown_side += 1
            same += n          # 방향을 모르면 보정하지 않는다(보수적이지 않음 → 경고)
        elif side == site_side:
            same += n
        else:
            opp += n

    k = c("횡단저항")
    warn = []
    if 안분:
        쓴출처 = ", ".join(sorted(x for x in 출처 if x and x != "실측")) or "영역 단위"
        warn.append(f"⛔ 유동인구가 실측이 아닙니다 — {쓴출처} {안분}건을 P5 면적비로 "
                    f"안분했습니다. 균등분포를 가정한 값이라 간선도로변 집중이 반영되지 "
                    f"않았고, 집중계수 {c('유동_안분_집중계수')} 는 미검증입니다. "
                    f"명세가 요구하는 07~09시 현장 실측 카운트를 대신하지 못합니다.")
    if 면적미상:
        warn.append(f"⚠ 영역 단위 유동 행 {면적미상}건을 버렸습니다 — 단위면적_m2 가 없어 "
                    f"안분할 수 없습니다. 면적을 추측해 나누면 그 값은 근거가 아닙니다.")
    if unknown_side:
        warn.append(f"⚠ 도로변 미상 유동 지점 {unknown_side}곳 — 횡단저항 보정 없이 "
                    f"같은 편으로 계산했습니다. D_am 이 과대평가됩니다.")
    if not points:
        warn.append("⛔ 유동인구 데이터 없음 — D_am 은 알고리즘 정확도의 핵심 변수입니다. "
                    "07~09시 현장 통행량 실측 카운트가 필요합니다.")
    return {
        "D_am_같은편": same, "D_am_반대편": opp,
        "실측여부": not 안분, "안분_행": 안분, "면적미상_행": 면적미상,
        "D_am": same + opp,
        "D_am_adj": same + opp * k,
        "D_all": d_all,
        "횡단저항": k,
        "경고": warn,
    }


def weekend_night(area: dict, points: list[dict]) -> float:
    """주말·야간 유입(Mode B 배점용). 시간대 라벨이 '주말' 또는 '야간' 인 지점의 합."""
    lat0, lon0 = area["위도"], area["경도"]
    tot = 0.0
    for row in points:
        band = str(row.get("시간대", "")).strip()
        if band not in ("주말", "야간"):
            continue
        lat, lon = to_f(row.get("위도")), to_f(row.get("경도"))
        if not lat or not lon:
            continue
        x, y = geo.project(lat0, lon0, lat, lon)
        if geo.point_in_poly(x, y, area["P5"]):
            tot += to_f(row.get("인원"))
    return tot


def demand(area: dict, cells: list[dict], points: list[dict], site_side: str) -> dict:
    hw = residents_workers(area, cells)
    ft = foot_traffic(area, points, site_side)
    out = {**hw, **ft, "주말야간": weekend_night(area, points)}
    if not cells:
        out.setdefault("경고", []).append(
            "⛔ 격자 인구 데이터 없음 — H·W 가 0 입니다. 통계청 SGIS 격자를 넣으십시오.")
    return out


def load_cells(path) -> list[dict]:
    return read_csv(path) if path else []


def load_points(path) -> list[dict]:
    return read_csv(path) if path else []
