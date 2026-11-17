"""Funded session auto-management (alpaca/live_supervisor.py), offline.

After the operator's own Enable and Arm, the supervisor runs the desk's Check on its own cadence until
the arm ends or Stop, then a bounded reconcile-only phase until the broker confirms flat or an explicit
UNRESOLVED handoff. It never enables, arms or re-arms. A desk it never saw armed gets no call.
The desk paths use the in-process live venue from test_alpaca_session_night: no socket to Alpaca, no
key, no order beyond what the synthetic venue records.
"""
import datetime as _dt
import os
import sys
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.dirname(os.path.abspath(__file__))
for _p in (DESK, TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from alpaca import live_supervisor as LS  # noqa: E402
from alpaca import trading_profile as TP  # noqa: E402
from test_alpaca_session_night import _Base, FixedClock  # noqa: E402


def _count_checks(c):
    calls = []
    real = c.check_new_bars

    def wrapped():
        calls.append(1)
        return real()
    c.check_new_bars = wrapped
    return calls


class Source(unittest.TestCase):
    def test_never_enables_arms_or_clears(self):
        with open(LS.__file__) as fh:
            code = fh.read().split('"""', 2)[2]        # code only, not the module docstring
        for word in (".arm(", "alpaca_enable", "clear_stop", "approve", "set_limits", ".post(", "urlopen"):
            self.assertNotIn(word, code, word)

    def test_cadence_is_the_profile_protection_interval(self):
        class R(object):
            pass
        self.assertEqual(LS.LiveSupervisor(R()).every_s, TP.PROTECT_CHECK_S)


class OnTheDesk(_Base):
    def test_unarmed_desk_is_left_alone(self):
        c = self.live()
        calls = _count_checks(c)
        sup = LS.LiveSupervisor(c)
        self.assertIsNone(sup.tick())
        self.assertEqual(calls, [])
        st = c.session_state()
        self.assertFalse(st["auto_manage"]["active"])
        self.assertEqual(st["auto_manage"]["state"], LS.IDLE)
        self.assertFalse(c.mgr.state()["armed"])
        self.assertFalse(c.adapter_state.enabled)

    def test_armed_desk_is_checked_without_clicks(self):
        c = self.armed_live()
        calls = _count_checks(c)
        sup = LS.LiveSupervisor(c)
        sup.tick()
        sup.tick()
        self.assertEqual(len(calls), 2)
        st = c.session_state()
        self.assertTrue(st["auto_manage"]["active"])
        self.assertEqual(st["auto_manage"]["checks"], 2)
        self.assertEqual(st["auto_manage"]["every_s"], TP.PROTECT_CHECK_S)
        self.assertIn("after you enable and arm it", st["schedule"]["note"])
        self.assertIn("never enables or arms itself", st["schedule"]["note"])

    def test_stop_ends_management_and_it_never_rearms(self):
        c = self.armed_live()
        sup = LS.LiveSupervisor(c)
        sup.tick()
        c.stop_and_close()
        calls = _count_checks(c)
        for _ in range(3):
            sup.tick()
        self.assertEqual(calls, [])
        self.assertFalse(c.mgr.state()["armed"])
        self.assertFalse(c.adapter_state.enabled)
        am = c.session_state()["auto_manage"]
        self.assertEqual((am["phase"], am["state"]), ("flat", LS.FLAT))     # flat confirmed, then done
        self.assertFalse(am["active"])

    def test_expiry_is_a_bounded_clean_stop(self):
        c = self.armed_live()
        exp = AS_parse(c.mgr.state()["expires_utc"])
        sup = LS.LiveSupervisor(c)
        c.clock = FixedClock(exp + _dt.timedelta(minutes=1))
        sup.tick()                                        # this Check ends the arm on the desk clock
        self.assertFalse(c.mgr.state()["armed"])
        self.assertTrue(c._controls()["stopped"])
        self.assertFalse(c.adapter_state.enabled)
        am = c.session_state()["auto_manage"]
        self.assertFalse(am["active"])
        self.assertEqual(am["phase"], "flat")
        calls = _count_checks(c)
        sup.tick()
        self.assertEqual(calls, [])

    def test_a_failing_check_is_counted_and_retried(self):
        c = self.armed_live()
        sup = LS.LiveSupervisor(c)
        boom = [True]
        real = c.check_new_bars

        def flaky():
            if boom:
                boom.pop()
                raise RuntimeError("synthetic")
            return real()
        c.check_new_bars = flaky
        sup.tick()
        sup.tick()
        am = c.session_state()["auto_manage"]
        self.assertEqual((am["errors"], am["checks"]), (1, 1))
        self.assertEqual(am["last_error"], None)


class _Fake(object):
    """A desk double: armed until disarm(), then holds `pos` until a reconcile_check flattens it."""

    def __init__(self, pos=1.0, flatten_after=None, reconcile=True):
        self.armed, self.stopped, self.pos, self.flat = True, False, pos, False
        self.flatten_after, self.recon, self.checks = flatten_after, 0, 0
        fake = self

        class mgr(object):
            intents = {"I-x": {"kind": "close", "side": "sell", "qty": 1.0, "status": "uncertain",
                               "client_id": "desk-close-x"}}

            @staticmethod
            def state():
                return {"armed": fake.armed,
                        "controls": {"stopped": fake.stopped, "flat_confirmed": fake.flat,
                                     "close_pending": None if fake.flat else "close working"},
                        "exposure": {"position_qty": fake.pos, "working_orders": []}}
        self.mgr = mgr

        class adapter_state(object):
            enabled = True
        self.adapter_state = adapter_state
        if not reconcile:
            self.reconcile_check = None

    def check_new_bars(self):
        self.checks += 1
        return {"ok": True, "bars": 0}

    def reconcile_check(self):
        self.recon += 1
        if self.flatten_after is not None and self.recon >= self.flatten_after:
            self.pos, self.flat = 0.0, True
        return {"ok": True, "reconcile_only": True}

    def stop(self):
        self.armed, self.stopped = False, True


class Reconcile(unittest.TestCase):
    def test_nothing_is_called_before_an_arm_is_seen(self):
        r = _Fake()
        r.armed = False
        sup = LS.LiveSupervisor(r, every_s=300)
        for _ in range(5):
            sup.tick()
        self.assertEqual((r.checks, r.recon), (0, 0))
        self.assertEqual(sup.view["phase"], "idle")

    def test_reconciles_until_the_broker_confirms_flat(self):
        r = _Fake(flatten_after=2)
        sup = LS.LiveSupervisor(r, every_s=300)
        sup.tick()
        r.stop()
        sup.tick()
        self.assertEqual(sup.view["phase"], "reconciling")
        self.assertTrue(sup.view["active"])
        sup.tick()
        self.assertEqual((sup.view["phase"], sup.view["state"]), ("flat", LS.FLAT))
        self.assertEqual((r.checks, r.recon), (1, 2))
        sup.tick()
        self.assertEqual(r.recon, 2)                           # done: no more calls

    def test_bound_reached_is_an_explicit_unresolved_handoff(self):
        r = _Fake()
        sup = LS.LiveSupervisor(r, every_s=300)
        self.assertEqual(sup.reconcile_max, 3)                 # RECONCILE_S / every_s
        sup.tick()
        r.stop()
        for _ in range(10):
            sup.tick()
        self.assertEqual(r.recon, sup.reconcile_max)
        self.assertEqual(sup.view["phase"], "unresolved")
        self.assertFalse(sup.view["active"])
        h = sup.view["handoff"]
        self.assertEqual(h["position_qty"], 1.0)
        self.assertEqual(h["unsettled_orders"][0]["client_id"], "desk-close-x")
        self.assertEqual(r.auto_manage["phase"], "unresolved")

    def test_errors_count_toward_the_bound(self):
        r = _Fake()

        def boom():
            r.recon += 1
            raise RuntimeError("synthetic")
        r.reconcile_check = boom
        sup = LS.LiveSupervisor(r, every_s=300)
        sup.tick()
        r.stop()
        for _ in range(10):
            sup.tick()
        self.assertEqual(r.recon, sup.reconcile_max)
        self.assertEqual(sup.view["phase"], "unresolved")
        self.assertEqual(sup.view["errors"], sup.reconcile_max)

    def test_a_desk_without_reconcile_check_is_handed_off_at_once(self):
        r = _Fake(reconcile=False)
        sup = LS.LiveSupervisor(r, every_s=300)
        sup.tick()
        r.stop()
        sup.tick()
        self.assertEqual(sup.view["phase"], "unresolved")

    def test_a_new_operator_arm_starts_managing_again(self):
        r = _Fake(flatten_after=1)
        sup = LS.LiveSupervisor(r, every_s=300)
        sup.tick()
        r.stop()
        sup.tick()
        self.assertEqual(sup.view["phase"], "flat")
        r.armed, r.stopped, r.pos, r.flat = True, False, 1.0, False   # the operator armed again
        sup.tick()
        self.assertEqual((sup.view["phase"], sup.view["reconcile_checks"]), ("managing", 0))
        self.assertEqual(r.checks, 2)


class Loop(unittest.TestCase):
    def test_run_ticks_until_halted_then_reports_ended(self):
        class R(object):
            def __init__(self):
                self.n = 0

            class mgr(object):
                @staticmethod
                def state():
                    return {"armed": True, "controls": {"stopped": False}}

            class adapter_state(object):
                enabled = True

            def check_new_bars(self):
                self.n += 1
                return {"ok": True, "bars": 0, "utc": "2026-11-17T15:00:00Z"}
        r = R()
        waits = iter([False, False, False, True])
        sup = LS.LiveSupervisor(r, every_s=1, wait=lambda s: next(waits))
        sup.run()
        self.assertEqual(r.n, 3)
        self.assertEqual(r.auto_manage["state"], LS.ENDED)
        self.assertFalse(r.auto_manage["active"])

    def test_unreadable_desk_is_not_due(self):
        class R(object):
            def check_new_bars(self):
                raise AssertionError("must not be called")
        self.assertIsNone(LS.LiveSupervisor(R()).tick())

    def test_start_and_stop_join_the_thread(self):
        class R(object):
            pass
        sup = LS.LiveSupervisor(R(), every_s=60).start()
        self.assertTrue(sup.thread.is_alive())
        sup.stop()
        self.assertFalse(sup.thread.is_alive())


def AS_parse(ts):
    import alpaca_session as AS
    return AS.parse_ts(ts)


if __name__ == "__main__":
    unittest.main()
