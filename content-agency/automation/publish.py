#!/usr/bin/env python3
"""
업종 전문 콘텐츠 대행 — 발행 패키지 생성기

검수에서 '승인'된 콘텐츠를 채널별(블로그/릴스/리뷰) 발행 패키지로 묶는다.
각 패키지는 발행 체크리스트가 붙어, 담당자가 해당 플랫폼에 붙여넣기만 하면 된다.

입력 우선순위:
  1) output/approved.json  (review.html 에서 '승인본 내보내기' 한 파일)  ← 권장
  2) output/manifest.json  에서 status == '승인' 인 항목
  (둘 다 없으면 안내 후 종료)

출력: output/publish/<채널>/<slug>.md  +  output/publish/발행체크리스트.md

⚠️ 최종 게시(네이버·인스타 등)는 각 플랫폼 계정 인증이 필요해 무인 자동화 대상이 아니다.
   이 스크립트는 '붙여넣기 준비 완료' 상태까지 자동화한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUTPUT_DIR = ROOT / "output"
PUB_DIR = OUTPUT_DIR / "publish"

# 채널별 발행 가이드 (플레이북 기준)
CHANNEL_GUIDE = {
    "blog": {
        "label": "네이버 블로그",
        "steps": [
            "네이버 블로그 글쓰기 → 제목 3안 중 검색 키워드 포함된 것 선택",
            "본문 붙여넣기 → 소제목/이미지 배치",
            "발행 전: 검수 포인트(사실·가격·규제) 최종 확인",
            "태그 입력 → 플레이스/스마트플레이스 연동 확인 → 발행",
        ],
        "cadence": "주 2~3회 (오전 발행 권장)",
    },
    "reels": {
        "label": "인스타그램 릴스",
        "steps": [
            "대본 표대로 촬영(촬영 준비물 참고) → 편집·자막",
            "캡션 + 해시태그 붙여넣기",
            "커버 이미지 선택 → 예약 또는 즉시 게시",
        ],
        "cadence": "주 1~2회 (저녁 시간대 도달 유리)",
    },
    "review": {
        "label": "플레이스/배달앱 리뷰 답글",
        "steps": [
            "부정 리뷰 답글은 사람 최종 승인 후 등록",
            "긍정/중립 답글은 톤 확인 후 일괄 등록",
        ],
        "cadence": "주 2회 일괄 처리",
    },
}


def load_entries():
    approved = OUTPUT_DIR / "approved.json"
    manifest = OUTPUT_DIR / "manifest.json"
    if approved.exists():
        return json.loads(approved.read_text(encoding="utf-8")), "approved.json"
    if manifest.exists():
        items = json.loads(manifest.read_text(encoding="utf-8"))
        return [it for it in items if it.get("status") == "승인"], "manifest.json(status=승인)"
    return None, None


def read_body(entry) -> str:
    fp = OUTPUT_DIR / entry.get("file", "")
    if fp.exists():
        return fp.read_text(encoding="utf-8")
    return entry.get("preview", "(본문 없음)")


def main() -> int:
    entries, source = load_entries()
    if entries is None:
        print("output/approved.json 또는 output/manifest.json 이 없습니다.\n"
              "먼저 generate_content.py 실행 → review.html 로 승인하세요.", file=sys.stderr)
        return 1
    if not entries:
        print("승인된 항목이 없습니다. review.html 에서 '승인' 후 다시 실행하세요.", file=sys.stderr)
        return 2

    PUB_DIR.mkdir(parents=True, exist_ok=True)
    checklist = ["# 발행 체크리스트", "", f"소스: {source} · 승인 {len(entries)}건", ""]

    by_channel = {}
    for e in entries:
        ch = e.get("channel", "blog")
        by_channel.setdefault(ch, []).append(e)

    for ch, group in by_channel.items():
        guide = CHANNEL_GUIDE.get(ch, {"label": ch, "steps": [], "cadence": "-"})
        ch_dir = PUB_DIR / ch
        ch_dir.mkdir(exist_ok=True)
        checklist += [f"## {guide['label']} — {len(group)}건 (권장 주기: {guide['cadence']})", ""]
        for e in group:
            body = read_body(e)
            header = (
                f"<!-- 발행 패키지 · {guide['label']} · {e.get('industry','')} · {e.get('brand','')} -->\n"
                f"<!-- 발행 절차:\n" + "".join(f"     {i}. {s}\n" for i, s in enumerate(guide["steps"], 1)) + "-->\n\n"
            )
            out = ch_dir / f"{e['slug']}.md"
            out.write_text(header + body, encoding="utf-8")
            checklist.append(f"- [ ] {e.get('topic','')}  →  `{out.relative_to(REPO)}`")
        checklist.append("")

    (PUB_DIR / "발행체크리스트.md").write_text("\n".join(checklist), encoding="utf-8")
    print(f"발행 패키지 생성 완료: {PUB_DIR.relative_to(REPO)} ({len(entries)}건)")
    print(f"체크리스트: {(PUB_DIR / '발행체크리스트.md').relative_to(REPO)}")
    print("각 파일을 해당 플랫폼에 붙여넣어 발행하세요. (최종 게시 클릭은 사람이)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
