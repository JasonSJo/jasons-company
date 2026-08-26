#!/usr/bin/env bash
# 카페 프랜차이즈 상권 분석 — 전체 파이프라인 한 번에
#
#   POI 수집 → 후보지 점수화 → 손익 시뮬레이션 → 후보지별 상권조사 리포트
#
# 기본은 dry-run(무료·네트워크 없음)이다. --live 를 붙일 때만 카카오 로컬 API 를
# 호출하며, 이때 KAKAO_REST_KEY 가 필요하다.
#
#   ./run_all.sh                                   # 예시 데이터로 전 과정 확인(무료)
#   ./run_all.sh --sites 내후보지.csv               # 내 데이터로
#   ./run_all.sh --live --sites 내후보지.csv        # 실제 POI 수집까지
set -euo pipefail
cd "$(dirname "$0")"

SITES="후보지.example.csv"
BRAND="brand.example.yaml"
RADIUS=500
LIVE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sites)  SITES="$2"; shift 2 ;;
    --brand)  BRAND="$2"; shift 2 ;;
    --radius) RADIUS="$2"; shift 2 ;;
    --live)   LIVE="--live"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
  esac
done

PY="${PYTHON:-python3}"
POIS="output/pois.csv"

echo "════════════════════════════════════════════"
echo " 상권 분석 파이프라인  (후보지: $SITES)"
[[ -n "$LIVE" ]] && echo " ⚠ --live: 카카오 로컬 API 를 실제 호출합니다 (쿼터 소모)"
echo "════════════════════════════════════════════"

echo -e "\n[1/4] POI 수집"
"$PY" collect_pois.py --sites "$SITES" --out "$POIS" --radius "$RADIUS" $LIVE

echo -e "\n[2/4] 후보지 점수화"
"$PY" score_sites.py --sites "$SITES" --pois "$POIS" --brand "$BRAND"

echo -e "\n[3/4] 손익 시뮬레이션"
"$PY" estimate_revenue.py --sites "$SITES" --pois "$POIS" --brand "$BRAND"

echo -e "\n[4/4] 상권조사 리포트"
"$PY" build_report.py --sites "$SITES" --pois "$POIS" --brand "$BRAND"

echo -e "\n✅ 완료 — output/ 을 확인하세요"
echo "   · output/상권_후보지_순위.md      순위·등급 한눈에"
echo "   · output/손익_시뮬레이션.md       매출·손익·민감도"
echo "   · output/reports/                후보지별 제출용 리포트"
echo
echo "사람이 해야 할 일: 현장 실사(주차·동선·간판 가시성) · 임대조건 협상 · 최종 출점 결정"
