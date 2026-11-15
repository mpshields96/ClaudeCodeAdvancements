"""Dated, explicit (never scheduled) NFL schedule and free line intake."""
from datetime import date,datetime,timedelta
import csv,hashlib,io,json,os,tempfile
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
import sunday_quotes as oq
ROOT=Path(__file__).resolve().parent/"weekly_inputs"
CENTRAL=ZoneInfo("America/Chicago")
def day_value(text):
    day=date.fromisoformat(str(text))
    if day.weekday()!=6 or day<date(2026,11,22) or day.year>2100:raise ValueError("Choose a Sunday after the frozen November 15 edition.")
    return day
def schedule(day):
    url="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates="+day.strftime("%Y%m%d")
    with urlopen(Request(url,headers={"Accept":"application/json"}),timeout=12) as r:
        data=json.load(r)
    if not isinstance(data,dict) or not isinstance(data.get("events"),list):raise ValueError("Schedule source returned no event collection.")
    if not any(x.get("slug")=="nfl" for x in data.get("leagues",[])):raise ValueError("Schedule is not an NFL scoreboard.")
    data["_source"]={"source_url":url,"observed_utc":oq.stamp(oq.utc()),"slate_date":str(day)}
    return data
HISTORY_URL="https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
def save_team_history(folder):
    """Store the actual public data used by each future price edition. Never replace the issued data."""
    with urlopen(Request(HISTORY_URL,headers={"Accept":"text/csv"}),timeout=15) as resp:
        raw=resp.read(16_000_001)
    if len(raw)>16_000_000:raise ValueError("Public team history exceeds size bound.")
    fields=set((csv.DictReader(io.StringIO(raw[:10000].decode('utf-8-sig'))).fieldnames or []))
    if not {"game_id","season","week","gameday","home_team","away_team","away_score","home_score"}.issubset(fields):raise ValueError("Public team history schema changed.")
    now=oq.utc();sha=hashlib.sha256(raw).hexdigest();base=folder/"football_history"/(oq.stamp(now).replace(":","")+"-"+sha[:12]);base.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("wb",dir=base,delete=False) as tmp:tmp.write(raw)
    os.replace(tmp.name,base/"games.csv")
    oq.atomic(base/"MANIFEST.json",{"files":[{"path":"games.csv","url":HISTORY_URL,"sha256":sha,"bytes":len(raw),"retrieved_at_utc":oq.stamp(now),"kind":"nflverse team schedule and outcomes"}]})
    return base.name

def history_for(day,edition):
    """Only the exact snapshot named by this dated price capture may replace the bundled baseline."""
    folder=ROOT/str(day);name=edition["captured_utc"].replace(":","")+".json"
    cap=folder/"captures"/name
    if not cap.is_file() or oq.digest(cap)!=edition["sha256"]:raise ValueError("Cannot verify the dated price edition.")
    row=oq.read(cap);ref=row.get("team_history")
    if not ref:return None
    import re
    if not isinstance(ref,str) or not re.fullmatch(r"[0-9TZ-]+-[0-9a-f]{12}",ref):raise ValueError("Invalid dated team history reference.")
    return folder/"football_history"/ref/"games.csv"

def acquire(day,*,fresh=False,detailed=False,include_history=False,root=ROOT,source=schedule,feed=oq.odds_feed.capture):
    day=day_value(day);folder=Path(root)/str(day);folder.mkdir(parents=True,exist_ok=True)
    with oq.lock(folder):
        sp=folder/"schedule.json"; op=folder/"odds.json"
        if not sp.exists(): oq.atomic(sp,source(day))
        sched=oq.read(sp)
        valid=[e for e in sched["events"] if oq.when(e["date"]).astimezone(CENTRAL).date()==day]
        if not valid:raise ValueError("No Sunday NFL games have been independently scheduled for this date.")
        if op.is_file():
            old=oq.read(op)
            same_coverage=(not detailed or bool(old.get("detailed_requested")) or bool(old.get("event_odds")))
            if same_coverage and (not fresh or 0<=(oq.utc()-oq.when(old["captured_utc"])).total_seconds()<900):return folder,old,0
            # Kickoffs and neutral-site designations can change between editions.
            if fresh and (oq.utc()-oq.when(sched["_source"]["observed_utc"])).total_seconds()>=900:
                sched=source(day)
                valid=[e for e in sched["events"] if oq.when(e["date"]).astimezone(CENTRAL).date()==day]
                if not valid:raise ValueError("No verified games on the updated Sunday schedule.")
        if all(oq.when(e["date"])<=oq.utc() for e in valid):raise ValueError("All games on this slate have already started.")
        history=None;history_problem=None
        if include_history:
            try:history=save_team_history(folder)
            except (OSError,ValueError,UnicodeError):history_problem="Updated public team scores were unavailable; the dated screen uses the bundled baseline."
        new=feed(day,detailed)
        if new.get("day")!=str(day) or not isinstance(new.get("games"),list) or not new.get("observations"):raise ValueError("The dated source capture could not be verified.")
        # Keep each source edition. A review pins its own bytes, and cannot migrate to the next edition.
        new["detailed_requested"]=bool(detailed)
        if history:new["team_history"]=history
        if history_problem:new["team_history_warning"]=history_problem
        dst=folder/"captures"/(new["captured_utc"].replace(":","")+".json")
        if not dst.exists():oq.atomic(dst,new)
        oq.atomic(sp,sched);oq.atomic(op,new); cost=sum(o["used_last"] for o in new["observations"])
        return folder,new,cost
if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument("date");ap.add_argument("--refresh",action="store_true")
    a=ap.parse_args();f,x,c=acquire(a.date,fresh=a.refresh);print(f"{f}: {len(x['games'])} games offered, {c} free credits used, {x['observations'][-1]['remaining']} left.")
