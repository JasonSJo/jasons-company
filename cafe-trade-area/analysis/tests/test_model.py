#!/usr/bin/env python3
"""
상권 분석 모델 단위 테스트 — 표준 라이브러리 unittest 만 쓴다(추가 설치 불필요).

  python3 -m unittest discover -s tests -t .      # analysis/ 에서 실행
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common as C  # noqa: E402

BRAND = {
    "객단가_원": 5200, "영업일수": 30, "영업시간": 13, "좌석수_기본": 24,
    "테이크아웃_비중": 0.45, "반경_m": 500,
    "변동비": {"재료비율": 0.35, "카드수수료율": 0.022, "로열티율": 0.03, "광고분담금율": 0.01},
    "고정비": {"최소인건비_월_만원": 620, "인건비율": 0.20, "수도광열_월_만원": 85,
             "소모품_월_만원": 45, "기타_월_만원": 40},
    "초기투자": {"인테리어_평당_만원": 250, "장비_만원": 4500, "가맹비_만원": 1000, "교육비_만원": 300},
}

GOOD = {
    "후보지명": "양호", "전용면적_평": 22, "월임대료_만원": 300, "보증금_만원": 6000,
    "권리금_만원": 2000, "관리비_만원": 25, "층": 1, "코너여부": "Y", "전면길이_m": 9,
    "주차가능대수": 0, "좌석수": 28, "지하철_도보분": 4, "지하철_일평균승하차": 30000,
    "주거인구_500m": 9000, "직장인구_500m": 12000, "유동인구_일평균": 20000,
    "아파트세대수": 1000, "대학_학원수": 3, "오피스빌딩수": 20,
    "카페수_500m": 20, "동일포지션_경쟁수": 2,
}


def variant(**kw):
    s = dict(GOOD)
    s.update(kw)
    return s


class TestUtils(unittest.TestCase):
    def test_to_f_handles_dirty_values(self):
        self.assertEqual(C.to_f("1,234"), 1234.0)
        self.assertEqual(C.to_f("22평"), 22.0)
        self.assertEqual(C.to_f(""), 0.0)
        self.assertEqual(C.to_f(None, 7), 7)
        self.assertEqual(C.to_f("-"), 0.0)

    def test_is_yes(self):
        for v in ("Y", "yes", "예", "O", "1", "있음"):
            self.assertTrue(C.is_yes(v), v)
        for v in ("N", "", "아니오", "X"):
            self.assertFalse(C.is_yes(v), v)

    def test_haversine_known_distance(self):
        # 강남역 ↔ 역삼역 실제 약 900m
        d = C.haversine(37.4979, 127.0276, 37.5006, 127.0364)
        self.assertTrue(830 < d < 950, d)

    def test_weights_sum_to_100(self):
        self.assertEqual(sum(C.WEIGHTS.values()), 100)


class TestScoring(unittest.TestCase):
    def test_total_never_exceeds_100(self):
        huge = variant(주거인구_500m=999999, 직장인구_500m=999999, 유동인구_일평균=999999,
                       지하철_일평균승하차=999999, 카페수_500m=0, 동일포지션_경쟁수=0,
                       월임대료_만원=1, 주차가능대수=10)
        r = C.score_site(huge, [], 500)
        self.assertLessEqual(r["총점"], 100)
        for k, w in C.WEIGHTS.items():
            self.assertLessEqual(r["항목"][k], w)

    def test_no_negative_component_scores(self):
        awful = variant(카페수_500m=200, 동일포지션_경쟁수=50, 지하철_도보분=60,
                        코너여부="N", 층=3, 전면길이_m=2, 월임대료_만원=9999)
        r = C.score_site(awful, [], 500)
        for k in C.WEIGHTS:
            self.assertGreaterEqual(r["항목"][k], 0, k)

    def test_more_competition_lowers_score(self):
        few = C.score_site(variant(카페수_500m=5), [], 500)["항목"]["경쟁"]
        many = C.score_site(variant(카페수_500m=60), [], 500)["항목"]["경쟁"]
        self.assertGreater(few, many)

    def test_own_store_within_radius_triggers_cannibalization(self):
        site = variant(위도=37.5445, 경도=127.0557)
        pois = [{"상호": "자사 성수점", "분류": "자사점", "브랜드": "카페하다",
                 "위도": "37.5450", "경도": "127.0560"}]
        r = C.score_site(site, pois, 500)
        self.assertIsNotNone(r["경쟁"]["자사점_최근접_m"])
        self.assertLess(r["경쟁"]["자사점_최근접_m"], 500)
        self.assertIn("자기잠식", " ".join(r["근거"]))

    def test_competition_takes_max_of_survey_and_poi(self):
        """POI 수집이 누락돼도 현장 조사값이 있으면 경쟁을 과소평가하지 않는다."""
        site = variant(위도=37.5445, 경도=127.0557, 카페수_500m=30)
        pois = [{"상호": "카페A", "분류": "카페", "브랜드": "개인",
                 "위도": "37.5446", "경도": "127.0558"}]
        self.assertEqual(C.competition(site, pois, 500)["카페수"], 30)

    def test_grade_boundaries(self):
        self.assertEqual(C.grade(80)[0], "A")
        self.assertEqual(C.grade(79.9)[0], "B")
        self.assertEqual(C.grade(65)[0], "B")
        self.assertEqual(C.grade(64.9)[0], "C")
        self.assertEqual(C.grade(49.9)[0], "D")


class TestRevenue(unittest.TestCase):
    def test_share_falls_as_competition_rises(self):
        a = C.analyze(variant(카페수_500m=5), [], BRAND)["매출추정"]["점유율"]
        b = C.analyze(variant(카페수_500m=50), [], BRAND)["매출추정"]["점유율"]
        self.assertGreater(a, b)

    def test_share_capped(self):
        r = C.analyze(variant(카페수_500m=0, 동일포지션_경쟁수=0), [], BRAND)
        self.assertLessEqual(r["매출추정"]["점유율"], C.SHARE_CAP)

    def test_seat_cap_binds_only_dine_in(self):
        """좌석이 1석이어도 테이크아웃 몫은 남아야 한다."""
        r = C.analyze(variant(좌석수=1), [], BRAND)["매출추정"]
        self.assertTrue(r["좌석제약"])
        self.assertGreater(r["일객수_추정"], 0)
        self.assertLess(r["일객수_추정"], r["일객수_이론"])

    def test_revenue_scales_with_ticket(self):
        base = C.analyze(GOOD, [], BRAND)["손익"]["월매출_만원"]
        up = C.analyze(GOOD, [], dict(BRAND, 객단가_원=10400))["손익"]["월매출_만원"]
        self.assertAlmostEqual(up, base * 2, delta=1.0)


class TestPnl(unittest.TestCase):
    def test_profit_identity(self):
        p = C.analyze(GOOD, [], BRAND)["손익"]
        self.assertAlmostEqual(p["영업이익_만원"], p["공헌이익_만원"] - p["고정비_만원"], delta=0.2)
        self.assertAlmostEqual(p["공헌이익_만원"], p["월매출_만원"] - p["변동비_만원"], delta=0.2)

    def test_bep_is_a_true_breakeven(self):
        """BEP 매출을 그대로 넣으면 영업이익이 0 이어야 한다."""
        r = C.analyze(GOOD, [], BRAND)
        bep = r["손익"]["BEP월매출_만원"]
        self.assertIsNotNone(bep)
        at_bep = C.estimate_pnl(GOOD, {"월매출_만원": bep}, BRAND)
        self.assertAlmostEqual(at_bep["영업이익_만원"], 0.0, delta=1.0)

    def test_bep_true_breakeven_in_labor_rate_zone(self):
        """매출이 커져 인건비가 비율 구간으로 넘어가도 BEP 가 성립해야 한다."""
        brand = dict(BRAND, 고정비=dict(BRAND["고정비"], 최소인건비_월_만원=100))
        r = C.analyze(GOOD, [], brand)
        bep = r["손익"]["BEP월매출_만원"]
        at_bep = C.estimate_pnl(GOOD, {"월매출_만원": bep}, brand)
        self.assertAlmostEqual(at_bep["영업이익_만원"], 0.0, delta=1.0)

    def test_deposit_excluded_from_payback(self):
        p = C.analyze(GOOD, [], BRAND)["손익"]
        self.assertAlmostEqual(p["초기투자_만원"],
                               p["회수대상투자_만원"] + p["보증금_만원"], delta=0.2)
        self.assertAlmostEqual(p["투자회수_개월"],
                               p["회수대상투자_만원"] / p["영업이익_만원"], delta=0.2)

    def test_loss_making_site_has_no_payback(self):
        bad = variant(유동인구_일평균=500, 주거인구_500m=500, 직장인구_500m=100,
                      월임대료_만원=900, 카페수_500m=80)
        r = C.analyze(bad, [], BRAND)
        self.assertLess(r["손익"]["영업이익_만원"], 0)
        self.assertIsNone(r["손익"]["투자회수_개월"])
        self.assertTrue(any("투자회수 불가" in x for x in r["리스크"]))

    def test_structurally_impossible_brand(self):
        """변동비+인건비율이 100% 를 넘으면 BEP 가 없다."""
        brand = dict(BRAND, 변동비=dict(BRAND["변동비"], 재료비율=0.95))
        r = C.analyze(GOOD, [], brand)
        self.assertIsNone(r["손익"]["BEP월매출_만원"])
        self.assertTrue(any("구조적 적자" in x for x in r["리스크"]))


class TestExampleData(unittest.TestCase):
    """동봉한 예시 데이터가 모델을 통과하고 현실적인 범위에 들어오는지."""

    def setUp(self):
        root = Path(__file__).resolve().parent.parent
        self.sites = C.read_csv(root / "후보지.example.csv")
        self.pois = C.read_csv(root / "pois.example.csv")

    def test_all_example_sites_analyze(self):
        self.assertEqual(len(self.sites), 6)
        for s in self.sites:
            r = C.analyze(s, self.pois, BRAND)
            self.assertGreater(r["총점"], 0)
            # 국내 프랜차이즈 카페 월매출 현실 범위(1천만~1억)
            self.assertTrue(1000 <= r["손익"]["월매출_만원"] <= 10000,
                            f"{r['후보지명']}: {r['손익']['월매출_만원']}만원")

    def test_ranking_discriminates(self):
        scored = [C.analyze(s, self.pois, BRAND) for s in self.sites]
        totals = sorted(r["총점"] for r in scored)
        self.assertGreater(totals[-1] - totals[0], 10, "예시 데이터가 후보지를 변별하지 못함")


if __name__ == "__main__":
    unittest.main(verbosity=2)
