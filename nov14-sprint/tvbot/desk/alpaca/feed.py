"""Free IEX SPY bars for the paper desk: Alpaca 1Min bars aggregated into the desk's slots.

IexSpyFeed(transport, calendar, minutes=60, source=DATA_LABEL_IEX)

  fetch_closed_bars(after_ts_close, now_utc, received_ts=None) -> [bar]
      One manual operator fetch. Returns every desk slot that closed after
      `after_ts_close` (None: today's closed slots) and at or before `now_utc`,
      oldest first, in the desk's bar shape (ts_open, ts_close, open, high, low,
      close, volume) plus provenance (symbol, feed, source, bar_count_1min,
      minutes_expected, partial, received_ts, delivered_ts). A slot with no IEX
      minute at all yields no bar (intake then reports the gap); it is listed in
      last_fetch["empty_slots"]. Nothing here sleeps, polls or runs in the
      background: one call is one click.
  clock() -> {timestamp, is_open, next_open, next_close}    (trading host /v2/clock)
  calendar_days(start, end) -> [{date, open, close}]         (trading host /v2/calendar)
  check_calendar(start, end) -> cross_check differences against the local calendar

Every bars request is GET data /v2/stocks/SPY/bars with feed=iex, timeframe=1Min,
adjustment=raw, sort=asc. Alpaca's default feed is sip (paid), so feed=iex is
always sent. The transport (W1) enforces the fixed hosts; this module never
builds a URL, reads a key or opens a socket.

Assumption carried from RESEARCH.md section 3 [UNVERIFIED]: a 1Min bar's `t` is
the start of its minute. A minute is used only when slot_open <= t and
t + 1min <= slot_close.
"""
import bisect as _bisect
import datetime as _dt
import math as _math
import re as _re

from alpaca import DATA_LABEL_IEX, DATA_LABEL_MOCK, FEED, SYMBOL
from orders.calendar import _alpaca_rows, cross_check, iso, parse_ts

UTC = _dt.timezone.utc
ONE_MIN = _dt.timedelta(minutes=1)
MINUTE_MARKS = 16   # first genuine minute opens kept per slot, for the lab's later-entry proxy
BARS_PATH = "/v2/stocks/%s/bars" % SYMBOL
SOURCES = (DATA_LABEL_IEX, DATA_LABEL_MOCK)
MAX_PAGES = 100
MAX_LOOKBACK_DAYS = 10

_RFC3339 = _re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(Z|z|[+-]\d{2}:\d{2})$")
_DAY = _re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FeedRefused(ValueError):
    """The feed was asked for something outside free IEX SPY (raised before any request)."""


class FeedError(RuntimeError):
    """A response could not be trusted (HTTP error, wrong symbol, bad shape, conflicting data)."""


def parse_rfc3339(text):
    """Aware UTC datetime from Alpaca's RFC-3339 timestamps (0-9 fraction digits, Z or offset).

    Fractions beyond microseconds are truncated. A missing zone, a bare date or a
    non-string is refused with ValueError.
    """
    if not isinstance(text, str):
        raise ValueError("timestamp must be a string: %r" % (text,))
    m = _RFC3339.match(text.strip())
    if not m:
        raise ValueError("not an RFC-3339 timestamp with a zone: %r" % (text,))
    y, mo, d, h, mi, s, frac, zone = m.groups()
    micro = int((frac or "0")[:6].ljust(6, "0"))
    if zone in ("Z", "z"):
        tz = UTC
    else:
        sign = 1 if zone[0] == "+" else -1
        tz = _dt.timezone(sign * _dt.timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6])))
    return _dt.datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), micro, tzinfo=tz).astimezone(UTC)


def _num(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not _math.isfinite(v):
        raise FeedError("minute bar %s is not a finite number: %r" % (what, v))
    return v


def _short(payload):
    if isinstance(payload, dict):
        msg = payload.get("message")
        if isinstance(msg, str):
            return msg[:200]
    return type(payload).__name__


class IexSpyFeed(object):
    def __init__(self, transport, calendar, minutes=60, symbol=SYMBOL, feed=FEED,
                 source=DATA_LABEL_IEX, page_limit=1000):
        if symbol != SYMBOL:
            raise FeedRefused("only %s is allowed, not %r" % (SYMBOL, symbol))
        if feed != FEED:
            raise FeedRefused("only the free iex feed is allowed, not %r" % (feed,))
        if source not in SOURCES:
            raise FeedRefused("unknown data label %r" % (source,))
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
            raise FeedRefused("bar minutes must be a positive whole number")
        if isinstance(page_limit, bool) or not isinstance(page_limit, int) or not 1 <= page_limit <= 10000:
            raise FeedRefused("page_limit must be 1..10000")
        self.transport = transport
        self.calendar = calendar
        self.minutes = minutes
        self.symbol = symbol
        self.feed = feed
        self.source = source
        self.page_limit = page_limit
        self.last_fetch = {}

    def __repr__(self):
        return "IexSpyFeed(%s %s %dmin, %s)" % (self.symbol, self.feed, self.minutes, self.source)

    # ---- slots -----------------------------------------------------------
    def _closed_slots(self, after, now):
        first = self.calendar.local_date(after if after is not None else now)
        last = self.calendar.local_date(now)
        if (last - first).days > MAX_LOOKBACK_DAYS:
            raise FeedError("after_ts_close is more than %d days before now; start a new session"
                            % MAX_LOOKBACK_DAYS)
        out, day = [], first
        while day <= last:
            for o, c in self.calendar.bar_slots(day, self.minutes):   # CalendarNotCovered propagates
                if c <= now and (after is None or c > after):
                    out.append((o, c))
            day += _dt.timedelta(days=1)
        return out

    # ---- requests --------------------------------------------------------
    def _get(self, origin_key, path, query):
        status, payload = self.transport.request("GET", origin_key, path, query=query)
        if status != 200:
            raise FeedError("%s %s failed: HTTP %s: %s" % (origin_key, path, status, _short(payload)))
        return payload

    def _minutes(self, start, end):
        query = {"feed": self.feed, "timeframe": "1Min", "start": iso(start), "end": iso(end),
                 "limit": self.page_limit, "adjustment": "raw", "sort": "asc"}
        rows, seen, token, pages = [], set(), None, 0
        while True:
            q = dict(query, page_token=token) if token else query
            payload = self._get("data", BARS_PATH, q)
            pages += 1
            if not isinstance(payload, dict):
                raise FeedError("bars response is not an object")
            if payload.get("symbol") != self.symbol:
                raise FeedError("bars response symbol %r is not %s" % (payload.get("symbol"), self.symbol))
            bars = payload.get("bars")
            if bars is None:
                bars = []                 # Alpaca may send null for an empty page
            if not isinstance(bars, list):
                raise FeedError("bars is not a list")
            rows.extend(bars)
            token = payload.get("next_page_token")
            if token is None or token == "":
                return rows, pages
            if not isinstance(token, str) or token in seen:
                raise FeedError("page token repeated or malformed; stopping")
            seen.add(token)
            if pages >= MAX_PAGES:
                raise FeedError("more than %d pages; refusing to continue" % MAX_PAGES)

    def _clean(self, rows):
        """{minute_start: bar} with identical duplicates dropped; conflicts raise."""
        out, dups = {}, 0
        for b in rows:
            if not isinstance(b, dict):
                raise FeedError("minute bar is not an object")
            try:
                t = parse_rfc3339(b.get("t"))
            except ValueError as exc:
                raise FeedError("minute bar time: %s" % exc)
            if t.second or t.microsecond:
                raise FeedError("minute bar time %r is not on a minute" % (b.get("t"),))
            o, h, lo, c = (_num(b.get(k), k) for k in ("o", "h", "l", "c"))
            v = _num(b.get("v"), "v")
            if v < 0 or h < max(o, c) or lo > min(o, c):
                raise FeedError("minute bar %s has inconsistent prices or negative volume" % iso(t))
            m = {"t": t, "o": o, "h": h, "l": lo, "c": c, "v": v,
                 "n": b.get("n"), "vw": b.get("vw")}
            prev = out.get(t)
            if prev is not None:
                if prev != m:
                    raise FeedError("conflicting duplicate minute %s" % iso(t))
                dups += 1
                continue
            out[t] = m
        return out, dups

    # ---- public ----------------------------------------------------------
    def fetch_closed_bars(self, after_ts_close, now_utc, received_ts=None):
        now = parse_ts(now_utc)
        after = parse_ts(after_ts_close) if after_ts_close is not None else None
        recv = parse_ts(received_ts) if received_ts is not None else now
        self.last_fetch = {"now": iso(now), "after": iso(after) if after else None, "pages": 0,
                           "window": None, "closed_slots": 0, "bars": 0, "minutes_received": 0,
                           "minutes_used": 0, "minutes_outside_slots": 0, "duplicates_identical": 0,
                           "empty_slots": [], "partial_slots": [], "source": self.source}
        slots = self._closed_slots(after, now)
        self.last_fetch["closed_slots"] = len(slots)
        if not slots:
            return []
        start = slots[0][0] if after is None else min(after, slots[0][0])
        end = slots[-1][1] - ONE_MIN               # Alpaca start/end are inclusive
        self.last_fetch["window"] = [iso(start), iso(end)]
        rows, pages = self._minutes(start, end)
        minutes, dups = self._clean(rows)
        self.last_fetch.update(pages=pages, minutes_received=len(rows), duplicates_identical=dups)

        opens = [o for o, _c in slots]
        buckets = [[] for _ in slots]
        starts = [[] for _ in slots]
        outside = 0
        for t in sorted(minutes):
            i = _bisect.bisect_right(opens, t) - 1
            if i >= 0 and t + ONE_MIN <= slots[i][1]:
                buckets[i].append(minutes[t])
                starts[i].append(t)
            else:
                outside += 1
        self.last_fetch["minutes_outside_slots"] = outside

        out, r = [], iso(recv)
        for (o, c), mins, ts in zip(slots, buckets, starts):
            expected = int((c - o).total_seconds() // 60)
            if not mins:
                self.last_fetch["empty_slots"].append([iso(o), iso(c)])
                continue
            vol = sum(m["v"] for m in mins)
            vw = [m for m in mins if isinstance(m["vw"], (int, float)) and not isinstance(m["vw"], bool)]
            vw_vol = sum(m["v"] for m in vw)
            bar = {"ts_open": iso(o), "ts_close": iso(c),
                   "open": mins[0]["o"], "high": max(m["h"] for m in mins),
                   "low": min(m["l"] for m in mins), "close": mins[-1]["c"], "volume": vol,
                   "symbol": self.symbol, "feed": self.feed, "source": self.source,
                   "bar_count_1min": len(mins), "minutes_expected": expected,
                   "partial": len(mins) < expected,
                   "vwap_iex": (sum(m["vw"] * m["v"] for m in vw) / vw_vol) if vw_vol > 0 else None,
                   "received_ts": r, "delivered_ts": r,
                   # local state only: genuine IEX minute starts and opens, never filled or invented
                   "minute_opens": [[iso(t), m["o"]] for t, m in zip(ts[:MINUTE_MARKS], mins[:MINUTE_MARKS])]}
            if bar["partial"]:
                self.last_fetch["partial_slots"].append([iso(o), iso(c)])
            out.append(bar)
        self.last_fetch["minutes_used"] = sum(b["bar_count_1min"] for b in out)
        self.last_fetch["bars"] = len(out)
        return out

    def clock(self):
        p = self._get("trading", "/v2/clock", None)
        if not isinstance(p, dict) or not isinstance(p.get("is_open"), bool):
            raise FeedError("clock response is malformed")
        try:
            return {"timestamp": iso(parse_rfc3339(p.get("timestamp"))), "is_open": p["is_open"],
                    "next_open": iso(parse_rfc3339(p.get("next_open"))),
                    "next_close": iso(parse_rfc3339(p.get("next_close")))}
        except ValueError as exc:
            raise FeedError("clock response time: %s" % exc)

    def calendar_days(self, start, end):
        for d in (start, end):
            if not isinstance(d, str) or not _DAY.match(d):
                raise FeedRefused("calendar dates must be YYYY-MM-DD")
        p = self._get("trading", "/v2/calendar", {"start": start, "end": end})
        if not isinstance(p, list):
            raise FeedError("calendar response is not a list")
        try:
            _alpaca_rows(p)
        except ValueError as exc:
            raise FeedError("calendar response: %s" % exc)
        return [{"date": r["date"], "open": r["open"], "close": r["close"]} for r in p]

    def check_calendar(self, start, end):
        """Differences between Alpaca's /v2/calendar and the local calendar ([] = agree)."""
        return cross_check(self.calendar, self.calendar_days(start, end), start, end)
