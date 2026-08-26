#!/usr/bin/env python3
"""
카페 프랜차이즈 상권 분석 — 반경 내 경쟁·시설 POI 수집

후보지 CSV 의 좌표를 돌면서 반경 안의 카페(CE7)·지하철(SW8)·학교(SC4) 등을
카카오 로컬 API 로 수집해 pois.csv 로 저장한다.

  dry-run (기본, 무료·네트워크 없음) : pois.example.csv 를 그대로 복사해 형식만 확인
  --live                              : 실제 API 호출 (KAKAO_REST_KEY 필요)

카카오 로컬 API 는 개인 개발자 기준 무료 쿼터가 있으나, 쿼터 초과 시 과금될 수
있으므로 --live 는 사람이 명시적으로 붙일 때만 동작한다.

준비:
  1) https://developers.kakao.com 에서 앱 생성 → REST API 키 발급
  2) export KAKAO_REST_KEY="발급받은키"

사용법:
  python collect_pois.py                                   # dry-run
  python collect_pois.py --live --radius 500
  python collect_pois.py --live --sites 내후보지.csv --out output/pois.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from common import read_csv, to_f

ROOT = Path(__file__).resolve().parent
API = "https://dapi.kakao.com/v2/local/search/category.json"

# 카카오 카테고리 그룹 → 이 시스템의 '분류'
CATEGORIES = {"CE7": "카페", "SW8": "지하철", "SC4": "학교", "HP8": "병원", "MT1": "마트"}
HEADER = ["상호", "분류", "브랜드", "위도", "경도", "비고"]

# 상호에서 브랜드를 뽑기 위한 사전 — common.RIVAL/ANCHOR 판정에 쓰인다
BRANDS = ["스타벅스", "투썸", "커피빈", "블루보틀", "폴바셋", "메가", "컴포즈",
          "빽다방", "더벤티", "감성커피", "매머드", "이디야", "할리스", "파리바게뜨"]


def brand_of(name: str) -> str:
    for b in BRANDS:
        if b in name:
            return b
    return "개인"


def fetch_category(key: str, code: str, lat: float, lon: float, radius: int) -> list[dict]:
    """한 카테고리를 페이지 끝까지 긁는다(최대 3페이지·45건 — 반경 500m 면 충분)."""
    out, page = [], 1
    while page <= 3:
        q = urllib.parse.urlencode({
            "category_group_code": code, "x": f"{lon}", "y": f"{lat}",
            "radius": int(radius), "page": page, "size": 15, "sort": "distance",
        })
        req = urllib.request.Request(f"{API}?{q}", headers={"Authorization": f"KakaoAK {key}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"  ! API 오류 {e.code} ({code}) — 키/쿼터를 확인하세요", file=sys.stderr)
            break
        except OSError as e:
            print(f"  ! 네트워크 오류 ({code}): {e}", file=sys.stderr)
            break
        out += data.get("documents", [])
        if data.get("meta", {}).get("is_end", True):
            break
        page += 1
        time.sleep(0.2)   # 초당 호출 제한 여유
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="반경 내 경쟁·시설 POI 수집")
    ap.add_argument("--sites", default=str(ROOT / "후보지.example.csv"))
    ap.add_argument("--out", default=str(ROOT / "output" / "pois.csv"))
    ap.add_argument("--radius", type=int, default=500)
    ap.add_argument("--live", action="store_true", help="실제 카카오 API 호출(키 필요)")
    args = ap.parse_args()

    sites_path = Path(args.sites)
    if not sites_path.exists():
        print(f"후보지 CSV 를 찾을 수 없습니다: {sites_path}", file=sys.stderr)
        return 1
    sites = read_csv(sites_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.live:
        sample = ROOT / "pois.example.csv"
        rows = read_csv(sample) if sample.exists() else []
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEADER)
            w.writeheader()
            w.writerows([{k: r.get(k, "") for k in HEADER} for r in rows])
        print(f"[dry-run] 예시 POI {len(rows)}건을 {out_path} 로 복사했습니다. (API 호출 없음·무료)")
        print("          실제 수집: KAKAO_REST_KEY 설정 후 --live 를 붙이세요.")
        return 0

    key = os.environ.get("KAKAO_REST_KEY", "").strip()
    if not key:
        print("KAKAO_REST_KEY 환경변수가 없습니다. export KAKAO_REST_KEY=... 후 다시 실행하세요.",
              file=sys.stderr)
        return 1

    seen, rows = set(), []
    for s in sites:
        lat, lon = to_f(s.get("위도")), to_f(s.get("경도"))
        name = (s.get("후보지명") or "").strip()
        if not lat or not lon:
            print(f"  - 좌표 없음, 건너뜀: {name}")
            continue
        print(f"  · {name} 반경 {args.radius}m 수집 중…")
        for code, kind in CATEGORIES.items():
            for d in fetch_category(key, code, lat, lon, args.radius):
                pid = d.get("id")
                if pid in seen:
                    continue
                seen.add(pid)
                place = d.get("place_name", "")
                rows.append({
                    "상호": place, "분류": kind, "브랜드": brand_of(place) if kind == "카페" else "",
                    "위도": d.get("y", ""), "경도": d.get("x", ""),
                    "비고": d.get("road_address_name") or d.get("address_name") or "",
                })

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    print(f"\n✅ POI {len(rows)}건 → {out_path}")
    print("   자사 기존점은 분류를 '자사점' 으로 직접 추가해야 자기잠식 경고가 동작합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
