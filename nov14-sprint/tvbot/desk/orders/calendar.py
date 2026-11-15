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
"""
import datetime as _dt
from zoneinfo import ZoneInfo

UTC = _dt.timezone.utc

DEFAULT_TZ = "America/Chicago"
DEFAULT_SESSIONS = (("08:30", "15:00"),)
DEFAULT_CLOSED_DAYS = ("2026-11-26", "2026-12-25")
DEFAULT_EARLY_CLOSES = {"2026-11-27": "12:00", "2026-12-24": "12:00"}
DEFAULT_COVERED = ("2026-10-01", "2026-12-31")
WEEKDAYS = (0, 1, 2, 3, 4)
_DEFAULT = object()


class CalendarNotCovered(ValueError):
    """The holiday table makes no claim about this date."""


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
