"""Tests for orders.calendar and orders.intake (offline, simulated fixtures only).

Run: /usr/bin/python3 -I -m unittest discover -s <desk>/tests -p 'test_orders*'
"""
import json
import os
import sys
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(os.path.dirname(DESK), "fixtures")
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from orders.calendar import SessionCalendar, parse_ts, iso  # noqa: E402
from orders.intake import check_bar, bar_can_fill, missing_slots  # noqa: E402


def load_bars(path):
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") == "manifest":
                continue
            out.append(rec)
    return out


def scan(bars, cal):
    """[(index, code)] for every bar that fails, carrying prev like the manager does."""
    bad, prev = [], None
    for i, b in enumerate(bars):
        ok, code, _d = check_bar(b, prev, cal)
        if not ok:
            bad.append((i, code))
        if code not in ("BAD_BAR", "OUT_OF_ORDER"):
            prev = b
    return bad


def round_the_clock():
    return SessionCalendar(tz="UTC", sessions=(("00:00", "24:00"),), closed_days=(), early_closes={},
                           weekdays=(0, 1, 2, 3, 4, 5, 6), name="utc-24x7")


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.cal = SessionCalendar()

    def test_thanksgiving_closed_and_early_close(self):
        self.assertFalse(self.cal.is_trading_day("2026-11-26"))
        self.assertEqual(self.cal.windows("2026-11-26"), [])
        w = self.cal.windows("2026-11-27")
        self.assertEqual(len(w), 1)
        self.assertEqual(iso(w[0][0]), "2026-11-27T14:30:00Z")
        self.assertEqual(iso(w[0][1]), "2026-11-27T18:00:00Z")   # 12:00 CT
        self.assertTrue(self.cal.is_open("2026-11-27T17:59:00Z"))
        self.assertFalse(self.cal.is_open("2026-11-27T18:00:00Z"))

    def test_dst_change_moves_utc_open(self):
        # DST ends 2026-11-01 in America/Chicago.
        self.assertEqual(iso(self.cal.windows("2026-10-30")[0][0]), "2026-10-30T13:30:00Z")
        self.assertEqual(iso(self.cal.windows("2026-11-02")[0][0]), "2026-11-02T14:30:00Z")

    def test_weekend_closed(self):
        self.assertFalse(self.cal.is_trading_day("2026-11-21"))
        self.assertFalse(self.cal.is_open("2026-11-21T16:00:00Z"))
        self.assertEqual(iso(self.cal.next_open("2026-11-21T16:00:00Z")), "2026-11-23T14:30:00Z")

    def test_naive_timestamp_refused(self):
        with self.assertRaises(ValueError):
            parse_ts("2026-11-20T15:00:00")
        import datetime as dt
        with self.assertRaises(ValueError):
            parse_ts(dt.datetime(2026, 11, 20, 15, 0))

    def test_overnight_window_refused(self):
        with self.assertRaises(ValueError):
            SessionCalendar(tz="UTC", sessions=(("22:00", "02:00"),))

    def test_expected_bars_hourly(self):
        bars = self.cal.expected_bars("2026-11-27", 60)
        self.assertEqual(bars[0], ("2026-11-27T14:30:00Z", "2026-11-27T15:30:00Z"))
        self.assertEqual(bars[-1], ("2026-11-27T17:30:00Z", "2026-11-27T18:00:00Z"))

    def test_christmas_eve_early_close_and_christmas_closed(self):
        w = self.cal.windows("2026-12-24")
        self.assertEqual([(iso(a), iso(b)) for a, b in w], [("2026-12-24T14:30:00Z", "2026-12-24T18:00:00Z")])
        self.assertTrue(self.cal.is_open("2026-12-24T17:59:00Z"))
        self.assertFalse(self.cal.is_open("2026-12-24T18:00:00Z"))
        self.assertFalse(self.cal.is_trading_day("2026-12-25"))
        self.assertEqual(self.cal.windows("2026-12-25"), [])
        self.assertEqual(iso(self.cal.next_open("2026-12-24T18:00:00Z")), "2026-12-28T14:30:00Z")

    def test_session_bounds(self):
        a, b = self.cal.session_bounds("2026-11-20")
        self.assertEqual((iso(a), iso(b)), ("2026-11-20T14:30:00Z", "2026-11-20T21:00:00Z"))
        a, b = self.cal.session_bounds("2026-12-24")
        self.assertEqual((iso(a), iso(b)), ("2026-12-24T14:30:00Z", "2026-12-24T18:00:00Z"))
        self.assertIsNone(self.cal.session_bounds("2026-12-25"))
        self.assertIsNone(self.cal.session_bounds("2026-11-21"))     # Saturday
        fx = SessionCalendar.fixture_profile()
        a, b = fx.session_bounds("2026-06-01")
        self.assertEqual((iso(a), iso(b)), ("2026-06-01T14:30:00Z", "2026-06-01T21:30:00Z"))

    def test_uncovered_dates_are_refused_visibly(self):
        from orders.calendar import CalendarNotCovered
        self.assertEqual(self.cal.describe()["covered"], ["2026-10-01", "2026-12-31"])
        for day in ("2027-01-04", "2026-09-30"):
            with self.assertRaises(CalendarNotCovered):
                self.cal.windows(day)
            with self.assertRaises(ValueError):
                self.cal.session_bounds(day)
            with self.assertRaises(CalendarNotCovered):
                self.cal.is_trading_day(day)
        self.assertFalse(self.cal.is_open("2027-01-04T16:00:00Z"))          # fail closed
        self.assertIsNone(self.cal.next_open("2026-12-31T21:00:00Z"))       # never guesses Jan 2027
        bar = {"ts_open": "2027-01-04T15:30:00Z", "ts_close": "2027-01-04T16:30:00Z",
               "delivered_ts": "2027-01-04T16:30:02Z", "open": 100.0, "high": 101.0,
               "low": 99.0, "close": 100.5, "volume": 1000}
        ok, code, detail = check_bar(bar, None, self.cal)
        self.assertFalse(ok)
        self.assertEqual(code, "CALENDAR_NOT_COVERED")
        self.assertIn("OUT_OF_SESSION", detail["codes"])
        # Custom and fixture calendars make no coverage claim unless asked.
        self.assertTrue(SessionCalendar.fixture_profile().covers("2030-01-02"))
        self.assertIsNone(SessionCalendar.fixture_profile().covered)
        limited = SessionCalendar(tz="UTC", sessions=(("14:30", "21:30"),), closed_days=(),
                                  early_closes={}, covered=("2026-06-01", "2026-06-30"))
        self.assertFalse(limited.covers("2026-07-01"))


class FixtureIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = SessionCalendar.fixture_profile()
        cls.normal = load_bars(os.path.join(FIX, "normal_bars.jsonl"))

    def test_normal_and_holdout_bars_all_pass(self):
        self.assertEqual(scan(self.normal, self.cal), [])
        self.assertEqual(scan(load_bars(os.path.join(FIX, "holdout_bars.jsonl")), self.cal), [])

    def test_omitted_hour_is_gap_in_session(self):
        b = self.normal
        ok, code, detail = check_bar(b[4], b[2], self.cal)
        self.assertFalse(ok)
        self.assertEqual(code, "GAP_IN_SESSION")
        self.assertEqual(detail["first_missing"], b[3]["ts_open"])
        self.assertEqual(missing_slots(b[2], b[4], self.cal), [(b[3]["ts_open"], b[3]["ts_close"])])

    def test_dropped_bar_fixture(self):
        bad = scan(load_bars(os.path.join(FIX, "adverse", "b04_dropped_bar.jsonl")), self.cal)
        self.assertEqual([c for _i, c in bad], ["GAP_IN_SESSION"])

    def test_overnight_and_weekend_are_not_gaps(self):
        b = self.normal
        self.assertEqual(check_bar(b[7], b[6], self.cal)[1], "OK")         # overnight
        fri = [i for i, x in enumerate(b) if parse_ts(x["ts_open"]).weekday() == 4]
        last_fri = max(i for i in fri if i + 1 < len(b) and parse_ts(b[i + 1]["ts_open"]).weekday() == 0)
        self.assertEqual(check_bar(b[last_fri + 1], b[last_fri], self.cal)[1], "OK")   # weekend

    def test_zero_volume(self):
        bar = dict(self.normal[1], volume=0)
        ok, code, _ = check_bar(bar, self.normal[0], self.cal)
        self.assertFalse(ok)
        self.assertEqual(code, "ZERO_VOLUME")
        self.assertFalse(bar_can_fill(bar))
        self.assertTrue(bar_can_fill(self.normal[1]))

    def test_old_exchange_ts_is_stale_even_with_fast_delivery(self):
        bar = dict(self.normal[1])
        close = parse_ts(bar["ts_close"])
        import datetime as dt
        bar["exchange_ts"] = iso(close - dt.timedelta(seconds=60))
        bar["delivered_ts"] = iso(close + dt.timedelta(seconds=1))   # the response was fast
        ok, code, detail = check_bar(bar, self.normal[0], self.cal)
        self.assertEqual(code, "STALE_EXCHANGE_TS")
        self.assertEqual(detail["exchange_ts_source"], "exchange_ts")
        # An explicit received time decides the same way.
        ok, code, _ = check_bar(dict(self.normal[1]), self.normal[0], self.cal,
                                received_ts=iso(close + dt.timedelta(seconds=30)))
        self.assertEqual(code, "STALE_EXCHANGE_TS")

    def test_future_exchange_ts(self):
        bar = dict(self.normal[1])
        import datetime as dt
        bar["exchange_ts"] = iso(parse_ts(bar["delivered_ts"]) + dt.timedelta(seconds=60))
        self.assertEqual(check_bar(bar, self.normal[0], self.cal)[1], "FUTURE_EXCHANGE_TS")

    def test_bar_received_before_its_close_is_refused(self):
        import datetime as dt
        bar = dict(self.normal[1])
        close = parse_ts(bar["ts_close"])
        bar["delivered_ts"] = iso(close - dt.timedelta(seconds=2))   # inside the 5 s skew allowance
        ok, code, detail = check_bar(bar, self.normal[0], self.cal)
        self.assertFalse(ok)
        self.assertEqual(code, "NOT_CLOSED_AT_RECEIPT")
        self.assertEqual(detail["not_closed"]["ts_close"], bar["ts_close"])
        ok, code, _ = check_bar(dict(self.normal[1]), self.normal[0], self.cal,
                                received_ts=iso(close - dt.timedelta(seconds=1)))
        self.assertEqual(code, "NOT_CLOSED_AT_RECEIPT")

    def test_exchange_ts_before_close_is_refused_even_when_fresh(self):
        import datetime as dt
        bar = dict(self.normal[1])
        close = parse_ts(bar["ts_close"])
        bar["exchange_ts"] = iso(close - dt.timedelta(seconds=1))
        bar["delivered_ts"] = iso(close + dt.timedelta(seconds=1))   # age 2 s: fresh
        ok, code, detail = check_bar(bar, self.normal[0], self.cal)
        self.assertFalse(ok)
        self.assertEqual(code, "EXCHANGE_TS_BEFORE_CLOSE")
        self.assertNotIn("NOT_CLOSED_AT_RECEIPT", detail["codes"])
        self.assertNotIn("STALE_EXCHANGE_TS", detail["codes"])
        # Received exactly at the close is a closed bar.
        ok, code, _ = check_bar(dict(self.normal[1]), self.normal[0], self.cal, received_ts=bar["ts_close"])
        self.assertEqual(code, "OK")

    def test_no_received_time_fails_closed(self):
        bar = dict(self.normal[1])
        bar.pop("delivered_ts", None)
        ok, code, detail = check_bar(bar, self.normal[0], self.cal)
        self.assertFalse(ok)
        self.assertEqual(code, "STALE_EXCHANGE_TS")

    def test_stale_fixture(self):
        bad = scan(load_bars(os.path.join(FIX, "adverse", "b01_stale_signal_bar.jsonl")), self.cal)
        self.assertIn("STALE_EXCHANGE_TS", [c for _i, c in bad])

    def test_duplicate_bar_is_out_of_order(self):
        for name in ("c01_duplicate_bar.jsonl", "c02_conflicting_duplicate.jsonl"):
            bad = scan(load_bars(os.path.join(FIX, "adverse", name)), self.cal)
            self.assertEqual([c for _i, c in bad], ["OUT_OF_ORDER"], name)

    def test_future_bar_fixture_is_refused(self):
        bad = scan(load_bars(os.path.join(FIX, "adverse", "b02_future_bar.jsonl")), self.cal)
        self.assertTrue(bad)
        self.assertNotIn("OK", [c for _i, c in bad])

    def test_out_of_session(self):
        bar = dict(self.normal[0])
        bar.update(ts_open="2026-06-01T03:00:00Z", ts_close="2026-06-01T04:00:00Z",
                   delivered_ts="2026-06-01T04:00:02Z")
        self.assertEqual(check_bar(bar, None, self.cal)[1], "OUT_OF_SESSION")

    def test_bad_bars(self):
        b = self.normal
        self.assertEqual(check_bar(dict(b[1], high=b[1]["low"] - 1), b[0], self.cal)[1], "BAD_BAR")
        self.assertEqual(check_bar(dict(b[1], close=float("nan")), b[0], self.cal)[1], "BAD_BAR")
        missing = dict(b[1])
        missing.pop("volume")
        self.assertEqual(check_bar(missing, b[0], self.cal)[1], "BAD_BAR")
        self.assertEqual(check_bar(dict(b[1], ts_open="2026-06-01T15:30:00"), b[0], self.cal)[1], "BAD_BAR")
        bad = scan(load_bars(os.path.join(FIX, "adverse", "b03_missing_field.jsonl")), self.cal)
        self.assertEqual(bad[0][1], "BAD_BAR")
        bad = scan(load_bars(os.path.join(FIX, "adverse", "a02_alert_payload.jsonl")), self.cal)
        self.assertEqual([c for _i, c in bad], ["BAD_BAR"])


class TimingFixtureTests(unittest.TestCase):
    """Timing fixtures run round the clock (UTC, 7 days), so use a 24x7 calendar."""

    def setUp(self):
        self.cal = round_the_clock()

    def test_late_delivery_is_stale(self):
        bars = load_bars(os.path.join(FIX, "timing", "t01_late_delivery.jsonl"))
        bad = scan(bars, self.cal)
        self.assertEqual(len(bad), len(bars))
        self.assertTrue(all(c == "STALE_EXCHANGE_TS" for _i, c in bad))

    def test_on_time_control_passes(self):
        bars = load_bars(os.path.join(FIX, "timing", "t02_on_time_control.jsonl"))
        self.assertEqual(scan(bars, self.cal), [])

    def test_session_break_control_is_fresh(self):
        bars = load_bars(os.path.join(FIX, "timing", "t03_session_break_control.jsonl"))
        bad = scan(bars, self.cal)
        self.assertNotIn("STALE_EXCHANGE_TS", [c for _i, c in bad])
        # Bars before the break are clean. The break itself needs a per-day
        # schedule that a single-window calendar cannot express (STATUS gap).
        self.assertTrue(all(i >= 64 for i, _c in bad))


if __name__ == "__main__":
    unittest.main()
