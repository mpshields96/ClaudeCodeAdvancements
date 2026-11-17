"""Next-day PAPER start after an operator-run PAPER trial, and the exact private registration
(alpaca/registration.py) of the desk-placed PAPER orders the broker book does not hold.

Every id, price and quantity here is fictitious. The timestamps reproduce one shape only: a buy and a
sell of 3.6 shares filled after 8 pm New York time on a Monday (so they belong to Tuesday's trade
date), one zero-share cancel in between, and Alpaca's quirk where an order's final "fill" activity
carries an earlier transaction time than its "partial_fill". No network, no credentials, no orders.
Run: /usr/bin/python3 -I -B -m unittest discover -s <desk>/tests -p 'test_paper_registration*'
"""
import datetime as _dt
import json
import os
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock as _mock

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

import alpaca.broker as _broker_mod  # noqa: E402
from alpaca import LABEL_MOCK_LOCAL  # noqa: E402
from alpaca import registration as R  # noqa: E402
from alpaca.broker import AlpacaLiveBroker, AlpacaPaperBroker  # noqa: E402
from alpaca.mock import MockAlpacaTransport, MockTrading  # noqa: E402
from alpaca.state import AdapterState  # noqa: E402

TUE_OPEN = "2026-11-17T14:30:00Z"    # Tuesday 9:30 am New York: same trade date as the fills
TUE_LATE = "2026-11-18T00:30:00Z"    # Tuesday 7:30 pm New York: still the same trade date
WED_EARLY = "2026-11-18T06:30:00Z"   # Wednesday 1:30 am New York: the next trade date


def _utc(s):
    return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)


def _at(now):
    return _mock.patch.object(_broker_mod, "_utcnow_dt", lambda: _utc(now))


class Desk(object):
    """One fresh PAPER broker on the mock venue, with the trial's three foreign orders placed."""

    def __init__(self, test):
        self.dir = tempfile.mkdtemp(prefix="paper-registration-test-")
        test.addCleanup(shutil.rmtree, self.dir, True)
        self.trading = MockTrading()
        self.transport = MockAlpacaTransport(self.trading)
        AdapterState(self.dir).enable(by="test")
        self.b = self.new_broker()
        self.b.book["created_utc"] = "2026-11-14T00:00:00Z"
        self.b._save()

    def new_broker(self):
        self.b = AlpacaPaperBroker(self.transport, self.dir, LABEL_MOCK_LOCAL, AdapterState(self.dir))
        return self.b

    def order(self, cid, side, status, filled, submitted, done, avg=None, qty="3.6"):
        oid = self.trading.add_foreign_order(client_order_id=cid, side=side, status=status)
        row = self.trading.orders[oid]
        row.update(qty=Decimal(qty), filled_qty=Decimal(filled), submitted_at=submitted, created_at=submitted,
                   updated_at=done)
        if status == "filled":
            row.update(filled_at=done, filled_avg_price=avg)
        elif status == "canceled":
            row["canceled_at"] = done
        return oid

    def trial(self):
        """The fictitious trial: buy 3.6 filled, a zero-share cancel, sell 3.6 filled (flat)."""
        self.buy = self.order("reg-test-buy-1", "buy", "filled", "3.6", "2026-11-17T04:14:20Z",
                              "2026-11-17T04:14:27Z", avg=500.10)
        self.cancel = self.order("reg-test-cancel-1", "buy", "canceled", "0", "2026-11-17T04:23:40Z",
                                 "2026-11-17T04:23:48Z")
        self.sell = self.order("reg-test-sell-1", "sell", "filled", "3.6", "2026-11-17T04:45:30Z",
                               "2026-11-17T04:45:42Z", avg=500.05)
        for oid, t in ((self.buy, "2026-11-17T04:14:27"), (self.sell, "2026-11-17T04:45:42")):
            self.trading.add_fill_activity(oid, "2", "3.6", "0", "fill", t + ".100Z")          # final, earlier
            self.trading.add_fill_activity(oid, "1.6", "1.6", "2", "partial_fill", t + ".400Z")
        return self

    def rows(self, ids=None):
        out = [self.trading._out(r) for r in self.trading.orders.values()]
        return [r for r in out if ids is None or r["id"] in ids]

    def register(self, doc=None, mode=0o600, mutate=None):
        doc = doc if doc is not None else R.build(self.rows())
        if mutate:
            mutate(doc)
        p = R.path(self.dir)
        with open(p, "w") as fh:
            json.dump(doc, fh)
        os.chmod(p, mode)
        return p

    def listing(self, now):
        with _at(now):
            return self.b.list_orders()

    def enabled(self):
        return AdapterState(self.dir).enabled

    def codes(self):
        return [e["code"] for e in self.b.book["integrity"]]

    def notes(self, code):
        return [e["detail"] for e in self.b.book["integrity"] if e["code"] == code]

    def calls(self, path):
        return [c for c in self.trading.calls if c[1] == path]


class NextDayWithoutRegistrationTests(unittest.TestCase):
    """The existing rule alone: what tonight's shape does to a Tuesday start."""

    def test_overnight_trial_fills_lock_a_tuesday_start(self):
        d = Desk(self).trial()
        d.listing(TUE_OPEN)
        self.assertFalse(d.enabled())
        self.assertIn("FOREIGN_ORDER", d.codes())

    def test_overnight_trial_fills_still_lock_tuesday_evening(self):
        d = Desk(self).trial()
        d.listing(TUE_LATE)
        self.assertFalse(d.enabled())

    def test_next_trade_date_start_is_unlocked(self):
        d = Desk(self).trial()
        d.listing(WED_EARLY)
        self.assertTrue(d.enabled())
        self.assertNotIn("FOREIGN_ORDER", d.codes())
        self.assertEqual(len(d.notes("FOREIGN_ORDER_SETTLED")), 3)

    def test_zero_share_cancel_alone_never_locks(self):
        d = Desk(self)
        d.order("reg-test-cancel-1", "buy", "canceled", "0", "2026-11-17T04:23:40Z", "2026-11-17T04:23:48Z")
        d.listing(TUE_OPEN)
        self.assertTrue(d.enabled())

    def test_same_day_unknown_filled_row_locks(self):
        d = Desk(self)
        d.order("reg-test-unknown-1", "buy", "filled", "1", "2026-11-17T15:00:00Z", "2026-11-17T15:00:05Z",
                avg=500.0, qty="1")
        d.listing(TUE_LATE)
        self.assertFalse(d.enabled())

    def test_working_row_locks_even_on_a_later_date(self):
        d = Desk(self)
        oid = d.trading.add_foreign_order(client_order_id="reg-test-working-1", status="new")
        d.trading.orders[oid].update(submitted_at="2026-11-16T15:00:00Z", created_at="2026-11-16T15:00:00Z")
        d.listing(WED_EARLY)
        self.assertFalse(d.enabled())

    def test_partially_filled_canceled_row_locks_on_its_own_trade_date(self):
        d = Desk(self)
        d.order("reg-test-partial-1", "buy", "canceled", "1.6", "2026-11-17T04:14:20Z", "2026-11-17T04:15:00Z")
        d.listing(TUE_OPEN)
        self.assertFalse(d.enabled())


class RegistrationFlowTests(unittest.TestCase):
    def test_exact_registration_unlocks_a_tuesday_start(self):
        d = Desk(self).trial()
        d.register()
        out = d.listing(TUE_OPEN)
        self.assertTrue(d.enabled())
        self.assertTrue(out["complete"])
        self.assertNotIn("FOREIGN_ORDER", d.codes())
        settled = d.b.book["foreign_settled"]
        self.assertEqual(set(settled), {d.buy, d.sell, d.cancel})
        self.assertTrue(settled[d.buy]["reason"].startswith(R.REASON_PREFIX))
        self.assertIn("2 fill event(s)", settled[d.sell]["reason"])
        self.assertTrue(settled[d.cancel]["reason"].startswith("terminal canceled"))
        self.assertEqual(d.notes("REGISTRATION_AUTHENTICATED"), ["3 registered PAPER order(s), 4 fill event(s), "
                                                                 "flat reconcile"])
        self.assertEqual(len(d.calls("/v2/account/activities/FILL")), 1)
        self.assertFalse(d.b.book["listing_incomplete"])

    def test_activities_query_is_the_proven_shape(self):
        d = Desk(self).trial()
        d.register()
        d.listing(TUE_OPEN)
        (call,) = d.calls("/v2/account/activities/FILL")
        self.assertEqual(call[2], {"after": "2026-11-17T04:13:20Z", "page_size": "100", "direction": "asc"})

    def test_authentication_is_sticky_without_more_network_reads(self):
        d = Desk(self).trial()
        d.register()
        d.listing(TUE_OPEN)
        reads = len(d.calls("/v2/account/activities/FILL")), len(d.calls("/v2/positions"))
        d.trading.activities_fail = "outage"          # a later outage must not flip a settled start
        d.listing(TUE_LATE)
        d.new_broker()
        d.listing(TUE_LATE)
        self.assertTrue(d.enabled())
        self.assertEqual((len(d.calls("/v2/account/activities/FILL")), len(d.calls("/v2/positions"))), reads)
        self.assertEqual(len(d.notes("REGISTRATION_AUTHENTICATED")), 1)

    def test_next_trade_date_needs_no_registration_read(self):
        d = Desk(self).trial()
        d.register()
        d.listing(WED_EARLY)
        self.assertTrue(d.enabled())
        self.assertEqual(d.calls("/v2/account/activities/FILL"), [])

    def test_no_foreign_rows_reads_nothing(self):
        d = Desk(self)
        d.register(doc={"format": "wrong"})
        d.listing(TUE_OPEN)
        self.assertTrue(d.enabled())
        self.assertEqual(d.calls("/v2/account/activities/FILL"), [])
        self.assertEqual(d.notes("REGISTRATION_UNVERIFIED"), [])

    def test_unverified_note_is_written_once(self):
        d = Desk(self).trial()
        d.register(mode=0o644)
        d.listing(TUE_OPEN)
        d.listing(TUE_OPEN)
        self.assertEqual(len(d.notes("REGISTRATION_UNVERIFIED")), 1)


class RegistrationStillLocksTests(unittest.TestCase):
    """With a registration present, every one of these must still lock a Tuesday start."""

    def assertLocks(self, d, now=TUE_OPEN, unverified=True):
        d.listing(now)
        self.assertFalse(d.enabled())
        self.assertIn("FOREIGN_ORDER", d.codes())
        if unverified:
            self.assertTrue(d.notes("REGISTRATION_UNVERIFIED"))

    def test_same_day_unknown_order_beside_a_valid_registration(self):
        d = Desk(self).trial()
        d.register()
        d.order("reg-test-unknown-1", "buy", "filled", "1", "2026-11-17T15:00:00Z", "2026-11-17T15:00:05Z",
                avg=500.0, qty="1")
        d.trading.add_fill_activity(d.rows()[-1]["id"], "1", "1", "0", "fill", "2026-11-17T15:00:05.000Z")
        d.trading.set_position(1, 500.0)
        self.assertLocks(d, unverified=True)

    def test_same_day_unknown_order_when_the_registration_still_authenticates(self):
        d = Desk(self).trial()
        d.register()
        d.order("reg-test-unknown-2", "buy", "canceled", "0.5", "2026-11-17T15:00:00Z", "2026-11-17T15:00:05Z")
        d.listing(TUE_OPEN)
        self.assertFalse(d.enabled())
        self.assertIn("SPY order reg-test-unknown-2 (canceled) was not placed by this desk",
                      d.notes("FOREIGN_ORDER"))

    def test_working_order_beside_a_valid_registration(self):
        d = Desk(self).trial()
        d.register()
        d.trading.add_foreign_order(client_order_id="reg-test-working-1", status="new")
        d.listing(TUE_OPEN)
        self.assertFalse(d.enabled())

    def test_registered_order_still_working_at_the_broker(self):
        d = Desk(self).trial()
        d.register()
        d.trading.orders[d.sell].update(status="partially_filled", filled_at=None)
        self.assertLocks(d)

    def test_registered_fill_that_the_broker_shows_as_a_partial_cancel(self):
        d = Desk(self).trial()
        d.register()
        d.trading.orders[d.sell].update(status="canceled", filled_qty=Decimal("1.6"),
                                        canceled_at="2026-11-17T04:45:42Z", filled_at=None)
        self.assertLocks(d)

    def test_registration_naming_a_partially_filled_status_is_refused(self):
        d = Desk(self).trial()

        def partial(doc):
            sell = [o for o in doc["orders"] if o["client_order_id"] == "reg-test-sell-1"][0]
            sell.update(status="partially_filled")
        d.register(mutate=partial)
        self.assertLocks(d)

    def test_each_field_mismatch(self):
        changes = {
            "qty": ("qty", "3"), "filled_qty": ("filled_qty", "2.7"), "side": ("side", "sell"),
            "status": ("status", "canceled"), "client id": ("client_order_id", "reg-test-other-1"),
            "id": ("id", "mock-ord-9999"), "avg price": ("filled_avg_price", "500.11"),
            "filled_at": ("filled_at", "2026-11-17T04:14:28Z"), "submitted_at": ("submitted_at", "2026-11-17T04:14:21Z"),
            "extra stamp": ("canceled_at", "2026-11-17T04:14:27Z"),
        }
        for name, (key, value) in changes.items():
            with self.subTest(name):
                d = Desk(self).trial()

                def mutate(doc, key=key, value=value):
                    buy = [o for o in doc["orders"] if o["client_order_id"] == "reg-test-buy-1"][0]
                    buy[key] = value
                    if key == "filled_qty":
                        buy["qty"] = value
                d.register(mutate=mutate)
                d.listing(TUE_OPEN)
                self.assertFalse(d.enabled())
                self.assertIn("FOREIGN_ORDER", d.codes())

    def test_registered_order_missing_from_the_listing(self):
        d = Desk(self).trial()
        doc = R.build(d.rows())
        ghost = dict(doc["orders"][1], id="mock-ord-ghost", client_order_id="reg-test-ghost-1")
        doc["orders"].append(ghost)
        d.register(doc=doc)
        self.assertLocks(d)

    def test_registration_claiming_a_desk_book_order(self):
        d = Desk(self).trial()
        d.register()
        d.b.book["orders"]["reg-test-cancel-1"] = {"side": "buy", "qty": 1, "cum_qty": 0, "status": "canceled"}
        d.b._save()
        self.assertLocks(d)

    def test_fill_activity_problems(self):
        cases = {
            "partial missing": lambda t, d: t.activities.pop(1),
            "final missing": lambda t, d: t.activities.pop(0),
            "wrong side": lambda t, d: t.activities[0].update(side="sell"),
            "wrong symbol": lambda t, d: t.activities[0].update(symbol="QQQ"),
            "short total": lambda t, d: t.activities[1].update(qty="0.7"),
            "final leaves shares": lambda t, d: t.activities[0].update(leaves_qty="1.6"),
            "two finals": lambda t, d: t.activities[1].update(type="fill", cum_qty="3.6", leaves_qty="0"),
            "unknown type": lambda t, d: t.activities[1].update(type="fill_correction"),
            "float quantity": lambda t, d: t.activities[1].update(qty=1.6),
            "execution on the zero-share cancel": lambda t, d: t.add_fill_activity(
                d.cancel, "0.1", "0.1", "3.5", "partial_fill", "2026-11-17T04:23:45.000Z"),
        }
        for name, change in cases.items():
            with self.subTest(name):
                d = Desk(self).trial()
                d.register()
                change(d.trading, d)
                self.assertLocks(d)

    def test_registration_that_is_not_flat(self):
        d = Desk(self).trial()
        d.register(doc={"format": R.FORMAT, "mode": "paper",
                        "orders": R.build(d.rows([d.buy, d.cancel, d.sell]))["orders"][:2]})
        self.assertLocks(d)

    def test_broker_position_that_is_not_flat(self):
        d = Desk(self).trial()
        d.register()
        d.trading.set_position(1, 500.0)
        self.assertLocks(d)

    def test_a_full_activities_page(self):
        d = Desk(self).trial()
        d.register()
        for i in range(96):
            d.trading.add_fill_activity("mock-ord-other", "1", "1", "0", "fill", "2026-11-17T05:%02d:00.000Z" % (i % 60))
        self.assertLocks(d)

    def test_activities_outage_and_bad_answers(self):
        for kind in ("outage", "http", "bad_json"):
            with self.subTest(kind):
                d = Desk(self).trial()
                d.register()
                d.trading.activities_fail = kind
                self.assertLocks(d)

    def test_positions_outage(self):
        d = Desk(self).trial()
        d.register()
        d.trading.faults.append({"method": "GET", "kind": "5xx", "left": 5, "prefix": "/v2/positions"})
        self.assertLocks(d)

    def test_incomplete_listing(self):
        d = Desk(self).trial()
        d.register()
        d.trading.listing_cap = 3
        d.b.list_limit = 3
        self.assertLocks(d)

    def test_untrusted_files(self):
        def group_readable(d):
            d.register(mode=0o640)

        def world_readable(d):
            d.register(mode=0o604)

        def symlink(d):
            real = os.path.join(d.dir, "elsewhere.json")
            with open(real, "w") as fh:
                json.dump(R.build(d.rows()), fh)
            os.chmod(real, 0o600)
            os.symlink(real, R.path(d.dir))

        def folder(d):
            os.mkdir(R.path(d.dir))

        def not_json(d):
            with open(R.path(d.dir), "w") as fh:
                fh.write("{not json")
            os.chmod(R.path(d.dir), 0o600)

        def wrong_format(d):
            d.register(mutate=lambda doc: doc.update(format="paper-desk-registration-0"))

        def live_mode(d):
            d.register(mutate=lambda doc: doc.update(mode="live"))

        def float_qty(d):
            p = d.register()
            with open(p) as fh:
                text = fh.read()
            with open(p, "w") as fh:
                fh.write(text.replace('"filled_qty": "3.6"', '"filled_qty": 3.6').replace('"qty": "3.6"', '"qty": 3.6'))

        for name, setup in (("group readable", group_readable), ("world readable", world_readable),
                            ("symlink", symlink), ("folder", folder), ("not json", not_json),
                            ("wrong format", wrong_format), ("live mode", live_mode), ("float qty", float_qty)):
            with self.subTest(name):
                d = Desk(self).trial()
                setup(d)
                self.assertLocks(d)

    def test_removed_registration_locks_again(self):
        d = Desk(self).trial()
        d.register()
        d.listing(TUE_OPEN)
        self.assertTrue(d.enabled())
        os.remove(R.path(d.dir))
        d.listing(TUE_LATE)
        self.assertFalse(d.enabled())

    def test_non_paper_transport_never_reads_a_registration(self):
        d = Desk(self).trial()
        d.register()
        d.transport.MODE = "live"
        with _mock.patch.object(R, "load", side_effect=AssertionError("read")):
            self.assertLocks(d, unverified=False)
        self.assertEqual(d.calls("/v2/account/activities/FILL"), [])


class LiveNeverRegistersTests(unittest.TestCase):
    def stub(self, cls, mode="paper"):
        b = object.__new__(cls)
        b.transport = SimpleNamespace(MODE=mode)
        b.state_dir = "/nonexistent-registration-dir"
        b.book = {"orders": {}, "integrity": [], "foreign_settled": {}}
        return b

    def test_live_broker_returns_nothing_without_reading(self):
        with _mock.patch.object(R, "load", side_effect=AssertionError("read")):
            self.assertEqual(self.stub(AlpacaLiveBroker)._registration_settled({}, True), {})
            self.assertEqual(self.stub(AlpacaPaperBroker, mode="live")._registration_settled({}, True), {})

    def test_paper_broker_reads_it(self):
        with _mock.patch.object(R, "load", return_value=None) as load:
            self.assertEqual(self.stub(AlpacaPaperBroker)._registration_settled({}, True), {})
        load.assert_called_once()


class RegistrationFileTests(unittest.TestCase):
    def rows(self):
        return Desk(self).trial().rows()

    def test_build_validates_and_keeps_only_needed_fields(self):
        doc = R.build(self.rows())
        self.assertEqual(doc["format"], R.FORMAT)
        self.assertEqual(doc["mode"], "paper")
        self.assertEqual(len(doc["orders"]), 3)
        self.assertTrue(all(set(o) <= set(R.KEEP) for o in doc["orders"]))

    def test_refusals(self):
        base = R.build(self.rows())
        bad = {
            "empty": lambda doc: doc.update(orders=[]),
            "duplicate id": lambda doc: doc["orders"].append(dict(doc["orders"][0])),
            "not SPY": lambda doc: doc["orders"][0].update(symbol="QQQ"),
            "unknown side": lambda doc: doc["orders"][0].update(side="short"),
            "working": lambda doc: doc["orders"][0].update(status="new"),
            "partially filled": lambda doc: doc["orders"][0].update(status="partially_filled"),
            "filled short of qty": lambda doc: doc["orders"][0].update(filled_qty="2"),
            "cancel with shares": lambda doc: doc["orders"][1].update(filled_qty="0.1"),
            "bool qty": lambda doc: doc["orders"][0].update(qty=True),
            "float qty": lambda doc: doc["orders"][0].update(qty=3.6),
            "no filled_at": lambda doc: doc["orders"][0].pop("filled_at"),
            "no avg price": lambda doc: doc["orders"][0].pop("filled_avg_price"),
            "too many": lambda doc: doc.update(orders=doc["orders"] * 100),
        }
        for name, change in bad.items():
            with self.subTest(name):
                doc = json.loads(json.dumps(base))
                change(doc)
                with self.assertRaises(R.RegistrationInvalid):
                    R.validate(doc)

    def test_write_is_private_and_never_overwrites(self):
        d = tempfile.mkdtemp(prefix="paper-registration-file-")
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, R.FILE)
        R.write(p, R.build(self.rows()))
        self.assertEqual(os.stat(p).st_mode & 0o777, 0o600)
        self.assertEqual(len(R.load(d)), 3)
        with self.assertRaises(OSError):
            R.write(p, R.build(self.rows()))

    def test_command_prints_no_ids(self):
        d = tempfile.mkdtemp(prefix="paper-registration-cli-")
        self.addCleanup(shutil.rmtree, d, True)
        src = os.path.join(d, "orders.json")
        with open(src, "w") as fh:
            json.dump({"orders": self.rows()}, fh)
        out = os.path.join(d, R.FILE)
        with _mock.patch("builtins.print") as printed:
            self.assertEqual(R.main([src, out]), 0)
        text = " ".join(str(a) for c in printed.call_args_list for a in c[0])
        self.assertNotIn("mock-ord", text)
        self.assertNotIn("reg-test", text)
        self.assertEqual(os.stat(out).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
