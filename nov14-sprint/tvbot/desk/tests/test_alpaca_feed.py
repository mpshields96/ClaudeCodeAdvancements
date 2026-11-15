import os
"""Tests for alpaca.feed, alpaca.mock_data and the NYSE calendar profile (W2).

Offline only: an in-process transport routes to MockData; no socket, no key,
no Alpaca host. Every bar is synthetic.

Run from desk/: /usr/bin/python3 -IB -m unittest discover -s tests -p 'test_alpaca_feed*'
"""
import datetime as _dt
import sys
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from alpaca import DATA_LABEL_IEX, DATA_LABEL_MOCK  # noqa: E402
from alpaca.transport import encode_query, validate_path  # noqa: E402
from alpaca.mock_data import MockData  # noqa: E402
from alpaca.feed import IexSpyFeed, FeedRefused, FeedError, parse_rfc3339  # noqa: E402
from orders.calendar import (SessionCalendar, CalendarNotCovered, cross_check,  # noqa: E402
                             parse_ts, iso, NYSE_COVERED)
from orders.intake import check_bar  # noqa: E402

MON = "2026-11-16"      # Monday, EST: regular session 14:30Z-21:00Z
HALF = "2026-11-27"     # NYSE early close 13:00 ET = 18:00Z


class _Transport(object):
    """Minimal stand-in for W1's MockAlpacaTransport: same request() shape, no network.

    It runs W1's own path and query checks so the feed's requests are known to
    pass the real transport's guards.
    """

    def __init__(self, data, clock=None, calendar_rows=None):
        self.data = data
        self.clock_payload = clock
        self.calendar_rows = calendar_rows
        self.calls = []
        self.override = None

    def request(self, method, origin_key, path, query=None, body=None):
        validate_path(path)
        encode_query(origin_key, query)
        self.calls.append((method, origin_key, path, dict(query or {})))
        if self.override is not None:
            return self.override(method, origin_key, path, query)
        if origin_key == "data":
            return self.data.handle(method, path, query)
        if path == "/v2/clock":
            return 200, self.clock_payload
        if path == "/v2/calendar":
            return 200, self.calendar_rows
        return 404, {"message": "not mocked"}


def nyse():
    return SessionCalendar.nyse_2026_2027()


def make_feed(days=(MON,), page_limit=1000, **mock_kw):
    cal = nyse()
    data = MockData(days=days, calendar=cal, **mock_kw)
    tr = _Transport(data)
    return IexSpyFeed(tr, cal, minutes=60, source=DATA_LABEL_MOCK, page_limit=page_limit), tr, data


class NyseCalendarProfile(unittest.TestCase):
    def test_covers_2026_and_2027_only(self):
        cal = nyse()
        self.assertEqual(cal.describe()["covered"], list(NYSE_COVERED))
        self.assertEqual(NYSE_COVERED, ("2026-01-01", "2027-12-31"))
        for day in ("2028-01-03", "2025-12-31"):
            with self.assertRaises(CalendarNotCovered):
                cal.windows(day)
        self.assertIsNone(cal.next_open("2027-12-31T21:30:00Z"))
        self.assertFalse(cal.is_open("2028-01-03T15:00:00Z"))

    def test_2027_holidays_and_early_close(self):
        cal = nyse()
        for day in ("2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
                    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"):
            self.assertFalse(cal.is_trading_day(day), day)
        self.assertEqual([iso(t) for t in cal.session_bounds("2027-11-26")],
                         ["2027-11-26T14:30:00Z", "2027-11-26T18:00:00Z"])
        # summer (EDT): 09:30-16:00 ET is 13:30Z-20:00Z
        self.assertEqual([iso(t) for t in cal.session_bounds("2027-06-01")],
                         ["2027-06-01T13:30:00Z", "2027-06-01T20:00:00Z"])

    def test_2026_full_year_holidays(self):
        cal = nyse()
        for day in ("2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
                    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"):
            self.assertFalse(cal.is_trading_day(day), day)
        self.assertTrue(cal.is_trading_day("2026-07-02"))

    def test_agrees_with_default_calendar_on_its_covered_range(self):
        cal, default = nyse(), SessionCalendar()
        d = _dt.date(2026, 10, 1)
        while d <= _dt.date(2026, 12, 31):
            self.assertEqual(cal.windows(d), default.windows(d), d.isoformat())
            d += _dt.timedelta(days=1)

    def test_default_calendar_unchanged(self):
        self.assertEqual(SessionCalendar().describe()["covered"], ["2026-10-01", "2026-12-31"])
        with self.assertRaises(CalendarNotCovered):
            SessionCalendar().windows("2027-01-04")

    def test_half_day_slots(self):
        slots = [(iso(a), iso(b)) for a, b in nyse().bar_slots(HALF, 60)]
        self.assertEqual(slots[-1], ("2026-11-27T17:30:00Z", "2026-11-27T18:00:00Z"))
        self.assertEqual(len(slots), 4)


class CalendarCrossCheck(unittest.TestCase):
    def rows(self, start="2026-11-23", end="2026-11-30"):
        return nyse().as_alpaca_rows(start, end)

    def test_rows_shape_matches_alpaca(self):
        rows = self.rows()
        self.assertEqual(rows[0], {"date": "2026-11-23", "open": "09:30", "close": "16:00"})
        dates = [r["date"] for r in rows]
        self.assertNotIn("2026-11-26", dates)            # Thanksgiving
        self.assertIn({"date": "2026-11-27", "open": "09:30", "close": "13:00"}, rows)

    def test_identical_rows_have_no_differences(self):
        self.assertEqual(cross_check(nyse(), self.rows()), [])

    def test_reports_each_kind_of_difference(self):
        rows = self.rows()
        rows = [r for r in rows if r["date"] != "2026-11-24"]                  # missing_at_alpaca
        rows.append({"date": "2026-11-26", "open": "09:30", "close": "16:00"})  # closed_locally
        for r in rows:
            if r["date"] == "2026-11-27":
                r["close"] = "16:00"                                            # close_differs
            if r["date"] == "2026-11-30":
                r["open"] = "10:00"                                             # open_differs
        kinds = dict((d["date"], d["kind"]) for d in cross_check(nyse(), rows))
        self.assertEqual(kinds, {"2026-11-24": "missing_at_alpaca", "2026-11-26": "closed_locally",
                                 "2026-11-27": "close_differs", "2026-11-30": "open_differs"})

    def test_uncovered_dates_reported_not_guessed(self):
        cal = SessionCalendar()      # default: covered to 2026-12-31 only
        rows = [{"date": "2027-01-04", "open": "09:30", "close": "16:00"}]
        out = cross_check(cal, rows)
        self.assertEqual([(d["date"], d["kind"]) for d in out], [("2027-01-04", "not_covered")])

    def test_malformed_rows_refused(self):
        for bad in ([{"date": "2026-11-23", "open": "9:30"}], [{"open": "09:30", "close": "16:00"}],
                    ["x"], {"date": "2026-11-23"}):
            with self.assertRaises(ValueError):
                cross_check(nyse(), bad)


class MockDataServer(unittest.TestCase):
    def setUp(self):
        self.data = MockData(days=(MON,), calendar=nyse())
        self.q = {"timeframe": "1Min", "feed": "iex", "start": "2026-11-16T14:30:00Z",
                  "end": "2026-11-16T20:59:00Z"}

    def test_serves_alpaca_shape(self):
        status, payload = self.data.handle("GET", "/v2/stocks/SPY/bars", self.q)
        self.assertEqual(status, 200)
        self.assertEqual(payload["symbol"], "SPY")
        self.assertIsNone(payload["next_page_token"])
        self.assertEqual(len(payload["bars"]), 390)
        self.assertEqual(set(payload["bars"][0]), {"t", "o", "h", "l", "c", "v", "n", "vw"})
        self.assertEqual(payload["bars"][0]["t"], "2026-11-16T14:30:00Z")

    def test_multi_symbol_endpoint(self):
        q = dict(self.q, symbols="SPY")
        status, payload = self.data.handle("GET", "/v2/stocks/bars", q)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["bars"]["SPY"]), 390)

    def test_paginates(self):
        q = dict(self.q, limit=100)
        seen, token, pages = [], None, 0
        while True:
            qq = dict(q, page_token=token) if token else q
            status, payload = self.data.handle("GET", "/v2/stocks/SPY/bars", qq)
            self.assertEqual(status, 200)
            seen.extend(b["t"] for b in payload["bars"])
            pages += 1
            token = payload["next_page_token"]
            if not token:
                break
        self.assertEqual(pages, 4)
        self.assertEqual(len(seen), 390)
        self.assertEqual(len(set(seen)), 390)

    def test_refuses_non_iex_feed(self):
        for feed in ("sip", "otc", "boats", None):
            q = dict(self.q)
            if feed is None:
                q.pop("feed")        # Alpaca's default is sip, so absent is refused too
            else:
                q["feed"] = feed
            status, payload = self.data.handle("GET", "/v2/stocks/SPY/bars", q)
            self.assertTrue(400 <= status < 500, (feed, status))
            self.assertIn("iex", payload["message"])

    def test_refuses_other_symbols(self):
        status, _ = self.data.handle("GET", "/v2/stocks/AAPL/bars", self.q)
        self.assertTrue(400 <= status < 500)
        for syms in ("AAPL", "SPY,AAPL"):
            status, _ = self.data.handle("GET", "/v2/stocks/bars", dict(self.q, symbols=syms))
            self.assertTrue(400 <= status < 500, syms)

    def test_refuses_other_methods_params_and_timeframes(self):
        self.assertEqual(self.data.handle("POST", "/v2/stocks/SPY/bars", self.q)[0], 405)
        self.assertEqual(self.data.handle("GET", "/v2/stocks/SPY/bars", dict(self.q, timeframe="1Hour"))[0], 422)
        self.assertEqual(self.data.handle("GET", "/v2/stocks/SPY/bars", dict(self.q, extra="x"))[0], 422)
        self.assertEqual(self.data.handle("GET", "/v2/stocks/SPY/quotes", self.q)[0], 404)


class FeedRefusals(unittest.TestCase):
    def test_constructor_refuses_other_symbol_feed_or_label(self):
        cal = nyse()
        tr = _Transport(MockData(days=(MON,), calendar=cal))
        with self.assertRaises(FeedRefused):
            IexSpyFeed(tr, cal, symbol="AAPL")
        with self.assertRaises(FeedRefused):
            IexSpyFeed(tr, cal, feed="sip")
        with self.assertRaises(FeedRefused):
            IexSpyFeed(tr, cal, source="SIP CONSOLIDATED")
        with self.assertRaises(FeedRefused):
            IexSpyFeed(tr, cal, minutes=0)
        self.assertEqual(IexSpyFeed(tr, cal).source, DATA_LABEL_IEX)

    def test_every_request_is_free_iex_spy_1min(self):
        feed, tr, _ = make_feed(page_limit=50)
        feed.fetch_closed_bars(None, "2026-11-16T21:05:00Z")
        self.assertGreater(len(tr.calls), 1)
        for method, origin, path, q in tr.calls:
            self.assertEqual((method, origin, path), ("GET", "data", "/v2/stocks/SPY/bars"))
            self.assertEqual(q["feed"], "iex")
            self.assertEqual(q["timeframe"], "1Min")
            self.assertEqual(q["adjustment"], "raw")
            self.assertFalse(set(q) - {"feed", "timeframe", "start", "end", "limit", "adjustment",
                                       "sort", "page_token"})

    def test_http_error_and_bad_payloads_raise(self):
        feed, tr, _ = make_feed()
        tr.override = lambda *a: (403, {"message": "subscription does not permit"})
        with self.assertRaises(FeedError) as cm:
            feed.fetch_closed_bars(None, "2026-11-16T21:05:00Z")
        self.assertIn("403", str(cm.exception))
        tr.override = lambda *a: (200, {"bars": [], "symbol": "AAPL", "next_page_token": None})
        with self.assertRaises(FeedError):
            feed.fetch_closed_bars(None, "2026-11-16T21:05:00Z")
        tr.override = lambda *a: (200, {"bars": "nope", "symbol": "SPY", "next_page_token": None})
        with self.assertRaises(FeedError):
            feed.fetch_closed_bars(None, "2026-11-16T21:05:00Z")

    def test_repeated_page_token_raises(self):
        feed, tr, _ = make_feed()
        tr.override = lambda *a: (200, {"bars": [], "symbol": "SPY", "next_page_token": "same"})
        with self.assertRaises(FeedError):
            feed.fetch_closed_bars(None, "2026-11-16T21:05:00Z")

    def test_conflicting_duplicate_minute_raises(self):
        b = {"t": "2026-11-16T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10, "n": 1, "vw": 1.2}
        b2 = dict(b, c=1.9)
        feed, tr, _ = make_feed()
        tr.override = lambda *a: (200, {"bars": [b, b2], "symbol": "SPY", "next_page_token": None})
        with self.assertRaises(FeedError):
            feed.fetch_closed_bars(None, "2026-11-16T15:30:00Z")

    def test_uncovered_day_raises_visibly(self):
        cal = SessionCalendar()      # default table stops at 2026-12-31
        tr = _Transport(MockData(days=(), calendar=nyse()))
        feed = IexSpyFeed(tr, cal, source=DATA_LABEL_MOCK)
        with self.assertRaises(CalendarNotCovered):
            feed.fetch_closed_bars(None, "2027-01-04T16:00:00Z")
        self.assertEqual(tr.calls, [])


class FeedAggregation(unittest.TestCase):
    def test_first_slot_closes_exactly_at_1530z(self):
        feed, _, data = make_feed()
        self.assertEqual(feed.fetch_closed_bars(None, "2026-11-16T15:29:59Z"), [])
        bars = feed.fetch_closed_bars(None, "2026-11-16T15:30:00Z")
        self.assertEqual(len(bars), 1)
        b = bars[0]
        self.assertEqual((b["ts_open"], b["ts_close"]), ("2026-11-16T14:30:00Z", "2026-11-16T15:30:00Z"))
        mins = [m for m in data.bars if "2026-11-16T14:30:00Z" <= m["t"] < "2026-11-16T15:30:00Z"]
        self.assertEqual(len(mins), 60)
        self.assertEqual(b["open"], mins[0]["o"])
        self.assertEqual(b["close"], mins[-1]["c"])
        self.assertEqual(b["high"], max(m["h"] for m in mins))
        self.assertEqual(b["low"], min(m["l"] for m in mins))
        self.assertEqual(b["volume"], sum(m["v"] for m in mins))
        self.assertEqual((b["bar_count_1min"], b["minutes_expected"], b["partial"]), (60, 60, False))
        self.assertEqual((b["symbol"], b["feed"], b["source"]), ("SPY", "iex", DATA_LABEL_MOCK))
        self.assertEqual(b["received_ts"], "2026-11-16T15:30:00Z")
        self.assertEqual(b["delivered_ts"], b["received_ts"])

    def test_full_day_excludes_open_slot_and_half_hour_last(self):
        feed, _, _ = make_feed()
        bars = feed.fetch_closed_bars(None, "2026-11-16T20:45:00Z")
        self.assertEqual(len(bars), 6)                       # 20:30-21:00 is not closed yet
        bars = feed.fetch_closed_bars(None, "2026-11-16T21:00:00Z")
        self.assertEqual(len(bars), 7)
        last = bars[-1]
        self.assertEqual((last["ts_open"], last["ts_close"]), ("2026-11-16T20:30:00Z", "2026-11-16T21:00:00Z"))
        self.assertEqual((last["bar_count_1min"], last["minutes_expected"], last["partial"]), (30, 30, False))

    def test_after_ts_close_returns_only_later_slots(self):
        feed, _, _ = make_feed()
        bars = feed.fetch_closed_bars("2026-11-16T17:30:00Z", "2026-11-16T21:05:00Z")
        self.assertEqual([b["ts_close"] for b in bars],
                         ["2026-11-16T18:30:00Z", "2026-11-16T19:30:00Z", "2026-11-16T20:30:00Z",
                          "2026-11-16T21:00:00Z"])

    def test_extended_hours_minutes_are_dropped(self):
        feed, _, data = make_feed(include_extended=True)
        self.assertTrue(any(m["t"] < "2026-11-16T14:30:00Z" for m in data.bars))
        self.assertTrue(any(m["t"] >= "2026-11-16T21:00:00Z" for m in data.bars))
        bars = feed.fetch_closed_bars("2026-11-15T21:00:00Z", "2026-11-16T23:00:00Z")
        self.assertEqual(len(bars), 7)
        self.assertEqual(bars[0]["bar_count_1min"], 60)
        self.assertEqual(bars[-1]["bar_count_1min"], 30)
        self.assertGreater(feed.last_fetch["minutes_outside_slots"], 0)

    def test_half_day(self):
        feed, _, _ = make_feed(days=(HALF,), include_extended=True)
        bars = feed.fetch_closed_bars(None, "2026-11-27T19:00:00Z")
        self.assertEqual([(b["ts_open"], b["ts_close"], b["bar_count_1min"]) for b in bars],
                         [("2026-11-27T14:30:00Z", "2026-11-27T15:30:00Z", 60),
                          ("2026-11-27T15:30:00Z", "2026-11-27T16:30:00Z", 60),
                          ("2026-11-27T16:30:00Z", "2026-11-27T17:30:00Z", 60),
                          ("2026-11-27T17:30:00Z", "2026-11-27T18:00:00Z", 30)])
        self.assertFalse(any(b["partial"] for b in bars))

    def test_missing_minutes_mark_partial(self):
        drop = ("2026-11-16T15:31:00Z", "2026-11-16T15:45:00Z", "2026-11-16T16:29:00Z")
        feed, _, _ = make_feed(drop_minutes=drop)
        bars = feed.fetch_closed_bars(None, "2026-11-16T16:30:00Z")
        self.assertEqual([b["partial"] for b in bars], [False, True])
        self.assertEqual(bars[1]["bar_count_1min"], 57)
        self.assertEqual(bars[1]["minutes_expected"], 60)

    def test_slot_without_any_minute_is_not_invented(self):
        drop = tuple(iso(parse_ts("2026-11-16T15:30:00Z") + _dt.timedelta(minutes=i)) for i in range(60))
        feed, _, _ = make_feed(drop_minutes=drop)
        bars = feed.fetch_closed_bars(None, "2026-11-16T17:30:00Z")
        self.assertEqual([b["ts_open"] for b in bars], ["2026-11-16T14:30:00Z", "2026-11-16T16:30:00Z"])
        self.assertEqual(feed.last_fetch["empty_slots"], [["2026-11-16T15:30:00Z", "2026-11-16T16:30:00Z"]])

    def test_pagination_gives_same_bars(self):
        big, tr1, _ = make_feed(page_limit=1000)
        small, tr2, _ = make_feed(page_limit=37)
        a = big.fetch_closed_bars(None, "2026-11-16T21:05:00Z")
        b = small.fetch_closed_bars(None, "2026-11-16T21:05:00Z")
        self.assertEqual(len(tr1.calls), 1)
        self.assertEqual(len(tr2.calls), 11)                 # ceil(390 / 37)
        self.assertEqual(a, b)

    def test_nanosecond_and_offset_timestamps(self):
        self.assertEqual(iso(parse_rfc3339("2026-11-16T14:30:00.123456789Z")), "2026-11-16T14:30:00Z")
        self.assertEqual(iso(parse_rfc3339("2025-06-24T14:15:22-04:00")), "2025-06-24T18:15:22Z")
        for bad in ("2026-11-16T14:30:00", "2026-11-16", "x", 5):
            with self.assertRaises(ValueError):
                parse_rfc3339(bad)
        feed, _, _ = make_feed(ts_style="ns")
        self.assertEqual(len(feed.fetch_closed_bars(None, "2026-11-16T21:00:00Z")), 7)

    def test_received_ts_defaults_to_now_and_can_be_given(self):
        feed, _, _ = make_feed()
        b = feed.fetch_closed_bars(None, "2026-11-16T15:30:00Z", received_ts="2026-11-16T15:30:01Z")[0]
        self.assertEqual(b["received_ts"], "2026-11-16T15:30:01Z")
        with self.assertRaises(ValueError):
            feed.fetch_closed_bars(None, "2026-11-16T15:30:00")       # naive refused


class FeedIntoIntake(unittest.TestCase):
    def test_bars_pass_intake_one_click_per_close(self):
        """Operator checks 2s after each close; every produced bar passes check_bar."""
        cal = nyse()
        data = MockData(days=(MON, "2026-11-17"), calendar=cal, include_extended=True)
        feed = IexSpyFeed(_Transport(data), cal, minutes=60, source=DATA_LABEL_MOCK)
        prev, after, accepted = None, None, 0
        for day in (MON, "2026-11-17"):
            for _o, close in cal.bar_slots(day, 60):
                now = iso(close + _dt.timedelta(seconds=2))
                bars = feed.fetch_closed_bars(after, now)
                self.assertEqual(len(bars), 1, now)
                bar = bars[0]
                res = check_bar(bar, prev, cal, minutes=60)
                ok = res[0] if isinstance(res, tuple) else res["ok"]
                self.assertTrue(ok, (now, res))
                prev, after, accepted = bar, bar["ts_close"], accepted + 1
        self.assertEqual(accepted, 14)

    def test_late_check_is_flagged_stale_by_intake_default(self):
        """A fetch long after the close is visible as stale, not silently accepted."""
        feed, _, _ = make_feed()
        bar = feed.fetch_closed_bars(None, "2026-11-16T15:40:00Z")[0]
        res = check_bar(bar, None, nyse(), minutes=60)
        ok = res[0] if isinstance(res, tuple) else res["ok"]
        self.assertFalse(ok)


class ClockAndCalendarEndpoints(unittest.TestCase):
    def test_clock(self):
        tr = _Transport(MockData(), clock={"timestamp": "2026-11-16T10:15:22-05:00", "is_open": True,
                                           "next_open": "2026-11-17T09:30:00-05:00",
                                           "next_close": "2026-11-16T16:00:00-05:00"})
        feed = IexSpyFeed(tr, nyse(), source=DATA_LABEL_MOCK)
        c = feed.clock()
        self.assertEqual(c["timestamp"], "2026-11-16T15:15:22Z")
        self.assertIs(c["is_open"], True)
        self.assertEqual(c["next_close"], "2026-11-16T21:00:00Z")
        self.assertEqual(tr.calls[-1][:3], ("GET", "trading", "/v2/clock"))
        tr.clock_payload = {"timestamp": "2026-11-16T10:15:22-05:00", "is_open": "yes",
                            "next_open": "x", "next_close": "y"}
        with self.assertRaises(FeedError):
            feed.clock()

    def test_calendar_days_feed_the_cross_check(self):
        cal = nyse()
        rows = cal.as_alpaca_rows("2026-11-23", "2026-11-30")
        wire = [dict(r, session_open="0400", session_close="2000", settlement_date="2026-11-25")
                for r in rows]
        tr = _Transport(MockData(), calendar_rows=wire)
        feed = IexSpyFeed(tr, cal, source=DATA_LABEL_MOCK)
        got = feed.calendar_days("2026-11-23", "2026-11-30")
        self.assertEqual(tr.calls[-1], ("GET", "trading", "/v2/calendar",
                                        {"start": "2026-11-23", "end": "2026-11-30"}))
        self.assertEqual(cross_check(cal, got, "2026-11-23", "2026-11-30"), [])
        tr.calendar_rows = {"not": "a list"}
        with self.assertRaises(FeedError):
            feed.calendar_days("2026-11-23", "2026-11-30")


class WithW1MockTransport(unittest.TestCase):
    """The same feed through W1's MockAlpacaTransport (stringified query values, data guards)."""

    def test_feed_clock_and_calendar_through_w1_transport(self):
        from alpaca.mock import MockAlpacaTransport, MockTrading
        cal = nyse()
        tr = MockAlpacaTransport(trading=MockTrading(), data=MockData(days=(MON,), calendar=cal))
        feed = IexSpyFeed(tr, cal, minutes=60, source=DATA_LABEL_MOCK, page_limit=100)
        bars = feed.fetch_closed_bars(None, "2026-11-16T21:00:02Z")
        self.assertEqual(len(bars), 7)
        self.assertEqual(feed.last_fetch["pages"], 4)
        self.assertIs(feed.clock()["is_open"], True)
        self.assertEqual(feed.check_calendar("2026-06-01", "2026-06-01"), [])


if __name__ == "__main__":
    unittest.main()
