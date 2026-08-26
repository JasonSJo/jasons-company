#!/usr/bin/env python3
"""
콘솔 데모가 파이프라인 산출과 같은지 확인.

app/js/demo.js 는 analysis/output/심의결과.json 을 구워 만든 파일이다. 모델을
고치고 다시 굽지 않으면 콘솔의 '예시 결과'가 CLI 와 다른 숫자를 보여준다.
어긋나면:  cd analysis && python3 review_sites.py && node ../app/js/gen_demo.js
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT.parent / "app" / "js" / "demo.js"
OUT = ROOT / "output" / "심의결과.json"


class TestDemoSync(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            self.skipTest("node 가 없어 demo.js 대조를 건너뜁니다")
        if not OUT.exists():
            subprocess.run([sys.executable, "review_sites.py"], cwd=ROOT,
                           capture_output=True, timeout=300, check=True)

    def demo(self):
        code = "const d=require(process.argv[1]);process.stdout.write(JSON.stringify(d.DEMO));"
        p = subprocess.run(["node", "-e", code, str(DEMO)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_demo_matches_pipeline_output(self):
        want = json.loads(OUT.read_text(encoding="utf-8"))
        got = self.demo()
        hint = "node app/js/gen_demo.js 로 다시 구우세요"
        self.assertEqual(got["모드"], want["모드"], hint)
        self.assertEqual(len(got["후보지"]), len(want["후보지"]), hint)
        for a, b in zip(got["후보지"], want["후보지"]):
            self.assertEqual(a["이름"], b["이름"], hint)
            self.assertAlmostEqual(a["S"], b["S"], places=9, msg=f"{a['이름']} S — {hint}")
            self.assertEqual(a["판정"]["판정"], b["판정"]["판정"], f"{a['이름']} 판정 — {hint}")
            self.assertEqual(a["판정"]["사유"], b["판정"]["사유"], f"{a['이름']} 사유 — {hint}")
            self.assertAlmostEqual(a["매출"]["월매출_중앙"], b["매출"]["월매출_중앙"],
                                   places=6, msg=f"{a['이름']} 매출 — {hint}")

    def test_demo_carries_governance_notice(self):
        gov = (self.demo().get("설정") or {}).get("거버넌스") or {}
        self.assertIn("대외 배포 금지", gov.get("문서등급", ""))
        self.assertIn("예상매출액 산정서", gov.get("고지", ""))
