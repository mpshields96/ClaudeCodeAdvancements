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


if __name__ == "__main__":
    unittest.main()
