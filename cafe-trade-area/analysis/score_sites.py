#!/usr/bin/env python3
"""
카페 프랜차이즈 상권 분석 — 후보지 점수화·순위

후보지 CSV + POI CSV + 브랜드 파라미터를 읽어 100점 만점으로 채점하고
등급(A~D)과 함께 순위표를 만든다. API 비용 없음(전부 규칙 기반).

배점: 배후수요 30 · 유동인구 25 · 경쟁 20 · 접근성 15 · 비용 10

사용법:
  python score_sites.py
  python score_sites.py --sites 내후보지.csv --pois output/pois.csv --top 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from common import WEIGHTS, analyze, nf, read_csv, write_json, write_text

ROOT = Path(__file__).resolve().parent


def load_brand(path: Path) -> dict:
    if not path.exists():
        print(f"브랜드 설정이 없어 기본값으로 진행합니다: {path}", file=sys.stderr)
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def bar(pts: float, full: int, width: int = 10) -> str:
    n = int(round(width * pts / full)) if full else 0
    return "█" * n + "·" * (width - n)


def render(results: list[dict], brand: dict) -> str:
    L = [f"# 상권 후보지 우선순위 — {brand.get('브랜드', '카페 프랜차이즈')}", "",
         f"후보지 {len(results)}곳 · 상권 반경 {int(brand.get('반경_m', 500))}m · "
         f"객단가 {int(brand.get('객단가_원', 5200)):,}원 기준", "",
         "| 순위 | 후보지 | 총점 | 등급 | 추정 월매출 | 영업이익 | BEP달성 | 회수개월 |",
         "|---:|---|---:|:--:|---:|---:|---:|---:|"]
    for i, r in enumerate(results, 1):
        p = r["손익"]
        pay = f"{nf(p['투자회수_개월'])}" if p["투자회수_개월"] else "—"
        L.append(f"| {i} | {r['후보지명']} | **{r['총점']}** | {r['등급']} | "
                 f"{nf(p['월매출_만원'])}만 | {nf(p['영업이익_만원'])}만 | "
                 f"{nf(p['BEP달성률'] * 100)}% | {pay} |")
    L.append("")
    L.append("> 등급: **A** 즉시 출점 검토(80+) · **B** 조건부 추천(65+) · "
             "**C** 보류·재협상(50+) · **D** 부적합")
    L += ["", "---", ""]

    for i, r in enumerate(results, 1):
        L.append(f"## {i}. {r['후보지명']} — {r['총점']}점 ({r['등급']}, {r['등급설명']})")
        if r["주소"]:
            L.append(f"`{r['주소']}`")
        L.append("")
        L.append("| 항목 | 점수 | | 근거 |")
        L.append("|---|---:|---|---|")
        for (k, w), why in zip(WEIGHTS.items(), r["근거"]):
            L.append(f"| {k} | {r['항목'][k]}/{w} | `{bar(r['항목'][k], w)}` | {why} |")
        c, p, rev = r["경쟁"], r["손익"], r["매출추정"]
        L += ["",
              f"- **경쟁** 반경 내 카페 {c['카페수']}곳 (동일포지션 {c['동일포지션']} · "
              f"앵커 {c['앵커브랜드']})",
              f"- **매출추정** 일 {nf(rev['일객수_추정'])}객 × {rev['객단가_원']:,}원 "
              f"→ 월 **{nf(p['월매출_만원'])}만원**",
              f"- **손익** 영업이익 {nf(p['영업이익_만원'])}만원 "
              f"({nf(p['영업이익률'] * 100, 1)}%) · BEP {p['BEP월매출_만원'] or '—'}만원",
              f"- **투자** {nf(p['초기투자_만원'])}만원(보증금 {nf(p['보증금_만원'])} 포함) · "
              f"회수 {p['투자회수_개월'] or '—'}개월"]
        if r["리스크"]:
            L += ["", "**리스크**"] + [f"- {x}" for x in r["리스크"]]
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="후보지 상권 점수화")
    ap.add_argument("--sites", default=str(ROOT / "후보지.example.csv"))
    ap.add_argument("--pois", default=str(ROOT / "pois.example.csv"))
    ap.add_argument("--brand", default=str(ROOT / "brand.example.yaml"))
    ap.add_argument("--top", type=int, default=0, help="상위 N곳만 출력(0=전체)")
    ap.add_argument("--out", default=str(ROOT / "output" / "상권_후보지_순위.md"))
    ap.add_argument("--json", default=str(ROOT / "output" / "sites_scored.json"))
    args = ap.parse_args()

    sites_path = Path(args.sites)
    if not sites_path.exists():
        print(f"후보지 CSV 를 찾을 수 없습니다: {sites_path}", file=sys.stderr)
        return 1
    sites = read_csv(sites_path)
    pois_path = Path(args.pois)
    pois = read_csv(pois_path) if pois_path.exists() else []
    if not pois:
        print(f"POI 파일이 없어 CSV 의 카페수_500m 값으로 경쟁을 계산합니다: {pois_path}",
              file=sys.stderr)
    brand = load_brand(Path(args.brand))

    results = [analyze(s, pois, brand) for s in sites if (s.get("후보지명") or "").strip()]
    results.sort(key=lambda r: (-r["총점"], -(r["손익"]["영업이익_만원"])))
    if args.top:
        results = results[: args.top]

    write_text(Path(args.out), render(results, brand))
    write_json(Path(args.json), results)

    print(f"후보지 {len(results)}곳 채점 완료 → {args.out}")
    for i, r in enumerate(results, 1):
        p = r["손익"]
        print(f"  {i}. [{r['등급']}] {r['후보지명']:<16} {r['총점']:>5}점  "
              f"월매출 {nf(p['월매출_만원']):>7}만  영업이익 {nf(p['영업이익_만원']):>7}만")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
