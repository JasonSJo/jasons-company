#!/usr/bin/env python3
"""
파이썬 모델 ↔ 웹앱 모델 대조 테스트

analysis/common.py 와 app/js/model.js 는 같은 공식을 두 언어로 구현한 것이다.
한쪽만 고치면 "콘솔에서 본 점수와 CLI 로 낸 리포트가 다른" 사고가 난다.
이 테스트는 같은 예시 데이터를 양쪽에 넣고 모든 수치가 일치하는지 확인한다.

node 가 없으면 건너뛴다(파이썬 쪽 단위 테스트는 그대로 돈다).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common as C  # noqa: E402
import yaml  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNNER = HERE / "parity_runner.js"
TOL = 0.05  # 만원/명 단위 반올림 차이 허용치


def verdict(r: dict) -> str:
    """build_report.verdict 를 테스트에서 재사용 (임포트 순환 방지용 지연 임포트)."""
    from build_report import verdict as v
    return v(r)[0]


class TestPythonJsParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("node 가 없어 웹앱 모델 대조를 건너뜁니다")
        cls.brand = yaml.safe_load((ROOT / "brand.example.yaml").read_text(encoding="utf-8"))
        cls.sites = C.read_csv(ROOT / "후보지.example.csv")
        cls.pois = C.read_csv(ROOT / "pois.example.csv")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(cls.brand, f, ensure_ascii=False)
            brand_json = f.name
        proc = subprocess.run(
            ["node", str(RUNNER), str(ROOT / "후보지.example.csv"),
             str(ROOT / "pois.example.csv"), brand_json],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise AssertionError(f"parity_runner.js 실행 실패:\n{proc.stderr}")
        cls.js = {r["후보지명"]: r for r in json.loads(proc.stdout)}

    def _cmp(self, name, path, py, js):
        if isinstance(py, (int, float)) and not isinstance(py, bool):
            self.assertIsNotNone(js, f"{name} {path}: JS 값이 없음")
            self.assertAlmostEqual(float(py), float(js), delta=TOL,
                                   msg=f"{name} {path}: py={py} js={js}")
        else:
            self.assertEqual(py, js, f"{name} {path}: py={py!r} js={js!r}")

    def test_every_field_matches(self):
        self.assertTrue(self.sites, "예시 후보지가 비어 있음")
        for s in self.sites:
            name = (s.get("후보지명") or "").strip()
            with self.subTest(site=name):
                py = C.analyze(s, self.pois, self.brand)
                js = self.js.get(name)
                self.assertIsNotNone(js, f"{name} 이 JS 결과에 없음")

                self._cmp(name, "총점", py["총점"], js["총점"])
                self._cmp(name, "등급", py["등급"], js["등급"])
                for k in C.WEIGHTS:
                    self._cmp(name, f"항목.{k}", py["항목"][k], js["항목"][k])
                for k, v in py["경쟁"].items():
                    self._cmp(name, f"경쟁.{k}", v, js["경쟁"][k])
                for k, v in py["매출추정"].items():
                    self._cmp(name, f"매출추정.{k}", v, js["매출추정"][k])
                for k, v in py["손익"].items():
                    self._cmp(name, f"손익.{k}", v, js["손익"][k])
                self.assertEqual(py["리스크"], js["리스크"], f"{name}: 리스크 문구 불일치")
                self.assertEqual(verdict(py), js["결론"], f"{name}: 심의 결론 불일치")

    def test_edge_cases_match(self):
        """상·하한이 실제로 걸리는 입력(점유율 캡·좌석 캡·전항목 만점/0·결측)에서도 일치해야 한다.

        예시 데이터만으로는 캡 상수가 한 번도 안 걸려 드리프트를 놓친다.
        """
        edge = HERE / "edge_cases.csv"
        proc = subprocess.run(
            ["node", str(RUNNER), str(edge), str(ROOT / "pois.example.csv")],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        js = {r["후보지명"]: r for r in json.loads(proc.stdout)}
        rows = C.read_csv(edge)
        self.assertEqual(len(rows), 5)

        seen_share_cap = seen_seat_cap = seen_full = False
        for s in rows:
            name = (s.get("후보지명") or "").strip()
            with self.subTest(site=name):
                py = C.analyze(s, self.pois, {})
                j = js[name]
                self._cmp(name, "총점", py["총점"], j["총점"])
                for k in C.WEIGHTS:
                    self._cmp(name, f"항목.{k}", py["항목"][k], j["항목"][k])
                for k, v in py["매출추정"].items():
                    self._cmp(name, f"매출추정.{k}", v, j["매출추정"][k])
                for k, v in py["손익"].items():
                    self._cmp(name, f"손익.{k}", v, j["손익"][k])
                self.assertEqual(py["리스크"], j["리스크"], f"{name}: 리스크 문구 불일치")

                if py["매출추정"]["점유율"] >= C.SHARE_CAP:
                    seen_share_cap = True
                if py["매출추정"]["좌석제약"]:
                    seen_seat_cap = True
                if py["총점"] >= 99:
                    seen_full = True

        # 픽스처가 실제로 경계를 밟았는지 — 안 밟으면 이 테스트는 무의미하다
        self.assertTrue(seen_share_cap, "점유율 상한 구간을 밟는 케이스가 없음")
        self.assertTrue(seen_seat_cap, "좌석 상한 구간을 밟는 케이스가 없음")
        self.assertTrue(seen_full, "전 항목 만점 구간을 밟는 케이스가 없음")

    def test_js_defaults_match_python_defaults(self):
        """브랜드 설정을 비워도 양쪽 기본값이 같아야 한다."""
        proc = subprocess.run(
            ["node", str(RUNNER), str(ROOT / "후보지.example.csv"), str(ROOT / "pois.example.csv")],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        js = {r["후보지명"]: r for r in json.loads(proc.stdout)}
        defaults = {"객단가_원": 5200, "영업일수": 30, "영업시간": 13, "좌석수_기본": 24,
                    "테이크아웃_비중": 0.45, "반경_m": 500,
                    "변동비": {"재료비율": 0.35, "카드수수료율": 0.022,
                             "로열티율": 0.03, "광고분담금율": 0.01},
                    "고정비": {"최소인건비_월_만원": 620, "인건비율": 0.20,
                             "수도광열_월_만원": 85, "소모품_월_만원": 45, "기타_월_만원": 40},
                    "초기투자": {"인테리어_평당_만원": 250, "장비_만원": 4500,
                              "가맹비_만원": 1000, "교육비_만원": 300}}
        for s in self.sites:
            name = (s.get("후보지명") or "").strip()
            with self.subTest(site=name):
                py = C.analyze(s, self.pois, defaults)
                self._cmp(name, "총점(기본값)", py["총점"], js[name]["총점"])
                self._cmp(name, "월매출(기본값)", py["손익"]["월매출_만원"],
                          js[name]["손익"]["월매출_만원"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestReportParity(unittest.TestCase):
    """콘솔이 내려주는 리포트와 CLI 가 만드는 리포트가 글자 단위로 같은지.

    수치가 같아도 문장·표 형식이 갈리면 '같은 리포트'라고 말할 수 없다.
    """

    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("node 가 없어 리포트 대조를 건너뜁니다")
        cls.brand = yaml.safe_load((ROOT / "brand.example.yaml").read_text(encoding="utf-8"))
        cls.sites = C.read_csv(ROOT / "후보지.example.csv")
        cls.pois = C.read_csv(ROOT / "pois.example.csv")

    def test_report_markdown_identical(self):
        from build_report import render

        day = "2026-01-01"   # 조사일은 양쪽에 같은 값을 주입해 비교한다
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(self.brand, f, ensure_ascii=False)
            brand_json = f.name
        proc = subprocess.run(
            ["node", str(RUNNER), "--report", day, str(ROOT / "후보지.example.csv"),
             str(ROOT / "pois.example.csv"), brand_json],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        js = json.loads(proc.stdout)

        for s in self.sites:
            name = (s.get("후보지명") or "").strip()
            with self.subTest(site=name):
                py = render(C.analyze(s, self.pois, self.brand), s, self.pois, self.brand, day)
                self.assertIn(name, js)
                if py != js[name]:
                    a, b = py.split("\n"), js[name].split("\n")
                    diff = next((f"{i + 1}행\n  py: {x!r}\n  js: {y!r}"
                                 for i, (x, y) in enumerate(zip(a, b)) if x != y),
                                f"줄 수 불일치 py={len(a)} js={len(b)}")
                    self.fail(f"{name} 리포트 불일치 — {diff}")
