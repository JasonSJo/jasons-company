#!/usr/bin/env python3
"""
위치 모듈 — 좌표 파서·이름 제안·외부 링크

입력 페이지는 주소를 골라 좌표를 채운다. 좌표가 어긋나면 상권이 통째로 다른 곳에
잡히므로, 파서가 한국 범위 밖 값이나 순서가 뒤바뀐 입력을 어떻게 다루는지 고정한다.
외부 링크는 네트워크를 타지 않고 형식만 본다(각 서비스가 URL 을 바꿀 수 있다).

node 가 없으면 건너뛴다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.parse import quote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DUMP = Path(__file__).resolve().parent / "place_dump.js"
ADDR = "서울 성동구 연무장길 42"


class TestPlace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("node 가 없어 위치 모듈 검사를 건너뜁니다")
        p = subprocess.run(["node", str(DUMP)], capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            raise AssertionError(f"place_dump.js 실패:\n{p.stderr}")
        cls.d = json.loads(p.stdout)
        cls.coords = {c["입력"]: c["결과"] for c in cls.d["coords"]}

    def test_좌표를_읽는다(self):
        want = {"위도": 37.5445, "경도": 127.0557}
        for text in ("37.5445, 127.0557", "위도 37.5445 경도 127.0557", "37.5445\t127.0557"):
            with self.subTest(입력=text):
                self.assertEqual(self.coords[text], want)

    def test_순서가_뒤바뀌어도_받는다(self):
        """지도마다 경도를 먼저 주는 곳이 있다. 한국 범위로 판별해 바로잡는다."""
        self.assertEqual(self.coords["127.0557, 37.5445"],
                         {"위도": 37.5445, "경도": 127.0557})

    def test_좌표가_아니면_거절한다(self):
        """엉뚱한 값을 조용히 통과시키면 상권이 다른 곳에 잡힌다."""
        for text in ("서울시", "1, 2", "", "37.5445"):
            with self.subTest(입력=text):
                self.assertIsNone(self.coords[text])

    def test_이름을_제안한다(self):
        got = {json.dumps(n["입력"], ensure_ascii=False): n["결과"] for n in self.d["names"]}
        self.assertEqual(got[json.dumps({"이름": "스타벅스 성수점", "주소": ADDR}, ensure_ascii=False)],
                         "스타벅스 성수점")
        # 건물·상호가 없으면 주소 뒤쪽 세 토막으로 줄인다
        self.assertEqual(got[json.dumps({"이름": "", "주소": ADDR}, ensure_ascii=False)],
                         "성동구 연무장길 42")
        self.assertEqual(got[json.dumps({"이름": "", "주소": "서울 성동구"}, ensure_ascii=False)],
                         "서울 성동구")

    def test_네_곳_모두_링크한다(self):
        self.assertEqual(self.d["서비스"],
                         ["네이버지도", "네이버 부동산", "호갱노노", "일사편리"])
        self.assertEqual(len(self.d["링크"]), 4)

    def test_링크가_https_이고_주소를_인코딩한다(self):
        enc = quote(ADDR, safe="")
        for l in self.d["링크"]:
            with self.subTest(서비스=l["이름"]):
                u = urlparse(l["href"])
                self.assertEqual(u.scheme, "https", "외부 링크는 https 여야 합니다")
                self.assertTrue(u.netloc, l["href"])
                # 검색 URL 이면 주소가 인코딩되어 들어가야 한다(일사편리는 검색 파라미터가 없다)
                if l["이름"] != "일사편리":
                    self.assertIn(enc, l["href"].replace("%20", "%20"))

    def test_주소가_없으면_링크를_만들지_않는다(self):
        """빈 주소로 검색 URL 을 열면 엉뚱한 페이지로 보낸다."""
        self.assertEqual(self.d["링크_주소없음"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
