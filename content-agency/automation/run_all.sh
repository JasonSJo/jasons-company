#!/usr/bin/env bash
# 업종 전문 콘텐츠 대행 — 전체 자동화 오케스트레이터
#
# 업체 프로필 하나로 다음을 한 번에 실행한다:
#   1) 캘린더 생성  2) 콘텐츠 생성  3) 규제 검출  4) 규제 통과분 자동 승인
#   5) 채널별 발행 패키지 생성  6) (지표 CSV 있으면) 월간 리포트
#
# 사람이 남는 일: (a) 의료·법률 등 보류분 최종 검수  (b) 플랫폼에 붙여넣기 게시  (c) 영업
#
# 사용법:
#   ./run_all.sh                          # 예시 업체, dry-run(무료)
#   ./run_all.sh --business my.yaml --days 30 --live   # 실제 콘텐츠(💳 비용)
set -euo pipefail
cd "$(dirname "$0")"

BUSINESS="business.example.yaml"; DAYS=30; LIVE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --business) BUSINESS="$2"; shift 2 ;;
    --days) DAYS="$2"; shift 2 ;;
    --live) LIVE="--live"; shift ;;
    *) echo "알 수 없는 옵션: $1"; exit 1 ;;
  esac
done
CAL="content_calendar.generated.yaml"

echo "════ 전체 자동화 파이프라인 ════"
echo "▶ 1/6 캘린더 생성 ($BUSINESS · ${DAYS}일)"
python3 build_calendar.py --business "$BUSINESS" --days "$DAYS" --out "$CAL"

echo "▶ 2/6 콘텐츠 생성 ${LIVE:-(dry-run·무료)}"
python3 generate_content.py --calendar "$CAL" $LIVE

echo "▶ 3/6 규제 검출"
if ls output/*.md >/dev/null 2>&1; then
  python3 compliance_check.py output || true
else
  echo "  ℹ dry-run: .md 없음(프롬프트만). --live 시 실제 검출."
fi

echo "▶ 4/6 규제 통과분 자동 승인"
python3 auto_approve.py

echo "▶ 5/6 채널별 발행 패키지 생성"
python3 publish.py || echo "  (승인분이 없으면 건너뜀)"

echo "▶ 6/6 월간 리포트"
if [ -f metrics.example.csv ]; then
  python3 report.py --brand "$(python3 -c "import yaml;print(yaml.safe_load(open('$BUSINESS')).get('brand',''))")" --month "$(date +%Y-%m 2>/dev/null || echo YYYY-MM)" || true
else
  echo "  ℹ 지표 CSV 없음 — 리포트는 실적 데이터 준비 후 report.py 로 생성."
fi

echo ""
echo "════ 완료 ════"
echo "결과물:"
echo "  · 발행 패키지: output/publish/  (붙여넣기 후 게시 — 사람)"
echo "  · 보류분(의료·법률·규제위반): review.html 에서 검수 — 사람"
echo "  · 월간 리포트: output/월간리포트.md (지표 있을 때)"
