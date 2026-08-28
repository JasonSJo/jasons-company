#!/usr/bin/env python3
"""
통신사 유동인구 수집·반입

D_am 은 판정을 가장 크게 움직이는 값이다. 그래서 여기서 지키려는 것은 '데이터가
들어온다' 가 아니라 **잘못 들어오지 않는다** 는 쪽이다:

  · 시간대 문자열이 M2 와 어긋나면 행은 멀쩡히 들어가고 D_am 만 0 이 된다.
  · 인원을 못 읽었을 때 0 으로 바꾸면 그 구역이 '사람 없는 곳' 이 된다.
  · 면적을 모르는 구역을 넣으면 M2 가 버리고 경고만 쌓인다.
  · dry-run 이 인원 수를 지어내면 그 숫자가 심의표에 실려 실측으로 오인된다.
"""
from __future__ import annotations

import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collect_carrier_flow as CF   # noqa: E402
import geo                          # noqa: E402
import m2_demand as M2              # noqa: E402
from common import read_csv         # noqa: E402

AREAS = [
    {"구역코드": "1120058010001", "면적_m2": "42000", "위도": "37.5445", "경도": "127.0557"},
    {"구역코드": "1120058010002", "면적_m2": "38000", "위도": "37.5450", "경도": "127.0562"},
]


def write_csv(path: Path, rows: list[dict], cols: list[str] = None) -> Path:
    cols = cols or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return path


class TestTimeBand(unittest.TestCase):
    def test_M2_와_같은_문자열을_쓴다(self):
        """직접 적으면 어긋났을 때 행은 들어가고 D_am 만 0 이 된다 — 조용한 실패다."""
        self.assertIs(CF.AM, M2.AM)
        self.assertIs(CF.ALL, M2.ALL)

    def test_07에서_09시만_오전이다(self):
        for v in ("07", "08", "09", "8", "08시", "08-09"):
            self.assertEqual(CF.시간대(v), M2.AM, v)
        for v in ("06", "10", "14", "23", "00"):
            self.assertEqual(CF.시간대(v), "", v)

    def test_시간이_없으면_전체로_본다(self):
        for v in ("", None, "합계"):
            self.assertEqual(CF.시간대(v), M2.ALL, repr(v))


class TestNumberParsing(unittest.TestCase):
    """엑셀을 거쳐 온 파일에는 전각 숫자와 단위가 섞인다."""

    def test_전각_숫자를_읽는다(self):
        self.assertEqual(CF.숫자("３００"), 300.0)
        self.assertEqual(CF.숫자("318.２"), 318.2)

    def test_읽지_못하면_0_이_아니라_None(self):
        """0 으로 바꾸면 그 구역이 '사람 없는 곳' 이 되어 D_am 을 끌어내린다."""
        for v in ("미상", "N/A", "-", "", None):
            self.assertIsNone(CF.숫자(v), repr(v))

    def test_쉼표와_단위를_받는다(self):
        self.assertEqual(CF.숫자("1,234"), 1234.0)
        self.assertEqual(CF.숫자("500명"), 500.0)


class TestImport(unittest.TestCase):
    """계약형 통신사 데이터 반입 — 공개 API 가 없어 이 경로가 실무의 기본이다."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="carrier-"))
        self.areas = write_csv(self.tmp / "areas.csv", AREAS)

    def 반입(self, rows, cols=None, extra=None):
        src = write_csv(self.tmp / "in.csv", rows, cols)
        out = self.tmp / "out.csv"
        rc = CF.main(["--import", str(src), "--provider", "kt-plip",
                      "--areas", str(self.areas), "--out", str(out)] + (extra or []))
        self.assertEqual(rc, 0)
        return read_csv(out)

    def test_통신사_이름이_출처에_남는다(self):
        """M2 의 경고가 '어느 자료로 판정했는지' 를 이름으로 말해야 한다."""
        got = self.반입([{"집계구_코드": "1120058010001", "시간대구분": "08",
                       "총생활인구수": "412.7"}])
        self.assertEqual(len(got), 1)
        self.assertIn("KT", got[0]["출처"])
        self.assertEqual(got[0]["시간대"], M2.AM)
        self.assertEqual(float(got[0]["단위면적_m2"]), 42000.0)

    def test_면적을_모르면_행을_만들지_않는다(self):
        """추측한 면적으로 나눈 값은 근거가 아니다. M2 에 넘기면 버려지고 경고만 쌓인다."""
        got = self.반입([{"집계구_코드": "9999999999999", "시간대구분": "08",
                       "총생활인구수": "500"}])
        self.assertEqual(got, [])

    def test_읽지_못한_인원은_0_으로_넣지_않는다(self):
        got = self.반입([
            {"집계구_코드": "1120058010001", "시간대구분": "08", "총생활인구수": "미상"},
            {"집계구_코드": "1120058010002", "시간대구분": "08", "총생활인구수": "255"},
        ])
        self.assertEqual(len(got), 1)
        self.assertEqual(float(got[0]["인원"]), 255.0)

    def test_도로변을_지어내지_않는다(self):
        """기지국 데이터에는 도로 좌·우 구분이 없다. 채워 넣으면 M2 가 횡단저항을
        적용하고, 근거 없는 보정이 D_am 에 들어간다."""
        got = self.반입([{"집계구_코드": "1120058010001", "시간대구분": "08",
                       "총생활인구수": "412"}])
        self.assertEqual(got[0]["도로변"], "")

    def test_열_이름을_직접_이어_줄_수_있다(self):
        """통신사마다 열 이름이 다르다. 못 찾으면 추측하지 않고 사람이 잇는다."""
        got = self.반입(
            [{"zone": "1120058010001", "hh": "08", "cnt_x": "412"}],
            extra=["--map", "구역코드=zone", "--map", "인원=cnt_x", "--map", "시간=hh"])
        self.assertEqual(len(got), 1)
        self.assertEqual(float(got[0]["인원"]), 412.0)


class TestReachesM2(unittest.TestCase):
    """반입한 행이 실제로 D_am 에 도달하는가. 여기까지 봐야 '붙었다' 고 할 수 있다."""

    def test_D_am_에_들어가고_실측이_아니라고_말한다(self):
        tmp = Path(tempfile.mkdtemp(prefix="carrier-m2-"))
        areas = write_csv(tmp / "areas.csv", AREAS)
        src = write_csv(tmp / "in.csv", [
            {"집계구_코드": "1120058010001", "시간대구분": "08", "총생활인구수": "412.7"},
            {"집계구_코드": "1120058010002", "시간대구분": "08", "총생활인구수": "318.2"},
        ])
        out = tmp / "out.csv"
        CF.main(["--import", str(src), "--provider", "kt-plip",
                 "--areas", str(areas), "--out", str(out)])
        rows = read_csv(out)

        lat0, lon0 = 37.5445, 127.0557
        p5 = [geo.project(lat0, lon0, lat0 + dy, lon0 + dx)
              for dy, dx in [(0.003, -0.004), (0.003, 0.004),
                             (-0.003, 0.004), (-0.003, -0.004)]]
        got = M2.foot_traffic({"위도": lat0, "경도": lon0, "P5": p5}, rows, "A")

        self.assertGreater(got["D_am"], 0, "통신사 행이 D_am 에 닿지 않았습니다")
        self.assertEqual(got["안분_행"], 2)
        self.assertFalse(got["실측여부"])
        경고 = " ".join(got["경고"])
        self.assertIn("실측이 아닙니다", 경고)
        self.assertIn("KT", 경고, "어느 자료로 판정했는지 경고가 말하지 않습니다")


class TestDryRun(unittest.TestCase):
    def test_인원을_지어내지_않는다(self):
        """지어낸 유동인구가 심의표에 실리면 실측으로 오인된다."""
        tmp = Path(tempfile.mkdtemp(prefix="carrier-dry-"))
        out = tmp / "out.csv"
        rc = CF.main(["--provider", "seoul-living", "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertEqual(read_csv(out), [])

    def test_반입_전용_공급자는_라이브를_거절한다(self):
        tmp = Path(tempfile.mkdtemp(prefix="carrier-live-"))
        rc = CF.main(["--provider", "kt-plip", "--live",
                      "--out", str(tmp / "o.csv")])
        self.assertEqual(rc, 2)


class TestProviderTable(unittest.TestCase):
    """'어느 통신사를 쓸 수 있나' 에 코드를 읽지 않고 답할 수 있어야 한다."""

    def test_통신사_셋이_다_있다(self):
        통신사 = {p["통신사"] for p in CF.PROVIDERS.values()}
        for x in ("KT", "SKT", "LG U+"):
            self.assertIn(x, 통신사)

    def test_받는_법이_솔직하다(self):
        """공개 API 가 없는 것을 'API' 라고 적으면 붙였다고 착각하게 된다."""
        for key in ("kt-plip", "skt-geovision", "lgu-flow"):
            self.assertEqual(CF.PROVIDERS[key]["받는법"], "반입", key)
        self.assertEqual(CF.PROVIDERS["seoul-living"]["받는법"], "API")
        self.assertEqual(CF.PROVIDERS["seoul-living"]["비용"], "무료")

    def test_목록에_실측이_아니라는_말이_있다(self):
        self.assertIn("실측이 아닙니다", CF.목록())


if __name__ == "__main__":
    unittest.main(verbosity=2)
