"""Bar intake checks for the paper desk.

check_bar(bar, prev_bar, calendar) -> (ok, code, detail)

Codes (first failure wins; detail["codes"] lists every failure found):
  BAD_BAR             missing field, bad number, or high/low inconsistent
  OUT_OF_ORDER        bar does not open after the previous bar (duplicate or backwards)
  STALE_EXCHANGE_TS   received_ts - exchange_ts > max_age_s, however fast the
                      response itself was. With no exchange_ts the bar's ts_close
                      is the exchange time. No received time at all fails closed.
  FUTURE_EXCHANGE_TS  exchange time is later than the received time by more than
                      max_future_skew_s (a clock you cannot trust)
  NOT_CLOSED_AT_RECEIPT    received before its ts_close: the bar was still
                      forming, so its high/low/close are not final. No skew
                      allowance. Same name as session.py's own guard.
  EXCHANGE_TS_BEFORE_CLOSE the bar's exchange_ts is earlier than its ts_close:
                      the exchange stamped a bar that had not closed.
  GAP_IN_SESSION      an in-session bar the calendar expects between prev_bar and
                      bar is missing. Judged by the calendar, not by row number or
                      seq, so a scheduled break, overnight close, weekend or
                      holiday passes.
  CALENDAR_NOT_COVERED the bar's day is outside the calendar's covered range, so
                      holidays there are unknown (ranks above OUT_OF_SESSION)
  OUT_OF_SESSION      the bar opens while the calendar says the market is closed
  ZERO_VOLUME         volume is 0. Such a bar can never justify a fill.

Defaults follow the BTC order-core snapshot rule (snapshotMaxAgeMs 5000,
maxFutureSkewMs 5000): 5 seconds each.
"""
import math

from orders.calendar import parse_ts, iso

DEFAULT_MAX_AGE_S = 5.0
DEFAULT_MAX_FUTURE_SKEW_S = 5.0
REQUIRED_FIELDS = ("ts_open", "ts_close", "open", "high", "low", "close", "volume")
PRIORITY = ("BAD_BAR", "OUT_OF_ORDER", "STALE_EXCHANGE_TS", "FUTURE_EXCHANGE_TS",
            "NOT_CLOSED_AT_RECEIPT", "EXCHANGE_TS_BEFORE_CLOSE", "GAP_IN_SESSION", "CALENDAR_NOT_COVERED", "OUT_OF_SESSION",
            "ZERO_VOLUME")
MAX_GAP_SCAN_DAYS = 400


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def bar_can_fill(bar):
    """A bar may back a mock fill only if it traded."""
    v = bar.get("volume") if isinstance(bar, dict) else None
    return _finite(v) and v > 0


def missing_slots(prev_bar, bar, calendar, minutes=None):
    """Calendar slots that open strictly after prev_bar and strictly before bar."""
    p_open = parse_ts(prev_bar["ts_open"])
    b_open = parse_ts(bar["ts_open"])
    if minutes is None:
        minutes = int(round((parse_ts(bar["ts_close"]) - b_open).total_seconds() / 60.0))
        prev_minutes = int(round((parse_ts(prev_bar["ts_close"]) - p_open).total_seconds() / 60.0))
        # A clipped last bar (early close) is shorter; use the longer of the two.
        minutes = max(minutes, prev_minutes, 1)
    first_day = calendar.local_date(p_open)
    last_day = calendar.local_date(b_open)
    span = (last_day - first_day).days
    if span < 0:
        return []
    if span > MAX_GAP_SCAN_DAYS:
        return [("scan-limit", "more than %d days between bars" % MAX_GAP_SCAN_DAYS)]
    out = []
    import datetime as _dt
    for i in range(span + 1):
        day = first_day + _dt.timedelta(days=i)
        for s_open, s_close in calendar.bar_slots(day, minutes):
            if p_open < s_open < b_open:
                out.append((iso(s_open), iso(s_close)))
    return out


def check_bar(bar, prev_bar, calendar, max_age_s=DEFAULT_MAX_AGE_S, received_ts=None,
              max_future_skew_s=DEFAULT_MAX_FUTURE_SKEW_S, minutes=None):
    """Return (ok, code, detail). code is "OK" when every check passes."""
    codes = []
    detail = {"codes": codes}
    if not isinstance(bar, dict):
        return False, "BAD_BAR", {"codes": ["BAD_BAR"], "msg": "bar is not an object"}
    missing = [k for k in REQUIRED_FIELDS if bar.get(k) is None]
    if missing:
        return False, "BAD_BAR", {"codes": ["BAD_BAR"], "msg": "missing fields", "missing": missing}
    try:
        b_open = parse_ts(bar["ts_open"])
        b_close = parse_ts(bar["ts_close"])
    except (ValueError, TypeError) as exc:
        return False, "BAD_BAR", {"codes": ["BAD_BAR"], "msg": "bad timestamp: %s" % exc}
    nums = [bar[k] for k in ("open", "high", "low", "close", "volume")]
    if not all(_finite(x) for x in nums) or bar["volume"] < 0:
        return False, "BAD_BAR", {"codes": ["BAD_BAR"], "msg": "non-finite or negative number"}
    if b_close <= b_open:
        return False, "BAD_BAR", {"codes": ["BAD_BAR"], "msg": "ts_close is not after ts_open"}
    if bar["high"] < max(bar["open"], bar["close"]) or bar["low"] > min(bar["open"], bar["close"]) \
            or bar["low"] > bar["high"]:
        return False, "BAD_BAR", {"codes": ["BAD_BAR"], "msg": "high/low inconsistent with open/close"}

    # Ordering
    if prev_bar is not None:
        try:
            p_open = parse_ts(prev_bar["ts_open"])
        except (KeyError, ValueError, TypeError):
            p_open = None
        if p_open is not None and b_open <= p_open:
            codes.append("OUT_OF_ORDER")
            detail["prev_ts_open"] = prev_bar.get("ts_open")

    # Freshness: the exchange time, not the response time, decides.
    recv_raw = received_ts if received_ts is not None else bar.get("delivered_ts")
    exch_raw = bar.get("exchange_ts")
    detail["exchange_ts_source"] = "exchange_ts" if exch_raw is not None else "ts_close"
    if exch_raw is None:
        exch_raw = bar["ts_close"]
    try:
        exch = parse_ts(exch_raw)
        recv = parse_ts(recv_raw) if recv_raw is not None else None
    except (ValueError, TypeError) as exc:
        return False, "BAD_BAR", {"codes": ["BAD_BAR"], "msg": "bad freshness timestamp: %s" % exc}
    if recv is None:
        codes.append("STALE_EXCHANGE_TS")
        detail["freshness"] = "no received time; fail closed"
    else:
        age = (recv - exch).total_seconds()
        detail["age_s"] = age
        detail["max_age_s"] = float(max_age_s)
        if age > float(max_age_s):
            codes.append("STALE_EXCHANGE_TS")
        elif age < -float(max_future_skew_s):
            codes.append("FUTURE_EXCHANGE_TS")
        if recv < b_close:
            codes.append("NOT_CLOSED_AT_RECEIPT")
        if exch < b_close:
            codes.append("EXCHANGE_TS_BEFORE_CLOSE")
        if recv < b_close or exch < b_close:
            detail["not_closed"] = {"ts_close": iso(b_close), "received": iso(recv), "exchange": iso(exch)}

    # Gaps, judged by the calendar
    if prev_bar is not None and "OUT_OF_ORDER" not in codes:
        try:
            gaps = missing_slots(prev_bar, bar, calendar, minutes=minutes)
        except (KeyError, ValueError, TypeError) as exc:
            gaps = [("unknown", "could not compare with previous bar: %s" % exc)]
        if gaps:
            codes.append("GAP_IN_SESSION")
            detail["missing_count"] = len(gaps)
            detail["first_missing"] = gaps[0][0]
            detail["last_missing"] = gaps[-1][0]

    covers = getattr(calendar, "covers", None)
    if covers is not None and not covers(calendar.local_date(b_open)):
        codes.append("CALENDAR_NOT_COVERED")
        detail["calendar_covered"] = calendar.describe().get("covered")
    if not calendar.is_open(b_open):
        codes.append("OUT_OF_SESSION")
        detail["calendar"] = calendar.name

    if bar["volume"] == 0:
        codes.append("ZERO_VOLUME")

    if not codes:
        return True, "OK", detail
    for code in PRIORITY:
        if code in codes:
            detail["msg"] = code
            return False, code, detail
    return False, codes[0], detail
