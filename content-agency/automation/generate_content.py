#!/usr/bin/env python3
"""
업종 전문 콘텐츠 대행 — 콘텐츠 자동 생성 엔진

content_calendar.yaml 의 각 항목을 읽어 업종 플레이북 + 템플릿 프롬프트로
블로그/릴스/리뷰답글 초안을 일괄 생성하고 output/ 에 저장한다.

⚠️ 비용/승인 관련:
  - --dry-run(기본값)은 프롬프트만 조립해 output/ 에 저장한다. API를 호출하지 않으므로 비용이 0원이다.
  - --live 는 Claude API를 실제 호출한다. 토큰 비용이 발생하므로 사용자가 명시적으로 승인해야 하는 단계다.
  - API 키(ANTHROPIC_API_KEY)가 없으면 --live 는 실행을 거부한다.

사용법:
  python generate_content.py                      # dry-run: 프롬프트만 생성 (무료)
  python generate_content.py --live               # 실제 생성 (비용 발생 — 승인 필요)
  python generate_content.py --calendar my.yaml   # 다른 캘린더 지정
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml 이 필요합니다:  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUTPUT_DIR = ROOT / "output"
MODEL = "claude-opus-5"

# 업종별 규제 가드레일 (플레이북에서 요약)
GUARDRAILS = {
    "요식업": "근거 없는 '최고/1위' 등 최상급 표현 금지, 원산지·가격 정확성 유지(표시광고법).",
    "병의원": "치료효과 보장·단정('완치','부작용 없는','100%') 금지, 환자 후기·전후사진 광고 활용 제한(의료법 제56조). 발행 전 원장 승인 필수.",
    "뷰티": "시술 효과의 개인차 명시, 화장품·의료기기 관련 과장·의학적 효능 표현 주의(화장품법).",
    "전문서비스": "승소·환급 결과 보장 금지, 수임 유인성 과장 금지(변호사법·세무사법 등). 발행 전 담당 전문가 승인 필수.",
}

CHANNEL_TASK = {
    "blog": "네이버 블로그 정보성 글 (공백 포함 1,200~1,800자, 소제목 3~5개, 훅→핵심정보→실용팁→부드러운 CTA)",
    "reels": "인스타그램 릴스 대본 (15~30초, 0~3초 훅 / 4~22초 전개 3포인트 / 23~30초 CTA, 초·화면·자막·나레이션 표 + 캡션 + 해시태그 8개)",
    "review": "플레이스/배달앱 리뷰 답글 (2~4문장, 진심 어린·개인화된 톤, 분기: 긍정/중립/부정)",
}


def build_prompt(item: dict) -> str:
    industry = item["industry"]
    guard = GUARDRAILS.get(industry, "관련 광고 규정을 준수할 것.")
    task = CHANNEL_TASK.get(item["channel"], "콘텐츠 초안")
    return f"""너는 {industry} 전문 콘텐츠 에디터다. 아래 조건으로 {task} 을(를) 작성해라.

[매장/기관 정보]
- 상호: {item.get('brand', '(미기재)')}
- 지역: {item.get('region', '(미기재)')}
- 강점: {item.get('strengths', '(미기재)')}
- 타깃 고객: {item.get('target', '(미기재)')}

[콘텐츠 조건]
- 주제/메인 키워드: {item['topic']}
- 검색/도달 의도: 정보 우선, 광고 톤 배제, 과장 없이 신뢰감 있게

[규제 가드레일 — {industry}]
{guard}

[출력]
1) 제목/훅 3안
2) 본문(또는 대본 표)
3) 해시태그
4) 검수 포인트 — 사람이 반드시 확인할 사실/가격/규제 항목"""


def generate_live(prompt: str, client) -> str:
    # 스트리밍으로 큰 출력의 HTTP 타임아웃을 방지 (claude-api 스킬 권장)
    with client.messages.stream(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    return "".join(b.text for b in msg.content if b.type == "text")


def main() -> int:
    ap = argparse.ArgumentParser(description="업종 전문 콘텐츠 자동 생성 엔진")
    ap.add_argument("--calendar", default=str(ROOT / "content_calendar.example.yaml"))
    ap.add_argument("--live", action="store_true", help="Claude API 실제 호출 (비용 발생 — 승인 필요)")
    args = ap.parse_args()

    calendar_path = Path(args.calendar)
    if not calendar_path.exists():
        print(f"캘린더 파일을 찾을 수 없습니다: {calendar_path}", file=sys.stderr)
        return 1

    items = yaml.safe_load(calendar_path.read_text(encoding="utf-8")) or []
    if not isinstance(items, list):
        print("캘린더 형식 오류: 최상위는 항목 리스트여야 합니다.", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(exist_ok=True)

    client = None
    if args.live:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("⚠️ --live 는 ANTHROPIC_API_KEY 가 필요하고 토큰 비용이 발생합니다.\n"
                  "   비용 승인 후 키를 설정하고 다시 실행하세요. (지금은 실행을 중단합니다.)",
                  file=sys.stderr)
            return 2
        try:
            import anthropic
        except ImportError:
            print("anthropic SDK 가 필요합니다:  pip install -r requirements.txt", file=sys.stderr)
            return 1
        client = anthropic.Anthropic()

    mode = "LIVE(비용 발생)" if args.live else "DRY-RUN(무료·프롬프트만)"
    print(f"모드: {mode} · 항목 {len(items)}건 · 출력: {OUTPUT_DIR}")

    manifest = []
    for i, item in enumerate(items, 1):
        prompt = build_prompt(item)
        slug = f"{i:02d}_{item['industry']}_{item['channel']}_{item['topic']}".replace(" ", "-")[:80]
        if args.live:
            print(f"  [{i}/{len(items)}] 생성 중… {slug}")
            body = generate_live(prompt, client)
            out = OUTPUT_DIR / f"{slug}.md"
            out.write_text(f"# {item['topic']}\n\n{body}\n", encoding="utf-8")
        else:
            body = prompt
            out = OUTPUT_DIR / f"{slug}.prompt.txt"
            out.write_text(prompt, encoding="utf-8")
        manifest.append({
            "slug": slug,
            "file": out.name,
            "industry": item["industry"],
            "channel": item["channel"],
            "topic": item["topic"],
            "brand": item.get("brand", ""),
            "mode": "live" if args.live else "dry-run",
            "status": "검수대기",   # 검수대기 | 승인 | 보류 | 반려
            "preview": body[:500],
        })
        print(f"      → {out.relative_to(REPO)}")

    # 검수 대시보드(review.html)가 읽는 매니페스트
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"매니페스트: {(OUTPUT_DIR / 'manifest.json').relative_to(REPO)}  →  review.html 로 검수")
    print("완료.")
    if not args.live:
        print("실제 콘텐츠를 생성하려면(비용 발생) 승인 후 --live 로 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
