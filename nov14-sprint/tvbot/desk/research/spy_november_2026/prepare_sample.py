"""Build the November private study's hourly bars from the vendor's start-stamped minutes.

The caller supplies a private FirstRate SPY sample. No network, orders, credentials or publication.
Only the aggregate quality counts may accompany a public release.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MINUTE = timedelta(minutes=1)
EXPECTED_SHA = "eb450195f7fd679c320233a042b51efd09f23a09e2a39bf067fc06d9fea5d0b8"
START = date(2026, 11, 2)
END = date(2026, 11, 13)

def stamp(ts):
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def prepare(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA:
        raise ValueError("This dated study requires the November 2–13, 2026 sample.")
    minutes = {}
    last = None
    total = 0
    with ZipFile(path) as archive, archive.open("SPY_1min.csv") as raw:
        for row in csv.reader(io.TextIOWrapper(raw, encoding="ascii")):
            ts, o, h, l, c, v = row
            ts = datetime.fromisoformat(ts).replace(tzinfo=ET)
            if last is not None and ts <= last:
                raise ValueError("Duplicate or reversed minute")
            last = ts
            total += 1
            if not (START <= ts.date() <= END):
                raise ValueError("Unexpected date")
            if ts.weekday() >= 5 or not (time(9, 30) <= ts.time() < time(16)):
                continue
            values = [float(x) for x in (o, h, l, c)]
            o, h, l, c = values
            v = int(v)
            if not (all(math.isfinite(x) for x in values) and 0 < l <= min(o,c) <= max(o,c) <= h and v > 0):
                raise ValueError("Bad price or volume in regular hours")
            minutes[ts] = (o,h,l,c,v)
    days = [START+timedelta(days=i) for i in range((END-START).days+1)
            if (START+timedelta(days=i)).weekday() < 5]
    bars, slots = [], []
    for day in days:
        open_ts = datetime.combine(day, time(9,30), ET)
        end = datetime.combine(day, time(16), ET)
        while open_ts < end:
            stop = min(open_ts+60*MINUTE,end)
            timestamps = [open_ts+i*MINUTE for i in range(int((stop-open_ts)/MINUTE))]
            if any(t not in minutes for t in timestamps):
                raise ValueError("Missing minute in session slot starting " + stamp(open_ts))
            rows = [minutes[t] for t in timestamps]
            bars.append(dict(type="bar",symbol="SPY",source="FirstRate historical trade bars",
                             seq=len(bars)+1, ts_open=stamp(open_ts), ts_close=stamp(stop),
                             delivered_ts=stamp(stop), open=rows[0][0], high=max(r[1] for r in rows),
                             low=min(r[2] for r in rows), close=rows[-1][3], volume=sum(r[4] for r in rows)))
            slots.append(dict(day=day.isoformat(),entry_ts=stamp(timestamps[1]),entry=rows[1][0],
                              exit=rows[-1][3], high=max(r[1] for r in rows[1:]),
                              low=min(r[2] for r in rows[1:])))
            open_ts=stop
    counts = dict(start=START.isoformat(),end=END.isoformat(),sessions=len(days),
                  vendor_rows=total,regular_minutes=len(minutes),outside_regular=total-len(minutes),
                  bars=len(bars),closing_30m_slots=len(days),missing_expected_minutes=0,
                  sha256=digest,holdout_start=days[6].isoformat(),holdout_end=days[-1].isoformat())
    return counts,bars,slots

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    a=parser.parse_args()
    print(json.dumps(prepare(a.sample)[0],indent=2))
