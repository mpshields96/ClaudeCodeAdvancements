"""Alpaca's RFC 3339 timestamps (up to nine fraction digits) must parse on Python 3.9.6.

Regression for INVALID_MARKET_CLOCK / INVALID_QUOTE on the real paper endpoint: readiness
used datetime.fromisoformat, which on 3.9 rejects nine-digit fractions for both the clock and
the quote. Connectivity must stay distinct from session readiness after the fix.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

DESK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(DESK), str(DESK / "tests")]
from alpaca.readiness import _timestamp, check_connection, read_quote
from test_alpaca_readiness import QUOTE, Responses
import report

NOW = "2026-11-16T15:31:00.123456789Z"
UTC = timezone.utc


class ReadinessTimestampTests(unittest.TestCase):
    def test_nine_digit_fraction_with_z(self):
        dt = _timestamp("2026-11-16T15:31:00.123456789Z")
        self.assertEqual(dt, datetime(2026, 11, 16, 15, 31, 0, 123456, tzinfo=UTC))
        self.assertEqual(dt.utcoffset(), timedelta(0))

    def test_nine_digit_fraction_with_offset(self):
        dt = _timestamp("2026-11-16T10:31:00.987654321-05:00")
        self.assertEqual(dt, datetime(2026, 11, 16, 15, 31, 0, 987654, tzinfo=UTC))
        self.assertEqual(dt.utcoffset(), timedelta(0))

    def test_zero_three_and_six_digits(self):
        for text, micro in [("2026-11-16T15:31:00Z", 0), ("2026-11-16T15:31:00.123Z", 123000),
                            ("2026-11-16T15:31:00.123456+00:00", 123456)]:
            with self.subTest(text=text):
                self.assertEqual(_timestamp(text), datetime(2026, 11, 16, 15, 31, 0, micro, tzinfo=UTC))

    def test_naive_input_still_refused(self):
        for value in ["2026-11-16T15:31:00", "2026-11-16T15:31:00.123456789",
                      datetime(2026, 11, 16, 15, 31)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _timestamp(value)

    def test_aware_datetime_passes_through_as_utc(self):
        est = timezone(timedelta(hours=-5))
        self.assertEqual(_timestamp(datetime(2026, 11, 16, 10, 31, tzinfo=est)),
                         datetime(2026, 11, 16, 15, 31, tzinfo=UTC))

    def test_garbage_still_refused(self):
        for value in [None, 12, "", "not a time", "2026-11-16T15:31:00.1234567890Z"]:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                _timestamp(value)


class ReadinessBehaviourTests(unittest.TestCase):
    def test_nine_digit_quote_fresh_when_recent(self):
        t = Responses()
        t.payload[QUOTE]["quote"]["t"] = "2026-11-16T15:30:59.500000001Z"
        out = read_quote(t, NOW)
        self.assertEqual(out["reason"], "FRESH")
        self.assertTrue(out["fresh"])

    def test_nine_digit_quote_still_stale(self):
        t = Responses()
        t.payload[QUOTE]["quote"]["t"] = "2026-11-13T20:59:59.912345678Z"
        out = read_quote(t, NOW)
        self.assertTrue(out["valid"])
        self.assertFalse(out["fresh"])
        self.assertEqual(out["reason"], "STALE_QUOTE")

    def test_nine_digit_quote_still_future(self):
        t = Responses()
        t.payload[QUOTE]["quote"]["t"] = "2026-11-16T15:31:05.000000001Z"
        self.assertEqual(read_quote(t, NOW)["reason"], "FUTURE_QUOTE")

    def test_closed_market_with_nine_digit_clock_is_connected_but_not_ready(self):
        t = Responses()
        t.payload["/v2/clock"] = {"is_open": False, "timestamp": "2026-11-16T00:19:41.123456789-05:00"}
        t.payload[QUOTE]["quote"]["t"] = "2026-11-13T20:59:59.912345678Z"
        out = check_connection(t, "2026-11-16T05:19:41.5Z")
        self.assertTrue(out["connection_verified"])
        self.assertFalse(out["market_conditions_ready"])
        self.assertEqual(set(out["reasons"]), {"MARKET_CLOSED", "STALE_QUOTE"})
        self.assertNotIn("INVALID_MARKET_CLOCK", out["reasons"])
        self.assertNotIn("INVALID_QUOTE", out["reasons"])

    def test_open_market_with_nine_digit_clock_and_quote_is_ready(self):
        t = Responses()
        t.payload["/v2/clock"]["timestamp"] = "2026-11-16T10:31:00.000000123-05:00"
        t.payload[QUOTE]["quote"]["t"] = "2026-11-16T15:30:58.999999999Z"
        out = check_connection(t, NOW)
        self.assertTrue(out["connection_verified"])
        self.assertTrue(out["market_conditions_ready"], out["reasons"])
        self.assertEqual(out["reasons"], [])

    def test_unparseable_clock_still_invalid(self):
        t = Responses()
        t.payload["/v2/clock"]["timestamp"] = "2026-11-16 15:31"
        out = check_connection(t, NOW)
        self.assertIn("INVALID_MARKET_CLOCK", out["reasons"])
        self.assertFalse(out["market_conditions_ready"])


class ReportTimestampTests(unittest.TestCase):
    def test_short_ts_nine_digits(self):
        self.assertEqual(report.short_ts("2026-11-16T15:31:00.123456789Z"), "2026-11-16 15:31Z")
        self.assertEqual(report.short_ts("2026-11-16T10:31:00.123456789-05:00"), "2026-11-16 15:31Z")

    def test_short_ts_zero_three_six_digits(self):
        for text in ["2026-11-16T15:31:00Z", "2026-11-16T15:31:00.123Z", "2026-11-16T15:31:00.123456+00:00"]:
            with self.subTest(text=text):
                self.assertEqual(report.short_ts(text), "2026-11-16 15:31Z")

    def test_short_ts_naive_and_garbage_unchanged(self):
        self.assertEqual(report.short_ts("2026-11-16T15:31:00"), "2026-11-16 15:31")
        self.assertEqual(report.short_ts("not a time"), "not a time")
        self.assertEqual(report.short_ts(""), "")

    def test_iso_week_nine_digits_matches_plain(self):
        plain = report.iso_week("2026-11-16T15:31:00Z")
        self.assertIsNotNone(plain)
        self.assertEqual(report.iso_week("2026-11-16T15:31:00.123456789Z"), plain)
        self.assertEqual(report.iso_week("2026-11-16T10:31:00.123456789-05:00"), plain)

    def test_iso_week_naive_and_garbage_unchanged(self):
        self.assertEqual(report.iso_week("2026-11-16T15:31:00"), report.iso_week("2026-11-16T15:31:00Z"))
        self.assertIsNone(report.iso_week("not a time"))
        self.assertIsNone(report.iso_week(None))


if __name__ == "__main__":
    unittest.main()
