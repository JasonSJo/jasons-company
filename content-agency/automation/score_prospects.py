#!/usr/bin/env python3
"""
업종 전문 콘텐츠 대행 — 타깃(잠재고객) 우선순위 점수화

수집한 잠재고객 CSV를 읽어 '콘텐츠 니즈 = 전환 가능성' 점수로 정렬한다.
니즈가 큰 곳(리뷰 적음·답글 없음·SNS 방치·신규 오픈)이 상단으로 온다.
콜드 아웃리치를 상단부터 치면 같은 노력으로 계약 확률이 올라간다. API 비용 없음.

CSV 형식(타겟리스트.example.csv 참고):
  상호,업종,지역,연락처,플레이스_리뷰수,답글여부,SNS_최근게시_경과일,신규오픈_개월,웹사이트

사용법:
  python score_prospects.py --csv 타겟리스트.example.csv
  python score_prospects.py --csv my.csv --top 20
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def to_int(v, default=0):
    try:
        return int(str(v).replace(",", "").strip())
    except (ValueError, AttributeError):
        return default


def score(row: dict) -> tuple[int, list[str]]:
    pts, why = 0, []
    reviews = to_int(row.get("플레이스_리뷰수"), 999)
    if reviews < 20:
        pts += 2; why.append("리뷰 적음")
    if str(row.get("답글여부", "")).strip().upper() in ("N", "NO", "아니오", "X", ""):
        pts += 2; why.append("답글 없음")
    if to_int(row.get("SNS_최근게시_경과일"), 0) > 30:
        pts += 2; why.append("SNS 방치")
    opened = to_int(row.get("신규오픈_개월"), 99)
    if 0 < opened <= 6:
        pts += 2; why.append("신규 오픈")
    web = str(row.get("웹사이트", "")).strip().upper()
    if web in ("N", "NO", "없음", "X", ""):
        pts += 1; why.append("웹 없음")
    return pts, why


def main() -> int:
    ap = argparse.ArgumentParser(description="잠재고객 우선순위 점수화")
    ap.add_argument("--csv", default=str(ROOT / "타겟리스트.example.csv"))
    ap.add_argument("--top", type=int, default=0, help="상위 N곳만 출력(0=전체)")
    ap.add_argument("--out", default=str(ROOT / "output" / "타겟_우선순위.md"))
    args = ap.parse_args()

    p = Path(args.csv)
    if not p.exists():
        print(f"타깃 CSV 를 찾을 수 없습니다: {p}", file=sys.stderr)
        return 1

    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    if not rows:
        print("CSV 에 데이터가 없습니다.", file=sys.stderr)
        return 1

    ranked = []
    for r in rows:
        pts, why = score(r)
        ranked.append((pts, why, r))
    ranked.sort(key=lambda x: x[0], reverse=True)
    if args.top:
        ranked = ranked[:args.top]

    def tier(p):
        return "🔥 최우선" if p >= 6 else ("⭐ 우선" if p >= 4 else "일반")

    lines = ["# 타깃 우선순위 (니즈 점수 높은 순)", "",
             f"총 {len(rows)}곳 · 점수 = 콘텐츠 니즈 = 전환 가능성. 상단부터 접촉 권장.", "",
             "| 순위 | 상호 | 업종 | 지역 | 연락처 | 점수 | 등급 | 근거 |",
             "|---:|---|---|---|---|---:|---|---|"]
    for i, (pts, why, r) in enumerate(ranked, 1):
        lines.append(f"| {i} | {r.get('상호','')} | {r.get('업종','')} | {r.get('지역','')} | "
                     f"{r.get('연락처','')} | {pts} | {tier(pts)} | {', '.join(why) or '-'} |")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    hot = sum(1 for p, _, _ in ranked if p >= 6)
    print(f"점수화 완료: {out.relative_to(ROOT.parent)}")
    print(f"  🔥 최우선 {hot}곳 · 전체 {len(ranked)}곳 → 상단부터 아웃리치")
    print("  다음: 영업-아웃리치-키트.md 스크립트로 상위 20~30곳 접촉")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
