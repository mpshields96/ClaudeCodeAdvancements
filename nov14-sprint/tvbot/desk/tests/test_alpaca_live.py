"""LIVE path, offline only. Every request here goes to an in-process FakeOpener or nowhere; no socket
opens, no key is read, nothing reaches Alpaca.

1. Separation: paper keys cannot reach the live host, live keys cannot reach the paper host, the paper
   launcher has no live choice, and the paper broker refuses a live transport.
2. The per-session live gate (alpaca/live.py, alpaca/live_launch.py): every missing or wrong input is
   refused before any socket or key read, including a real subprocess run of the live command.
3. Sessions (alpaca/sessions.py): only regular hours are supported; overnight is never traded silently.
4. The 23:11Z finding at on_bar level: the manager uses its configured freshness window.
5. The desk's protections re-run over LiveHttpsTransport (a test-only rehearsal broker subclass).
All limits below are TEST VALUES in temp dirs, not Matthew's limits.
"""
import datetime as _dt
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.dirname(os.path.abspath(__file__))
for _p in (DESK, TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpaca  # noqa: E402
from alpaca import LABEL_INJECTED, LABEL_MOCK_LOCAL  # noqa: E402
from alpaca import live as L  # noqa: E402
from alpaca import live_launch, sessions, sizing  # noqa: E402
from alpaca import setup as SETUP  # noqa: E402
from alpaca.broker import AlpacaLiveBroker, AlpacaPaperBroker  # noqa: E402
from alpaca.mock import MockAlpacaTransport, MockTrading  # noqa: E402
from alpaca.setup import CredentialsError  # noqa: E402
from alpaca.state import AdapterState  # noqa: E402
from alpaca.transport import HttpsTransport, StaticTestProvider, TransportRefused  # noqa: E402
from orders.calendar import SessionCalendar, iso, parse_ts  # noqa: E402
from orders.intake import DEFAULT_MAX_AGE_S, check_bar  # noqa: E402
from orders.manager import OrderManager  # noqa: E402
from test_alpaca_broker import BARS, LIMITS, SYNTH_KEY, SYNTH_SECRET, Case, FakeOpener, posts  # noqa: E402

LIVE_SYNTH_KEY = "AKSYNTH-TEST-0001"       # synthetic; shaped like a live key id, not a real key
PAPER_SYNTH_KEY = "PKSYNTH-TEST-0001"      # synthetic; shaped like a paper key id, not a real key
TEST_LIVE_VALUES = {"fixed_shares": 1, "max_loss_per_trade": 10.0, "daily_loss": 30.0,   # TEST VALUES
                    "per_trade_notional": 2000, "gross_exposure": 2000}
NOW = _dt.datetime(2026, 11, 16, 15, 0, tzinfo=_dt.timezone.utc)       # a fixed clock for phrases


class _Boom(Exception):
    pass


class NoNetworkNoKeys(object):
    """While active, opening any socket or running any subprocess (the Keychain reader) fails the test."""

    def __enter__(self):
        self._sock, self._conn, self._run = socket.socket, socket.create_connection, subprocess.run

        def boom(*a, **k):
            raise _Boom("network or key read attempted")
        socket.socket = boom
        socket.create_connection = boom
        subprocess.run = boom
        return self

    def __exit__(self, *exc):
        socket.socket, socket.create_connection, subprocess.run = self._sock, self._conn, self._run
        return False


def _lines(*items):
    it = iter(items)
    return lambda: next(it)


def approve_live_dir(root, values=None):
    """Approve TEST VALUE live limits in root/state-alpaca-live through the real approve-limits command."""
    live_dir = os.path.join(root, L.LIVE_STATE_DIRNAME)
    draft = os.path.join(root, "draft.json")
    with open(draft, "w") as fh:
        json.dump(values or TEST_LIVE_VALUES, fh)
    out, err = io.StringIO(), io.StringIO()
    code = live_launch.main(["approve-limits", "--state-dir", live_dir, "--draft-from", draft], out=out, err=err,
                            isatty=lambda: True, read_line=_lines(L.LIVE_CONFIRM_LIMITS, "offline test"))
    if code != 0:
        raise AssertionError("approve-limits failed: %s" % err.getvalue())
    return live_dir, sizing.approved_path(live_dir)


def shown_hash(limits_path):
    """The full approval-record hash of the limits an operator would be shown before typing."""
    return sizing.load_limits(path=limits_path, allow_draft=False)["hash"]


SWAPPED_LIVE_VALUES = dict(TEST_LIVE_VALUES, max_loss_per_trade=100.0, daily_loss=300.0)   # TEST VALUES


def mint_auth(root, monotonic=None):
    live_dir, limits = approve_live_dir(root)
    phrase = L.confirm_phrase(1, L.session_date(NOW))
    return L.live_gate_authorize(limits, live_dir, L.LIVE_PORT, phrase, True, now_utc=NOW, monotonic=monotonic,
                                 shown_hash=shown_hash(limits))


class _LiveRehearsalBroker(AlpacaPaperBroker):
    """TEST ONLY: lets the paper broker's order logic run over LiveHttpsTransport and a FakeOpener, so the
    protections are exercised on the live request path. Production code never sets this flag."""
    _ALLOW_LIVE_TRANSPORT = True


# ---------------------------------------------------------------- 1. separation

class SeparationTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="alpaca-live-sep-")
        self.auth = mint_auth(self.root)
        self.trading = MockTrading()
        self.opener = FakeOpener(self.trading)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def live_transport(self, key=LIVE_SYNTH_KEY, **kw):
        return L.LiveHttpsTransport(StaticTestProvider(key, SYNTH_SECRET, mode="live"), self.auth,
                                    opener=self.opener, **kw)

    def test_paper_transport_refuses_live_mode_providers(self):
        for prov in (StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"),
                     L.LiveEnvProvider(environ={}), L.LiveKeychainProvider(runner=lambda a: (1, ""))):
            with self.assertRaises(TransportRefused):
                HttpsTransport(prov, opener=self.opener)
        self.assertEqual(self.opener.requests, [])

    def test_live_transport_refuses_paper_mode_providers(self):
        for prov in (StaticTestProvider(SYNTH_KEY, SYNTH_SECRET), SETUP.EnvProvider(environ={}),
                     SETUP.KeychainProvider()):
            with self.assertRaises(TransportRefused):
                L.LiveHttpsTransport(prov, self.auth, opener=self.opener)
        self.assertEqual(self.opener.requests, [])

    def test_paper_key_on_live_transport_never_opens(self):
        t = self.live_transport(key=PAPER_SYNTH_KEY)
        with self.assertRaises(TransportRefused):
            t.request("GET", "trading", "/v2/account")
        self.assertEqual(self.opener.requests, [])

    def test_live_key_on_paper_transport_never_opens(self):
        t = HttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET), opener=self.opener)
        with self.assertRaises(TransportRefused):
            t.request("GET", "trading", "/v2/account")
        self.assertEqual(self.opener.requests, [])

    def test_live_requests_go_only_to_the_live_host(self):
        t = self.live_transport()
        t.request("GET", "trading", "/v2/account")
        req = self.opener.requests[-1]
        self.assertTrue(req.full_url.startswith("https://api.alpaca.markets/v2/account"), req.full_url)
        self.assertEqual(req.get_header("User-agent"), "paper-desk-alpaca-live/1")
        self.assertEqual(req.get_header("Apca-api-key-id"), LIVE_SYNTH_KEY)

    def test_paper_requests_go_only_to_the_paper_host(self):
        t = HttpsTransport(StaticTestProvider(SYNTH_KEY, SYNTH_SECRET), opener=self.opener)
        t.request("GET", "trading", "/v2/account")
        self.assertTrue(self.opener.requests[-1].full_url.startswith("https://paper-api.alpaca.markets/"))

    def test_live_origins_edited_to_paper_host_refused(self):
        saved = dict(L.LIVE_ORIGINS)
        try:
            L.LIVE_ORIGINS["trading"] = "https://paper-api.alpaca.markets"
            with self.assertRaises(TransportRefused):
                self.live_transport().request("GET", "trading", "/v2/account")
            L.LIVE_ORIGINS["trading"] = "https://api.alpaca.markets.evil.example"
            with self.assertRaises(TransportRefused):
                self.live_transport().request("GET", "trading", "/v2/account")
        finally:
            L.LIVE_ORIGINS.clear()
            L.LIVE_ORIGINS.update(saved)
        self.assertEqual(self.opener.requests, [])

    def test_paper_origins_edited_to_live_host_refused(self):
        saved = dict(alpaca.ORIGINS)
        try:
            alpaca.ORIGINS["trading"] = L.LIVE_TRADING_ORIGIN
            t = HttpsTransport(StaticTestProvider(SYNTH_KEY, SYNTH_SECRET), opener=self.opener)
            with self.assertRaises(TransportRefused):
                t.request("GET", "trading", "/v2/account")
        finally:
            alpaca.ORIGINS.clear()
            alpaca.ORIGINS.update(saved)
        self.assertEqual(self.opener.requests, [])

    def test_live_transport_needs_a_gate_authorization(self):
        prov = StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live")
        with self.assertRaises(TransportRefused):
            L.LiveHttpsTransport(prov, None, opener=self.opener)
        with self.assertRaises(TransportRefused):
            L.LiveAuthorization(object(), "2026-11-16", 1, "h", self.root, 0.0)

    def test_expired_authorization_refuses_before_send(self):
        clock = [1000.0]
        auth = L.live_gate_authorize(sizing.approved_path(os.path.join(self.root, L.LIVE_STATE_DIRNAME)),
                                     os.path.join(self.root, L.LIVE_STATE_DIRNAME), L.LIVE_PORT,
                                     L.confirm_phrase(1, L.session_date(NOW)), True, now_utc=NOW,
                                     monotonic=lambda: clock[0], shown_hash=shown_hash(
                                         sizing.approved_path(os.path.join(self.root, L.LIVE_STATE_DIRNAME))))
        t = L.LiveHttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"), auth,
                                 opener=self.opener, monotonic=lambda: clock[0])
        t.request("GET", "trading", "/v2/account")
        self.assertEqual(len(self.opener.requests), 1)
        clock[0] += L.AUTH_MAX_AGE_S + 1
        with self.assertRaises(TransportRefused):
            t.request("GET", "trading", "/v2/account")
        self.assertEqual(len(self.opener.requests), 1)

    def test_paper_providers_refuse_live_names(self):
        with self.assertRaises(CredentialsError):
            SETUP.KeychainProvider(service=SETUP.LIVE_KEYCHAIN_SERVICE)
        with self.assertRaises(CredentialsError):
            SETUP.EnvProvider(environ={}, key_var=SETUP.LIVE_ENV_KEY_VAR)
        with self.assertRaises(CredentialsError):
            SETUP.EnvProvider(environ={}, secret_var=SETUP.LIVE_ENV_SECRET_VAR)

    def test_live_providers_read_only_live_names_and_refuse_paper_keys(self):
        env = {SETUP.ENV_KEY_VAR: LIVE_SYNTH_KEY, SETUP.ENV_SECRET_VAR: SYNTH_SECRET}
        with self.assertRaises(CredentialsError):                  # the paper variable names are not read
            L.LiveEnvProvider(environ=env).get()
        env = {L.LIVE_ENV_KEY_VAR: PAPER_SYNTH_KEY, L.LIVE_ENV_SECRET_VAR: SYNTH_SECRET}
        with self.assertRaises(CredentialsError):
            L.LiveEnvProvider(environ=env).get()
        seen = []

        def runner(argv):
            seen.append(argv)
            return 0, PAPER_SYNTH_KEY + "\n"
        with self.assertRaises(CredentialsError):
            L.LiveKeychainProvider(runner=runner).get()
        self.assertIn(L.LIVE_KEYCHAIN_SERVICE, seen[0])
        self.assertNotIn(SETUP.KEYCHAIN_SERVICE, seen[0])

    def test_paper_launcher_has_no_live_choice(self):
        with open(os.path.join(DESK, "launch.py")) as fh:
            src = fh.read()
        self.assertIn('choices=("offline", "alpaca-paper")', src)
        self.assertNotIn("api.alpaca.markets\"", src.replace("paper-api.alpaca.markets", ""))
        self.assertNotIn("live_launch", src)
        self.assertNotIn("LiveHttpsTransport", src)

    def test_paper_broker_refuses_a_live_transport(self):
        bdir = os.path.join(self.root, "b")
        os.makedirs(bdir)
        with self.assertRaises(ValueError):
            AlpacaPaperBroker(self.live_transport(), bdir, LABEL_INJECTED, AdapterState(bdir))
        self.assertEqual(self.opener.requests, [])


# ---------------------------------------------------------------- 2. the live gate

class LiveGateTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="alpaca-live-gate-")
        self.live_dir, self.limits = approve_live_dir(self.root)
        self.phrase = L.confirm_phrase(1, L.session_date(NOW))
        self.shown = shown_hash(self.limits)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def gate(self, **kw):
        args = dict(limits_path=self.limits, state_dir=self.live_dir, port=L.LIVE_PORT, typed=self.phrase,
                    stdin_is_tty=True, now_utc=NOW, shown_hash=self.shown)
        args.update(kw)
        with NoNetworkNoKeys():
            return L.live_gate_authorize(**args)

    def test_correct_inputs_mint_an_authorization(self):
        auth = self.gate()
        self.assertIsInstance(auth, L.LiveAuthorization)
        self.assertEqual((auth.shares, auth.session_date), (1, "2026-11-16"))

    def test_each_missing_or_wrong_input_refuses(self):
        paper_dir = os.path.join(self.root, "state-alpaca-paper")
        os.makedirs(paper_dir)
        cases = {
            "no limits": dict(limits_path=None),
            "paper state dir": dict(state_dir=paper_dir),
            "plain state dir": dict(state_dir=os.path.join(self.root, "state")),
            "paper port": dict(port=L.PAPER_PORT),
            "piped input": dict(stdin_is_tty=False),
            "wrong phrase": dict(typed="yes"),
            "empty phrase": dict(typed=""),
            "yesterday's phrase": dict(typed=L.confirm_phrase(1, "2026-11-15")),
            "wrong share count": dict(typed=L.confirm_phrase(2, "2026-11-16")),
        }
        for name, kw in cases.items():
            with self.subTest(name):
                with self.assertRaises(L.LiveGateRefused):
                    self.gate(**kw)

    def test_limits_outside_the_live_dir_refused(self):
        other = os.path.join(self.root, "elsewhere.json")
        shutil.copy(self.limits, other)
        with self.assertRaises(L.LiveGateRefused):
            self.gate(limits_path=other)

    def test_paper_approved_limits_refused(self):
        pdir = os.path.join(self.root, "p", L.LIVE_STATE_DIRNAME)
        os.makedirs(pdir)
        sizing.save_draft(pdir, TEST_LIVE_VALUES)
        d = sizing.read_draft(pdir)
        sizing.approve(pdir, sizing.CONFIRM_PHRASE, "paper approval", reviewed_draft_hash=sizing.content_hash(
            d["values"]), prior_approved_hash=None)
        with self.assertRaises(L.LiveGateRefused):
            self.gate(limits_path=sizing.approved_path(pdir), state_dir=pdir)

    def test_dir_holding_paper_adapter_state_refused(self):
        with open(os.path.join(self.live_dir, "alpaca_paper.json"), "w") as fh:
            fh.write("{}")
        with self.assertRaises(L.LiveGateRefused):
            self.gate()

    def test_edited_limits_refused(self):
        with open(self.limits) as fh:
            obj = json.load(fh)
        obj["values"]["fixed_shares"] = 5
        with open(self.limits, "w") as fh:
            json.dump(obj, fh)
        with self.assertRaises(L.LiveGateRefused):
            self.gate(typed=L.confirm_phrase(5, "2026-11-16"))

    def run_main(self, argv, typed=None, tty=True):
        out, err = io.StringIO(), io.StringIO()
        with NoNetworkNoKeys():
            code = live_launch.main(argv, out=out, err=err, isatty=lambda: tty,
                                    read_line=_lines(*(typed or [""])))
        return code, out.getvalue(), err.getvalue()

    def test_start_without_limits_exits_2_before_anything(self):
        code, out, err = self.run_main(["start", "--state-dir", self.live_dir])
        self.assertEqual(code, 2)
        self.assertIn("REFUSED (live)", err)
        self.assertIn("no connection was opened", err)
        self.assertEqual(out, "")

    def test_no_subcommand_exits_2(self):
        self.assertEqual(self.run_main([])[0], 2)

    def test_start_piped_input_exits_2(self):
        code, _, err = self.run_main(["start", "--state-dir", self.live_dir, "--limits", self.limits], tty=False)
        self.assertEqual(code, 2)
        self.assertIn("terminal", err)

    def test_start_wrong_phrase_exits_2(self):
        code, _, err = self.run_main(["start", "--state-dir", self.live_dir, "--limits", self.limits],
                                     typed=["LIVE SPY 1 SHARES"])
        self.assertEqual(code, 2)

    def test_start_correct_phrase_stops_at_not_wired(self):
        typed = L.confirm_phrase(1, L.session_date())
        code, out, err = self.run_main(["start", "--state-dir", self.live_dir, "--limits", self.limits],
                                       typed=[typed])
        self.assertEqual(code, 3, err)
        self.assertIn("LIVE GATE PASSED", out)
        self.assertIn("Nothing was sent", out)
        self.assertIn(L.LABEL_ALPACA_LIVE, out)

    # The 02:40Z binding finding: limits swapped while the confirmation prompt is open.
    def test_missing_shown_hash_refused(self):
        with self.assertRaises(L.LiveGateRefused):
            self.gate(shown_hash=None)

    def test_limits_reapproved_after_they_were_shown_are_refused(self):
        approve_live_dir(self.root, SWAPPED_LIVE_VALUES)       # same share count, larger loss limits
        with self.assertRaises(L.LiveGateRefused) as cm:
            self.gate()
        self.assertIn("changed while you were confirming", str(cm.exception))

    def test_authorization_carries_the_shown_snapshot_not_a_later_file(self):
        auth = self.gate()
        self.assertEqual(auth.limits["hash"], self.shown)
        self.assertEqual(auth.limits_hash, self.shown)
        self.assertEqual(float(auth.limits["values"]["max_loss_per_trade"]), 10.0)
        approve_live_dir(self.root, SWAPPED_LIVE_VALUES)
        self.assertEqual(float(auth.limits["values"]["max_loss_per_trade"]), 10.0)
        self.assertEqual(float(auth.limits["values"]["daily_loss"]), 30.0)

    def test_start_refuses_limits_swapped_during_the_prompt(self):
        typed = L.confirm_phrase(1, L.session_date())
        root = self.root

        def swap_then_type():
            approve_live_dir(root, SWAPPED_LIVE_VALUES)
            return typed

        out, err = io.StringIO(), io.StringIO()
        with NoNetworkNoKeys():
            code = live_launch.main(["start", "--state-dir", self.live_dir, "--limits", self.limits],
                                    out=out, err=err, isatty=lambda: True, read_line=swap_then_type)
        self.assertEqual(code, 2, out.getvalue())
        self.assertIn("changed while you were confirming", err.getvalue())
        self.assertNotIn("LIVE GATE PASSED", out.getvalue())
        self.assertIn("'max_loss_per_trade': 10", out.getvalue())     # what was shown: the original

    def test_start_on_paper_port_exits_2(self):
        code, _, _ = self.run_main(["start", "--state-dir", self.live_dir, "--limits", self.limits,
                                    "--port", str(L.PAPER_PORT)])
        self.assertEqual(code, 2)

    # Codex finding on 198dda2: only 8765 was refused; the installed desks' ports, port 0 and 65536 passed.
    def test_installed_desk_ports_zero_and_out_of_range_are_refused(self):
        for port in (18855, 18858, 0, 65536, -1, 70000, L.PAPER_PORT):
            with self.subTest(port=port):
                with self.assertRaises(L.LiveGateRefused):
                    L.check_live_port(port)
                code, out, err = self.run_main(["start", "--state-dir", self.live_dir, "--limits", self.limits,
                                                "--port", str(port)], typed=[L.confirm_phrase(1, L.session_date())])
                self.assertEqual(code, 2, out)
                self.assertIn("REFUSED (live)", err)
                self.assertIn("Nothing was sent", err)
                self.assertNotIn("LIVE GATE PASSED", out)
                self.assertEqual(out, "")                       # refused before the limits or prompt are shown

    def test_every_paper_and_rehearsal_fallback_port_is_refused(self):
        import launch
        tries = launch.free_port.__defaults__[0]
        self.assertEqual(tries, L.FREE_PORT_TRIES)              # live's ranges track launch.free_port
        for preferred in (launch.DEFAULT_PORT, 18855, 18858):
            for port in range(preferred, preferred + tries):
                with self.subTest(port=port):
                    with self.assertRaises(L.LiveGateRefused):
                        L.check_live_port(port)
                    with self.assertRaises(L.LiveGateRefused):
                        self.gate(port=port)
        self.assertEqual(L.check_live_port(launch.DEFAULT_PORT + tries), launch.DEFAULT_PORT + tries)

    def test_only_whole_number_ports(self):
        for bad in (True, False, "8795", 8795.0, None):
            with self.subTest(bad=bad):
                with self.assertRaises(L.LiveGateRefused):
                    L.check_live_port(bad)

    def test_live_port_passes_and_the_normal_live_entry_still_runs_offline(self):
        self.assertEqual(L.check_live_port(L.LIVE_PORT), L.LIVE_PORT)
        for first, last, _ in L.non_live_port_ranges():
            self.assertFalse(first <= L.LIVE_PORT <= last)
        code, out, err = self.run_main(["start", "--state-dir", self.live_dir, "--limits", self.limits,
                                        "--port", str(L.LIVE_PORT)], typed=[L.confirm_phrase(1, L.session_date())])
        self.assertEqual(code, 3, err)
        self.assertIn(L.LABEL_ALPACA_LIVE, out)
        self.assertIn("LIVE GATE PASSED", out)

    def test_a_taken_live_port_is_refused_never_moved(self):
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            holder.bind(("127.0.0.1", 0))                      # an OS-chosen loopback port stands in for 8795
            taken = holder.getsockname()[1]
            if any(a <= taken <= b for a, b, _ in L.non_live_port_ranges()):
                self.skipTest("OS picked a paper-range port")
            orig = L.check_live_port
            L.check_live_port = lambda p: p                      # only the bind step is under test here
            try:
                with self.assertRaises(L.LiveGateRefused) as ctx:
                    L.bind_live_port_exactly(taken)
            finally:
                L.check_live_port = orig
            self.assertIn("does not move to another port", str(ctx.exception))
            with self.assertRaises(L.LiveGateRefused):
                L.bind_live_port_exactly(18858)                  # checked before any socket is made
        finally:
            holder.close()

    def test_approve_limits_refusals(self):
        draft = os.path.join(self.root, "draft.json")
        self.assertEqual(self.run_main(["approve-limits", "--state-dir", os.path.join(self.root, "state"),
                                        "--draft-from", draft], typed=[L.LIVE_CONFIRM_LIMITS, "r"])[0], 2)
        self.assertEqual(self.run_main(["approve-limits", "--state-dir", self.live_dir, "--draft-from", draft],
                                       typed=[L.LIVE_CONFIRM_LIMITS, "r"], tty=False)[0], 2)
        self.assertEqual(self.run_main(["approve-limits", "--state-dir", self.live_dir, "--draft-from", draft],
                                       typed=[sizing.CONFIRM_PHRASE, "r"])[0], 2)

    def test_approved_snapshot_is_operator_approved_by_the_live_command(self):
        with open(self.limits) as fh:
            obj = json.load(fh)
        self.assertEqual(obj["by"], L.LIVE_APPROVER)
        self.assertEqual(obj["provenance"], sizing.PROV_APPROVED)
        self.assertEqual(obj["values"], TEST_LIVE_VALUES)

    def test_real_process_without_limits_exits_2(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("APCA_", "ALPACA_"))}
        p = subprocess.run([sys.executable, "-I", os.path.join(DESK, "alpaca", "live_launch.py"), "start",
                            "--state-dir", self.live_dir], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=30, env=env, cwd=self.root)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("--limits is required", p.stderr)
        self.assertIn("Nothing was sent", p.stderr)


# ---------------------------------------------------------------- 3. sessions

class SessionWindowTests(unittest.TestCase):
    cal = SessionCalendar.nyse_2026_2027()

    def at(self, s):
        return parse_ts(s)

    def test_classification(self):
        cases = [
            ("2026-11-16T15:00:00Z", sessions.REGULAR),       # Mon 10:00 ET
            ("2026-11-16T10:00:00Z", sessions.PRE_MARKET),    # Mon 05:00 ET
            ("2026-11-16T22:00:00Z", sessions.AFTER_HOURS),   # Mon 17:00 ET
            ("2026-11-16T02:00:00Z", sessions.OVERNIGHT),     # Sun 21:00 ET
            ("2026-11-17T03:00:00Z", sessions.OVERNIGHT),     # Mon 22:00 ET
            ("2026-11-17T08:30:00Z", sessions.OVERNIGHT),     # Tue 03:30 ET
            ("2026-11-14T15:00:00Z", sessions.CLOSED),        # Saturday
            ("2026-11-21T02:00:00Z", sessions.CLOSED),        # Fri 21:00 ET: no Friday-night session
            ("2026-11-26T15:00:00Z", sessions.CLOSED),        # Thanksgiving, NYSE closed
            ("2026-11-27T19:00:00Z", sessions.AFTER_HOURS),   # Fri after the 13:00 ET early close
        ]
        for ts, want in cases:
            with self.subTest(ts):
                row = sessions.classify(self.at(ts), self.cal)
                self.assertEqual(row["session"], want, row)
                self.assertEqual(row["desk_supported"], want == sessions.REGULAR)

    def test_overnight_is_labeled_not_supported(self):
        row = sessions.status_field(self.at("2026-11-16T02:00:00Z"), self.cal)
        self.assertFalse(row["desk_supported"])
        self.assertIn("NOT supported", row["label"])
        self.assertIn("never traded silently", row["label"])
        self.assertEqual(row["at_utc"], "2026-11-16T02:00:00Z")

    def test_uncovered_date_fails_closed(self):
        row = sessions.classify(self.at("2031-06-02T15:00:00Z"), self.cal)
        self.assertFalse(row["desk_supported"])

    def test_naive_time_refused(self):
        with self.assertRaises(ValueError):
            sessions.classify(_dt.datetime(2026, 11, 16, 15, 0), self.cal)

    def bar(self, ts_open):
        o = parse_ts(ts_open)
        c = o + _dt.timedelta(minutes=1)
        return {"symbol": "SPY", "ts_open": iso(o), "ts_close": iso(c), "open": 100.0, "high": 100.1,
                "low": 99.9, "close": 100.0, "volume": 10, "delivered_ts": iso(c + _dt.timedelta(seconds=2))}

    def test_bars_outside_regular_hours_are_refused_at_intake(self):
        ok, _, _ = check_bar(self.bar("2026-11-16T15:00:00Z"), None, self.cal)
        self.assertTrue(ok)
        for ts in ("2026-11-16T10:00:00Z", "2026-11-16T22:00:00Z", "2026-11-16T02:00:00Z"):
            with self.subTest(ts):
                ok, code, d = check_bar(self.bar(ts), None, self.cal)
                self.assertFalse(ok)
                self.assertIn("OUT_OF_SESSION", d.get("codes") or [code])

    def test_order_payload_never_asks_for_extended_hours(self):
        tmp = tempfile.mkdtemp(prefix="alpaca-live-ext-")
        try:
            trading = MockTrading()
            AdapterState(tmp).enable(by="test")
            b = AlpacaPaperBroker(MockAlpacaTransport(trading), tmp, LABEL_MOCK_LOCAL, AdapterState(tmp))
            b.submit("x1", "buy", 1, limit=101.0)
            body = posts(trading)[-1][3]
            self.assertNotIn("extended_hours", body)
            self.assertEqual(body["time_in_force"], "day")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- 4. on_bar freshness window

def aged(bar, age_s):
    b = dict(bar)
    b.pop("exchange_ts", None)
    b["delivered_ts"] = iso(parse_ts(b["ts_close"]) + _dt.timedelta(seconds=age_s))
    return b


class OnBarFreshnessTests(Case):
    """The 23:11Z finding at on_bar level: OrderManager.on_bar applies its own bar_max_age_s."""

    def manager(self, max_age):
        m = OrderManager(self.dir, self.b, LIMITS, calendar=self.cal, bar_max_age_s=max_age)
        self.mgrs.append(m)
        return m

    def test_window_900_accepts_a_61s_bar_default_5_refuses_it(self):
        m = self.manager(900)
        m.on_bar(aged(BARS[0], 61))
        self.assertIsNone(m._bar_status)
        m.close()
        self.mgrs.remove(m)
        shutil.rmtree(self.dir)
        os.makedirs(self.dir)
        AdapterState(self.dir).enable(by="test")
        self.new_broker()
        m5 = self.manager(DEFAULT_MAX_AGE_S)
        m5.on_bar(aged(BARS[0], 61))
        self.assertEqual(m5._bar_status, "STALE_EXCHANGE_TS")

    def test_window_900_refuses_a_901s_bar_and_blocks_entries(self):
        m = self.manager(900)
        m.on_bar(aged(BARS[0], 2))
        self.assertIsNone(m._bar_status)
        self.assertTrue(m.arm("S1", expires_utc="2026-06-30T00:00:00Z")["ok"])
        m.on_bar(aged(BARS[1], 901))
        self.assertEqual(m._bar_status, "STALE_EXCHANGE_TS")
        n = len(posts(self.trading))
        iid = m.submit_intent({"decision_id": "late", "side": "buy", "qty": 1, "ref_price": m.mark,
                               "limit": round(m.mark + 5, 2), "invalidation": m.mark - 0.5})
        self.assertEqual(m.intents[iid]["status"], "rejected")
        self.assertEqual(m.intents[iid].get("reason"), "BAR_STALE_EXCHANGE_TS")
        self.assertEqual(len(posts(self.trading)), n)


# ---------------------------------------------------------------- 5. protections over the live transport

class LiveRehearsalTests(Case):
    """The paper broker's order logic over LiveHttpsTransport and a FakeOpener (no socket)."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="alpaca-live-rehearsal-")
        self.auth = mint_auth(self.root)
        self.dir = os.path.join(self.root, "broker")
        os.makedirs(self.dir)
        self.cal = SessionCalendar.fixture_profile()
        self.trading = MockTrading()
        self.opener = FakeOpener(self.trading)
        self.transport = L.LiveHttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"),
                                              self.auth, opener=self.opener)
        AdapterState(self.dir).enable(by="test")
        self.mgrs = []
        self.b = self.new_broker()
        self.i = 0

    def tearDown(self):
        Case.tearDown(self)
        shutil.rmtree(self.root, ignore_errors=True)

    def new_broker(self):
        self.b = _LiveRehearsalBroker(self.transport, self.dir, LABEL_INJECTED, AdapterState(self.dir))
        return self.b

    def assert_live_host_only(self):
        hosts = {r.full_url.split("/")[2] for r in self.opener.requests}
        self.assertEqual(hosts, {"api.alpaca.markets"})

    def test_one_post_per_intent_and_duplicate_decision_ignored(self):
        self.start()
        iid = self.buy("e1", 2)
        self.assertEqual(self.m.intents[iid]["status"], "acked")
        self.assertEqual(self.buy("e1", 2), iid)
        self.assertEqual(len(posts(self.trading)), 1)
        self.bar()
        self.assertEqual(self.m.pos_qty, 2)
        self.assertEqual(self.fill_count(iid), 1)
        self.assert_live_host_only()

    def test_lost_ack_adopted_by_query_not_resent(self):
        self.start()
        self.trading.fault("POST", "lost_ack")
        iid = self.buy("e1", 2)
        self.assertEqual(self.m.intents[iid]["status"], "acked")
        self.assertEqual(len(self.trading.orders), 1)
        self.assertEqual(len(posts(self.trading)), 1)
        self.assert_live_host_only()

    def test_restart_reconciles_from_the_venue_without_resending(self):
        self.start()
        iid = self.buy("e1", 1)
        self.bar()
        n = len(posts(self.trading))
        m = self.restart()
        self.assertEqual(m.pos_qty, 1)
        self.assertEqual(self.fill_count(iid), 1)
        self.assertTrue(m.reconcile()["ok"])
        self.assertEqual(len(posts(self.trading)), n)
        self.assert_live_host_only()

    def test_caps_refuse_before_any_send(self):
        self.start()
        a = self.buy("big", 30)                                            # 30 x ~105 > 2000 notional
        self.assertEqual(self.m.intents[a].get("reason"), "NOTIONAL")
        b = self.buy("wide", 1, invalidation=self.m.mark - 20)             # 1 x ~25 risk > 10 per trade
        self.assertEqual(self.m.intents[b].get("reason"), "MAX_LOSS")
        self.assertEqual(posts(self.trading), [])
        self.buy("e1", 15)                                                 # inside every cap
        self.bar()
        self.assertEqual(self.m.pos_qty, 15)
        c = self.buy("more", 5)                                            # gross 15 + 5 at ~100+ > 2000
        self.assertEqual(self.m.intents[c].get("reason"), "RISK_GROSS")
        self.assertEqual(len(posts(self.trading)), 1)

    def test_stop_and_close_cancels_protection_then_closes_flat(self):
        self.start()
        self.buy("e1", 1)
        self.bar()
        pid = self.m.submit_intent({"decision_id": "prot", "kind": "protective", "side": "sell", "qty": 1,
                                    "stop": 90.0})
        self.assertEqual(self.m.intents[pid]["status"], "acked")
        r = self.m.stop_and_close()
        self.assertEqual(self.m.intents[pid]["status"], "canceled")
        self.assertEqual(r["close"]["state"], "closing", r)
        closes = [c for c in posts(self.trading) if c[3]["side"] == "sell" and c[3]["type"] == "market"]
        self.assertEqual(len(closes), 1)
        self.bar()
        self.assertTrue(self.m.controls.get("flat_confirmed"))
        self.assertEqual((self.trading.pos_qty, self.m.pos_qty), (0, 0))
        self.assert_live_host_only()

    def test_records_still_say_simulated_so_this_cannot_pass_for_live_evidence(self):
        self.start()
        self.buy("e1", 1)
        self.bar()
        rows = list(self.b.positions().values()) + [dict(e) for e in self.b.events() if isinstance(e, dict)]
        self.assertTrue(rows)
        self.assertTrue(all(r.get("simulated") is True for r in rows), rows)
        self.assertTrue(all(r.get("evidence") == LABEL_INJECTED for r in rows))


# ---------------------------------------------------------------- 6. the live broker class (not used by any launcher)

class LiveBrokerTests(Case):
    """AlpacaLiveBroker over the REAL LiveHttpsTransport (injected False). TEST ONLY: its opener is swapped
    for a FakeOpener after construction, so no socket opens; NoNetworkNoKeys guards every test."""

    def setUp(self):
        self.guard = NoNetworkNoKeys().__enter__()
        self.root = tempfile.mkdtemp(prefix="alpaca-live-broker-")
        self.clock = [1000.0]
        self.auth = mint_auth(self.root, monotonic=lambda: self.clock[0])
        self.dir = self.auth.state_dir
        self.cal = SessionCalendar.fixture_profile()
        self.trading = MockTrading()
        self.opener = FakeOpener(self.trading)
        self.transport = self.real_transport()
        L.LiveAdapterState(self.dir).enable(by="test")
        self.mgrs = []
        self.b = self.new_broker()
        self.i = 0

    def tearDown(self):
        Case.tearDown(self)
        self.guard.__exit__(None, None, None)
        shutil.rmtree(self.root, ignore_errors=True)

    def real_transport(self, auth=None):
        t = L.LiveHttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"), auth or self.auth,
                                 monotonic=lambda: self.clock[0])
        self.assertFalse(t.injected)
        t._opener = self.opener          # TEST ONLY: the real class, but no socket
        return t

    def new_broker(self):
        self.b = AlpacaLiveBroker(self.transport, self.dir, L.LABEL_ALPACA_LIVE, L.LiveAdapterState(self.dir))
        return self.b

    def refused(self, *args):
        with self.assertRaises(ValueError) as cm:
            AlpacaLiveBroker(*args)
        return str(cm.exception)

    def test_refuses_a_paper_or_injected_transport(self):
        live_state = L.LiveAdapterState(self.dir)
        self.assertIn("real LiveHttpsTransport",
                      self.refused(MockAlpacaTransport(self.trading), self.dir, L.LABEL_ALPACA_LIVE, live_state))
        self.assertIn("real LiveHttpsTransport",
                      self.refused(HttpsTransport(StaticTestProvider(SYNTH_KEY, SYNTH_SECRET), opener=self.opener),
                                   self.dir, L.LABEL_ALPACA_LIVE, live_state))
        injected = L.LiveHttpsTransport(StaticTestProvider(LIVE_SYNTH_KEY, SYNTH_SECRET, mode="live"), self.auth,
                                        opener=self.opener, monotonic=lambda: self.clock[0])
        self.assertIn("real LiveHttpsTransport", self.refused(injected, self.dir, L.LABEL_ALPACA_LIVE, live_state))

    def test_refuses_other_labels_other_folders_paper_state_and_expired_auth(self):
        live_state = L.LiveAdapterState(self.dir)
        for label in (LABEL_INJECTED, LABEL_MOCK_LOCAL, alpaca.LABEL_ALPACA_PAPER):
            self.assertIn("live label", self.refused(self.transport, self.dir, label, live_state))
        other = os.path.join(self.root, "elsewhere", L.LIVE_STATE_DIRNAME)
        os.makedirs(other)
        self.assertIn("folder the live gate authorized",
                      self.refused(self.transport, other, L.LABEL_ALPACA_LIVE, L.LiveAdapterState(other)))
        paper_dir = os.path.join(self.root, "state-alpaca-paper")
        self.assertIn("must be named", self.refused(self.transport, paper_dir, L.LABEL_ALPACA_LIVE, live_state))
        self.assertIn("live adapter state",
                      self.refused(self.transport, self.dir, L.LABEL_ALPACA_LIVE, AdapterState(self.dir)))
        self.assertIn("live adapter state",
                      self.refused(self.transport, self.dir, L.LABEL_ALPACA_LIVE, L.LiveAdapterState(other)))
        self.clock[0] += L.AUTH_MAX_AGE_S + 1
        self.assertIn("expired", self.refused(self.transport, self.dir, L.LABEL_ALPACA_LIVE, live_state))

    def test_paper_broker_refuses_the_live_label_and_live_state(self):
        mock = MockAlpacaTransport(self.trading)
        paper_dir = tempfile.mkdtemp(prefix="alpaca-paper-", dir=self.root)
        with self.assertRaises(ValueError):
            AlpacaPaperBroker(mock, paper_dir, L.LABEL_ALPACA_LIVE, AdapterState(paper_dir))
        with self.assertRaises(ValueError):
            AlpacaPaperBroker(mock, paper_dir, LABEL_MOCK_LOCAL, L.LiveAdapterState(paper_dir))
        with self.assertRaises(ValueError):
            _LiveRehearsalBroker(self.transport, paper_dir, L.LABEL_ALPACA_LIVE, AdapterState(paper_dir))

    def test_live_records_say_real_money_and_go_only_to_the_live_host(self):
        self.start()
        iid = self.buy("e1", 1)
        self.bar()
        self.assertEqual(self.fill_count(iid), 1)
        rows = list(self.b.positions().values()) + [dict(e) for e in self.b.events() if isinstance(e, dict)]
        self.assertTrue(rows)
        self.assertTrue(all(r.get("simulated") is False for r in rows), rows)
        self.assertTrue(all(r.get("evidence") == L.LABEL_ALPACA_LIVE for r in rows))
        self.assertEqual({r.full_url.split("/")[2] for r in self.opener.requests}, {"api.alpaca.markets"})

    def test_one_post_per_intent_and_restart_resends_nothing(self):
        self.start()
        iid = self.buy("e1", 2)
        self.assertEqual(self.buy("e1", 2), iid)
        self.assertEqual(len(posts(self.trading)), 1)
        self.bar()
        self.restart()
        self.bar()
        self.assertEqual(len(posts(self.trading)), 1)
        self.assertEqual((self.trading.pos_qty, self.m.pos_qty), (2, 2))

    def test_live_state_never_writes_the_paper_file_so_the_next_gate_still_passes(self):
        self.start()
        self.buy("e1", 1)
        self.bar()
        self.assertTrue(os.path.exists(os.path.join(self.dir, L.LIVE_STATE_FILE)))
        self.assertFalse(os.path.exists(os.path.join(self.dir, alpaca.STATE_FILE)))
        limits = sizing.approved_path(self.dir)
        again = L.live_gate_authorize(limits, self.dir, L.LIVE_PORT, L.confirm_phrase(1, L.session_date(NOW)), True,
                                      now_utc=NOW, shown_hash=shown_hash(limits))
        self.assertEqual(again.limits_hash, self.auth.limits_hash)

    def test_a_disable_by_another_writer_is_adopted_from_the_live_file(self):
        self.start()
        L.LiveAdapterState(self.dir).disable("operator stop", by="test")
        before = len(posts(self.trading))
        self.buy("e2", 1)
        self.assertEqual(len(posts(self.trading)), before)
        self.assertFalse(self.b.adapter_state.enabled)


if __name__ == "__main__":
    unittest.main()
