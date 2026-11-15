"""Tests for the desk strategies (worker C). Stdlib only, offline.

Run:
  /usr/bin/python3 -I -m unittest discover -s <desk>/tests -p 'test_strategies*'
"""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
TVBOT = os.path.dirname(DESK)
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from strategies import base as B          # noqa: E402
from strategies import engine as E        # noqa: E402
from strategies import registry as R      # noqa: E402
from strategies import research as RS     # noqa: E402

FIXTURE = os.path.join(TVBOT, "fixtures", "normal_bars.jsonl")


def load_bars():
    bars = []
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                row = json.loads(ln)
                if row.get("type") == "bar":
                    bars.append(row)
    bars.sort(key=lambda b: (b["ts_close"], b["seq"]))
    return bars


BARS = load_bars()
KINDS = tuple(R.STRATEGIES)


def stream(kind, bars, cfg=None, position=None):
    R.clear_cache()
    fn = R.STRATEGIES[kind]
    return [fn(bars[:k], position, cfg) for k in range(1, len(bars) + 1)]


class RegistryShape(unittest.TestCase):
    def test_registry_has_required_strategies(self):
        for k in ("ema", "gold_basket", "fixed_risk_single", "bounded_fixed", "cash"):
            self.assertIn(k, R.STRATEGIES)
            self.assertTrue(callable(R.STRATEGIES[k]))

    def test_every_decision_has_every_field(self):
        for kind in KINDS:
            for d in stream(kind, BARS):
                for f in B.DECISION_FIELDS:
                    self.assertIn(f, d, "%s missing %s" % (kind, f))
                    self.assertIsNotNone(d[f], "%s %s is None at seq %s" % (kind, f, d.get("bar_seq")))
                self.assertIn(d["action"], B.ACTIONS)
                self.assertTrue(d["simulated"])
                self.assertIsInstance(d["qty"], int)
                self.assertGreaterEqual(d["qty"], 0)
                if d["action"] in ("pass", "hold"):
                    self.assertEqual(d["qty"], 0, "%s %s with qty" % (kind, d["action"]))
                for k in ("reason_code", "reason_text", "case_for", "case_against", "pass_condition"):
                    self.assertTrue(str(d[k]).strip(), "%s empty %s" % (kind, k))
                self.assertTrue(d["est_cost"].get("simulated"))
                self.assertIsInstance(d["refusal_checks"], list)
                self.assertTrue(d["refusal_checks"], "%s no refusal checks" % kind)
                for c in d["refusal_checks"]:
                    self.assertEqual(set(c), {"id", "passed", "detail"})
                    self.assertIsInstance(c["passed"], bool)

    def test_no_bars_is_a_complete_pass(self):
        for kind in KINDS:
            R.clear_cache()
            for d in (R.STRATEGIES[kind]([], None, {}),
                      R.STRATEGIES[kind](BARS[:10], None, {"now": "2000-01-01T00:00:00Z"})):
                self.assertEqual(d["action"], "pass")
                self.assertEqual(d["qty"], 0)
                for f in B.DECISION_FIELDS:
                    self.assertIn(f, d)
                self.assertEqual([c["id"] for c in d["refusal_checks"]], ["NO_BARS"])


class CashAlwaysPasses(unittest.TestCase):
    def test_cash(self):
        for d in stream("cash", BARS, position=0):
            self.assertEqual(d["action"], "pass")
            self.assertEqual(d["qty"], 0)
            self.assertEqual(d["reason_code"], "CASH_ALWAYS_PASSES")
            self.assertTrue(d["reason_text"].strip())

    def test_cash_research_is_zero(self):
        r = E.run("cash", BARS, {"keep_records": True})
        self.assertEqual(r.fills, [])
        self.assertEqual(r.book.cash, 0.0)


class NoLookahead(unittest.TestCase):
    def _poison(self, bars, k):
        out = copy.deepcopy(bars)
        for i in range(k, len(out)):
            b = out[i]
            f = 3.0 if i % 2 else 0.3
            for p in ("open", "high", "low", "close"):
                b[p] = round(b[p] * f, 2)
            b["volume"] = 0 if i % 3 == 0 else b["volume"]
        return out

    def test_future_bars_do_not_change_past_decisions(self):
        points = list(range(70, len(BARS), 53))
        for kind in KINDS:
            for k in points:
                R.clear_cache()
                d_prefix = R.STRATEGIES[kind](BARS[:k], None, {})
                R.clear_cache()
                d_now = R.STRATEGIES[kind](self._poison(BARS, k), None, {"now": BARS[k - 1]["ts_close"]})
                self.assertEqual(d_prefix, d_now, "%s changed by future bars at k=%d" % (kind, k))
                self.assertLessEqual(d_now["bar_ts_close"], BARS[k - 1]["ts_close"])

    def test_streaming_equals_prefix_replay(self):
        for kind in ("gold_basket", "ema"):
            streamed = stream(kind, BARS[:200])
            for k in (64, 120, 199):
                rep = E.run(kind, BARS[:k], {"research_escalation": False})
                self.assertEqual(rep.last, streamed[k - 1])

    def test_knowable_uses_delivered_ts(self):
        b = dict(BARS[0])
        b["delivered_ts"] = "2026-06-01T16:00:00Z"
        self.assertEqual(B.ts_knowable(b), "2026-06-01T16:00:00Z")


class Determinism(unittest.TestCase):
    def test_cached_and_fresh_agree(self):
        for kind in KINDS:
            a = stream(kind, BARS)
            b = stream(kind, BARS)
            R.clear_cache()
            last_fresh = R.STRATEGIES[kind](BARS, None, {})
            self.assertEqual(a, b)
            self.assertEqual(a[-1], last_fresh)

    def test_research_rows_repeat(self):
        cfg = {"research_escalation": True, "test_size": B.load_test_size()}
        r1 = RS.session_rows(RS.replay("gold_basket", BARS, cfg), cfg)
        r2 = RS.session_rows(RS.replay("gold_basket", BARS, cfg), cfg)
        self.assertEqual(r1, r2)


ZERO = {"kind": "bps", "half_spread_bps": 0.0, "slippage_bps": 0.0,
        "commission_per_share": 0.0, "commission_min": 0.0, "mult": 1.0}


class BasketNetting(unittest.TestCase):
    def test_average_reduce_flat(self):
        bk = E.Book()
        E.apply_fill(bk, 1, 10, 100.0, ZERO)
        E.apply_fill(bk, 1, 10, 110.0, ZERO)
        self.assertEqual(bk.qty, 20)
        self.assertAlmostEqual(bk.avg, 105.0)
        E.apply_fill(bk, -1, 5, 120.0, ZERO)
        self.assertEqual(bk.qty, 15)
        self.assertAlmostEqual(bk.avg, 105.0)
        self.assertAlmostEqual(E.equity(bk, 120.0, ZERO), 300.0)
        E.apply_fill(bk, -1, 15, 100.0, ZERO)
        self.assertEqual(bk.qty, 0)
        self.assertIsNone(bk.avg)
        self.assertAlmostEqual(bk.cash, 0.0)

    def test_flip_resets_average(self):
        bk = E.Book()
        E.apply_fill(bk, 1, 10, 100.0, ZERO)
        E.apply_fill(bk, -1, 15, 90.0, ZERO)
        self.assertEqual(bk.qty, -5)
        self.assertAlmostEqual(bk.avg, 90.0)

    def test_costs_and_basket_threshold(self):
        costs = B.cost_cfg({})
        bk = E.Book()
        bk.basket = {"id": "t", "cash0": bk.cash, "legs": [1], "start_ts": "x"}
        E.apply_fill(bk, 1, 20, 100.0, costs)
        self.assertLess(E.basket_pnl(bk, 100.0, costs), 0.0)
        for tgt in (3.0, -6.0):
            p = E.threshold_price(bk, tgt, costs)
            self.assertAlmostEqual(E.basket_pnl(bk, p, costs), tgt, places=6)
        bk2 = E.Book()
        bk2.basket = {"id": "s", "cash0": 0.0, "legs": [-1], "start_ts": "x"}
        E.apply_fill(bk2, -1, 20, 100.0, costs)
        p = E.threshold_price(bk2, 3.0, costs)
        self.assertLess(p, 100.0)
        self.assertAlmostEqual(E.basket_pnl(bk2, p, costs), 3.0, places=6)

    def test_desk_escalation_forced_off(self):
        R.clear_cache()
        fn = R.STRATEGIES["gold_basket"]
        seen = 0
        for k in range(1, len(BARS) + 1):
            d = fn(BARS[:k], None, {"research_escalation": True})
            if d["action"] in ("enter_long", "enter_short") and isinstance(d.get("basket"), dict):
                seen += 1
                self.assertEqual(d["basket"]["escalation_mult"], 1)
        self.assertGreater(seen, 0)

    def test_gold_fills_net_to_one_position(self):
        r = E.run("gold_basket", BARS, {"research_escalation": True})
        q = 0
        for f in r.fills:
            self.assertEqual(f["qty_before"], q)
            q = f["qty_before"] + f["side"] * f["qty"]
            self.assertEqual(f["qty_after"], q)
        self.assertEqual(q, r.book.qty)

    def test_reconcile_caps_exit_to_real_position(self):
        base = {"action": "exit", "qty": 20, "reason_code": "BASKET_STOP", "reason_text": "t",
                "refusal_checks": []}
        d = R._reconcile(dict(base), 0)
        self.assertEqual((d["action"], d["qty"], d["reason_code"]), ("pass", 0, "NOTHING_TO_EXIT"))
        self.assertEqual(d["refusal_checks"][-1]["id"], "NOTHING_TO_EXIT")
        d = R._reconcile(dict(base), {"qty": -7})
        self.assertEqual((d["action"], d["qty"]), ("exit", 7))
        d = R._reconcile(dict(base), None)
        self.assertEqual(d["qty"], 20)


class SizeAndHoldout(unittest.TestCase):
    def test_test_size_is_labeled_and_read_only(self):
        s = B.load_test_size()
        self.assertEqual(s["label"], "TEST VALUES")
        self.assertGreater(s["order_notional"], 0)
        self.assertEqual(B.base_qty(100.0, {"test_size": s}), int(s["order_notional"] // 100.0))

    def test_holdout_gate_refuses_changed_rules(self):
        tmp = tempfile.mkdtemp()
        old = RS.CLAIM
        try:
            RS.CLAIM = os.path.join(tmp, "claim.json")
            self.assertTrue(RS.holdout_gate("aaa")[0])
            self.assertTrue(RS.holdout_gate("aaa")[0])
            self.assertFalse(RS.holdout_gate("bbb")[0])
        finally:
            RS.CLAIM = old
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
