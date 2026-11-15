"""Regression checks for the fill plan (rule EMAX).

The fault these guard against: an order's stated plan named a fill bar that
opens BEFORE the decision is ready (earliest_fill_ts). Two outside reviewers
found it in packets PKT-7069f9b05f2a (74 should be 75) and PKT-a4e48b82b984
(124 should be 125). The rule now: a fill bar opens at or after
earliest_fill_ts, and the plan names that bar.

TEST ONLY: every bar here is synthetic, made by a script. Not market data.
Standard library unittest, Python 3.9. Temp folders sit under <tvbot>/out and
are removed in tearDown.

Run:
    /usr/bin/python3 -I -m unittest discover -s nov14-sprint/tvbot/tests -p "test_fill_plan.py" -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TVBOT = os.path.normpath(os.path.join(HERE, ".."))
BOT = os.path.join(TVBOT, "bot")
OUT = os.path.join(TVBOT, "out")
if BOT not in sys.path:
    sys.path.insert(0, BOT)

import engine  # noqa: E402
import run  # noqa: E402

FEED = os.path.join(TVBOT, "fixtures", "normal_bars.jsonl")
AS_OF = "2026-11-14T00:00:00Z"


def feed_lines():
    with open(FEED, encoding="utf-8") as fh:
        return [ln for ln in fh.read().splitlines() if ln.strip()]


class FillPlan(unittest.TestCase):

    def setUp(self):
        os.makedirs(OUT, exist_ok=True)
        self.tmp = tempfile.mkdtemp(dir=OUT)
        self.lines = feed_lines()
        self.bars = dict((json.loads(ln)["seq"], json.loads(ln)) for ln in self.lines[1:])

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def cut(self, name, last_seq):
        """A copy of the test feed that stops at bar last_seq."""
        path = os.path.join(self.tmp, name)
        keep = [self.lines[0]] + [ln for ln in self.lines[1:] if json.loads(ln)["seq"] <= last_seq]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(keep) + "\n")
        return path

    def run_through(self, last_seq, e=None, name=None):
        e = e or engine.Engine(as_of=AS_OF)
        res = e.process_feed(self.cut(name or "upto_%d.jsonl" % last_seq, last_seq))
        self.assertTrue(res["accepted"], res["reasons"])
        return e

    def orders(self, e):
        return [r for r in e.ledger if r["type"] == "order"]

    def test_first_entry_plans_bar_75_not_74(self):
        """PKT-7069f9b05f2a: signal at bar 73, ready 17:30:07Z. Bar 74 opens 17:30:00Z, too early."""
        e = self.run_through(73)
        o = self.orders(e)[-1]
        self.assertEqual(o["signal_seq"], 73)
        self.assertEqual(o["earliest_fill_ts"], "2026-06-15T17:30:07Z")
        self.assertEqual(o["min_fill_seq"], 74)
        self.assertEqual(o["earliest_fill_seq"], 75)
        self.assertEqual(o["earliest_fill_open_expected"], "2026-06-15T18:30:00Z")
        self.assertLess(self.bars[74]["ts_open"], o["earliest_fill_ts"])
        self.assertGreaterEqual(self.bars[75]["ts_open"], o["earliest_fill_ts"])

    def test_third_entry_plans_bar_125_not_124(self):
        """PKT-a4e48b82b984: signal at bar 123, ready 18:30:07Z. Bar 124 opens 18:30:00Z, too early."""
        e = self.run_through(123)
        o = self.orders(e)[-1]
        self.assertEqual(o["signal_seq"], 123)
        self.assertEqual(o["earliest_fill_ts"], "2026-06-24T18:30:07Z")
        self.assertEqual(o["earliest_fill_seq"], 125)
        self.assertEqual(self.bars[124]["ts_open"], "2026-06-24T18:30:00Z")
        self.assertLess(self.bars[124]["ts_open"], o["earliest_fill_ts"])
        self.assertGreaterEqual(self.bars[125]["ts_open"], o["earliest_fill_ts"])

    def test_every_planned_bar_opens_at_or_after_ready_time_and_is_the_bar_that_fills(self):
        e = self.run_through(max(self.bars))
        orders = self.orders(e)
        fills = dict((f["order_id"], f) for f in e.ledger if f["type"] == "fill")
        self.assertEqual(len(orders), 17)
        for o in orders:
            planned = self.bars[o["earliest_fill_seq"]]
            self.assertGreaterEqual(planned["ts_open"], o["earliest_fill_ts"], o["order_id"])
            self.assertGreater(o["earliest_fill_seq"], o["signal_seq"])
            f = fills[o["order_id"]]
            self.assertEqual(f["fill_seq"], o["earliest_fill_seq"], o["order_id"])
            self.assertGreaterEqual(f["fill_ts"], o["earliest_fill_ts"])
            exp = o["earliest_fill_open_expected"]
            if exp is not None:
                self.assertEqual(exp, planned["ts_open"], o["order_id"])
        problems, matched, planned_n = run.plan_check(e.ledger)
        self.assertEqual(problems, [])
        self.assertEqual((matched, planned_n), (17, 17))

    def test_signal_on_a_sessions_last_bar_plans_the_next_bar_with_no_claimed_open(self):
        """The next session's open time is not known yet, so the plan claims none."""
        e = self.run_through(max(self.bars))
        late = [o for o in self.orders(e) if o["signal_ts"].endswith("T21:30:00Z")]
        self.assertTrue(late, "the test feed should have a signal on a session's last bar")
        for o in late:
            self.assertIsNone(o["earliest_fill_open_expected"])
            self.assertEqual(o["earliest_fill_seq"], o["min_fill_seq"])
            self.assertGreaterEqual(self.bars[o["earliest_fill_seq"]]["ts_open"], o["earliest_fill_ts"])

    def test_plan_check_flags_the_old_fault(self):
        """The old plan (bar 74, opening 17:30:00Z, for a decision ready 17:30:07Z) is reported."""
        e = self.run_through(75)
        ledger = [dict(r) for r in e.ledger]
        for r in ledger:
            if r["type"] == "order" and r["signal_seq"] == 73:
                r["earliest_fill_seq"] = 74
                r["earliest_fill_open_expected"] = "2026-06-15T17:30:00Z"
        problems, matched, planned_n = run.plan_check(ledger)
        self.assertEqual(len(problems), 1)
        self.assertIn("before the decision is ready", problems[0])
        self.assertEqual(matched, 0)

    def test_plan_check_flags_a_fill_before_the_ready_time(self):
        e = self.run_through(75)
        ledger = [dict(r) for r in e.ledger]
        for r in ledger:
            if r["type"] == "fill":
                r["fill_seq"], r["fill_ts"] = 74, "2026-06-15T17:30:00Z"
        problems = run.plan_check(ledger)[0]
        self.assertTrue(any("came before its order allowed" in p for p in problems), problems)

    def test_an_order_saved_before_the_fix_still_waits_for_an_eligible_open(self):
        """A pending order with the old fields only (plan says 74) must still fill at bar 75."""
        e = self.run_through(73)
        p = e.state["pending"]
        self.assertIsNotNone(p)
        p.pop("min_fill_seq", None)
        p.pop("earliest_fill_open_expected", None)
        p["earliest_fill_seq"] = 74
        self.run_through(75, e=e, name="upto_75.jsonl")
        fills = [r for r in e.ledger if r["type"] == "fill"]
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["fill_seq"], 75)
        self.assertEqual(fills[0]["fill_ts"], "2026-06-15T18:30:00Z")


if __name__ == "__main__":
    unittest.main()
