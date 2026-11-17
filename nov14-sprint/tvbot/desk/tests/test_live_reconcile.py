"""Funded session after the arm ends: the reconcile-only phase works the close until the broker is flat.

The arm ends (its expiry, at the latest the wind-down before the regular close, or the operator's
Stop) while the desk still holds shares. The supervisor must not go idle then. It keeps running the
desk's reconcile_check (book fills, work the reduce-only close and its retries; no bar fetch, no
decision, no entry, no re-arm) until the broker confirms flat, and if that does not happen within
RECONCILE_S it stops with an explicit UNRESOLVED handoff.

Offline only. Every quantity, price and amount is an arbitrary TEST VALUE, not anyone's sizing,
terms or account. The live path uses the real alpaca/live.py gate over TEST VALUE limits in a temp
dir and the in-process fractional venue (alpaca/mock.py MockTrading): no socket, no key, no account,
no order leaves the process.
"""
import datetime as _dt
import os
import sys
import unittest
from pathlib import Path

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.dirname(os.path.abspath(__file__))
for _p in (DESK, TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpaca_session as AS  # noqa: E402
from alpaca import attempts  # noqa: E402
from alpaca import live as L  # noqa: E402
from alpaca import live_supervisor as LS  # noqa: E402
from alpaca import trading_profile as TP  # noqa: E402
from alpaca.mock import MockTrading  # noqa: E402
from orders import qty as Q  # noqa: E402
from test_alpaca_live import NOW, approve_live_dir, shown_hash  # noqa: E402
from test_alpaca_session_night import FixedClock, _Base, _posts, _venue  # noqa: E402

TERMS = dict(fixed_shares=0.002, per_trade_notional=2.0, gross_exposure=2.0,        # TEST VALUES
             daily_loss=0.2, max_loss_per_trade=0.05, max_daily_entries=1)
QTY = "0.002"                                                                       # TEST VALUE
PRICE = 640.0                                                                       # TEST VALUE
CASH = "100.00"                                                                     # TEST VALUE
START = _dt.datetime(2026, 11, 16, 15, 30, 1, tzinfo=_dt.timezone.utc)              # a Monday session


def _bar(a, b, o, close):
    n = int((b - a).total_seconds() / 60)
    return dict(symbol="SPY", source=AS.A.DATA_LABEL_IEX, ts_open=AS.iso(a), ts_close=AS.iso(b),
                exchange_ts=AS.iso(b), open=o, high=max(o, close) + 0.01, low=min(o, close) - 0.01,
                close=close, volume=12000, minutes_expected=n, bar_count_1min=n)


class Held(_Base):
    """An armed fractional live desk that entered TEST VALUE shares and placed its protective stop."""

    def setUp(self):
        super(Held, self).setUp()
        self._root = attempts.ROOT
        attempts.ROOT = Path(self.tmp, "attempt-db")

    def tearDown(self):
        attempts.ROOT = self._root
        super(Held, self).tearDown()

    def frac_authorize(self, live_dir, limits, typed):
        return L.live_gate_authorize(limits, live_dir, L.LIVE_PORT, typed, True, now_utc=NOW,
                                     monotonic=lambda: self.mono[0], shown_hash=shown_hash(limits))

    def held(self, every_s=300, protect_fault=None):
        root = os.path.join(self.tmp, "fixture")
        os.makedirs(root)
        state, limits = approve_live_dir(root, values=TERMS)
        auth = self.frac_authorize(state, limits, L.confirm_phrase(Q.parse(QTY), L.session_date(NOW)))
        trans = self.live_transport(auth)
        clock = FixedClock(START)
        trading = trans._opener.trading = trans.trading = MockTrading(fractional=True, cash=float(CASH))
        trans._opener.asset.update(fractionable=True)
        trans._opener.account = dict(id="fixture-only", cash=CASH, equity=CASH, buying_power=CASH,
                                     non_marginable_buying_power=CASH, status="ACTIVE", account_blocked=False,
                                     trading_blocked=False, trade_suspended_by_user=False)
        c = self.live(auth=auth, transport=trans, clock=clock)
        _venue(c)
        slots, day = [], _dt.date(2026, 10, 23)
        while day <= clock.now().date():
            if c.calendar.is_trading_day(day):
                slots.extend((a, b) for a, b in c.calendar.bar_slots(day, 60) if b <= clock.now())
            day += _dt.timedelta(days=1)
        bars = [_bar(a, b, PRICE - .98 - i * .001, PRICE - .981 - i * .001) for i, (a, b) in enumerate(slots[-72:])]
        c._fetch = lambda after, now: (bars, [])
        AS.read_quote = lambda t, now: dict(valid=True, fresh=True, reason="FRESH", feed="iex", symbol="SPY",
                                           bid=PRICE - .01, ask=PRICE, spread_usd=.01, spread_bps=.16,
                                           quote_utc=AS.iso(now), age_s=0)
        c.check_new_bars()
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])
        self.assertTrue(c.connection_check()["ok"])
        deadline = clock.t + _dt.timedelta(hours=1, minutes=4)
        armed = c.arm(expires_utc=AS.iso(deadline))
        self.assertTrue(armed["ok"], armed)
        sup = LS.LiveSupervisor(c, every_s=every_s)
        clock.t += _dt.timedelta(hours=1)
        _venue(c)
        sig = _bar(clock.t - _dt.timedelta(hours=1, seconds=1), clock.t - _dt.timedelta(seconds=1), PRICE - 1.06, PRICE)
        c._fetch = lambda after, now: ([sig], [])
        sup.tick()                                           # the entry decision on the closed bar
        self.assertEqual([p["side"] for p in _posts(c)], ["buy"], c.decisions[-1])
        c._fetch = lambda after, now: ([], [])
        trading.event_ts = AS.iso(clock.t)
        trading.advance(PRICE)                               # the entry fills
        if protect_fault:
            trading.hide_next = 1
            trading.fault("POST", protect_fault, path_prefix="/v2/orders")
        sup.tick()                                           # books the fill, covers it with the stop
        self.assertEqual(Q.parse(c.mgr.state()["exposure"]["position_qty"]), Q.parse(QTY))
        self.assertEqual(sup.view["phase"], "managing")
        self.c, self.trading, self.sup, self.clock, self.deadline = c, trading, sup, clock, deadline
        return c

    def expire(self):
        """Move the desk clock past the arm's end; the next tick's Check runs Stop & Close."""
        self.clock.t = self.deadline + _dt.timedelta(seconds=2)
        _venue(self.c)
        self.trading.event_ts = AS.iso(self.clock.t)

    def until_done(self, fill=True, limit=None):
        n = 0
        for _ in range(limit or self.sup.reconcile_max + 3):
            if self.sup.view["phase"] in LS._DONE:
                break
            if fill:
                self.trading.advance(PRICE)
            self.sup.tick()
            n += 1
        return n

    def entries(self):
        return [p for p in _posts(self.c) if p["side"] == "buy"]

    def assert_flat(self):
        st = self.c.mgr.state()
        self.assertEqual(self.sup.view["phase"], "flat", self.sup.view)
        self.assertEqual(self.sup.view["state"], LS.FLAT)
        self.assertFalse(self.sup.view["active"])
        self.assertTrue(st["controls"]["flat_confirmed"])
        self.assertEqual(float(st["exposure"]["position_qty"] or 0), 0.0)
        self.assertEqual(float(self.trading.pos_qty), 0.0)
        self.assertFalse(st["armed"])
        self.assertEqual(len(self.entries()), 1)              # no new entry after the arm ended


class AfterExpiry(Held):
    def test_close_fills_and_the_broker_confirms_flat(self):
        self.held()
        self.expire()
        self.sup.tick()                                      # expiry: Stop & Close, the market close goes out
        self.assertFalse(self.c.mgr.state()["armed"])
        self.assertEqual(self.sup.view["phase"], "reconciling", self.sup.view)
        self.assertTrue(self.sup.view["active"])
        self.assertIn("reduce-only", self.sup.view["state"])
        self.until_done()
        self.assert_flat()
        self.assertGreaterEqual(self.sup.view["reconcile_checks"], 1)

    def test_partial_close_fill_is_worked_to_flat(self):
        self.held()
        self.expire()
        self.trading.partial_next = "0.0007"                 # TEST VALUE
        self.sup.tick()
        self.trading.advance(PRICE)
        self.sup.tick()
        self.assertEqual(self.sup.view["phase"], "reconciling")
        self.assertLess(Q.parse(self.c.mgr.state()["exposure"]["position_qty"]), Q.parse(QTY))
        self.trading.partial_next = None
        self.until_done()
        self.assert_flat()

    def test_rejected_close_is_retried_to_flat(self):
        self.held()
        self.expire()
        self.trading.reject_next = "status"
        self.sup.tick()
        self.until_done()
        self.assert_flat()
        sells = [p for p in _posts(self.c) if p["side"] == "sell" and p["type"] == "market"]
        self.assertGreaterEqual(len(sells), 2, sells)

    def lose_close_ack(self):
        self.held()
        self.expire()
        self.trading.hide_next = 1
        self.trading.fault("POST", "lost_ack", path_prefix="/v2/orders")
        self.sup.tick()                                      # the close is sent; its response is lost

    def test_lost_close_ack_is_found_and_ends_flat(self):
        self.lose_close_ack()
        self.trading.reveal()                                # the venue shows the order it accepted
        self.until_done()
        self.assert_flat()
        sells = [p for p in _posts(self.c) if p["side"] == "sell" and p["type"] == "market"]
        self.assertEqual(len(sells), 1, sells)                # found by its client id, never resent

    def test_lost_close_ack_never_seen_is_handed_off_not_resent(self):
        self.lose_close_ack()
        self.until_done()
        self.assertEqual(self.sup.view["phase"], "unresolved", self.sup.view)
        h = self.sup.view["handoff"]
        close = [o for o in h["unsettled_orders"] if o["kind"] == "close"]
        self.assertEqual([o["status"] for o in close], ["uncertain"], h)
        self.assertTrue(close[0]["client_id"])
        sells = [p for p in _posts(self.c) if p["side"] == "sell" and p["type"] == "market"]
        self.assertEqual(len(sells), 1, sells)
        self.assertEqual(len(self.entries()), 1)

    def test_no_fill_ends_in_an_unresolved_handoff(self):
        self.held()
        self.expire()
        self.sup.tick()
        n = self.until_done(fill=False)
        self.assertEqual(self.sup.view["phase"], "unresolved", self.sup.view)
        self.assertEqual(self.sup.view["reconcile_checks"], self.sup.reconcile_max)
        self.assertLessEqual(n, self.sup.reconcile_max + 1)
        self.assertIn("UNRESOLVED", self.sup.view["state"])
        self.assertFalse(self.sup.view["active"])
        h = self.sup.view["handoff"]
        self.assertEqual(Q.parse(h["position_qty"]), Q.parse(QTY))
        self.assertTrue(h["stopped"])
        self.assertFalse(h["flat_confirmed"])
        self.assertTrue(any(o["side"] == "sell" for o in h["working_orders"]), h)
        before = len(self.trading.calls)
        for _ in range(3):
            self.sup.tick()                                  # nothing more is sent after the handoff
        self.assertEqual(len(self.trading.calls), before)
        self.assertEqual(self.c.session_state()["auto_manage"]["phase"], "unresolved")
        self.assertEqual(len(self.entries()), 1)

    def test_reconcile_never_fetches_bars_or_decides(self):
        self.held()
        self.expire()
        self.sup.tick()
        decided = len(self.c.decisions)
        fetched = []
        self.c._fetch = lambda after, now: fetched.append(1) or ([], [])
        self.until_done(fill=False, limit=3)
        self.assertEqual(fetched, [])
        self.assertEqual(len(self.c.decisions), decided)
        self.assertTrue(self.c.last_reconcile["reconcile_only"])


class AfterStop(Held):
    def test_operator_stop_is_reconciled_to_flat(self):
        self.held()
        self.c.stop_and_close()
        self.assertEqual(self.sup.view["phase"], "managing")
        self.sup.tick()                                      # the arm ended between ticks
        self.assertIn(self.sup.view["phase"], ("reconciling", "flat"))
        self.until_done()
        self.assert_flat()


class UncertainProtective(Held):
    """The protective stop's submit response was lost before the arm ended."""

    def test_found_protective_is_cancelled_then_closed_to_flat(self):
        self.held(protect_fault="lost_ack")
        self.expire()
        self.sup.tick()
        self.trading.reveal()
        self.until_done()
        self.assert_flat()

    def test_never_seen_protective_holds_the_close_and_hands_off(self):
        self.held(protect_fault="lost_ack")
        self.expire()
        self.sup.tick()
        self.until_done()
        self.assertEqual(self.sup.view["phase"], "unresolved", self.sup.view)
        h = self.sup.view["handoff"]
        self.assertFalse(h["flat_confirmed"])
        self.assertEqual(self.sup.view["reconcile_checks"], self.sup.reconcile_max)
        self.assertIn("close waits", h["close_pending"])        # nothing sells twice
        prot = [o for o in h["unsettled_orders"] if o["kind"] == "protective"]
        self.assertEqual([o["status"] for o in prot], ["uncertain"], h)
        self.assertEqual([p for p in _posts(self.c) if p["side"] == "sell" and p["type"] == "market"], [])
        self.assertEqual(len(self.entries()), 1)
        self.assertFalse(self.c.mgr.state()["armed"])


if __name__ == "__main__":
    unittest.main()
