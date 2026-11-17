"""Tests for orders.manager (paper desk order engine and controls).

Offline and simulated only: the broker is the in-process FakeBroker, the bars are
the synthetic tvbot fixtures, and the limits are TEST VALUES derived from
tvbot/config/smaller_size.json (order_notional 2000). Sizing is Matthew-only.

Run: /usr/bin/python3 -I -m unittest discover -s <desk>/tests -p 'test_orders*'
"""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(os.path.dirname(DESK), "fixtures")
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from orders.calendar import SessionCalendar, parse_ts, iso  # noqa: E402
from orders.fake_broker import FakeBroker, BrokerOutage  # noqa: E402
from orders.manager import OrderManager, NOT_FLAT_TEXT  # noqa: E402

# TEST VALUES from the v2 contract (tvbot/config/smaller_size.json order_notional 2000). Sizing is Matthew-only.
LIMITS = {"per_trade_notional": 2000, "max_loss_per_trade": 10.0, "daily_loss": 30.0, "gross_exposure": 2000,
          "label": "TEST VALUES"}
FAR = "2026-06-30T00:00:00Z"     # an expiry that never fires inside these tests


def load_bars(path):
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") == "manifest":
                continue
            out.append(rec)
    return out


BARS = load_bars(os.path.join(FIX, "normal_bars.jsonl"))


def codes(alarms):
    return [a["code"] for a in alarms]


class DeskCase(unittest.TestCase):
    """One state dir per test; every manager is closed in tearDown."""

    faults = None

    def setUp(self):
        self.cal = SessionCalendar.fixture_profile()
        self.dir = tempfile.mkdtemp(prefix="orders-test-")
        self.b = FakeBroker(seed=7, faults=self.faults)
        self.mgrs = []
        self.m = self.new_manager()
        self.i = 0

    def tearDown(self):
        for m in self.mgrs:
            m.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def new_manager(self):
        m = OrderManager(self.dir, self.b, LIMITS, calendar=self.cal)
        self.mgrs.append(m)
        return m

    def restart(self):
        self.m.close()
        self.m = self.new_manager()
        return self.m

    def bar(self, broker_only=False):
        """Advance one fixture bar: broker.step first, then the manager sees it."""
        bar = BARS[self.i]
        self.i += 1
        self.b.step(bar)
        if broker_only:
            return None
        return self.m.on_bar(bar)

    def start(self, expires=FAR):
        self.bar()
        r = self.m.arm("S1", expires_utc=expires)
        self.assertTrue(r["ok"], r)

    def buy(self, did, qty, **kw):
        """An entry. Its invalidation defaults to 0.50 under the entry price (pass None to omit it)."""
        intent = {"decision_id": did, "side": "buy", "qty": qty, "ref_price": self.m.mark}
        intent.update(kw)
        if "invalidation" not in kw and self.m.mark is not None:
            intent["invalidation"] = (kw.get("limit") or self.m.mark) - 0.5
        return self.m.submit_intent(intent)

    def read_audit(self):
        with open(os.path.join(self.dir, "audit.jsonl")) as fh:
            return [json.loads(x) for x in fh if x.strip()]

    def long10(self):
        """Arm, buy 10 at market, and let it fill on the next bar."""
        self.start()
        iid = self.buy("long", 10)
        self.bar()
        self.assertEqual(self.m.pos_qty, 10)
        self.assertEqual(self.m.intents[iid]["status"], "filled")
        return iid

    def protective(self, did="prot", qty=10, stop=None):
        if stop is None:
            stop = self.m.mark - 1.0                     # 10 x 1.00 = 10 at risk
        return self.m.submit_intent({"decision_id": did, "kind": "protective", "side": "sell", "qty": qty,
                                     "stop": stop})

    def status(self, iid):
        return self.m.intents[iid]["status"]

    def reason(self, iid):
        return self.m.intents[iid].get("reason")


class GateTests(DeskCase):
    def test_bad_intents_raise(self):
        with self.assertRaises(ValueError):
            self.m.submit_intent({"side": "buy", "qty": 1})
        with self.assertRaises(ValueError):
            self.m.submit_intent({"decision_id": "x", "side": "hold", "qty": 1})
        with self.assertRaises(ValueError):
            self.m.submit_intent({"decision_id": "y", "side": "buy", "qty": 1.5})
        with self.assertRaises(ValueError):
            OrderManager(tempfile.mkdtemp(), FakeBroker(1), {"per_trade_notional": 2000})

    def test_entries_need_arm(self):
        self.bar()
        iid = self.buy("d1", 1)
        self.assertEqual((self.status(iid), self.reason(iid)), ("rejected", "NOT_ARMED"))
        self.assertEqual(self.b.list_orders()["total"], 0)

    def test_duplicate_decision_sends_once(self):
        self.start()
        a = self.buy("same", 2)
        b = self.buy("same", 2)
        self.assertEqual(a, b)
        self.assertEqual(self.b.list_orders()["total"], 1)

    def test_per_trade_and_gross_limits(self):
        self.start()
        big = self.buy("big", 25, limit=90.0)            # 2250 > 2000
        self.assertEqual(self.reason(big), "NOTIONAL")
        first = self.buy("g1", 20, limit=90.0)           # 1800 working
        self.assertEqual(self.status(first), "acked")
        second = self.buy("g2", 20, limit=90.0)          # 1800 + 1800 > 2000
        self.assertEqual((self.status(second), self.reason(second)), ("rejected", "RISK_GROSS"))
        self.assertAlmostEqual(self.m.gross_exposure(), 1800.0)

    def test_worst_case_daily_loss_from_stops(self):
        self.long10()
        mark = self.m.mark
        p = self.protective(stop=mark - 2.5)             # 10 x 2.50 = 25 at risk
        self.assertEqual(self.status(p), "acked")
        iid = self.buy("w", 1, limit=mark, invalidation=mark - 9.0)   # 25 + 9 = 34 > 30
        self.assertEqual((self.status(iid), self.reason(iid)), ("rejected", "RISK_DAILY_LOSS_WORST_CASE"))

    def test_worst_case_counts_working_entries(self):
        self.start()
        lim = self.m.mark - 5.0                          # never touched by the fixture
        for k in range(3):
            iid = self.buy("w%d" % k, 2, limit=lim, invalidation=lim - 4.5)    # 9 each
            self.assertEqual(self.status(iid), "acked")
        iid = self.buy("w3", 2, limit=lim, invalidation=lim - 4.5)             # 27 + 9 = 36 > 30
        self.assertEqual(self.reason(iid), "RISK_DAILY_LOSS_WORST_CASE")

    def test_max_loss_per_trade(self):
        self.start()
        mark = self.m.mark
        iid = self.buy("ml", 10, invalidation=mark - 2.0)            # 10 x 2.00 = 20 > 10
        self.assertEqual((self.status(iid), self.reason(iid)), ("rejected", "MAX_LOSS"))
        # Operator rule: the per-trade cap is price risk only, so 9 + 1.50 cost
        # passes it; the cost counts against the daily cap (test_fees_count_in_daily_not_per_trade).
        cost = self.buy("mlc", 10, invalidation=mark - 0.9, est_cost=1.5)   # price risk 9 <= 10
        self.assertEqual(self.status(cost), "acked")
        self.assertEqual(self.b.list_orders()["total"], 1)

    def test_fees_count_in_daily_not_per_trade(self):
        self.start()
        mark = self.m.mark
        iid = self.buy("fd", 1, limit=mark, invalidation=mark - 9.0, est_cost=21.5)   # 9 <= 10; 9 + 21.5 > 30
        self.assertEqual((self.status(iid), self.reason(iid)), ("rejected", "RISK_DAILY_LOSS_WORST_CASE"))
        ok = self.buy("fd2", 1, limit=mark, invalidation=mark - 9.0, est_cost=20.5)   # 29.50 fits
        self.assertEqual(self.status(ok), "acked")
        nxt = self.buy("fd3", 1, limit=mark, invalidation=mark - 0.4, est_cost=0.2)
        # the working entry reserves its 9 + 20.50 including fees: 29.5 + 0.6 > 30
        self.assertEqual(self.reason(nxt), "RISK_DAILY_LOSS_WORST_CASE")
        self.assertEqual(self.b.list_orders()["total"], 1)

    def test_entry_needs_an_invalidation_on_the_losing_side(self):
        self.start()
        iid = self.buy("ns", 1, invalidation=None)
        self.assertEqual((self.status(iid), self.reason(iid)), ("rejected", "NO_STOP"))
        bad = self.buy("bs", 1, invalidation=self.m.mark + 1.0)
        self.assertEqual(self.reason(bad), "BAD_STOP")
        neg = self.buy("bc", 1, est_cost=-1.0)
        self.assertEqual(self.reason(neg), "BAD_COST")
        self.assertEqual(self.b.list_orders()["total"], 0)

    def test_contract_intent_fields_and_kind_audit(self):
        self.start()
        mark = self.m.mark
        iid = self.m.submit_intent({"decision_id": "k1", "kind": "entry", "symbol": "SYNTH", "side": "buy",
                                    "qty": 1, "intended_entry": mark, "invalidation": mark - 1.0,
                                    "est_cost": 0.1})
        self.assertEqual(self.status(iid), "acked")
        rows = [r for r in self.read_audit() if r.get("intent_id") == iid]
        self.assertTrue(rows)
        self.assertTrue(all(r["kind"] in ("intent", "order", "control", "alarm", "fill", "reconcile")
                            or isinstance(r["kind"], str) for r in rows))
        self.assertIn("entry", [r.get("order_kind") for r in rows])
        other = self.m.submit_intent({"decision_id": "k2", "kind": "entry", "symbol": "QQQ", "side": "buy",
                                      "qty": 1, "intended_entry": mark, "invalidation": mark - 1.0})
        self.assertEqual(self.reason(other), "WRONG_SYMBOL")

    def test_stale_bar_blocks_entries_and_keeps_mark(self):
        self.start()
        mark = self.m.mark
        bar = dict(BARS[1], close=150.0, high=150.0)
        bar["delivered_ts"] = iso(parse_ts(bar["ts_close"]) + dt.timedelta(seconds=60))
        self.b.step(BARS[1])
        self.m.on_bar(bar)
        self.assertEqual(self.m.entry_block_reason(), "BAR_STALE_EXCHANGE_TS")
        self.assertEqual(self.m.mark, mark)
        iid = self.buy("late", 1)
        self.assertEqual(self.reason(iid), "BAR_STALE_EXCHANGE_TS")

    def test_market_closed_blocks_entries(self):
        self.start()
        for _ in range(6):
            self.bar()                                   # bars[6] arrives after the 21:30Z close
        self.assertEqual(self.m.entry_block_reason(), "MARKET_CLOSED")

    def test_exit_gates(self):
        self.start()
        none = self.m.submit_intent({"decision_id": "x0", "kind": "exit", "side": "sell", "qty": 1})
        self.assertEqual(self.reason(none), "EXIT_NOT_REDUCING")
        iid = self.buy("long", 10)
        self.bar()
        self.assertEqual(self.status(iid), "filled")
        wrong = self.m.submit_intent({"decision_id": "x1", "kind": "exit", "side": "buy", "qty": 1})
        self.assertEqual(self.reason(wrong), "EXIT_NOT_REDUCING")
        big = self.m.submit_intent({"decision_id": "x2", "kind": "exit", "side": "sell", "qty": 15})
        self.assertEqual(self.reason(big), "EXIT_EXCEEDS_POSITION")
        p = self.protective()
        self.assertEqual(self.status(p), "acked")
        extra = self.protective(did="prot2", qty=5)
        self.assertEqual(self.reason(extra), "EXIT_EXCEEDS_POSITION")
        # A target exit is a separate bucket from the protective stop.
        tgt = self.m.submit_intent({"decision_id": "x3", "kind": "exit", "side": "sell", "qty": 10, "limit": 120.0})
        self.assertEqual(self.status(tgt), "acked")


class BrokerFaultTests(DeskCase):
    def test_lost_ack_is_adopted_by_query(self):
        self.start()
        self.b.set_fault("lost_ack")
        iid = self.buy("la", 3)
        self.assertEqual(self.status(iid), "acked")      # query found the order; nothing re-sent
        self.assertEqual(self.b.list_orders()["total"], 1)

    def test_lost_ack_survives_restart_and_recovers_fills(self):
        self.start()
        self.b.set_fault("lost_ack")
        real_query = self.b.query
        calls = {"n": 0}

        def flaky_query(cid):
            calls["n"] += 1
            if calls["n"] == 1:
                raise BrokerOutage("simulated: query lost too")
            return real_query(cid)

        self.b.query = flaky_query
        iid = self.buy("la", 10)
        self.assertEqual(self.status(iid), "uncertain")
        self.assertIn(self.m.entry_block_reason(), ("BROKER_DISCONNECTED", "UNRESOLVED_SUBMIT"))
        del self.b.query
        self.m.close()
        self.b.set_fault("partial", {"max_fill_qty": 4})
        self.b.set_fault("duplicate_event")
        for _ in range(3):
            self.bar(broker_only=True)                   # the desk is down; fills 4, 4, 2
        m2 = self.new_manager()
        self.m = m2
        rep = m2._last_report
        self.assertIn(iid, rep["adopted"])
        self.assertEqual(rep["fills_recovered"], 3)
        self.assertTrue(rep["ok"], rep)
        self.assertEqual((m2.pos_qty, self.status(iid)), (10, "filled"))
        self.assertEqual(self.b.list_orders()["total"], 1)
        r = self.bar()
        self.assertEqual(r["fills_booked"], 0)
        self.assertGreaterEqual(r["duplicates"], 3)
        self.assertEqual(m2.pos_qty, 10)

    def test_partial_fills(self):
        self.start()
        self.b.set_fault("partial", {"max_fill_qty": 3})
        iid = self.buy("p", 10)
        self.bar()
        self.assertEqual((self.m.pos_qty, self.status(iid)), (3, "acked"))
        for _ in range(3):
            self.bar()
        self.assertEqual((self.m.pos_qty, self.status(iid)), (10, "filled"))
        self.assertEqual(len(self.m.intents[iid]["fill_ids"]), 4)

    def test_cancel_fill_race(self):
        self.start()
        iid = self.buy("r", 4, limit=50.0)
        self.b.set_fault("cancel_fill_race")
        p = self.m.pause()
        self.assertEqual(p["cancel_refused"], [[iid, "refused:ALREADY_FILLED"]])
        self.m.poll()
        self.assertEqual((self.status(iid), self.m.pos_qty), ("filled", 4))
        self.assertTrue(self.m.reconcile()["ok"])

    def test_late_fill_after_cancel(self):
        self.b.set_fault("late_fill_after_cancel")
        self.start()
        iid = self.buy("l", 5, limit=200.0)
        p = self.m.pause()
        self.assertEqual(p["entries_canceled"], [iid])
        self.assertEqual(self.status(iid), "canceled")
        self.bar()
        self.assertEqual(self.m.pos_qty, 5)
        self.assertEqual(self.b.positions()["SYNTH"]["qty"], 5)
        with open(os.path.join(self.dir, "audit.jsonl")) as fh:
            filled = [json.loads(x) for x in fh if '"filled"' in x]
        self.assertTrue(any(r.get("late_after_cancel") for r in filled))
        self.assertTrue(self.m.reconcile()["ok"])

    def test_duplicate_and_out_of_order_events(self):
        self.b.set_fault("duplicate_event")
        self.b.set_fault("out_of_order")
        self.start()
        self.buy("d", 2)
        r = self.bar()
        self.assertEqual((r["fills_booked"], r["duplicates"]), (1, 1))
        self.assertEqual(self.m.pos_qty, 2)

    def test_margin_reject(self):
        self.start()
        self.b.set_fault("margin_reject", {"count": 1})
        a = self.buy("m1", 1)
        self.assertEqual((self.status(a), self.reason(a)), ("rejected", "INSUFFICIENT_BUYING_POWER"))
        b = self.buy("m2", 1)
        self.assertEqual(self.status(b), "acked")

    def test_outage_pending_cancel_retried_after_restart(self):
        self.start()
        iid = self.buy("o", 5, limit=90.0)
        self.b.set_outage(True)
        p = self.m.pause()
        self.assertEqual(p["cancel_failed"], [iid])
        self.assertEqual(self.m.controls["pending_cancels"], [iid])
        m2 = self.restart()
        self.assertIn("BROKER_UNREACHABLE", codes(m2.controls["alarms"]))
        self.assertTrue(m2.controls["paused"])
        self.b.set_outage(False)
        self.bar()
        self.assertEqual(self.status(iid), "canceled")
        self.assertEqual(m2.controls["pending_cancels"], [])
        self.assertEqual(m2.blocking_alarms(), [])


class ReconcileTests(DeskCase):
    def test_foreign_order_blocks_arm_until_gone(self):
        self.bar()
        self.b.inject_foreign_order("ext-1", "sell", 2, limit=150.0)
        self.assertIn("FOREIGN_ORDER", codes(self.m.reconcile()["alarms"]))
        r = self.m.arm("S1", expires_utc=FAR)
        self.assertEqual((r["ok"], r["reason"]), (False, "RECONCILE_NOT_CLEAN"))
        self.b.vanish_order("ext-1")
        self.assertTrue(self.m.arm("S1", expires_utc=FAR)["ok"])

    def test_order_missing(self):
        self.start()
        iid = self.buy("v", 5, limit=90.0)
        self.b.vanish_order(iid)
        rep = self.m.reconcile()
        self.assertIn("ORDER_MISSING", codes(rep["alarms"]))
        self.assertFalse(rep["ok"])

    def test_incomplete_listing(self):
        self.start()
        self.buy("t1", 2, limit=90.0)
        self.buy("t2", 2, limit=90.0)
        self.b.set_fault("truncated_listing", {"limit": 1})
        rep = self.m.reconcile()
        self.assertIn("INCOMPLETE_LISTING", codes(rep["alarms"]))
        self.assertEqual(self.m.entry_block_reason(), "BLOCKING_ALARM")

    def test_position_excess(self):
        self.start()
        self.b.force_position(5, 100.0)
        rep = self.m.reconcile()
        self.assertIn("POSITION_EXCESS", codes(rep["alarms"]))
        self.assertEqual(rep["positions"], {"broker": 5, "booked": 0})


class ControlTests(DeskCase):
    def test_pause_survives_restart_and_keeps_protective(self):
        self.long10()
        p = self.protective()
        entry = self.buy("add", 5, limit=90.0)
        self.assertEqual(self.status(entry), "acked")
        r = self.m.pause()
        self.assertEqual(r["entries_canceled"], [entry])
        self.assertEqual(r["protective_kept"], [p])
        m2 = self.restart()
        self.assertTrue(m2.controls["paused"])
        self.assertEqual(self.status(p), "acked")
        self.bar()
        again = self.buy("add2", 1)
        self.assertEqual(self.reason(again), "PAUSED")
        self.assertTrue(m2.resume()["ok"])
        self.assertIsNone(m2.entry_block_reason())

    def test_stop_and_close_waits_for_open_then_ends_flat(self):
        self.long10()
        p = self.protective()
        for _ in range(5):
            self.bar()                                   # through bars[6], delivered after the close
        r = self.m.stop_and_close()
        self.assertEqual(r["close"]["state"], "pending")
        self.assertIn("market closed", r["close"]["why"])
        self.assertEqual(self.status(p), "acked")        # the protective stop stays live overnight
        m2 = self.restart()
        self.assertTrue(m2.controls["stopped"])
        self.assertFalse(m2.controls["flat_confirmed"])
        self.assertEqual(m2.pos_qty, 10)
        r = self.bar()                                   # next day's open
        self.assertEqual(r["stop"]["state"], "closing")
        self.assertEqual(self.status(p), "acked")        # kept until the broker shows flat
        r = self.bar()
        self.assertEqual(r["stop"]["state"], "flat_confirmed")
        self.assertEqual(self.status(p), "canceled")
        self.assertEqual((m2.pos_qty, self.b.positions()["SYNTH"]["qty"]), (0, 0))
        self.assertTrue(m2.clear_stop(confirm=True)["ok"])
        self.assertTrue(m2.arm("S2", expires_utc=FAR)["ok"])

    def test_session_expiry_ends_flat(self):
        self.start(expires=None)                         # default: session end minus 3900 s
        self.assertEqual(self.m.controls["expires_utc"], "2026-06-01T20:25:00Z")
        self.buy("d1", 10)
        for _ in range(6):
            self.bar()
        c = self.m.controls
        self.assertEqual((c["stopped"], c["flat_confirmed"], c["stop_reason"]), (True, True, "SESSION_EXPIRED"))
        self.assertEqual(self.m.pos_qty, 0)
        m2 = self.restart()
        self.assertTrue(m2.clear_stop(confirm=True)["ok"])
        self.assertTrue(m2.arm("S2")["ok"])
        self.bar()
        self.assertEqual(self.reason(self.buy("d2", 1)), "PAUSED")   # resume is a separate operator step
        self.assertTrue(m2.resume()["ok"])
        self.assertEqual(self.status(self.buy("d3", 1)), "acked")

    def test_stopped_with_outage_refuses_everything_until_flat(self):
        self.long10()
        self.b.set_outage(True)
        r = self.m.stop_and_close()
        self.assertEqual(r["close"], {"state": "pending", "why": "broker unreachable"})
        self.assertEqual(self.m.clear_stop(confirm=True)["reason"], "NOT_FLAT_CONFIRMED")
        self.assertEqual(self.m.arm("S2")["reason"], "STOPPED")
        self.assertEqual(self.m.resume()["reason"], "STOPPED")
        self.assertEqual(self.m.enable_schedule(True)["reason"], "STOPPED")
        iid = self.buy("no", 1)
        self.assertEqual(self.reason(iid), "STOPPED")
        self.b.set_outage(False)
        self.assertEqual(self.bar()["stop"]["state"], "closing")
        self.assertEqual(self.bar()["stop"]["state"], "flat_confirmed")
        self.assertEqual(self.m.pos_qty, 0)


class StopContractV2Tests(DeskCase):
    """v2 contract: only clear_stop(confirm=True) lifts a Stop; nothing else does."""

    def broker_qty(self):
        return self.b.positions()["SYNTH"]["qty"]

    def test_clear_stop_needs_explicit_confirm_and_is_audited(self):
        self.start()
        rep = self.m.stop_and_close()
        self.assertTrue(rep["flat_confirmed"])
        self.assertEqual(self.m.clear_stop()["reason"], "CONFIRM_REQUIRED")
        self.assertEqual(self.m.clear_stop(confirm="yes")["reason"], "CONFIRM_REQUIRED")
        self.assertTrue(self.m.controls["stopped"])
        self.assertTrue(self.m.clear_stop(confirm=True)["ok"])
        self.assertFalse(self.m.controls["stopped"])
        acts = [r.get("action") for r in self.read_audit() if r.get("action", "").startswith("clear_stop")]
        self.assertEqual(acts, ["clear_stop_refused", "clear_stop_refused", "clear_stop"])

    def test_stop_survives_schedule_rearm_restart_and_expiry(self):
        self.start()
        self.assertTrue(self.m.enable_schedule(True)["ok"])
        self.assertTrue(self.m.stop_and_close()["flat_confirmed"])
        self.assertFalse(self.m.controls["schedule_enabled"])
        self.assertEqual(self.m.enable_schedule(True)["reason"], "STOPPED")
        self.assertEqual(self.m.arm("S2", expires_utc=FAR)["reason"], "STOPPED")
        m2 = self.restart()
        self.assertTrue(m2.controls["stopped"])
        for _ in range(13):                              # overnight and the next session
            self.bar()
        self.assertTrue(m2.controls["stopped"])
        self.assertEqual(m2.enable_schedule(True)["reason"], "STOPPED")
        iid = self.buy("after", 1)
        self.assertEqual(self.reason(iid), "STOPPED")
        self.assertEqual(self.b.list_orders()["total"], 0)
        self.assertTrue(m2.clear_stop(confirm=True)["ok"])
        self.assertTrue(m2.controls["paused"])           # clearing a Stop does not unpause
        self.assertTrue(m2.resume()["ok"])
        self.assertTrue(m2.enable_schedule(True)["ok"])

    def test_explicit_expiry_is_kept_and_ends_flat(self):
        self.bar()
        exp = iso(parse_ts(BARS[2]["ts_close"]) + dt.timedelta(minutes=5))
        self.assertTrue(self.m.arm("S1", expires_utc=exp)["ok"])
        self.assertEqual(self.m.controls["expires_utc"], exp)
        self.buy("e1", 10)
        self.bar()
        self.bar()
        self.assertFalse(self.m.controls["stopped"])
        self.bar()                                       # delivered after the expiry
        self.assertTrue(self.m.controls["stopped"])
        self.assertEqual(self.m.controls["stop_reason"], "SESSION_EXPIRED")
        r = self.bar()
        self.assertEqual(r["stop"]["state"], "flat_confirmed")
        self.assertEqual((self.m.pos_qty, self.broker_qty()), (0, 0))

    def test_expiry_after_session_end_flattens_at_next_open(self):
        """session.py passes session end + 5 min. With hourly bars no bar lands in
        that gap, so the position is held overnight under its protective (STATUS gap)."""
        day_end = self.cal.windows(self.cal.local_date(parse_ts(BARS[0]["ts_open"])))[0][1]
        self.bar()
        self.assertTrue(self.m.arm("S1", expires_utc=iso(day_end + dt.timedelta(minutes=5)))["ok"])
        self.buy("long", 10)
        self.bar()
        p = self.protective()
        while self.i < 7:                                # the rest of day 1
            self.bar()
        self.assertFalse(self.m.controls["stopped"])
        self.bar()                                       # day 2's first bar: expired, close sent
        self.assertTrue(self.m.controls["stopped"])
        self.assertEqual(self.status(p), "acked")
        self.assertEqual(self.broker_qty(), 10)
        r = self.bar()
        self.assertEqual(r["stop"]["state"], "flat_confirmed")
        self.assertEqual((self.broker_qty(), self.status(p)), (0, "canceled"))


class StopCloseQATests(DeskCase):
    """Codex QA 16:31Z: no false flat, and protection kept until the close is done."""

    def broker_qty(self):
        return self.b.positions()["SYNTH"]["qty"]

    def broker_status(self, iid):
        return self.b.query(self.m.intents[iid]["client_id"])["status"]

    def test_false_flat_with_foreign_order(self):
        self.start()
        self.b.inject_foreign_order("ext", "buy", 1, limit=50)
        rep = self.m.stop_and_close()
        self.assertFalse(rep["flat_confirmed"])
        self.assertIn("ext", [e["client_id"] for e in rep["external_orders"]])
        self.assertIn(NOT_FLAT_TEXT, rep["status_text"])
        self.assertEqual(self.b.query("ext")["status"], "working")      # never canceled by the desk
        r = self.m.clear_stop(confirm=True)
        self.assertEqual(r["reason"], "NOT_FLAT_CONFIRMED")
        self.assertTrue(any("external" in x for x in r["blockers"]))
        self.assertTrue(self.m.controls["stopped"])
        self.b.cancel("ext")                             # the operator deals with it outside the desk
        self.assertEqual(self.m.poll()["stop"]["state"], "flat_confirmed")
        self.assertTrue(self.m.clear_stop(confirm=True)["ok"])

    def test_false_flat_with_truncated_listing(self):
        self.start()
        self.b.inject_foreign_order("ext", "buy", 1, limit=50)
        self.b.set_fault("truncated_listing", {"limit": 0})
        rep = self.m.stop_and_close()
        self.assertFalse(rep["flat_confirmed"])
        self.assertIn("listing incomplete", rep["status_text"])
        self.assertEqual(self.m.clear_stop(confirm=True)["reason"], "NOT_FLAT_CONFIRMED")

    def test_rejected_close_keeps_protection(self):
        self.long10()
        p = self.protective()
        self.b.set_fault("margin_reject", {"count": 1})
        rep = self.m.stop_and_close()
        self.assertEqual(rep["close"]["state"], "pending")
        self.assertIn("close rejected", rep["close"]["why"])
        self.assertEqual((self.status(p), self.broker_status(p)), ("acked", "working"))
        self.assertEqual(self.broker_qty(), 10)
        r = self.bar()
        self.assertEqual(r["stop"]["state"], "closing")  # retried
        self.assertEqual(self.status(p), "acked")
        r = self.bar()
        self.assertEqual(r["stop"]["state"], "flat_confirmed")
        self.assertEqual((self.broker_qty(), self.status(p)), (0, "canceled"))

    def test_unfilled_close_keeps_protection(self):
        self.long10()
        p = self.protective()
        self.assertEqual(self.m.stop_and_close()["close"]["state"], "closing")
        bar = dict(BARS[self.i], volume=0)               # nothing trades on this bar
        self.i += 1
        self.b.step(bar)
        r = self.m.on_bar(bar)
        self.assertEqual(r["stop"]["state"], "pending")
        self.assertIn("close order working", r["stop"]["why"])
        self.assertEqual((self.status(p), self.broker_qty()), ("acked", 10))
        r = self.bar()
        self.assertEqual(r["stop"]["state"], "flat_confirmed")
        self.assertEqual(self.status(p), "canceled")

    def test_partial_close_keeps_protection_and_never_reverses(self):
        self.long10()
        p = self.protective()
        self.b.set_fault("partial", {"max_fill_qty": 4})
        self.m.stop_and_close()
        seen, last = [], None
        for _ in range(4):
            last = self.bar()
            q = self.broker_qty()
            seen.append(q)
            self.assertGreaterEqual(q, 0)
            if q:
                self.assertEqual(self.status(p), "acked")
            if last.get("stop", {}).get("state") == "flat_confirmed":
                break
        self.assertEqual(seen[:3], [6, 2, 0])
        self.assertEqual(last["stop"]["state"], "flat_confirmed")
        self.assertEqual(self.status(p), "canceled")

    def test_gap_bar_with_close_and_protective_does_not_reverse(self):
        self.long10()
        m = self.m.mark
        self.protective(stop=m - 1.0)
        self.assertEqual(self.m.stop_and_close()["close"]["state"], "closing")
        bar = dict(BARS[self.i], open=m - 5, high=m - 4, low=m - 6, close=m - 4.5)   # both could trade
        self.i += 1
        self.b.step(bar)
        r = self.m.on_bar(bar)
        self.assertEqual((self.broker_qty(), self.m.pos_qty), (0, 0))
        self.assertEqual(r["stop"]["state"], "flat_confirmed")


class PersistenceTests(DeskCase):
    def test_second_manager_is_locked_out(self):
        with self.assertRaises(RuntimeError):
            OrderManager(self.dir, self.b, LIMITS, calendar=self.cal)

    def test_torn_tail_is_repaired(self):
        self.start()
        iid = self.buy("keep", 2, limit=90.0)
        path = os.path.join(self.dir, "intents.jsonl")
        with open(path, "a") as fh:
            fh.write('{"rec": "intent", "intent_id": "torn')
        m2 = self.restart()
        self.assertIn(iid, m2.intents)
        self.assertTrue(os.path.exists(path + ".torn"))
        self.assertNotIn("BAD_RECORD", codes(m2.controls["alarms"]))
        with open(path, "rb") as fh:
            self.assertTrue(fh.read().endswith(b"\n"))

    def test_unreadable_controls_fail_closed(self):
        self.start()
        self.m.close()
        with open(os.path.join(self.dir, "controls.json"), "w") as fh:
            fh.write("not json{")
        m2 = self.new_manager()
        self.m = m2
        c = m2.controls
        self.assertEqual((c["stopped"], c["paused"], c["armed"]), (True, True, False))
        self.assertEqual(c["stop_reason"], "CONTROLS_UNREADABLE")
        self.assertIn("CONTROLS_UNREADABLE", codes(m2.blocking_alarms()))
        self.assertEqual(m2.entry_block_reason(), "STOPPED")


class ReplayTests(DeskCase):
    def test_normal_bars_replay_ends_flat_and_simulated(self):
        days = 10
        for day in range(days):
            for k in range(7):
                self.bar()
                if k == 0:
                    if self.m.controls.get("stopped"):
                        self.assertTrue(self.m.clear_stop(confirm=True)["ok"])
                        self.assertTrue(self.m.resume()["ok"])   # Stop & Close leaves the desk paused
                    self.assertTrue(self.m.arm("S%d" % day)["ok"])
                    self.buy("day%d" % day, 10)
        c = self.m.controls
        self.assertTrue(c["stopped"] and c["flat_confirmed"])
        self.assertEqual((self.m.pos_qty, self.b.positions()["SYNTH"]["qty"]), (0, 0))
        self.assertEqual(len(self.m.fills), 2 * days)    # one entry and one close per day
        self.assertTrue(all(f["mock"] and f["simulated"] for f in self.m.fills))
        rows = self.m.ledger_rows()
        self.assertTrue(rows and all(r["simulated"] for r in rows))
        self.assertTrue(all(f["mock"] and f["simulated"] for r in rows for f in r["fills"]))
        st = self.m.state()
        self.assertTrue(st["simulated"])
        self.assertEqual(st["limits"]["label"], "TEST VALUES")
        with open(os.path.join(self.dir, "audit.jsonl")) as fh:
            audit = [json.loads(x) for x in fh if x.strip()]
        self.assertTrue(audit and all(r["simulated"] for r in audit))
        with open(os.path.join(self.dir, "intents.jsonl")) as fh:
            self.assertTrue(all(json.loads(x)["simulated"] for x in fh if x.strip()))


if __name__ == "__main__":
    unittest.main()
