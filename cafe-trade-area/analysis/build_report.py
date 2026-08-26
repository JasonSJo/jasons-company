#!/usr/bin/env python3
"""
카페 프랜차이즈 상권 분석 — 후보지별 상권조사 리포트 생성

가맹 희망자·투자 심의에 그대로 제출할 수 있는 형태의 상권조사 리포트를
후보지마다 한 파일씩 만든다. 점수·매출·손익은 common.py 의 같은 모델을 쓰므로
score_sites.py / estimate_revenue.py 결과와 어긋나지 않는다. API 비용 없음.

사용법:
  python build_report.py
  python build_report.py --site "판교" --outdir output/reports
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import yaml

from common import WEIGHTS, analyze, haversine, n1, nf, read_csv, to_f, to_i, write_text

ROOT = Path(__file__).resolve().parent


def n1_3(v) -> str:
    """소수 셋째 자리까지, 꼬리 0 은 떼고 — JS Number 표기와 맞춘다."""
    return (f"{nf(v, 3)}".rstrip("0").rstrip(".")) or "0"


def nearby(site: dict, pois: list[dict], radius: float, kind: str) -> list[tuple[float, dict]]:
    lat, lon = to_f(site.get("위도")), to_f(site.get("경도"))
    if not lat or not lon:
        return []
    out = []
    for p in pois:
        if str(p.get("분류", "")).strip() != kind:
            continue
        plat, plon = to_f(p.get("위도")), to_f(p.get("경도"))
        if not plat or not plon:
            continue
        d = haversine(lat, lon, plat, plon)
        if d <= radius:
            out.append((d, p))
    return sorted(out, key=lambda x: x[0])


def verdict(r: dict) -> tuple[str, str]:
    """점수만으로 결론 내지 않는다 — 손익이 안 나오면 등급이 높아도 반려다."""
    p = r["손익"]
    if p["투자회수_개월"] is None or p["BEP달성률"] < 1.0:
        return "반려", "추정 손익 기준 적자 구간입니다. 임대조건 재협상 또는 후보 제외를 권고합니다."
    if r["등급"] == "A" and p["투자회수_개월"] <= 30:
        return "출점 추천", "상권·손익 모두 기준을 충족합니다. 계약 조건 확정 후 진행하십시오."
    if p["투자회수_개월"] <= 36 and r["총점"] >= 65:
        return "조건부 추천", "임대조건·초기투자 축소를 전제로 진행 가능합니다."
    return "보류", "회수기간 또는 상권 점수가 기준에 미달합니다. 조건 개선 시 재심의하십시오."


def render(r: dict, site: dict, pois: list[dict], brand: dict, today: str = "") -> str:
    radius = to_f(brand.get("반경_m"), 500)
    p, rev, c = r["손익"], r["매출추정"], r["경쟁"]
    v, v_note = verdict(r)

    L = [f"# 상권조사 리포트 — {r['후보지명']}", "",
         f"| | |", "|---|---|",
         f"| 브랜드 | {brand.get('브랜드', '—')} |",
         f"| 주소 | {r['주소'] or '—'} |",
         f"| 조사 반경 | {nf(radius)}m |",
         f"| 조사일 | {today or date.today().isoformat()} |",
         f"| 종합점수 | **{n1(r['총점'])} / 100 ({r['등급']}등급 · {r['등급설명']})** |",
         f"| 결론 | **{v}** |", "",
         f"> {v_note}", "",
         "## 1. 점수 요약", "",
         "| 항목 | 배점 | 획득 | 근거 |", "|---|---:|---:|---|"]
    for (k, w), why in zip(WEIGHTS.items(), r["근거"]):
        L.append(f"| {k} | {w} | {n1(r['항목'][k])} | {why} |")
    L.append(f"| **합계** | **100** | **{n1(r['총점'])}** | |")

    L += ["", "## 2. 배후수요", "",
          f"- 주거인구 {to_i(site.get('주거인구_500m')):,}명 · "
          f"아파트 {to_i(site.get('아파트세대수')):,}세대",
          f"- 직장인구 {to_i(site.get('직장인구_500m')):,}명 · "
          f"오피스빌딩 {to_i(site.get('오피스빌딩수')):,}개",
          f"- 대학·학원 {to_i(site.get('대학_학원수')):,}개",
          f"- 유동인구 일평균 {to_i(site.get('유동인구_일평균')):,}명"]
    stn = (site.get("지하철역명") or "").strip()
    if stn:
        L.append(f"- 최근접역 **{stn}** 도보 {nf(to_f(site.get('지하철_도보분')))}분 · "
                 f"일평균 승하차 {to_i(site.get('지하철_일평균승하차')):,}명")

    L += ["", "## 3. 경쟁 현황", "",
          f"반경 {nf(radius)}m 내 카페 **{c['카페수']}곳** — "
          f"동일포지션(저가·테이크아웃) {c['동일포지션']}곳, 앵커 브랜드 {c['앵커브랜드']}곳.", ""]
    cafes = nearby(site, pois, radius, "카페")
    if cafes:
        L += ["| 거리 | 상호 | 브랜드 |", "|---:|---|---|"]
        L += [f"| {nf(d)}m | {q.get('상호', '')} | {q.get('브랜드', '')} |" for d, q in cafes[:15]]
        if len(cafes) > 15:
            L.append(f"| … | 외 {len(cafes) - 15}곳 | |")
        if len(cafes) < c["카페수"]:
            L += ["", f"> 좌표가 확보된 곳만 표에 나옵니다. 현장 조사 기준 총 {c['카페수']}곳으로 "
                      f"계산했습니다 (경쟁 과소평가 방지)."]
    else:
        L.append("> 좌표 기반 POI 가 없어 현장 조사 수치로만 계산했습니다. "
                 "`collect_pois.py --live` 로 실제 목록을 수집하면 이 표가 채워집니다.")
    if c["자사점_최근접_m"] is not None:
        L += ["", f"- 자사 기존점 최근접 거리 **{c['자사점_최근접_m']:,}m**"
                  + (" ⚠ 자기잠식 검토 필요" if c["자사점_최근접_m"] < 500 else "")]

    L += ["", "## 4. 입지·접근성", "",
          f"- {to_i(site.get('층'), 1)}층 · 전용 {nf(to_f(site.get('전용면적_평')))}평 · "
          f"전면 {nf(to_f(site.get('전면길이_m')))}m · "
          f"코너 {'O' if str(site.get('코너여부', '')).upper().startswith(('Y', 'O')) else 'X'} · "
          f"주차 {to_i(site.get('주차가능대수'))}대 · 좌석 {to_i(site.get('좌석수'))}석",
          f"- 보증금 {nf(to_f(site.get('보증금_만원')))}만 · "
          f"월임대료 {nf(to_f(site.get('월임대료_만원')))}만 · "
          f"관리비 {nf(to_f(site.get('관리비_만원')))}만 · "
          f"권리금 {nf(to_f(site.get('권리금_만원')))}만",
          "", "## 5. 매출 추정", "",
          "추정 근거는 **상권 총 카페수요 × 자사 점유율** 입니다. "
          "유동인구에 유입률을 한 번 곱하는 방식은 유동에 이미 포함된 직장·주거 인구를 "
          "중복 계산해 매출을 과대추정하므로 쓰지 않았습니다.", "",
          f"| 단계 | 값 |", "|---|---:|",
          f"| 상권 하루 카페 이용객(추정) | {nf(rev['상권수요_일객수'])}명 |",
          f"| 반경 내 카페 수 | {rev['경쟁카페수']}곳 |",
          f"| 입지 배수(접근성 반영) | ×{n1_3(rev['입지배수'])} |",
          f"| **자사 점유율** | **{nf(rev['점유율'] * 100, 2)}%** |",
          f"| 하루 객수(추정) | {nf(rev['일객수_추정'])}명 |",
          f"| 객단가 | {rev['객단가_원']:,}원 |",
          f"| **월 매출(추정)** | **{nf(p['월매출_만원'])}만원** |"]
    if rev["좌석제약"]:
        L += ["", f"> 좌석 처리능력({nf(rev['좌석상한_일객수'])}명/일)이 상한으로 작동했습니다. "
                  f"테이크아웃 동선 강화 또는 좌석 확충 시 상향 여지가 있습니다."]

    L += ["", "## 6. 추정 손익 (월)", "",
          "| 항목 | 금액(만원) |", "|---|---:|",
          f"| 매출 | {nf(p['월매출_만원'])} |",
          f"| 변동비 ({nf(p['변동비율'] * 100, 1)}%) | −{nf(p['변동비_만원'])} |",
          f"| 인건비 | −{nf(p['인건비_만원'])} |",
          f"| 임대료·관리비 | −{nf(p['임대료_만원'])} |",
          f"| 기타 고정비 | −{nf(p['고정비_만원'] - p['인건비_만원'] - p['임대료_만원'])} |",
          f"| **영업이익** | **{nf(p['영업이익_만원'])} ({nf(p['영업이익률'] * 100, 1)}%)** |", "",
          f"- 손익분기 월매출 **{'도달 불가' if p['BEP월매출_만원'] is None else format(p['BEP월매출_만원'], ',.0f')}"
          f"{'' if p['BEP월매출_만원'] is None else '만원'}** "
          f"(현재 추정 대비 {nf(p['BEP달성률'] * 100)}%)",
          f"- 초기투자 **{nf(p['초기투자_만원'])}만원** "
          f"(보증금 {nf(p['보증금_만원'])}만 회수분 제외 시 {nf(p['회수대상투자_만원'])}만원)",
          f"- 투자회수 **{'—' if p['투자회수_개월'] is None else n1(p['투자회수_개월'])}개월**"]

    L += ["", "## 7. 리스크", ""]
    L += [f"- {x}" for x in r["리스크"]] or ["- 특이 리스크 없음"]

    L += ["", "## 8. 결론", "",
          f"**{v}** — {v_note}", "",
          "---", "",
          "※ 본 리포트의 매출·손익은 공개 지표와 규칙 기반 모델에 의한 **추정치**이며, "
          "실제 매출을 보장하지 않습니다. 가맹 계약 전 반드시 현장 실사와 "
          "가맹사업법상 정보공개서를 함께 검토하십시오."]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="후보지별 상권조사 리포트 생성")
    ap.add_argument("--sites", default=str(ROOT / "후보지.example.csv"))
    ap.add_argument("--pois", default=str(ROOT / "pois.example.csv"))
    ap.add_argument("--brand", default=str(ROOT / "brand.example.yaml"))
    ap.add_argument("--site", default="", help="후보지명(부분일치). 생략하면 전체")
    ap.add_argument("--outdir", default=str(ROOT / "output" / "reports"))
    args = ap.parse_args()

    sites = read_csv(Path(args.sites))
    if args.site:
        sites = [s for s in sites if args.site in (s.get("후보지명") or "")]
    pois_path = Path(args.pois)
    pois = read_csv(pois_path) if pois_path.exists() else []
    bpath = Path(args.brand)
    brand = (yaml.safe_load(bpath.read_text(encoding="utf-8")) or {}) if bpath.exists() else {}

    outdir = Path(args.outdir)
    made = []
    for s in sites:
        name = (s.get("후보지명") or "").strip()
        if not name:
            continue
        r = analyze(s, pois, brand)
        safe = name.replace("/", "-").replace(" ", "_")
        path = write_text(outdir / f"상권조사_{safe}.md", render(r, s, pois, brand))
        made.append((r, path))

    print(f"리포트 {len(made)}건 → {outdir}")
    for r, path in made:
        print(f"  · [{r['등급']}] {r['후보지명']:<16} {verdict(r)[0]:<8} {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
