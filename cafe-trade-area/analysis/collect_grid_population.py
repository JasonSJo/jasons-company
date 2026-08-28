#!/usr/bin/env python3
"""
격자 인구 수집 (통계청 SGIS · 전국)

M2 의 배후 수요 H(세대수)·W(직장인구)는 격자인구.csv 에서 온다. 지금까지 이 파일은
사람이 준비해야 했고, 그래서 **전국 어디든 후보지를 넣기 전에 손작업이 하나 있었다.**
SGIS 는 전국 격자 센서스를 무료 API 로 준다. 여기를 이으면 그 손작업이 사라진다.

  python3 collect_grid_population.py --sites 후보지.csv                 # dry-run
  SGIS_KEY=... SGIS_SECRET=... python3 collect_grid_population.py --live

유동인구와 달리 **추정이 아니다.** 거주·사업체는 등록 데이터라 기지국 신호처럼
'있었을 것' 을 세는 값이 아니다. 그래서 M2 도 이 값에는 대용 경고를 붙이지 않는다.
전국 어디서나 같은 방식으로 나오므로 지역 편차 걱정도 없다.

확인한 것과 아직 못 한 것을 갈라 둔다.

  ✅ 인증  consumer_key/secret → result.accessToken (문서로 확인)
  ❓ 조회  SGIS 통계 API 는 좌표 사각형이 아니라 **adm_cd(행정구역코드) + year** 로
          부르는 형태다(household.json → household_cnt, company.json → 종사자수).
          격자 단위 상품이 따로 있는지는 이 환경에서 문서를 열 수 없어 확정하지
          못했다. 처음 세운 bbox 가정은 틀렸을 가능성이 높다.

  그래서 추측으로 코드를 더 쌓는 대신 **--probe** 를 뒀다. 키가 있는 곳에서 한 번
  돌리면 후보 엔드포인트를 하나씩 눌러 보고 무엇이 답하는지, 응답 필드가 무엇인지
  그대로 출력한다. 그 출력이 연동을 확정하는 근거다.

      SGIS_KEY=... SGIS_SECRET=... python3 collect_grid_population.py --probe

⚠ dry-run 은 인구 수를 지어내지 않는다 (빈 표만 만든다).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# 구역코드→면적·중심점 표는 유동인구 쪽과 같은 형식이다. 구현을 둘로 두면
# 한쪽만 고쳐져 같은 CSV 가 두 도구에서 다르게 읽히는 일이 생긴다.
from collect_carrier_flow import load_areas
from common import read_csv, to_f

ROOT = Path(__file__).resolve().parent

# 인증은 문서로 확인했다: consumer_key/secret → result.accessToken
AUTH_URL = "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json"

# 자료 조회는 아직 확인 중이다. SGIS 통계 API 는 좌표 사각형이 아니라
# **adm_cd(행정구역코드) + year** 로 부르는 형태이고(household.json 은 household_cnt 를,
# population.json 은 population 을 준다), 격자 단위 상품이 따로 있는지는 문서를
# 열지 못해 확정하지 못했다. 그래서 후보 엔드포인트를 여러 개 두고 --probe 로
# 실제 키를 써서 어느 것이 답하는지 한 번에 알아본다.
DATA_URL = "https://sgisapi.kostat.go.kr/OpenAPI3/stats/household.json"

# ── KOSIS (국가통계포털) ──────────────────────────────
# SGIS 와 같은 자리를 채우는 두 번째 길. 전국·무료이고 주민등록인구와
# 전국사업체조사(종사자수)가 있다. 어려운 것은 호출이 아니라 **어느 통계표(tblId)를
# 쓸지 고르는 것**이라, 목록 조회를 probe 에 넣어 눈으로 고르게 한다.
KOSIS_LIST_URL = "https://kosis.kr/openapi/statisticsList.do"
KOSIS_DATA_URL = "https://kosis.kr/openapi/statisticsData.do"

# 목록에서 훑어볼 분류. vwCd=MT_ZTITLE 는 주제별 목록이다.
KOSIS_LIST_PROBES = [
    ("주제별 최상위", {"vwCd": "MT_ZTITLE", "parentListId": "A"}),
    ("인구·가구", {"vwCd": "MT_ZTITLE", "parentListId": "A_1"}),
    ("사업체", {"vwCd": "MT_ZTITLE", "parentListId": "F_29"}),
]

CANDIDATES = [
    ("가구(행정동)", "https://sgisapi.kostat.go.kr/OpenAPI3/stats/household.json",
     "adm_cd", "household_cnt 세대수"),
    ("인구(행정동)", "https://sgisapi.kostat.go.kr/OpenAPI3/stats/population.json",
     "adm_cd", "population 총인구"),
    ("인구 검색", "https://sgisapi.kostat.go.kr/OpenAPI3/stats/searchpopulation.json",
     "adm_cd", "population · avg_age"),
    ("사업체(행정동)", "https://sgisapi.kostat.go.kr/OpenAPI3/stats/company.json",
     "adm_cd", "종사자수 = W 후보"),
    ("행정구역 단계", "https://sgisapi.kostat.go.kr/OpenAPI3/addr/stage.json",
     "none", "adm_cd 목록 — 좌표→코드 변환의 출발점"),
    ("창업 인구요약", "https://sgisapi.kostat.go.kr/OpenAPI3/startupbiz/pplsummary.json",
     "bbox", "격자/영역 인구 (형식 미확인)"),
]

# M2 가 먹는 격자인구.csv 열
HEADER = ["격자ID", "중심위도", "중심경도", "한변_m", "세대수", "직장인구"]

# 응답 표기가 바뀌어도 하나만 맞으면 읽힌다
FIELDS = {
    "격자ID": ["grid_id", "GRID_ID", "격자ID", "cell_id"],
    "위도": ["lat", "y", "중심위도", "point_y"],
    "경도": ["lon", "lng", "x", "중심경도", "point_x"],
    "세대수": ["hshld_cnt", "household_cnt", "세대수", "hh_cnt", "ho_cnt"],
    "직장인구": ["corp_worker_cnt", "worker_cnt", "직장인구", "employee_cnt", "tot_worker"],
    "한변": ["grid_size", "한변_m", "cell_size"],
}

# 후보지 반경 몇 m 까지 격자를 받을지. P10(도보 10분 ≈ 667m)을 덮어야 M2 의
# 면적 가중 교차가 성립한다. 넉넉히 잡되 요청 수가 폭발하지 않게.
DEFAULT_RADIUS = 800.0


def pick(item: dict, names: list[str]) -> str:
    for n in names:
        if n in item and str(item[n]).strip() != "":
            return str(item[n]).strip()
    return ""


def bbox(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """후보지 주변 사각형. 위도 1도 ≈ 111km, 경도는 위도에 따라 줄어든다."""
    dlat = radius_m / 111_000.0
    dlon = radius_m / (111_000.0 * max(0.1, math.cos(math.radians(lat))))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def sites_bboxes(sites: list[dict], radius: float) -> list[dict]:
    """후보지마다 조회 영역 하나. 좌표가 없는 후보지는 건너뛴다 —
    주소만으로는 격자를 고를 수 없고, 추측한 좌표로 받은 인구는 근거가 아니다."""
    out = []
    for s in sites:
        lat, lon = to_f(s.get("위도")), to_f(s.get("경도"))
        name = str(s.get("후보지명", "")).strip()
        if not (lat and lon):
            continue
        y1, x1, y2, x2 = bbox(lat, lon, radius)
        out.append({"이름": name, "위도": lat, "경도": lon,
                    "minx": x1, "miny": y1, "maxx": x2, "maxy": y2})
    return out


def get_token(key: str, secret: str, url: str = AUTH_URL) -> tuple[str, str]:
    q = urllib.parse.urlencode({"consumer_key": key, "consumer_secret": secret})
    try:
        with urllib.request.urlopen(f"{url}?{q}", timeout=20,
                                    context=ssl.create_default_context()) as r:
            doc = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return "", f"HTTP {e.code}"
    except (OSError, ValueError) as e:
        return "", f"{type(e).__name__}: {e}"
    tok = ((doc.get("result") or {}).get("accessToken") or "").strip()
    if not tok:
        return "", f"토큰이 없습니다: {json.dumps(doc, ensure_ascii=False)[:300]}"
    return tok, ""


def fetch_grid(token: str, box: dict, url: str = DATA_URL) -> tuple[list, str]:
    q = urllib.parse.urlencode({
        "accessToken": token,
        "minx": box["minx"], "miny": box["miny"],
        "maxx": box["maxx"], "maxy": box["maxy"],
    })
    try:
        with urllib.request.urlopen(f"{url}?{q}", timeout=25,
                                    context=ssl.create_default_context()) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return [], f"HTTP {e.code}"
    except OSError as e:
        return [], f"네트워크 오류: {e}"
    try:
        doc = json.loads(body)
    except ValueError as e:
        return [], f"JSON 파싱 실패: {e} · 응답 앞부분: {body[:300]}"
    if str(doc.get("errCd", "0")) not in ("0", "None", ""):
        return [], f"errCd {doc.get('errCd')} {doc.get('errMsg', '')}"
    rows = doc.get("result")
    if not isinstance(rows, list):
        return [], f"예상한 형태가 아닙니다: {json.dumps(doc, ensure_ascii=False)[:300]}"
    return rows, ""


def to_rows(records: list, 한변: float = 100.0) -> tuple[list[dict], dict]:
    """SGIS 응답 → 격자인구 행. 좌표나 인구를 못 읽은 격자는 만들지 않는다."""
    out, 버림 = [], {"좌표없음": 0, "인구없음": 0}
    for r in records:
        if not isinstance(r, dict):
            continue
        lat, lon = to_f(pick(r, FIELDS["위도"])), to_f(pick(r, FIELDS["경도"]))
        if not (33.0 <= lat <= 39.0 and 124.0 <= lon <= 132.0):
            버림["좌표없음"] += 1
            continue
        h = to_f(pick(r, FIELDS["세대수"]))
        w = to_f(pick(r, FIELDS["직장인구"]))
        if h <= 0 and w <= 0:
            # 사람도 일자리도 없는 격자는 M2 에 넣어 봐야 0 을 더할 뿐이다
            버림["인구없음"] += 1
            continue
        gid = pick(r, FIELDS["격자ID"]) or f"G{round(lat * 10000)}_{round(lon * 10000)}"
        out.append({
            "격자ID": gid,
            "중심위도": round(lat, 6), "중심경도": round(lon, 6),
            "한변_m": to_f(pick(r, FIELDS["한변"])) or 한변,
            "세대수": round(h, 1), "직장인구": round(w, 1),
        })
    return out, 버림


def dedupe(rows: list[dict]) -> tuple[list[dict], int]:
    """후보지 조회 영역이 겹치면 같은 격자가 여러 번 온다. 그대로 두면 H·W 가
    겹친 만큼 부풀어 그 후보지의 배후 수요가 근거 없이 커진다."""
    본것, out, 중복 = set(), [], 0
    for r in rows:
        if r["격자ID"] in 본것:
            중복 += 1
            continue
        본것.add(r["격자ID"])
        out.append(r)
    return out, 중복


def write_rows(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in HEADER} for r in rows])
    return path


def _probe_one(token: str, url: str, params: dict, timeout: int = 20) -> dict:
    """엔드포인트 하나를 눌러 보고 결과를 그대로 담아 온다. 판단은 사람이 한다."""
    q = urllib.parse.urlencode({**params, "accessToken": token})
    full = f"{url}?{q}"
    try:
        with urllib.request.urlopen(full, timeout=timeout,
                                    context=ssl.create_default_context()) as r:
            body = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "말": f"HTTP {e.code}"}
    except OSError as e:
        return {"ok": False, "status": 0, "말": f"{type(e).__name__}: {e}"}

    try:
        doc = json.loads(body)
    except ValueError:
        return {"ok": False, "status": status, "말": "JSON 이 아님",
                "앞부분": body[:300]}

    errcd = str(doc.get("errCd", "0"))
    if errcd not in ("0", "None", ""):
        return {"ok": False, "status": status,
                "말": f"errCd {errcd} {doc.get('errMsg', '')}"}

    res = doc.get("result")
    첫 = None
    if isinstance(res, list) and res:
        첫 = res[0]
    elif isinstance(res, dict):
        첫 = res
    return {"ok": True, "status": status, "말": "응답 있음",
            "건수": len(res) if isinstance(res, list) else 1,
            "필드": sorted(첫)[:25] if isinstance(첫, dict) else None,
            "표본": json.dumps(첫, ensure_ascii=False)[:400] if 첫 else "",
            "앞부분": body[:300] if 첫 is None else ""}


def probe(key: str, secret: str, auth_url: str, adm_cd: str, year: str,
          box: dict = None) -> int:
    """키를 가지고 실제로 눌러 보고, 무엇이 답하는지 그대로 출력한다.

    SGIS 문서를 이 환경에서 열 수 없어 자료 엔드포인트를 확정하지 못했다. 추측으로
    코드를 더 쌓는 대신, 키가 있는 곳에서 한 번 돌리면 진실이 나오게 만든다.
    이 출력을 그대로 붙여 주면 연동을 정확히 맞출 수 있다.
    """
    if not (key and secret):
        print("SGIS_KEY / SGIS_SECRET 이 필요합니다.", file=sys.stderr)
        print("  발급: sgis.kostat.go.kr → 개발지원센터 → 오픈API → 인증키 신청",
              file=sys.stderr)
        return 2

    print("SGIS 연동 점검")
    print(f"  인증  {auth_url}")
    token, err = get_token(key, secret, auth_url)
    if err:
        print(f"  ✕ 토큰 발급 실패 — {err}")
        print("\n키가 맞는지, 승인이 끝났는지 확인하십시오. 신청 직후에는 "
              "승인까지 시간이 걸릴 수 있습니다.")
        return 1
    print(f"  ✓ 토큰 발급됨 ({len(token)}자)")

    print("\n후보 엔드포인트를 하나씩 눌러 봅니다. 이 표가 연동을 확정하는 근거입니다.")
    작동 = []
    for 이름, url, kind, 설명 in CANDIDATES:
        if kind == "adm_cd":
            params = {"adm_cd": adm_cd, "year": year}
        elif kind == "bbox" and box:
            params = {"minx": box["minx"], "miny": box["miny"],
                      "maxx": box["maxx"], "maxy": box["maxy"]}
        elif kind == "bbox":
            params = {}
        else:
            params = {}
        got = _probe_one(token, url, params)
        mark = "✓" if got["ok"] else "✕"
        print(f"\n{mark} {이름}  ({설명})")
        print(f"   {url}")
        if params:
            print(f"   파라미터 {params}")
        print(f"   → {got['말']}")
        if got.get("필드"):
            print(f"   필드 {got['필드']}")
        if got.get("표본"):
            print(f"   표본 {got['표본']}")
        if got.get("앞부분"):
            print(f"   응답 앞부분 {got['앞부분']}")
        if got["ok"]:
            작동.append(이름)

    print("\n" + "─" * 60)
    if 작동:
        print(f"응답한 엔드포인트: {', '.join(작동)}")
        print("이 출력을 그대로 전달해 주시면 FIELDS 와 DATA_URL 을 정확히 맞추겠습니다.")
        print("특히 볼 것: 세대수(household_cnt)와 직장인구(종사자수)에 해당하는 "
              "필드명, 그리고 좌표나 격자 단위가 있는지.")
    else:
        print("응답한 엔드포인트가 없습니다. 인증은 됐으므로 키 문제는 아니고, "
              "주소나 파라미터가 다릅니다.")
        print("SGIS 개발지원센터의 '데이터 API' 문서에서 실제 주소를 확인해 "
              "--data-url 로 넣어 주십시오.")
    return 0 if 작동 else 1


def kosis_fetch(api_key: str, org_id: str, tbl_id: str, itm_id: str,
                obj_l1: str, prd_se: str, prd_de: str,
                url: str = KOSIS_DATA_URL) -> tuple[list, str]:
    """KOSIS 자료 조회. 표를 고르는 것은 사람이 하고(--probe), 여기서는 받아만 온다.

    통계표마다 항목(itmId)과 분류(objL1)가 달라 상수로 박을 수 없다. 그래서 전부
    인자로 받는다 — probe 로 표를 고른 뒤 플래그만 바꿔 부르면 코드는 그대로다.
    """
    q = urllib.parse.urlencode({
        "method": "getList", "apiKey": api_key, "format": "json", "jsonVD": "Y",
        "orgId": org_id, "tblId": tbl_id,
        "itmId": itm_id or "ALL", "objL1": obj_l1 or "ALL",
        "prdSe": prd_se, **({"startPrdDe": prd_de, "endPrdDe": prd_de} if prd_de
                            else {"newEstPrdCnt": "1"}),
    })
    try:
        with urllib.request.urlopen(f"{url}?{q}", timeout=30,
                                    context=ssl.create_default_context()) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return [], f"HTTP {e.code}"
    except OSError as e:
        return [], f"네트워크 오류: {e}"
    try:
        doc = json.loads(body)
    except ValueError as e:
        return [], f"JSON 파싱 실패: {e} · 응답 앞부분: {body[:300]}"
    # KOSIS 는 오류도 HTTP 200 + JSON 으로 보낸다
    if isinstance(doc, dict) and doc.get("errMsg"):
        return [], f"{doc.get('err')} {doc.get('errMsg')}"
    rows = doc if isinstance(doc, list) else doc.get("result") or []
    if not rows:
        return [], f"자료가 비었습니다: {json.dumps(doc, ensure_ascii=False)[:300]}"
    return rows, ""


# KOSIS 응답의 흔한 표기. 통계표마다 다르므로 여러 개를 함께 받는다.
KOSIS_FIELDS = {
    "코드": ["C1", "C1_OBJ_NM_ENG", "objL1", "C1_OBJ_NM"],
    "이름": ["C1_NM", "C1_OBJ_NM", "PRD_DE"],
    "값": ["DT", "dt", "값"],
    "단위": ["UNIT_NM", "unit"],
    "시점": ["PRD_DE", "prdDe"],
}


def kosis_to_cells(rows: list, areas: dict, 항목: str) -> tuple[list[dict], dict]:
    """KOSIS 행 → 격자인구.csv 행. 구역 면적·중심점 표(--areas)가 있어야 한다.

    KOSIS 는 행정구역 코드와 값만 주고 좌표도 면적도 주지 않는다. M2 는 둘 다
    필요하다(중심점으로 P10 과 겹치는지 보고, 면적으로 안분한다). 그래서 표가 없는
    구역은 행을 만들지 않는다 — 면적을 추측해 나눈 값은 근거가 아니다.

    항목 은 이 표가 무엇을 담는지 — "세대수" 또는 "직장인구".
    """
    out, 버림 = [], {"코드없음": 0, "값없음": 0, "면적없음": 0}
    for r in rows:
        if not isinstance(r, dict):
            continue
        code = pick(r, KOSIS_FIELDS["코드"])
        if not code:
            버림["코드없음"] += 1
            continue
        n = to_f(pick(r, KOSIS_FIELDS["값"]))
        if n <= 0:
            버림["값없음"] += 1
            continue
        info = areas.get(code) or areas.get(code[:5]) or {}
        면적, lat, lon = info.get("면적_m2", 0), info.get("위도", 0), info.get("경도", 0)
        if not (면적 > 0 and lat and lon):
            버림["면적없음"] += 1
            continue
        out.append({
            "격자ID": f"KOSIS:{code}",
            "중심위도": round(lat, 6), "중심경도": round(lon, 6),
            # 정사각형으로 환산한 한 변. M2 가 이 값으로 겹친 면적을 잰다.
            # 300m 를 넘으면 M2 가 '격자가 아니다' 경고를 남긴다.
            "한변_m": round(면적 ** 0.5, 1),
            "세대수": round(n, 1) if 항목 == "세대수" else 0,
            "직장인구": round(n, 1) if 항목 == "직장인구" else 0,
        })
    return out, 버림


def merge_cells(a: list[dict], b: list[dict]) -> list[dict]:
    """같은 구역의 세대수 표와 직장인구 표를 한 행으로 합친다."""
    by = {}
    for r in a + b:
        cur = by.setdefault(r["격자ID"], dict(r))
        cur["세대수"] = max(to_f(cur.get("세대수")), to_f(r.get("세대수")))
        cur["직장인구"] = max(to_f(cur.get("직장인구")), to_f(r.get("직장인구")))
    return list(by.values())


def kosis_probe(api_key: str) -> int:
    """KOSIS 통계표 목록을 훑는다.

    KOSIS 는 호출 자체는 쉽지만 **어느 통계표를 쓸지** 고르는 데서 막힌다. 표가
    수만 개이고 이름이 비슷해서, 코드에 tblId 를 박아 두면 그게 맞는 표인지 아무도
    확인하지 못한다. 그래서 목록을 그대로 보여 주고 사람이 고르게 한다.
    """
    if not api_key:
        print("KOSIS_API_KEY 가 필요합니다.", file=sys.stderr)
        print("  발급: https://kosis.kr/openapi/index/index.jsp (무료)", file=sys.stderr)
        return 2

    print("KOSIS 통계표 목록 조회")
    print(f"  {KOSIS_LIST_URL}")
    찾음 = 0
    for 이름, extra in KOSIS_LIST_PROBES:
        q = urllib.parse.urlencode({
            "method": "getList", "apiKey": api_key,
            "format": "json", "jsonVD": "Y", **extra,
        })
        try:
            with urllib.request.urlopen(f"{KOSIS_LIST_URL}?{q}", timeout=25,
                                        context=ssl.create_default_context()) as r:
                body = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            print(f"\n✕ {이름} — HTTP {e.code}")
            continue
        except OSError as e:
            print(f"\n✕ {이름} — {type(e).__name__}: {e}")
            continue

        try:
            doc = json.loads(body)
        except ValueError:
            print(f"\n✕ {이름} — JSON 이 아님")
            print(f"   응답 앞부분 {body[:300]}")
            continue

        # KOSIS 는 오류도 200 + JSON 으로 보낸다
        if isinstance(doc, dict) and doc.get("errMsg"):
            print(f"\n✕ {이름} — {doc.get('err')} {doc.get('errMsg')}")
            continue
        items = doc if isinstance(doc, list) else doc.get("result") or []
        if not items:
            print(f"\n✕ {이름} — 목록이 비었습니다  {json.dumps(doc, ensure_ascii=False)[:200]}")
            continue

        찾음 += 1
        print(f"\n✓ {이름} — {len(items)}건  (파라미터 {extra})")
        for it in items[:12]:
            if not isinstance(it, dict):
                continue
            print("   " + " · ".join(
                f"{k}={it[k]}" for k in ("ORG_ID", "TBL_ID", "LIST_ID", "TBL_NM", "LIST_NM")
                if k in it))

    print("\n" + "─" * 60)
    if 찾음:
        print("쓸 통계표를 고르십시오. H 는 세대수(주민등록 또는 인구총조사 가구),")
        print("W 는 전국사업체조사의 종사자수입니다.")
        print("고른 표의 ORG_ID 와 TBL_ID 를 알려 주시면 조회까지 이어 놓겠습니다.")
        print(f"  자료 조회는 {KOSIS_DATA_URL} 에 orgId·tblId·objL1=ALL·itmId·prdSe 로 부릅니다.")
    else:
        print("목록을 하나도 받지 못했습니다. 키가 승인됐는지 확인하십시오.")
    return 0 if 찾음 else 1


def make_areas(sites: list[dict], out: Path) -> int:
    """후보지에 필요한 구역코드만 골라 --areas 표의 뼈대를 만든다.

    전국 229개 시군구 표를 통째로 만들 필요가 없다. 이번 심의에 올린 후보지가
    속한 구역만 채우면 되고, 그게 보통 몇 개다. 어느 코드가 필요한지 여기서
    짚어 주면 사람이 그 줄만 채우면 된다.

    면적과 중심점은 **비워서 낸다.** 여기서 지어내면 그 값으로 배후 수요가 안분되고,
    아무도 그게 추측이었다는 걸 모르게 된다. 어디서 받아 채우는지는 함께 적는다.
    """
    코드 = {}
    for st in sites:
        b = "".join(ch for ch in str(st.get("법정동코드") or "") if ch.isdigit())
        이름 = str(st.get("후보지명", "")).strip()
        주소 = str(st.get("주소", "")).strip()
        if len(b) >= 5:
            코드.setdefault(b[:5], []).append(이름)
        else:
            코드.setdefault("", []).append(f"{이름} ({주소 or '주소 없음'})")

    없는것 = 코드.pop("", [])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["구역코드", "구역명", "면적_m2", "위도", "경도", "비고"])
        for code, names in sorted(코드.items()):
            w.writerow([code, "", "", "", "", "후보지: " + ", ".join(sorted(set(names)))])

    print(f"--areas 뼈대를 만들었습니다 — 시군구 {len(코드)}개 → {out}")
    for code, names in sorted(코드.items()):
        print(f"  {code}  ← {', '.join(sorted(set(names)))}")
    if 없는것:
        print(f"\n  ⚠ 법정동코드가 없는 후보지 {len(없는것)}곳: {', '.join(없는것)}")
        print("     입력 화면에서 주소를 검색하면 자동으로 채워집니다.")
    print("\n면적_m2 · 위도 · 경도는 비워 뒀습니다. 지어내면 그 값으로 배후 수요가")
    print("안분되고 아무도 그게 추측이었다는 걸 모르게 됩니다. 아래에서 채우십시오:")
    print("  · 면적  KOSIS '지적통계 — 행정구역별 국토이용현황' 또는")
    print("          행정안전부 행정구역 경계(data.go.kr)에서 계산")
    print("  · 중심점 같은 경계 파일의 도형 중심(centroid)")
    print("\n채운 뒤: --areas 로 넣으면 KOSIS·통신사 유동인구 양쪽에서 같이 씁니다.")
    return 0


def kosis_run(args, out: Path) -> int:
    """KOSIS 에서 세대수·종사자수를 받아 격자인구.csv 를 만든다."""
    api_key = os.environ.get("KOSIS_API_KEY", "").strip()
    areas = load_areas(args.areas)

    if not args.live:
        write_rows([], out)
        print("dry-run — KOSIS 를 호출하지 않았습니다.")
        print(f"  키 KOSIS_API_KEY {'있음' if api_key else '없음'} · 비용 무료")
        print(f"  구역 면적표 {len(areas)}건" if areas
              else "  구역 면적표 없음 — --areas 로 구역코드→면적·중심점 표가 필요합니다")
        print("  쓸 통계표를 먼저 고르십시오:")
        print(f"    KOSIS_API_KEY=... python3 {Path(__file__).name} --source kosis --probe")
        print("  고른 뒤:")
        print(f"    KOSIS_API_KEY=... python3 {Path(__file__).name} --source kosis --live \\")
        print("        --areas 행정구역.csv --tbl-id-household DT_xxx --tbl-id-worker DT_yyy")
        print("  ※ dry-run 은 인구 수를 만들어 내지 않습니다.")
        print(f"  → {out} (빈 표)")
        return 0

    if not api_key:
        print("KOSIS_API_KEY 가 필요합니다. https://kosis.kr/openapi/index/index.jsp",
              file=sys.stderr)
        return 2
    if not (args.tbl_id_household or args.tbl_id_worker):
        print("--tbl-id-household 나 --tbl-id-worker 중 하나는 있어야 합니다.",
              file=sys.stderr)
        print("  --probe 로 통계표를 먼저 고르십시오.", file=sys.stderr)
        return 2
    자리표시자 = [t for t in (args.tbl_id_household, args.tbl_id_worker)
              if t and ("x" * 3 in t.lower() or "y" * 3 in t.lower())]
    if 자리표시자:
        print(f"통계표 ID 가 아직 자리표시자입니다: {', '.join(자리표시자)}",
              file=sys.stderr)
        print("  문서의 DT_xxxx / DT_yyyy 는 예시 자리입니다. --probe 로 실제 표를 "
              "고른 뒤 그 TBL_ID 를 넣으십시오.", file=sys.stderr)
        return 2
    if not areas:
        print("--areas 로 구역코드→면적·중심점 표가 필요합니다.", file=sys.stderr)
        print("  KOSIS 는 행정구역 코드와 값만 주고 좌표도 면적도 주지 않습니다. "
              "M2 는 둘 다 필요합니다(중심점으로 P10 과 겹치는지 보고, 면적으로 안분).",
              file=sys.stderr)
        return 2

    묶음 = []
    for tbl, 항목 in ((args.tbl_id_household, "세대수"), (args.tbl_id_worker, "직장인구")):
        if not tbl:
            continue
        rows, err = kosis_fetch(api_key, args.org_id, tbl, args.itm_id,
                                args.obj_l1, args.prd_se, args.prd_de)
        if err:
            print(f"  ✕ {항목} ({tbl}) — {err}", file=sys.stderr)
            continue
        cells, 버림 = kosis_to_cells(rows, areas, 항목)
        print(f"  ✓ {항목} ({tbl}) — 받은 행 {len(rows)} · 만든 행 {len(cells)}")
        for k, v in 버림.items():
            if v:
                print(f"      버림 {k} {v}건")
        묶음.append(cells)

    if not 묶음:
        print("한 표도 받지 못했습니다.", file=sys.stderr)
        return 1
    cells = merge_cells(묶음[0], 묶음[1] if len(묶음) > 1 else [])
    write_rows(cells, out)
    큰것 = [c for c in cells if to_f(c["한변_m"]) > 300]
    print(f"KOSIS 격자인구 — 구역 {len(cells)}개 → {out}")
    if 큰것:
        print(f"  🙋 {len(큰것)}개 구역이 한 변 300m 를 넘습니다. M2 가 P10 과 겹친 "
              f"면적비로 안분하면서 '격자가 아니다' 경고를 남깁니다 — 구역 안에서 "
              f"사람이 고르게 산다고 가정한 값입니다.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="통계청 SGIS 격자 인구를 받는다 (전국)")
    ap.add_argument("--sites", default=str(ROOT / "후보지.example.csv"))
    ap.add_argument("--radius", type=float, default=DEFAULT_RADIUS,
                    help=f"후보지 주변 조회 반경 m (기본 {DEFAULT_RADIUS:g} · P10 을 덮어야 한다)")
    ap.add_argument("--live", action="store_true", help="실제로 호출한다(기본은 dry-run)")
    ap.add_argument("--source", default="sgis", choices=("sgis", "kosis"),
                    help="어느 기관에서 받을지. 둘 다 전국·무료이고 같은 자리를 채운다")
    ap.add_argument("--probe", action="store_true",
                    help="키로 인증한 뒤 후보 엔드포인트를 하나씩 눌러 보고 무엇이 "
                         "답하는지 그대로 출력한다. 이 출력이 연동을 확정하는 근거다")
    ap.add_argument("--adm-cd", default="11", help="--probe 에서 쓸 행정구역코드 (기본 11 = 서울)")
    ap.add_argument("--year", default="2023", help="--probe 에서 쓸 기준연도")
    # KOSIS 조회 — probe 로 표를 고른 뒤 여기에 넣는다. 코드를 고칠 필요가 없다.
    ap.add_argument("--areas", help="구역코드→면적·중심점 표 (CSV). KOSIS 조회에 필요하다")
    ap.add_argument("--make-areas", action="store_true",
                    help="후보지에 필요한 구역코드만 골라 --areas 표의 뼈대를 만든다")
    ap.add_argument("--org-id", default="101", help="KOSIS 기관코드 (통계청=101)")
    ap.add_argument("--tbl-id-household", default="", help="세대수 통계표 ID")
    ap.add_argument("--tbl-id-worker", default="", help="종사자수 통계표 ID")
    ap.add_argument("--itm-id", default="ALL", help="KOSIS 항목 ID")
    ap.add_argument("--obj-l1", default="ALL", help="KOSIS 분류(행정구역) — 기본 전체")
    ap.add_argument("--prd-se", default="Y", help="수록주기 (Y=연간)")
    ap.add_argument("--prd-de", default="", help="기준시점 (비우면 최신 1건)")
    ap.add_argument("--auth-url", default=AUTH_URL)
    ap.add_argument("--data-url", default=DATA_URL)
    ap.add_argument("--out", default=str(ROOT / "output" / "격자인구.csv"))
    args = ap.parse_args(argv)

    sites_path = Path(args.sites)
    if not sites_path.exists():
        print(f"후보지 파일이 없습니다: {sites_path}", file=sys.stderr)
        return 1
    sites = read_csv(sites_path)
    boxes = sites_bboxes(sites, args.radius)
    out = Path(args.out)

    좌표없음 = len(sites) - len(boxes)
    key = os.environ.get("SGIS_KEY", "").strip()
    secret = os.environ.get("SGIS_SECRET", "").strip()

    if args.make_areas:
        return make_areas(sites, Path(args.areas or (ROOT / "output" / "행정구역.csv")))

    if args.probe:
        if args.source == "kosis":
            return kosis_probe(os.environ.get("KOSIS_API_KEY", "").strip())
        return probe(key, secret, args.auth_url, args.adm_cd, args.year,
                     boxes[0] if boxes else None)

    if args.source == "kosis":
        return kosis_run(args, out)

    if not args.live:
        write_rows([], out)
        print(f"dry-run — SGIS 를 호출하지 않았습니다.")
        print(f"  후보지 {len(sites)}곳 중 좌표 있는 {len(boxes)}곳을 조회 대상으로 잡았습니다"
              + (f" (좌표 없음 {좌표없음}곳)" if 좌표없음 else ""))
        print(f"  키 SGIS_KEY {'있음' if key else '없음'} · "
              f"SGIS_SECRET {'있음' if secret else '없음'} · 비용 무료")
        print(f"  실제로 받으려면: SGIS_KEY=... SGIS_SECRET=... "
              f"python3 {Path(__file__).name} --live --sites {args.sites}")
        print("  ※ dry-run 은 인구 수를 만들어 내지 않습니다 — 지어낸 배후 수요가 "
              "심의표에 실리면 실측으로 오인됩니다.")
        print(f"  → {out} (빈 표)")
        return 0

    if not (key and secret):
        print("SGIS_KEY / SGIS_SECRET 이 필요합니다. "
              "sgis.kostat.go.kr/developer 에서 무료로 발급합니다.", file=sys.stderr)
        return 2
    if not boxes:
        print("좌표가 있는 후보지가 없습니다. 입력 화면에서 주소를 검색해 좌표를 "
              "채우십시오.", file=sys.stderr)
        return 2

    token, err = get_token(key, secret, args.auth_url)
    if err:
        print(f"토큰 발급 실패: {err}", file=sys.stderr)
        return 1

    rows, 실패 = [], []
    for b in boxes:
        got, ferr = fetch_grid(token, b, args.data_url)
        if ferr:
            실패.append((b["이름"], ferr))
            continue
        made, 버림 = to_rows(got)
        rows += made
    rows, 중복 = dedupe(rows)
    write_rows(rows, out)

    print(f"SGIS 격자 인구 — 후보지 {len(boxes)}곳 · 격자 {len(rows)}개")
    if 중복:
        print(f"  겹친 격자 {중복}개는 한 번만 넣었습니다 — 그대로 두면 H·W 가 "
              f"겹친 만큼 부풀어 오릅니다")
    for name, e in 실패:
        print(f"  ⚠ {name}: {e}", file=sys.stderr)
    if 실패 and not rows:
        print("  한 곳도 받지 못했습니다. 위 오류를 보고 --auth-url / --data-url 이나 "
              "FIELDS 를 고치십시오.", file=sys.stderr)
        return 1
    print(f"  → {out}")
    print(f"  다음: python3 review_sites.py --sites {args.sites} (격자인구.csv 를 씁니다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
