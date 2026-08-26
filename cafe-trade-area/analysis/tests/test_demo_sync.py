#!/usr/bin/env python3
"""
웹앱 데모 데이터가 예시 CSV 와 같은지 확인.

app/js/demo.js 는 CSV 를 구워 만든 파일이라 CSV 만 고치고 다시 굽지 않으면
콘솔의 '데모 데이터' 가 CLI 예시와 달라진다. 이 테스트가 그걸 잡는다.
어긋나면:  node app/js/gen_demo.js
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT.parent / "app" / "js"


class TestDemoSync(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            self.skipTest("node 가 없어 demo.js 대조를 건너뜁니다")

    def _demo(self):
        code = ("const d=require(process.argv[1]);"
                "process.stdout.write(JSON.stringify("
                "{s:d.DEMO_SITES,p:d.DEMO_POIS,b:d.DEMO_BRAND}));")
        proc = subprocess.run(["node", "-e", code, str(APP / "demo.js")],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        import json
        return json.loads(proc.stdout)

    def test_demo_matches_example_csv(self):
        d = self._demo()
        sites = C.read_csv(ROOT / "후보지.example.csv")
        pois = C.read_csv(ROOT / "pois.example.csv")
        self.assertEqual(len(d["s"]), len(sites), "후보지 수 불일치 — node app/js/gen_demo.js")
        self.assertEqual(len(d["p"]), len(pois), "POI 수 불일치 — node app/js/gen_demo.js")
        for js, py in zip(d["s"], sites):
            self.assertEqual(js, py, f"{py.get('후보지명')} 불일치 — node app/js/gen_demo.js")
        for js, py in zip(d["p"], pois):
            self.assertEqual(js, py, f"{py.get('상호')} 불일치 — node app/js/gen_demo.js")

    def test_demo_brand_matches_example_yaml(self):
        """콘솔 데모의 브랜드 파라미터도 brand.example.yaml 과 같아야 한다."""
        import yaml
        want = yaml.safe_load((ROOT / "brand.example.yaml").read_text(encoding="utf-8"))
        self.assertEqual(self._demo()["b"], want, "브랜드 불일치 — node app/js/gen_demo.js")


if __name__ == "__main__":
    unittest.main(verbosity=2)
