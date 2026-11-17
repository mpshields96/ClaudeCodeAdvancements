"""Bounded Arm: /api/arm takes an optional body expires_utc that can only SHORTEN the arm.

The automated paper runner (alpaca/paper_runner.py --auto) arms only to its own run end, and only
when /api/health reports arm_bounded_expiry true. The UI's Arm button sends no body expiry: its arm
ends WIND_DOWN_S before the regular close (the desk calendar's, early closes included, or the venue
clock's next_close when that is earlier), so the reduce-only Stop & Close goes out while the venue
still takes it. Inside the wind-down no arm is taken. A past or unreadable expiry is refused with no
arm; a later one is capped at the wind-down; an earlier operator end is kept.

Offline only: the desk paths use the in-process venues from test_alpaca_session_night (no socket to
Alpaca, no key, no order). The server paths use a loopback DeskServer and a fake controller.
"""
import datetime as _dt
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.dirname(os.path.abspath(__file__))
for _p in (DESK, TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import types  # noqa: E402

import alpaca_session as AS  # noqa: E402
import session as S  # noqa: E402
from alpaca import trading_profile as TP  # noqa: E402
from ui import server  # noqa: E402
from test_alpaca_session_night import _Base, _venue, FixedClock  # noqa: E402


class PlanCall(unittest.TestCase):
    def test_ui_arm_without_a_body_expiry_is_unchanged(self):
        self.assertEqual(server._plan_call("arm", "arm", {}), ("arm", {}, ()))
        self.assertEqual(server._plan_call("arm", "arm", {"expires_utc": ""}), ("arm", {}, ()))

    def test_body_expiry_is_passed_through(self):
        body = server._clean_body({"expires_utc": "2026-11-17T16:00:00Z", "other": 1})
        self.assertEqual(body, {"expires_utc": "2026-11-17T16:00:00Z"})
        self.assertEqual(server._plan_call("arm", "arm", body),
                         ("arm", {"expires_utc": "2026-11-17T16:00:00Z"}, ()))

    def test_malformed_body_expiry_is_refused(self):
        for bad in ("tomorrow", "2026-11-17 16:00:00", "2026-11-17T16:00:00+00:00", "1700000000", 5, True):
            with self.assertRaises(ValueError, msg=bad):
                server._plan_call("arm", "arm", {"expires_utc": bad})


class DeskArm(_Base):
    def ready(self):
        c = self.live()
        self.assertTrue(c.alpaca_enable(confirm=True)["ok"])
        c.check_new_bars()
        _venue(c)
        self.assertTrue(c.connection_check()["ok"])
        now, day = c._today()
        cap = c.calendar.session_bounds(day)[1] - _dt.timedelta(seconds=TP.WIND_DOWN_S)
        return c, now, cap

    def test_capability_flag(self):
        self.assertIs(AS.AlpacaSessionController.ARM_BOUNDED_EXPIRY, True)
        self.assertFalse(hasattr(S.SessionController, "ARM_BOUNDED_EXPIRY"))

    def test_no_expiry_ends_the_arm_at_the_wind_down_before_the_close(self):
        c, now, cap = self.ready()
        close = c.calendar.session_bounds(c._today()[1])[1]
        self.assertEqual(TP.WIND_DOWN_S, 900)
        self.assertLess(now, cap)
        r = c.arm()
        self.assertTrue(r["ok"], r)
        self.assertEqual(c.mgr.state()["expires_utc"], AS.iso(cap))
        self.assertEqual((close - cap).total_seconds(), TP.WIND_DOWN_S)   # before the close, never after
        b = c.arm_bounds
        self.assertEqual((b["regular_close_utc"], b["close_source"]), (AS.iso(close), "desk calendar"))
        self.assertEqual((b["wind_down_utc"], b["arm_ends_utc"]), (AS.iso(cap), AS.iso(cap)))
        self.assertIs(b["operator_end"], False)
        self.assertEqual(c.session_state()["arm_bounds"]["arm_ends_utc"], AS.iso(cap))

    def test_inside_the_wind_down_no_arm_is_taken(self):
        c, _now, cap = self.ready()
        for t in (cap, cap + _dt.timedelta(minutes=5)):
            c.clock = FixedClock(t)
            _venue(c, now=t)
            r = c.arm()
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["reason"], "ARM_WIND_DOWN", r)
            self.assertFalse(c.mgr.state()["armed"])

    def test_venue_close_earlier_than_the_calendar_moves_the_wind_down(self):
        c, now, cap = self.ready()
        vclose = now + _dt.timedelta(minutes=40)          # an unscheduled early close, still ahead
        self.assertLess(vclose, cap)
        c.transport.trading.clock = dict(c.transport.trading.clock, next_close=AS.iso(vclose))
        r = c.arm()
        self.assertTrue(r["ok"], r)
        want = vclose - _dt.timedelta(seconds=TP.WIND_DOWN_S)
        self.assertEqual(c.mgr.state()["expires_utc"], AS.iso(want))
        self.assertEqual((c.arm_bounds["close_source"], c.arm_bounds["regular_close_utc"]),
                         ("venue clock", AS.iso(vclose)))

    def test_earlier_expiry_shortens_the_arm(self):
        c, now, cap = self.ready()
        want = min(now + _dt.timedelta(minutes=10), cap)
        r = c.arm(expires_utc=AS.iso(want))
        self.assertTrue(r["ok"], r)
        self.assertEqual(c.mgr.state()["expires_utc"], AS.iso(want))
        self.assertTrue(c.mgr.state()["armed"])
        self.assertIs(c.arm_bounds["operator_end"], want != cap)        # the earlier operator end is kept
        self.assertEqual(c.arm_bounds["arm_ends_utc"], AS.iso(want))

    def test_later_expiry_is_capped(self):
        c, _now, cap = self.ready()
        r = c.arm(expires_utc=AS.iso(cap + _dt.timedelta(hours=6)))
        self.assertTrue(r["ok"], r)
        self.assertEqual(c.mgr.state()["expires_utc"], AS.iso(cap))

    def test_past_or_unreadable_expiry_is_refused_with_no_arm(self):
        for bad in (lambda now: AS.iso(now - _dt.timedelta(seconds=1)), lambda now: AS.iso(now),
                    lambda now: "not-a-time", lambda now: "2026-11-17T16:00:00"):
            c, now, _cap = self.ready()
            r = c.arm(expires_utc=bad(now))
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["reason"], "ARM_EXPIRY_INVALID")
            self.assertFalse(c.mgr.state()["armed"])
            c.close()


class Bounds(unittest.TestCase):
    """_arm_bounds over the desk's own NYSE calendar (no desk, no venue call). TEST times."""

    def bounds(self, now, venue=None):
        cal = AS.SessionCalendar.nyse_2026_2027()
        fake = types.SimpleNamespace(calendar=cal, _venue_clock_seen=venue)
        return AS.AlpacaSessionController._arm_bounds(fake, now, cal.local_date(AS.iso(now)))

    def test_normal_day_winds_down_15_minutes_before_the_close(self):
        b = self.bounds(AS.parse_ts("2026-11-17T15:00:00Z"))
        self.assertEqual(b["regular_close_utc"], AS.iso(AS.parse_ts("2026-11-17T21:00:00Z")))
        self.assertEqual(b["wind_down_utc"], AS.iso(AS.parse_ts("2026-11-17T20:45:00Z")))

    def test_early_close_days_wind_down_before_the_early_close(self):
        for day in ("2026-11-27", "2026-12-24"):
            b = self.bounds(AS.parse_ts(day + "T15:00:00Z"))
            self.assertEqual(b["regular_close_utc"], AS.iso(AS.parse_ts(day + "T18:00:00Z")), day)
            self.assertEqual(b["wind_down_utc"], AS.iso(AS.parse_ts(day + "T17:45:00Z")), day)
            self.assertEqual(b["close_source"], "desk calendar")

    def test_venue_next_close_counts_only_when_open_earlier_and_ahead(self):
        now = AS.parse_ts("2026-11-17T15:00:00Z")
        early = {"is_open": True, "next_close": "2026-11-17T19:00:00Z"}
        self.assertEqual(self.bounds(now, early)["wind_down_utc"], AS.iso(AS.parse_ts("2026-11-17T18:45:00Z")))
        self.assertEqual(self.bounds(now, early)["close_source"], "venue clock")
        for ignored in ({"is_open": True, "next_close": "2026-11-17T14:00:00Z"},     # already past
                        {"is_open": True, "next_close": "2026-11-18T21:00:00Z"},     # later than the calendar
                        {"is_open": False, "next_close": "2026-11-17T19:00:00Z"},    # venue closed
                        {"is_open": True, "next_close": "garbage"}, None):
            b = self.bounds(now, ignored)
            self.assertEqual((b["close_source"], b["wind_down_utc"]),
                             ("desk calendar", AS.iso(AS.parse_ts("2026-11-17T20:45:00Z"))), ignored)


class _FakeDesk(object):
    def __init__(self, bounded):
        if bounded:
            self.ARM_BOUNDED_EXPIRY = True
        self.calls = []

    def arm(self, expires_utc=None):
        self.calls.append(expires_utc)
        return {"ok": True}


class Health(unittest.TestCase):
    def start(self, ctl):
        self.tmp = tempfile.mkdtemp(prefix="arm_bound_")
        self.srv = server.make_server(self.tmp, host="127.0.0.1", port=0, manager=ctl)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self._stop)

    def _stop(self):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, method, path, body=None):
        port = self.srv.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        h = {"Host": "127.0.0.1:%d" % port}
        data = None
        if method == "POST":
            data = json.dumps(body or {}).encode("utf-8")
            h["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        out = json.loads(r.read().decode("utf-8"))
        conn.close()
        return r.status, out

    def test_flag_true_only_for_a_bounded_desk(self):
        self.start(_FakeDesk(bounded=True))
        self.assertIs(self.call("GET", "/api/health")[1]["arm_bounded_expiry"], True)

    def test_flag_false_for_an_unbounded_desk(self):
        self.start(_FakeDesk(bounded=False))
        self.assertIs(self.call("GET", "/api/health")[1]["arm_bounded_expiry"], False)

    def test_flag_false_with_no_controller(self):
        self.start(None)
        self.assertIs(self.call("GET", "/api/health")[1]["arm_bounded_expiry"], False)

    def test_route_passes_body_expiry_and_ui_arm_passes_none(self):
        ctl = _FakeDesk(bounded=True)
        self.start(ctl)
        st, _ = self.call("POST", "/api/arm", {"expires_utc": "2026-11-17T16:00:00Z"})
        self.assertEqual(st, 200)
        st, _ = self.call("POST", "/api/arm", {})
        self.assertEqual(st, 200)
        st, _ = self.call("POST", "/api/arm", {"expires_utc": "soon"})
        self.assertNotEqual(st, 200)
        self.assertEqual(ctl.calls, ["2026-11-17T16:00:00Z", None])


if __name__ == "__main__":
    unittest.main()
