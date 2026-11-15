"""One serialized, memoized, manual check of the release owner's exact contracts."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import tempfile

PACKAGED = Path(__file__).resolve().parent/"release_data"
LIVE = PACKAGED if PACKAGED.is_dir() else Path(os.path.expanduser("~/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live"))
sys.path.insert(0, str(LIVE))
import verify_card
import odds_feed

UTC = timezone.utc
FRESH = 120
COLLAPSE = 25
IDENT = ("event_id","market","subject","side","point","minimum_price","kickoff")
ORIG_CARD = "96d09884cab7d0444c8f95551def07f43a94ed9de22695a280947310d4106932"
ORIG_OBS = "7fedae05443dd316cee03ea36101bda6a997b70c2cbf887b245725c5db4869d3"
ORIG_FILE = "prices-20261115T070857592195Z.json"

def read(p): return json.loads(p.read_text())
def digest(p): return sha256(p.read_bytes()).hexdigest()
def packed(x): return json.dumps(x, sort_keys=True, separators=(",",":"),allow_nan=False).encode()
def utc(): return datetime.now(UTC)
def stamp(dt): return dt.isoformat(timespec="seconds").replace("+00:00","Z")
def when(s):
    dt = datetime.fromisoformat(s.replace("Z","+00:00"))
    if dt.tzinfo is None: raise ValueError("Timezone required")
    return dt
def price(x): return type(x) is int and 100 <= abs(x) <= 200
def payout(x): return (1+x/100) if x>0 else (1-100/x)
def identity(c):
    if not re.fullmatch(r"[a-f0-9]{32}", c["event_id"]) or not price(c["minimum_price"]):
        raise ValueError("Unrecognized event or price floor")
    if c["market"] not in (odds_feed.GAME_MARKETS+","+odds_feed.EVENT_MARKETS).split(","):
        raise ValueError("Unrecognized market")
    if not c["label"] or not c["side"] or not isinstance(c["subject"],str): raise ValueError("Incomplete contract")
    m=c["market"]; point=c["point"]; side=c["side"]; sub=c["subject"]
    if ((m in ("h2h","spreads")) == (side in ("Over","Under")) or
        ((m.startswith("player_") or m.startswith("team_totals")) != bool(sub)) or
        ((m=="h2h") != (point is None)) or (point is not None and
        (type(point) not in (int,float) or not -1000 <= point <= 1000))):
        raise ValueError("Inconsistent market, subject, line or side")
    d={k:c[k] for k in IDENT}; d["kickoff"]=stamp(when(d["kickoff"]).astimezone(UTC))
    if point is not None: d["point"]=float(point)
    return sha256(packed(d)).hexdigest()
def keys(card):
    a=[identity(c) for c in card["calls"]]
    if len(a)>6 or len(set(a))!=len(a): raise ValueError("Duplicate or excessive calls")
    return a,sha256(packed(sorted(a))).hexdigest()
def estimate(card,now):
    return len({(c["event_id"],c["market"]) for c in card["calls"] if when(c["kickoff"])>now})
def atomic(p,doc):
    p.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("wb",dir=p.parent,delete=False) as f: f.write(packed(doc)+b"\n")
    os.replace(f.name,p)
@contextmanager
def lock(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/".sunday-refresh.lock").open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        yield
def unavailable(c,t,status="Could not verify the live quote"):
    return dict(selection=c["label"],utc=stamp(t),status=status)
def check(card, *, mode="normal", root=None, verify=None, clock=utc):
    root=LIVE/"observations" if root is None else Path(root)
    verify=verify_card.verify if verify is None else verify
    ids,fp=keys(card)
    start=clock()
    with lock(root):
        now=clock(); cache=root/("exact-"+fp+".json")
        recent=None
        if cache.exists():
            try:
                v=read(cache)
                if v["fingerprint"]==fp and set(v["by_contract"])==set(ids) and when(v["checked_utc"])<=now: recent=v
            except (ValueError,KeyError,TypeError,OSError): pass
        if recent is None and root==LIVE/"observations" and digest(LIVE/"Sunday_Card.json")==ORIG_CARD:
            original=read(LIVE/"Sunday_Card.json"); oldkeys,_=keys(original); old=root/ORIG_FILE
            if set(oldkeys)==set(ids) and old.is_file() and digest(old)==ORIG_OBS:
                legacy=read(old)
                recent=dict(legacy,by_contract=dict(zip(oldkeys,legacy["quotes"])),fingerprint=fp)
        age=(now-when(recent["checked_utc"])).total_seconds() if recent else float("inf")
        use=(mode=="saved" or (recent is not None and 0<=age<=(COLLAPSE if mode=="force" else FRESH)) or
             (recent is not None and when(recent["checked_utc"])>=start))
        if use:
            if recent is None:
                recent=dict(checked_utc=stamp(now),by_contract={k:unavailable(c,now) for k,c in zip(ids,card["calls"])},credits_remaining=None,credits_used=0)
            source="saved" if mode=="saved" else "reused"
            spent=0
        else:
            try:
                result=verify(card)
                if len(result["quotes"])!=len(ids) or any(q.get("selection")!=c["label"] for q,c in zip(result["quotes"],card["calls"])):
                    raise ValueError("Unexpected verifier response")
                checked=when(result["checked_utc"])
                if abs((clock()-checked).total_seconds())>180: raise ValueError("Unexpected observation time")
                recent=dict(result,by_contract=dict(zip(ids,result["quotes"])),fingerprint=fp)
                recent.pop("quotes")
                spent=result["credits_used"]; source="live"
            except Exception as error:
                # No URLs, tokens, exception messages or stack traces in a user receipt.
                recent=dict(checked_utc=stamp(clock()),by_contract={k:unavailable(c,clock()) for k,c in zip(ids,card["calls"])},credits_remaining=None,credits_used=None,fingerprint=fp,error=type(error).__name__)
                spent=None; source="failed"
            atomic(cache,recent)
            t=clock().strftime("%Y%m%dT%H%M%S%fZ")
            atomic(root/("exact-observation-"+t+".json"),recent)
        end=clock(); checked=when(recent["checked_utc"])
        out=[]
        for k,c in zip(ids,card["calls"]):
            q=dict(recent["by_contract"][k],selection=c["label"],contract_id=k)
            if when(c["kickoff"])<=end: q=unavailable(c,end,"Game started")
            if q.get("price") is not None:
                if not price(q["price"]) or q.get("book") not in verify_card.BOOK_NAMES:
                    q=unavailable(c,end,"Exact line unavailable at qualifying odds")
                else:
                    link=verify_card.event_link(dict(key=q["book"],link=q.get("book_event_link")))
                    q["book_event_link"]=link
                    try: book_age=(end-when(q["book_updated_utc"])).total_seconds()
                    except (KeyError,ValueError,TypeError): book_age=float("inf")
                    if mode=="saved" or not 0<=book_age<=1800 or not 0<=(end-checked).total_seconds()<=FRESH:
                        q["status"]="Saved observation only"
                        q.pop("book_event_link",None)
                    elif q.get("status")=="Price qualifies" and payout(q["price"])<payout(c["minimum_price"]):
                        q["status"]="Pass at this price"
            q["contract_id"]=k; out.append(q)
        return dict(checked_utc=recent["checked_utc"],source=source,selection_fingerprint=fp,credits_used=spent,
                    observation_credits_used=recent.get("credits_used"),credits_remaining=recent.get("credits_remaining"),quotes=out)
if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card",type=Path,default=LIVE/"Sunday_Card.json")
    parser.add_argument("--mode",choices=("normal","saved","force"),default="normal",help="Normal reuses 120 seconds; force coalesces within 25 seconds")
    args=parser.parse_args()
    print(json.dumps(check(read(args.card),mode=args.mode),indent=2))
