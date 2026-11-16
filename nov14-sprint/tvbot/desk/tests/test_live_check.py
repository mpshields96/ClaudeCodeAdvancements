"""The standalone live connection check has no route to an order or an armed session."""
import contextlib
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from urllib.parse import urlsplit

DESK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(DESK), str(DESK / "tests")]

import live_check
from alpaca import live
from alpaca.transport import StaticTestProvider, TransportRefused
from test_alpaca_broker import FakeResp
from test_alpaca_live import approve_live_dir, mint_auth, NoNetworkNoKeys
from test_alpaca_readiness import Responses


class LiveCheckTests(unittest.TestCase):
    def test_refusal_happens_before_credentials(self):
        with tempfile.TemporaryDirectory() as scratch, NoNetworkNoKeys(), \
                patch.object(live, "make_live_provider") as provider, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            live_dir = str(Path(scratch) / live.LIVE_STATE_DIRNAME)
            self.assertEqual(live_check.main(["--state-dir", live_dir]), 2)
            approve_live_dir(scratch)
            with patch("sys.stdin.isatty", return_value=False):
                self.assertEqual(live_check.main(["--state-dir", live_dir]), 2)
            with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="NO"):
                self.assertEqual(live_check.main(["--state-dir", live_dir]), 2)
            provider.assert_not_called()

    def test_only_four_exact_read_requests_can_pass(self):
        with tempfile.TemporaryDirectory() as scratch, NoNetworkNoKeys():
            opener = Mock()
            provider = StaticTestProvider("AK-SYNTHETIC-CHECK", "synthetic-secret", mode="live")
            transport = live_check.ReadOnlyLiveTransport(provider, mint_auth(scratch), opener=opener)
            attempts = [
                ("POST", "trading", "/v2/orders", None, {"symbol": "SPY"}),
                ("DELETE", "trading", "/v2/orders", None, None),
                ("GET", "trading", "/v2/orders", None, None),
                ("GET", "trading", "/v2/account", None, {}),
                ("GET", "trading", "/v2/clock", {"extra": "q"}, None),
                ("GET", "data", live_check.QUOTE_PATH, {"feed":"sip"}, None),
                ("GET", "trading", live_check.QUOTE_PATH, {"feed":"iex"}, None),
            ]
            for method, origin, path, query, body in attempts:
                with self.subTest(method=method, path=path, query=query), self.assertRaises(TransportRefused):
                    transport.request(method, origin, path, query=query, body=body)
            opener.open.assert_not_called()

    def test_cli_uses_live_origins_and_distinguishes_sunday_from_failure(self):
        sunday = datetime(2026, 11, 16, 2, 30, tzinfo=timezone.utc)
        fixtures = Responses().payload
        fixtures["/v2/clock"] = {"is_open":False, "timestamp":sunday.isoformat()}
        fixtures[live_check.QUOTE_PATH]["quote"]["t"] = "2026-11-13T20:59:00+00:00"
        opener = Mock()
        opener.open.side_effect = lambda req, timeout: FakeResp(
            200, fixtures[urlsplit(req.full_url).path], req.full_url)
        provider = StaticTestProvider("AK-SYNTHETIC-CHECK", "synthetic-secret", mode="live")
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as scratch, NoNetworkNoKeys():
            state, _ = approve_live_dir(scratch)
            phrase = live.confirm_phrase(1, live.session_date())
            with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value=phrase), \
                    patch.object(live, "make_live_provider", return_value=provider), \
                    patch("alpaca.transport.default_opener", return_value=opener), \
                    patch.object(live_check, "datetime") as clock, contextlib.redirect_stdout(out):
                clock.now.return_value = sunday
                self.assertEqual(live_check.main(["--state-dir", state]), 0)
        urls = [(c.args[0].get_method(), c.args[0].full_url) for c in opener.open.call_args_list]
        self.assertEqual(urls, [
            ("GET", "https://api.alpaca.markets/v2/account"),
            ("GET", "https://api.alpaca.markets/v2/assets/SPY"),
            ("GET", "https://api.alpaca.markets/v2/clock"),
            ("GET", "https://data.alpaca.markets/v2/stocks/SPY/quotes/latest?feed=iex"),
        ])
        for text in ("Live account connection verified", "clock: closed", "STALE_QUOTE", "OUTSIDE_REGULAR_SESSION"):
            self.assertIn(text, out.getvalue())
        for private in ("identifier-that-must-stay-local", "99999.99", "synthetic-secret", "AK-SYNTHETIC"):
            self.assertNotIn(private, out.getvalue())
