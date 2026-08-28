#!/usr/bin/env python3
"""
SGIS 격자 인구 수집 (전국)

H·W 는 M2 의 배후 수요다. 지금까지 격자인구.csv 를 사람이 준비해야 했고, 그래서
전국 어디든 후보지를 넣기 전에 손작업이 하나 있었다. 여기서 지키는 것:

  · 조회 영역이 P10(도보 10분)을 덮는가 — 좁으면 배후 수요가 잘린다
  · 겹친 격자를 두 번 더하지 않는가 — 더하면 H·W 가 부풀고 그 후보지만 좋아 보인다
  · 좌표·인구를 못 읽은 격자를 0 으로 만들지 않는가
  · dry-run 이 인구를 지어내지 않는가
"""
from __future__ import annotations

import io
import json
import math
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collect_grid_population as GP   # noqa: E402
import geo                             # noqa: E402
import m2_demand as M2                 # noqa: E402
from common import read_csv            # noqa: E402


class TestBBox(unittest.TestCase):
    def test_반경이_P10_을_덮는다(self):
        """P10 = 4km/h × 10분 ≈ 667m. 조회 영역이 그보다 좁으면 배후 수요가 잘린다."""
        self.assertGreaterEqual(GP.DEFAULT_RADIUS, 667.0)

    def test_사각형이_요청한_반경을_담는다(self):
        lat, lon, r = 37.5445, 127.0557, 800.0
        y1, x1, y2, x2 = GP.bbox(lat, lon, r)
        # 남북
        self.assertAlmostEqual((y2 - lat) * 111_000, r, delta=1.0)
        # 동서 — 위도가 올라가면 경도 1도가 짧아지므로 그만큼 넓게 잡아야 한다
        동서_m = (x2 - lon) * 111_000 * math.cos(math.radians(lat))
        self.assertAlmostEqual(동서_m, r, delta=1.0)

    def test_좌표가_없는_후보지는_건너뛴다(self):
        """주소만으로는 격자를 고를 수 없다. 추측한 좌표로 받은 인구는 근거가 아니다."""
        got = GP.sites_bboxes([
            {"후보지명": "있음", "위도": "37.5", "경도": "127.0"},
            {"후보지명": "없음", "위도": "", "경도": ""},
        ], 800.0)
        self.assertEqual([b["이름"] for b in got], ["있음"])


class TestParse(unittest.TestCase):
    def test_필드명이_달라도_읽는다(self):
        rows, _ = GP.to_rows([
            {"grid_id": "G1", "lat": "37.5445", "lon": "127.0557",
             "hshld_cnt": "8", "corp_worker_cnt": "14"},
            {"격자ID": "G2", "중심위도": "37.5450", "중심경도": "127.0562",
             "세대수": "7", "직장인구": "19"},
        ])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["세대수"], 8.0)
        self.assertEqual(rows[1]["직장인구"], 19.0)

    def test_한국_밖_좌표는_버린다(self):
        rows, 버림 = GP.to_rows([
            {"lat": "0", "lon": "0", "hshld_cnt": "10", "corp_worker_cnt": "5"}])
        self.assertEqual(rows, [])
        self.assertEqual(버림["좌표없음"], 1)

    def test_사람도_일자리도_없는_격자는_넣지_않는다(self):
        rows, 버림 = GP.to_rows([
            {"lat": "37.5", "lon": "127.0", "hshld_cnt": "0", "corp_worker_cnt": "0"}])
        self.assertEqual(rows, [])
        self.assertEqual(버림["인구없음"], 1)

    def test_격자ID_가_없으면_좌표로_만든다(self):
        """ID 가 없으면 겹침 제거가 안 되고, 같은 격자를 여러 번 더하게 된다."""
        rows, _ = GP.to_rows([
            {"lat": "37.5445", "lon": "127.0557", "hshld_cnt": "8", "corp_worker_cnt": "0"}])
        self.assertTrue(rows[0]["격자ID"])

    def test_겹친_격자를_두_번_더하지_않는다(self):
        """후보지 조회 영역이 겹치면 같은 격자가 여러 번 온다."""
        rows, _ = GP.to_rows([
            {"grid_id": "G1", "lat": "37.5", "lon": "127.0", "hshld_cnt": "8", "corp_worker_cnt": "1"},
            {"grid_id": "G1", "lat": "37.5", "lon": "127.0", "hshld_cnt": "8", "corp_worker_cnt": "1"},
        ])
        out, 중복 = GP.dedupe(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(중복, 1)


class TestReachesM2(unittest.TestCase):
    """받은 격자가 실제로 H·W 로 도달하는가. 거기까지 봐야 '붙었다' 고 할 수 있다."""

    def test_H_와_W_가_나온다(self):
        tmp = Path(tempfile.mkdtemp(prefix="grid-"))
        rows, _ = GP.to_rows([
            {"grid_id": "G1", "lat": "37.5445", "lon": "127.0557",
             "hshld_cnt": "8", "corp_worker_cnt": "14"},
            {"grid_id": "G2", "lat": "37.5450", "lon": "127.0562",
             "hshld_cnt": "7", "corp_worker_cnt": "19"},
        ])
        out = GP.write_rows(rows, tmp / "격자인구.csv")
        cells = M2.load_cells(out)
        self.assertEqual(len(cells), 2)

        lat0, lon0 = 37.5445, 127.0557
        p10 = [geo.project(lat0, lon0, lat0 + dy, lon0 + dx)
               for dy, dx in [(0.006, -0.008), (0.006, 0.008),
                              (-0.006, 0.008), (-0.006, -0.008)]]
        got = M2.residents_workers({"위도": lat0, "경도": lon0, "P10": p10}, cells)
        self.assertGreater(got["H"], 0, "격자가 H 에 닿지 않았습니다")
        self.assertGreater(got["W"], 0, "격자가 W 에 닿지 않았습니다")


class TestDryRun(unittest.TestCase):
    def test_인구를_지어내지_않는다(self):
        """지어낸 배후 수요가 심의표에 실리면 실측으로 오인된다."""
        tmp = Path(tempfile.mkdtemp(prefix="grid-dry-"))
        out = tmp / "out.csv"
        rc = GP.main(["--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertEqual(read_csv(out), [])

    def test_키가_없으면_라이브를_거절한다(self):
        tmp = Path(tempfile.mkdtemp(prefix="grid-live-"))
        import os
        saved = {k: os.environ.pop(k, None) for k in ("SGIS_KEY", "SGIS_SECRET")}
        try:
            rc = GP.main(["--live", "--out", str(tmp / "o.csv")])
            self.assertEqual(rc, 2)
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


class TestProbe(unittest.TestCase):
    """SGIS 문서를 이 환경에서 열 수 없어 자료 엔드포인트를 확정하지 못했다.
    추측으로 코드를 쌓는 대신, 키가 있는 곳에서 한 번 돌리면 진실이 나오게 한다."""

    def setUp(self):
        self.원래 = urllib.request.urlopen
        self.응답 = {
            GP.AUTH_URL: {"result": {"accessToken": "TOKEN-abc"}},
            "https://sgisapi.kostat.go.kr/OpenAPI3/stats/household.json":
                {"errCd": 0, "result": [{"adm_cd": "11", "adm_nm": "서울특별시",
                                         "household_cnt": "4227000"}]},
        }

        class FakeResp:
            def __init__(s, body):
                s._b = body.encode()
                s.status = 200
            def read(s):
                return s._b
            def __enter__(s):
                return s
            def __exit__(s, *a):
                return False

        def fake(url, timeout=None, context=None):
            base = url.split("?")[0]
            if base in self.응답:
                return FakeResp(json.dumps(self.응답[base], ensure_ascii=False))
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

        urllib.request.urlopen = fake

    def tearDown(self):
        urllib.request.urlopen = self.원래

    def 실행(self):
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = GP.probe("KEY", "SECRET", GP.AUTH_URL, "11", "2023", None)
        finally:
            sys.stdout = old
        return rc, buf.getvalue()

    def test_응답한_것과_아닌_것을_갈라_보여_준다(self):
        rc, 말 = self.실행()
        self.assertEqual(rc, 0)
        self.assertIn("토큰 발급됨", 말)
        self.assertIn("household.json", 말)
        self.assertIn("household_cnt", 말, "응답 필드를 보여 주지 않습니다")
        self.assertIn("HTTP 404", 말, "실패한 후보도 보여 줘야 합니다")

    def test_인증이_실패하면_거기서_멈춘다(self):
        self.응답 = {GP.AUTH_URL: {"result": {}}}
        rc, 말 = self.실행()
        self.assertEqual(rc, 1)
        self.assertIn("토큰 발급 실패", 말)

    def test_하나도_답하지_않으면_0_이_아닌_코드(self):
        self.응답 = {GP.AUTH_URL: {"result": {"accessToken": "T"}}}
        rc, 말 = self.실행()
        self.assertEqual(rc, 1)
        self.assertIn("응답한 엔드포인트가 없습니다", 말)

    def test_키가_없으면_발급_방법을_알려_준다(self):
        buf, old = io.StringIO(), sys.stderr
        sys.stderr = buf
        try:
            rc = GP.probe("", "", GP.AUTH_URL, "11", "2023", None)
        finally:
            sys.stderr = old
        self.assertEqual(rc, 2)
        self.assertIn("개발지원센터", buf.getvalue())


class TestConfirmedEndpoints(unittest.TestCase):
    def test_인증_주소는_문서로_확인한_것이다(self):
        self.assertEqual(
            GP.AUTH_URL,
            "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json")

    def test_후보에_가구와_사업체가_들어_있다(self):
        """H 는 세대수, W 는 종사자수에서 온다. 둘 다 눌러 봐야 한다."""
        urls = " ".join(u for _, u, _, _ in GP.CANDIDATES)
        self.assertIn("household", urls)
        self.assertIn("company", urls)


class TestCoarseCellWarning(unittest.TestCase):
    """무료로 열린 전국 인구 자료(SGIS 통계·KOSIS)는 대부분 행정구역 단위다.
    그걸 격자인구.csv 에 그대로 넣으면 M2 가 균등분포로 안분하는데, 유동인구 쪽은
    같은 안분을 할 때 크게 경고하면서 여기는 조용했다."""

    def 상권(self, 반경_deg=0.003):
        lat0, lon0 = 37.5445, 127.0557
        p10 = [geo.project(lat0, lon0, lat0 + dy, lon0 + dx)
               for dy, dx in [(반경_deg, -반경_deg), (반경_deg, 반경_deg),
                              (-반경_deg, 반경_deg), (-반경_deg, -반경_deg)]]
        return {"위도": lat0, "경도": lon0, "P10": p10, "P5": p10}

    def test_100m_격자는_조용하다(self):
        cells = [{"격자ID": "G1", "중심위도": 37.5445, "중심경도": 127.0557,
                  "한변_m": "100", "세대수": "8", "직장인구": "14"}]
        got = M2.residents_workers(self.상권(), cells)
        self.assertEqual(got["굵은칸"], 0)
        self.assertEqual(got["경고"], [])

    def test_행정구역_단위는_경고한다(self):
        cells = [{"격자ID": "A1", "중심위도": 37.5445, "중심경도": 127.0557,
                  "한변_m": "1225", "세대수": "22000", "직장인구": "31000"}]
        got = M2.residents_workers(self.상권(), cells)
        self.assertEqual(got["굵은칸"], 1)
        말 = " ".join(got["경고"])
        self.assertIn("격자가 아닙니다", 말)
        self.assertIn("고르게 산다고 가정", 말)

    def test_큰_구역은_면적비로_깎인다(self):
        """P10 보다 큰 구역을 통째로 더하면 배후 수요가 몇 배로 부푼다."""
        작은상권 = self.상권(0.001)      # P10 을 좁게
        cells = [{"격자ID": "A1", "중심위도": 37.5445, "중심경도": 127.0557,
                  "한변_m": "1225", "세대수": "22000", "직장인구": "0"}]
        got = M2.residents_workers(작은상권, cells)
        self.assertLess(got["H"], 22000 * 0.5,
                        "행정동 인구가 거의 그대로 들어왔습니다 — 면적 가중이 안 먹었습니다")
        self.assertGreater(got["H"], 0)

    def test_배후_경고가_유동_경고에_먹히지_않는다(self):
        """demand() 가 dict 를 그냥 펼치면 뒤엣것이 앞엣것의 '경고' 를 덮어쓴다.
        경고가 사라지는 버그는 값이 틀리는 버그보다 알아채기 어렵다."""
        cells = [{"격자ID": "A1", "중심위도": 37.5445, "중심경도": 127.0557,
                  "한변_m": "1225", "세대수": "22000", "직장인구": "31000"}]
        points = [{"지점ID": "p", "위도": "37.5445", "경도": "127.0557",
                   "도로변": "A", "시간대": M2.AM, "인원": "300", "출처": "실측"}]
        got = M2.demand(self.상권(), cells, points, "A")
        말 = " ".join(got["경고"])
        self.assertIn("격자가 아닙니다", 말, "배후 인구 경고가 사라졌습니다")

    def test_칸이_하나도_없으면_말해_준다(self):
        got = M2.residents_workers(self.상권(), [])
        self.assertEqual(got["H"], 0)
        self.assertIn("하나도 없습니다", " ".join(got["경고"]))


class TestKosis(unittest.TestCase):
    """KOSIS 는 호출이 아니라 **어느 통계표를 쓸지** 고르는 데서 막힌다."""

    def test_키가_없으면_발급처를_알려_준다(self):
        buf, old = io.StringIO(), sys.stderr
        sys.stderr = buf
        try:
            rc = GP.kosis_probe("")
        finally:
            sys.stderr = old
        self.assertEqual(rc, 2)
        self.assertIn("kosis.kr/openapi", buf.getvalue())

    def test_목록을_받으면_통계표를_보여_준다(self):
        원래 = urllib.request.urlopen

        class FakeResp:
            def __init__(s, body):
                s._b = body.encode()
                s.status = 200
            def read(s):
                return s._b
            def __enter__(s):
                return s
            def __exit__(s, *a):
                return False

        목록 = [{"ORG_ID": "101", "TBL_ID": "DT_1B040A3",
                "TBL_NM": "주민등록인구현황", "LIST_ID": "A_1"}]

        def fake(url, timeout=None, context=None):
            if url.split("?")[0] == GP.KOSIS_LIST_URL:
                return FakeResp(json.dumps(목록, ensure_ascii=False))
            raise urllib.error.HTTPError(url, 404, "nf", None, None)

        urllib.request.urlopen = fake
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = GP.kosis_probe("KEY")
        finally:
            sys.stdout = old
            urllib.request.urlopen = 원래
        말 = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("DT_1B040A3", 말)
        self.assertIn("주민등록인구현황", 말)
        self.assertIn("ORG_ID", 말)

    def test_오류_응답을_목록으로_착각하지_않는다(self):
        """KOSIS 는 오류도 HTTP 200 + JSON 으로 보낸다."""
        원래 = urllib.request.urlopen

        class FakeResp:
            def __init__(s, body):
                s._b = body.encode()
                s.status = 200
            def read(s):
                return s._b
            def __enter__(s):
                return s
            def __exit__(s, *a):
                return False

        def fake(url, timeout=None, context=None):
            return FakeResp(json.dumps({"err": "20", "errMsg": "인증키가 유효하지 않습니다"},
                                       ensure_ascii=False))

        urllib.request.urlopen = fake
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = GP.kosis_probe("BAD")
        finally:
            sys.stdout = old
            urllib.request.urlopen = 원래
        self.assertEqual(rc, 1)
        self.assertIn("인증키가 유효하지 않습니다", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
