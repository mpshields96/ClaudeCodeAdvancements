"""Night controller checks: operator-started live mode wiring plus three entry/expiry safety fixes.

Everything here is offline. The "live" transport is the in-process mock venue with MODE="live"
and synthetic payloads; no network, no credentials, no account, no orders leave the process.
This is operational readiness only; it says nothing about the strategy's edge.
"""
import datetime as _dt
import os
import shutil
import sys
import tempfile
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DESK)

import alpaca as A  # noqa: E402
import alpaca_session as AS  # noqa: E402
from alpaca import sizing  # noqa: E402
from alpaca.broker import AlpacaPaperBroker  # noqa: E402
from alpaca.mock import MockAlpacaTransport, MockTrading  # noqa: E402
from alpaca.mock_data import MockData  # noqa: E402


class LiveShapedMock(MockAlpacaTransport):
    """The mock venue dressed as alpaca/live.py LiveHttpsTransport (MODE="live"). TEST VALUES."""
    MODE = "live"

    def request(self, method, origin_key, path, query=None, body=None):
        if method == "GET" and origin_key == "trading" and path == "/v2/assets/" + A.SYMBOL:
            self.trading.calls.append((method, path, dict(query or {}), body))
            return 200, {"symbol": A.SYMBOL, "tradable": True, "status": "active"}
        return MockAlpacaTransport.request(self, method, origin_key, path, query, body)


class _TestBroker(AlpacaPaperBroker):
    _ALLOW_LIVE_TRANSPORT = True       # forward-compatible with W-B's MODE check

    def _fresh_enabled(self):
        # Mirrors the in-progress broker change: re-read the adapter through its own class, so the
        # live adapter re-reads alpaca_live.json (the committed broker re-reads alpaca_paper.json and
        # therefore fails closed in a live folder).
        if not self.adapter_state.enabled:
            return False
        fresh = type(self.adapter_state)(os.path.dirname(self.adapter_state.path))
        if not fresh.enabled:
            self.adapter_state.data = fresh.data
            return False
        return True


def _broker(transport, state_dir, label, adapter_state):
    return _TestBroker(transport, state_dir, A.LABEL_MOCK_LOCAL, adapter_state)


class FixedClock(object):
    name = "FIXED TEST CLOCK"

    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t

    def on_check(self, calendar, minutes):
        return self.t


class FakeAuthorization(object):
    """Shape of alpaca/live.py LiveAuthorization (synthetic)."""

    def __init__(self, limits, state_dir, shares=None, ok=True):
        self.limits = limits
        self.limits_hash = limits["hash"]
        self.shares = int(limits["values"]["fixed_shares"]) if shares is None else shares
        self.state_dir = state_dir
        self._ok = ok

    def valid(self, now_monotonic):
        return self._ok


def _transport(cls=LiveShapedMock):
    return cls(trading=MockTrading(), data=MockData(days=AS.AlpacaSessionController._mock_days()))


def _posts(c):
    return [b for (m, p, q, b) in c.transport.trading.calls if m == "POST" and p == "/v2/orders"]


def _venue(c, is_open=True, now=None):
    now = now or c.clock.now()
    c.transport.trading.clock = {"timestamp": AS.iso(now), "is_open": is_open,
                                 "next_open": AS.iso(now), "next_close": AS.iso(now)}


def _fresh_quote(c):
    def rq(transport, now):
        return {"feed": "iex", "symbol": A.SYMBOL, "valid": True, "fresh": True, "reason": "FRESH",
                "bid": 399.98, "ask": 400.02, "spread_usd": 0.04, "spread_bps": 1.0,
                "quote_utc": AS.iso(now), "age_s": 0.5}
    return rq


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="desk-night-")
        self.ctrls = []
        self._rq = AS.read_quote

    def tearDown(self):
        AS.read_quote = self._rq
        for c in self.ctrls:
            try:
                c.close()
            except Exception:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def snapshot(self, sub="lim", **vals):
        d = os.path.join(self.tmp, sub)
        os.makedirs(d, exist_ok=True)
        v = {"fixed_shares": 10, "per_trade_notional": 6000.0, "gross_exposure": 12000.0,
             "max_loss_per_trade": 150.0, "daily_loss": 300.0}
        v.update(vals)
        sizing.save_draft(d, v)
        seen = sizing.read_draft(d)
        prior = None
        if os.path.exists(sizing.approved_path(d)):
            prior = sizing.load_limits(path=sizing.approved_path(d))["hash"]
        sizing.approve(d, sizing.CONFIRM_PHRASE, "synthetic test approval",
                       reviewed_draft_hash=sizing.content_hash(seen.get("values")), prior_approved_hash=prior)
        return d, sizing.load_limits(path=sizing.approved_path(d))

    def live(self, sub="live", snap=None, clock="mock", **kw):
        sd = os.path.join(self.tmp, sub)
        if snap is None:
            _d, snap = self.snapshot(sub + "-lim")
        if clock == "mock":
            clock = AS.MockClock(sd, AS.SessionCalendar.nyse_2026_2027())
        kw.setdefault("transport", _transport())
        kw.setdefault("broker_factory", _broker)
        if "authorization" not in kw:
            kw.setdefault("limits_snapshot", snap)
            kw.setdefault("limits_hash", snap["hash"])
        c = AS.AlpacaSessionController(sd, strategy="ema", mode="live", clock=clock, **kw)
        self.ctrls.append(c)
        return c

    def armed_live(self):
        c = self.live()
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])
        c.check_new_bars()
        _venue(c)
        self.assertTrue(c.connection_check()["ok"])
        r = c.arm()
        self.assertTrue(r.get("ok"), r)
        return c


class LiveModeWiring(_Base):
    def test_live_labels_and_state_are_truthful(self):
        c = self.live()
        self.assertEqual(c.broker_mode, "alpaca-live")
        self.assertEqual(c.evidence_label, AS.LABEL_ALPACA_LIVE)
        st = c.session_state()
        self.assertTrue(st["live"])
        self.assertEqual(st["mode"], "live")
        self.assertFalse(st["simulated"])
        self.assertIn("ALPACA LIVE", st["badge"])
        self.assertIn("REAL MONEY", st["external_broker_badge"])
        self.assertIn("REAL MONEY", st["fill_model"])
        self.assertIn("live session", st["schedule"]["note"])
        self.assertEqual(st["adapter"]["path_name"], AS.LIVE_STATE_FILE)
        for k in ("account", "exposure", "fills"):
            self.assertIn(k, st["ownership"])
        c.alpaca_enable(confirm=True)
        self.assertTrue(os.path.exists(os.path.join(c.state_dir, AS.LIVE_STATE_FILE)))
        self.assertFalse(os.path.exists(os.path.join(c.state_dir, AS.PAPER_STATE_FILE)))

    def test_limits_snapshot_is_never_reread_from_disk(self):
        d, snap = self.snapshot("ondisk")
        c = self.live(snap=snap)
        self.assertEqual(c.limits["max_loss_per_trade"], 150.0)
        self.snapshot("ondisk", max_loss_per_trade=90.0, fixed_shares=4)    # disk changes after launch
        self.assertEqual(sizing.load_limits(path=sizing.approved_path(d))["values"]["max_loss_per_trade"], 90.0)
        self.assertEqual(c.limits["max_loss_per_trade"], 150.0)
        self.assertEqual(c.strategy_cfg["fixed_qty"], 10)
        self.assertTrue([x for x in c.preflight() if x["check"] == "limits loaded"][0]["ok"])
        self.assertIs(c._limits_snapshot, snap)

    def test_mutated_snapshot_fails_preflight(self):
        _d, snap = self.snapshot("mut")
        c = self.live(snap=snap)
        snap["values"]["max_loss_per_trade"] = 999.0
        lim = [x for x in c.preflight() if x["check"] == "limits loaded"][0]
        self.assertFalse(lim["ok"])
        self.assertIn("changed after approval", lim["detail"])

    def test_authorization_input(self):
        _d, snap = self.snapshot("auth")
        sd = os.path.join(self.tmp, "auth-live")
        c = self.live(sub="auth-live", snap=snap, authorization=FakeAuthorization(snap, sd))
        self.assertEqual(c.broker_mode, "alpaca-live")
        for bad in (FakeAuthorization(snap, sd, ok=False), FakeAuthorization(snap, sd, shares=3),
                    FakeAuthorization(snap, os.path.join(self.tmp, "elsewhere"))):
            with self.assertRaises(AS.LiveModeRefused):
                self.live(sub="auth-live", snap=snap, authorization=bad)

    def test_transport_and_folder_separation(self):
        _d, snap = self.snapshot("sep")
        with self.assertRaises(AS.LiveModeRefused):          # live never takes a paper/mock transport
            self.live(sub="a", snap=snap, transport=_transport(MockAlpacaTransport))
        with self.assertRaises(AS.LiveModeRefused):          # live needs a transport
            self.live(sub="a2", snap=snap, transport=None)
        with self.assertRaises(AS.LiveModeRefused):          # paper never takes a live transport
            AS.AlpacaSessionController(os.path.join(self.tmp, "b"), mode="https", transport=_transport(),
                                       broker_factory=_broker)
        with self.assertRaises(AS.LiveModeRefused):          # mock never takes live inputs
            AS.AlpacaSessionController(os.path.join(self.tmp, "b2"), limits_snapshot=snap,
                                       limits_hash=snap["hash"])
        with self.assertRaises(AS.LiveModeRefused):          # limits are never a path in live
            self.live(sub="c", snap=snap, limits_path="/nonexistent/approved.json")
        with self.assertRaises(AS.LiveModeRefused):          # hash mismatch
            self.live(sub="d", snap=snap, limits_hash="0" * 64)
        draft = dict(snap, provenance="draft")
        with self.assertRaises(AS.LiveModeRefused):
            self.live(sub="e", snap=draft, limits_hash=draft["hash"])
        paper_dir = os.path.join(self.tmp, "paperdir")
        os.makedirs(paper_dir)
        with open(os.path.join(paper_dir, AS.PAPER_STATE_FILE), "w") as fh:
            fh.write("{}")
        with self.assertRaises(AS.LiveModeRefused):          # live never shares the paper folder
            self.live(sub="paperdir", snap=snap)
        live_dir = os.path.join(self.tmp, "livedir")
        os.makedirs(live_dir)
        with open(os.path.join(live_dir, AS.LIVE_STATE_FILE), "w") as fh:
            fh.write("{}")
        with self.assertRaises(AS.LiveModeRefused):          # paper never shares the live folder
            AS.AlpacaSessionController(live_dir, mode="https", transport=_transport(MockAlpacaTransport),
                                       broker_factory=_broker)

    def test_missing_live_broker_refuses_without_paper_fallback(self):
        _d, snap = self.snapshot("nobroker")
        try:
            import alpaca.live as L
            has = hasattr(L, "AlpacaLiveBroker")
        except Exception:
            has = False
        if has:
            self.skipTest("alpaca.live.AlpacaLiveBroker exists in this checkout")
        with self.assertRaises(Exception) as cm:
            self.live(sub="nobroker", snap=snap, broker_factory=None)
        self.assertNotIsInstance(cm.exception, AssertionError)

    def test_connection_check_is_get_only(self):
        c = self.live()
        _venue(c)
        n0 = len(c.transport.trading.calls)
        before = [x for x in c.preflight() if x["check"] == "live connection check"][0]
        self.assertFalse(before["ok"])
        r = c.connection_check()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["orders_sent"], 0)
        new = c.transport.trading.calls[n0:]
        self.assertTrue(new)
        self.assertEqual({m for (m, p, q, b) in new}, {"GET"})
        self.assertEqual({p for (m, p, q, b) in new}, {"/v2/account", "/v2/clock", "/v2/assets/SPY"})
        self.assertEqual(_posts(c), [])
        self.assertFalse(c.adapter_state.enabled)
        self.assertNotIn("buying_power", repr(r))
        self.assertTrue([x for x in c.preflight() if x["check"] == "live connection check"][0]["ok"])
        self.assertTrue(c.session_state()["connection_check"]["ok"])

    def test_live_arm_requires_connection_check(self):
        c = self.live()
        c.alpaca_enable(confirm=True)
        c.check_new_bars()
        _venue(c)
        r = c.arm()
        self.assertFalse(r["ok"])
        self.assertIn("live connection check", [f["check"] for f in r["failed"]])

    def test_protective_stop_attaches_in_live_mode(self):
        c = self.armed_live()
        c._fetch = lambda after, now: ([], [])
        px = float(c.bars[-1]["close"])
        did = "night-live-entry-0001"
        c.decisions.append({"decision_id": did, "invalidation": px - 2.0})
        c.mgr.submit_intent({"decision_id": did, "kind": "entry", "side": "buy", "qty": 3,
                             "limit": round(px + 0.5, 2), "ref_price": px, "intended_entry": px,
                             "invalidation": px - 2.0})
        c.transport.trading.advance(px)
        _venue(c)
        c.check_new_bars()
        stops = [b for b in _posts(c) if b.get("type") == "stop"]
        self.assertTrue(stops, _posts(c))
        self.assertEqual(stops[0]["side"], "sell")


class EntryGates(_Base):
    def _bounds(self, c, bar):
        d = {"decision_id": "night-gate-0001"}
        return d, c._entry_bounds(d, bar, c.mgr.state(), 1, "buy", 400.0, 395.0)

    def test_sparse_hour_refused_and_shown(self):
        c = self.armed_live()
        AS.read_quote = _fresh_quote(c)
        _venue(c)
        for n, exp in ((12, 60), (49, 60), (10, 30)):
            d, (limit, refusal) = self._bounds(c, {"bar_count_1min": n, "minutes_expected": exp})
            self.assertIsNone(limit)
            self.assertEqual(refusal[0], "SPARSE_HOUR", (n, exp))
        st = c.session_state()["last_entry_refusal"]
        self.assertEqual(st["code"], "SPARSE_HOUR")
        self.assertIn("10 of 30", st["detail"])
        d, (limit, refusal) = self._bounds(c, {"bar_count_1min": None, "minutes_expected": 60})
        self.assertEqual(refusal[0], "SPARSE_HOUR")                      # unknown count fails closed
        for n, exp in ((60, 60), (50, 60), (30, 30)):                    # complete or >= minimum
            d, (limit, refusal) = self._bounds(c, {"bar_count_1min": n, "minutes_expected": exp})
            self.assertIsNone(refusal, (n, exp, refusal))
        self.assertEqual(_posts(c), [])

    def test_venue_closed_after_arm_holds_entry(self):
        c = self.armed_live()
        AS.read_quote = _fresh_quote(c)
        _venue(c, is_open=False)                    # venue halts/closes after Arm
        d, (limit, refusal) = self._bounds(c, {"bar_count_1min": 60, "minutes_expected": 60})
        self.assertIsNone(limit)
        self.assertEqual(refusal[0], "VENUE_CLOSED")
        self.assertFalse(d["venue_recheck"]["ok"])
        self.assertEqual(c.session_state()["last_entry_refusal"]["code"], "VENUE_CLOSED")
        self.assertEqual(_posts(c), [])

    def test_outside_regular_session_holds_entry(self):
        c = self.armed_live()
        AS.read_quote = _fresh_quote(c)
        day = c.clock.now().date()
        c.clock = FixedClock(_dt.datetime(day.year, day.month, day.day, 23, 30, tzinfo=_dt.timezone.utc))
        _venue(c, is_open=True)                     # even a venue claiming "open" is not enough
        d, (limit, refusal) = self._bounds(c, {"bar_count_1min": 60, "minutes_expected": 60})
        self.assertEqual(refusal[0], "SESSION_NOT_REGULAR")
        self.assertEqual(_posts(c), [])

    def test_https_paper_mode_has_the_same_gates(self):
        sd = os.path.join(self.tmp, "paper")
        lim_dir, _snap = self.snapshot("paper-lim")
        c = AS.AlpacaSessionController(sd, strategy="ema", mode="https",
                                       transport=_transport(MockAlpacaTransport), broker_factory=_broker,
                                       limits_path=sizing.approved_path(lim_dir),
                                       clock=AS.MockClock(sd, AS.SessionCalendar.nyse_2026_2027()))
        self.ctrls.append(c)
        AS.read_quote = _fresh_quote(c)
        _venue(c, is_open=False)
        d, (limit, refusal) = self._bounds(c, {"bar_count_1min": 60, "minutes_expected": 60})
        self.assertEqual(refusal[0], "VENUE_CLOSED")
        d, (limit, refusal) = self._bounds(c, {"bar_count_1min": 20, "minutes_expected": 60})
        self.assertEqual(refusal[0], "SPARSE_HOUR")


class ExpiryWithoutBars(_Base):
    def test_expiry_disarms_during_data_outage(self):
        c = self.armed_live()
        exp = AS.parse_ts(c.mgr.state()["expires_utc"])

        def outage(after, now):
            raise RuntimeError("HTTP 503 from bar feed (synthetic)")
        c._fetch = outage
        c.clock = FixedClock(exp - _dt.timedelta(minutes=5))
        c.check_new_bars()                                     # outage before expiry: still armed
        self.assertTrue(c.mgr.state()["armed"])
        self.assertIsNotNone(c.session_state()["data_outage"])
        self.assertEqual(c.session_state()["data_outage"]["failures"], 1)
        c.clock = FixedClock(exp + _dt.timedelta(minutes=1))
        c.check_new_bars()                                     # expiry on the desk clock, no bar needed
        self.assertFalse(c.mgr.state()["armed"])
        self.assertTrue(c._controls()["stopped"])
        self.assertFalse(c.adapter_state.enabled)
        st = c.session_state()
        self.assertEqual(st["data_outage"]["failures"], 2)
        self.assertIn("unavailable since", st["data_outage"]["detail"])
        self.assertEqual(st["last_expiry"]["expires_utc"], AS.iso(exp))
        self.assertIsNotNone(st["last_check"]["expiry"])
        self.assertFalse(st["last_check"]["ok"])
        self.assertEqual(_posts(c), [])

    def test_outage_clears_on_next_good_fetch(self):
        c = self.live()
        c.alpaca_enable(confirm=True)
        real = c._fetch

        def outage(after, now):
            raise RuntimeError("HTTP 503 (synthetic)")
        c._fetch = outage
        c.check_new_bars()
        self.assertIsNotNone(c.session_state()["data_outage"])
        c._fetch = real
        c.check_new_bars()
        self.assertIsNone(c.session_state()["data_outage"])
        self.assertIn("data_outage_cleared", c.last_check)


class MockStillStarts(_Base):
    def test_mock_mode_starts_and_reports_mock(self):
        c = AS.AlpacaSessionController(os.path.join(self.tmp, "mock"), strategy="ema")
        self.ctrls.append(c)
        st = c.session_state()
        self.assertEqual(st["broker_mode"], "alpaca-mock")
        self.assertFalse(st["live"])
        self.assertTrue(st["simulated"])
        self.assertIsNone(st["data_outage"])
        self.assertNotIn("ownership", st)
        c.alpaca_enable(confirm=True)
        c.check_new_bars()
        self.assertTrue(c.last_check["ok"])
        self.assertTrue(c.arm().get("ok"))


if __name__ == "__main__":
    unittest.main()
