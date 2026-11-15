"""Connection and market readiness must use only the documented, pinned read routes."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
from alpaca.readiness import check_connection, main, read_quote

AT = "2026-11-16T15:31:00+00:00"
QUOTE = "/v2/stocks/SPY/quotes/latest"

class Responses:
    def __init__(self):
        self.calls = []
        self.payload = {
            "/v2/account": {"status":"ACTIVE","account_blocked":False,"trading_blocked":False,
                            "id":"identifier-that-must-stay-local","buying_power":"99999.99"},
            "/v2/assets/SPY": {"symbol":"SPY","status":"active","tradable":True},
            "/v2/clock": {"is_open":True,"timestamp":AT},
            QUOTE: {"symbol":"SPY","quote":{"bp":"100.00","ap":"100.02","bs":1,"as":3,"t":AT}},
        }
        self.status = {}
    def request(self, method, origin, path, query=None):
        self.calls.append((method,origin,path,query))
        return self.status.get(path,200), self.payload[path]

class ReadinessTests(unittest.TestCase):
    def test_four_read_routes_and_redaction(self):
        t = Responses()
        out = check_connection(t, AT)
        self.assertTrue(out["connection_verified"])
        self.assertTrue(out["market_conditions_ready"])
        self.assertEqual(out["quote"]["spread_usd"],.02)
        self.assertAlmostEqual(out["quote"]["spread_bps"],1.99980002)
        for private in ["identifier-that-must-stay-local","99999.99"]:
            self.assertNotIn(private,json.dumps(out))
        self.assertEqual(t.calls,[("GET","trading","/v2/account",None),("GET","trading","/v2/assets/SPY",None),
                                  ("GET","trading","/v2/clock",None),("GET","data",QUOTE,{"feed":"iex"})])
    def test_closed_is_distinct_from_connection(self):
        t = Responses()
        t.payload["/v2/clock"]["is_open"] = False
        t.payload[QUOTE]["quote"]["t"] = "2026-11-13T20:59:59Z"
        out = check_connection(t, AT)
        self.assertTrue(out["connection_verified"])
        self.assertFalse(out["market_conditions_ready"])
        self.assertEqual(set(out["reasons"]),{"MARKET_CLOSED","STALE_QUOTE"})
    def test_quotes_reject_crossed_invalid_and_future(self):
        for changes,reason in [({"ap":99},"CROSSED_QUOTE"),({"ap":float("nan")},"INVALID_QUOTE"),
                               ({"bs":0},"INVALID_QUOTE"),({"t":"2026-11-16T15:31:03Z"},"FUTURE_QUOTE")]:
            with self.subTest(reason=reason):
                t=Responses()
                t.payload[QUOTE]["quote"].update(changes)
                out=read_quote(t,AT)
                self.assertFalse(out["fresh"])
                self.assertEqual(out["reason"],reason)
                json.dumps(out,allow_nan=False)
    def test_account_and_clock_fail_closed(self):
        t = Responses()
        t.payload["/v2/account"]["trading_blocked"] = True
        out=check_connection(t,"2026-11-16T16:31:00Z")
        self.assertTrue(out["connection_verified"])
        self.assertFalse(out["market_conditions_ready"])
        self.assertIn("MARKET_CLOCK_SKEW",out["reasons"])
        self.assertIn("ACCOUNT_BLOCKED_OR_UNVERIFIED",out["reasons"])
    def test_401_stops_after_one_read_and_hides_error_body(self):
        t=Responses()
        t.payload["/v2/account"]={"message":"private upstream error"}
        t.status["/v2/account"]=401
        out=check_connection(t,AT)
        self.assertEqual(len(t.calls),1)
        self.assertEqual(out["reasons"],["AUTHENTICATION_FAILED"])
        self.assertNotIn("private upstream error",json.dumps(out))
    def test_blank_or_draft_limits_never_construct_a_provider_or_transport(self):
        with tempfile.TemporaryDirectory() as d, patch("alpaca.setup.KeychainProvider") as kp, \
                patch("alpaca.setup.EnvProvider") as ep, patch("alpaca.transport.HttpsTransport") as http, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--state-dir",d]),2)
            Path(d,"limits_draft.json").write_text(json.dumps({"provenance":"draft","values":{}}))
            self.assertEqual(main(["--state-dir",d,"--provider","env"]),2)
            kp.assert_not_called()
            ep.assert_not_called()
            http.assert_not_called()
