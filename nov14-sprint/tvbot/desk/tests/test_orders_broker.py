"""Tests for orders.fake_broker (in-process, simulated, no network).

Run: /usr/bin/python3 -I -m unittest discover -s <desk>/tests -p 'test_orders*'
"""
import json
import os
import sys
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from orders.fake_broker import FakeBroker, BrokerOutage, BrokerUncertain  # noqa: E402


def bar(o, h, l, c, v=1000, ts="2026-06-01T15:30:00Z"):
    return {"ts_open": ts, "ts_close": ts, "open": o, "high": h, "low": l, "close": c,
            "volume": v, "delivered_ts": ts}


class FillRuleTests(unittest.TestCase):
    def setUp(self):
        self.b = FakeBroker(seed=7)

    def test_market_fills_at_open_and_flags(self):
        self.assertEqual(self.b.submit("m1", "buy", 10)["status"], "accepted")
        fills = self.b.step(bar(101, 103, 99, 102))
        self.assertEqual(len(fills), 1)
        f = fills[0]
        self.assertEqual((f["qty"], f["price"]), (10, 101.0))
        self.assertTrue(f["mock"])
        self.assertTrue(f["simulated"])
        self.assertTrue(f["exec_id"].startswith("EX-7-"))
        self.assertEqual(self.b.positions()["SYNTH"]["qty"], 10)
        evs = self.b.events()
        self.assertEqual([e["type"] for e in evs], ["ack", "fill"])
        self.assertTrue(all(e["simulated"] for e in evs))

    def test_order_placed_after_a_bar_waits_for_the_next(self):
        self.b.step(bar(100, 101, 99, 100))
        self.b.submit("m1", "buy", 5)
        self.assertEqual(self.b.query("m1")["filled_qty"], 0)
        self.b.step(bar(104, 105, 103, 104))
        self.assertEqual(self.b.query("m1")["avg_fill_price"], 104.0)

    def test_limit_rules(self):
        self.b.submit("bl", "buy", 5, limit=99.5)
        self.b.submit("sl", "sell", 5, limit=102.5)
        self.b.step(bar(101, 102, 100, 101))      # neither touched
        self.assertEqual(self.b.query("bl")["status"], "working")
        self.assertEqual(self.b.query("sl")["status"], "working")
        self.b.step(bar(98, 99, 97, 98))          # gaps below the buy limit: fills at the open
        self.assertEqual(self.b.query("bl")["avg_fill_price"], 98.0)
        self.b.step(bar(102, 104, 101.5, 103))    # sell limit touched: fills at the limit
        self.assertEqual(self.b.query("sl")["avg_fill_price"], 102.5)

    def test_stop_sell_gaps_through(self):
        self.b.submit("st", "sell", 3, stop=95)
        self.b.step(bar(100, 101, 96, 97))
        self.assertEqual(self.b.query("st")["status"], "working")
        self.b.step(bar(93, 94, 92, 93))
        self.assertEqual(self.b.query("st")["avg_fill_price"], 93.0)

    def test_zero_volume_never_fills(self):
        self.b.submit("m1", "buy", 5)
        self.assertEqual(self.b.step(bar(100, 101, 99, 100, v=0)), [])
        self.assertEqual(self.b.query("m1")["filled_qty"], 0)

    def test_volume_caps_fill(self):
        self.b.submit("m1", "buy", 50)
        self.b.step(bar(100, 101, 99, 100, v=20))
        self.assertEqual(self.b.query("m1")["filled_qty"], 20)

    def test_duplicate_client_id_rejected(self):
        self.b.submit("x", "buy", 1)
        r = self.b.submit("x", "buy", 1)
        self.assertEqual((r["status"], r["reason"]), ("rejected", "DUPLICATE_CLIENT_ORDER_ID"))

    def test_cancel_answers(self):
        self.assertEqual(self.b.cancel("nope")["reason"], "UNKNOWN_ORDER")
        self.b.submit("w", "buy", 1, limit=50)
        self.assertEqual(self.b.cancel("w")["status"], "canceled")
        self.assertEqual(self.b.cancel("w")["reason"], "ALREADY_DONE")
        self.b.submit("f", "buy", 1)
        self.b.step(bar(100, 101, 99, 100))
        self.assertEqual(self.b.cancel("f")["reason"], "ALREADY_FILLED")


class FaultTests(unittest.TestCase):
    def test_lost_ack_order_exists(self):
        b = FakeBroker(seed=1, faults=["lost_ack"])
        with self.assertRaises(BrokerUncertain):
            b.submit("a", "buy", 2)
        self.assertEqual(b.query("a")["status"], "working")
        self.assertEqual(b.events(), [])          # the ack was lost
        self.assertEqual(b.submit("b", "buy", 1)["status"], "accepted")   # count defaults to 1

    def test_partial_fills(self):
        b = FakeBroker(seed=1, faults={"partial": {"max_fill_qty": 3}})
        b.submit("p", "buy", 7)
        sizes = []
        for _ in range(4):
            sizes.extend(f["qty"] for f in b.step(bar(100, 101, 99, 100)))
        self.assertEqual(sizes, [3, 3, 1])
        self.assertEqual(b.query("p")["status"], "filled")

    def test_cancel_fill_race(self):
        b = FakeBroker(seed=1, faults=["cancel_fill_race"])
        b.submit("r", "buy", 4, limit=50)
        b.step(bar(100, 101, 99, 100.5))
        r = b.cancel("r")
        self.assertEqual((r["status"], r["reason"]), ("rejected", "ALREADY_FILLED"))
        q = b.query("r")
        self.assertEqual((q["status"], q["filled_qty"], q["avg_fill_price"]), ("filled", 4, 100.5))

    def test_late_fill_after_cancel(self):
        b = FakeBroker(seed=1, faults=["late_fill_after_cancel"])
        b.submit("l", "buy", 4, limit=200)
        self.assertEqual(b.cancel("l")["status"], "canceled")
        b.events()
        fills = b.step(bar(100, 101, 99, 100))
        self.assertEqual(len(fills), 1)
        self.assertEqual(b.positions()["SYNTH"]["qty"], 4)
        self.assertEqual([e["type"] for e in b.events()], ["fill"])

    def test_duplicate_and_out_of_order_events(self):
        b = FakeBroker(seed=3, faults=["duplicate_event", "out_of_order"])
        b.submit("d", "buy", 2)
        b.step(bar(100, 101, 99, 100))
        evs = b.events()
        self.assertEqual(len(evs), 4)
        self.assertEqual(sorted(e["type"] for e in evs), ["ack", "ack", "fill", "fill"])
        execs = [e["exec_id"] for e in evs if e["type"] == "fill"]
        self.assertEqual(execs[0], execs[1])

    def test_margin_reject_count(self):
        b = FakeBroker(seed=1, faults={"margin_reject": {"count": 1}})
        self.assertEqual(b.submit("a", "buy", 1)["reason"], "INSUFFICIENT_BUYING_POWER")
        self.assertEqual(b.submit("b", "buy", 1)["status"], "accepted")
        always = FakeBroker(seed=1, faults=["margin_reject"])
        for i in range(3):
            self.assertEqual(always.submit("z%d" % i, "buy", 1)["status"], "rejected")

    def test_outage_gates_api_not_step(self):
        b = FakeBroker(seed=1, faults={"outage": {"calls": 2}})
        for _ in range(2):
            with self.assertRaises(BrokerOutage):
                b.positions()
        self.assertEqual(b.positions()["SYNTH"]["qty"], 0)
        b.set_outage(True)
        for call in (lambda: b.submit("x", "buy", 1), lambda: b.cancel("x"), lambda: b.query("x"),
                     b.list_orders, b.events):
            with self.assertRaises(BrokerOutage):
                call()
        b.step(bar(100, 101, 99, 100))           # the market keeps moving
        b.set_outage(False)
        self.assertEqual(b.list_orders()["total"], 0)

    def test_truncated_listing(self):
        b = FakeBroker(seed=1, faults={"truncated_listing": {"limit": 1}})
        b.submit("a", "buy", 1, limit=50)
        b.submit("b", "buy", 1, limit=50)
        lst = b.list_orders()
        self.assertEqual((len(lst["orders"]), lst["complete"], lst["total"]), (1, False, 2))

    def test_unknown_fault_refused(self):
        with self.assertRaises(ValueError):
            FakeBroker(seed=1, faults=["meteor"])

    def test_helpers(self):
        b = FakeBroker(seed=1)
        b.inject_foreign_order("ext-1", "sell", 2, limit=150)
        self.assertEqual(b.query("ext-1")["tag"], "foreign")
        b.vanish_order("ext-1")
        self.assertIsNone(b.query("ext-1"))
        b.force_position(-3, 99.0)
        self.assertEqual(b.positions()["SYNTH"]["qty"], -3)

    def test_same_seed_same_result(self):
        def run():
            b = FakeBroker(seed=11, faults=["out_of_order", "duplicate_event"])
            for i in range(3):
                b.submit("o%d" % i, "buy", 1)
            b.step(bar(100, 101, 99, 100))
            return [(e["type"], e["client_id"]) for e in b.events()]
        self.assertEqual(run(), run())


def hbar(o, h, l, c, ts_open, ts_close, v=1000):
    """An hourly bar with distinct open and close times, delivered 2 s after the close."""
    return {"ts_open": ts_open, "ts_close": ts_close, "open": o, "high": h, "low": l, "close": c,
            "volume": v, "delivered_ts": ts_close[:-3] + "02Z"}


class V2BrokerTests(unittest.TestCase):
    def test_reduce_only_never_reverses(self):
        b = FakeBroker(seed=1)
        b.force_position(3, 100.0)
        b.submit("r", "sell", 5, reduce_only=True)
        b.step(bar(100, 101, 99, 100))
        self.assertEqual(b.positions()["SYNTH"]["qty"], 0)
        self.assertEqual(b.query("r")["filled_qty"], 3)

    def test_snapshot_restore_round_trip(self):
        b = FakeBroker(seed=5, faults=["out_of_order"], half_spread_bps=2, slip_bps=1)
        b.submit("a", "buy", 4)
        b.submit("w", "sell", 2, limit=150)
        b.step(bar(100, 101, 99, 100))
        snap = b.snapshot()
        self.assertTrue(snap["simulated"])
        c = FakeBroker.restore(json.loads(json.dumps(snap)))
        for x in (b, c):
            x.submit("n", "buy", 1)
            x.step(bar(101, 102, 100, 101))
        self.assertEqual(b.positions(), c.positions())
        self.assertEqual(b.query("n"), c.query("n"))
        self.assertEqual(b.query("w"), c.query("w"))
        self.assertEqual(b.events(), c.events())

    def test_spread_and_slip_move_fills_against_the_order(self):
        b = FakeBroker(seed=1, half_spread_bps=5, slip_bps=5)
        b.submit("bb", "buy", 1)
        b.submit("ss", "sell", 1)
        fills = b.step(bar(100, 101, 99, 100.5))
        by = {f["client_id"]: f for f in fills}
        self.assertAlmostEqual(by["bb"]["price"], 100.1)
        self.assertAlmostEqual(by["ss"]["price"], 99.9)
        for f in fills:
            self.assertEqual(f["base_price"], 100.0)
            self.assertEqual((f["half_spread_bps"], f["slip_bps"]), (5.0, 5.0))
            self.assertTrue(f["price_basis"].startswith("SIMULATED"))
            self.assertTrue(f["simulated"])
        with self.assertRaises(ValueError):
            FakeBroker(seed=1, slip_bps=-1)

    def test_market_order_never_fills_at_a_price_printed_before_submit(self):
        b = FakeBroker(seed=1)
        b.step(hbar(100, 101, 99, 100.5, "2026-06-01T14:30:00Z", "2026-06-01T15:30:00Z"))
        b.submit("m", "buy", 2)                          # submitted at 15:30:02
        self.assertEqual(b.step(hbar(99, 100, 98, 99.5, "2026-06-01T14:30:00Z", "2026-06-01T15:30:00Z")), [])
        fills = b.step(hbar(103, 104, 101, 102, "2026-06-01T15:30:00Z", "2026-06-01T16:30:00Z"))
        self.assertEqual(len(fills), 1)
        f = fills[0]
        self.assertEqual(f["base_price"], 102.0)         # the close, not the 15:30 open
        self.assertEqual(f["event_ts"], "2026-06-01T16:30:00Z")
        self.assertGreaterEqual(f["event_ts"], "2026-06-01T15:30:02Z")
        self.assertIn("report_ts", f)

    def test_order_placed_before_the_bar_opens_fills_at_open(self):
        b = FakeBroker(seed=1)
        b.step(hbar(100, 101, 99, 100.5, "2026-06-01T13:00:00Z", "2026-06-01T14:00:00Z"))
        b.submit("m", "buy", 2)                          # 14:00:02, before the 14:30 open
        f = b.step(hbar(103, 104, 101, 102, "2026-06-01T14:30:00Z", "2026-06-01T15:30:00Z"))[0]
        self.assertEqual((f["base_price"], f["event_ts"]), (103.0, "2026-06-01T14:30:00Z"))


if __name__ == "__main__":
    unittest.main()
