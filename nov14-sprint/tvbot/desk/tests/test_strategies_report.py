"""Weekly report portability checks (worker C). Stdlib only, offline, no PDF engine.

* short_ts prints 'YYYY-MM-DD HH:MMZ' (never '18:30:Z').
* The stylesheet is inline: no private print-edition file is read, and the
  core grid, table and type rules ship inside report.py.

Run:
  /usr/bin/python3 -I -m unittest discover -s <desk>/tests -p 'test_strategies*'
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
if DESK not in sys.path:
    sys.path.insert(0, DESK)

import report as RP  # noqa: E402


class ShortTs(unittest.TestCase):
    def test_utc_forms(self):
        for ts in ("2026-09-28T18:30:00Z", "2026-09-28T18:30:00+00:00", "2026-09-28T13:30:00-05:00",
                   "2026-09-28T18:30:00.123456Z"):
            self.assertEqual(RP.short_ts(ts), "2026-09-28 18:30Z", ts)

    def test_no_stray_colon_and_safe_fallbacks(self):
        self.assertNotIn(":Z", RP.short_ts("2026-07-22T20:30:00Z"))
        self.assertEqual(RP.short_ts("2026-09-28T18:30:00"), "2026-09-28 18:30")
        self.assertEqual(RP.short_ts("not a time"), "not a time")
        self.assertEqual(RP.short_ts(None), "")


class PortableStyle(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="desk-report-test-")
        review = {"weeks": ["2026-W40"], "default_week": "2026-W40",
                  "by_week": {"2026-W40": {"comparison": [{"metric": "fees (simulated)", "value": 2.0}],
                                           "round_trips": [{"entry_ts": "2026-10-01T15:30:00Z",
                                                            "exit_ts": "2026-10-01T18:30:00Z", "net_pnl": -1.0,
                                                            "fills": [{"qty": 1, "price": 100.0},
                                                                      {"qty": 1, "price": 99.5}]}]}}}
        with open(os.path.join(self.d, "review.json"), "w", encoding="utf-8") as fh:
            json.dump(review, fh)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_css_is_inline_and_complete(self):
        self.assertFalse(hasattr(RP, "CSS_PATH"))
        css = RP.report_css()
        for rule in ("size:letter", ".tiles.four{ grid-template-columns:1fr 1fr 1fr 1fr",
                     "table{ width:100%", "h1{", "--serif", "@bottom-left"):
            self.assertIn(rule, css)

    def test_html_carries_the_style_and_no_private_reference(self):
        week, page = RP.build_html(self.d)
        self.assertEqual(week, "2026-W40")
        self.assertIn(RP.REPORT_CSS, page)
        self.assertIn("class='tiles four'", page)
        self.assertNotIn("Income Pivot", page)
        self.assertNotIn("print-edition", page)
        self.assertIn("2026-10-01 18:30Z", page)
        self.assertNotIn(":Z<", page)
        self.assertNotIn("+$2.00", page)                      # fees are shown without a plus sign


if __name__ == "__main__":
    unittest.main()
