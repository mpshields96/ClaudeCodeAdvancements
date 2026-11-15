"""In-process fake of Alpaca's market-data bars endpoints (no network, synthetic bars only).

MockData.handle(method, path, query) -> (status, payload) is what W1's
MockAlpacaTransport calls for origin_key "data". It serves synthetic SPY 1Min
bars in Alpaca's response shape (see RESEARCH.md section 3):

  GET /v2/stocks/SPY/bars   -> {"bars": [{t,o,h,l,c,v,n,vw}], "symbol": "SPY", "next_page_token"}
  GET /v2/stocks/bars       -> {"bars": {"SPY": [...]}, "next_page_token"}   (symbols must be "SPY")

It refuses what the desk must never ask for: a feed other than iex (absent too,
since Alpaca's default is sip), a symbol other than SPY, a timeframe other than
1Min, unknown parameters and non-GET methods, each with a 4xx. Prices follow a
deterministic synthetic path; nothing here is market data.
"""
import datetime as _dt
from zoneinfo import ZoneInfo

from orders.calendar import SessionCalendar, parse_ts, iso

ET = ZoneInfo("America/New_York")
_PARAMS = {"timeframe", "feed", "start", "end", "limit", "adjustment", "sort", "page_token",
           "asof", "currency", "symbols"}
_PAGE_PREFIX = "mock-page-"


def _err(status, message):
    return status, {"code": status * 10000 + 1, "message": "mock: " + message}


def _ts(d, style):
    s = d.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return s + (".000000000Z" if style == "ns" else "Z")


def _key(t):
    return iso(parse_ts(t[:19] + "Z")) if isinstance(t, str) else t


class MockData(object):
    """Synthetic SPY minute bars for the given local days.

    days            local dates (YYYY-MM-DD) to generate regular-session minutes for
    calendar        SessionCalendar deciding the regular session (default NYSE 2026-2027)
    include_extended  also emit pre-market (08:00 ET to the open) and post-market
                    (close to 17:00 ET) minutes, so tests can check they are dropped
    drop_minutes    minute start times (ISO Z) to leave out (no IEX trade that minute)
    ts_style        "s" -> 2026-11-16T14:30:00Z, "ns" -> 2026-11-16T14:30:00.000000000Z
    bars            explicit Alpaca-shape minute bars instead of generated ones
    """

    def __init__(self, days=(), calendar=None, include_extended=False, drop_minutes=(),
                 ts_style="s", base_price=500.0, bars=None):
        self.calendar = calendar or SessionCalendar.nyse_2026_2027()
        self.calls = []
        drop = set(drop_minutes)
        if bars is not None:
            self.bars = [dict(b) for b in bars]
        else:
            self.bars = []
            k = 0
            for day in days:
                for t in self._minutes(day, include_extended):
                    if iso(t) in drop:
                        k += 1
                        continue
                    self.bars.append(self._bar(t, k, base_price, ts_style))
                    k += 1
        self.bars.sort(key=lambda b: _key(b["t"]))

    def _minutes(self, day, include_extended):
        w = self.calendar.windows(day)
        if not w:
            return []
        start, end = w[0][0], w[-1][1]
        if include_extended:
            d = _dt.date.fromisoformat(str(day))
            pre = _dt.datetime(d.year, d.month, d.day, 8, 0, tzinfo=ET).astimezone(_dt.timezone.utc)
            post = _dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=ET).astimezone(_dt.timezone.utc)
            start, end = min(start, pre), max(end, post)
        out, t, step = [], start, _dt.timedelta(minutes=1)
        while t < end:
            out.append(t)
            t += step
        return out

    @staticmethod
    def _bar(t, k, base, style):
        o = round(base + 0.01 * (k % 37) - 0.005 * (k % 11), 4)
        c = round(o + 0.02 * ((k % 5) - 2), 4)
        h = round(max(o, c) + 0.03, 4)
        lo = round(min(o, c) - 0.03, 4)
        return {"t": _ts(t, style), "o": o, "h": h, "l": lo, "c": c,
                "v": 100 + (k * 7) % 400, "n": 5 + k % 9, "vw": round((o + h + lo + c) / 4.0, 4)}

    def handle(self, method, path, query=None):
        q = dict(query or {})
        self.calls.append((method, path, dict(q)))
        if path == "/v2/stocks/SPY/bars":
            multi = False
        elif path == "/v2/stocks/bars":
            multi = True
        elif path.startswith("/v2/stocks/") and path.endswith("/bars"):
            return _err(403, "only SPY is served")
        else:
            return _err(404, "path not served by the mock data host")
        if method != "GET":
            return _err(405, "only GET is allowed")
        unknown = sorted(set(q) - _PARAMS)
        if unknown:
            return _err(422, "unknown parameters %s" % ",".join(unknown))
        if q.get("feed") != "iex":
            return _err(403, "only the free iex feed is served (got %r)" % (q.get("feed"),))
        if multi:
            if str(q.get("symbols", "")) != "SPY":
                return _err(403, "only SPY is served")
        elif "symbols" in q:
            return _err(422, "symbols is not a parameter of the single-symbol endpoint")
        if q.get("timeframe") != "1Min":
            return _err(422, "the mock serves timeframe=1Min only")
        try:
            limit = int(q.get("limit", 1000))
            start = parse_ts(q["start"]) if q.get("start") else None
            end = parse_ts(q["end"]) if q.get("end") else None
        except (TypeError, ValueError) as exc:
            return _err(422, "bad parameter: %s" % exc)
        if limit < 1 or limit > 10000:
            return _err(422, "limit must be 1..10000")
        if q.get("sort", "asc") != "asc":
            return _err(422, "the mock serves sort=asc only")
        offset = 0
        token = q.get("page_token")
        if token:
            if not str(token).startswith(_PAGE_PREFIX) or not str(token)[len(_PAGE_PREFIX):].isdigit():
                return _err(422, "bad page_token")
            offset = int(str(token)[len(_PAGE_PREFIX):])
        sel = []
        for b in self.bars:
            t = parse_ts(_key(b["t"]))
            if start is not None and t < start:
                continue
            if end is not None and t > end:       # start and end are inclusive
                continue
            sel.append(b)
        page = [dict(b) for b in sel[offset:offset + limit]]
        nxt = _PAGE_PREFIX + str(offset + limit) if offset + limit < len(sel) else None
        if multi:
            return 200, {"bars": {"SPY": page}, "next_page_token": nxt}
        return 200, {"bars": page, "symbol": "SPY", "next_page_token": nxt}
