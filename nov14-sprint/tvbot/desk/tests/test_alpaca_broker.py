"""Tests for the Alpaca PAPER adapter: alpaca.transport, alpaca.mock, alpaca.broker (W1).

No network, no credentials: every request goes to the in-process MockTrading through MockAlpacaTransport,
or through HttpsTransport with an injected fake opener and StaticTestProvider synthetic values.
No socket is opened; no environment variable or Keychain item is read. Limits are TEST VALUES.

Run: /usr/bin/python3 -IB -m unittest discover -s <desk>/tests -p 'test_alpaca_broker*'
"""
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
FIX = os.path.join(os.path.dirname(DESK), "fixtures")
if DESK not in sys.path:
    sys.path.insert(0, DESK)

import alpaca  # noqa: E402
from alpaca import LABEL_ALPACA_PAPER, LABEL_INJECTED, LABEL_MOCK_LOCAL  # noqa: E402
from alpaca.broker import BOOK_FILE, AlpacaPaperBroker, map_status  # noqa: E402
from alpaca.mock import MockAlpacaTransport, MockTrading  # noqa: E402
from alpaca.state import AdapterState  # noqa: E402
from alpaca.transport import (HttpsTransport, StaticTestProvider, TransportRefused, encode_query,  # noqa: E402
                              validate_path)
from orders.calendar import SessionCalendar  # noqa: E402
from orders.fake_broker import BrokerOutage, BrokerUncertain  # noqa: E402
from orders.manager import OrderManager  # noqa: E402

# TEST VALUES only (same as test_orders_manager). Real limits are Matthew's alone.
LIMITS = {"per_trade_notional": 2000, "max_loss_per_trade": 10.0, "daily_loss": 30.0, "gross_exposure": 2000,
          "label": "TEST VALUES"}
FAR = "2026-06-30T00:00:00Z"
LX = 101.00   # TEST VALUE: an entry limit above the 100.00 test price
SYNTH_KEY = "SYNTHKEYID-TEST-0001"                       # synthetic, not a real key
SYNTH_SECRET = "SYNTHSECRET-TEST-DO-NOT-USE-0001"        # synthetic, not a real secret


def load_bars(path):
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                if rec.get("type") != "manifest":
                    out.append(rec)
    return out


BARS = load_bars(os.path.join(FIX, "normal_bars.jsonl"))


def posts(trading):
    return [c for c in trading.calls if c[0] == "POST"]


class FakeResp(object):
    def __init__(self, status, payload, url):
        self.status = status
        self._raw = b"" if payload is None else json.dumps(payload).encode()
        self._url = url

    def geturl(self):
        return self._url

    def getcode(self):
        return self.status

    def read(self):
        return self._raw

    def close(self):
        pass


class FakeOpener(object):
    """Stands in for urllib's opener: routes HttpsTransport requests to MockTrading. No socket."""

    def __init__(self, trading):
        self.trading = trading
        self.requests = []
        self.mode = None              # None | "redirect" | "foreign" | "status302"
        self.only = None              # apply mode only to this HTTP method

    def open(self, req, timeout=None):
        self.requests.append(req)
        url = req.full_url
        parts = urllib.parse.urlsplit(url)
        mode = self.mode if (self.only is None or req.get_method() == self.only) else None
        if mode == "redirect":
            raise urllib.error.HTTPError(url, 302, "Found", {"Location": "https://evil.example/v2/x"}, io.BytesIO(b""))
        if mode == "foreign":
            return FakeResp(200, {}, "https://evil.example" + parts.path)
        if mode == "status302":
            return FakeResp(302, None, url)
        query = dict(urllib.parse.parse_qsl(parts.query)) or None
        body = json.loads(req.data.decode()) if req.data else None
        st, payload = self.trading.handle(req.get_method(), parts.path, query, body)
        if st >= 400:
            raise urllib.error.HTTPError(url, st, "err", {}, io.BytesIO(json.dumps(payload or {}).encode()))
        return FakeResp(st, payload, url)


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="alpaca-broker-test-")
        self.cal = SessionCalendar.fixture_profile()
        self.trading = MockTrading()
        self.transport = MockAlpacaTransport(self.trading)
        AdapterState(self.dir).enable(by="test")
        self.mgrs = []
        self.b = self.new_broker()
        self.i = 0

    def tearDown(self):
        for m in self.mgrs:
            m.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def new_broker(self):
        self.b = AlpacaPaperBroker(self.transport, self.dir, LABEL_MOCK_LOCAL, AdapterState(self.dir))
        return self.b

    def new_manager(self):
        self.m = OrderManager(self.dir, self.b, LIMITS, calendar=self.cal)
        self.mgrs.append(self.m)
        return self.m

    def restart(self):
        """Process restart: the Alpaca side (MockTrading) survives, the desk objects are rebuilt from disk."""
        self.m.close()
        self.new_broker()
        return self.new_manager()

    def bar(self, manager=True, market=True):
        bar = BARS[self.i]
        self.i += 1
        if market:
            self.trading.advance(bar["close"])
        self.b.step(bar)
        if manager:
            return self.m.on_bar(bar)
        return None

    def start(self):
        self.new_manager()
        self.bar()
        r = self.m.arm("S1", expires_utc=FAR)
        self.assertTrue(r["ok"], r)

    def buy(self, did, qty, **kw):
        kw.setdefault("limit", round(self.m.mark + 5.0, 2))   # TEST VALUE: entries are always priced
        intent = {"decision_id": did, "side": "buy", "qty": qty, "ref_price": self.m.mark,
                  "invalidation": (kw.get("limit") or self.m.mark) - 0.5}
        intent.update(kw)
        return self.m.submit_intent(intent)

    def fill_count(self, iid):
        return len([f for f in self.m.fills if f["intent_id"] == iid])


class ManagerFlowTests(Case):
    def test_ack_and_fill_through_manager(self):
        self.start()
        iid = self.buy("e1", 3)
        self.assertEqual(self.m.intents[iid]["status"], "acked")
        self.assertEqual(len(posts(self.trading)), 1)
        self.bar()
        self.assertEqual(self.m.intents[iid]["status"], "filled")
        self.assertEqual(self.m.pos_qty, 3)
        self.assertEqual(self.trading.pos_qty, 3)
        fill = self.m.fills[-1]
        self.assertFalse(fill["mock"] is None)
        self.assertTrue(self.m.reconcile()["ok"])

    def test_lost_ack_is_adopted_by_query_not_resent(self):
        self.start()
        self.trading.fault("POST", "lost_ack")
        iid = self.buy("e1", 2)
        self.assertEqual(self.m.intents[iid]["status"], "acked")
        self.assertEqual(len(self.trading.orders), 1)       # one order at Alpaca, no duplicate POST landed
        self.bar()
        self.assertEqual(self.m.pos_qty, 2)
        self.assertEqual(self.fill_count(iid), 1)

    def test_lost_response_hidden_order_survives_restart_and_books_once(self):
        """Release blocker 1: accepted at the venue, response lost, lookup and listing empty, restart."""
        self.start()
        self.trading.fault("POST", "lost_ack")
        self.trading.hide_next = 1
        iid = self.buy("e1", 1)
        cid = self.m.intents[iid]["client_id"]
        self.assertEqual(self.m.intents[iid]["status"], "uncertain")
        self.assertEqual(len(self.trading.orders), 1)
        rep = self.m.reconcile(reason="test")
        self.assertIn("SUBMIT_UNRESOLVED", [a["code"] for a in rep["alarms"] if a["blocking"]])
        self.assertEqual(rep["not_placed"], [])
        self.b.note_reconcile(rep)
        self.assertEqual(self.b.submit("other-1", "buy", 1, limit=LX)["reason"], "RECOVERY_AMBIGUOUS")
        m = self.restart()
        self.assertEqual(m.intents[iid]["status"], "uncertain")
        self.assertEqual(self.b.uncertain_client_ids(), [cid])
        self.assertEqual(self.b.submit("other-2", "buy", 1, limit=LX)["reason"], "RECOVERY_AMBIGUOUS")
        self.assertEqual(m.pos_qty, 0)
        self.trading.reveal()                             # the venue's order becomes visible, then trades
        self.bar()
        self.bar()
        self.assertEqual(self.m.pos_qty, 1)
        self.assertEqual(self.fill_count(iid), 1)
        self.assertNotEqual(self.m.intents[iid]["status"], "not_placed")
        self.assertEqual(len(self.trading.orders), 1)     # one order at Alpaca
        self.assertEqual(set(c[3]["client_order_id"] for c in posts(self.trading)), {cid})
        self.assertEqual(self.b.uncertain_client_ids(), [])
        self.assertFalse(any(r.get("reason") == "NOT_PLACED" for r in self.m.audit_rows()
                             if isinstance(r, dict))) if hasattr(self.m, "audit_rows") else None

    def test_timeout_without_order_resends_same_client_id_once(self):
        self.start()
        self.trading.fault("POST", "timeout")
        iid = self.buy("e1", 2)
        self.assertEqual(self.m.intents[iid]["status"], "acked")
        self.assertEqual(len(self.trading.orders), 1)
        self.assertEqual(len(posts(self.trading)), 2)        # first lost, one resend with the same client id
        cids = set(json.dumps(c[3], sort_keys=True) for c in posts(self.trading))
        self.assertEqual(len(cids), 1)

    def test_unresolved_uncertain_blocks_new_exposure(self):
        self.start()
        self.trading.fault("POST", "lost_ack")
        self.trading.fault("GET", "5xx", count=3, path_prefix="/v2/orders")   # the recovery query fails, positions read works
        iid = self.buy("e1", 2)
        self.assertEqual(self.m.intents[iid]["status"], "uncertain")
        self.assertEqual(self.b.block_reason(), "RECOVERY_AMBIGUOUS")
        n = len(posts(self.trading))
        r = self.b.submit("other-1", "buy", 1, limit=LX)
        self.assertEqual((r["status"], r["reason"]), ("rejected", "RECOVERY_AMBIGUOUS"))
        self.assertEqual(len(posts(self.trading)), n)        # nothing sent
        self.trading.faults = []
        rep = self.m.reconcile()
        self.assertEqual(self.m.intents[iid]["status"], "acked", rep)
        self.assertIsNone(self.b.block_reason())

    def test_partial_fills_across_restart_no_double_booking(self):
        self.start()
        self.trading.partial_next = 1
        iid = self.buy("e1", 3)
        self.bar()                                       # 1 of 3
        self.assertEqual(self.m.pos_qty, 1)
        self.bar(manager=False)                          # broker sees 2 of 3, desk dies before booking it
        self.trading.advance(BARS[self.i]["close"])      # 3 of 3 lands at Alpaca while the desk is down
        m = self.restart()
        self.assertEqual(m.pos_qty, 3)
        self.assertEqual(self.fill_count(iid), 3)
        self.assertEqual(sorted(f["exec_id"] for f in m.fills if f["intent_id"] == iid),
                         sorted("%s:%d" % (m.intents[iid]["order_id"], k) for k in (1, 2, 3)))
        self.bar()
        self.bar()
        m = self.restart()
        self.assertEqual(m.pos_qty, 3)
        self.assertEqual(self.fill_count(iid), 3)
        self.assertEqual(m.intents[iid]["status"], "filled")
        self.assertTrue(m.reconcile()["ok"])

    def test_reject_http_and_status(self):
        self.start()
        self.trading.reject_next = "http"
        a = self.buy("e1", 1)
        self.assertEqual(self.m.intents[a]["status"], "rejected")
        self.assertEqual(self.m.intents[a].get("reason"), "INSUFFICIENT_BUYING_POWER")
        self.trading.reject_next = "status"
        b = self.buy("e2", 1)
        self.assertEqual(self.m.intents[b]["status"], "rejected")
        self.assertEqual(self.m.intents[b].get("reason"), "ALPACA_REJECTED")
        self.bar()
        self.assertEqual(self.m.pos_qty, 0)

    def test_foreign_spy_order_disables_and_manager_flags_it(self):
        self.trading.add_foreign_order()
        self.new_manager()
        self.assertFalse(AdapterState(self.dir).enabled)
        self.assertIn("FOREIGN_ORDER", AdapterState(self.dir).data["disabled_reason"])
        self.assertIn("FOREIGN_ORDER", [a["code"] for a in self.m.reconcile()["alarms"]])

    def test_incomplete_listing_blocks(self):
        for k in range(3):
            self.b.submit("pre-%d" % k, "buy", 1, limit=1.00)
        self.b.list_limit = 2
        self.trading.listing_cap = 2
        self.new_manager()
        rep = self.m.reconcile()
        self.assertFalse(rep["ok"])
        self.assertEqual(self.b.block_reason(), "RECOVERY_AMBIGUOUS")


class BrokerUnitTests(Case):
    def test_status_map(self):
        self.assertEqual(map_status("partially_filled"), "working")
        self.assertEqual(map_status("expired"), "canceled")
        self.assertEqual(map_status("done_for_day"), "canceled")
        self.assertEqual(map_status("weird"), "weird")

    def test_label_must_match_transport(self):
        with self.assertRaises(ValueError):
            AlpacaPaperBroker(self.transport, self.dir, LABEL_ALPACA_PAPER, AdapterState(self.dir))
        real_shape = HttpsTransport(StaticTestProvider(SYNTH_KEY, SYNTH_SECRET))   # builds an opener, sends nothing
        with self.assertRaises(ValueError):
            AlpacaPaperBroker(real_shape, self.dir, LABEL_MOCK_LOCAL, AdapterState(self.dir))
        with self.assertRaises(ValueError):
            AlpacaPaperBroker(self.transport, self.dir, "made up label", AdapterState(self.dir))

    def test_cancel_race_fill_after_cancel_request(self):
        self.trading.cancel_mode = "pending"
        self.b.step({"close": 100.0, "ts_close": "t1"})
        r = self.b.submit("c1", "buy", 2, limit=99.00)
        self.assertEqual(r["status"], "accepted")
        c = self.b.cancel("c1")
        self.assertEqual(c["status"], "canceled")
        self.assertEqual(c["alpaca_status"], "pending_cancel")
        self.b.events()
        self.trading.advance(98.50)                       # fills before the cancel completes
        fills = self.b.step({"close": 98.50, "ts_close": "t2"})
        self.assertEqual([f["qty"] for f in fills], [2])
        self.assertEqual(self.b.query("c1")["status"], "filled")
        again = self.b.cancel("c1")
        self.assertEqual((again["status"], again["reason"]), ("rejected", "ALREADY_FILLED"))
        self.assertEqual(self.b.cancel("nobody")["reason"], "UNKNOWN_ORDER")

    def test_cancel_then_canceled_event_once(self):
        self.b.submit("c2", "buy", 1, limit=50.00)
        self.b.events()
        self.assertEqual(self.b.cancel("c2")["status"], "canceled")
        self.b.step({"close": 100.0})
        evs = [e for e in self.b.events() if e["type"] == "canceled"]
        self.assertEqual(len(evs), 1)
        again = self.b.cancel("c2")
        self.assertEqual(again["reason"], "ALREADY_DONE")

    def test_disabled_refusal_persists_across_reopen(self):
        other = AdapterState(self.dir)                    # another writer (the UI) turns it off
        other.disable("operator turned it off (test)", by="operator")
        n = len(self.trading.calls)
        r = self.b.submit("d1", "buy", 1, limit=LX)
        self.assertEqual(r["reason"], "ADAPTER_DISABLED")
        self.assertEqual(len(self.trading.calls), n)      # refused before any request
        b2 = self.new_broker()
        self.assertEqual(b2.submit("d2", "buy", 1, limit=LX)["reason"], "ADAPTER_DISABLED")
        self.assertFalse(AdapterState(self.dir).enabled)
        self.assertEqual(posts(self.trading), [])

    def test_reduce_only_allowed_when_disabled_and_capped(self):
        self.b.submit("r0", "buy", 2, limit=LX)
        self.trading.advance(100.0)
        self.b.step({"close": 100.0})
        AdapterState(self.dir).disable("test", by="operator")
        r = self.b.submit("r1", "sell", 5, stop=95.00, reduce_only=True)
        self.assertEqual(r["status"], "accepted")
        self.assertEqual(self.trading.orders[r["order_id"]]["qty"], 2)
        r2 = self.b.submit("r2", "sell", 1, stop=94.00, reduce_only=True)   # room is used by r1
        self.assertEqual(r2["reason"], "REDUCE_ONLY_NO_POSITION")
        self.assertEqual(self.b.submit("r3", "buy", 1, limit=LX)["reason"], "ADAPTER_DISABLED")

    def test_exec_caps_refuse_before_sending(self):
        self.b.exec_caps = {"per_trade_notional": 150.0, "gross_exposure": 250.0}    # TEST VALUES
        self.b.step({"close": 100.0, "ts_close": "t1"})
        r = self.b.submit("x1", "buy", 2, limit=LX)
        self.assertEqual(r["reason"], "EXEC_CAP")
        self.assertEqual(self.b.exec_refusals[-1]["notional"], 202.0)
        self.assertEqual(posts(self.trading), [])
        self.assertEqual(self.b.submit("x2", "buy", 1, limit=LX)["status"], "accepted")
        self.assertEqual(self.b.submit("x3", "buy", 1, limit=LX)["status"], "accepted")
        self.assertEqual(self.b.submit("x4", "buy", 1, limit=LX)["reason"], "EXEC_CAP")

    def test_local_rejects(self):
        self.assertEqual(self.b.submit("bad id!", "buy", 1)["reason"], "BAD_CLIENT_ID")
        self.assertEqual(self.b.submit("p1", "buy", 1, limit=-1.0)["reason"], "BAD_PRICE")
        self.assertEqual(self.b.submit("p2", "buy", 1, limit=100.0, stop=99.0)["reason"], "UNSUPPORTED_ORDER_TYPE")
        with self.assertRaises(ValueError):
            self.b.submit("p3", "buy", 1.5)
        self.assertEqual(self.b.submit("ok1", "buy", 1, limit=LX)["status"], "accepted")
        dup = self.b.submit("ok1", "buy", 1, limit=LX)
        self.assertEqual(dup["reason"], "DUPLICATE_CLIENT_ORDER_ID")
        self.assertEqual(len(posts(self.trading)), 1)

    def test_server_duplicate_is_adopted(self):
        self.trading.fault("POST", "lost_ack")
        with self.assertRaises(BrokerUncertain):
            self.b.submit("dup1", "buy", 1, limit=LX)
        rec = self.b.book["orders"]["dup1"]
        rec["state"] = "not_found"                        # as if a query had wrongly said not found
        r = self.b.submit("dup1", "buy", 1, limit=LX)
        self.assertEqual(r["reason"], "DUPLICATE_CLIENT_ORDER_ID")
        self.assertTrue(r["order_id"])
        self.assertEqual(len(self.trading.orders), 1)

    def test_crash_between_persist_and_post_is_uncertain(self):
        self.b.book["orders"]["s1"] = {"state": "sending", "order_id": None, "side": "buy", "qty": 1,
                                       "status": None, "cum_qty": 0, "fills": []}
        self.b._save()
        b2 = self.new_broker()
        self.assertEqual(b2.uncertain_client_ids(), ["s1"])
        self.assertEqual(b2.block_reason(), "RECOVERY_AMBIGUOUS")
        with self.assertRaises(BrokerUncertain):
            b2.query("s1")                                # a 404 is not proof it was never placed
        self.assertEqual(b2.uncertain_client_ids(), ["s1"])
        self.assertEqual(b2.block_reason(), "RECOVERY_AMBIGUOUS")
        amb, why = b2.recovery_ambiguous()
        self.assertTrue(amb)
        self.assertTrue(why.startswith("SUBMIT_UNRESOLVED"))

    def test_position_mismatch_disables(self):
        self.trading.set_position(5, 100.0)
        self.b.positions()
        st = AdapterState(self.dir)
        self.assertFalse(st.enabled)
        self.assertIn("POSITION_MISMATCH", st.data["disabled_reason"])

    def test_malformed_book_disables(self):
        with open(os.path.join(self.dir, BOOK_FILE), "w") as fh:
            fh.write("{not json")
        with self.assertRaises(ValueError):
            self.new_broker()
        self.assertFalse(AdapterState(self.dir).enabled)

    def test_outage_on_read_is_broker_outage(self):
        self.trading.fault("GET", "timeout")
        with self.assertRaises(BrokerOutage):
            self.b.positions()
        self.trading.fault("GET", "5xx")
        self.assertEqual(self.b.step({"close": 100.0}), [])

    def test_snapshot_round_trip(self):
        self.b.exec_caps = {"per_trade_notional": 1.0}
        self.b.step({"close": 101.0, "ts_close": "t9"})
        snap = json.loads(json.dumps(self.b.snapshot()))
        b2 = self.new_broker().restore(snap)
        self.assertEqual(b2.exec_caps, {"per_trade_notional": 1.0})
        self.assertEqual(b2._last_close, 101.0)
        with self.assertRaises(ValueError):
            b2.restore({"format": "fake-broker"})


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="alpaca-transport-test-")
        self.trading = MockTrading()
        self.opener = FakeOpener(self.trading)
        self.t = HttpsTransport(StaticTestProvider(SYNTH_KEY, SYNTH_SECRET), opener=self.opener)
        AdapterState(self.dir).enable(by="test")
        self.b = AlpacaPaperBroker(self.t, self.dir, LABEL_INJECTED, AdapterState(self.dir))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_round_trip_uses_fixed_paper_host_and_headers(self):
        r = self.b.submit("t1", "buy", 1, limit=LX)
        self.assertEqual(r["status"], "accepted")
        req = self.opener.requests[-1]
        self.assertTrue(req.full_url.startswith("https://paper-api.alpaca.markets/v2/orders"))
        self.assertEqual(req.get_header("Apca-api-key-id"), SYNTH_KEY)

    def test_redirect_refused(self):
        self.opener.mode = "redirect"
        with self.assertRaises(TransportRefused) as cm:
            self.t.request("GET", "trading", "/v2/account")
        self.assertTrue(cm.exception.sent)
        self.opener.mode = "status302"
        with self.assertRaises(TransportRefused):
            self.t.request("GET", "trading", "/v2/account")

    def test_redirect_on_post_is_uncertain_and_disables(self):
        self.opener.mode = "redirect"
        self.opener.only = "POST"
        with self.assertRaises(BrokerUncertain):
            self.b.submit("t2", "buy", 1, limit=LX)
        self.assertFalse(AdapterState(self.dir).enabled)
        self.assertEqual(self.b.uncertain_client_ids(), ["t2"])

    def test_foreign_host_refused(self):
        self.opener.mode = "foreign"
        with self.assertRaises(TransportRefused):
            self.t.request("GET", "trading", "/v2/account")
        with self.assertRaises(BrokerOutage):
            self.b.positions()
        self.assertFalse(AdapterState(self.dir).enabled)

    def test_live_host_refused_even_if_origins_edited(self):
        saved = dict(alpaca.ORIGINS)
        try:
            alpaca.ORIGINS["trading"] = "https://api.alpaca.markets"
            with self.assertRaises(TransportRefused):
                self.t.request("GET", "trading", "/v2/account")
            alpaca.ORIGINS["trading"] = "https://paper-api.alpaca.markets.evil.example"
            with self.assertRaises(TransportRefused):
                self.t.request("GET", "trading", "/v2/account")
        finally:
            alpaca.ORIGINS.clear()
            alpaca.ORIGINS.update(saved)
        self.assertEqual(self.opener.requests, [])
        with self.assertRaises(TransportRefused):
            self.t.request("GET", "live", "/v2/account")

    def test_path_injection_refused(self):
        bad = ["/v1/orders", "/v2/../v1/x", "/v2/orders?x=1", "/v2/orders#f", "/v2/orders%2f..", "/v2/@evil",
               "https://evil.example/v2/x", "/v2/a\\b", "/v2/a b", "/v2/a\nb", "/v2/x://y", "v2/orders"]
        for p in bad:
            with self.assertRaises(TransportRefused, msg=p):
                validate_path(p)
            with self.assertRaises(TransportRefused, msg=p):
                self.t.request("GET", "trading", p)
            with self.assertRaises(TransportRefused, msg=p):
                MockAlpacaTransport(self.trading).request("GET", "trading", p)
        self.assertEqual(self.opener.requests, [])
        self.assertEqual(validate_path("/v2/orders:by_client_order_id"), "/v2/orders:by_client_order_id")

    def test_feed_and_paid_params_refused(self):
        for q in ({"feed": "sip"}, {"feed": "otc"}, {"feed": "boats"}, {"symbols": "SPY", "x": "sip"}):
            with self.assertRaises(TransportRefused, msg=q):
                encode_query("data", q)
            with self.assertRaises(TransportRefused, msg=q):
                self.t.request("GET", "data", "/v2/stocks/SPY/bars", q)
            with self.assertRaises(TransportRefused, msg=q):
                MockAlpacaTransport(self.trading).request("GET", "data", "/v2/stocks/SPY/bars", q)
        self.assertEqual(self.opener.requests, [])
        self.assertIn("feed=iex", encode_query("data", {"feed": "iex", "timeframe": "1Min"}))

    def test_paper_label_fills_reach_manager_ledger_as_not_mock(self):
        # Real-shape transport (injected False), its opener swapped for the fake before any request: no socket.
        t = HttpsTransport(StaticTestProvider(SYNTH_KEY, SYNTH_SECRET))
        t._opener = self.opener
        d = tempfile.mkdtemp(prefix="alpaca-paper-label-test-")
        try:
            AdapterState(d).enable(by="test")
            b = AlpacaPaperBroker(t, d, LABEL_ALPACA_PAPER, AdapterState(d))
            self.assertEqual(b.price_basis, "Alpaca paper fill")
            m = OrderManager(d, b, LIMITS, calendar=SessionCalendar.fixture_profile())
            try:
                bar = BARS[0]
                self.trading.advance(bar["close"])
                b.step(bar)
                m.on_bar(bar)
                self.assertTrue(m.arm("S1", expires_utc=FAR)["ok"])
                iid = m.submit_intent({"decision_id": "p1", "side": "buy", "qty": 1, "ref_price": m.mark,
                                       "limit": round(m.mark + 5.0, 2), "invalidation": m.mark - 0.5})
                bar = BARS[1]
                self.trading.advance(bar["close"])
                b.step(bar)
                m.on_bar(bar)
                self.assertEqual(m.pos_qty, 1)
                self.assertIs(m.fills[-1]["mock"], False)
                row = [r for r in m.ledger_rows() if r["intent_id"] == iid][0]
                self.assertIs(row["fills"][0]["mock"], False)
                self.assertTrue(row["simulated"])
            finally:
                m.close()
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertTrue(all(r.full_url.startswith("https://paper-api.alpaca.markets/") for r in self.opener.requests))

    def test_no_secret_in_exceptions_repr_or_state_files(self):
        texts = [repr(self.t), str(self.t), repr(self.t._provider)]
        self.b.submit("s1", "buy", 1, limit=LX)
        self.b.query("s1")
        self.b.cancel("s1")
        self.b.list_orders()
        self.trading.fault("POST", "5xx")
        self.trading.fault("GET", "timeout")
        for mode, call in ((None, lambda: self.b.submit("s2", "buy", 1, limit=LX)),
                           (None, lambda: self.b.positions()),
                           ("redirect", lambda: self.b.submit("s3", "buy", 1, limit=LX, reduce_only=False)),
                           ("foreign", lambda: self.b.positions()),
                           (None, lambda: self.t.request("GET", "data", "/v2/x", {"feed": "sip"})),
                           (None, lambda: HttpsTransport(StaticTestProvider(SYNTH_KEY, "bad secret\n"),
                                                         opener=self.opener).request("GET", "trading", "/v2/account"))):
            self.opener.mode = mode
            try:
                call()
            except Exception as exc:                      # every failure path, collected
                texts.extend([str(exc), repr(exc), str(getattr(exc, "__context__", ""))])
            else:
                texts.append(json.dumps(self.b.recovery_view(), default=str))
        for name in os.listdir(self.dir):
            with open(os.path.join(self.dir, name)) as fh:
                texts.append(fh.read())
        blob = "\n".join(texts)
        self.assertGreater(len(texts), 10)
        self.assertNotIn(SYNTH_SECRET, blob)
        self.assertNotIn(SYNTH_KEY, blob)
        self.assertNotIn("bad secret", blob)


if __name__ == "__main__":
    unittest.main()
