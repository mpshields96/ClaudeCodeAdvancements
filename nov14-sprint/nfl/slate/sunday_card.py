"""Load the frozen decision and immutable price snapshot. No network access."""
from collections import Counter
from datetime import timedelta
from pathlib import Path
import json
from zoneinfo import ZoneInfo
import sunday_quotes as oq
from compare_books import contract_prices
S=Path(__file__).resolve().parent
L=oq.LIVE
CT=ZoneInfo("America/Chicago")
KEY=("event_id","market","subject","side","point")
def key(c): return tuple(c[k] for k in KEY)
def central(s): return oq.when(s).astimezone(CT).strftime("%a %-I:%M %p CT")
def window(k):
    h=oq.when(k).astimezone(CT).hour
    return "early" if h<14 else "late" if h<18 else "night"
def load_frozen(l=L):
    capture=l/"sunday-odds.json"; decisions=oq.read(l/"Final_Decisions.json")
    base=oq.read(l/"Sunday_Card.json"); snapshot=oq.read(capture)
    if not (oq.digest(capture)==decisions["capture_sha256"]==base["snapshot_sha256"]):
        raise ValueError("The decisions and the saved slate do not match.")
    taken=oq.when(decisions["decided_utc"])
    if oq.when(base["issued_utc"])!=taken or not oq.when(snapshot["captured_utc"])<=taken<=oq.utc():
        raise ValueError("Decision timestamp does not match the issued card.")
    if not isinstance(decisions["calls"],list) or not isinstance(decisions.get("window_notes",{}),dict):
        raise ValueError("Invalid release decision.")
    original={key(c):c for c in base["calls"]}
    if len(original)!=len(base["calls"]) or set(original)!={key(d) for d in decisions["calls"]}:
        raise ValueError("The selected contracts differ from the issued card.")
    games={g["id"]:g for g in snapshot["games"]}
    if len(games)!=len(snapshot["games"]) or len(games)!=12 or snapshot["day"]!="2026-11-15":
        raise ValueError("The frozen Sunday slate is incomplete.")
    if taken>=min(oq.when(g["commence_time"]) for g in games.values()):
        raise ValueError("This card was not frozen before kickoff.")
    rows={key(r):r for r in contract_prices(snapshot)}
    count=Counter(); used=set(); calls=[]
    for d in decisions["calls"]:
        c=dict(original[key(d)])
        r=rows.get(key(d)); g=games.get(c["event_id"])
        if not r or not g or c["kickoff"]!=g["commence_time"] or c["minimum_price"]!=d["minimum_price"]:
            raise ValueError("Kickoff, floor or frozen contract changed.")
        oq.identity(c)
        if (not d["condition"].strip() or not d["rationale"].strip() or not d["risk"].strip()
           or d["condition"]!=c["condition"] or c["observed_book"] not in r["all_prices"]
           or c["observed_price"]!=r["all_prices"][c["observed_book"]]["price"]
           or not oq.price(c["observed_price"]) or oq.payout(c["observed_price"])<oq.payout(c["minimum_price"])):
            raise ValueError("Missing judgment or unverifiable original odds.")
        w=window(c["kickoff"]); count[w]+=1
        if count[w]>2: raise ValueError("Two-call window limit exceeded.")
        used.add(c["event_id"])
        c.update(rationale=d["rationale"],risk=d["risk"],sources=d.get("sources",[]),bucket=w)
        calls.append(c)
    card=dict(base,calls=calls,window_notes=decisions.get("window_notes",{}))
    return card,snapshot
def engine():
    p=S/"results/sunday_20261115_selections.json"
    return oq.read(p) if p.exists() else None
def full_snapshot(root, *, force=False, clock=oq.utc, capture=oq.odds_feed.capture):
    """Archive a separate manual detailed refresh; never mutate the decision snapshot."""
    import datetime
    root=Path(root)
    with oq.lock(root):
        now=clock(); first=oq.read(L/"sunday-odds.json")
        candidates=sorted(root.glob("manual-slate-*.json"),reverse=True)
        latest=oq.read(candidates[0]) if candidates else first
        age=(now-oq.when(latest["captured_utc"])).total_seconds()
        if 0<=age<(30 if force else 900):
            return latest,"reused",0
        if not any(oq.when(g["commence_time"])>now for g in first["games"]):
            return latest,"all games started",0
        new=capture(datetime.date.fromisoformat(first["day"]),True)
        if not new.get("observations") or not isinstance(new.get("games"),list):
            raise ValueError("Unverified slate refresh")
        dest=root/("manual-slate-"+now.strftime("%Y%m%dT%H%M%S%fZ")+".json")
        oq.atomic(dest,new)
        return new,"live",sum(x["used_last"] for x in new["observations"])

def released(l=L,selection_file=None):
    card,snapshot=load_frozen(l)
    eng=oq.read(selection_file or S/"results/sunday_20261115_selections.json")
    if (eng.get("capture_sha256")!=card["snapshot_sha256"] or not eng.get("rules_verified")
        or oq.when(eng["decided_utc"])!=oq.when(card["issued_utc"])):
        raise ValueError("The picker output is not the verified release for this price snapshot.")
    by={key(c):c for c in eng["calls"]}
    if len(by)!=len(eng["calls"]) or set(by)!={key(c) for c in card["calls"]}:
        raise ValueError("The picker and the frozen decision disagree.")
    for c in card["calls"]:
        e=by[key(c)]
        if (e["minimum_price"]!=c["minimum_price"] or e["kickoff"]!=c["kickoff"] or e["price"]!=c["observed_price"]
            or e["condition"]!=c["condition"] or e["rationale"]!=c["rationale"]):
            raise ValueError("The picker changed a material term of the issued call.")
        c["engine"]=e
    return card,snapshot
