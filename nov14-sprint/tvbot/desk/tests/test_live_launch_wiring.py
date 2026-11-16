"""alpaca/live_launch.py start: what happens after the live gate passes.

Fakes only. The Keychain reader (subprocess.run) and outbound connections (socket.create_connection) raise;
the only socket opened is the loopback port probe on an OS-chosen port. The UI server, browser and Ctrl-C wait
are replaced, and the live transport's opener is a FakeOpener over MockTrading, so no request can leave the
process. Every key is synthetic.
"""
import http.client
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.dirname(os.path.abspath(__file__))
for _p in (DESK, TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import launch  # noqa: E402
from alpaca import live as L  # noqa: E402
from alpaca import live_launch  # noqa: E402
from alpaca.mock import MockTrading  # noqa: E402
from alpaca.transport import StaticTestProvider  # noqa: E402
from test_alpaca_broker import SYNTH_SECRET, FakeOpener  # noqa: E402
from test_alpaca_live import LIVE_SYNTH_KEY, _lines, approve_live_dir  # noqa: E402


_REAL_CREATE_CONNECTION = socket.create_connection


class _Boom(AssertionError):
    pass


def _boom(*a, **k):
    raise _Boom("a key read or outbound connection was attempted")


def _free_live_capable_port():
    """An OS-chosen loopback port outside every paper and rehearsal range (stands in for 8795)."""
    for _ in range(50):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if not any(a <= port <= b for a, b, _ in L.non_live_port_ranges()):
            return port
    raise unittest.SkipTest("no free loopback port outside the paper ranges")


class FakeServer(object):
    def __init__(self, state_dir, host, port, manager):
        self.state_dir, self.host, self.port, self.manager = state_dir, host, port, manager
        self.served = self.shut = self.closed = False

    def serve_forever(self):
        self.served = True

    def shutdown(self):
        self.shut = True

    def server_close(self):
        self.closed = True


class FakeController(object):
    """Records the constructor kwargs; keeps live on/off state in the real alpaca_live.json."""
    built = []
    raise_type_error = False

    def __init__(self, **kw):
        if FakeController.raise_type_error:
            raise TypeError("unexpected keyword argument 'authorization'")
        FakeController.built.append(kw)
        self.kw = kw
        self.adapter_state = L.LiveAdapterState(kw["state_dir"])
        self.evidence_label = L.LABEL_ALPACA_LIVE
        self.closed = False

    def close(self):
        self.closed = True


class FakeAS(object):
    MODE_LIVE = "live"
    AlpacaSessionController = FakeController


class LiveWiringTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="live-wiring-")
        self.live_dir, self.limits = approve_live_dir(self.root)
        self.port = _free_live_capable_port()
        FakeController.built = []
        FakeController.raise_type_error = False
        self.servers, self.browsers, self.transports = [], [], []
        self.opener = FakeOpener(MockTrading())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def fake_transport(self, provider_kind, auth):
        t = L.LiveHttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"), auth)
        t._opener = self.opener          # TEST ONLY: the real live class, but no socket
        self.transports.append(t)
        return t

    def fake_server(self, state_dir, host, port, manager):
        srv = FakeServer(state_dir, host, port, manager)
        self.servers.append(srv)
        return srv

    def run_start(self, typed=None, AS=FakeAS, transport=None, extra=()):
        typed = typed if typed is not None else L.confirm_phrase(1, L.session_date())
        out, err = io.StringIO(), io.StringIO()
        argv = ["start", "--state-dir", self.live_dir, "--limits", self.limits, "--port", str(self.port)]
        with mock.patch.object(subprocess, "run", _boom), \
                mock.patch.object(socket, "create_connection", _boom), \
                mock.patch.object(live_launch, "_session_module", return_value=AS), \
                mock.patch.object(live_launch, "_make_transport", transport or self.fake_transport), \
                mock.patch.object(live_launch, "_make_server", self.fake_server), \
                mock.patch.object(live_launch, "_open_browser", self.browsers.append), \
                mock.patch.object(live_launch, "_wait_until_interrupted", side_effect=KeyboardInterrupt):
            code = live_launch.main(argv + list(extra), out=out, err=err, isatty=lambda: True,
                                    read_line=_lines(typed))
        return code, out.getvalue(), err.getvalue()

    def assert_nothing_sent(self):
        self.assertEqual(self.opener.requests, [])
        self.assertEqual(self.opener.trading.calls, [])

    def assert_lock_released(self):
        lock = launch.hold_scenario_lock(self.live_dir)
        self.assertIsNotNone(lock, "the live scenario lock was not released")
        lock.close()

    # -- the gate refused: nothing is built
    def test_gate_refused_builds_no_transport_controller_or_server(self):
        code, _, err = self.run_start(typed="LIVE SPY 1 SHARES")
        self.assertEqual(code, 2)
        self.assertIn("REFUSED (live)", err)
        self.assertEqual((FakeController.built, self.transports, self.servers), ([], [], []))
        self.assert_nothing_sent()

    # -- the gate passed: a live controller with the gate's authorization, served on the exact port
    def test_gate_passed_builds_the_live_controller_with_the_gate_authorization(self):
        code, out, err = self.run_start()
        self.assertEqual(code, 0, err)
        self.assertEqual(len(FakeController.built), 1)
        kw = FakeController.built[0]
        self.assertEqual(sorted(kw), ["live_authorization", "mode", "state_dir", "strategy", "transport"])
        self.assertEqual(kw["mode"], "live")
        self.assertEqual(kw["state_dir"], os.path.abspath(self.live_dir))
        auth = kw["live_authorization"]
        self.assertIsInstance(auth, L.LiveAuthorization)
        self.assertEqual(os.path.abspath(auth.state_dir), os.path.abspath(self.live_dir))
        self.assertEqual(auth.shares, 1)
        self.assertIs(kw["transport"], self.transports[0])
        self.assertIs(kw["transport"].authorization, auth)
        self.assertEqual(len(self.servers), 1)
        srv = self.servers[0]
        self.assertEqual((srv.host, srv.port), ("127.0.0.1", self.port))
        self.assertIsInstance(srv.manager, launch.AlpacaDeskControls)
        self.assertTrue(srv.served and srv.shut and srv.closed)
        self.assertTrue(FakeController.built and self.browsers == ["http://127.0.0.1:%d/" % self.port])
        self.assertIn("adapter   DISABLED", out)
        self.assertIn("sent      no order", out)
        self.assertIn(L.LABEL_ALPACA_LIVE, out)
        self.assert_nothing_sent()
        self.assert_lock_released()

    def test_no_browser_flag(self):
        code, _, err = self.run_start(extra=["--no-browser"])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.browsers, [])

    # -- the port is taken: exit 2, refused before any controller or server is built
    def test_a_taken_port_exits_2_and_nothing_is_built_or_moved(self):
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            holder.bind(("127.0.0.1", self.port))
            holder.listen(1)
            code, _, err = self.run_start()
        finally:
            holder.close()
        self.assertEqual(code, 2)
        self.assertIn("does not move to another port", err)
        self.assertEqual((FakeController.built, self.transports, self.servers), ([], [], []))
        self.assert_nothing_sent()
        self.assert_lock_released()

    # -- a paper (non-live) transport is never passed to the controller
    def test_a_paper_transport_is_refused_before_the_controller(self):
        class PaperLike(object):
            MODE = "paper"
        code, _, err = self.run_start(transport=lambda kind, auth: PaperLike())
        self.assertEqual(code, 2)
        self.assertIn("only the live transport", err)
        self.assertEqual((FakeController.built, self.servers), ([], []))
        self.assert_lock_released()

    def test_the_production_transport_factory_builds_only_the_live_transport(self):
        code, _, err = self.run_start()        # mint a real authorization through the gate
        self.assertEqual(code, 0, err)
        auth = FakeController.built[0]["live_authorization"]
        provider = StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live")
        with mock.patch.object(L, "make_live_provider", return_value=provider) as made, \
                mock.patch.object(subprocess, "run", _boom), mock.patch.object(socket, "create_connection", _boom):
            t = live_launch._make_transport("keychain", auth)
        made.assert_called_once_with("keychain")
        self.assertIs(type(t), L.LiveHttpsTransport)
        self.assertEqual(t.MODE, "live")

    # -- the adapter always starts disabled, even if the live file said enabled
    def test_a_previously_enabled_live_adapter_starts_disabled(self):
        L.LiveAdapterState(self.live_dir).enable(by="test")
        self.assertTrue(L.LiveAdapterState(self.live_dir).enabled)
        code, out, err = self.run_start()
        self.assertEqual(code, 0, err)
        self.assertIs(L.LiveAdapterState(self.live_dir).enabled, False)
        self.assertIn("adapter   DISABLED", out)
        self.assertFalse(os.path.exists(os.path.join(self.live_dir, "alpaca_paper.json")))
        self.assert_nothing_sent()

    # -- exit 3 stays the fallback
    def test_no_live_mode_in_the_session_module_keeps_exit_3(self):
        code, out, err = self.run_start(AS=None)
        self.assertEqual(code, 3, err)
        self.assertIn("LIVE GATE PASSED", out)
        self.assertEqual((FakeController.built, self.transports, self.servers), ([], [], []))

    def test_a_controller_start_up_failure_exits_2_names_the_stage_and_says_what_may_have_been_read(self):
        FakeController.raise_type_error = True           # stands in for any construction error
        code, out, err = self.run_start()
        self.assertEqual(code, 2, err)
        self.assertIn("session controller start-up failed: TypeError", err)
        self.assertIn("may have read the live key", err)
        self.assertNotIn("no key was read", err)
        self.assertNotIn("LIVE GATE PASSED", out)
        self.assertEqual(self.servers, [])
        self.assert_nothing_sent()
        self.assert_lock_released()

    def test_a_failure_before_the_controller_names_its_stage_and_nothing_was_read(self):
        def broken(kind, auth):
            raise RuntimeError("provider missing")
        code, _, err = self.run_start(transport=broken)
        self.assertEqual(code, 2)
        self.assertIn("live transport failed: RuntimeError: provider missing", err)
        self.assertIn("no key was read", err)
        self.assertEqual((FakeController.built, self.servers), ([], []))
        self.assert_lock_released()


    # -- a refusal after the controller exists says what may have been read, and closes it
    def test_a_server_bind_failure_after_the_controller_is_refused_truthfully(self):
        def no_server(*a):
            raise OSError(48, "Address already in use")
        self.fake_server = no_server                    # run_start installs this as _make_server
        code, _, err = self.run_start()
        self.assertEqual(code, 2)
        self.assertIn("does not move to another port", err)
        self.assertIn("No order was sent", err)
        self.assertNotIn("no key was read", err)
        self.assertTrue(FakeController.built)
        self.assert_lock_released()


class LiveContractTests(unittest.TestCase):
    """The names and state the controller's live mode (alpaca_session.py) relies on."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="live-contract-")
        self.live_dir = os.path.join(self.root, L.LIVE_STATE_DIRNAME)
        os.makedirs(self.live_dir)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_live_broker_is_found_as_alpaca_live_AlpacaLiveBroker(self):
        from alpaca.broker import AlpacaLiveBroker
        self.assertIs(L.AlpacaLiveBroker, AlpacaLiveBroker)
        with self.assertRaises(AttributeError):
            L.NoSuchThing  # noqa: B018

    def test_the_live_broker_judges_live_state_by_its_file_not_its_class(self):
        # alpaca_session.py keeps its own on/off class over alpaca_live.json; the real-controller start
        # below shows it is accepted. A paper file or another folder is still refused (test_alpaca_live).
        import inspect
        from alpaca import broker
        src = inspect.getsource(broker.AlpacaLiveBroker.__init__)
        self.assertIn("LiveAdapterState.FILE", src)
        self.assertIn("realpath", src)


class RealControllerStartTests(LiveWiringTests.__bases__[0]):
    """The real alpaca_session live mode, over the real LiveHttpsTransport with a FakeOpener."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="live-wiring-real-")
        self.live_dir, self.limits = approve_live_dir(self.root)
        self.port = _free_live_capable_port()
        self.opener = FakeOpener(MockTrading())
        self.servers, self.transports, self.runners = [], [], []

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def start_real(self, server=None, wait=None):
        AS = live_launch._session_module()
        if AS is None:
            self.skipTest("this build's alpaca_session has no live mode")
        real_cls = AS.AlpacaSessionController

        class Recording(real_cls):
            def __init__(inner, **kw):
                real_cls.__init__(inner, **kw)
                self.runners.append(inner)

        class AS2(object):
            MODE_LIVE = AS.MODE_LIVE
            AlpacaSessionController = Recording

        def transport(kind, auth):
            t = L.LiveHttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"), auth)
            t._opener = self.opener
            self.transports.append(t)
            return t

        def fake_server(state_dir, host, port, manager):
            srv = FakeServer(state_dir, host, port, manager)
            self.servers.append(srv)
            return srv

        out, err = io.StringIO(), io.StringIO()
        argv = ["start", "--state-dir", self.live_dir, "--limits", self.limits, "--port", str(self.port),
                "--no-browser"]
        with mock.patch.object(subprocess, "run", _boom), \
                mock.patch.object(socket, "create_connection", _boom), \
                mock.patch.object(live_launch, "_session_module", return_value=AS2), \
                mock.patch.object(live_launch, "_make_transport", transport), \
                mock.patch.object(live_launch, "_make_server", server or fake_server), \
                mock.patch.object(live_launch, "_wait_until_interrupted", side_effect=wait or KeyboardInterrupt):
            code = live_launch.main(argv, out=out, err=err, isatty=lambda: True,
                                    read_line=_lines(L.confirm_phrase(1, L.session_date())))
        return code, out.getvalue(), err.getvalue()

    def assert_start_sent_no_order(self):
        methods = [c[0] for c in self.opener.trading.calls]
        self.assertNotIn("POST", methods, "an order was sent at start")
        self.assertNotIn("DELETE", methods, "a cancel was sent at start")
        self.assertNotIn("PATCH", methods)
        for req in self.opener.requests:
            self.assertEqual(req.get_method(), "GET")
            self.assertIn("api.alpaca.markets", req.full_url)
            self.assertNotIn("paper-api", req.full_url)

    def test_real_live_controller_starts_disabled_and_sends_no_order(self):
        code, _, err = self.start_real()
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.runners), 1)
        self.assertIs(self.runners[0].adapter_state.enabled, False)
        self.assert_start_sent_no_order()
        self.assertFalse(os.path.exists(os.path.join(self.live_dir, "alpaca_paper.json")))
        print("\n[live wiring] real controller start: %d fake-opener request(s): %s"
              % (len(self.opener.requests), [r.get_method() + " " + r.full_url.split("?")[0]
                                              for r in self.opener.requests]), file=sys.stderr)


    def test_the_real_desk_server_reports_a_live_desk_with_the_adapter_disabled(self):
        """The real ui server on a free loopback port (no FakeServer). W-A owns its `simulated` value,
        so that field is not asserted here."""
        replies = {}

        def loopback_only(address, *a, **k):
            if address[0] != "127.0.0.1":
                raise _Boom("a non-loopback connection was attempted")
            return _REAL_CREATE_CONNECTION(address, *a, **k)

        def read_then_quit():
            with mock.patch.object(socket, "create_connection", loopback_only):
                for route in ("/api/health", "/api/session"):
                    conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
                    try:
                        conn.request("GET", route)
                        reply = conn.getresponse()
                        replies[route] = (reply.status, json.loads(reply.read()))
                    finally:
                        conn.close()
            raise KeyboardInterrupt

        code, out, err = self.start_real(server=live_launch._make_server, wait=read_then_quit)
        self.assertEqual(code, 0, err)
        status, health = replies["/api/health"]
        self.assertEqual(status, 200)
        self.assertEqual(health["broker_mode"], "alpaca-live")
        self.assertIs(health["controller_attached"], True)
        self.assertEqual(os.path.realpath(health["state_dir"]), os.path.realpath(self.live_dir))
        status, session = replies["/api/session"]
        self.assertEqual(status, 200)
        self.assertIs(session["_controller_attached"], True)
        self.assertIs(session["adapter"]["enabled"], False)
        self.assertIs(L.LiveAdapterState(self.live_dir).enabled, False)
        self.assertIn("adapter   DISABLED", out)
        self.assert_start_sent_no_order()



class _AccountOpener(FakeOpener):
    """FakeOpener that also serves GET /v2/account and /v2/assets/SPY with live-shaped status fields."""

    def __init__(self, trading, suspended=False):
        FakeOpener.__init__(self, trading)
        self.account = {"status": "ACTIVE", "trading_blocked": False, "account_blocked": False,
                        "trade_suspended_by_user": suspended}

    def open(self, req, timeout=None):
        import urllib.parse
        from test_alpaca_broker import FakeResp
        path = urllib.parse.urlsplit(req.full_url).path
        if req.get_method() == "GET" and path == "/v2/account":
            self.requests.append(req)
            self.trading.calls.append(("GET", path, {}, None))
            return FakeResp(200, dict(self.account), req.full_url)
        if req.get_method() == "GET" and path == "/v2/assets/SPY":
            self.requests.append(req)
            self.trading.calls.append(("GET", path, {}, None))
            return FakeResp(200, {"symbol": "SPY", "tradable": True, "status": "active"}, req.full_url)
        return FakeOpener.open(self, req, timeout)


class LiveArmConnectionCheckTests(RealControllerStartTests):
    """Enable on a live desk runs the GET-only connection check that live Arm needs; Reconcile refreshes
    it. A failing account keeps the check failed and Arm refused. No order is sent either way."""

    test_real_live_controller_starts_disabled_and_sends_no_order = None          # run once, in the base
    test_the_real_desk_server_reports_a_live_desk_with_the_adapter_disabled = None

    def drive(self, suspended):
        self.opener = _AccountOpener(MockTrading(), suspended=suspended)
        seen = {}

        def operator():
            runner = self.runners[-1]
            controls = launch.AlpacaDeskControls(runner)
            seen["enable"] = controls.alpaca_enable(confirm=True)
            seen["preflight"] = {c["check"]: c for c in runner.preflight()}
            seen["arm"] = runner.arm()
            seen["reconcile"] = controls.reconcile_now()
            seen["enabled_after"] = runner.adapter_state.enabled
            raise KeyboardInterrupt

        code, out, err = self.start_real(wait=operator)
        self.assertEqual(code, 0, err)
        return seen

    def test_enable_runs_the_connection_check_so_it_no_longer_blocks_arm(self):
        seen = self.drive(suspended=False)
        cc = seen["enable"]["connection_check"]
        self.assertTrue(seen["enable"]["ok"])
        self.assertTrue(cc["ok"], cc)
        self.assertEqual((cc["method"], cc["orders_sent"]), ("GET only", 0))
        self.assertTrue(seen["preflight"]["live connection check"]["ok"], seen["preflight"]["live connection check"])
        failed = [f["check"] for f in seen["arm"].get("failed", [])]
        self.assertNotIn("live connection check", failed)
        # Arm may still refuse on the calendar or venue clock (it is not a session day here); the full
        # Enable -> Preflight -> Arm path on a session-day clock is Codex's probe_live_command.py.
        self.assertTrue(seen["reconcile"]["ok"])
        self.assertTrue(seen["reconcile"]["connection_check"]["ok"])
        self.assertTrue(seen["enabled_after"])
        self.assert_start_sent_no_order()

    def test_a_suspended_account_keeps_the_check_failed_and_arm_refused(self):
        seen = self.drive(suspended=True)
        cc = seen["enable"]["connection_check"]
        self.assertTrue(seen["enable"]["ok"])                 # Enable is not undone by a failed check
        self.assertFalse(cc["ok"])
        self.assertIn("trade_suspended_by_user", json.dumps(cc))
        self.assertFalse(seen["preflight"]["live connection check"]["ok"])
        self.assertFalse(seen["arm"]["ok"])
        self.assertIn("live connection check", [f["check"] for f in seen["arm"]["failed"]])
        self.assertFalse(seen["reconcile"]["connection_check"]["ok"])
        self.assertTrue(seen["enabled_after"])
        self.assert_start_sent_no_order()

    def test_paper_and_mock_controls_do_not_run_a_connection_check(self):
        class Runner(object):
            live = False
            calls = []

            def alpaca_enable(self, confirm=False):
                return {"ok": True, "simulated": True}

            def reconcile_now(self):
                return {"ok": True, "result": {}}

            def connection_check(self):
                self.calls.append("cc")
                raise AssertionError("no connection check outside live mode")

        r = Runner()
        c = launch.AlpacaDeskControls(r)
        self.assertNotIn("connection_check", c.alpaca_enable(confirm=True))
        self.assertNotIn("connection_check", c.reconcile_now())
        self.assertEqual(r.calls, [])


if __name__ == "__main__":
    unittest.main()
