"""Fractional share size through the Alpaca controller, the live gate and the preflight rows.

Offline only. Every quantity and amount here is an arbitrary TEST VALUE, not anyone's sizing or
account. The live path uses the real alpaca/live.py gate over TEST VALUE limits in a temp dir and
the in-process venue from test_alpaca_session_night (its NoNetworkNoKeys guard covers these
tests): no socket, no key, no account, no order leaves the process. Operational readiness only;
it says nothing about edge.
"""
import json
import os
import sys
import unittest
from decimal import Decimal

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.dirname(os.path.abspath(__file__))
for _p in (DESK, TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpaca_session as AS  # noqa: E402
import session as S  # noqa: E402
from alpaca import live as L  # noqa: E402
from orders import qty as Q  # noqa: E402
from test_alpaca_live import NOW, TEST_LIVE_VALUES, approve_live_dir, shown_hash  # noqa: E402
from test_alpaca_session_night import _Base  # noqa: E402

FRAC = Decimal("0.37")                                                         # TEST VALUE
FRAC_VALUES = dict(TEST_LIVE_VALUES, fixed_shares=0.37, max_daily_entries=2)   # TEST VALUES
SYNTH_AMOUNT = "4321.98"                                                       # TEST VALUE
ASSET = {"symbol": "SPY", "tradable": True, "status": "active"}


def _entry(decision_id, qty):
    return {"decision_id": decision_id, "action": "enter_long", "qty": qty,
            "intended_entry": 400.0, "invalidation": 399.0}


def _armed_flat():
    return {"armed": True, "controls": {"stopped": False, "paused": False},
            "exposure": {"position_qty": 0, "working_orders": []}}


def _account(**kw):
    a = {"status": "ACTIVE", "trading_blocked": False, "account_blocked": False,
         "trade_suspended_by_user": False, "cash": SYNTH_AMOUNT,
         "non_marginable_buying_power": SYNTH_AMOUNT}
    a.update(kw)
    return a


def _live_broker(*a):
    return AS._need("alpaca.broker", "AlpacaLiveBroker")(*a)


def _rows(c):
    return {r["check"]: r for r in c.preflight()}


class Phrase(unittest.TestCase):
    def test_whole_share_phrase_is_byte_identical(self):
        self.assertEqual(L.confirm_phrase(3, "2026-11-16"), "LIVE SPY 3 SHARES 2026-11-16")
        self.assertEqual(L.confirm_phrase("3", "2026-11-16"), "LIVE SPY 3 SHARES 2026-11-16")

    def test_fractional_phrase_is_exact_text(self):
        self.assertEqual(L.confirm_phrase(Decimal("0.370"), "2026-11-16"), "LIVE SPY 0.37 SHARES 2026-11-16")
        self.assertEqual(L.confirm_phrase(0.37, "2026-11-16"), "LIVE SPY 0.37 SHARES 2026-11-16")


class Eligibility(unittest.TestCase):
    def test_fractionable_must_be_exactly_true_in_fractional_mode(self):
        for bad in ({}, {"fractionable": False}, {"fractionable": None}, {"fractionable": "true"}):
            why = AS._eligibility("asset", dict(ASSET, **bad), fractional=True)
            self.assertIn("FRACTIONABLE_UNVERIFIED", why or "", bad)
        self.assertIsNone(AS._eligibility("asset", dict(ASSET, fractionable=True), fractional=True))

    def test_whole_share_asset_check_unchanged(self):
        self.assertIsNone(AS._eligibility("asset", ASSET))
        self.assertIsNone(AS._eligibility("asset", dict(ASSET, fractionable=False)))

    def test_cash_readable_is_a_flag_only(self):
        self.assertTrue(AS._cash_readable(_account()))
        for bad in ({"cash": None}, {"non_marginable_buying_power": "n/a"}, {"cash": True}, {"cash": "NaN"}):
            self.assertFalse(AS._cash_readable(_account(**bad)), bad)


class FractionalLive(_Base):
    def frac_limits(self):
        root = os.path.join(self.tmp, "frac")
        os.makedirs(root, exist_ok=True)
        return approve_live_dir(root, values=FRAC_VALUES)

    def frac_authorize(self, live_dir, limits, typed):
        return L.live_gate_authorize(limits, live_dir, L.LIVE_PORT, typed, True, now_utc=NOW,
                                     monotonic=lambda: self.mono[0], shown_hash=shown_hash(limits))

    def frac_live(self, **kw):
        live_dir, limits = self.frac_limits()
        auth = self.frac_authorize(live_dir, limits, L.confirm_phrase(FRAC, L.session_date(NOW)))
        return self.live(auth=auth, **kw)

    def test_gate_compares_the_exact_fraction(self):
        live_dir, limits = self.frac_limits()
        today = L.session_date(NOW)
        for wrong in ("LIVE SPY 0 SHARES %s" % today, "LIVE SPY 1 SHARES %s" % today,
                      "LIVE SPY 0.3 SHARES %s" % today):
            with self.assertRaises(L.LiveGateRefused, msg=wrong):
                self.frac_authorize(live_dir, limits, wrong)
        auth = self.frac_authorize(live_dir, limits, "LIVE SPY 0.37 SHARES %s" % today)
        self.assertEqual(auth.shares, FRAC)
        self.assertIn("0.37 shares", repr(auth))

    def test_exact_size_daily_max_and_cost_profile_reach_the_controller(self):
        c = self.frac_live()
        self.assertEqual(Q.parse(c.strategy_cfg["fixed_qty"]), FRAC)
        self.assertEqual(c.strategy_cfg.get("cost_profile"), "alpaca_equity")
        self.assertIs(c.strategy_cfg.get("fractional"), True)
        self.assertEqual(c.mgr.limits.get("max_daily_entries"), 2)
        ok, why = c._limits_intact()
        self.assertTrue(ok, why)
        rows = _rows(c)
        self.assertIn("fixed 0.37 share(s)", rows["limits loaded"]["detail"])
        self.assertIn("fractional 0.37 shares (DAY, simple orders)", rows["sizing"]["detail"])
        self.assertEqual(rows["sizing"]["ok"], bool(getattr(c.broker, "fractional", False)))
        if not rows["sizing"]["ok"]:
            self.assertIn("FRACTIONAL_NOT_ENABLED", rows["sizing"]["detail"])
        self.assertTrue(rows["daily entries"]["ok"], rows["daily entries"])
        self.assertTrue(rows["daily entries"]["detail"].startswith("0 of 2 today"))

    def test_broker_is_built_with_fractional_true(self):
        seen = []

        def factory(*a, **kw):
            seen.append(kw)
            b = _live_broker(*a)
            b.fractional = bool(kw.get("fractional"))
            return b
        c = self.frac_live(broker_factory=factory)
        self.assertEqual(seen, [{"fractional": True}])
        self.assertTrue(_rows(c)["sizing"]["ok"])

    def test_fractionable_unverified_blocks_arm(self):
        c = self.frac_live()
        rows = _rows(c)
        self.assertFalse(rows["SPY fractionable"]["ok"])
        self.assertIn("FRACTIONABLE_UNVERIFIED", rows["SPY fractionable"]["detail"])
        self.assertFalse(rows["non-margin cash"]["ok"])
        venue = c.transport._opener
        venue.account = _account()
        for asset in (dict(ASSET), dict(ASSET, fractionable=False)):
            venue.asset = asset
            cc = c.connection_check()
            self.assertFalse(cc["ok"])
            asset_row = [r for r in cc["checks"] if r["check"] == "asset"][0]
            self.assertIn("FRACTIONABLE_UNVERIFIED", asset_row["detail"])
            rows = _rows(c)
            self.assertFalse(rows["SPY fractionable"]["ok"])
            self.assertIn("FRACTIONABLE_UNVERIFIED", rows["SPY fractionable"]["detail"])
            res = c.arm()
            self.assertFalse(res["ok"])
            self.assertEqual(res.get("reason"), "PREFLIGHT")
            self.assertIn("SPY fractionable", [f["check"] for f in res.get("failed", [])])

    def test_fractionable_true_and_cash_checked_without_amounts(self):
        c = self.frac_live()
        venue = c.transport._opener
        venue.account = _account()
        venue.asset = dict(ASSET, fractionable=True)
        cc = c.connection_check()
        self.assertTrue(cc["ok"], cc)
        self.assertNotIn(SYNTH_AMOUNT, json.dumps(cc, default=str))
        rows = _rows(c)
        self.assertTrue(rows["SPY fractionable"]["ok"], rows["SPY fractionable"])
        self.assertTrue(rows["non-margin cash"]["ok"], rows["non-margin cash"])
        self.assertNotIn(SYNTH_AMOUNT, json.dumps(rows, default=str))
        venue.account = _account(non_marginable_buying_power=None)
        cc = c.connection_check()
        self.assertFalse(cc["ok"])
        rows = _rows(c)
        self.assertFalse(rows["non-margin cash"]["ok"])
        self.assertIn("CASH_UNAVAILABLE", rows["non-margin cash"]["detail"])

    def test_daily_entries_at_max_says_exits_stay_available(self):
        c = self.frac_live()
        st = c.mgr.state()
        st["daily_entries"] = {"used": 2, "max": 2, "day": "2026-11-16"}
        c.mgr.state = lambda: st
        row = _rows(c)["daily entries"]
        self.assertTrue(row["ok"])
        self.assertIn("2 of 2 today", row["detail"])
        self.assertIn("exits stay available", row["detail"])

    def test_fractional_entry_refused_by_a_whole_share_broker(self):
        c = self.frac_live()
        c.broker.fractional = False
        res = c._route(_entry("dec-test-frac", 0.37), {"close": 400.0}, _armed_flat())
        self.assertEqual(res["status"], "rejected")
        self.assertEqual(res["why"], "FRACTIONAL_NOT_ENABLED")
        self.assertIn("0.37-share entry", res["detail"])
        self.assertEqual([b for (m, p, q, b) in c.transport.trading.calls
                          if m == "POST" and p == "/v2/orders"], [])

    def test_protection_view_is_exact_for_a_fractional_position(self):
        c = self.frac_live()
        st = c.mgr.state()
        st["exposure"]["position_qty"] = 0.37
        st["exposure"]["working_orders"] = []
        st["protective_orders"] = [{"side": "sell", "remaining": 0.12, "kind": "protective"}]
        c.mgr.state = lambda: st
        pv = c._protection_view()
        self.assertEqual(Q.parse(pv["position_qty"]), FRAC)
        self.assertEqual(Q.parse(pv["protective_qty"]), Decimal("0.12"))
        self.assertEqual(Q.parse(pv["uncovered_qty"]), Decimal("0.25"))
        self.assertIn("0.25 of 0.37 booked SPY shares", pv["warning"])


class WholeShareUnchanged(_Base):
    def test_whole_share_desk_has_no_new_failing_rows_or_cost_keys(self):
        c = self.live()
        self.assertNotIn("cost_profile", c.strategy_cfg)
        self.assertNotIn("fractional", c.strategy_cfg)
        rows = _rows(c)
        self.assertEqual(rows["sizing"], {"check": "sizing", "ok": True, "detail": "whole 1 shares"})
        for name in ("SPY fractionable", "non-margin cash", "daily entries"):
            self.assertNotIn(name, rows)
        cc = c.connection_check()
        self.assertNotIn("non-margin cash", [r["check"] for r in cc["checks"]])
        self.assertTrue([r for r in cc["checks"] if r["check"] == "asset"][0]["ok"])

    def test_whole_share_broker_built_without_the_kwarg(self):
        seen = []

        def factory(*a, **kw):
            seen.append(kw)
            return _live_broker(*a)
        self.live(broker_factory=factory)
        self.assertEqual(seen, [{}])

    def test_whole_share_protection_view_unchanged(self):
        c = self.live()
        st = c.mgr.state()
        st["exposure"]["position_qty"] = 3
        st["exposure"]["working_orders"] = []
        st["protective_orders"] = [{"side": "sell", "remaining": 1, "kind": "protective"}]
        c.mgr.state = lambda: st
        pv = c._protection_view()
        self.assertEqual((pv["position_qty"], pv["uncovered_qty"]), (3, 2))
        self.assertIs(type(pv["uncovered_qty"]), int)
        self.assertIn("2 of 3 booked SPY shares", pv["warning"])


class OfflineDesk(_Base):
    def test_offline_desk_refuses_a_fractional_entry(self):
        c = S.SessionController(state_dir=os.path.join(self.tmp, "offline"), strategy="ema")
        self.ctrls.append(c)
        self.assertFalse(getattr(c.broker, "fractional", False))
        res = c._route(_entry("dec-test-offline", 0.37), {"close": 400.0}, _armed_flat())
        self.assertEqual(res["why"], "FRACTIONAL_NOT_ENABLED")

    def test_session_json_keeps_decimal_exact(self):
        self.assertEqual(json.loads(json.dumps({"q": FRAC}, default=Q.json_default_str)), {"q": 0.37})


if __name__ == "__main__":
    unittest.main()
