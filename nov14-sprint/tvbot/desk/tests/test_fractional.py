"""Fractional share sizing and the daily-entry control.

Every number here is an arbitrary synthetic test value, not anyone's sizing or limits.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal

DESK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK_DIR not in sys.path:
    sys.path.insert(0, DESK_DIR)

from alpaca import sizing  # noqa: E402
from orders import qty as Q  # noqa: E402

PHRASE = sizing.CONFIRM_PHRASE
# Synthetic fractional example: arbitrary values chosen only so the arithmetic is easy to read.
FRAC = {"fixed_shares": 0.25, "max_loss_per_trade": 7.0, "daily_loss": 9.0,
        "per_trade_notional": 300.0, "gross_exposure": 300.0, "max_daily_entries": 2}
WHOLE = {"fixed_shares": 3, "max_loss_per_trade": 12.0, "daily_loss": 40.0,
         "per_trade_notional": 1500.0, "gross_exposure": 1600.0}


class TestQty(unittest.TestCase):
    def test_parse_whole_stays_int(self):
        for v in (1, "1", 1.0, "2.000", Decimal("7")):
            q = Q.parse(v)
            self.assertIs(type(q), int)
        self.assertEqual(Q.text(Q.parse("2.000")), "2")

    def test_parse_fraction_exact(self):
        self.assertEqual(Q.parse(0.1), Decimal("0.1"))
        self.assertEqual(Q.parse("0.123456789"), Decimal("0.123456789"))
        self.assertEqual(Q.text(Q.parse("1.50")), "1.5")
        self.assertEqual(Q.text(Q.parse("0.000000001")), "0.000000001")   # never exponent form

    def test_parse_refusals(self):
        for bad in (True, None, "", "x", float("nan"), float("inf"), "-1", 0, -0.5,
                    "0.0000000001", "1.0000000001", "1234567.123456789"):
            with self.assertRaises(Q.QtyError, msg=repr(bad)):
                Q.parse(bad)

    def test_json_round_trip_exact(self):
        for s in ("0.1", "0.123456789", "12.5", "999999.123456789"):
            q = Q.parse(s)
            back = Q.parse(json.loads(json.dumps(Q.to_json(q))))
            self.assertEqual(back, q, s)
        self.assertEqual(Q.to_json(3), 3)
        self.assertEqual(json.dumps({"q": Q.parse("0.5")}, default=Q.json_default), '{"q": 0.5}')

    def test_signed_and_norm(self):
        self.assertEqual(Q.parse_signed("-0.25"), Decimal("-0.25"))
        self.assertEqual(Q.parse_signed(0), 0)
        self.assertIs(type(Q.norm(Decimal("0.5") + Decimal("0.5"))), int)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="frac-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def approve(self, reason="synthetic test"):
        w = sizing.worksheet(self.dir)
        return sizing.approve(self.dir, PHRASE, reason, reviewed_draft_hash=w["draft_hash"],
                              prior_approved_hash=w["approved_hash"])


class TestFractionalWorksheet(Base):
    def test_fraction_needs_max_daily_entries(self):
        vals = dict(FRAC)
        vals.pop("max_daily_entries")
        sizing.save_draft(self.dir, vals)                # a draft may be incomplete
        with self.assertRaises(sizing.LimitsError) as cm:
            self.approve()
        self.assertIn("max_daily_entries is required for fractional shares", str(cm.exception))
        self.assertIsNone(sizing.read_approved(self.dir))

    def test_fraction_approves_and_loads_exactly(self):
        sizing.save_draft(self.dir, FRAC)
        snap = self.approve()
        loaded = sizing.load_limits(state_dir=self.dir)
        self.assertEqual(Q.parse(loaded["values"]["fixed_shares"]), Decimal("0.25"))
        self.assertEqual(loaded["values"]["max_daily_entries"], 2)
        lim = sizing.as_session_limits(loaded)
        self.assertEqual(lim["max_daily_entries"], 2)
        self.assertEqual(snap["values_hash"], sizing.content_hash(FRAC))

    def test_bad_daily_entries_and_precision_refused(self):
        for bad in ({"max_daily_entries": 0}, {"max_daily_entries": 1.5}, {"max_daily_entries": "x"},
                    {"max_daily_entries": True}, {"fixed_shares": "0.1234567891"}):
            with self.assertRaises(sizing.LimitsError, msg=repr(bad)):
                sizing.save_draft(self.dir, bad)

    def test_whole_share_records_hash_and_shape_unchanged(self):
        # A record without the optional field hashes exactly as the five-field hash always did.
        legacy = {k: WHOLE.get(k) for k in sizing.FIELDS}
        blob = json.dumps(legacy, sort_keys=True, separators=(",", ":"))
        import hashlib
        self.assertEqual(sizing.content_hash(WHOLE), hashlib.sha256(blob.encode()).hexdigest())
        clean, problems = sizing.validate(WHOLE)
        self.assertEqual(problems, [])
        self.assertEqual(set(clean), set(sizing.FIELDS))
        sizing.save_draft(self.dir, WHOLE)
        self.approve()
        lim = sizing.as_session_limits(sizing.load_limits(state_dir=self.dir))
        self.assertNotIn("max_daily_entries", lim)      # session config binding stays identical

    def test_whole_shares_may_set_daily_entries(self):
        vals = dict(WHOLE, max_daily_entries=4)
        sizing.save_draft(self.dir, vals)
        self.approve()
        self.assertEqual(sizing.load_limits(state_dir=self.dir)["values"]["max_daily_entries"], 4)

    def test_effects_fraction_minimum_check(self):
        below = sizing.effects(FRAC, ref_price="3.00", stop_distance="0.10")   # 0.25 x 3.00 = 0.75
        row = [c for c in below["checks"] if c["cap"] == "min_fractional_buy"][0]
        self.assertFalse(row["ok"])
        self.assertIn("never rounds it up", row["reason"])
        at = sizing.effects(FRAC, ref_price="4.00", stop_distance="0.10")      # exactly 1.00
        self.assertTrue([c for c in at["checks"] if c["cap"] == "min_fractional_buy"][0]["ok"])
        self.assertEqual(at["notional"], 1.0)
        whole = sizing.effects(WHOLE, ref_price="4.00", stop_distance="0.10")
        self.assertNotIn("min_fractional_buy", {c["cap"] for c in whole["checks"]})

    def test_worksheet_lists_optional_field(self):
        w = sizing.worksheet(self.dir)
        self.assertIn("max_daily_entries", w["fields"])
        self.assertEqual(w["required_fields"], list(sizing.FIELDS))
        self.assertIn("max_daily_entries", w["help"])



# ---------------------------------------------------------------- order manager (offline, injected fakes)
from orders.calendar import SessionCalendar, parse_ts  # noqa: E402
from orders.fake_broker import FakeBroker, BrokerOutage  # noqa: E402
from orders.manager import OrderManager  # noqa: E402

FIXDIR = os.path.join(os.path.dirname(DESK_DIR), "fixtures")


def _bars(path):
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                if rec.get("type") != "manifest":
                    out.append(rec)
    return out


BARS = _bars(os.path.join(FIXDIR, "normal_bars.jsonl"))
# Arbitrary TEST VALUES for the manager (same scale as test_orders_manager), not anyone's limits.
MLIM = {"per_trade_notional": 2000, "max_loss_per_trade": 10.0, "daily_loss": 30.0, "gross_exposure": 2000,
        "label": "TEST VALUES"}
FAR = "2026-06-30T00:00:00Z"


class CountingFake(FakeBroker):
    """Whole-share fake broker that also answers the durable daily-entry query."""

    def __init__(self, *a, **kw):
        FakeBroker.__init__(self, *a, **kw)
        self.count_mode = "ok"        # ok | raise | incomplete
        self.outside = []             # buys placed by another copy of the desk (another state dir)
        self.count_calls = 0

    def entry_buys_since(self, after):
        self.count_calls += 1
        if self.count_mode == "raise":
            raise BrokerOutage("simulated count read failure")
        rows = [{"client_id": o["client_id"], "symbol": o["symbol"], "side": o["side"],
                 "submitted_at": o["submit_ts"], "status": o["status"]}
                for o in self._orders.values() if o["side"] == "buy"]
        return {"complete": self.count_mode != "incomplete", "orders": rows + list(self.outside)}


class FracFake(CountingFake):
    """CountingFake with exact fractional quantities, a funding read and an optional fill cap."""
    fractional = True

    def __init__(self, *a, **kw):
        CountingFake.__init__(self, *a, **kw)
        self.cash = {"cash": "500.00", "non_marginable_buying_power": "500.00"}
        self.fill_cap = None

    def funding(self):
        if self.cash is None:
            raise BrokerOutage("simulated account read failure")
        return dict(self.cash)

    def _new_order(self, client_id, side, qty, limit, stop, tag, reduce_only=False):
        o = FakeBroker._new_order(self, client_id, side, 1, limit, stop, tag, reduce_only=reduce_only)
        o["qty"] = Q.parse(qty)
        return o

    def submit(self, client_id, side, qty, limit=None, stop=None, tag=None, reduce_only=False):
        self._gate()
        qty = Q.parse(qty)
        if client_id in self._orders:
            return {"status": "rejected", "client_id": client_id, "reason": "DUPLICATE_CLIENT_ORDER_ID",
                    "order_id": self._orders[client_id]["order_id"], "simulated": True}
        order = self._new_order(client_id, side, qty, limit, stop, tag, reduce_only=reduce_only)
        self._orders[client_id] = order
        self._emit({"type": "ack", "client_id": client_id, "order_id": order["order_id"]})
        return {"status": "accepted", "client_id": client_id, "order_id": order["order_id"], "simulated": True}

    def _apply_fill(self, order, qty, base_price, event_ts=None):
        qty = Q.dec(qty)
        if self.fill_cap is not None:
            qty = min(qty, self.fill_cap)
        qty = Q.norm(qty)
        self._exec_seq += 1
        price = self._cost_adjust(order["side"], float(base_price))
        ts = self._ts()
        fill = {"type": "fill", "exec_id": "EX-%d-%d" % (self.seed, self._exec_seq),
                "client_id": order["client_id"], "order_id": order["order_id"], "side": order["side"],
                "qty": qty, "price": price, "fee": 0.0, "ts": ts, "event_ts": event_ts or ts, "report_ts": ts,
                "mock": True, "simulated": True}
        prev = order["filled_qty"]
        order["filled_qty"] = Q.norm(Q.dec(prev) + Q.dec(qty))
        order["avg_fill_price"] = price
        order["fills"].append(dict(fill))
        self._update_position(qty if order["side"] == "buy" else -qty, price)
        if order["filled_qty"] >= order["qty"]:
            order["status"] = "filled"
        self._emit(fill)
        return fill

    def _update_position(self, signed, price):
        q0 = self._pos_qty
        q1 = Q.norm(Q.dec(q0) + Q.dec(signed))
        if q0 == 0 or (q0 > 0) == (signed > 0):
            self._pos_avg = (self._pos_avg * float(abs(q0)) + price * float(abs(signed))) / float(abs(q1)) \
                if q1 else 0.0
        elif q1 == 0:
            self._pos_avg = 0.0
        self._pos_qty = q1


class MgrCase(unittest.TestCase):
    broker_cls = CountingFake
    max_daily = 1

    def setUp(self):
        self.cal = SessionCalendar.fixture_profile()
        self.dirs = [tempfile.mkdtemp(prefix="frac-mgr-")]
        self.b = self.broker_cls(seed=7)
        self.mgrs = []
        self.m = self.new_manager()
        self.i = 0

    def tearDown(self):
        for m in self.mgrs:
            m.close()
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def limits(self):
        lim = dict(MLIM)
        if self.max_daily is not None:
            lim["max_daily_entries"] = self.max_daily
        return lim

    def new_manager(self, state_dir=None, broker=None):
        m = OrderManager(state_dir or self.dirs[0], broker or self.b, self.limits(), calendar=self.cal)
        self.mgrs.append(m)
        return m

    def restart(self):
        self.m.close()
        self.m = self.new_manager()

    def bar(self):
        bar = BARS[self.i]
        self.i += 1
        self.b.step(bar)
        return self.m.on_bar(bar)

    def start(self):
        self.bar()
        r = self.m.arm("S1", expires_utc=FAR)
        self.assertTrue(r["ok"], r)

    def buy(self, did, qty, **kw):
        intent = {"decision_id": did, "side": "buy", "qty": qty, "ref_price": self.m.mark}
        intent.update(kw)
        if "invalidation" not in kw:
            intent["invalidation"] = (kw.get("limit") or self.m.mark) - 0.5
        return self.m.submit_intent(intent)

    def sell(self, did, kind, qty, **kw):
        intent = {"decision_id": did, "kind": kind, "side": "sell", "qty": qty}
        intent.update(kw)
        return self.m.submit_intent(intent)

    def st(self, iid):
        it = self.m.intents[iid]
        return it["status"], it.get("reason")

    def sent(self):
        return self.b.list_orders()["orders"]


class TestDailyEntriesWhole(MgrCase):
    def test_second_entry_same_day_refused_nothing_sent(self):
        self.start()
        a = self.buy("d1", 1, limit=self.m.mark - 5.0)
        self.assertEqual(self.st(a)[0], "acked")
        b = self.buy("d2", 1, limit=self.m.mark - 5.0)
        self.assertEqual(self.st(b), ("rejected", "DAILY_ENTRY_LIMIT"))
        self.assertEqual(len(self.sent()), 1)
        self.assertEqual(self.m.state()["daily_entries"]["used"], 1)

    def test_count_survives_restart_and_duplicates_count_once(self):
        self.max_daily = 2
        self.restart()
        self.start()
        a = self.buy("same", 1, limit=self.m.mark - 5.0)
        self.assertEqual(self.buy("same", 1, limit=self.m.mark - 5.0), a)
        self.restart()
        self.bar()
        self.assertEqual(self.st(self.buy("other", 1, limit=self.m.mark - 5.0))[0], "acked")
        self.restart()
        self.bar()
        third = self.buy("third", 1, limit=self.m.mark - 5.0)
        self.assertEqual(self.st(third), ("rejected", "DAILY_ENTRY_LIMIT"))
        self.assertEqual(len(self.sent()), 2)

    def test_attempt_persisted_before_send_counts_when_not_placed(self):
        self.start()
        self.b.set_outage(True)
        a = self.buy("d1", 1, limit=self.m.mark - 5.0)
        self.b.set_outage(False)
        self.assertEqual(len(self.sent()), 0)
        self.assertEqual(self.m.intents[a].get("entry_attempt_day"), self.m._day_key(None))
        self.assertEqual(len(self.m._entries_today()), 1)
        self.restart()
        self.bar()                                      # the fixture clock, not the wall clock
        self.assertEqual(len(self.m._entries_today()), 1)
        self.assertEqual(self.st(self.buy("d2", 1, limit=self.m.mark - 5.0))[1], "DAILY_ENTRY_LIMIT")

    def test_exits_never_read_the_count(self):
        self.max_daily = 1
        self.restart()
        self.start()
        iid = self.buy("long", 10)
        self.bar()
        self.assertEqual(self.m.pos_qty, 10, self.st(iid))
        calls = self.b.count_calls
        self.b.count_mode = "raise"
        p = self.sell("prot", "protective", 10, stop=self.m.mark - 1.0)
        self.assertEqual(self.st(p)[0], "acked")
        self.assertEqual(self.st(self.buy("more", 1))[1], "ENTRY_COUNT_UNVERIFIED")
        r = self.m.stop_and_close()
        self.assertTrue(r["stopped"], r)
        self.assertEqual(r["close"]["state"], "closing", r)
        for _ in range(4):
            if self.m.pos_qty == 0:
                break
            self.bar()
        self.assertEqual(self.m.pos_qty, 0)
        self.assertTrue(self.m.connected)
        self.assertEqual(self.b.count_calls, calls + 1)       # only the refused entry asked

    def test_fresh_state_dir_same_day_sees_other_copy(self):
        self.start()
        today = self.m.now().strftime("%Y-%m-%dT%H:%M:%S.123456789Z")
        other = CountingFake(seed=8)
        other.outside = [{"client_id": "other-copy-1", "symbol": "SYNTH", "side": "buy",
                          "submitted_at": today, "status": "filled"}]
        self.dirs.append(tempfile.mkdtemp(prefix="frac-mgr-copy-"))
        self.m = self.new_manager(state_dir=self.dirs[-1], broker=other)
        self.b = other
        self.bar()
        self.assertTrue(self.m.arm("S2", expires_utc=FAR)["ok"])
        x = self.buy("fresh", 1, limit=self.m.mark - 5.0)
        self.assertEqual(self.st(x), ("rejected", "DAILY_ENTRY_LIMIT"))
        self.assertEqual(len(self.sent()), 0)
        # Yesterday's buy and another symbol's buy do not count.
        other.outside = [{"client_id": "y", "symbol": "SYNTH", "side": "buy", "submitted_at": "2000-01-03T15:00:00Z"},
                         {"client_id": "z", "symbol": "OTHER", "side": "buy", "submitted_at": today}]
        y = self.buy("fresh2", 1, limit=self.m.mark - 5.0)
        self.assertEqual(self.st(y)[0], "acked")

    def test_unverifiable_count_holds_entry(self):
        self.start()
        for mode in ("raise", "incomplete"):
            self.b.count_mode = mode
            x = self.buy("u-" + mode, 1, limit=self.m.mark - 5.0)
            self.assertEqual(self.st(x), ("rejected", "ENTRY_COUNT_UNVERIFIED"))
            self.assertTrue(self.m.connected)
        self.assertEqual(len(self.sent()), 0)
        self.assertEqual(len(self.m._entries_today()), 0)


class TestDailyEntriesLocalOnly(MgrCase):
    broker_cls = FakeBroker

    def test_previous_day_attempt_does_not_count(self):
        self.start()
        a = self.buy("d1", 1, limit=self.m.mark - 5.0)
        self.assertEqual(self.st(self.buy("d2", 1, limit=self.m.mark - 5.0))[1], "DAILY_ENTRY_LIMIT")
        self.m.intents[a]["entry_attempt_day"] = "2000-01-03"
        self.assertEqual(self.st(self.buy("d3", 1, limit=self.m.mark - 5.0))[0], "acked")

    def test_no_daily_field_no_count_and_whole_desk_refuses_fraction(self):
        self.max_daily = None
        self.restart()
        self.start()
        for k in range(3):
            self.assertEqual(self.st(self.buy("n%d" % k, 1, limit=self.m.mark - 5.0))[0], "acked")
        self.assertFalse(self.m.fractional)
        with self.assertRaises(ValueError) as cm:
            self.buy("half", 0.5)
        self.assertIn("FRACTIONAL_NOT_ENABLED", str(cm.exception))


class TestFractionalManager(MgrCase):
    broker_cls = FracFake
    max_daily = 2

    def test_partial_fill_protective_and_close_exact(self):
        self.start()
        self.assertTrue(self.m.fractional)
        self.b.fill_cap = Decimal("0.02")
        iid = self.buy("f", "0.05")
        self.bar()
        it = self.m.intents[iid]
        self.assertEqual(Q.dec(it["filled_qty"]), Decimal("0.02"))
        self.assertEqual(self.m.pos_qty, Decimal("0.02"))
        self.assertEqual(self.m._remaining(it), Decimal("0.03"))
        p = self.sell("prot", "protective", self.m.pos_qty, stop=self.m.mark - 1.0)
        self.assertEqual(self.st(p)[0], "acked")
        prot = [o for o in self.sent() if o["client_id"] == self.m.intents[p]["client_id"]][0]
        self.assertEqual(prot["qty"], Decimal("0.02"))
        self.b.fill_cap = None
        self.bar()
        self.assertEqual(self.m.pos_qty, Decimal("0.05"))
        r = self.m.stop_and_close()
        self.assertEqual(Q.dec(r["close"]["qty"]), Decimal("0.05"), r)
        for _ in range(4):
            if self.m.pos_qty == 0:
                break
            self.bar()
        self.assertEqual(self.m.pos_qty, 0)
        sells = [o for o in self.sent() if o["side"] == "sell" and o["stop"] is None]
        self.assertTrue(sells and all(Q.is_fractional(Q.dec(o["qty"])) or o["qty"] == 0 for o in sells), sells)
        json.dumps(self.m.state())                      # views stay JSON-serializable

    def test_below_minimum_never_upsized_or_counted(self):
        self.start()
        lim = 50.0                                      # far under the fixture mark: never fills here
        x = self.buy("small", "0.019", limit=lim, invalidation=lim - 0.5)     # 0.95
        self.assertEqual(self.st(x), ("rejected", "BELOW_MIN_NOTIONAL"))
        self.assertEqual(Q.dec(self.m.intents[x]["qty"]), Decimal("0.019"))
        y = self.buy("at", "0.02", limit=lim, invalidation=lim - 0.5)         # exactly 1.00
        self.assertEqual(self.st(y)[0], "acked")
        self.assertEqual([o["qty"] for o in self.sent()], [Decimal("0.02")])
        self.assertEqual(len(self.m._entries_today()), 1)

    def test_cash_and_working_buys(self):
        self.start()
        lim = 50.0
        self.b.cash = None
        self.assertEqual(self.st(self.buy("c0", "0.02", limit=lim, invalidation=lim - 0.5))[1], "CASH_UNAVAILABLE")
        self.b.cash = {"cash": "nan", "non_marginable_buying_power": "9"}
        self.assertEqual(self.st(self.buy("c1", "0.02", limit=lim, invalidation=lim - 0.5))[1], "CASH_UNAVAILABLE")
        self.b.cash = {"cash": "1.50", "non_marginable_buying_power": "0.90"}
        self.assertEqual(self.st(self.buy("c2", "0.02", limit=lim, invalidation=lim - 0.5))[1], "INSUFFICIENT_CASH")
        self.assertEqual(len(self.m._entries_today()), 0)
        self.b.cash = {"cash": "1.50", "non_marginable_buying_power": "1.50"}
        self.assertEqual(self.st(self.buy("c3", "0.02", limit=lim, invalidation=lim - 0.5))[0], "acked")
        self.assertEqual(self.st(self.buy("c4", "0.02", limit=lim, invalidation=lim - 0.5))[1], "INSUFFICIENT_CASH")
        self.assertEqual(len(self.sent()), 1)

    def test_reduction_below_one_dollar_still_sent_and_no_fractional_short(self):
        self.start()
        self.b.fill_cap = Decimal("0.001")
        self.buy("f", "0.05")
        self.bar()
        self.assertEqual(self.m.pos_qty, Decimal("0.001"))
        e = self.sell("trim", "exit", "0.001")
        self.assertEqual(self.st(e)[0], "acked")
        self.assertIn(Decimal("0.001"), [o["qty"] for o in self.sent() if o["side"] == "sell"])
        with self.assertRaises(ValueError):
            self.buy("bad", "0.0000000001")
        s = self.m.submit_intent({"decision_id": "short", "side": "sell", "qty": "0.05",
                                  "ref_price": self.m.mark, "invalidation": self.m.mark + 0.5})
        self.assertEqual(self.st(s)[0], "rejected")


class TestNineDigitDayKey(unittest.TestCase):
    def test_nine_digit_fraction_keeps_its_day(self):
        cal = SessionCalendar.fixture_profile()
        self.assertEqual(parse_ts("2026-03-02T23:59:59.999999999Z"), parse_ts("2026-03-02T23:59:59.999999Z"))
        self.assertEqual(parse_ts("2026-03-02T14:30:00.5Z"), parse_ts("2026-03-02T14:30:00.500000Z"))
        d = tempfile.mkdtemp(prefix="frac-day-")
        try:
            m = OrderManager(d, FakeBroker(seed=1), MLIM, calendar=cal)
            try:
                raw = "2026-03-02T15:00:00.123456789Z"
                self.assertEqual(m._day_key(raw), cal.local_date(parse_ts("2026-03-02T15:00:00Z")).isoformat())
                self.assertNotEqual(m._day_key(raw), m._day_key("2000-01-03T15:00:00Z"))
            finally:
                m.close()
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_dec_of_float_is_exact(self):
        self.assertEqual(Q.dec(0.25), Decimal("0.25"))
        self.assertEqual(Q.dec("0.1"), Decimal("0.1"))
        self.assertEqual(Q.dec(3), Decimal(3))


if __name__ == "__main__":
    unittest.main()
