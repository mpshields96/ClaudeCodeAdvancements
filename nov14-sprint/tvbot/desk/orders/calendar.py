"""Session calendar for the paper desk.

SessionCalendar answers two questions on a simulated clock:
  is_open(ts)               is the market in session at this instant?
  expected_bars(day, mins)  which bars should exist for this local day?

Times are kept in the calendar's zone (default America/Chicago) so DST is
handled by zoneinfo. Sessions are local wall-clock windows on trading
weekdays. A gap between two windows (a scheduled break) or between days
(overnight, weekend, holiday) is not "expected" and so is never a gap.

Default profile: US equity regular hours in Central time (08:30-15:00).
Its table: 2026-11-26 (Thanksgiving) and 2026-12-25 (Christmas) closed;
2026-11-27 and 2026-12-24 close early at 12:00 CT (13:00 ET). Source: the
Codex QA brief of 2026-11-15 and NYSE's published 2026 schedule, not
re-fetched by this code. The table is only claimed for 2026-10-01..2026-12-31
(DEFAULT_COVERED). A date outside it is refused visibly: windows(),
is_trading_day() and session_bounds() raise CalendarNotCovered, is_open()
answers False (fail closed) and next_open() returns None. Extend the table
and DEFAULT_COVERED together, from the exchange's own published calendar.
Calendars you build yourself (custom tz/sessions/closed_days, or
fixture_profile) are uncovered-by-default, i.e. unlimited, unless you pass
covered=(first_day, last_day).

fixture_profile(): the synthetic tvbot fixtures put seven hourly bars at
14:30Z..20:30Z on every weekday with no holidays and no DST shift. Use that
profile when replaying tvbot/fixtures/normal_bars.jsonl, or the default
Chicago calendar will flag those bars as out of session.

nyse_2026_2027(): the same Central-time regular session with NYSE's full
published 2026 and 2027 holiday and early-close table, covered
2026-01-01..2027-12-31 (NYSE_COVERED). Source: https://www.nyse.com/markets/hours-calendars,
read 2026-11-15 (cited in alpaca/RESEARCH.md section 5). It agrees with the
default profile on 2026-10-01..2026-12-31; the default keeps its narrower range.
as_alpaca_rows() renders a profile as Alpaca GET /v2/calendar rows (ET HH:MM)
and cross_check(calendar, rows) reports where Alpaca's rows and the local table
disagree, without guessing for uncovered dates.
"""
import datetime as _dt
import re as _re
from zoneinfo import ZoneInfo

UTC = _dt.timezone.utc

DEFAULT_TZ = "America/Chicago"
DEFAULT_SESSIONS = (("08:30", "15:00"),)
DEFAULT_CLOSED_DAYS = ("2026-11-26", "2026-12-25")
DEFAULT_EARLY_CLOSES = {"2026-11-27": "12:00", "2026-12-24": "12:00"}
DEFAULT_COVERED = ("2026-10-01", "2026-12-31")
WEEKDAYS = (0, 1, 2, 3, 4)
_DEFAULT = object()

# NYSE published schedule (https://www.nyse.com/markets/hours-calendars, read 2026-11-15).
NYSE_CLOSED_DAYS = (
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
)
# 1:00 p.m. ET early closes, written in Central time like the default profile.
NYSE_EARLY_CLOSES = {"2026-11-27": "12:00", "2026-12-24": "12:00", "2027-11-26": "12:00"}
NYSE_COVERED = ("2026-01-01", "2027-12-31")
ALPACA_CALENDAR_TZ = "America/New_York"   # zone of /v2/calendar open/close [UNVERIFIED, see RESEARCH.md]


class CalendarNotCovered(ValueError):
    """The holiday table makes no claim about this date."""


_FRAC = _re.compile(r"^(.*T\d{2}:\d{2}:\d{2}\.)(\d+)(.*)$")


def parse_ts(ts):
    """Return an aware UTC datetime from an ISO string, epoch seconds or aware datetime.

    A naive datetime or a string without a zone is refused: guessing a zone
    is how a session boundary moves by an hour.
    """
    if isinstance(ts, bool):
        raise TypeError("timestamp cannot be a bool")
    if isinstance(ts, _dt.datetime):
        if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
            raise ValueError("naive datetime refused")
        return ts.astimezone(UTC)
    if isinstance(ts, (int, float)):
        return _dt.datetime.fromtimestamp(float(ts), UTC)
    if isinstance(ts, str):
        s = ts.strip()
        if s.endswith("Z") or s.endswith("z"):
            s = s[:-1] + "+00:00"
        # Alpaca sends RFC 3339 with 0-9 fraction digits; Python 3.9's fromisoformat takes exactly
        # 3 or 6. Use six: truncate extra digits (never rounds into the next second or day), pad short.
        m = _FRAC.match(s)
        if m:
            s = m.group(1) + m.group(2)[:6].ljust(6, "0") + m.group(3)
        d = _dt.datetime.fromisoformat(s)
        if d.tzinfo is None:
            raise ValueError("timestamp without a zone refused: %r" % (ts,))
        return d.astimezone(UTC)
    raise TypeError("unsupported timestamp type: %r" % (type(ts).__name__,))


def iso(d):
    """Format an aware datetime as YYYY-MM-DDTHH:MM:SSZ (the fixture format)."""
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hm(text):
    """'HH:MM' -> minutes after local midnight. '24:00' is allowed as an end."""
    hh, mm = str(text).split(":")
    minutes = int(hh) * 60 + int(mm)
    if minutes < 0 or minutes > 24 * 60 or int(mm) >= 60:
        raise ValueError("bad local time %r" % (text,))
    return minutes


def _date(day):
    if isinstance(day, _dt.datetime):
        raise TypeError("pass a date or 'YYYY-MM-DD', not a datetime")
    if isinstance(day, _dt.date):
        return day
    return _dt.date.fromisoformat(str(day))


class SessionCalendar(object):
    """Trading calendar on local wall-clock windows. No wall clock is read here."""

    def __init__(self, tz=DEFAULT_TZ, sessions=DEFAULT_SESSIONS,
                 closed_days=DEFAULT_CLOSED_DAYS, early_closes=None,
                 weekdays=WEEKDAYS, name=None, covered=_DEFAULT):
        self.tz_name = tz
        self.tz = ZoneInfo(tz)
        parsed = []
        for start, end in sessions:
            s, e = _hm(start), _hm(end)
            if e <= s:
                raise ValueError("session %s-%s must end after it starts (no overnight windows)" % (start, end))
            parsed.append((s, e))
        parsed.sort()
        for (s1, e1), (s2, _e2) in zip(parsed, parsed[1:]):
            if s2 < e1:
                raise ValueError("sessions overlap")
        self.sessions = tuple(parsed)
        self.closed_days = frozenset(_date(d) for d in closed_days)
        if early_closes is None:
            early_closes = DEFAULT_EARLY_CLOSES if tz == DEFAULT_TZ and sessions == DEFAULT_SESSIONS else {}
        self.early_closes = dict((_date(d), _hm(t)) for d, t in early_closes.items())
        self.weekdays = frozenset(int(w) for w in weekdays)
        if covered is _DEFAULT:
            stock = tz == DEFAULT_TZ and sessions == DEFAULT_SESSIONS and closed_days is DEFAULT_CLOSED_DAYS
            covered = DEFAULT_COVERED if stock else None
        if covered is not None:
            first, last = _date(covered[0]), _date(covered[1])
            if last < first:
                raise ValueError("covered range ends before it starts")
            covered = (first, last)
        self.covered = covered
        self.name = name or ("%s %s" % (tz, ",".join("%s-%s" % w for w in sessions)))

    @classmethod
    def fixture_profile(cls):
        """Calendar matching tvbot/fixtures: 14:30Z-21:30Z weekdays, no holidays."""
        return cls(tz="UTC", sessions=(("14:30", "21:30"),), closed_days=(),
                   early_closes={}, name="fixture-utc-1430-2130")

    @classmethod
    def nyse_2026_2027(cls):
        """US equity regular hours (08:30-15:00 CT) with NYSE's 2026-2027 table."""
        return cls(tz=DEFAULT_TZ, sessions=DEFAULT_SESSIONS, closed_days=NYSE_CLOSED_DAYS,
                   early_closes=NYSE_EARLY_CLOSES, covered=NYSE_COVERED,
                   name="NYSE regular hours 2026-2027 (CT)")

    def as_alpaca_rows(self, start, end):
        """Trading days start..end as Alpaca /v2/calendar rows: {date, open, close} in ET HH:MM."""
        et = ZoneInfo(ALPACA_CALENDAR_TZ)
        d, last = _date(start), _date(end)
        out = []
        while d <= last:
            w = self.windows(d)
            if w:
                out.append({"date": d.isoformat(),
                            "open": w[0][0].astimezone(et).strftime("%H:%M"),
                            "close": w[-1][1].astimezone(et).strftime("%H:%M")})
            d += _dt.timedelta(days=1)
        return out

    def describe(self):
        return {
            "name": self.name,
            "tz": self.tz_name,
            "sessions": ["%02d:%02d-%02d:%02d" % (s // 60, s % 60, e // 60, e % 60) for s, e in self.sessions],
            "closed_days": sorted(d.isoformat() for d in self.closed_days),
            "early_closes": dict((d.isoformat(), "%02d:%02d" % (m // 60, m % 60))
                                 for d, m in sorted(self.early_closes.items())),
            "covered": None if self.covered is None else [d.isoformat() for d in self.covered],
        }

    def covers(self, day):
        """True when the holiday table makes a claim about this local day."""
        if self.covered is None:
            return True
        d = _date(day)
        return self.covered[0] <= d <= self.covered[1]

    def _require(self, d):
        if not self.covers(d):
            raise CalendarNotCovered("%s: calendar %r only covers %s..%s; refusing to guess holidays"
                                     % (d.isoformat(), self.name, self.covered[0].isoformat(),
                                        self.covered[1].isoformat()))

    def _local(self, day, minutes):
        base = _dt.datetime(day.year, day.month, day.day, tzinfo=self.tz)
        if minutes >= 24 * 60:
            nxt = day + _dt.timedelta(days=1)
            return _dt.datetime(nxt.year, nxt.month, nxt.day, tzinfo=self.tz).astimezone(UTC)
        local = base.replace(hour=minutes // 60, minute=minutes % 60)
        return local.astimezone(UTC)

    def is_trading_day(self, day):
        d = _date(day)
        self._require(d)
        return d.weekday() in self.weekdays and d not in self.closed_days

    def windows(self, day):
        """[(start_utc, end_utc)] for a local day; [] when closed."""
        d = _date(day)
        if not self.is_trading_day(d):
            return []
        cut = self.early_closes.get(d)
        out = []
        for s, e in self.sessions:
            if cut is not None:
                e = min(e, cut)
            if e <= s:
                continue
            out.append((self._local(d, s), self._local(d, e)))
        return out

    def session_bounds(self, day):
        """(open_utc, close_utc) of a local day's first and last window; None when closed.

        An early close is already applied. A scheduled break between windows is
        inside these bounds, so use windows() or is_open() for in-session checks.
        Raises CalendarNotCovered outside the covered range.
        """
        w = self.windows(day)
        if not w:
            return None
        return (w[0][0], w[-1][1])

    def local_date(self, ts):
        return parse_ts(ts).astimezone(self.tz).date()

    def is_open(self, ts):
        u = parse_ts(ts)
        d = u.astimezone(self.tz).date()
        if not self.covers(d):
            return False     # fail closed; windows() raises with the reason
        for start, end in self.windows(d):
            if start <= u < end:
                return True
        return False

    def bar_slots(self, day, minutes):
        """[(open_utc, close_utc)] datetimes; bars anchor on each window's start."""
        minutes = int(minutes)
        if minutes <= 0:
            raise ValueError("bar minutes must be positive")
        step = _dt.timedelta(minutes=minutes)
        out = []
        for start, end in self.windows(day):
            t = start
            while t < end:
                close = min(t + step, end)
                out.append((t, close))
                t = t + step
        return out

    def expected_bars(self, day, minutes):
        """[(ts_open, ts_close)] as fixture-format strings for one local day."""
        return [(iso(a), iso(b)) for a, b in self.bar_slots(day, minutes)]

    def next_open(self, ts, max_days=14):
        """First session start at or after ts, or None within max_days.

        Also None when the search reaches a day the calendar does not cover.
        """
        u = parse_ts(ts)
        d = u.astimezone(self.tz).date()
        for i in range(max_days + 1):
            day = d + _dt.timedelta(days=i)
            if not self.covers(day):
                return None
            for start, end in self.windows(day):
                if end > u:
                    return max(start, u) if start <= u else start
        return None


_HHMM = _re.compile(r"^\d{2}:\d{2}$")


def _alpaca_rows(rows):
    """Validate Alpaca /v2/calendar rows; return {date: (open, close)} and duplicate dates."""
    if not isinstance(rows, list):
        raise ValueError("calendar rows must be a list")
    seen, dups = {}, []
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError("calendar row is not an object: %r" % (r,))
        try:
            d = _dt.date.fromisoformat(str(r["date"]))
            op, cl = str(r["open"]), str(r["close"])
        except (KeyError, ValueError) as exc:
            raise ValueError("bad calendar row %r: %s" % (r, exc))
        if not (_HHMM.match(op) and _HHMM.match(cl)):
            raise ValueError("calendar row times must be HH:MM: %r" % (r,))
        _hm(op), _hm(cl)
        if d in seen:
            dups.append(d)
        seen[d] = (op, cl)
    return seen, dups


def cross_check(calendar, rows, start=None, end=None):
    """Compare Alpaca GET /v2/calendar rows with a local SessionCalendar.

    Returns a list of differences (empty when they agree), each
    {"date", "kind", "local", "alpaca"} where kind is one of
    not_covered, missing_at_alpaca, closed_locally, open_differs, close_differs,
    duplicate_row. Alpaca times are read as US Eastern. Dates the local table does
    not cover are reported as not_covered, never guessed. The range defaults to
    the first..last row date. Raises ValueError on malformed rows.
    """
    by_date, dups = _alpaca_rows(rows)
    if start is None and end is None and not by_date:
        return []
    first = _date(start) if start is not None else min(by_date)
    last = _date(end) if end is not None else max(by_date)
    et = ZoneInfo(ALPACA_CALENDAR_TZ)
    out = [{"date": d.isoformat(), "kind": "duplicate_row", "local": None, "alpaca": by_date[d]}
           for d in sorted(set(dups))]
    d = first
    while d <= last:
        row = by_date.get(d)
        if not calendar.covers(d):
            if row is not None or d.weekday() < 5:
                out.append({"date": d.isoformat(), "kind": "not_covered", "local": None,
                            "alpaca": list(row) if row else None})
            d += _dt.timedelta(days=1)
            continue
        w = calendar.windows(d)
        local = None
        if w:
            local = [w[0][0].astimezone(et).strftime("%H:%M"), w[-1][1].astimezone(et).strftime("%H:%M")]
        if local and row is None:
            out.append({"date": d.isoformat(), "kind": "missing_at_alpaca", "local": local, "alpaca": None})
        elif row is not None and not local:
            out.append({"date": d.isoformat(), "kind": "closed_locally", "local": None, "alpaca": list(row)})
        elif row is not None:
            if row[0] != local[0]:
                out.append({"date": d.isoformat(), "kind": "open_differs", "local": local, "alpaca": list(row)})
            if row[1] != local[1]:
                out.append({"date": d.isoformat(), "kind": "close_differs", "local": local, "alpaca": list(row)})
        d += _dt.timedelta(days=1)
    return out
