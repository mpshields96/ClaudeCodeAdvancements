"""Night controller checks: operator-started live mode wiring plus three entry/expiry safety fixes.

Everything here is offline. Live mode is built from the REAL alpaca/live.py classes: a
LiveAuthorization minted by the live gate over TEST VALUE limits in a temp dir, and a real
LiveHttpsTransport (injected False) with a synthetic live-shaped key whose opener is swapped,
after construction, for an in-process venue (MockTrading + MockData). No socket opens, no key or
Keychain is read (NoNetworkNoKeys guards every test), no account is touched, no order leaves the
process. This is operational readiness only; it says nothing about the strategy's edge.
"""
import datetime as _dt
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.dirname(os.path.abspath(__file__))
for _p in (DESK, TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpaca as A  # noqa: E402
import alpaca_session as AS  # noqa: E402
import session as S  # noqa: E402
from alpaca import live as L  # noqa: E402
from alpaca import sizing  # noqa: E402
from alpaca.broker import AlpacaLiveBroker, AlpacaPaperBroker  # noqa: E402
from alpaca.mock import MockAlpacaTransport, MockTrading  # noqa: E402
from alpaca.mock_data import MockData  # noqa: E402
from alpaca.transport import HttpsTransport, StaticTestProvider, TransportRefused  # noqa: E402
from test_alpaca_broker import SYNTH_KEY, SYNTH_SECRET, FakeResp  # noqa: E402
from test_alpaca_live import (LIVE_SYNTH_KEY, NOW, SWAPPED_LIVE_VALUES, NoNetworkNoKeys,  # noqa: E402
                              approve_live_dir, shown_hash)


class LiveVenueOpener(object):
    """Stands in for urllib's opener behind the real LiveHttpsTransport: trading paths go to
    MockTrading, data paths to MockData, the asset lookup gets a synthetic answer. No socket."""

    def __init__(self, trading, data):
        self.trading, self.data, self.requests = trading, data, []
        self.asset = {"symbol": A.SYMBOL, "tradable": True, "status": "active"}
        self.account = None                 # when set, served for /v2/account instead of MockTrading's

    def open(self, req, timeout=None):
        self.requests.append(req)
        url = req.full_url
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query)) or None
        body = json.loads(req.data.decode()) if req.data else None
        method = req.get_method()
        if method == "GET" and parts.path == "/v2/assets/" + A.SYMBOL:
            self.trading.calls.append((method, parts.path, {}, None))
            st, payload = 200, dict(self.asset)
        elif method == "GET" and parts.path == "/v2/account" and self.account is not None:
            self.trading.calls.append((method, parts.path, {}, None))
            st, payload = 200, dict(self.account)
        elif parts.netloc.startswith("data."):
            st, payload = self.data.handle(method, parts.path, query)
        else:
            st, payload = self.trading.handle(method, parts.path, query, body)
            if method == "GET" and parts.path == "/v2/account" and st == 200:
                # Alpaca documents this field on GET /v2/account; the local mock omits it.
                payload = dict(payload, trade_suspended_by_user=False)
        if st >= 400:
            raise urllib.error.HTTPError(url, st, "err", {}, io.BytesIO(json.dumps(payload or {}).encode()))
        return FakeResp(st, payload, url)


class LiveShapedMock(MockAlpacaTransport):
    """An injected mock dressed as live (MODE="live"); live mode must refuse it."""
    MODE = "live"


class _TestBroker(AlpacaPaperBroker):
    pass


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
    """Shape of LiveAuthorization without the gate's mint; live mode must refuse it."""

    def __init__(self, auth):
        self.__dict__.update(auth.__dict__)

    def valid(self, now_monotonic):
        return True


def _mock_transport(cls=MockAlpacaTransport):
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
        self.guard = NoNetworkNoKeys().__enter__()
        self.tmp = tempfile.mkdtemp(prefix="desk-night-")
        self.ctrls = []
        self._rq = AS.read_quote
        self.mono = [1000.0]

    def tearDown(self):
        AS.read_quote = self._rq
        for c in self.ctrls:
            try:
                c.close()
            except Exception:
                pass
        self.guard.__exit__(None, None, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def snapshot(self, sub="lim", **vals):
        """Paper TEST VALUE limits approved through alpaca/sizing (for the https paper comparisons)."""
        d = os.path.join(self.tmp, sub)
        os.makedirs(d, exist_ok=True)
        v = {"fixed_shares": 10, "per_trade_notional": 6000.0, "gross_exposure": 12000.0,
             "max_loss_per_trade": 150.0, "daily_loss": 300.0}
        v.update(vals)
        sizing.save_draft(d, v)
        seen = sizing.read_draft(d)
        sizing.approve(d, sizing.CONFIRM_PHRASE, "synthetic test approval",
                       reviewed_draft_hash=sizing.content_hash(seen.get("values")), prior_approved_hash=None)
        return d, sizing.load_limits(path=sizing.approved_path(d))

    def gate(self, root):
        """Approve TEST VALUE live limits in root/state-alpaca-live and run the real live gate."""
        root = os.path.join(self.tmp, root)
        os.makedirs(root, exist_ok=True)
        live_dir, limits = approve_live_dir(root)
        return self.authorize(live_dir, limits)

    def authorize(self, live_dir, limits):
        phrase = L.confirm_phrase(1, L.session_date(NOW))
        return L.live_gate_authorize(limits, live_dir, L.LIVE_PORT, phrase, True, now_utc=NOW,
                                     monotonic=lambda: self.mono[0], shown_hash=shown_hash(limits))

    def live_transport(self, auth, venue=None):
        t = L.LiveHttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"), auth,
                                 monotonic=lambda: self.mono[0])
        self.assertFalse(t.injected)
        trading = MockTrading()
        t._opener = venue or LiveVenueOpener(trading, MockData(days=AS.AlpacaSessionController._mock_days()))
        t.trading = t._opener.trading      # TEST ONLY: lets the checks read the synthetic venue
        return t

    def live(self, root="live", auth=None, clock="mock", **kw):
        auth = auth or self.gate(root)
        sd = kw.pop("state_dir", auth.state_dir)
        if clock == "mock":
            clock = AS.MockClock(sd, AS.SessionCalendar.nyse_2026_2027())
        if "transport" not in kw:
            kw["transport"] = self.live_transport(auth)
        kw.setdefault("live_authorization", auth)
        c = AS.AlpacaSessionController(sd, strategy="ema", mode="live", clock=clock, **kw)
        self.ctrls.append(c)
        return c

    def refused(self, **kw):
        with self.assertRaises(AS.LiveModeRefused):
            self.live(**kw)

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
    def test_live_labels_rows_and_state_are_truthful(self):
        c = self.live()
        self.assertIsInstance(c.broker, AlpacaLiveBroker)
        self.assertIsInstance(c.adapter_state, L.LiveAdapterState)
        self.assertEqual(c.broker_mode, "alpaca-live")
        self.assertEqual(c.evidence_label, L.LABEL_ALPACA_LIVE)
        self.assertEqual(c._row_flags()["simulated"], False)
        self.assertEqual(c._row_flags()["evidence"], L.LABEL_ALPACA_LIVE)
        st = c.session_state()
        self.assertTrue(st["live"])
        self.assertEqual(st["mode"], "live")
        self.assertFalse(st["simulated"])
        self.assertIn("ALPACA LIVE", st["badge"])
        self.assertIn("REAL MONEY", st["external_broker_badge"])
        self.assertIn("REAL MONEY", st["fill_model"])
        self.assertIn("live session", st["schedule"]["note"])
        self.assertEqual(st["adapter"]["path_name"], L.LIVE_STATE_FILE)
        for k in ("account", "exposure", "fills"):
            self.assertIn(k, st["ownership"])
        self.assertFalse(c.adapter_state.enabled)                 # the live adapter starts disabled
        c.alpaca_enable(confirm=True)
        self.assertTrue(os.path.exists(os.path.join(c.state_dir, L.LIVE_STATE_FILE)))
        self.assertFalse(os.path.exists(os.path.join(c.state_dir, AS.PAPER_STATE_FILE)))

    def test_limits_file_swapped_after_authorization_is_ignored(self):
        auth = self.gate("swap")
        root = os.path.dirname(auth.state_dir)
        approve_live_dir(root, SWAPPED_LIVE_VALUES)                # swapped before the controller is built
        on_disk = sizing.load_limits(path=sizing.approved_path(auth.state_dir), allow_draft=False)
        self.assertEqual(on_disk["values"]["max_loss_per_trade"], 100.0)
        c = self.live(auth=auth)
        self.assertEqual(c.limits["max_loss_per_trade"], 10.0)    # the snapshot the operator approved
        self.assertEqual(c.limits["daily_loss"], 30.0)
        self.assertEqual(c.strategy_cfg["fixed_qty"], 1)
        self.assertIs(c._limits_snapshot, auth.limits)
        self.assertEqual(c._limits_hash, auth.limits_hash)
        approve_live_dir(root, dict(SWAPPED_LIVE_VALUES, max_loss_per_trade=7.0))   # and again after
        self.assertEqual(c.limits["max_loss_per_trade"], 10.0)
        self.assertTrue([x for x in c.preflight() if x["check"] == "limits loaded"][0]["ok"])

    def test_mutated_snapshot_fails_preflight(self):
        auth = self.gate("mut")
        c = self.live(auth=auth)
        auth.limits["values"]["max_loss_per_trade"] = 999.0
        lim = [x for x in c.preflight() if x["check"] == "limits loaded"][0]
        self.assertFalse(lim["ok"])
        self.assertIn("changed after approval", lim["detail"])

    def test_paper_injected_and_foreign_transports_are_refused(self):
        auth = self.gate("tx")
        self.refused(auth=auth, transport=None)
        self.refused(auth=auth, transport=_mock_transport())
        self.refused(auth=auth, transport=_mock_transport(LiveShapedMock))
        self.refused(auth=auth, transport=HttpsTransport(StaticTestProvider(SYNTH_KEY, SYNTH_SECRET),
                                                         opener=LiveVenueOpener(MockTrading(), None)))
        injected = L.LiveHttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"), auth,
                                        opener=LiveVenueOpener(MockTrading(), None),
                                        monotonic=lambda: self.mono[0])
        self.assertTrue(injected.injected)
        self.refused(auth=auth, transport=injected)
        other = self.authorize(auth.state_dir, sizing.approved_path(auth.state_dir))   # another gate run
        self.refused(auth=auth, transport=self.live_transport(other))
        self.refused(auth=FakeAuthorization(auth), transport=self.live_transport(auth))
        self.refused(auth=auth, live_authorization=None)
        t = self.live_transport(auth)
        self.mono[0] += L.AUTH_MAX_AGE_S + 1                     # the authorization expires
        self.refused(auth=auth, transport=t)
        with self.assertRaises(TransportRefused):                 # and the transport refuses to send
            t.request("GET", "trading", "/v2/account")

    def test_state_folder_binding(self):
        auth = self.gate("dirs")
        self.refused(auth=auth, limits_path=sizing.approved_path(auth.state_dir))   # never a limits path
        elsewhere = os.path.join(self.tmp, "elsewhere", L.LIVE_STATE_DIRNAME)
        os.makedirs(elsewhere)
        self.refused(auth=auth, state_dir=elsewhere)               # not the folder the gate authorized
        misnamed = os.path.join(self.tmp, "state-alpaca-paper")
        os.makedirs(misnamed)
        self.refused(auth=auth, state_dir=misnamed)                # a paper-named folder
        with open(os.path.join(auth.state_dir, AS.PAPER_STATE_FILE), "w") as fh:
            fh.write("{}")
        self.refused(auth=auth)                                    # paper adapter file in the live folder

    def test_paper_and_mock_never_take_live_inputs(self):
        auth = self.gate("sep")
        lt = self.live_transport(auth)
        with self.assertRaises(AS.LiveModeRefused):                # paper never takes a live transport
            AS.AlpacaSessionController(os.path.join(self.tmp, "b"), mode="https", transport=lt,
                                       broker_factory=_broker)
        with self.assertRaises(AS.LiveModeRefused):                # mock never takes a live authorization
            AS.AlpacaSessionController(os.path.join(self.tmp, "b2"), live_authorization=auth)
        live_dir = os.path.join(self.tmp, "livedir")
        os.makedirs(live_dir)
        with open(os.path.join(live_dir, L.LIVE_STATE_FILE), "w") as fh:
            fh.write("{}")
        with self.assertRaises(AS.LiveModeRefused):                # paper never shares the live folder
            AS.AlpacaSessionController(live_dir, mode="https", transport=_mock_transport(),
                                       broker_factory=_broker)
        lim_dir, _snap = self.snapshot("paper-lim")
        sd = os.path.join(self.tmp, "paper")
        p = AS.AlpacaSessionController(sd, strategy="ema", mode="https", transport=_mock_transport(),
                                       broker_factory=_broker, limits_path=sizing.approved_path(lim_dir),
                                       clock=AS.MockClock(sd, AS.SessionCalendar.nyse_2026_2027()))
        self.ctrls.append(p)
        self.assertEqual(p.broker_mode, "alpaca-paper")
        self.assertFalse(p.session_state()["live"])
        self.assertNotIsInstance(p.adapter_state, L.LiveAdapterState)
        self.assertNotEqual(p.evidence_label, L.LABEL_ALPACA_LIVE)

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
        self.assertEqual({r.full_url.split("/")[2] for r in c.transport._opener.requests},
                         {"api.alpaca.markets"} | ({"data.alpaca.markets"} if any(
                             "data." in r.full_url for r in c.transport._opener.requests) else set()))
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
        c.mgr.submit_intent({"decision_id": did, "kind": "entry", "side": "buy", "qty": 1,
                             "limit": round(px + 0.5, 2), "ref_price": px, "intended_entry": px,
                             "invalidation": px - 2.0})
        c.transport.trading.advance(px)
        _venue(c)
        c.check_new_bars()
        stops = [b for b in _posts(c) if b.get("type") == "stop"]
        self.assertTrue(stops, _posts(c))
        self.assertEqual(stops[0]["side"], "sell")
        hosts = {r.full_url.split("/")[2] for r in c.transport._opener.requests}
        self.assertNotIn("paper-api.alpaca.markets", hosts)


def _flags_true(obj, where, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "simulated" and v is not False:
                out.append(where)
            _flags_true(v, where, out)
    elif isinstance(obj, list):
        for v in obj:
            _flags_true(v, where, out)


def _sim_values(path):
    """Every "simulated" value anywhere in every row of one desk file, as {row_label: [values]}."""
    with open(path) as fh:
        text = fh.read()
    rows = [json.loads(x) for x in text.splitlines() if x.strip()] if path.endswith(".jsonl") \
        else [json.loads(text)]
    found = {}

    def walk(obj, label):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "simulated":
                    found.setdefault(label, []).append(v)
                walk(v, label)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, label)
    for i, r in enumerate(rows):
        walk(r, "%s#%d:%s" % (os.path.basename(path), i,
                              (r.get("kind") or r.get("rec") or "") if isinstance(r, dict) else ""))
    return rows, found


MANAGER_FILES = ("controls.json", "intents.jsonl", "audit.jsonl", "ledger.jsonl")


def _persisted_simulated(state_dir):
    """Every file the desk wrote, every row: where simulated is anything but False."""
    out = []
    for name in sorted(os.listdir(state_dir)):
        path = os.path.join(state_dir, name)
        if not os.path.isfile(path) or not name.endswith((".json", ".jsonl")):
            continue
        with open(path) as fh:
            text = fh.read()
        rows = [json.loads(x) for x in text.splitlines() if x.strip()] if name.endswith(".jsonl") \
            else [json.loads(text)]
        for i, r in enumerate(rows):
            _flags_true(r, "%s#%d:%s" % (name, i, r.get("kind") or r.get("rec") or "") if isinstance(r, dict)
                        else name, out)
    return out


class LiveEligibility(_Base):
    def _check_refused(self, c, field):
        _venue(c)
        r = c.connection_check()
        self.assertFalse(r["ok"], r)
        self.assertIn(field, json.dumps(r["checks"]))
        c.alpaca_enable(confirm=True)
        c.check_new_bars()
        _venue(c)
        a = c.arm()
        self.assertFalse(a["ok"])
        lc = [f for f in a["failed"] if f["check"] == "live connection check"][0]
        self.assertIn("nothing is sent", lc["detail"])
        self.assertEqual(_posts(c), [])
        self.assertFalse(c.mgr.state()["armed"])

    def test_malformed_account_blocks_arm(self):
        for acct, field in (({"status": "ACTIVE", "trading_blocked": None, "account_blocked": None}, "trading_blocked"),
                            ({"status": "ACTIVE"}, "account_blocked"),
                            ({"status": "ACCOUNT_CLOSED", "trading_blocked": False, "account_blocked": False}, "ACTIVE"),
                            ({"status": "ACTIVE", "trading_blocked": True, "account_blocked": False}, "trading_blocked"),
                            # Codex 6b97d48 retest: ACTIVE, both block flags false, suspended by the user.
                            ({"status": "ACTIVE", "trading_blocked": False, "account_blocked": False,
                              "trade_suspended_by_user": True}, "trade_suspended_by_user"),
                            ({"status": "ACTIVE", "trading_blocked": False, "account_blocked": False},
                             "trade_suspended_by_user"),
                            ({"status": "ACTIVE", "trading_blocked": False, "account_blocked": False,
                              "trade_suspended_by_user": None}, "trade_suspended_by_user")):
            c = self.live(root="acct-%d" % len(self.ctrls))
            c.transport._opener.account = acct
            self._check_refused(c, field)

    def test_wrong_or_inactive_asset_blocks_arm(self):
        for asset, field in (({"symbol": "QQQ", "tradable": True, "status": "inactive"}, "QQQ"),
                             ({"symbol": "SPY", "tradable": True, "status": "inactive"}, "inactive"),
                             ({"symbol": "SPY", "tradable": None, "status": "active"}, "tradable"),
                             ({}, "symbol")):
            c = self.live(root="asset-%d" % len(self.ctrls))
            c.transport._opener.asset = asset
            self._check_refused(c, field)

    def test_unparseable_clock_blocks_arm(self):
        c = self.live()
        _venue(c)
        c.transport.trading.clock = dict(c.transport.trading.clock, timestamp="not-a-time")
        r = c.connection_check()
        self.assertFalse(r["ok"])
        self.assertFalse([x for x in r["checks"] if x["check"] == "clock"][0]["ok"])

    def test_stale_or_earlier_session_check_blocks_arm(self):
        real = AS._monotonic
        t = [5000.0]
        AS._monotonic = lambda: t[0]
        try:
            c = self.live()
            c.alpaca_enable(confirm=True)
            c.check_new_bars()
            _venue(c)
            self.assertTrue(c.connection_check()["ok"])
            t[0] += AS.CONNECTION_CHECK_MAX_AGE_S + 1
            a = c.arm()
            self.assertFalse(a["ok"])
            self.assertIn("old", [f for f in a["failed"] if f["check"] == "live connection check"][0]["detail"])
            self.assertTrue(c.connection_check()["ok"])
            self.assertTrue(c.arm()["ok"])
            c.mgr.disarm(reason="TEST")
            a = c.arm()                                          # a check made before the last Arm
            self.assertFalse(a["ok"])
            self.assertIn("earlier session",
                          [f for f in a["failed"] if f["check"] == "live connection check"][0]["detail"])
        finally:
            AS._monotonic = real
        self.assertEqual(_posts(c), [])

    def _date_check(self, c):
        pf = c.preflight()
        checks = pf["checks"] if isinstance(pf, dict) else pf
        return [x for x in checks if x["check"] == "live authorization date"]

    def test_live_limits_source_label_says_live(self):
        c = self.live()
        lab = c.limits_source.get("label") or ""
        self.assertIn("LIVE", lab)
        self.assertNotIn("PAPER", lab)
        self.assertEqual(c.limits_source.get("hash"), c._limits_hash)
        self.assertEqual(c.limits_source.get("hash"), c.live_authorization.limits_hash)
        # Preflight still passes with the relabelled descriptor, and the arm that relies on it succeeds.
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])
        c.check_new_bars()
        _venue(c)
        self.assertTrue(c.connection_check()["ok"])
        pf = c.preflight()
        checks = pf["checks"] if isinstance(pf, dict) else pf
        self.assertTrue(all(x["ok"] for x in checks), [x for x in checks if not x["ok"]])
        r = c.arm()
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(c.limits_source.get("hash"), c._limits_hash)

    def test_live_authorization_date_same_day_passes(self):
        c = self.armed_live()
        rows = self._date_check(c)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["ok"], rows[0])
        self.assertIn(c.live_authorization.session_date, rows[0]["detail"])

    def test_live_authorization_next_chicago_day_refuses_arm(self):
        c = self.live()
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])
        c.check_new_bars()
        c.clock = FixedClock(c.clock.now() + _dt.timedelta(days=1))
        _venue(c)
        c.connection_check()
        rows = self._date_check(c)
        self.assertFalse(rows[0]["ok"])
        self.assertIn("run the live gate again", rows[0]["detail"])
        r = c.arm()
        self.assertFalse(r.get("ok"), r)
        self.assertEqual(_posts(c), [])

    def test_every_live_entry_rechecks_eligibility(self):
        c = self.armed_live()
        c.transport._opener.asset = {"symbol": "QQQ", "tradable": True, "status": "inactive"}
        c._sparse_hour = lambda bar: None
        c._venue_recheck = lambda d: None
        AS.read_quote = _fresh_quote(c)
        d = {"decision_id": "elig-1"}
        px = float(c.bars[-1]["close"])
        out, held = c._entry_bounds_checked(d, c.bars[-1], c.mgr.state(), 1, "buy", px, px - 2.0)
        self.assertIsNone(out)
        self.assertEqual(held[0], "LIVE_ELIGIBILITY")
        self.assertIn("QQQ", held[1])
        self.assertFalse(d["live_eligibility"]["ok"])
        self.assertEqual(_posts(c), [])

    def test_user_suspended_account_rule(self):
        ok = {"status": "ACTIVE", "trading_blocked": False, "account_blocked": False}
        self.assertIsNone(AS._eligibility("account", dict(ok, trade_suspended_by_user=False)))
        for v in (True, None):
            self.assertIn("trade_suspended_by_user",
                          AS._eligibility("account", dict(ok, trade_suspended_by_user=v)))
        self.assertIn("trade_suspended_by_user", AS._eligibility("account", ok))
        # paper and mock: the local mock omits the field, so only an explicit true fails there
        self.assertIsNone(AS._eligibility("account", ok, live=False))
        self.assertIn("trade_suspended_by_user",
                      AS._eligibility("account", dict(ok, trade_suspended_by_user=True), live=False))

    def test_user_suspended_entry_recheck_holds(self):
        c = self.armed_live()
        c.transport._opener.account = {"status": "ACTIVE", "trading_blocked": False,
                                       "account_blocked": False, "trade_suspended_by_user": True}
        c._sparse_hour = lambda bar: None
        c._venue_recheck = lambda d: None
        AS.read_quote = _fresh_quote(c)
        d = {"decision_id": "susp-1"}
        px = float(c.bars[-1]["close"])
        out, held = c._entry_bounds_checked(d, c.bars[-1], c.mgr.state(), 4, "buy", px, px - 2.0)
        self.assertIsNone(out)
        self.assertEqual(held[0], "LIVE_ELIGIBILITY")
        self.assertIn("trade_suspended_by_user", held[1])
        self.assertEqual(_posts(c), [])

    def test_nanosecond_venue_clock_parses(self):
        self.assertEqual(AS.parse_venue_ts("2026-11-16T09:30:00.123456789-05:00"),
                         AS.parse_ts("2026-11-16T14:30:00.123456Z"))
        self.assertIsNone(AS._eligibility("clock", {"timestamp": "2026-11-16T09:30:00.123456789-05:00",
                                                    "is_open": True}))

    def test_live_persisted_rows_say_simulated_false(self):
        """controls.json, intents.jsonl, audit.jsonl, ledger.jsonl, desk_audit.jsonl, session.json
        and progress.json: every row from the first one on, nested values included, says simulated
        False, and Arm does. review.json says False at the top level. Lab and decision rows (and
        decision copies nested in review.json) are a known limitation in NIGHT_WD_STATUS.md."""
        c = self.live()
        self.assertIs(c.mgr.simulated, False)
        self.assertIs(c.simulated, False)
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])
        c.check_new_bars()
        _venue(c)
        self.assertTrue(c.connection_check()["ok"])
        armed = c.arm()
        self.assertTrue(armed["ok"], armed)
        self.assertIs(armed["simulated"], False)
        c._fetch = lambda after, now: ([], [])
        px = float(c.bars[-1]["close"])
        did = "night-live-rows-0001"
        c.decisions.append({"decision_id": did, "invalidation": px - 2.0})
        c.mgr.submit_intent({"decision_id": did, "kind": "entry", "side": "buy", "qty": 1,
                             "limit": round(px + 0.5, 2), "ref_price": px, "intended_entry": px,
                             "invalidation": px - 2.0})
        c.transport.trading.advance(px)
        _venue(c)
        c.check_new_bars()
        c._write_state()
        bad = []
        for n in MANAGER_FILES:
            rows, found = _sim_values(os.path.join(c.state_dir, n))
            self.assertTrue(rows, n)
            self.assertEqual(len(found), len(rows), "%s: a row without a simulated flag" % n)
            bad += [where for where, vals in found.items() if any(v is not False for v in vals)]
        ledger = rows
        self.assertTrue([r for r in ledger if r.get("fills")] or [r for r in ledger if r.get("evidence")], ledger)
        for n in ("desk_audit.jsonl", "session.json", "progress.json"):
            rows, found = _sim_values(os.path.join(c.state_dir, n))
            self.assertTrue(found, n)
            bad += [where for where, vals in found.items() if any(v is not False for v in vals)]
        with open(os.path.join(c.state_dir, "desk_audit.jsonl")) as fh:
            first = json.loads(fh.readline())
        self.assertEqual((first["kind"], first["simulated"]), ("session_config_bound", False))
        c.review()
        with open(os.path.join(c.state_dir, "review.json")) as fh:
            self.assertIs(json.load(fh)["simulated"], False)
        self.assertIs(c.session_state()["simulated"], False)
        self.assertEqual(bad, [])
        self.assertTrue([r for r in ledger if r.get("evidence") == L.LABEL_ALPACA_LIVE])

    def test_paper_rows_unchanged(self):
        lim_dir, _snap = self.snapshot("paper-rows")
        sd = os.path.join(self.tmp, "paper-rows-sd")
        p = AS.AlpacaSessionController(sd, strategy="ema", mode="https", transport=_mock_transport(),
                                       broker_factory=_broker, limits_path=sizing.approved_path(lim_dir),
                                       clock=AS.MockClock(sd, AS.SessionCalendar.nyse_2026_2027()))
        self.ctrls.append(p)
        p._write_state()
        self.assertIs(p.mgr.simulated, True)
        self.assertFalse(hasattr(p.broker, "rows_simulated"))
        with open(os.path.join(sd, "controls.json")) as fh:
            self.assertIs(json.load(fh)["simulated"], True)
        self._all_true(sd)
        self.assertIs(p.simulated, True)
        with open(os.path.join(sd, "desk_audit.jsonl")) as fh:
            self.assertIs(json.loads(fh.readline())["simulated"], True)

    def _all_true(self, sd):
        seen = 0
        for n in MANAGER_FILES:
            path = os.path.join(sd, n)
            if not os.path.exists(path):
                continue
            rows, found = _sim_values(path)
            for where, vals in found.items():
                seen += len(vals)
                self.assertTrue(all(v is True for v in vals), (where, vals))
        self.assertTrue(seen)

    def test_mock_rows_unchanged(self):
        sd = os.path.join(self.tmp, "mock-rows")
        c = AS.AlpacaSessionController(sd, strategy="ema")
        self.ctrls.append(c)
        self.assertIs(c.mgr.simulated, True)
        c.alpaca_enable(confirm=True)
        c.check_new_bars()
        self.assertTrue(c.arm().get("ok"))
        c._write_state()
        self._all_true(sd)


class SessionSimulatedFlag(unittest.TestCase):
    def test_keyword_must_be_bool(self):
        d = tempfile.mkdtemp(prefix="night-sess-sim-")
        self.addCleanup(shutil.rmtree, d, True)
        with self.assertRaises(ValueError):
            S.SessionController(state_dir=d, simulated="no")


class ManagerSimulatedFlag(unittest.TestCase):
    """orders.manager.OrderManager: the simulated keyword (fakes only, no network)."""

    def setUp(self):
        from orders.calendar import SessionCalendar
        from orders.fake_broker import FakeBroker
        self.cal = SessionCalendar.fixture_profile()
        self.FakeBroker = FakeBroker
        self.dir = tempfile.mkdtemp(prefix="night-mgr-sim-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.limits = {"per_trade_notional": 2000, "max_loss_per_trade": 10.0, "daily_loss": 30.0,
                       "gross_exposure": 2000, "label": "TEST VALUES"}

    def _mgr(self, sub, broker=None, **kw):
        from orders.manager import OrderManager
        m = OrderManager(os.path.join(self.dir, sub), broker or self.FakeBroker(seed=7), self.limits,
                         calendar=self.cal, **kw)
        self.addCleanup(m.close)
        return m

    def _values(self, m):
        out = []
        for n in ("controls.json", "intents.jsonl", "audit.jsonl"):
            path = os.path.join(m.state_dir, n)
            if os.path.exists(path):
                out += [v for vals in _sim_values(path)[1].values() for v in vals]
        return out

    def test_default_is_true_everywhere(self):
        m = self._mgr("default")
        m.arm()
        self.assertIs(m.simulated, True)
        self.assertIs(m.controls["simulated"], True)
        vals = self._values(m)
        self.assertTrue(vals)
        self.assertTrue(all(v is True for v in vals), vals)

    def test_false_from_the_first_row(self):
        m = self._mgr("false", simulated=False)
        res = m.arm()
        self.assertIs(res["simulated"], False)
        self.assertIs(m.controls["simulated"], False)
        alarm = m._add_alarm("TEST", "night", persist=True)
        self.assertIs(alarm["simulated"], False)
        vals = self._values(m)
        self.assertTrue(vals)
        self.assertTrue(all(v is False for v in vals), vals)

    def test_broker_rows_simulated_false(self):
        b = self.FakeBroker(seed=7)
        b.rows_simulated = False
        m = self._mgr("broker", broker=b)
        self.assertIs(m.simulated, False)
        self.assertTrue(all(v is False for v in self._values(m)))

    def test_explicit_keyword_wins_and_must_be_bool(self):
        b = self.FakeBroker(seed=7)
        b.rows_simulated = False
        self.assertIs(self._mgr("kw", broker=b, simulated=True).simulated, True)
        from orders.manager import OrderManager
        for bad in ("false", 0, None.__class__):
            with self.assertRaises(ValueError):
                OrderManager(os.path.join(self.dir, "bad"), self.FakeBroker(seed=7), self.limits,
                             calendar=self.cal, simulated=bad)


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
                                       transport=_mock_transport(), broker_factory=_broker,
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


class ExpiryHoldingPosition(_Base):
    """Codex P1 (expiry_holding): a filled position with its protective stop, then a data outage
    and expiry after the close. The manager must decide on the desk clock, not the last bar's."""

    def holding(self):
        c = self.armed_live()
        AS.read_quote = _fresh_quote(c)
        c._fetch = lambda after, now: ([], [])
        px = float(c.bars[-1]["close"])
        did = "night-holding-0001"
        c.decisions.append({"decision_id": did, "invalidation": px - 2.0})
        c.mgr.submit_intent({"decision_id": did, "kind": "entry", "side": "buy", "qty": 1,
                             "limit": round(px + 0.5, 2), "ref_price": px, "intended_entry": px,
                             "invalidation": px - 2.0})
        c.transport.trading.advance(px)
        _venue(c)
        c.check_new_bars()
        prot = [it for it in c.mgr._live(["protective"]) if it["side"] == "sell"]
        self.assertTrue(prot, "setup: the fill must have a working protective stop")
        return c, prot

    def calls_after(self, c, n):
        return [(m, p, b) for (m, p, q, b) in c.transport.trading.calls[n:] if m in ("POST", "DELETE")]

    def test_expiry_after_close_sends_nothing_and_keeps_stop(self):
        c, prot = self.holding()
        day = c.clock.now().date()
        bounds = c.calendar.session_bounds(day.isoformat())
        exp = AS.parse_ts(c.mgr.state()["expires_utc"])
        t = max(exp, bounds[1]) + _dt.timedelta(minutes=5)
        stale = c.mgr.now()
        self.assertLess(stale, t)

        def outage(after, now):
            raise RuntimeError("HTTP 503 from bar feed (synthetic)")
        c._fetch = outage
        c.clock = FixedClock(t)
        _venue(c, is_open=False)
        n = len(c.transport.trading.calls)
        check = c.check_new_bars()
        self.assertFalse(check["ok"])
        self.assertIsNotNone(check["expiry"])
        self.assertTrue(c._controls()["stopped"])
        self.assertFalse(c.mgr.state()["armed"])
        self.assertEqual(c.mgr.now(), t)                        # fed from the desk clock
        self.assertEqual(self.calls_after(c, n), [])            # no protective cancel, no market order
        still = [it["intent_id"] for it in c.mgr._live(["protective"])]
        self.assertEqual(still, [it["intent_id"] for it in prot])
        why = c._controls().get("close_pending") or ""
        self.assertIn("market closed", why)
        self.assertIn("held, protected by its working stop", why)
        self.assertIn("next regular session", why)

    def test_venue_closed_stop_and_close_sends_nothing_and_keeps_stop(self):
        c, prot = self.holding()
        t = c.mgr.now() + _dt.timedelta(minutes=10)              # calendar: regular hours
        c.clock = FixedClock(t)
        _venue(c, is_open=False)                                 # venue clock: closed
        n = len(c.transport.trading.calls)
        r = c.stop_and_close()
        self.assertTrue(r["stopped"])
        self.assertEqual(self.calls_after(c, n), [])
        self.assertEqual([it["intent_id"] for it in c.mgr._live(["protective"])],
                         [it["intent_id"] for it in prot])
        self.assertIn("held, protected by its working stop", r.get("status_text") or "")
        self.assertIn("venue clock says market closed", r.get("status_text") or "")
        self.assertIn("protective stop kept", r.get("status_text") or "")

    def test_unverified_venue_clock_stop_and_close_sends_nothing_and_keeps_stop(self):
        c, prot = self.holding()
        t = c.mgr.now() + _dt.timedelta(minutes=10)              # calendar: regular hours
        c.clock = FixedClock(t)
        c.transport.trading.clock = {"timestamp": AS.iso(t)}     # venue clock: no is_open, unverifiable
        n = len(c.transport.trading.calls)
        r = c.stop_and_close()
        self.assertTrue(r["stopped"])
        self.assertEqual(self.calls_after(c, n), [])             # 0 DELETE of the stop, 0 market POST
        self.assertEqual([it["intent_id"] for it in c.mgr._live(["protective"])],
                         [it["intent_id"] for it in prot])
        txt = r.get("status_text") or ""
        self.assertIn("clock unverified", txt)
        self.assertIn("protective stop kept", txt)

    def test_crossing_chicago_date_holds_entries_but_exits_and_reconcile_work(self):
        c, prot = self.holding()
        t = c.mgr.now() + _dt.timedelta(minutes=10)
        while True:                                              # next trading day, same time of day
            t += _dt.timedelta(days=1)
            if c.calendar.is_trading_day(t.date()):
                break
        bounds = c.calendar.session_bounds(t.date().isoformat())
        self.assertTrue(bounds[0] <= t < bounds[1], "setup: regular hours on the next day")
        c.clock = FixedClock(t)
        _venue(c, is_open=True)
        n = len(c.transport.trading.calls)
        c._sparse_hour = lambda bar: None
        c._venue_recheck = lambda d: None
        d = {"decision_id": "date-1"}
        px = float(c.bars[-1]["close"])
        out, held = c._entry_bounds_checked(d, c.bars[-1], c.mgr.state(), 1, "buy", px, px - 2.0)
        self.assertIsNone(out)
        self.assertEqual(held[0], "LIVE_AUTH_DATE")
        self.assertFalse(d["live_authorization_date"]["ok"])
        self.assertEqual(self.calls_after(c, n), [])             # entry held: 0 new orders
        self.assertEqual([it["intent_id"] for it in c.mgr._live(["protective"])],
                         [it["intent_id"] for it in prot])        # the stop is still working
        self.assertTrue(c.mgr.reconcile(reason="after-midnight")["connected"])
        r = c.stop_and_close()                                   # the exit still goes out
        self.assertTrue(r["stopped"])
        sent = [b for (m, p, q, b) in c.transport.trading.calls[n:] if m == "POST" and p == "/v2/orders"]
        self.assertTrue(any((b or {}).get("type") == "market" and (b or {}).get("side") == "sell" for b in sent), sent)

    def test_regular_hours_stop_and_close_still_closes(self):
        c, prot = self.holding()
        t = c.mgr.now() + _dt.timedelta(minutes=10)
        bounds = c.calendar.session_bounds(t.date().isoformat())
        self.assertTrue(bounds[0] <= t < bounds[1], "setup: still in regular hours")
        c.clock = FixedClock(t)
        _venue(c, is_open=True)
        n = len(c.transport.trading.calls)
        r = c.stop_and_close()
        self.assertTrue(r["stopped"])
        posts = [b for (m, p, b) in self.calls_after(c, n) if m == "POST"]
        self.assertTrue(any((b or {}).get("side") == "sell" and (b or {}).get("type") == "market"
                            for b in posts), (r, self.calls_after(c, n)))


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
