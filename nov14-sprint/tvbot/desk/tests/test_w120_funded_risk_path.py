"""W120 fractional risk path under the operator rule: max_loss_per_trade caps price risk to the stop
only; the estimated fees are budgeted separately inside the daily loss cap, together with planned and
working risk.

FractionalRiskPath drives the normal strategy -> controller -> order manager path on the fractional
live fixture: in-process MockTrading, a fixed New York clock, the NoNetworkNoKeys guard, a private temp
state directory and a fictional attempt store. The terms below are FICTITIOUS test figures, used only
to pin the arithmetic; no limits file outside the temp fixture is written and nothing is approved.

ReservationRestart checks, on the generic order manager, that a working entry's est_cost is persisted
with its intent, survives a manager restart and still reserves daily headroom.
"""
import datetime as dt
import os
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, DESK)

import alpaca_session as AS  # noqa: E402
from alpaca import attempts, sizing  # noqa: E402
from alpaca.mock import MockTrading  # noqa: E402
from test_alpaca_live import NOW, approve_live_dir  # noqa: E402
from test_alpaca_session_night import FixedClock, _posts, _venue  # noqa: E402
import test_fractional_session as FS  # noqa: E402  (module import: its TestCase is not re-collected here)
import test_orders_manager as T  # noqa: E402

QTY = "0.0021"
TERMS = dict(fixed_shares=float(QTY), per_trade_notional=1.80, gross_exposure=1.80,
             daily_loss=0.06, max_loss_per_trade=0.03, max_daily_entries=1)   # FICTITIOUS test figures
CASH = 500.0   # synthetic fixture cash and equity, well above any cash-proportional sizing floor


def price_risk(px):
    return float(QTY) * px * 0.015   # 1.5% stop (bot/rules.py DEFAULT_PARAMS)


class FractionalRiskPath(unittest.TestCase):
    def setUp(self):
        self.t = FS.FractionalLive("test_gate_compares_the_exact_fraction")   # used as a fixture only
        self.t.setUp()
        self._root = attempts.ROOT
        attempts.ROOT = Path(self.t.tmp, "fictional-attempt-db")

    def tearDown(self):
        attempts.ROOT = self._root
        self.t.tearDown()

    def run_signal(self, price=750.0, loss=0.0):
        t = self.t
        root = Path(t.tmp, "fixture")
        root.mkdir()
        state, limits = approve_live_dir(str(root), values=TERMS)
        auth = t.frac_authorize(state, limits, AS.L.confirm_phrase(QTY, AS.L.session_date(NOW)))
        trans = t.live_transport(auth)
        clock = FixedClock(NOW + dt.timedelta(minutes=30, seconds=1))   # 10:30 New York, regular session
        trans._opener.trading = trans.trading = MockTrading(fractional=True, cash=CASH)
        trans._opener.asset.update(fractionable=True)
        trans._opener.account = dict(id="fixture-only-account", cash=str(CASH), equity=str(CASH),
                                     buying_power=str(CASH), non_marginable_buying_power=str(CASH),
                                     status="ACTIVE", account_blocked=False, trading_blocked=False,
                                     trade_suspended_by_user=False)
        c = t.live(auth=auth, transport=trans, clock=clock)
        _venue(c)
        day, slots = dt.date(2026, 10, 23), []
        while day <= clock.now().date():
            if c.calendar.is_trading_day(day):
                slots.extend((a, b) for a, b in c.calendar.bar_slots(day, 60) if b <= clock.now())
            day += dt.timedelta(days=1)
        slots = slots[-72:]

        def bar(a, b, o, close):
            n = int((b - a).total_seconds() / 60)
            return dict(symbol="SPY", source=AS.A.DATA_LABEL_IEX, ts_open=AS.iso(a), ts_close=AS.iso(b),
                        exchange_ts=AS.iso(b), open=o, high=max(o, close) + 0.01, low=min(o, close) - 0.01,
                        close=close, volume=12000, minutes_expected=n, bar_count_1min=n)
        hist = [bar(a, b, price - .98 - i * 0.001, price - .981 - i * 0.001) for i, (a, b) in enumerate(slots)]
        c._fetch = lambda after, now: (hist, [])
        AS.read_quote = lambda trans, now: dict(valid=True, fresh=True, reason="FRESH", feed="iex", symbol="SPY",
                                                bid=price - .01, ask=price, spread_usd=.01, spread_bps=.13,
                                                quote_utc=AS.iso(now), age_s=0)   # restored by the fixture
        c.check_new_bars()
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])
        self.assertTrue(c.connection_check()["ok"])
        armed = c.arm()
        self.assertTrue(armed.get("ok"), armed)
        if loss:
            c.mgr.by_day[c.mgr._day_key(None)] = dict(realized=-loss, fees=0.0)
        clock.t += dt.timedelta(hours=1)
        _venue(c)
        sig = bar(clock.now() - dt.timedelta(hours=1, seconds=1), clock.now() - dt.timedelta(seconds=1),
                  price - 1.06, price)
        c._fetch = lambda after, now: ([sig], [])
        c.check_new_bars()
        d = c.decisions[-1]
        self.assertEqual((d.get("action"), d.get("reason_code")), ("enter_long", "CROSS_UP"))
        entries = [it for it in c.mgr.intents.values() if it["kind"] == "entry"]
        self.assertEqual(len(entries), 1)
        return c, d, entries[0], _posts(c)

    def test_entry_at_750_posts_and_carries_its_fees(self):
        c, d, it, posts = self.run_signal()
        chk = [r for r in d["refusal_checks"] if r["id"] == "MAX_LOSS_WOULD_BREACH"][0]
        self.assertTrue(chk["passed"], chk)
        self.assertEqual([(p["side"], p["type"], p["qty"], p["limit_price"]) for p in posts],
                         [("buy", "limit", QTY, "750.00")])
        self.assertEqual(it["status"], "acked")
        cost = d["est_cost"]["usd"]
        self.assertGreater(cost, 0.02)                                   # $0.02 round-trip fees + spread
        self.assertAlmostEqual(it["est_cost"], cost)                     # rides on the intent to the manager
        self.assertAlmostEqual(d["routing"]["risk_usd"], round(price_risk(750), 4))   # price only, 4 dp
        self.assertAlmostEqual(c.mgr._stop_risk(), price_risk(750) + cost, places=6)  # working reserve
        self.assertIsNotNone(it.get("entry_attempt_day"))
        # one RTH entry and the gross cap still hold: a second identical buy is refused
        again = c.mgr.submit_intent({"decision_id": "second", "kind": "entry", "symbol": "SPY", "side": "buy",
                                     "qty": QTY, "ref_price": 750.0, "limit": 750.0,
                                     "invalidation": 738.75, "est_cost": cost})
        self.assertIn(c.mgr.intents[again].get("reason"), ("RISK_GROSS", "DAILY_ENTRY_LIMIT"))
        self.assertEqual(len(_posts(c)), 1)

    def test_per_trade_cap_prior_loss_vetoes_by_daily_worst_case(self):
        c, d, it, posts = self.run_signal(loss=TERMS["max_loss_per_trade"])
        self.assertEqual((it["status"], it.get("reason")), ("rejected", "RISK_DAILY_LOSS_WORST_CASE"))
        self.assertEqual(posts, [])
        self.assertIsNone(it.get("entry_attempt_day"))                   # a veto spends no daily entry
        self.assertNotIn("day_stop", {k: v for k, v in c.mgr.controls.items() if v})

    def test_headroom_edge_is_the_fee_inclusive_daily_sum(self):
        # 0.06 - 0.023625 price risk - est cost (about 0.0209) leaves about $0.0154 of prior loss.
        _, d, it, posts = self.run_signal(loss=0.0154)
        self.assertEqual(it["status"], "acked")
        self.assertEqual(len(posts), 1)
        self.assertLessEqual(0.0154 + price_risk(750) + d["est_cost"]["usd"], TERMS["daily_loss"])

    def test_headroom_edge_just_over_vetoes(self):
        _, d, it, posts = self.run_signal(loss=0.0155)
        self.assertEqual(it.get("reason"), "RISK_DAILY_LOSS_WORST_CASE")
        self.assertEqual(posts, [])
        self.assertGreater(0.0155 + price_risk(750) + d["est_cost"]["usd"], TERMS["daily_loss"])

    def test_band_edges_pass_price_only_cap(self):
        for px in (476.20, 857.14):   # $1 minimum and the per-trade notional cap at 0.0021 sh
            with self.subTest(price=px):
                self.tearDown()
                self.setUp()
                _, d, it, posts = self.run_signal(price=px)
                self.assertEqual(it["status"], "acked", px)
                self.assertLessEqual(d["routing"]["risk_usd"], TERMS["max_loss_per_trade"])
                self.assertGreater(price_risk(px) + d["est_cost"]["usd"], TERMS["max_loss_per_trade"])
                self.assertEqual(len(posts), 1)


class ReservationRestart(T.DeskCase):
    def test_working_entry_fee_reserve_survives_restart(self):
        self.start()
        mark = self.m.mark
        iid = self.buy("w1", 1, limit=mark - 5.0, invalidation=mark - 14.0, est_cost=20.0)   # 9 + 20 working
        self.assertEqual(self.status(iid), "acked")
        self.assertAlmostEqual(self.m._stop_risk(), 29.0)
        self.restart()
        self.bar()
        self.m.arm("S1", expires_utc=T.FAR)
        self.assertAlmostEqual(self.m.intents[iid]["est_cost"], 20.0)
        self.assertAlmostEqual(self.m._stop_risk(), 29.0)
        nxt = self.buy("w2", 1, limit=self.m.mark, invalidation=self.m.mark - 0.6, est_cost=0.5)   # 29 + 1.1 > 30
        self.assertEqual(self.reason(nxt), "RISK_DAILY_LOSS_WORST_CASE")

    def test_open_position_reserves_its_unbooked_exit_fee(self):
        self.start()
        iid = self.buy("long", 10, est_cost=6.0)
        self.bar()
        self.assertEqual(self.m.pos_qty, 10)
        booked = self.m.intents[iid].get("fees", 0.0)
        self.assertAlmostEqual(self.m._open_fee_reserve(), max(0.0, 6.0 - booked))
        self.assertEqual(self.status(self.protective()), "acked")          # 10 x 1.00 = 10 to the stop
        # booked fees + 10 stop + (6 - booked) exit-fee reserve + 9 price risk + 5.5 fees = 30.5 > 30;
        # without the reserve it would be 24.5 and pass.
        nxt = self.buy("add", 1, limit=self.m.mark, invalidation=self.m.mark - 9.0, est_cost=5.5)
        self.assertEqual(self.reason(nxt), "RISK_DAILY_LOSS_WORST_CASE")
        ok = self.buy("add2", 1, limit=self.m.mark - 5.0, invalidation=self.m.mark - 14.0, est_cost=4.5)  # 29.5
        self.assertEqual(self.status(ok), "acked")        # rests below the market; a working entry is not
                                                          # double-counted in the exit-fee reserve
        self.restart()
        self.bar()
        self.assertAlmostEqual(self.m._open_fee_reserve(), max(0.0, 6.0 - booked))


class PlannerPreview(unittest.TestCase):
    """The Setup panel preview applies the same split: per-trade = price risk, daily = price risk + costs."""

    def test_fractional_terms_preview(self):
        e = sizing.effects(TERMS, ref_price=750.0, stop_distance=11.25, fee_per_share=5.0)   # costs 0.021
        chk = {c["cap"]: c for c in e["checks"]}
        self.assertTrue(chk["max_loss_per_trade"]["ok"], chk["max_loss_per_trade"])      # 0.023625 <= 0.03
        self.assertIn("count against the daily cap", chk["max_loss_per_trade"]["reason"])
        self.assertTrue(chk["daily_loss"]["ok"])                                           # 0.044625 <= 0.06
        late = sizing.effects(TERMS, ref_price=750.0, stop_distance=11.25, fee_per_share=5.0,
                              realized_loss_today=0.03)
        self.assertFalse({c["cap"]: c for c in late["checks"]}["daily_loss"]["ok"])       # 0.074625 > 0.06

    def test_price_risk_over_cap_still_flagged(self):
        e = sizing.effects(TERMS, ref_price=750.0, stop_distance=15.0)                     # 0.0315 > 0.03
        self.assertFalse({c["cap"]: c for c in e["checks"]}["max_loss_per_trade"]["ok"])

    def test_share_suggestion_uses_price_risk(self):
        whole = dict(fixed_shares=1, max_loss_per_trade=10.0, daily_loss=30.0, per_trade_notional=2000.0,
                     gross_exposure=2000.0)
        e = sizing.effects(whole, ref_price=400.0, stop_distance=2.0, fee_per_share=0.01)
        self.assertEqual(e["suggestions"][0]["shares"], 5)       # floor(10 / 2); fees go to the daily cap


if __name__ == "__main__":
    unittest.main()
