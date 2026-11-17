"""A protective stop whose submit the broker never confirmed covers nothing on screen, and is never resent.

During funded management the entry fills and the desk sends the protective stop. If that POST times
out before the venue answers (no order visible) or its response is lost (the order may exist), the
stop is NOT confirmed working. The desk must show those shares as UNCOVERED and UNCONFIRMED, naming
the order's client id, and must not send a second stop for them (nothing sells twice). Once the
venue shows the order, the same shares count as covered.

Offline only. Every quantity, price and amount is an arbitrary TEST VALUE, not anyone's sizing,
terms or account; the venue is the in-process alpaca/mock.py MockTrading (no socket, no key).
"""
import os
import sys
import types
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.dirname(os.path.abspath(__file__))
for _p in (DESK, TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpaca_session as AS  # noqa: E402
from orders import qty as Q  # noqa: E402
from test_alpaca_session_night import _posts  # noqa: E402
from test_live_reconcile import QTY, Held  # noqa: E402


def _stop_posts(c):
    return [p for p in _posts(c) if p.get("type") in ("stop", "stop_limit")]


class DuringManagement(Held):
    def assert_unconfirmed(self, pv):
        self.assertEqual(Q.parse(pv["position_qty"]), Q.parse(QTY))
        self.assertEqual(Q.parse(pv["uncovered_qty"]), Q.parse(QTY), pv)
        self.assertEqual(Q.parse(pv["unconfirmed_qty"]), Q.parse(QTY), pv)
        self.assertEqual(pv["bare_qty"], 0, pv)
        self.assertEqual((pv["protective_qty"], pv["covered_qty"]), (0, 0), pv)
        prot = [o for o in pv["unconfirmed_orders"] if o["kind"] == "protective"]
        self.assertEqual(len(prot), 1, pv)
        self.assertIn(prot[0]["status"], AS.UNCONFIRMED_STATUSES)
        self.assertIn("NOT confirmed protected", pv["warning"])
        self.assertIn(prot[0]["client_id"], pv["warning"])
        return prot[0]

    def test_timed_out_stop_shows_uncovered_and_is_not_resent(self):
        self.held(protect_fault="timeout")
        self.trading.hide_next = 0                     # a pre-submit timeout created no order to hide
        self.assertEqual(len(_stop_posts(self.c)), 1)
        self.assertEqual([o for o in self.trading.orders.values() if o.get("type") == "stop"], [])
        self.assert_unconfirmed(self.c._protection_view())
        for _ in range(3):                             # later Checks during the arm
            self.sup.tick()
            self.assertEqual(self.sup.view["phase"], "managing")
            self.assert_unconfirmed(self.c._protection_view())
        self.assertEqual(len(_stop_posts(self.c)), 1)  # never a second stop for the same shares
        shown = self.c.session_state()
        self.assertIn("NOT confirmed protected", repr(shown))

    def test_lost_ack_stop_counts_only_once_the_venue_shows_it(self):
        self.held(protect_fault="lost_ack")
        first = self.assert_unconfirmed(self.c._protection_view())
        self.sup.tick()
        self.assert_unconfirmed(self.c._protection_view())
        self.trading.reveal()                          # the venue shows the order it accepted
        self.sup.tick()
        pv = self.c._protection_view()
        self.assertEqual(Q.parse(pv["covered_qty"]), Q.parse(QTY), pv)
        self.assertEqual((pv["uncovered_qty"], pv["unconfirmed_qty"], pv["bare_qty"]), (0, 0, 0), pv)
        self.assertNotIn("warning", pv)
        stops = _stop_posts(self.c)
        self.assertEqual(len(stops), 1, stops)         # found by its client id, never resent
        self.assertEqual(stops[0].get("client_order_id"), first["client_id"])


def _view(position, protective=(), working=()):
    """The protection view over a hand-built manager state (TEST VALUES)."""
    st = {"exposure": {"position_qty": position, "working_orders": list(working)},
          "protective_orders": list(protective), "controls": {"stopped": False}}
    fake = types.SimpleNamespace(mock=True, mgr=types.SimpleNamespace(state=lambda: st, intents={}))
    return AS.AlpacaSessionController._protection_view(fake)


class Split(unittest.TestCase):
    def test_confirmed_unconfirmed_and_bare_shares_are_counted_apart(self):
        pv = _view(3, protective=[dict(side="sell", remaining=1, status="acked", client_id="p1", kind="protective")],
                   working=[dict(side="sell", remaining=1, status="uncertain", client_id="x1", kind="exit")])
        self.assertEqual((pv["protective_qty"], pv["exit_working_qty"], pv["covered_qty"]), (1, 0, 1))
        self.assertEqual((pv["uncovered_qty"], pv["unconfirmed_qty"], pv["bare_qty"]), (2, 1, 1))
        self.assertIn("exit x1", pv["warning"])
        self.assertIn("no working protective stop or exit order", pv["warning"])

    def test_pending_stop_is_unconfirmed_not_covered(self):
        pv = _view("0.002", protective=[dict(side="sell", remaining="0.002", status="pending",
                                             client_id="p2", kind="protective")])
        self.assertEqual((pv["covered_qty"], pv["bare_qty"]), (0, 0))
        self.assertEqual(Q.parse(pv["unconfirmed_qty"]), Q.parse("0.002"))

    def test_flat_desk_has_nothing_uncovered(self):
        pv = _view(0)
        self.assertEqual((pv["uncovered_qty"], pv["unconfirmed_qty"], pv["bare_qty"]), (0, 0, 0))
        self.assertNotIn("warning", pv)

    def test_confirmed_stop_covers_without_warning(self):
        pv = _view(2, protective=[dict(side="sell", remaining=2, status="acked", client_id="p3", kind="protective")])
        self.assertEqual((pv["covered_qty"], pv["uncovered_qty"]), (2, 0))
        self.assertNotIn("warning", pv)


if __name__ == "__main__":
    unittest.main()
