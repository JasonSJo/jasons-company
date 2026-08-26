#!/usr/bin/env python3
"""
M2 · 수요 변수 산출

100m 격자 인구를 등시선 폴리곤과 **면적 가중 교차**해 배후 수요를 뽑고,
유동인구는 출근 진행 방향과 후보지의 도로 좌·우 위치로 나눠 보정한다.

    H     = Σ(격자세대수   × 격자∩P10 면적비)
    W     = Σ(격자직장인구 × 격자∩P10 면적비)
    D_am  = Σ(07~10시 유동인구, P5 기준)
    D_all = Σ(전시간대 유동인구, P5 기준)

    D_am_adj = D_am_같은편 + (D_am_반대편 × 0.3)

횡단저항 0.3 은 **미검증 실무 판단값**이다(config.횡단저항). M6 가 교정한다.

입력 파일
  격자인구.csv  격자ID,중심위도,중심경도,한변_m,세대수,직장인구
  유동인구.csv  지점ID,위도,경도,도로변,시간대,인원      시간대 ∈ {오전, 전체}
                도로변은 후보지 CSV 의 `도로변` 과 같은 라벨 체계여야 한다(A/B 등).
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

    for row in points:
        lat, lon = to_f(row.get("위도")), to_f(row.get("경도"))
        if not lat or not lon:
            continue
        x, y = geo.project(lat0, lon0, lat, lon)
        if not geo.point_in_poly(x, y, p5):
            continue
        n = to_f(row.get("인원"))
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
    if unknown_side:
        warn.append(f"⚠ 도로변 미상 유동 지점 {unknown_side}곳 — 횡단저항 보정 없이 "
                    f"같은 편으로 계산했습니다. D_am 이 과대평가됩니다.")
    if not points:
        warn.append("⛔ 유동인구 데이터 없음 — D_am 은 알고리즘 정확도의 핵심 변수입니다. "
                    "07~09시 현장 통행량 실측 카운트가 필요합니다.")
    return {
        "D_am_같은편": same, "D_am_반대편": opp,
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
