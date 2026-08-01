#!/usr/bin/env python3
"""
업종 전문 콘텐츠 대행 — 30일 콘텐츠 캘린더 자동 생성기

업체 프로필(business.yaml) 하나로, 업종별 키워드 공식(플레이북)에 따라
발행일이 배정된 콘텐츠 캘린더를 자동 생성한다. API 비용 없음(순수 규칙 기반).

출력물(content_calendar.generated.yaml)은 그대로 generate_content.py 의 입력이 된다.

사용법:
  python build_calendar.py                          # business.example.yaml → 30일
  python build_calendar.py --business my.yaml --days 30 --start 2026-08-01
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml 이 필요합니다:  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent

# 업종별 토픽 템플릿. {kw}=핵심키워드, {region}=지역, {menu}=대표 항목
TOPIC_TEMPLATES = {
    "요식업": {
        "blog": ["{region} {menu} 맛집", "{region} {situation} 좋은 곳", "{menu} 제대로 즐기는 법"],
        "reels": ["{menu} 30초 소개", "{region} 웨이팅 그래도 가는 이유"],
        "review": ["최근 리뷰 답글 일괄 처리"],
    },
    "병의원": {
        "blog": ["{menu} 과정 단계별 정리", "{symptom} 확인할 3가지", "{menu} 후 관리 가이드"],
        "reels": ["{menu} 궁금증 Q&A", "{symptom} 이럴 땐 내원하세요"],
        "review": ["상담 후기 답글 정리"],
    },
    "뷰티": {
        "blog": ["{menu} 시술 정보", "{region} {menu} 추천", "여름 {menu} 관리 팁"],
        "reels": ["{menu} 전후 비교", "홈케어 3가지 루틴"],
        "review": ["예약 고객 리뷰 답글"],
    },
    "전문서비스": {
        "blog": ["{menu} 절차 정리", "{kw} 자주 묻는 질문", "{menu} 사례로 보는 핵심"],
        "reels": ["{kw} 놓치기 쉬운 포인트"],
        "review": ["상담 신청 응대 정리"],
    },
}

# 주간 발행 리듬 (요일: 0=월 … 6=일)  채널
WEEKLY_RHYTHM = [(0, "blog"), (2, "reels"), (3, "blog"), (4, "review"), (5, "blog")]


def fmt(tpl: str, biz: dict, menu: str) -> str:
    return (tpl.replace("{region}", biz.get("region", ""))
               .replace("{menu}", menu)
               .replace("{kw}", biz.get("keyword", menu))
               .replace("{situation}", biz.get("situation", "모임"))
               .replace("{symptom}", biz.get("symptom", "증상")).strip())


def build(biz: dict, days: int, start: dt.date) -> list[dict]:
    industry = biz["industry"]
    templates = TOPIC_TEMPLATES.get(industry)
    if not templates:
        raise SystemExit(f"지원하지 않는 업종: {industry} (요식업/병의원/뷰티/전문서비스)")
    menus = biz.get("menus") or [biz.get("keyword", "대표 항목")]

    items, mi, ti = [], 0, {"blog": 0, "reels": 0, "review": 0}
    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        for wd, channel in WEEKLY_RHYTHM:
            if day.weekday() != wd:
                continue
            pool = templates[channel]
            menu = menus[mi % len(menus)]
            topic = fmt(pool[ti[channel] % len(pool)], biz, menu)
            ti[channel] += 1
            mi += 1
            items.append({
                "date": day.isoformat(),
                "industry": industry,
                "channel": channel,
                "brand": biz.get("brand", ""),
                "region": biz.get("region", ""),
                "strengths": biz.get("strengths", ""),
                "target": biz.get("target", ""),
                "topic": topic,
            })
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description="30일 콘텐츠 캘린더 자동 생성")
    ap.add_argument("--business", default=str(ROOT / "business.example.yaml"))
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--start", default=dt.date.today().isoformat(), help="YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--out", default=str(ROOT / "content_calendar.generated.yaml"))
    args = ap.parse_args()

    biz_path = Path(args.business)
    if not biz_path.exists():
        print(f"업체 프로필을 찾을 수 없습니다: {biz_path}", file=sys.stderr)
        return 1
    biz = yaml.safe_load(biz_path.read_text(encoding="utf-8"))
    start = dt.date.fromisoformat(args.start)

    items = build(biz, args.days, start)
    header = f"# {biz.get('brand','')} · {biz['industry']} · {args.start}부터 {args.days}일 · 자동 생성 {len(items)}건\n"
    Path(args.out).write_text(header + yaml.safe_dump(items, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"캘린더 생성 완료: {Path(args.out).name} · {len(items)}건")
    print(f"다음 단계:  python generate_content.py --calendar {Path(args.out).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
