"""Profile sizing: every new buy is sized from this account's own available cash under the shared
Balanced DNA / Moderate risk profile (alpaca/trading_profile.py, alpaca/sizing.profile_size).

Paper: the size scales with the paper account's cash (SHARES_PER_USD x available), paper's own caps
are recomputed from that cash on every entry, and cost and risk are recalculated on the resulting
quantity; the worksheet size only signals the entry. Live: the size is never above the approved size,
the approved caps stay as signed, and a size the venue cannot take is an explicit pass.

Offline only. Every quantity, balance and limit here is a FICTITIOUS TEST VALUE, not anyone's sizing
or account. The connected paths use the in-process venues from test_alpaca_session_night (no socket,
no key, no order leaves the process). Operational readiness only; it says nothing about edge.
"""
import copy
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

import alpaca as A  # noqa: E402
import alpaca_session as AS  # noqa: E402
import session as S  # noqa: E402
from alpaca import live as L  # noqa: E402
from alpaca import sizing as Z  # noqa: E402
from alpaca import trading_profile as TP  # noqa: E402
from orders import qty as Q  # noqa: E402
from strategies import base as B  # noqa: E402
from test_alpaca_live import NOW, approve_live_dir, shown_hash  # noqa: E402
from test_alpaca_session_night import _Base, _TestBroker, _mock_transport  # noqa: E402
from test_fractional_session import _account, _armed_flat  # noqa: E402

PRICE = 600.0                                                                   # TEST VALUE
STOP = 590.0                                                                    # TEST VALUE
LIVE_QTY = Decimal("0.0021")                                                    # TEST VALUE
LIVE_TERMS = {"fixed_shares": 0.0021, "max_daily_entries": 1, "max_loss_per_trade": 0.03,
              "daily_loss": 0.06, "per_trade_notional": 1.80, "gross_exposure": 1.80}  # FICTITIOUS
LEGACY_WORKSHEET = {"fixed_shares": 1, "per_trade_notional": 1000.0, "gross_exposure": 2000.0,
                    "max_loss_per_trade": 20.0, "daily_loss": 50.0}           # FICTITIOUS


def _bal(cash, equity=None, nmbp=None, **kw):
    b = {"cash": cash, "equity": cash if equity is None else equity,
         "non_marginable_buying_power": cash if nmbp is None else nmbp}
    b.update(kw)
    return b


def _paper_size(cash, price=PRICE, stop=STOP, working=0, **kw):
    return Z.profile_size(_bal(cash, **kw), working, price, stop=stop)


class Profile(unittest.TestCase):
    def test_paper_caps_scale_with_available_cash(self):
        self.assertEqual(TP.paper_caps(Decimal("100000")),
                         {"per_trade_notional": 2300.0, "gross_exposure": 2300.0,
                          "max_loss_per_trade": 40.0, "daily_loss": 100.0})
        self.assertEqual(TP.paper_caps(Decimal("25000")),
                         {"per_trade_notional": 575.0, "gross_exposure": 575.0,
                          "max_loss_per_trade": 10.0, "daily_loss": 25.0})
        self.assertEqual(TP.paper_caps(Decimal("12345.67"))["max_loss_per_trade"], 4.93)   # floored

    def test_describe_both_modes(self):
        p, lv = TP.describe("paper"), TP.describe("live")
        for d in (p, lv):
            self.assertEqual((d["id"], d["label"], d["version"]), (TP.PROFILE_ID, TP.LABEL, TP.VERSION))
            self.assertEqual(d["pace"]["signal_check_s"], TP.SIGNAL_CHECK_S)
            self.assertEqual(d["pace"]["protect_check_s"], TP.PROTECT_CHECK_S)
        self.assertIn("recomputed", p["risk"]["caps"])
        self.assertIn("unchanged", lv["risk"]["caps"])
        self.assertIn("never above the approved", lv["summary"])

    def test_quote_age_comes_from_the_profile(self):
        from alpaca import readiness
        self.assertEqual(readiness.MAX_QUOTE_AGE, TP.MAX_QUOTE_AGE_S)
        self.assertEqual(AS.BAR_MAX_AGE_S, float(TP.BAR_MAX_AGE_S))


class Helper(unittest.TestCase):
    def test_paper_scales_forward_with_its_own_cash(self):
        q, info, caps = _paper_size("100000.00")
        self.assertEqual(q, Decimal("2.8"))
        self.assertEqual(info["binding"], "profile")
        self.assertEqual(info["mode"], "paper")
        self.assertEqual(caps["per_trade_notional"], 2300.0)
        q, info, caps = _paper_size("25000.00")
        self.assertEqual(q, Decimal("0.7"))
        self.assertEqual(info["binding"], "profile")
        self.assertEqual(caps["max_loss_per_trade"], 10.0)

    def test_tighter_stop_risk_cuts_the_paper_size(self):
        q, info, _ = _paper_size("100000.00", stop=PRICE - 20.0)
        self.assertEqual(q, Decimal("2"))            # $40 stop risk cap / $20 to the stop
        self.assertEqual(info["binding"], "stop_risk")

    def test_notional_and_gross_caps_cut_the_paper_size(self):
        q, info, _ = _paper_size("100000.00", price=1000.0, stop=999.0)
        self.assertEqual(q, Decimal("2.3"))          # $2,300 notional cap / $1,000
        self.assertEqual(info["binding"], "notional")
        q, info, _ = Z.profile_size(_bal("100000.00"), 0, PRICE, stop=STOP, gross_used_usd=1700)
        self.assertEqual(q, Decimal(1))              # ($2,300 - $1,700 used) / $600
        self.assertEqual(info["binding"], "gross")

    def test_lower_equity_or_nonmargin_sizes_from_it(self):
        self.assertEqual(_paper_size("100000.00", equity="25000.00")[0], Decimal("0.7"))
        self.assertEqual(_paper_size("100000.00", nmbp="25000.00")[0], Decimal("0.7"))

    def test_margin_buying_power_never_adds(self):
        self.assertEqual(_paper_size("25000.00", buying_power="200000.00")[0], Decimal("0.7"))
        self.assertEqual(_paper_size("100000.00", buying_power="25000.00")[0], Decimal("0.7"))

    def test_working_buys_reduce_available(self):
        q, _, caps = _paper_size("100000.00", working=Decimal("75000"))
        self.assertEqual(q, Decimal("0.7"))
        self.assertEqual(caps["per_trade_notional"], 575.0)
        q, info, _ = _paper_size("100000.00", working=Decimal("120000"))
        self.assertIsNone(q)
        self.assertEqual(info["code"], Z.CASH_SCALED_TO_ZERO)

    def test_whole_share_desk_floors_to_whole(self):
        q, _, _ = Z.profile_size(_bal("100000.00"), 0, PRICE, stop=STOP, fractional=False)
        self.assertEqual(q, 2)
        q, info, _ = Z.profile_size(_bal("25000.00"), 0, PRICE, stop=STOP, fractional=False)
        self.assertIsNone(q)
        self.assertEqual(info["code"], Z.CASH_SCALED_TO_ZERO)

    def test_unreadable_or_missing_balance_is_unverified(self):
        for bad in ({"cash": None}, {"equity": "nan"}, {"non_marginable_buying_power": "-1"},
                    {"cash": True}, {"buying_power": None}, {"equity": "x"}):
            b = _bal("100000.00")
            b.update(bad)
            q, info, caps = Z.profile_size(b, 0, PRICE, stop=STOP)
            self.assertIsNone(q, bad)
            self.assertIsNone(caps, bad)
            self.assertEqual(info["code"], Z.CASH_UNVERIFIED, bad)
        b = _bal("100000.00")
        del b["equity"]
        self.assertEqual(Z.profile_size(b, 0, PRICE)[1]["code"], Z.CASH_UNVERIFIED)
        self.assertEqual(Z.profile_size(_bal("100000.00"), 0, 0)[1]["code"], Z.CASH_UNVERIFIED)

    def test_live_never_above_the_approved_size(self):
        q, info, caps = Z.profile_size(_bal("100000.00"), 0, PRICE, stop=STOP, approved_qty=LIVE_QTY)
        self.assertEqual(q, LIVE_QTY)
        self.assertEqual(info["binding"], "approved")
        self.assertEqual(info["mode"], "live")
        self.assertIsNone(caps)

    def test_live_lower_cash_reduces_then_passes_below_the_minimum(self):
        q, info, _ = Z.profile_size(_bal("60.00"), 0, PRICE, stop=STOP, approved_qty=LIVE_QTY)
        self.assertEqual(q, Decimal("0.00168"))
        self.assertEqual(info["binding"], "profile")
        q, info, _ = Z.profile_size(_bal("40.00"), 0, PRICE, stop=STOP, approved_qty=LIVE_QTY)
        self.assertIsNone(q)
        self.assertEqual(info["sized_qty"], 0.00112)
        self.assertEqual(info["code"], Z.CASH_SCALED_BELOW_MIN)
        self.assertEqual(info["notional_usd"], 0.67)

    def test_info_carries_no_balance(self):
        _, info, _ = Z.profile_size(_bal("24371.17", equity="31193.29", nmbp="27531.41"), Decimal("1071.03"),
                                    PRICE, stop=STOP)
        blob = json.dumps(info)
        for amount in ("24371", "31193", "27531", "23300", "1071"):
            self.assertNotIn(amount, blob)


def _fractional_factory(transport, state_dir, label, adapter_state, fractional=False):
    return _TestBroker(transport, state_dir, A.LABEL_MOCK_LOCAL, adapter_state, fractional=fractional)


class PaperRoute(_Base):
    """The connected paper desk on a legacy 1-share worksheet: the profile size, not the worksheet's."""

    def paper(self, sub="paper-prof", factory=_fractional_factory, cash="100000.00", lim_dir=None):
        sd = os.path.join(self.tmp, sub)
        if lim_dir is None:
            lim_dir, _snap = self.snapshot(sub + "-lim", **LEGACY_WORKSHEET)
        self.lim_dir = lim_dir
        c = AS.AlpacaSessionController(sd, strategy="ema", mode="https", transport=_mock_transport(),
                                       broker_factory=factory, limits_path=Z.approved_path(lim_dir),
                                       clock=AS.MockClock(sd, AS.SessionCalendar.nyse_2026_2027()))
        self.ctrls.append(c)
        self.fund(c, cash)
        return c

    @staticmethod
    def fund(c, cash):
        t = c.transport.trading
        t.cash = t.equity = t.non_marginable_buying_power = cash

    @staticmethod
    def _d(decision_id, qty=1, stop=STOP):
        return {"decision_id": decision_id, "action": "enter_long", "qty": qty,
                "intended_entry": PRICE, "invalidation": stop}

    def test_paper_is_built_for_the_profile(self):
        c = self.paper()
        self.assertTrue(c._profile_paper)
        self.assertTrue(c.broker.fractional)
        self.assertEqual(c.strategy_cfg.get("cost_profile"), "alpaca_equity")
        self.assertNotIn("limits", c.strategy_cfg)
        self.assertEqual(c.limits.get("max_daily_entries"), TP.PAPER_MAX_DAILY_ENTRIES)

    def test_each_entry_scales_forward_from_this_accounts_cash(self):
        c = self.paper()
        d = self._d("dec-test-prof-100k")
        self.assertIsNone(c._cash_size(d, {"close": PRICE}, _armed_flat()))
        self.assertEqual(Q.parse(d["qty"]), Decimal("2.8"))
        self.assertEqual(d["cash_sizing"]["signal_qty"], 1)
        self.assertEqual(d["profile"]["id"], TP.PROFILE_ID)
        self.assertEqual(d["profile"]["mode"], "paper")
        self.assertEqual(d["operative_caps"]["per_trade_notional"], 2300.0)
        self.fund(c, "25000.00")
        d2 = self._d("dec-test-prof-25k")
        self.assertIsNone(c._cash_size(d2, {"close": PRICE}, _armed_flat()))
        self.assertEqual(Q.parse(d2["qty"]), Decimal("0.7"))
        self.assertEqual(d2["operative_caps"]["max_loss_per_trade"], 10.0)
        self.assertEqual(c._operative_caps["per_trade_notional"], 575.0)

    def test_cost_and_risk_are_recalculated_on_the_resulting_qty(self):
        c = self.paper()
        d = self._d("dec-test-prof-cost")
        d["est_cost"] = B.est_cost(1, PRICE, B.cost_cfg(c.strategy_cfg), sides=2)
        c._cash_size(d, {"close": PRICE}, _armed_flat())
        want = B.est_cost("2.8", PRICE, B.cost_cfg(c.strategy_cfg), sides=2,
                          note="round trip for the profile size")
        self.assertEqual(d["est_cost"], want)
        self.assertGreater(d["est_cost"]["usd"], 0)
        self.assertEqual(d["price_risk_usd"], 28.0)

    def test_tighter_stop_cuts_the_size_and_its_risk(self):
        c = self.paper()
        d = self._d("dec-test-prof-stop", stop=PRICE - 20.0)
        c._cash_size(d, {"close": PRICE}, _armed_flat())
        self.assertEqual(Q.parse(d["qty"]), Decimal("2"))
        self.assertEqual(d["cash_sizing"]["binding"], "stop_risk")
        self.assertEqual(d["price_risk_usd"], 40.0)

    def test_caps_in_force_on_desk_manager_and_broker(self):
        c = self.paper()
        c._cash_size(self._d("dec-test-prof-caps"), {"close": PRICE}, _armed_flat())
        for k, v in (("per_trade_notional", 2300.0), ("gross_exposure", 2300.0),
                     ("max_loss_per_trade", 40.0), ("daily_loss", 100.0)):
            self.assertEqual(c._operative_caps[k], v)
            self.assertEqual(c.mgr.limits[k], v)
        self.assertEqual(c.broker.exec_caps, {"per_trade_notional": 2300.0, "gross_exposure": 2300.0})

    def test_session_state_shows_the_operative_profile(self):
        c = self.paper()
        prof = c.session_state()["trading_profile"]
        self.assertEqual((prof["id"], prof["mode"]), (TP.PROFILE_ID, "paper"))
        self.assertTrue(prof["applied"])
        self.assertIsNone(prof["operative_caps"])
        c._cash_size(self._d("dec-test-prof-state"), {"close": PRICE}, _armed_flat())
        prof = c.session_state()["trading_profile"]
        self.assertEqual(prof["operative_caps"]["daily_loss"], 100.0)

    def test_preflight_sizing_row_needs_no_connection_check(self):
        c = self.paper()
        rows = {r["check"]: r for r in c.preflight()}
        self.assertTrue(rows["sizing"]["ok"], rows["sizing"])
        self.assertIn(TP.LABEL, rows["sizing"]["detail"])
        self.assertIn("fractional DAY simple orders", rows["sizing"]["detail"])
        for k in ("SPY fractionable", "non-margin cash"):
            self.assertNotIn(k, rows)

    def test_unreadable_cash_is_a_pass_with_no_order(self):
        c = self.paper()
        c.transport.trading.account_omit = {"equity"}
        c.transport.trading.equity = None
        c.transport.trading.cash = "not-a-number"
        res = c._route(self._d("dec-test-prof-unver"), {"close": PRICE}, _armed_flat())
        self.assertEqual((res["status"], res["why"]), ("rejected", Z.CASH_UNVERIFIED))
        self.assertIn("Pass:", res["detail"])
        self.assertEqual([b for (m, p, q, b) in c.transport.trading.calls
                          if m == "POST" and p == "/v2/orders"], [])
        self.assertIsNone(c._operative_caps)

    def test_legacy_state_restarts_on_the_profile(self):
        sub = "paper-legacy"
        c = self.paper(sub)
        c.close()
        path = os.path.join(self.tmp, sub, S.SESSION_CONFIG_FILE)
        with open(path) as fh:
            have = json.load(fh)
        sc = have["strategy_cfg"]
        for k in ("fractional", "cost_profile"):
            sc.pop(k, None)
        sc["limits"] = {k: LEGACY_WORKSHEET[k] for k in
                        ("per_trade_notional", "max_loss_per_trade", "daily_loss", "gross_exposure")}
        with open(path, "w") as fh:
            json.dump(have, fh)
        c2 = self.paper(sub, lim_dir=self.lim_dir)
        self.assertTrue(c2._profile_paper)
        self.assertFalse(c2.mgr.state()["armed"])
        d = self._d("dec-test-prof-legacy")
        self.assertIsNone(c2._cash_size(d, {"close": PRICE}, _armed_flat()))
        self.assertEqual(Q.parse(d["qty"]), Decimal("2.8"))


class FundedRoute(_Base):
    """The connected live desk at FICTITIOUS approved limits: never above them."""

    def funded(self, values=None):
        root = os.path.join(self.tmp, "funded")
        os.makedirs(root, exist_ok=True)
        live_dir, limits = approve_live_dir(root, values=values or LIVE_TERMS)
        qty = Decimal(str((values or LIVE_TERMS)["fixed_shares"]))
        auth = L.live_gate_authorize(limits, live_dir, L.LIVE_PORT, L.confirm_phrase(qty, L.session_date(NOW)),
                                     True, now_utc=NOW, monotonic=lambda: self.mono[0],
                                     shown_hash=shown_hash(limits))
        return self.live(auth=auth)

    @staticmethod
    def _d(decision_id, qty=0.0021):
        return {"decision_id": decision_id, "action": "enter_long", "qty": qty,
                "intended_entry": PRICE, "invalidation": STOP}

    def _posts(self, c):
        return [b for (m, p, q, b) in c.transport.trading.calls if m == "POST" and p == "/v2/orders"]

    def test_live_is_not_on_paper_caps(self):
        c = self.funded()
        self.assertFalse(c._profile_paper)
        prof = c.session_state()["trading_profile"]
        self.assertEqual((prof["id"], prof["mode"]), (TP.PROFILE_ID, "live"))
        with self.assertRaises(RuntimeError):
            c._apply_operative_caps(TP.paper_caps(Decimal("100000")))

    def test_ample_cash_keeps_the_approved_size_and_caps(self):
        c = self.funded()
        c.transport._opener.account = _account(cash="500.00", non_marginable_buying_power="500.00", equity="500.00")
        lim = copy.deepcopy(c.limits)
        d = self._d("dec-test-live-ample")
        c._route(d, {"close": PRICE}, _armed_flat())
        self.assertEqual(Q.parse(d["qty"]), LIVE_QTY)
        self.assertEqual(d["cash_sizing"]["binding"], "approved")
        self.assertEqual(d["profile"]["mode"], "live")
        self.assertNotIn("operative_caps", d)
        self.assertEqual(c.limits, lim)
        for k in ("per_trade_notional", "gross_exposure", "max_loss_per_trade", "daily_loss"):
            self.assertEqual(c.limits[k], LIVE_TERMS[k])
        self.assertIsNone(c._operative_caps)

    def test_lower_cash_reduces_the_size(self):
        c = self.funded()
        c.transport._opener.account = _account(cash="500.00", non_marginable_buying_power="500.00", equity="60.00")
        d = self._d("dec-test-live-eq60")
        c._route(d, {"close": PRICE}, _armed_flat())
        self.assertEqual(Q.parse(d["qty"]), Decimal("0.00168"))
        self.assertEqual(d["cash_sizing"]["binding"], "profile")

    def test_low_available_is_an_explicit_pass_with_no_order(self):
        c = self.funded()
        c.transport._opener.account = _account(cash="40.00", non_marginable_buying_power="40.00", equity="40.00")
        lim = copy.deepcopy(c.limits)
        d = self._d("dec-test-live-cash40")
        res = c._route(d, {"close": PRICE}, _armed_flat())
        self.assertEqual(res["status"], "rejected")
        self.assertEqual(res["why"], Z.CASH_SCALED_BELOW_MIN)
        self.assertIn("Pass:", res["detail"])
        self.assertIn("0.00112 sh", res["detail"])
        self.assertIn("below Alpaca's $1 fractional minimum", res["detail"])
        self.assertEqual(self._posts(c), [])
        self.assertEqual(c.limits, lim)
        self.assertNotIn("40.00", json.dumps([res, d["cash_sizing"]]))

    def test_missing_equity_passes_unverified(self):
        c = self.funded()
        c.transport._opener.account = _account(cash="500.00", non_marginable_buying_power="500.00")
        res = c._route(self._d("dec-test-live-noeq"), {"close": PRICE}, _armed_flat())
        self.assertEqual((res["status"], res["why"]), ("rejected", Z.CASH_UNVERIFIED))
        self.assertEqual(self._posts(c), [])

    def test_working_buys_count_before_each_buy(self):
        c = self.funded()
        c.transport._opener.account = _account(cash="360.00", non_marginable_buying_power="360.00", equity="360.00")
        c.mgr._live = lambda kinds=None: [
            {"side": "buy", "kind": "entry", "qty": 0.5, "filled_qty": 0, "limit": PRICE, "status": "uncertain"},
            {"side": "sell", "kind": "protective", "qty": 0.0021, "filled_qty": 0, "stop": STOP,
             "status": "acked"}]
        self.assertEqual(c._working_buy_usd(), Decimal("300"))
        d = self._d("dec-test-live-working")
        c._route(d, {"close": PRICE}, _armed_flat())
        self.assertEqual(Q.parse(d["qty"]), Decimal("0.00168"))

    def test_not_armed_or_stopped_reads_no_account(self):
        c = self.funded()
        calls = []
        c.broker.funding = lambda: calls.append(1) or {}
        st = _armed_flat()
        st["armed"] = False
        c._route(self._d("dec-test-live-unarmed"), {"close": PRICE}, st)
        st = _armed_flat()
        st["controls"]["stopped"] = True
        c._route(self._d("dec-test-live-stopped"), {"close": PRICE}, st)
        self.assertEqual(calls, [])


class WholeShareRoute(_Base):
    def test_whole_share_live_desk_with_plenty_of_cash_is_unchanged(self):
        c = self.live()
        d = {"decision_id": "dec-test-whole", "action": "enter_long", "qty": 1,
             "intended_entry": 400.0, "invalidation": 399.0}
        c._route(d, {"close": 400.0}, _armed_flat())
        self.assertEqual(d["qty"], 1)
        self.assertIs(type(d["qty"]), int)
        self.assertEqual(d["cash_sizing"]["binding"], "approved")


if __name__ == "__main__":
    unittest.main()
