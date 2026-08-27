#!/usr/bin/env python3
"""
실거래가 → M5 시세 대조 연결

실거래가가 **판정에 실제로 들어가는지**, 그리고 **없을 때 아무것도 바꾸지 않는지**를
동시에 고정한다. 후자가 더 중요하다 — 시세 데이터가 없다고 판정이 달라지면
데이터를 못 받은 지역의 후보지가 근거 없이 불리해진다.

또 하나: 이 신호는 **보류까지만** 한다. 매매가를 임대료로 환산한 값은 층·용도·전면
편차를 못 담아서, 부결(탈락)의 근거로 삼기에는 약하다.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collect_transactions as TX   # noqa: E402
import config as C                  # noqa: E402
import m5_verdict as M5             # noqa: E402
import pipeline                     # noqa: E402
from common import read_csv         # noqa: E402
from tests.test_pipeline import load  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SETTINGS = {"운영": {"변동비": {"원재료율": 0.35, "로열티율": 0.03, "광고분담금율": 0.01,
                          "기타변동비율": 0.022},
                   "고정비": {"고정인건비_월_만원": 620, "기타_월_만원": 170}}}
CLEAN = {"근저당_과다": "N", "임대인_불일치": "N", "소송_계류": "N", "인허가_불가": "N"}


def expected_rent(unit: float, area_py: float) -> float:
    return unit * area_py * M5.PY_PER_M2 * C.c("상업용_연임대수익률") / 12.0


def judge(rent: float, market, area_py=20, S=90.0):
    site = dict(CLEAN, 월임대료_만원=rent, 관리비_만원=30, 전용면적_평=area_py)
    F = rent + 30 + 620 + 170
    med = (F / (1 - 0.412)) * 3.0      # margin 은 넉넉히 — 시세 조건만 남긴다
    return M5.judge(site, {"월매출_중앙": med, "월매출_하한": med},
                    SETTINGS, S, [], None, market)


class TestMarketGate(unittest.TestCase):
    def setUp(self):
        self.unit = 1000.0
        self.market = {"건수": 40, "만원_per_m2_중앙": self.unit}
        self.기대 = expected_rent(self.unit, 20)

    def test_시세_데이터가_없으면_판정이_전혀_달라지지_않는다(self):
        rent = self.기대 * 10          # 시세만 보면 명백히 과한 임대료
        with_none = judge(rent, None)
        with_empty = judge(rent, {})
        self.assertEqual(with_none["판정"], "통과")
        self.assertEqual(with_none["사유"], [])
        self.assertIsNone(with_none["시세대조"])
        self.assertEqual(with_empty["판정"], with_none["판정"])
        self.assertEqual(with_empty["비고"], with_none["비고"])

    def test_시세를_크게_넘으면_보류가_된다(self):
        r = judge(self.기대 * (C.c("시세대비_보류배수") + 0.5), self.market)
        self.assertEqual(r["판정"], "보류")
        self.assertTrue(any("임대료가 지역 시세 기대치의" in x for x in r["사유"]), r["사유"])

    def test_시세_신호는_부결까지_가지_않는다(self):
        """환산값은 층·용도 편차를 못 담는다 — 약한 근거로 사람을 떨어뜨리지 않는다."""
        r = judge(self.기대 * 50, self.market)
        self.assertEqual(r["판정"], "보류")

    def test_시세_안쪽이면_통과한다(self):
        r = judge(self.기대 * (C.c("시세대비_보류배수") - 0.5), self.market)
        self.assertEqual(r["판정"], "통과")
        self.assertEqual(r["사유"], [])

    def test_표본이_적으면_대조하지_않는다(self):
        n = int(C.c("시세대조_최소건수"))
        rent = self.기대 * (C.c("시세대비_보류배수") + 0.5)
        few = judge(rent, {"건수": n - 1, "만원_per_m2_중앙": self.unit})
        enough = judge(rent, {"건수": n, "만원_per_m2_중앙": self.unit})
        self.assertIsNone(few["시세대조"])
        self.assertEqual(few["판정"], "통과")
        self.assertEqual(enough["판정"], "보류")

    def test_전용면적이_없으면_대조하지_않는다(self):
        """면적이 비면 건물가치를 못 구한다. 0 으로 밀어붙이면 기대 임대료가 0 이 되고
        모든 후보지가 무조건 보류로 떨어진다."""
        site = dict(CLEAN, 월임대료_만원=500, 관리비_만원=30, 전용면적_평="")
        r = M5.judge(site, {"월매출_중앙": 99000, "월매출_하한": 99000},
                     SETTINGS, 90.0, [], None, self.market)
        self.assertIsNone(r["시세대조"])
        self.assertEqual(r["판정"], "통과")

    def test_근거가_산출물에_남는다(self):
        r = judge(self.기대, self.market)
        self.assertIn("지역 시세 대조", " ".join(r["비고"]))
        self.assertAlmostEqual(r["시세대조"]["기대_월임대료_만원"], self.기대, delta=1e-9)
        self.assertEqual(r["시세대조"]["건수"], 40)

    def test_계수를_바꾸면_기준도_같이_움직인다(self):
        """콘솔에서 조정 가능한 계수라는 것이 산술에도 실제로 반영돼야 한다."""
        rent = self.기대 * 3
        self.assertEqual(judge(rent, self.market)["판정"], "보류")
        orig = C.COEFFICIENTS["시세대비_보류배수"]
        C.COEFFICIENTS["시세대비_보류배수"] = (5.0, orig[1], orig[2])
        try:
            self.assertEqual(judge(rent, self.market)["판정"], "통과")
        finally:
            C.COEFFICIENTS["시세대비_보류배수"] = orig


class TestSummaryLoading(unittest.TestCase):
    def test_CSV_를_지역코드별_요약으로_읽는다(self):
        rows = [{"지역코드": "11680", "거래금액_만원": 90000, "건물면적_m2": 100,
                 "만원_per_m2": 900, "거래일": "2026-01-02"},
                {"지역코드": "11680", "거래금액_만원": 110000, "건물면적_m2": 100,
                 "만원_per_m2": 1100, "거래일": "2026-03-02"},
                {"지역코드": "41135", "거래금액_만원": 50000, "건물면적_m2": 50,
                 "만원_per_m2": 1000, "거래일": "2026-02-02"}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "실거래가.csv"
            TX.write_rows(p, rows)
            got = TX.load_summaries(p)
        self.assertEqual(set(got), {"11680", "41135"})
        self.assertEqual(got["11680"]["건수"], 2)
        self.assertAlmostEqual(got["11680"]["만원_per_m2_중앙"], 1000.0)

    def test_단가를_못_읽은_행이_중앙값을_끌어내리지_않는다(self):
        rows = [{"지역코드": "11680", "거래금액_만원": 90000, "건물면적_m2": "",
                 "만원_per_m2": "", "거래일": "2026-01-02"},
                {"지역코드": "11680", "거래금액_만원": 100000, "건물면적_m2": 100,
                 "만원_per_m2": 1000, "거래일": "2026-02-02"}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "실거래가.csv"
            TX.write_rows(p, rows)
            got = TX.load_summaries(p)
        self.assertAlmostEqual(got["11680"]["만원_per_m2_중앙"], 1000.0)

    def test_없는_파일은_빈_요약이다(self):
        self.assertEqual(TX.load_summaries(Path("/없는/경로/실거래가.csv")), {})

    def test_법정동코드_앞_다섯_자리가_조회_키다(self):
        self.assertEqual(TX.lawd("1168010100"), "11680")
        self.assertEqual(TX.lawd("11680"), "11680")
        self.assertEqual(TX.lawd(""), "")


class TestPipelineWiring(unittest.TestCase):
    """파이프라인이 후보지의 법정동코드로 지역 요약을 실제로 찾아 M5 에 넘기는가."""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.단가 = 1200.0

    def _run(self, market):
        sites = [dict(r) for r in self.data["sites"]]
        for r in sites:
            r["법정동코드"] = "1120010300"          # 성동구 — 전부 같은 지역으로 둔다
        d = dict(self.data, sites=sites)
        return pipeline.analyze_all(**d, market=market)

    def test_지역코드로_요약을_찾아_넘긴다(self):
        res = self._run({"11200": {"건수": 30, "만원_per_m2_중앙": self.단가}})
        대조 = [r["판정"]["시세대조"] for r in res["후보지"]]
        self.assertTrue(all(x is not None for x in 대조), "시세 대조가 하나도 안 걸렸습니다")
        for r in res["후보지"]:
            기대 = expected_rent(self.단가, float(r["후보지"]["전용면적_평"]))
            self.assertAlmostEqual(r["판정"]["시세대조"]["기대_월임대료_만원"], 기대, delta=1e-9)

    def test_다른_지역의_시세는_붙지_않는다(self):
        res = self._run({"41135": {"건수": 30, "만원_per_m2_중앙": self.단가}})
        self.assertTrue(all(r["판정"]["시세대조"] is None for r in res["후보지"]))

    def test_법정동코드가_없으면_대조하지_않는다(self):
        res = pipeline.analyze_all(
            **self.data, market={"11200": {"건수": 30, "만원_per_m2_중앙": self.단가}})
        self.assertTrue(all(r["판정"]["시세대조"] is None for r in res["후보지"]),
                        "법정동코드가 빈 예시 후보지에 시세가 붙었습니다")

    def test_시세가_없을_때와_판정이_같다(self):
        없이 = pipeline.analyze_all(**self.data)
        빈것 = pipeline.analyze_all(**self.data, market={})
        self.assertEqual([r["판정"]["판정"] for r in 없이["후보지"]],
                         [r["판정"]["판정"] for r in 빈것["후보지"]])


class TestFetchIsOptIn(unittest.TestCase):
    """수집은 명시적으로 켤 때만 일어난다 — 심의표를 뽑을 때마다 외부 API 를 두드리면
    키가 없는 환경에서 파이프라인이 실패하고, 요금제·쿼터도 사람 모르게 소모된다."""

    class Args:
        def __init__(self, path, collect=False):
            self.실거래 = str(path)
            self.실거래_수집 = collect
            self.실거래_개월 = 12

    def test_기본은_저장된_표만_읽는다(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "실거래가.csv"
            TX.write_rows(p, [{"지역코드": "11200", "거래금액_만원": 80000,
                               "건물면적_m2": 100, "만원_per_m2": 800,
                               "거래일": "2026-05-01"}])
            got = pipeline.load_market([], self.Args(p))
        self.assertEqual(got["11200"]["건수"], 1)

    def test_키가_없으면_수집을_켜도_조용히_건너뛴다(self):
        import os
        saved = os.environ.pop("DATA_GO_KR_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as d:
                got = pipeline.load_market(
                    [{"후보지명": "가", "법정동코드": "1120010300"}],
                    self.Args(Path(d) / "실거래가.csv", collect=True))
            self.assertEqual(got, {})
        finally:
            if saved is not None:
                os.environ["DATA_GO_KR_KEY"] = saved


class TestDocumentedHonestly(unittest.TestCase):
    def test_수집기가_더는_계산에_안_들어간다고_말하지_않는다(self):
        """이제 M5 에 들어간다. 문서가 '들어가지 않는다' 로 남아 있으면 거짓말이 된다."""
        for p in (ROOT / "collect_transactions.py", ROOT / "review_sites.py"):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("판정 계산에는 들어가지 않습니다", text, f"{p.name}")
            self.assertNotIn("M1~M6 계산에 들어가지 않는다", text, f"{p.name}")

    def test_환산_계수가_미검증으로_공시된다(self):
        for name in ("상업용_연임대수익률", "시세대비_보류배수", "시세대조_최소건수"):
            self.assertEqual(C.COEFFICIENTS[name][1], "ESTIMATED", name)
            self.assertIn(name, [k for k, _, _ in C.unvalidated()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
