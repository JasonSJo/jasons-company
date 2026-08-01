#!/usr/bin/env python3
"""
업종 전문 콘텐츠 대행 — 규제 통과분 자동 승인

output/manifest.json 의 각 콘텐츠를 규제 검출기로 스캔해:
  - HIGH 위반 없음 → status='승인'  (발행 파이프라인으로 진행)
  - HIGH 위반 있음 → status='보류'  (사람 수정 필요, 발행 제외)

review.html 의 수동 승인 단계를 대체하는 자동 게이트. API 비용 없음.

⚠️ 자동 승인은 규제 '금지어' 1차 필터일 뿐이다. 의료·법률 콘텐츠는 법적으로
   전문가 최종 확인이 필요하므로, 해당 업종은 발행 전 사람 검수를 반드시 유지할 것.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import compliance_check as cc

OUT = Path(__file__).resolve().parent / "output"


def main() -> int:
    mani = OUT / "manifest.json"
    if not mani.exists():
        print("output/manifest.json 이 없습니다. 먼저 generate_content.py 실행.", file=sys.stderr)
        return 1

    items = json.loads(mani.read_text(encoding="utf-8"))
    approved = held = 0
    for it in items:
        f = OUT / it.get("file", "")
        text = f.read_text(encoding="utf-8") if f.exists() else it.get("preview", "")
        high = [h for h in cc.scan_text(text) if h[1] == "HIGH"]
        # 의료·법률은 규제 통과여도 사람 확인 필요 → 자동승인 대상에서 제외(보류)
        needs_human = it.get("industry") in ("병의원", "전문서비스")
        if high or needs_human:
            it["status"] = "보류"
            held += 1
        else:
            it["status"] = "승인"
            approved += 1

    mani.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"자동 승인 {approved}건 · 보류 {held}건(규제 위반 또는 의료·법률=사람 검수 필요)")
    if held:
        print("  보류분은 review.html 에서 사람 검수 후 수동 승인하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
