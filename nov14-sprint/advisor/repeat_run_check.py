# Advisor check B4 (made-up prices). Usage: python3 -I repeat_run_check.py <scratch copy of tvbot> [slide]
# slide 0: correct (35 new bars). slide 7: 28 accepted, 7 lost. slide 35: 0 accepted. Feed still "accepted".
import sys, os, json, math, tempfile
from datetime import datetime, timedelta
TV = sys.argv[1]  # a scratch COPY of nov14-sprint/tvbot, never the live folder
SLIDE = int(sys.argv[2]) if len(sys.argv) > 2 else 0  # rows dropped from the start of run 2
sys.path.insert(0, os.path.join(TV, "bot"))
import real_feed, engine
work = tempfile.mkdtemp(dir=os.path.dirname(TV))
real = os.path.join(work, "real"); os.makedirs(real)
state = os.path.join(work, "paper")
def rows_until(end):
    rows, prev, i = [], 100.0, 0
    day = datetime(2026, 10, 12)
    while day <= end:
        if day.weekday() < 5:
            first = day.replace(hour=13 if day < datetime(2026, 11, 1) else 14, minute=30)
            for k in range(7):
                close = round(100.0 + 3.0*math.sin(i/9.0) + 0.02*i, 2)
                hi, lo = round(max(prev, close)+0.1, 2), round(min(prev, close)-0.1, 2)
                rows.append("%s,%.2f,%.2f,%.2f,%.2f,%d" % ((first+timedelta(hours=k)).strftime("%Y-%m-%d %H:%M:%S"), prev, hi, lo, close, 1000+i))
                prev, i = close, i+1
        day += timedelta(days=1)
    return rows
tpl = json.load(open(os.path.join(TV, "config", "source_template_twelvedata.json")))
tpl.update(terms_quote="Made-up quote for an advisor scratch check.", approved_by="Scratch Test Person", approved_utc="2026-11-13T00:00:00Z")
src = os.path.join(real, "source.json"); json.dump(tpl, open(src, "w"))
CLOCK = "2026-11-15T05:00:00Z"
for label, end in (("run1 to Nov 6", datetime(2026, 11, 6)), ("run2 to Nov 13 (longer file, same state)", datetime(2026, 11, 13))):
    with open(os.path.join(real, tpl["csv_path"]), "w") as fh:
        fh.write("datetime,open,high,low,close,volume\n" + "\n".join(rows_until(end)[(SLIDE if "run2" in label else 0):]) + "\n")
    conv = real_feed.convert(src, real, CLOCK)
    e = engine.Engine(as_of=CLOCK, state_dir=state, permitted_sources=conv["permitted"])
    try:
        res = e.process_feed(conv["feed"])
        print(label, "| rows", conv["report"]["rows"], "| accepted", res["accepted"], "| code", res.get("code"), "| bars_accepted", res.get("bars_accepted"), "| reasons", str(res.get("reasons"))[:160])
    except Exception as exc:
        print(label, "| EXCEPTION", type(exc).__name__, str(exc)[:200])
