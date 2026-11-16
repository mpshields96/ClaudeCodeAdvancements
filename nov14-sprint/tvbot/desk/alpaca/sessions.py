"""Which Alpaca trading session a moment falls in, and whether this desk supports it.

Alpaca's sessions (docs.alpaca.markets, "24/5 Trading" and "Orders at Alpaca", read 2026-11-16):
- Overnight      20:00 ET Sunday to 04:00 ET Friday (limit orders only, day/gtc, filled on Blue Ocean ATS;
                 data from feed=overnight or feed=boats, not the free IEX feed this desk uses)
- Pre-market     04:00-09:30 ET
- Regular        09:30-16:00 ET (the desk's NYSE calendar, which also knows holidays and early closes)
- After-hours    16:00-20:00 ET
Extended hours need extended_hours=true on a limit order; stop orders are not eligible. An order that is
not eligible, sent outside regular hours, is queued for the next trading day.

THIS DESK SUPPORTS REGULAR HOURS ONLY. It never sends extended_hours, uses day orders, refuses bars
outside the calendar (orders/intake OUT_OF_SESSION) and refuses the overnight and boats feeds. Every other
session is labeled here as not supported, with what would happen to an order sent then.

The holiday schedule of the overnight session is not modeled; it is refused like every other
non-regular session, so a mislabel cannot make the desk trade.
"""
import datetime as _dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
REGULAR, PRE_MARKET, AFTER_HOURS, OVERNIGHT, CLOSED = (
    "REGULAR", "PRE_MARKET", "AFTER_HOURS", "OVERNIGHT", "CLOSED")
SUPPORTED = (REGULAR,)

_LABELS = {
    REGULAR: "Regular hours (supported)",
    PRE_MARKET: "Pre-market 04:00-09:30 ET: NOT supported by this desk",
    AFTER_HOURS: "After-hours 16:00-20:00 ET: NOT supported by this desk",
    OVERNIGHT: "Overnight 24/5 session 20:00-04:00 ET: NOT supported by this desk (never traded silently)",
    CLOSED: "Market closed",
}
_QUEUE_NOTE = ("an order sent now (a day order without extended_hours) would wait for the next regular "
               "session; the desk does not send new entries now")


def classify(ts, calendar):
    """{"session", "desk_supported", "label", "note"} for an aware UTC datetime."""
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    if calendar.is_open(ts):
        return {"session": REGULAR, "desk_supported": True, "label": _LABELS[REGULAR], "note": ""}
    et = ts.astimezone(ET)
    wd, minutes = et.weekday(), et.hour * 60 + et.minute          # Monday = 0
    try:
        trading_day = calendar.is_trading_day(calendar.local_date(ts))
    except Exception:                # a date outside the calendar's table: fail closed (not a trading day)
        trading_day = False
    if (minutes >= 20 * 60 and wd in (6, 0, 1, 2, 3)) or (minutes < 4 * 60 and wd in (0, 1, 2, 3, 4)):
        name = OVERNIGHT
    elif trading_day and 4 * 60 <= minutes < 9 * 60 + 30:
        name = PRE_MARKET
    elif trading_day and minutes < 20 * 60 and minutes >= 9 * 60 + 30:
        name = AFTER_HOURS          # after the (possibly early) regular close
    else:
        name = CLOSED
    return {"session": name, "desk_supported": False, "label": _LABELS[name],
            "note": _QUEUE_NOTE if name != CLOSED else "no Alpaca session; orders would wait for the next open"}


def status_field(ts, calendar):
    """The read-only UI field `session_window` (see NIGHT_WB_STATUS.md)."""
    row = classify(ts, calendar)
    row["at_utc"] = ts.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return row
