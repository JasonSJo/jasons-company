#!/usr/bin/env python3
"""
업종 전문 콘텐츠 대행 — 규제 금지어 자동 검출 (컴플라이언스 QA)

콘텐츠(마크다운) 안의 광고 규제 위반 소지 표현을 자동으로 찾아낸다.
의료광고(의료법)·변호사법/세무사법·표시광고법 위반은 행정처분·과태료 리스크가 커,
발행 전 이 게이트로 걸러 사람 검수 부담을 줄인다. API 비용 없음(규칙 기반).

사용법:
  python compliance_check.py ../samples                 # 폴더 전체 스캔
  python compliance_check.py output/publish/blog/x.md   # 단일 파일
  python compliance_check.py ../samples --strict        # HIGH 발견 시 비정상 종료(발행 게이트)

종료코드: 0=문제없음/경고만, 1=HIGH 위반(‑‑strict 시), 2=경로 오류
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (정규식, 심각도, 설명, 근거)  — 심각도 HIGH=발행 차단 권장, WARN=검토 권장
RULES = [
    # 공통 최상급·보장 (표시광고법)
    (r"1위|국내\s*1위|업계\s*1위", "HIGH", "객관적 근거 없는 '1위'", "표시광고법"),
    (r"최고(의|급)?|최상(의)?|최강", "WARN", "최상급 표현", "표시광고법"),
    (r"유일(한|무이)|단\s*하나의", "WARN", "'유일' 배타적 표현", "표시광고법"),
    (r"100\s*%|백\s*퍼센트", "HIGH", "'100%' 단정", "표시광고법"),
    (r"무조건|절대(적)?|반드시", "WARN", "단정·절대 표현", "표시광고법"),
    (r"보장(합니다|해\s*드립니다|됩니다)?", "WARN", "'보장' 표현(맥락 확인)", "표시광고법"),
    # 의료 (의료법·의료광고)
    (r"완치|완벽(하게|한)?\s*(치료|개선)?", "HIGH", "치료효과 단정('완치/완벽')", "의료법"),
    (r"부작용(이)?\s*(전혀\s*)?(없|無)", "HIGH", "'부작용 없음' 단정", "의료법"),
    (r"평생|영구(적)?", "WARN", "'평생/영구' 지속효과 단정", "의료법"),
    (r"즉시\s*효과|바로\s*효과", "WARN", "즉효성 단정", "의료법"),
    (r"명의|신의\s*손", "WARN", "과장된 의료인 표현", "의료법"),
    (r"세계\s*최초|국내\s*최초", "WARN", "근거 필요한 '최초'", "의료법·표시광고법"),
    # 법률·세무 (변호사법·세무사법)
    (r"승소\s*(보장|확정)|반드시\s*승소|무조건\s*승소", "HIGH", "승소 보장 표현", "변호사법"),
    (r"100\s*%\s*환급|환급\s*보장|무조건\s*환급", "HIGH", "환급 보장 표현", "세무사법"),
]

COMPILED = [(re.compile(p), sev, desc, law) for p, sev, desc, law in RULES]


def scan_text(text: str):
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # 발행 카피가 아닌 내부 메모는 제외: HTML 주석, 검수 체크박스(- [ ]/- [x])
        if stripped.startswith("<!--") or re.match(r"- \[[ xX]\]", stripped):
            continue
        for rx, sev, desc, law in COMPILED:
            m = rx.search(line)
            if m:
                hits.append((i, sev, m.group(0), desc, law, line.strip()[:70]))
    return hits


def collect(path: Path):
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.md"))


def main() -> int:
    ap = argparse.ArgumentParser(description="규제 금지어 자동 검출")
    ap.add_argument("path", nargs="?", default="../samples")
    ap.add_argument("--strict", action="store_true", help="HIGH 위반 발견 시 비정상 종료(발행 게이트)")
    args = ap.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"경로를 찾을 수 없습니다: {root}", file=sys.stderr)
        return 2

    files = collect(root)
    if not files:
        print("스캔할 .md 파일이 없습니다.")
        return 0

    total_high = total_warn = 0
    for f in files:
        hits = scan_text(f.read_text(encoding="utf-8"))
        if not hits:
            print(f"✅ {f.name} — 문제 없음")
            continue
        print(f"\n🔎 {f.name}")
        for line_no, sev, term, desc, law, ctx in hits:
            mark = "⛔" if sev == "HIGH" else "⚠️"
            print(f"   {mark} L{line_no} [{sev}] '{term}' — {desc} ({law})")
            print(f"        …{ctx}…")
            if sev == "HIGH":
                total_high += 1
            else:
                total_warn += 1

    print(f"\n요약: ⛔ HIGH {total_high}건 · ⚠️ WARN {total_warn}건 · 파일 {len(files)}개")
    if total_high:
        print("⛔ HIGH 위반은 발행 전 반드시 수정하세요(행정처분·과태료 리스크).")
    if args.strict and total_high:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
