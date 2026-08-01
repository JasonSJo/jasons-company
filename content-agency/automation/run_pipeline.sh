#!/usr/bin/env bash
# 업종 전문 콘텐츠 대행 — 원커맨드 생산 파이프라인
#
# 캘린더 생성 → 콘텐츠 초안 생성 → 규제 검출(HIGH 차단)까지 자동 실행한다.
# 사람 개입은 이후 review.html(승인) 한 번뿐.
#
# 사용법:
#   ./run_pipeline.sh                         # 예시 업체로 dry-run(무료: 프롬프트만)
#   ./run_pipeline.sh --business my.yaml --days 30
#   ./run_pipeline.sh --live                  # 실제 생성(💳 토큰 비용) + 규제 자동 검출
#
# ⚠️ --live 는 ANTHROPIC_API_KEY 필요(비용 발생). 키 없으면 generate 단계에서 안전 중단.
set -euo pipefail
cd "$(dirname "$0")"

BUSINESS="business.example.yaml"
DAYS=30
LIVE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --business) BUSINESS="$2"; shift 2 ;;
    --days) DAYS="$2"; shift 2 ;;
    --live) LIVE="--live"; shift ;;
    *) echo "알 수 없는 옵션: $1"; exit 1 ;;
  esac
done

CAL="content_calendar.generated.yaml"

echo "▶ 1/3 캘린더 생성 ($BUSINESS · ${DAYS}일)"
python3 build_calendar.py --business "$BUSINESS" --days "$DAYS" --out "$CAL"

echo "▶ 2/3 콘텐츠 생성 ${LIVE:-(dry-run·무료)}"
python3 generate_content.py --calendar "$CAL" $LIVE

echo "▶ 3/3 규제 자동 검출 (HIGH 위반 차단)"
if ls output/*.md >/dev/null 2>&1; then
  if python3 compliance_check.py output --strict; then
    echo "✅ 규제 검출 통과"
  else
    echo "⛔ HIGH 위반 발견 — 발행 전 수정 필요. (위 목록 참고)"
    echo "   그래도 파이프라인은 초안을 남겼습니다: output/"
  fi
else
  echo "ℹ dry-run 이라 검출할 발행 콘텐츠(.md)가 없습니다. --live 시 자동 검출됩니다."
fi

echo ""
echo "다음 단계: review.html 로 승인 → publish.py → 발행"
echo "완료."
