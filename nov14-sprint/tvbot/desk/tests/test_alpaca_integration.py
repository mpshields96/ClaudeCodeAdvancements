"""Integration tests for the opt-in Alpaca PAPER session (alpaca_session.py, coordinator).

Everything runs against the real adapter pieces wired together: MockAlpacaTransport + MockTrading
(in-process fake venue, synthetic ids), MockData (synthetic SPY minutes), the real IexSpyFeed,
the real AlpacaPaperBroker and the real OrderManager. No socket, no credential, no environment
variable and no Keychain item is touched. Limits are the desk's TEST VALUES, never Matthew's.

Run: /usr/bin/python3 -IB -m unittest discover -s <desk>/tests -p 'test_alpaca_integration*'
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

import alpaca as A  # noqa: E402
import alpaca_session as AS  # noqa: E402
from alpaca.state import AdapterState  # noqa: E402


def posts(c):
    return [b for (m, p, q, b) in c.transport.trading.calls if m == "POST" and p == "/v2/orders"]


class AlpacaSessionIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-alpaca-int-")
        self.ctrls = []

    def tearDown(self):
        for c in self.ctrls:
            try:
                c.close()
            except Exception:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, sub="s", **kw):
        c = AS.AlpacaSessionController(os.path.join(self.tmp, sub), strategy="ema", **kw)
        self.ctrls.append(c)
        return c

    def run_days(self, c, checks=14):
        """Warm start, then the operator arms each trading day and clicks Check for new bars."""
        c.check_new_bars()
        day = None
        for _ in range(checks):
            if c.clock.now().date() != day:
                day = c.clock.now().date()
                c.arm()
            c.check_new_bars()

    # ------------------------------------------------------------ start-up and labels
    def test_fresh_init_publishes_mock_state(self):
        c = self.make()
        st = c.session_state()
        self.assertTrue(st["simulated"])
        self.assertEqual(st["broker_mode"], "alpaca-mock")
        self.assertEqual(st["evidence_label"], A.LABEL_MOCK_LOCAL)
        self.assertEqual(st["data_label"], A.DATA_LABEL_MOCK)
        self.assertIn("ALPACA MOCK", st["badge"])
        self.assertFalse(st["adapter"]["enabled"])           # opt-in: off until confirmed
        self.assertFalse(st["schedule"]["enabled"])
        self.assertFalse(st["quote"]["available"])
        self.assertIn("TEST VALUE", c.limits_source["label"])  # never presented as Matthew's sizing

    def test_enable_requires_explicit_confirm(self):
        c = self.make()
        self.assertEqual(c.alpaca_enable()["reason"], "CONFIRM_REQUIRED")
        self.assertFalse(c.adapter_state.enabled)
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])
        self.assertTrue(AdapterState(c.state_dir).enabled)    # persisted, not just in memory

    def test_no_play_schedule_or_auto_arm(self):
        c = self.make()
        self.assertEqual(c.play()["reason"], "NO_PLAY_IN_ALPACA_MODE")
        self.assertEqual(c.run_to_end()["reason"], "NO_PLAY_IN_ALPACA_MODE")
        self.assertEqual(c.set_schedule(True)["reason"], "NO_SCHEDULE_IN_ALPACA_MODE")
        c.alpaca_enable(confirm=True)
        self.assertEqual(c.arm(auto=True)["reason"], "NO_AUTO_ARM_IN_ALPACA_MODE")

    def test_https_mode_needs_approved_limits_and_never_builds_a_transport(self):
        with self.assertRaises(Exception) as cm:
            AS.AlpacaSessionController(os.path.join(self.tmp, "h"), mode="https")
        self.assertIn("limits", str(cm.exception).lower())

    # ------------------------------------------------------------ warm start
    def test_warm_start_reaches_warmup_and_never_routes_history(self):
        c = self.make()
        c.alpaca_enable(confirm=True)
        r = c.check_new_bars()
        self.assertTrue(r["ok"])
        self.assertTrue(r["warm_start"])
        wv = c.warmup_view()
        self.assertTrue(wv["ready"], wv["text"])
        self.assertGreaterEqual(wv["bars"], AS.WARMUP_BARS_DEFAULT)
        self.assertEqual(posts(c), [])                          # stale history never reaches the venue
        for b in c.bars:
            self.assertEqual(b["source"], A.DATA_LABEL_MOCK)
        for d in c.decisions:
            self.assertEqual(d.get("data_source"), A.DATA_LABEL_MOCK)
            self.assertNotIn(d.get("reason_code"), ("DATA_REJECTED_STALE_EXCHANGE_TS",))

    # ------------------------------------------------------------ bounded entries
    def test_armed_entry_is_a_bounded_limit_buy(self):
        c = self.make()
        c.alpaca_enable(confirm=True)
        self.run_days(c)
        buys = [b for b in posts(c) if b["side"] == "buy"]
        self.assertTrue(buys, "expected at least one armed entry in the synthetic walkthrough")
        entries = [d for d in c.decisions if d.get("action") == "enter_long" and d.get("entry_bound")]
        self.assertTrue(entries)
        for b in buys:
            self.assertEqual(b["symbol"], "SPY")
            self.assertEqual(b["type"], "limit")
            self.assertIn("limit_price", b)
            self.assertNotIn("notional", b)
        limits = sorted(float(b["limit_price"]) for b in buys)
        bounded = sorted(d["entry_bound"]["limit"] for d in entries if d["entry_bound"]["limit"] in limits)
        self.assertEqual(limits, bounded)
        for d in entries:
            eb = d["entry_bound"]
            self.assertLessEqual(eb["limit"], min(eb["bounds"].values()) + 1e-9)

    def test_gap_over_cap_serialized_post_never_exceeds_notional(self):
        c = self.make()
        c.limits["per_trade_notional"] = 499.0     # TEST VALUE just under the ~$500 synthetic price
        c.alpaca_enable(confirm=True)
        self.run_days(c)
        buys = [b for b in posts(c) if b["side"] == "buy"]
        self.assertTrue(buys)
        for b in buys:
            self.assertEqual(b["type"], "limit")
            self.assertLessEqual(int(b["qty"]) * float(b["limit_price"]), 499.0 + 1e-9)
        bound = [d["entry_bound"] for d in c.decisions if d.get("entry_bound")]
        self.assertTrue(all(eb["binding"] == "notional" for eb in bound))
        for f in c.broker.snapshot().get("fills", []) if isinstance(c.broker.snapshot(), dict) else []:
            if f.get("side") == "buy":
                self.assertLessEqual(float(f["price"]), 499.0 + 1e-9)

    def test_short_open_blocked(self):
        c = self.make()
        limit, why = c._entry_bounds({}, None, c.mgr.state(), 1, "sell", 500.0, 507.5)
        self.assertIsNone(limit)
        self.assertEqual(why[0], "SHORT_OPEN_BLOCKED")

    def test_entry_bound_refuses_limit_at_or_below_stop(self):
        c = self.make()
        c.limits["per_trade_notional"] = 450.0
        limit, why = c._entry_bounds({}, None, c.mgr.state(), 1, "buy", 500.0, 492.5)
        self.assertIsNone(limit)
        self.assertEqual(why[0], "ENTRY_BOUND")

    # ------------------------------------------------------------ strategy sizing basis
    def _approved(self, sub, **vals):
        """A SYNTHETIC worksheet approval in a scratch dir (never Matthew's values)."""
        sizing = AS.importlib.import_module("alpaca.sizing")
        d = os.path.join(self.tmp, sub + "-limits")
        os.makedirs(d, exist_ok=True)
        v = {"fixed_shares": 10, "per_trade_notional": 6000.0, "gross_exposure": 12000.0,
             "max_loss_per_trade": 150.0, "daily_loss": 300.0}
        v.update(vals)
        sizing.save_draft(d, v)
        seen = sizing.read_draft(d)                       # what the operator "reviewed"
        sizing.approve(d, sizing.CONFIRM_PHRASE, "synthetic test approval",
                       reviewed_draft_hash=sizing.content_hash(seen.get("values")),
                       prior_approved_hash=None)
        return sizing.approved_path(d)

    def test_strategy_sizing_uses_chosen_per_order_cap_not_offline_test_cap(self):
        from strategies import base as B
        c = self.make("sz", limits_path=self._approved("sz"))
        self.assertEqual(c.strategy_cfg["fixed_qty"], 10)
        self.assertEqual(B.base_qty(500, c.strategy_cfg), 10)    # $5,000 fits the $6,000 cap
        self.assertEqual(B.base_qty(600, c.strategy_cfg), 10)    # exactly at the cap
        self.assertEqual(B.base_qty(600.01, c.strategy_cfg), 0)  # above the cap: refused, never resized
        self.assertEqual(c.strategy_cfg["limits"]["gross_exposure"], 12000.0)
        self.assertNotIn("TEST VALUES", c.strategy_cfg["test_size"]["label"])

    def test_strategy_sizing_lower_chosen_cap_refuses(self):
        from strategies import base as B
        c = self.make("sz2", limits_path=self._approved("sz2", per_trade_notional=4000.0))
        self.assertEqual(B.base_qty(399, c.strategy_cfg), 10)
        self.assertEqual(B.base_qty(500, c.strategy_cfg), 0)     # 10 x $500 > $4,000

    def test_chosen_size_reaches_the_serialized_post(self):
        c = self.make("sz3", limits_path=self._approved("sz3"))
        c.alpaca_enable(confirm=True)
        self.run_days(c)
        buys = [b for b in posts(c) if b["side"] == "buy"]
        self.assertTrue(buys, "10 shares under a $6,000 cap must be able to enter")
        for b in buys:
            self.assertEqual(int(b["qty"]), 10)
            self.assertLessEqual(10 * float(b["limit_price"]), 6000.0 + 1e-9)

    def test_offline_desk_keeps_its_test_cap_contract(self):
        import session as S
        from strategies import base as B
        d = os.path.join(self.tmp, "offline")
        ctl = S.SessionController(state_dir=d, strategy="ema")
        try:
            self.assertNotIn("test_size", ctl.strategy_cfg)
            self.assertEqual(B.base_qty(500, ctl.strategy_cfg), 1)        # 1-share demo preset
            self.assertEqual(B.base_qty(500, dict(ctl.strategy_cfg, fixed_qty=10)), 0)  # $2,000 TEST cap
        finally:
            try:
                ctl.close()
            except Exception:
                pass

    # ------------------------------------------------------------ Stop, recovery, venue clock
    def test_stop_disables_adapter_persistently(self):
        c = self.make()
        c.alpaca_enable(confirm=True)
        c.stop_and_close(reason="TEST")
        self.assertFalse(AdapterState(c.state_dir).enabled)
        self.assertIn("STOP", AdapterState(c.state_dir).view()["disabled_reason"])
        self.assertEqual(c.alpaca_enable(confirm=True)["reason"], "STOPPED")
        self.assertTrue(c.reconcile_now()["ok"])             # read-only reconcile still works

    def test_failed_reconcile_blocks_new_exposure_until_clean(self):
        c = self.make()
        c.check_new_bars()
        c.broker.note_reconcile({"ok": False})
        self.assertEqual(c.alpaca_enable(confirm=True)["reason"], "RECOVERY_AMBIGUOUS")
        self.assertTrue(c.session_state()["recovery"]["ambiguous"])
        self.assertTrue(c.reconcile_now()["ok"])             # a clean operator reconcile clears it
        self.assertFalse(c.session_state()["recovery"]["ambiguous"])
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])

    def test_disabled_adapter_refuses_arm(self):
        c = self.make()
        c.check_new_bars()
        r = c.arm()
        self.assertFalse(r["ok"])
        self.assertIn("adapter enabled", [f["check"] for f in r["failed"]])

    def test_venue_clock_skew_fails_preflight_check(self):
        c = self.make()
        now = c.clock.now()
        c._sync_mock_venue_clock(now)
        self.assertTrue(c._venue_clock_check(now)["ok"])
        clk = dict(c.transport.trading.clock)
        clk["timestamp"] = AS.iso(now - AS._dt.timedelta(seconds=AS.VENUE_CLOCK_SKEW_S + 60))
        c.transport.trading.clock = clk
        self.assertFalse(c._venue_clock_check(now)["ok"])

    def test_broker_snapshot_and_ledger_flags_persisted(self):
        c = self.make()
        c.check_new_bars()
        path = os.path.join(c.state_dir, AS.SNAPSHOT_FILE)
        self.assertTrue(os.path.exists(path))
        with open(path) as fh:
            json.load(fh)
        flags = c._ledger_flags()
        self.assertTrue(flags["mock_fills"])
        self.assertEqual(flags["evidence"], A.LABEL_MOCK_LOCAL)
        self.assertEqual(flags["data_source"], A.DATA_LABEL_MOCK)


class AlpacaWeeklyHook(unittest.TestCase):
    """Codex weekly owner, 23:0xZ: a paper or mock session's weekly report goes to alpaca/weekly.py,
    not the offline synthetic-bar renderer, and the response label names its real source."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-alpaca-weekly-")
        self.c = AS.AlpacaSessionController(os.path.join(self.tmp, "s"), strategy="ema")
        self.c.alpaca_enable(confirm=True)
        self.c.check_new_bars()
        self.c.review()

    def tearDown(self):
        try:
            self.c.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mock_session_routes_to_alpaca_weekly(self):
        import report as RP
        _, page = RP.build_html(self.c.state_dir)
        self.assertIn("SPY rehearsal week", page)

    def test_label_is_source_aware(self):
        import launch as L
        self.assertIn("ALPACA MOCK", L._weekly_label(self.c))
        self.assertNotIn("TEST VALUES", L._weekly_label(self.c))

        class Offline(object):
            pass
        self.assertIn("offline synthetic bars", L._weekly_label(Offline()))


class DecimalCapsAndMockEventTime(unittest.TestCase):
    """Codex 23:09Z: 3 x $501.04 is exactly a $1503.12 cap (float says 1503.1200000000001), and mock
    fill times follow the synthetic bar clock so mock-week fills land in the mock week."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-alpaca-dec-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_base_qty_accepts_exact_cap_only(self):
        from strategies.base import base_qty
        cfg = {"fixed_qty": 3, "test_size": {"order_notional": 5000.0}, "limits": {"per_trade_notional": 1503.12}}
        self.assertEqual(base_qty(501.04, cfg), 3)
        self.assertEqual(base_qty(501.05, cfg), 0)      # a true excess is still refused

    def test_manager_cap_checks_accept_exact_equality_only(self):
        from orders.calendar import SessionCalendar
        from orders.fake_broker import FakeBroker
        from orders.manager import OrderManager
        lim = {"per_trade_notional": 1503.12, "max_loss_per_trade": 100.0, "daily_loss": 30.0,
               "gross_exposure": 1503.12, "label": "TEST VALUES"}
        m = OrderManager(self.tmp, FakeBroker(seed=7), lim, calendar=SessionCalendar.fixture_profile())
        try:
            def intent(px):
                return {"decision_id": "dec-cap", "kind": "entry", "side": "buy", "qty": 3, "limit": px,
                        "intended_entry": px, "invalidation": px - 1.0}
            self.assertIsNone(m._check_entry_risk(intent(501.04)))
            self.assertEqual(m._check_entry_risk(intent(501.05)), "NOTIONAL")
            lim2 = dict(lim, per_trade_notional=5000.0)
            m.limits.update(lim2)
            self.assertIsNone(m._check_entry_risk(intent(501.04)))
            self.assertEqual(m._check_entry_risk(intent(501.05)), "RISK_GROSS")
        finally:
            m.close()

    def test_mock_fill_time_follows_bar_clock(self):
        c = AS.AlpacaSessionController(os.path.join(self.tmp, "s"), strategy="ema")
        try:
            c.alpaca_enable(confirm=True)
            c.check_new_bars()
            tr = c.transport.trading
            bar = c.bars[-1]
            tr.event_ts = bar["ts_close"]
            fill_ts = tr._event_tick()
            self.assertEqual(fill_ts[:13], bar["ts_close"][:13])   # mock time, not today's wall clock
            tr.event_ts = None
            self.assertNotEqual(tr._event_tick()[:10], bar["ts_close"][:10])  # order times stay on _tick()
        finally:
            c.close()


class ManagerBarFreshnessBinding(unittest.TestCase):
    """Codex adviser 23:1xZ: the Alpaca session advertised 900 s but OrderManager.on_bar checked
    bars at intake's 5 s default, so a 10:30 bar checked at 10:31:01 was refused BAR_STALE_EXCHANGE_TS.
    The manager now uses the session's window; offline keeps 5 s; past the window is still refused."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-alpaca-fresh-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _aged(self, bar, age_s):
        from orders.calendar import parse_ts, iso
        import datetime as _dt
        b = dict(bar)
        b.pop("exchange_ts", None)
        b["delivered_ts"] = iso(parse_ts(b["ts_close"]) + _dt.timedelta(seconds=age_s))
        return b

    def test_alpaca_manager_uses_session_window_and_refuses_past_it(self):
        from orders.intake import check_bar
        c = AS.AlpacaSessionController(os.path.join(self.tmp, "a"), strategy="ema")
        try:
            self.assertEqual(c.mgr.bar_max_age_s, c.bar_max_age_s)
            self.assertEqual(c.bar_max_age_s, 900.0)
            c.alpaca_enable(confirm=True)
            c.check_new_bars()
            bar = c.bars[-1]
            ok, code, _ = check_bar(self._aged(bar, 61), None, c.mgr.calendar, max_age_s=c.mgr.bar_max_age_s)
            self.assertNotEqual(code, "STALE_EXCHANGE_TS")
            ok, code, d = check_bar(self._aged(bar, 901), None, c.mgr.calendar, max_age_s=c.mgr.bar_max_age_s)
            self.assertIn("STALE_EXCHANGE_TS", d.get("codes") or [code])
        finally:
            c.close()

    def test_offline_manager_keeps_five_seconds(self):
        import session as S
        from orders.intake import DEFAULT_MAX_AGE_S
        c = S.SessionController(os.path.join(self.tmp, "o"), strategy="ema")
        try:
            self.assertEqual(c.mgr.bar_max_age_s, DEFAULT_MAX_AGE_S)
            self.assertEqual(DEFAULT_MAX_AGE_S, 5.0)
        finally:
            c.close()


class SubPennyProtectiveStop(unittest.TestCase):
    """Codex adviser 23:1xZ: a normal EMA stop has fractional cents (e.g. 101.6914). It must reach
    the venue on the $0.01 tick toward the safe side (long sell stop UP, buy DOWN), never as a
    BAD_PRICE that leaves the shares bare; a refused initial protective retries under a NEW id;
    a stop already through the last close is refused visibly. Mock venue, synthetic ids, TEST VALUES."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-alpaca-cent-")
        self.c = AS.AlpacaSessionController(os.path.join(self.tmp, "s"), strategy="ema")
        self.c.alpaca_enable(confirm=True)
        self.c.check_new_bars()
        self.c.arm()
        self.trading = self.c.transport.trading
        self.px = float(self.c.bars[-1]["close"])
        self.c._fetch = lambda after, now: ([], [])

    def tearDown(self):
        try:
            self.c.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stops(self):
        return [b for b in posts(self.c) if b.get("type") == "stop"]

    def _entry(self, inval, partial=None):
        c = self.c
        did = "cent-test-entry-0001"
        c.decisions.append({"decision_id": did, "invalidation": inval})
        c.mgr.submit_intent({"decision_id": did, "kind": "entry", "side": "buy", "qty": 3,
                             "limit": round(self.px + 0.5, 2), "ref_price": self.px,
                             "intended_entry": self.px, "invalidation": inval})
        self.trading.partial_next = partial
        self.trading.advance(self.px)

    def test_cent_price_rule(self):
        from decimal import Decimal
        from alpaca.broker import cent_price
        self.assertEqual(cent_price(101.6914, "sell"), Decimal("101.70"))
        self.assertEqual(cent_price(101.6914, "buy"), Decimal("101.69"))
        self.assertEqual(cent_price(101.70, "sell"), Decimal("101.70"))
        self.assertEqual(cent_price(0.1 + 0.2, "sell"), Decimal("0.30"))      # float noise is not a cent
        for bad in (0, -1, float("nan"), float("inf"), None, "x", 0.001):
            self.assertIsNone(cent_price(bad, "buy"), bad)

    def test_fractional_ema_stop_is_posted_on_tick_and_partial_residual_covered(self):
        c = self.c
        inval = self.px - 2.0 + 0.0014                          # an EMA-like level with fractional cents
        self._entry(inval, partial=1)
        c.check_new_bars()                                     # books 1, attaches a 1-share stop
        self.trading.partial_next = None
        self.trading.advance(self.px)                          # the other 2 fill between Checks
        r = c.check_new_bars()
        stops = self._stops()
        self.assertEqual([int(b["qty"]) for b in stops], [1, 2], stops)
        from decimal import Decimal, ROUND_CEILING
        want = str(Decimal(repr(inval)).quantize(Decimal("0.01"), rounding=ROUND_CEILING))
        self.assertEqual({b["stop_price"] for b in stops}, {want})
        self.assertEqual(r["orders"]["protection"]["uncovered_qty"], 0)
        self.assertFalse([x for x in c.mgr.intents.values() if x.get("kind") == "protective"
                          and x.get("status") == "rejected"])

    def test_rejected_initial_protective_retries_under_new_id(self):
        c = self.c
        self._entry(round(self.px - 2.0, 2) + 0.0037)
        self.trading.reject_next = "http"                      # the first protective POST is refused
        c.check_new_bars()
        prot = [x for x in c.mgr.intents.values() if x.get("kind") == "protective"]
        self.assertEqual([x.get("status") for x in prot], ["rejected"], prot)
        self.assertEqual(c.session_state()["protection"]["uncovered_qty"], 3)
        self.assertIn("last_refusal", c.session_state()["protection"])
        c.check_new_bars()                                     # next Check: a NEW id, not the rejected one
        prot = [x for x in c.mgr.intents.values() if x.get("kind") == "protective"]
        ids = [x["decision_id"] for x in prot]
        self.assertEqual(len(set(ids)), 2, ids)
        self.assertTrue(ids[1].endswith("|try2"), ids)
        self.assertEqual(c.session_state()["protection"]["uncovered_qty"], 0)

    def test_stop_through_last_close_is_refused_visibly(self):
        c = self.c
        self._entry(round(self.px - 2.0, 2))
        c.bars[-1] = dict(c.bars[-1], close=round(self.px - 2.5, 2))   # market already below the stop
        n0 = len(self._stops())
        for x in list(c.mgr.intents.values()):
            if x.get("kind") == "protective":
                self.skipTest("protective already attached on entry fill")
        c._order_pass()
        self.assertEqual(len(self._stops()), n0)
        pv = c._protection_view()
        self.assertEqual(pv["uncovered_qty"], 3)
        with open(c.paths["desk_audit"]) as fh:
            self.assertIn("PROTECTIVE_STOP_CROSSED", fh.read())


class SizingOnlyRestartRevision(unittest.TestCase):
    """Codex 23:1xZ: the ordinary worksheet workflow. Launch, close, save a new sizing draft (or
    approve new limits), relaunch on the SAME state dir: a sizing-only revision is accepted and
    recorded; journals, day P&L, working orders and Stop are kept; the desk starts disarmed. A
    strategy or non-sizing change is still refused; the offline scenario lock is unchanged.
    Mock venue, synthetic ids, TEST VALUE limits (not Matthew's)."""

    DRAFT = {"fixed_shares": 2, "max_loss_per_trade": 40, "daily_loss": 120,
             "per_trade_notional": 1800, "gross_exposure": 3600}

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-alpaca-rev-")
        self.d = os.path.join(self.tmp, "s")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _open(self, strategy="ema", **kw):
        return AS.AlpacaSessionController(self.d, strategy=strategy, **kw)

    def _audit(self):
        with open(os.path.join(self.d, "desk_audit.jsonl")) as fh:
            return [json.loads(x) for x in fh if x.strip()]

    def test_draft_then_restart_keeps_history_and_starts_disarmed(self):
        import alpaca.sizing as SZ
        c = self._open()
        c.alpaca_enable(confirm=True)
        c.check_new_bars()
        c.arm()
        px = float(c.bars[-1]["close"])
        c.mgr.submit_intent({"decision_id": "rev-test-entry-0001", "kind": "entry", "side": "buy", "qty": 1,
                             "limit": round(px - 5.0, 2), "ref_price": px, "intended_entry": px,
                             "invalidation": round(px - 8.0, 2)})
        working = [x["decision_id"] for x in c.mgr.intents.values() if x.get("status") == "acked"]
        self.assertEqual(working, ["rev-test-entry-0001"])
        n_audit = len(self._audit())
        self.assertTrue(c.mgr.state()["armed"])
        c.close()
        SZ.save_draft(self.d, self.DRAFT)
        c2 = self._open()
        try:
            self.assertEqual(c2.fixed_qty, 2) if hasattr(c2, "fixed_qty") else None
            cfg = c2.session_config
            self.assertEqual(cfg["revision"], 1)
            self.assertEqual(cfg["strategy_cfg"]["fixed_qty"], 2)
            self.assertEqual(cfg["revisions"][0]["strategy_cfg"]["fixed_qty"], 1)
            self.assertEqual(cfg["limits_source"]["provenance"], "draft")
            self.assertFalse(c2.mgr.state()["armed"])                 # never inherits armed
            self.assertIn("rev-test-entry-0001",
                          [x["decision_id"] for x in c2.mgr.intents.values() if x.get("status") == "acked"])
            aud = self._audit()
            self.assertGreater(len(aud), n_audit)                     # journal appended, not replaced
            self.assertTrue(any(r.get("kind") == "session_config_revised" for r in aud))
            self.assertFalse(any(r.get("kind") == "session_config_change_refused" for r in aud))
        finally:
            c2.close()
        c3 = self._open()                                              # same revised config: plain resume
        try:
            self.assertEqual(c3.session_config["revision"], 1)
            self.assertIsNone(c3.config_revision)
        finally:
            c3.close()

    def test_stop_survives_a_sizing_revision(self):
        import alpaca.sizing as SZ
        c = self._open()
        c.alpaca_enable(confirm=True)
        c.check_new_bars()
        c.stop_and_close(reason="TEST")
        c.close()
        SZ.save_draft(self.d, self.DRAFT)
        c2 = self._open()
        try:
            self.assertTrue(c2.mgr.state()["controls"]["stopped"])
            self.assertFalse(AdapterState(self.d).enabled)            # Stop's disable persists
            self.assertEqual(c2.session_config["revision"], 1)
        finally:
            c2.close()

    def test_strategy_change_still_refused(self):
        import session as S
        c = self._open()
        c.close()
        with self.assertRaises(S.SessionConfigChanged):
            self._open(strategy="cash")
        cfg = dict(S.DEMO_STRATEGY_CFG, fast=int(S.DEMO_STRATEGY_CFG.get("fast", 9)) + 2)
        with self.assertRaises(S.SessionConfigChanged):
            self._open(strategy_cfg=cfg)

    def test_offline_scenario_size_change_still_refused(self):
        import session as S
        d = os.path.join(self.tmp, "offline")
        S.SessionController(d, strategy="ema", strategy_cfg=dict(S.DEMO_STRATEGY_CFG, fixed_qty=1)).close()
        with self.assertRaises(S.SessionConfigChanged):
            S.SessionController(d, strategy="ema", strategy_cfg=dict(S.DEMO_STRATEGY_CFG, fixed_qty=2))


class HttpsEntryQuoteGate(unittest.TestCase):
    """Codex 23:23Z: on the HTTPS path each BUY candidate reads the free-IEX latest quote via
    alpaca.readiness.read_quote; invalid/crossed/stale holds the new entry. Injected transport,
    synthetic payloads, no network, no account."""

    class _Q:
        def __init__(self, quote):
            self.quote = quote
        def request(self, method, origin, path, query=None, **kw):
            assert (method, origin, path) == ("GET", "data", "/v2/stocks/SPY/quotes/latest")
            return 200, {"symbol": "SPY", "quote": self.quote}

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-alpaca-qg-")
        self.c = AS.AlpacaSessionController(os.path.join(self.tmp, "s"), strategy="ema")

    def tearDown(self):
        self.c.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _bounds(self, quote):
        c = self.c
        real = c.transport
        c.mock, c.transport = False, self._Q(quote)
        try:
            d = {"decision_id": "qg-0001"}
            res = c._entry_bounds(d, None, c.mgr.state(), 1, "buy", 400.0, 395.0)
            return d, res
        finally:
            c.mock, c.transport = True, real

    def _iso(self, age_s):
        import datetime as dt
        t = dt.datetime.fromisoformat(str(self.c.clock.now()).replace("Z", "+00:00")) if not hasattr(self.c.clock.now(), "isoformat") else self.c.clock.now()
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return (t - dt.timedelta(seconds=age_s)).isoformat().replace("+00:00", "Z")

    def test_fresh_quote_allows_and_is_recorded(self):
        d, (limit, refusal) = self._bounds({"t": self._iso(1), "bp": 399.98, "ap": 400.02, "bs": 1, "as": 1})
        self.assertIsNone(refusal)
        self.assertTrue(d["quote_observation"]["fresh"])
        self.assertEqual(self.c.latest_quote["ask"], 400.02)

    def test_crossed_and_stale_hold_entry(self):
        for q, why in (({"t": self._iso(1), "bp": 400.05, "ap": 400.0, "bs": 1, "as": 1}, "CROSSED_QUOTE"),
                       ({"t": self._iso(3600), "bp": 399.98, "ap": 400.02, "bs": 1, "as": 1}, "STALE_QUOTE"),
                       ({"t": "garbage", "bp": 1, "ap": 2}, "INVALID_QUOTE")):
            d, (limit, refusal) = self._bounds(q)
            self.assertIsNone(limit)
            self.assertEqual(refusal[0], "QUOTE_GATE")
            self.assertIn(why, refusal[1])

    def test_mock_path_does_not_read_quotes(self):
        d = {"decision_id": "qg-0002"}
        self.c._entry_bounds(d, None, self.c.mgr.state(), 1, "buy", 400.0, 395.0)
        self.assertNotIn("quote_observation", d)


class LauncherConnectedGuards(unittest.TestCase):
    """Codex 22:56Z and 22:46Z. Both refusals happen before any lock, rename, broker object or
    python process, so these tests never reach a transport (and https never runs here)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-launch-guard-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_connected_fresh_is_refused_before_any_rename_or_lock(self):
        import contextlib
        import glob
        import io
        import launch as L
        d = os.path.join(self.tmp, "state-alpaca-paper")
        os.makedirs(d)
        journal = os.path.join(d, "intents.jsonl")
        with open(journal, "w") as fh:
            fh.write('{"synthetic": true}\n')
        out = io.StringIO()
        for extra in ([], ["--limits", os.path.join(self.tmp, "absent.json")]):
            with self.subTest(extra=extra), contextlib.redirect_stdout(out):
                rc = L.main(["--broker", "alpaca-paper", "--transport", "https", "--fresh",
                             "--state-dir", d, "--no-browser"] + extra)
            self.assertEqual(rc, 2)
        self.assertIn("--fresh is mock-only", out.getvalue())
        self.assertTrue(os.path.exists(journal))                      # journal untouched
        self.assertEqual(glob.glob(d + ".prev-*"), [])                # nothing moved aside
        self.assertFalse(os.path.exists(d.rstrip(os.sep) + L.LOCK_SUFFIX))   # no lock taken

    @unittest.skipUnless(os.path.exists("/bin/zsh"), "needs /bin/zsh")
    def test_mock_finder_command_refuses_other_transport_or_broker(self):
        import subprocess
        cmd = os.path.join(DESK, "Open Alpaca Paper Desk.command")
        for args in (["--transport", "https"], ["--transport=https"], ["--tra", "https"],
                     ["--broker", "offline"], ["--provider", "env", "--t=https"]):
            with self.subTest(args=args):
                p = subprocess.run(["/bin/zsh", cmd] + args, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
                text = p.stdout.decode("utf-8", "replace")
                self.assertEqual(p.returncode, 2, text)
                self.assertIn("REFUSED", text)
                self.assertNotIn("mock walkthrough check", text)       # launch.py never started
        with open(cmd) as fh:
            body = fh.read()
        self.assertIn('"$@" --transport mock', body)                  # mock forced last, even if missed



class ZeroBarCheckProtection(unittest.TestCase):
    """Codex 23:00Z (1->4 share case; 1->3 here to fit the TEST caps): a manual Check with zero new bars still books later fills of known orders and
    covers only the residual shares; no duplicate, nothing beside a pending Stop, and an uncovered
    count is visible when it cannot be covered. Mock venue, synthetic ids, TEST VALUE limits."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-alpaca-zero-")
        self.c = AS.AlpacaSessionController(os.path.join(self.tmp, "s"), strategy="ema")
        self.c.alpaca_enable(confirm=True)
        self.c.check_new_bars()                              # warm start
        self.c.arm()
        self.trading = self.c.transport.trading
        self.px = float(self.c.bars[-1]["close"])
        self.c._fetch = lambda after, now: ([], [])          # no new hourly bar yet

    def tearDown(self):
        try:
            self.c.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _partial_entry(self, with_invalidation=True):
        c = self.c
        did = "zero-bar-test-entry-0001"
        if with_invalidation:
            c.decisions.append({"decision_id": did, "invalidation": round(self.px - 3.0, 2)})
        c.mgr.submit_intent({"decision_id": did, "kind": "entry", "side": "buy", "qty": 3,
                             "limit": round(self.px + 0.5, 2), "ref_price": self.px,
                             "intended_entry": self.px, "invalidation": round(self.px - 3.0, 2)})
        self.assertEqual(len(self.trading.orders), 1, c.mgr.intents)
        self.trading.partial_next = 1
        self.trading.advance(self.px)                         # venue: 1 of 3 filled (3 x ~$500 fits the $2,000 TEST cap)
        c.check_new_bars()                                    # books 1, attaches a 1-share stop
        self.trading.partial_next = None
        self.trading.advance(self.px)                         # venue: the other 2 fill between Checks

    def _stops(self):
        return [b for b in posts(self.c) if b.get("type") == "stop"]

    def test_later_fill_booked_and_only_residual_covered_once(self):
        c = self.c
        self._partial_entry()
        stops = self._stops()
        self.assertEqual([int(b["qty"]) for b in stops], [1])
        self.assertEqual(c.mgr.pos_qty, 1)                    # desk has not seen the late fill yet
        r = c.check_new_bars()
        self.assertEqual(r["bars"], 0)
        self.assertEqual(r["exposure_before_check"]["position_qty"], 1)
        self.assertGreaterEqual(r["orders"]["poll"]["fills_booked"], 1)
        self.assertEqual(c.mgr.pos_qty, 3)
        self.assertEqual([int(b["qty"]) for b in self._stops()], [1, 2])   # residual only
        prot = r["orders"]["protection"]
        self.assertEqual((prot["covered_qty"], prot["uncovered_qty"]), (3, 0))
        self.assertIn("next Check", r["fill_timing_note"])
        c.check_new_bars()
        self.assertEqual(len(self._stops()), 2)               # no duplicate on a second Check
        self.assertEqual(c.session_state()["protection"]["uncovered_qty"], 0)

    def test_no_residual_protective_beside_a_pending_stop(self):
        c = self.c
        self._partial_entry()
        c.stop_and_close()
        n = len(self._stops())
        c.check_new_bars()
        c.check_new_bars()
        self.assertEqual(len(self._stops()), n)               # Stop & Close owns the position

    def test_uncovered_count_visible_when_no_invalidation(self):
        c = self.c
        self._partial_entry(with_invalidation=False)
        r = c.check_new_bars()
        self.assertEqual(self._stops(), [])
        prot = r["orders"]["protection"]
        self.assertEqual(prot["uncovered_qty"], 3)
        self.assertIn("no working protective", prot["warning"])
        self.assertEqual(c.session_state()["protection"]["uncovered_qty"], 3)

    def test_reconcile_stays_read_only(self):
        c = self.c
        self._partial_entry()
        n = len(posts(c))
        c.reconcile_now()
        self.assertEqual(len(posts(c)), n)

if __name__ == "__main__":
    unittest.main()
