#!/usr/bin/env python3
"""
카페 프랜차이즈 상권 분석 — 매출·손익 시뮬레이션과 민감도

score_sites.py 가 "어디가 좋은가"를 답한다면, 이 도구는 한 후보지에 대해
"얼마나 버는가 / 어디까지 버티는가"를 답한다.

  · 월 손익계산서(추정)
  · 손익분기 역산 — BEP 를 넘으려면 하루 몇 명이 필요한가
  · 민감도 — 객단가·점유율·임대료가 ±20% 흔들릴 때 영업이익이 어떻게 되는가

API 비용 없음.

사용법:
  python estimate_revenue.py                              # 전체 후보지 요약
  python estimate_revenue.py --site "성수 연무장길"        # 한 곳 상세 + 민감도
  python estimate_revenue.py --site "성수 연무장길" --rent 300 --ticket 5800
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from common import (analyze, estimate_pnl, estimate_revenue, nf, read_csv, score_site,
                    to_f, variable_rate, write_text)

ROOT = Path(__file__).resolve().parent
STEPS = (-0.2, -0.1, 0.0, 0.1, 0.2)


def pnl_table(p: dict) -> list[str]:
    s = p["월매출_만원"]
    pct = lambda v: f"{nf(v / s * 100, 1):>5}%" if s else "  —  "
    return [
        "| 항목 | 금액(만원) | 매출대비 |", "|---|---:|---:|",
        f"| 매출 | {nf(s)} | 100.0% |",
        f"| (−) 변동비 (재료·수수료·로열티·광고) | {nf(p['변동비_만원'])} | {pct(p['변동비_만원'])} |",
        f"| **공헌이익** | **{nf(p['공헌이익_만원'])}** | {pct(p['공헌이익_만원'])} |",
        f"| (−) 인건비 | {nf(p['인건비_만원'])} | {pct(p['인건비_만원'])} |",
        f"| (−) 임대료·관리비 | {nf(p['임대료_만원'])} | {pct(p['임대료_만원'])} |",
        f"| (−) 기타 고정비 | {nf(p['고정비_만원'] - p['인건비_만원'] - p['임대료_만원'])} | "
        f"{pct(p['고정비_만원'] - p['인건비_만원'] - p['임대료_만원'])} |",
        f"| **영업이익** | **{nf(p['영업이익_만원'])}** | **{pct(p['영업이익_만원'])}** |",
    ]


def breakeven_customers(p: dict, rev: dict, brand: dict) -> str:
    bep = p["BEP월매출_만원"]
    if not bep:
        return "- 손익분기: **구조적으로 도달 불가** (변동비+인건비율이 100% 이상)"
    days = to_f(brand.get("영업일수"), 30)
    need = bep * 10000 / rev["객단가_원"] / days
    now = rev["일객수_추정"]
    gap = now - need
    verdict = f"여유 {nf(gap)}명" if gap >= 0 else f"**{nf(-gap)}명 부족**"
    return (f"- 손익분기 월매출 **{nf(bep)}만원** = 하루 **{nf(need)}명** "
            f"(추정 {nf(now)}명 → {verdict})")


def sensitivity(site: dict, brand: dict, pois: list[dict]) -> list[str]:
    """서로 다른 세 레버를 흔들어 영업이익이 어디서 음수로 꺾이는지 본다.

    객단가와 집객력은 둘 다 매출을 같은 비율로 움직여 결과가 동일하므로
    한 줄('매출')로 합치고, 나머지 두 줄은 성격이 다른 비용 레버를 쓴다.
    """
    rows = []
    for label, key in (("매출 (객단가·집객)", "sales"), ("임대료", "rent"), ("재료비율", "cogs")):
        cells = []
        for d in STEPS:
            s2, b2 = dict(site), dict(brand)
            if key == "sales":
                b2["객단가_원"] = to_f(brand.get("객단가_원"), 5000) * (1 + d)
            elif key == "rent":
                s2["월임대료_만원"] = to_f(site.get("월임대료_만원")) * (1 + d)
            else:
                v = dict(brand.get("변동비", {}) or {})
                v["재료비율"] = to_f(v.get("재료비율"), 0.35) * (1 + d)
                b2["변동비"] = v
            scored = score_site(s2, pois, to_f(b2.get("반경_m"), 500))
            rev = estimate_revenue(s2, scored, b2)
            p = estimate_pnl(s2, rev, b2)
            v = p["영업이익_만원"]
            cells.append(f"**{nf(v)}**" if d == 0 else (f"{nf(v)}" if v >= 0 else f"⛔{nf(v)}"))
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    head = ["| 변수 \\ 변동 | " + " | ".join(f"{d:+.0%}" if d else "기준" for d in STEPS) + " |",
            "|---|" + "---:|" * len(STEPS)]
    return head + rows


def main() -> int:
    ap = argparse.ArgumentParser(description="매출·손익 시뮬레이션")
    ap.add_argument("--sites", default=str(ROOT / "후보지.example.csv"))
    ap.add_argument("--pois", default=str(ROOT / "pois.example.csv"))
    ap.add_argument("--brand", default=str(ROOT / "brand.example.yaml"))
    ap.add_argument("--site", default="", help="후보지명(부분일치). 생략하면 전체 요약")
    ap.add_argument("--ticket", type=float, default=0, help="객단가(원) 덮어쓰기")
    ap.add_argument("--rent", type=float, default=0, help="월임대료(만원) 덮어쓰기")
    ap.add_argument("--out", default=str(ROOT / "output" / "손익_시뮬레이션.md"))
    args = ap.parse_args()

    sites = read_csv(Path(args.sites))
    pois_path = Path(args.pois)
    pois = read_csv(pois_path) if pois_path.exists() else []
    bpath = Path(args.brand)
    brand = (yaml.safe_load(bpath.read_text(encoding="utf-8")) or {}) if bpath.exists() else {}
    if args.ticket:
        brand["객단가_원"] = args.ticket

    if args.site:
        sites = [s for s in sites if args.site in (s.get("후보지명") or "")]
        if not sites:
            print(f"'{args.site}' 와 일치하는 후보지가 없습니다.", file=sys.stderr)
            return 1
    if args.rent:
        for s in sites:
            s["월임대료_만원"] = args.rent

    L = [f"# 매출·손익 시뮬레이션 — {brand.get('브랜드', '카페 프랜차이즈')}", "",
         f"객단가 {int(to_f(brand.get('객단가_원'), 5000)):,}원 · "
         f"영업일 {int(to_f(brand.get('영업일수'), 30))}일 · "
         f"변동비율 {nf(variable_rate(brand) * 100, 1)}%", ""]

    for s in sites:
        r = analyze(s, pois, brand)
        p, rev = r["손익"], r["매출추정"]
        L += [f"## {r['후보지명']} — {r['총점']}점 ({r['등급']})", "",
              f"상권 하루 카페수요 {nf(rev['상권수요_일객수'])}명 ÷ 경쟁 {rev['경쟁카페수']}곳 "
              f"× 입지배수 {rev['입지배수']} → 점유율 **{nf(rev['점유율'] * 100, 2)}%** "
              f"→ 하루 **{nf(rev['일객수_추정'])}명**", ""]
        if rev["좌석제약"]:
            L.append(f"> 좌석({nf(rev['좌석상한_일객수'])}명/일 처리)이 상한입니다. "
                     f"테이크아웃 동선·좌석 확충 시 상향 여지가 있습니다.\n")
        L += pnl_table(p) + ["", breakeven_customers(p, rev, brand),
                             f"- 초기투자 **{nf(p['초기투자_만원'])}만원** "
                             f"(보증금 {nf(p['보증금_만원'])} 회수분 제외 시 "
                             f"{nf(p['회수대상투자_만원'])}만원) → 회수 "
                             f"**{p['투자회수_개월'] or '—'}개월**", ""]
        if len(sites) == 1:
            L += ["### 민감도 — 영업이익(만원)", ""] + sensitivity(s, brand, pois) + [""]
        if r["리스크"]:
            L += ["**리스크**"] + [f"- {x}" for x in r["리스크"]] + [""]

    write_text(Path(args.out), "\n".join(L))
    print(f"시뮬레이션 {len(sites)}건 → {args.out}")
    for s in sites:
        r = analyze(s, pois, brand)
        p = r["손익"]
        print(f"  · {r['후보지명']:<16} 월매출 {nf(p['월매출_만원']):>7}만  "
              f"영업이익 {nf(p['영업이익_만원']):>7}만 ({nf(p['영업이익률'] * 100, 1):>5}%)  "
              f"회수 {p['투자회수_개월'] or '—'}개월")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
