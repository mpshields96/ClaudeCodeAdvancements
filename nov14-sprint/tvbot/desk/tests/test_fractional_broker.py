"""Fractional mode of the Alpaca PAPER adapter (alpaca.broker with fractional=True) against alpaca.mock.

No network, no credentials: every request goes to the in-process MockTrading through MockAlpacaTransport.
Quantities and prices are arbitrary TEST VALUES, not anyone's real terms.

Covers SMALL_ACCOUNT_CONTRACT broker duties: exact qty on the wire and in the book, QTY_PRECISION,
BELOW_MIN_NOTIONAL (buys only), fresh-account INSUFFICIENT_CASH / CASH_UNAVAILABLE, exact partial
fills and positions, reduce-only exits capped at the owned remainder (never rounded up, no $1 minimum),
a venue reject of a tiny reduction carried with its message and not retried, duplicate safety, and
whole-share mode staying whole-only (FRACTIONAL_NOT_ENABLED).

Run: /usr/bin/python3 -IB -m unittest discover -s <desk>/tests -p 'test_fractional_broker*'
"""
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from alpaca import LABEL_MOCK_LOCAL  # noqa: E402
from alpaca.broker import BOOK_FILE, AlpacaLiveBroker, AlpacaPaperBroker  # noqa: E402
from alpaca.mock import MockAlpacaTransport, MockTrading  # noqa: E402
from alpaca.state import AdapterState  # noqa: E402
from orders import qty as _qty  # noqa: E402
from orders.fake_broker import BrokerUncertain  # noqa: E402

D = Decimal


def posts(trading):
    return [c for c in trading.calls if c[0] == "POST"]


class FracCase(unittest.TestCase):
    FRACTIONAL = True

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="alpaca-frac-test-")
        self.trading = MockTrading(buying_power=1000.0, fractional=self.FRACTIONAL)
        self.transport = MockAlpacaTransport(self.trading)
        AdapterState(self.dir).enable(by="test")
        self.b = self.new_broker()
        self.trading.advance(100.0)
        self.b.step({"close": 100.0, "ts_close": "t1"})

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def new_broker(self, fractional=None):
        frac = self.FRACTIONAL if fractional is None else fractional
        self.b = AlpacaPaperBroker(self.transport, self.dir, LABEL_MOCK_LOCAL, AdapterState(self.dir),
                                   fractional=frac)
        return self.b

    def own(self, cid, qty, limit=101.0, price=100.0, partial=None):
        """Buy `qty` and fill it at `price` (optionally capped to `partial`). Returns the step fills."""
        r = self.b.submit(cid, "buy", qty, limit=limit, tag="entry")
        self.assertEqual(r["status"], "accepted", r)
        self.trading.partial_next = partial
        self.trading.advance(price)
        self.trading.partial_next = None
        return self.b.step({"close": price, "ts_close": "t-" + cid})


class TestQuantizedOrderCreation(FracCase):
    def test_exact_qty_text_on_the_wire_and_in_the_book(self):
        r = self.b.submit("e1", "buy", D("0.123456789"), limit=100.0, tag="entry")
        self.assertEqual(r["status"], "accepted", r)
        body = posts(self.trading)[-1][3]
        self.assertEqual(body["qty"], "0.123456789")
        self.assertEqual(body["type"], "limit")
        self.assertEqual(body["time_in_force"], "day")
        self.assertEqual(self.trading.orders[r["order_id"]]["qty"], D("0.123456789"))
        rec = self.b.book["orders"]["e1"]
        self.assertEqual(rec["qty"], D("0.123456789"))
        with open(os.path.join(self.dir, BOOK_FILE)) as fh:
            on_disk = json.load(fh)
        self.assertEqual(_qty.parse(on_disk["orders"]["e1"]["qty"]), D("0.123456789"))   # exact round trip

    def test_string_qty_is_parsed_exactly(self):
        r = self.b.submit("e1", "buy", "0.5", limit=100.0, tag="entry")
        self.assertEqual(r["status"], "accepted", r)
        self.assertEqual(posts(self.trading)[-1][3]["qty"], "0.5")

    def test_more_than_nine_decimals_is_qty_precision_and_sends_nothing(self):
        r = self.b.submit("e1", "buy", D("0.1234567891"), limit=100.0, tag="entry")
        self.assertEqual((r["status"], r["reason"]), ("rejected", "QTY_PRECISION"))
        self.assertEqual(posts(self.trading), [])
        self.assertNotIn("e1", self.b.book["orders"])

    def test_buy_below_one_dollar_is_refused_never_upsized(self):
        r = self.b.submit("e1", "buy", D("0.0099"), limit=100.0, tag="entry")
        self.assertEqual((r["status"], r["reason"]), ("rejected", "BELOW_MIN_NOTIONAL"))
        self.assertEqual(posts(self.trading), [])
        ok = self.b.submit("e2", "buy", D("0.01"), limit=100.0, tag="entry")
        self.assertEqual(ok["status"], "accepted", ok)
        self.assertEqual(posts(self.trading)[-1][3]["qty"], "0.01")

    def test_bad_qty_is_a_caller_error(self):
        for bad in (D("0"), D("-0.5"), "abc", None):
            with self.assertRaises(ValueError):
                self.b.submit("e1", "buy", bad, limit=100.0, tag="entry")
        self.assertEqual(posts(self.trading), [])

    def test_only_the_contract_shapes_are_sent(self):
        own = self.own("e1", D("0.5"))
        self.assertTrue(own)
        n = len(posts(self.trading))
        refused = [
            self.b.submit("x1", "buy", D("0.1"), limit=100.0, tag="entry", reduce_only=True),   # reduce buy
            self.b.submit("x2", "sell", D("0.1"), limit=99.0, tag="exit", reduce_only=True),    # sell limit
            self.b.submit("x3", "sell", D("0.1"), stop=95.0, tag="protective"),                 # not reduce
            self.b.submit("x4", "sell", D("0.1"), tag="exit"),                                  # not reduce
        ]
        for r in refused:
            self.assertEqual((r["status"], r["reason"]), ("rejected", "FRACTIONAL_ORDER_SHAPE"), r)
        self.assertEqual(len(posts(self.trading)), n)


class TestFreshAccountCash(FracCase):
    def test_cash_below_notional_is_insufficient_cash(self):
        self.trading.cash = 40.0
        r = self.b.submit("e1", "buy", D("0.5"), limit=100.0, tag="entry")
        self.assertEqual((r["status"], r["reason"]), ("rejected", "INSUFFICIENT_CASH"))
        self.assertEqual(posts(self.trading), [])

    def test_non_marginable_buying_power_is_used_when_smaller(self):
        self.trading.cash = 1000.0
        self.trading.non_marginable_buying_power = 40.0
        r = self.b.submit("e1", "buy", D("0.5"), limit=100.0, tag="entry")
        self.assertEqual((r["status"], r["reason"]), ("rejected", "INSUFFICIENT_CASH"))
        self.assertEqual(posts(self.trading), [])

    def test_working_buys_count_against_available(self):
        self.trading.cash = 80.0
        self.trading.non_marginable_buying_power = 80.0
        first = self.b.submit("e1", "buy", D("0.5"), limit=100.0, tag="entry")
        self.assertEqual(first["status"], "accepted", first)
        r = self.b.submit("e2", "buy", D("0.4"), limit=100.0, tag="entry")
        self.assertEqual((r["status"], r["reason"]), ("rejected", "INSUFFICIENT_CASH"))
        self.assertEqual(len(posts(self.trading)), 1)

    def test_missing_or_bad_or_unreadable_account_is_cash_unavailable(self):
        def attempt(cid):
            r = self.b.submit(cid, "buy", D("0.1"), limit=100.0, tag="entry")
            self.assertEqual((r["status"], r["reason"]), ("rejected", "CASH_UNAVAILABLE"), r)

        self.trading.account_omit = {"non_marginable_buying_power"}
        attempt("e1")
        self.trading.account_omit = set()
        self.trading.cash = "abc"
        attempt("e2")
        self.trading.cash = 1000.0
        self.trading.fault("GET", "5xx", path_prefix="/v2/account")
        attempt("e3")
        self.assertEqual(posts(self.trading), [])

    def test_reductions_skip_the_cash_check(self):
        self.own("e1", D("0.3"))
        self.trading.cash = 0.0
        self.trading.non_marginable_buying_power = 0.0
        r = self.b.submit("s1", "sell", D("0.3"), tag="exit", reduce_only=True)
        self.assertEqual(r["status"], "accepted", r)


class TestPartialFillsAndPositions(FracCase):
    def test_partial_fills_are_exact_and_the_position_matches(self):
        r = self.b.submit("e1", "buy", D("0.75"), limit=101.0, tag="entry")
        self.assertEqual(r["status"], "accepted", r)
        self.trading.partial_next = D("0.3")
        self.trading.advance(100.0)
        f1 = self.b.step({"close": 100.0, "ts_close": "t2"})
        self.assertEqual([(f["qty"], f["exec_id"].rsplit(":", 1)[1]) for f in f1], [(D("0.3"), "0.3")])
        pos = self.b.positions()["SPY"]
        self.assertEqual(pos["qty"], D("0.3"))
        self.assertTrue(pos["qty_is_fractional"])
        self.assertFalse(pos["fractional"])            # supported here: not an unsupported fraction
        self.trading.partial_next = None
        self.trading.advance(100.0)
        f2 = self.b.step({"close": 100.0, "ts_close": "t3"})
        self.assertEqual([(f["qty"], f["exec_id"].rsplit(":", 1)[1]) for f in f2], [(D("0.45"), "0.75")])
        self.assertEqual(self.b.positions()["SPY"]["qty"], D("0.75"))
        self.assertTrue(AdapterState(self.dir).enabled, AdapterState(self.dir).data)

    def test_restart_keeps_exact_book_quantities(self):
        self.own("e1", D("0.75"), partial=D("0.3"))
        self.new_broker()
        rec = self.b.book["orders"]["e1"]
        self.assertEqual((rec["qty"], rec["cum_qty"]), (D("0.75"), D("0.3")))
        self.assertTrue(all(isinstance(f["qty"], (int, Decimal)) for f in rec.get("fills", [])))
        self.trading.advance(100.0)
        f = self.b.step({"close": 100.0, "ts_close": "t9"})
        self.assertEqual([x["qty"] for x in f], [D("0.45")])     # the remainder, once
        self.assertEqual(self.b.step({"close": 100.0, "ts_close": "t10"}), [])


class TestSafeRiskReducingSells(FracCase):
    def test_protective_stop_covers_exactly_the_filled_quantity(self):
        self.own("e1", D("0.75"), partial=D("0.3"))
        r = self.b.submit("p1", "sell", D("0.3"), stop=95.0, tag="protective", reduce_only=True)
        self.assertEqual(r["status"], "accepted", r)
        body = posts(self.trading)[-1][3]
        self.assertEqual((body["qty"], body["type"], body["side"]), ("0.3", "stop", "sell"))

    def test_exit_is_capped_at_the_owned_remainder_never_rounded_up(self):
        self.own("e1", D("0.3"))
        r = self.b.submit("x1", "sell", 1, tag="exit", reduce_only=True)
        self.assertEqual(r["status"], "accepted", r)
        self.assertEqual(posts(self.trading)[-1][3]["qty"], "0.3")
        self.trading.advance(100.0)
        self.b.step({"close": 100.0, "ts_close": "t5"})
        self.assertEqual(self.b.positions()["SPY"]["qty"], 0)       # flat, never short

    def test_tiny_reduction_has_no_dollar_minimum(self):
        self.own("e1", D("0.02"))
        r = self.b.submit("x1", "sell", D("0.005"), tag="exit", reduce_only=True)
        self.assertEqual(r["status"], "accepted", r)
        self.assertEqual(posts(self.trading)[-1][3]["qty"], "0.005")

    def test_venue_reject_of_tiny_reduction_carries_message_and_is_not_retried(self):
        self.own("e1", D("0.02"))
        self.trading.reject_sell_below = 1.0
        n = len(posts(self.trading))
        r = self.b.submit("x1", "sell", D("0.005"), tag="exit", reduce_only=True)
        self.assertEqual(r["status"], "rejected")
        self.assertEqual(r["http_status"], 422)
        self.assertIn("too small", r["venue_message"])
        self.assertEqual(len(posts(self.trading)), n + 1)          # one POST, no resize retry
        again = self.b.submit("x1", "sell", D("0.005"), tag="exit", reduce_only=True)
        self.assertEqual(again["reason"], "DUPLICATE_CLIENT_ORDER_ID")
        self.assertEqual(len(posts(self.trading)), n + 1)


class TestNoDuplicateSubmissions(FracCase):
    def test_same_client_id_is_never_sent_twice(self):
        self.assertEqual(self.b.submit("e1", "buy", D("0.5"), limit=100.0, tag="entry")["status"], "accepted")
        r = self.b.submit("e1", "buy", D("0.5"), limit=100.0, tag="entry")
        self.assertEqual(r["reason"], "DUPLICATE_CLIENT_ORDER_ID")
        self.assertEqual(len(posts(self.trading)), 1)

    def test_unresolved_submit_is_not_reposted_and_is_adopted_exactly(self):
        self.trading.fault("POST", "lost_ack")
        with self.assertRaises(BrokerUncertain):
            self.b.submit("e1", "buy", D("0.25"), limit=100.0, tag="entry")
        r = self.b.submit("e1", "buy", D("0.25"), limit=100.0, tag="entry")
        self.assertEqual(r["reason"], "SUBMIT_UNRESOLVED")
        self.assertEqual(len(posts(self.trading)), 1)
        found = self.b.query("e1")
        self.assertIsNotNone(found)
        self.assertEqual(self.b.book["orders"]["e1"]["qty"], D("0.25"))
        self.assertEqual(len(self.trading.orders), 1)

    def test_venue_unique_answer_is_adopted_by_query(self):
        self.assertEqual(self.b.submit("e1", "buy", D("0.25"), limit=100.0, tag="entry")["status"], "accepted")
        del self.b.book["orders"]["e1"]                           # the desk lost its record of the send
        r = self.b.submit("e1", "buy", D("0.25"), limit=100.0, tag="entry")
        self.assertEqual(r["reason"], "DUPLICATE_CLIENT_ORDER_ID")
        self.assertTrue(r["order_id"])
        self.assertEqual(len(self.trading.orders), 1)
        self.assertEqual(self.b.book["orders"]["e1"]["qty"], D("0.25"))


class TestSnapshotsAndConstruction(FracCase):
    def test_snapshot_is_json_after_a_fractional_refusal(self):
        self.b.exec_caps["per_trade_notional"] = 10.0              # TEST VALUE below a $50 order
        r = self.b.submit("e1", "buy", D("0.5"), limit=100.0, tag="entry")
        self.assertEqual(r["status"], "rejected", r)
        self.assertEqual(posts(self.trading), [])
        snap = json.loads(json.dumps(self.b.snapshot()))
        self.assertEqual(_qty.parse(snap["exec_refusals"][-1]["qty"]), D("0.5"))

    def test_fractional_flag_must_be_a_bool(self):
        with self.assertRaises(ValueError):
            self.new_broker(fractional="yes")
        sig = inspect.signature(AlpacaLiveBroker.__init__)
        self.assertIn("fractional", sig.parameters)
        self.assertIs(sig.parameters["fractional"].default, False)

    def test_mock_refuses_ten_decimals_directly(self):
        st, payload = self.transport.request("POST", "trading", "/v2/orders", None, {
            "symbol": "SPY", "qty": "0.1234567891", "side": "buy", "type": "limit", "limit_price": "100",
            "time_in_force": "day", "client_order_id": "raw1"})
        self.assertEqual(st, 422)
        self.assertIn("9 decimal", payload["message"])


class TestWholeModeStaysWhole(FracCase):
    FRACTIONAL = False

    def test_exact_fraction_is_refused_by_reason_sending_nothing(self):
        r = self.b.submit("e1", "buy", D("0.5"), limit=100.0, tag="entry")
        self.assertEqual((r["status"], r["reason"]), ("rejected", "FRACTIONAL_NOT_ENABLED"))
        self.assertEqual(posts(self.trading), [])

    def test_whole_decimal_and_int_still_trade(self):
        self.assertEqual(self.b.submit("e1", "buy", 1, limit=100.0, tag="entry")["status"], "accepted")
        self.assertEqual(posts(self.trading)[-1][3]["qty"], "1")

    def test_fractional_venue_position_is_an_integrity_stop(self):
        frac_venue = MockTrading(buying_power=1000.0, fractional=True)
        frac_venue.set_position(D("0.5"), 100.0)
        self.transport = MockAlpacaTransport(frac_venue)
        self.new_broker(fractional=False)
        pos = self.b.positions()["SPY"]
        self.assertTrue(pos["fractional"])
        self.assertFalse(AdapterState(self.dir).enabled)
        self.assertIn("FRACTIONAL_QTY", AdapterState(self.dir).data["disabled_reason"])


if __name__ == "__main__":
    unittest.main()
