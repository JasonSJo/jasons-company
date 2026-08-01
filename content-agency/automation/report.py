#!/usr/bin/env python3
"""
업종 전문 콘텐츠 대행 — 월간 성과 리포트 자동 집계

성과 지표 CSV(채널별 수치)를 읽어 월간 리포트(마크다운)를 자동 생성한다.
클라이언트에게 그대로 보낼 수 있는 형태. API 비용 없음.

CSV 형식(metrics.example.csv 참고):
  channel,metric,this_month,last_month
  블로그,검색 유입,4200,1350
  ...

사용법:
  python report.py --brand "성수 파스타랩" --month 2026-07 --csv metrics.example.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def pct(cur: float, prev: float) -> str:
    if prev == 0:
        return "신규" if cur else "-"
    d = (cur - prev) / prev * 100
    return f"{'+' if d >= 0 else ''}{d:.0f}%"


def num(s: str) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="월간 성과 리포트 자동 집계")
    ap.add_argument("--brand", default="(상호)")
    ap.add_argument("--month", default="YYYY-MM")
    ap.add_argument("--editor", default="담당 에디터")
    ap.add_argument("--csv", default=str(ROOT / "metrics.example.csv"))
    ap.add_argument("--out", default=str(ROOT / "output" / "월간리포트.md"))
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"지표 CSV 를 찾을 수 없습니다: {csv_path}", file=sys.stderr)
        return 1

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    if not rows:
        print("CSV 에 데이터가 없습니다.", file=sys.stderr)
        return 1

    lines = [
        f"# 월간 성과 리포트 — {args.brand}",
        f"> {args.month} · 담당 {args.editor}", "",
        "## 1. 한눈에 보기", "",
        "| 채널 | 지표 | 이번 달 | 지난 달 | 증감 |",
        "|---|---|---:|---:|---:|",
    ]
    improved = []
    for r in rows:
        cur, prev = num(r.get("this_month", 0)), num(r.get("last_month", 0))
        change = pct(cur, prev)
        lines.append(f"| {r.get('channel','')} | {r.get('metric','')} | "
                     f"{cur:,.0f} | {prev:,.0f} | {change} |")
        if prev and cur > prev:
            improved.append((r.get("metric", ""), change))

    lines += ["", "## 2. 핵심 요약", ""]
    if improved:
        top = sorted(improved, key=lambda x: x[1], reverse=True)[:3]
        lines.append("이번 달 개선 지표: " + ", ".join(f"{m}({c})" for m, c in top) + ".")
    else:
        lines.append("이번 달은 기반 데이터를 쌓는 단계로, 다음 달 성장 폭 확대가 기대됩니다.")

    lines += [
        "", "## 3. 다음 달 전략 제안", "",
        "- [ ] 개선 지표 채널에 콘텐츠 비중 확대",
        "- [ ] 성과 낮은 키워드 교체 및 A/B 테스트",
        "- [ ] 시즌 이슈 콘텐츠 선제 기획", "",
        "## 4. 논의 필요 (미팅 안건)", "",
        "- 예산·채널 확장 등 비용 발생 항목은 클라이언트 승인 필요 💳", "",
    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"리포트 생성 완료: {out.relative_to(ROOT.parent)} ({len(rows)}개 지표)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
