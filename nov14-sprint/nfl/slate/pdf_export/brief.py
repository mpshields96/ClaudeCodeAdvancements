"""Offline NFL decision brief. See README.md for the input and failure contracts."""
import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape, quoteattr
from zoneinfo import ZoneInfo

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

HERE = Path(__file__).resolve().parent
CT = ZoneInfo("America/Chicago")
B = {"draftkings":"DraftKings","betmgm":"BetMGM","fanduel":"FanDuel","betrivers":"BetRivers","espnbet":"theScore Bet","thescorebet":"theScore Bet"}
DOMAINS = {"draftkings":"draftkings.com","betmgm":"betmgm.com","fanduel":"fanduel.com","betrivers":"betrivers.com","espnbet":"thescore.bet"}
NAMES = {"h2h":"moneyline","spreads":"spread","totals":"game total","team_totals":"team total",
         "player_pass_yds":"passing yards","player_rush_yds":"rushing yards","player_reception_yds":"receiving yards",
         "team_totals_h1":"first-half team total","spreads_h1":"first-half spread","totals_h1":"first-half total","h2h_h1":"first-half moneyline"}

def require(ok, message):
    if not ok: raise ValueError(message)

def digest(data): return hashlib.sha256(data).hexdigest()
def load(p): return json.loads(Path(p).read_bytes())
def stamp(v):
    t = datetime.fromisoformat(str(v).replace("Z","+00:00"))
    require(t.tzinfo is not None, f"Timezone missing in timestamp: {v}")
    return t

def validprice(x): return isinstance(x,int) and not isinstance(x,bool) and abs(x) >= 100
def dec(x):
    require(validprice(x), f"Invalid American odds: {x}")
    return 1 + (100/abs(x) if x<0 else x/100)
def odds(x): return f"{x:+d}"
def when(t, day, fulldate=False):
    d=t.astimezone(CT)
    return ((d.strftime("%b %-d") + ", ") if fulldate or d.date()!=day else "") + d.strftime("%-I:%M %p").lower()
def book(k): return B.get(k,k) if isinstance(k,str) else ""
def to_ascii(s):
    return str(s).translate(str.maketrans({"’":"'","‘":"'","“":'"',"”":'"',"−":"-","–":"-","—":" - ","→":"to"," ":" "," ":" "}))
def tx(s): return escape(to_ascii(s))
def nonempty(obj,k): return isinstance(obj.get(k),str) and bool(obj[k].strip())
def identity(b): return tuple(b.get(k,'' if k=="subject" else None) for k in ("event_id","market","subject","side","point"))

def url_ok(url):
    if not isinstance(url,str) or re.search(r'[\s{}<>"\\]',url) or re.search(r'%7[bd]',url,re.I): return False
    u=urlsplit(url)
    return u.scheme=="https" and bool(u.hostname) and not u.username and not u.password and "." in u.hostname and not re.search(r"(?:^|&)(?:api_?key|token|auth)=",u.query,re.I)

def eventurl(raw, key):
    # Only validated, actually observed, concrete book links; never guess a jurisdiction or bet slip.
    if not url_ok(raw) or key not in DOMAINS:return None
    u=urlsplit(raw); host=u.hostname or ""
    return raw if (host==DOMAINS[key] or host.endswith("."+DOMAINS[key])) and not u.query and not u.fragment and ("event" in u.path.lower() or "game" in u.path.lower()) else None

def selection(b):
    m=b["market"]; s=b["side"]; subject=b.get("subject") or ""; p=b.get("point")
    if m in ("h2h","h2h_h1"): return s+" "+NAMES[m]
    if m in ("spreads","spreads_h1"):
        return f"{s} {p:+g} ({NAMES[m]})"
    if m in NAMES: return " ".join(v for v in (subject,s.lower(),f"{p:g}",NAMES[m]) if v)
    return b["label"]  # exact, explicitly supplied contract label only

def validate_card(card):
    require(isinstance(card,dict),"Expected a card object")
    day=date.fromisoformat(card["slate_date"]); issued=stamp(card["issued_utc"])
    require(isinstance(card.get("calls"),list),"Explicit calls array required (empty is a pass day)")
    require(isinstance(card.get("passes",[]),list),"passes must be an array")
    seen=set(); labels=set()
    for b in card["calls"]:
        for k in ("label","event_id","market","side","game","kickoff","window"):
            require(nonempty(b,k),f"Call missing {k}; refusing an ambiguous pick")
        require(b["market"] in NAMES,"Unknown market; supply a supported exact market")
        if b["market"] in ("h2h","h2h_h1"):
            require(b.get("point") is None and b["side"] not in ("Over","Under"),"Moneyline must be a team without a threshold")
        if b["market"].startswith(("player_","team_totals","totals")):
            require(b["side"] in ("Over","Under"),"Expected an Over or Under side")
        if b["market"] not in ("h2h","h2h_h1"):
            if b["market"] in NAMES: require(type(b.get("point")) in (int,float) and math.isfinite(b["point"]), "Exact threshold required")
        if b["market"].startswith(("player_","team_totals")): require(nonempty(b,"subject"),"Missing player or team on exact contract")
        require(validprice(b.get("minimum_price")) and 100<=abs(b["minimum_price"])<=200,"Missing price limit or outside the approved odds band")
        t=stamp(b["kickoff"])
        require(t.astimezone(CT).date()==day and issued<t,"Card date/time does not describe a pregame selection on this slate")
        require(identity(b) not in seen and b["label"] not in labels,"Duplicate contract or ambiguous selection label")
        seen.add(identity(b));labels.add(b["label"])
        require(b.get("ticket") is None,"This brief accepts proposed picks only; reconcile tickets separately")
    for p in card.get("passes",[]): require(nonempty(p,"window") and nonempty(p,"reason"),"Pass requires a window and reason")
    return day

def evidence_for(card, sha, path):
    p=Path(path) if path else HERE/"evidence"/(card["slate_date"]+".json")
    if not p.is_file():
        require(not path,f"Missing evidence file: {p}")
        return {},{}
    e=load(p)
    if not path and e.get("card_sha256")!=sha:return {},{}
    require(e.get("card_sha256")==sha and e.get("slate_date")==card["slate_date"],"Evidence does not match this exact card hash/date")
    rows=e.get("calls",[])
    ev={identity(b):b for b in rows}
    require(len(ev)==len(rows) and set(ev).issubset({identity(b) for b in card["calls"]}),"Evidence does not match exact contracts")
    for b in rows:
        p0=b.get("market_probability")
        require(p0 is None or type(p0) in (int,float) and 0<=p0<=1,"Invalid probability")
        for lab,url in b.get("sources",[]): require(bool(lab) and url_ok(url),"Invalid evidence link")
    return e,ev

def initial_quote(b,card):
    start=card.get("earliest_snapshot") or b.get("book_updated_utc")
    if not start or not b.get("observed_book") or not validprice(b.get("observed_price")) or not b.get("book_updated_utc"):return None
    t=stamp(start);last=stamp(b["book_updated_utc"])
    require(last<=t<=stamp(card["issued_utc"]) and t<stamp(b["kickoff"]),"Invalid initial quote timing")
    require(t-last<=timedelta(minutes=30),"Initial quote was stale at capture")
    return dict(utc=t,book=b["observed_book"],price=b["observed_price"],comparison={b["observed_book"]:b["observed_price"]},link=None,status="observed")

def read_watchlist(card, explicit, cutoff):
    """Consume the picker's published order. Never generate or reorder candidates here."""
    day=date.fromisoformat(card["slate_date"])
    name=f"sunday_{day:%Y%m%d}_watchlist.json"
    candidates=[explicit] if explicit is not None else [HERE.parent/"results"/name, HERE/"examples"/"sunday"/name]
    path=next((p for p in candidates if p and p.is_file()),None)
    if path is None:
        require(explicit is None,"Cannot find the requested watchlist")
        return None,[]
    data=load(path)
    bound=(bool(card.get("snapshot_sha256")) and data.get("slate_date")==card["slate_date"]
           and data.get("capture_sha256")==card["snapshot_sha256"])
    require(bound or explicit is None,"Watchlist date or capture digest does not match")
    if not bound:return None,[]
    published=stamp(data["ranked_utc"])
    # --as-of bounds the saved prices; the later football review has its own publication time.
    ranked=data["ranked"]
    require(isinstance(ranked,list) and len(ranked)<=5,"Expected up to five ranked rows")
    require([r["rank"] for r in ranked]==list(range(1,len(ranked)+1)),"Watchlist rank sequence is invalid")
    calls={identity(b) for b in card["calls"]}
    for row in ranked:
        is_formal=row.get("status")=="formal_call"
        if is_formal!=(identity(row) in calls):
            require(explicit is None,"Watchlist formal decisions do not match this card")
            return None,[]
    if not ranked:return None,[]
    comparisons=set()
    lines=[]
    quotes=[]
    times=[]
    for r in ranked:
        require(r["status"] in ("watchlist_only","formal_call") and r["volatility"] in ("High","Moderate","Low"),"Unrecognized ranked decision or volatility")
        require(nonempty(r,"risk_tag") and nonempty(r,"label") and nonempty(r,"game"),"Incomplete ranked choice")
        comparable=(r["event_id"],r["market"],r.get("subject",""))
        require(comparable not in comparisons,"Duplicate or opposing variant in the watchlist")
        comparisons.add(comparable)
        t=stamp(r["observed_utc"]);kt=stamp(r["kickoff"])
        require(not cutoff or t<=cutoff,"Ranked quote is later than the selected price cutoff")
        require(stamp(r["provider_updated_utc"])<=t<=published<kt and kt.astimezone(CT).date()==day,"Watchlist row is not pregame on the selected date")
        require(validprice(r["price"]) and abs(r["price"])<=200 and nonempty(r,"book"),"Invalid ranked price")
        quotes.append(dict(r,observed_price=r["price"],observed_book=r["book"],book_updated_utc=r["provider_updated_utc"]))
        times.append(when(t,day))
        formal=r["status"]=="formal_call"
        status="Formal" if formal else "Watch"
        condition=f'{status} · {r["volatility"].lower()} · {r["risk_tag"]}'
        label=r["label"]
        if r["market"]=="team_totals" and "full game" not in label.lower():
            label="Full game · "+label
        matchup=f'{r["game"]} · {when(kt,day)}'
        lines.append((str(r["rank"]),label,matchup,f'{odds(r["price"])} {book(r["book"])}',condition))
    title="Top 5 potential bets" if len(lines)==5 else f"Potential bets ({len(lines)} ranked)"
    timing=f"Quotes at {times[0]} CT." if len(set(times))==1 else "Quote times are shown beside each sportsbook."
    if len(set(times))>1:
        lines=[(n,lab,matchup,f"{price}, {t} CT",tag) for (n,lab,matchup,price,tag),t in zip(lines,times)]
    basis=f"Ranked at {when(published,day)} CT by football case and price. {timing}"
    supplement=data.get("supplement",{})
    if supplement and all(type(r.get("market_value_gap_pp")) in (float,int) for r in ranked):
        reviewed_at=stamp(supplement["published_utc"])
        require(published<=reviewed_at<min(stamp(r["kickoff"]) for r in ranked),"Watchlist supplement is not pregame")
        groups={}
        for r in ranked:
            groups.setdefault(r["market_value_label"],[]).append(f"#{r['rank']} {r['market_value_gap_pp']:+.2f}")
        labels=" · ".join(name+" ("+", ".join(values)+")" for name,values in groups.items())
        basis+=f" {when(reviewed_at,day)} CT review of market chance minus break-even at ranked prices, in percentage points. "+labels+"."
    return dict(title=title,basis=basis,rows=lines),quotes

def read_reviewed_calls(card, explicit, card_dir):
    """Read supplemental pregame analysis only for this frozen source and decision."""
    name="sunday_"+card["slate_date"].replace("-","")+"_selections.json"
    choices=[explicit] if explicit else [card_dir/name, HERE.parent/"results"/name, HERE/"examples"/"sunday"/name]
    path=next((p for p in choices if p.is_file()),None)
    if path is None:
        require(explicit is None,"The supplied reviewed selections file does not exist")
        return {}
    document=load(path)
    same_card=(document.get("slate_date")==card["slate_date"]
               and bool(card.get("snapshot_sha256"))
               and document.get("capture_sha256")==card["snapshot_sha256"]
               and document.get("stage")=="reviewed" and document.get("pregame") is True
               and stamp(document["decided_utc"])==stamp(card["issued_utc"]))
    if same_card:
        expected={gate_key(c) for c in card["calls"]}
        rows={gate_key(c):c for c in document["calls"]}
        same_card=expected==set(rows) and len(rows)==len(document["calls"])
    require(same_card or explicit is None,"Reviewed selections do not match the frozen date, source and exact decisions")
    return rows if same_card else {}

def check_capture(path,card,ranked_quotes=()):
    if not path:return
    data=Path(path).read_bytes()
    require(card.get("snapshot_sha256")==digest(data),"Snapshot does not match frozen card SHA-256")
    d=json.loads(data);require(d["day"]==card["slate_date"] and stamp(d["captured_utc"])==stamp(card["earliest_snapshot"]),"Snapshot date/time mismatch")
    for b in [*card["calls"],*ranked_quotes]:
        if b.get("observed_price") is None:continue
        matches=[]
        for g in d["games"]+d.get("event_odds",[]):
            if g["id"]!=b["event_id"] or stamp(g["commence_time"])!=stamp(b["kickoff"]):continue
            for bk in g["bookmakers"]:
                if bk["key"]!=b["observed_book"]:continue
                for m in bk["markets"]:
                    if m["key"]!=b["market"]:continue
                    for o in m["outcomes"]:
                        if (o["name"],o.get("description",""),o.get("point"))==(b["side"],b.get("subject",""),b.get("point")):
                            matches.append((o["price"],stamp(m.get("last_update") or bk["last_update"])))
        require((b["observed_price"],stamp(b["book_updated_utc"])) in matches,"Frozen quote not found in supplied snapshot: "+b["label"])

def packed(obj): return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def gate_key(b):
    d={k:b.get(k,"" if k=="subject" else None) for k in ("event_id","market","subject","side","point","minimum_price","kickoff")}
    d["kickoff"]=stamp(d["kickoff"]).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    if d["point"] is not None:d["point"]=float(d["point"])
    return digest(packed(d))

ORIG_CARD="96d09884cab7d0444c8f95551def07f43a94ed9de22695a280947310d4106932"
ORIG_OBS="7fedae05443dd316cee03ea36101bda6a997b70c2cbf887b245725c5db4869d3"

def observations(directory, card, cutoff=None):
    if not directory:return {}
    p=Path(directory);require(p.is_dir(),"Missing observations directory")
    byid={gate_key(b):b for b in card["calls"]}; fingerprint=digest(packed(sorted(byid)))
    out={b["label"]:{} for b in card["calls"]}
    for f in sorted([*p.glob("prices-*.json"),*p.glob("exact-*.json")]):
        data=f.read_bytes();d=json.loads(data)
        if "by_contract" in d:
            if d.get("fingerprint")!=fingerprint:continue
            require(set(d["by_contract"])==set(byid),"Observation fingerprint/keys disagree")
            rows=[(byid[k],q) for k,q in d["by_contract"].items()]
        elif card["_sha"]==ORIG_CARD and digest(data)==ORIG_OBS:
            require([b["label"] for b in card["calls"]]==[q["selection"] for q in d["quotes"]],"Pinned initial receipt/labels mismatch")
            rows=list(zip(card["calls"],d["quotes"]))
        elif d.get("card_sha256")==card["_sha"] and all(q.get("contract_id") in byid for q in d.get("quotes",[])):
            rows=[(byid[q["contract_id"]],q) for q in d["quotes"]]
        else:continue  # a similar label is not proof of the same contract
        t=stamp(d["checked_utc"])
        if cutoff and t>cutoff:continue
        for b,raw in rows:
            if any(k in raw and raw[k]!=b.get(k) for k in ("event_id","market","side","point","subject")):
                raise ValueError("Observation content contradicts its contract identity")
            status=raw.get("status","Unverified")
            # Failure receipts can be timestamped a second later by the gate.
            require(abs((stamp(raw["utc"])-t).total_seconds()) <= (0 if raw.get("price") is not None else 2),"Observation check time mismatch")
            q=dict(utc=t,book=None,price=None,comparison={},link=None,status=status)
            if t>=stamp(b["kickoff"]):q["status"]="Game started"
            elif status in ("Price qualifies","Pass at this price"):
                key=raw.get("book"); price=raw.get("price"); upd=stamp(raw["book_updated_utc"])
                comp=raw.get("comparison",{})
                require(bool(key) and validprice(price) and 100<=abs(price)<=200 and comp.get(key)==price and all(validprice(v) for v in comp.values()),"Incomplete market comparison")
                require(t-timedelta(minutes=30)<=upd<=t, "Book quote not fresh at observation")
                require(dec(price)>=max(map(dec,(v for v in comp.values() if 100<=abs(v)<=200)),default=0),"Observation does not match best eligible price")
                require((status=="Price qualifies")==(dec(price)>=dec(b["minimum_price"])),"Status contradicts price limit")
                q.update(book=key,price=price,comparison=comp,link=eventurl(raw.get("book_event_link"),key))
            old=out[b["label"]].get(t)
            require(old is None or old==q,"Conflicting receipts for the same contract and time")
            out[b["label"]][t]=q
    return {k:[d[t] for t in sorted(d)] for k,d in out.items()}

def source_link(label,url):
    return f'<link href={quoteattr(url)} color="#00655E"><u>{tx(label)}</u></link>'

PAPER="#FCFAF2"; INK="#27292A"; PLUM="#4E3046"; TEAL="#00645F"; MUTED="#475957"; RULE="#CACBBF"; PALE="#EEF1E8"; RUST="#86543B"
W,H=letter; X=37; USABLE=W-2*X; BODY_TOP=H-49
def col(x): return colors.HexColor(x)

class Block:
    def __init__(self,kind,**data): self.kind=kind;self.__dict__.update(data)

def ppara(s,sz,lead,font="Helvetica",color=INK):
    st=ParagraphStyle("txt",fontName=font,fontSize=sz,leading=lead,textColor=col(color),alignment=TA_LEFT,splitLongWords=1,allowWidows=0,allowOrphans=0)
    return Paragraph(s,st)

def paint_text(c,txt,x,y,width,size,leading,font="Helvetica",color=INK):
    p=ppara(txt,size,leading,font,color); _,h=p.wrap(width,9999)
    if c: p.drawOn(c,x,y-h)
    return h

def line(c,x1,y,x2,color=RULE):
    if c:
        c.setStrokeColor(col(color));c.setLineWidth(.55);c.line(x1,y,x2,y)

def drawblock(b,c,y,scale):
    base=10.35*scale; lead=base*1.28; gap=4.5*scale
    if b.kind=="hero":
        h=paint_text(c,tx(b.title),X,y,USABLE,31*scale,35*scale,"Times-Roman",PLUM)
        h+=3*scale;h+=paint_text(c,tx(b.deck),X,y-h,USABLE,base*1.10,lead*1.10)
        return h+7*scale
    if b.kind=="section":
        h=paint_text(c,tx(b.title).upper(),X,y,USABLE,8.2*scale,10*scale,"Helvetica-Bold",TEAL);return h+3*scale
    if b.kind=="row":
        cw=[USABLE*.49,USABLE*.26,USABLE*.25];xx=X;ht=[]
        for i,parts in enumerate(b.cells):
            z=2.5*scale
            for s,em in parts:
                z+=paint_text(c,s,xx,y-z,cw[i]-7,base*(1.04 if em else .90),lead*(1.04 if em else .90),"Helvetica-Bold" if em else "Helvetica",INK if em else MUTED)+1.4*scale
            xx+=cw[i];ht.append(z)
        h=max(ht)+2.5*scale;line(c,X,y-h,X+USABLE);return h
    if b.kind=="tablehead":
        if c:
            c.setFillColor(col(PALE));c.rect(X-4,y-17*scale,USABLE+8,17*scale,fill=1,stroke=0)
        for x,w,s in [(0,.49,"SELECTION  /  KICKOFF"),(.49,.26,"BEST SAVED QUOTE"),(.75,.25,"VALUE IF IT WINS")]:
            paint_text(c,s,X+USABLE*x,y-4*scale,USABLE*w-5,7.8*scale,9*scale,"Helvetica-Bold",TEAL)
        return 17*scale
    if b.kind=="small":
        h=paint_text(c,b.text,X,y-4*scale,USABLE,base*.93,lead*.94,"Helvetica",MUTED)
        return h+6*scale
    if b.kind=="shortlist":
        offset=4*scale
        offset+=paint_text(c,tx(b.title),X,y-offset,USABLE,17*scale,19*scale,"Times-Roman",PLUM)
        offset+=paint_text(c,tx(b.basis),X,y-offset,USABLE,base*.88,lead*.86,"Helvetica",MUTED)+3*scale
        widths=(.035,.35,.17,.145,.30)
        for idx,cells in enumerate([("#","MARKET","MATCHUP / KICKOFF","SAVED QUOTE","STATUS / RISK"),*b.rows]):
            is_header=idx==0
            if is_header and c:
                c.setFillColor(col(PALE));c.rect(X-3,y-offset-12*scale,USABLE+6,12*scale,fill=1,stroke=0)
            offset+=2.3*scale
            heights=[]
            x=X
            for ix,(cell,fraction) in enumerate(zip(cells,widths)):
                measure=paint_text(c,tx(cell),x,y-offset,USABLE*fraction-3,
                                   base*(.75 if is_header else .90),lead*(.72 if is_header else .88),
                                   "Helvetica-Bold" if is_header or ix==0 else "Helvetica",TEAL if is_header or ix==0 else INK)
                heights.append(measure)
                x+=USABLE*fraction
            offset+=max(heights)+2.1*scale
            if not is_header:line(c,X,y-offset,W-X)
        return offset+5*scale
    if b.kind=="feature":
        z=5*scale
        z+=paint_text(c,tx(b.title),X,y-z,USABLE,19*scale,21.5*scale,"Times-Roman",PLUM)+gap
        for txt in b.paragraphs:
            z+=paint_text(c,txt,X,y-z,USABLE,base,lead)+2.7*scale
        if b.sources:
            z+=paint_text(c,"&nbsp;&nbsp;·&nbsp;&nbsp;".join(source_link(l,u) for l,u in b.sources),X,y-z,USABLE,base*.85,lead*.85)
        z+=5*scale;line(c,X,y-z,X+USABLE);return z
    raise ValueError("Unknown block")

def prop_form(b,v,day):
    """Windows are consecutive current-season appearances, never last year's games or a hot-start filter."""
    if not b["market"].startswith("player_"):return ""
    history=v.get("recent_appearances")
    if not history:return "Recent five/ten current-season appearances were not verified. "
    rows=history.get("entries",[]);season=day.year-int(day.month<4)
    require(history.get("season")==season and history.get("season_type")=="REG" and history.get("complete_through_card") is True and url_ok(history.get("source_url")),"Prop sample must be complete current regular-season appearances with a source")
    if not rows:return "No completed appearance this season. "
    require([r.get("appearance") for r in rows]==list(range(1,len(rows)+1)), "Prop appearance sequence has a gap")
    dates=[date.fromisoformat(r["date"]) for r in rows]
    require(dates==sorted(set(dates)) and all(d.year-int(d.month<4)==season and d<day for d in dates),"Prop logs must be unique, dated, current season and pregame")
    require(all(type(r.get("value")) in (int,float) and math.isfinite(r["value"]) for r in rows),"Missing player value: never skip the game or count a missing stat as zero")
    def beats(a,line):return a>line if b["side"]=="Over" else a<line
    threshold=b["point"];five=rows[-5:];ten=rows[-10:]
    score=lambda a:sum(beats(r["value"],threshold) for r in a)
    side="cleared" if b["side"]=="Over" else "stayed below"
    short=b["subject"].split()[-1]
    if len(rows)>5:
        text=f"{short} {side} {threshold:g} in {score(five)} of his last 5 games and {score(ten)} of " + (f"{len(ten)} this season (fewer than 10 played)." if len(ten)<10 else "his last 10 this season.")
    else:text=f"{short} {side} {threshold:g} in {score(ten)} of {len(ten)} appearances this season; no longer sample is available."
    pushes=sum(r["value"]==threshold for r in ten)
    if pushes:text+=f" The sample includes {pushes} push(es)."
    known=[r for r in ten if type(r.get("prior_line")) in (int,float) and math.isfinite(r["prior_line"])]
    if known:
        require(url_ok(history.get("prior_line_source_url")),"Historical lines require a separate source")
        hist=sum(beats(r["value"],r["prior_line"]) for r in known)
        text+=f" He beat {hist} of {len(known)} actual prior lines. Their books and quote times are unverified."
    return text+" "

def replacement_notes(reviewed, bet, day):
    """Render the canonical decision's personnel review, including its publication time."""
    items=reviewed.get("replacement_context",[])
    require(isinstance(items,list),"Expected a list of replacement reviews")
    paragraphs=[]
    sources=[]
    for item in items:
        require(nonempty(item,"display"),"Replacement review needs a readable decision summary")
        effective=stamp(item["effective_as_of_utc"])
        require(effective<stamp(bet["kickoff"]),"Postgame replacement evidence cannot appear in a pregame brief")
        # Added time belongs to the supplemental review; original call terms remain attributed to issuance.
        follow_up=effective>stamp(reviewed["decided_utc"])
        label="Personnel follow-up" if follow_up else "Personnel"
        outlook=item.get("relative_to_starter")
        confidence=item.get("confidence")
        assessment=""
        if outlook in {"weaker","stronger","mixed","preserved"} and confidence in {"low","medium","high"}:
            assessment=f" The review rates the outlook versus the starter as {outlook} ({confidence} confidence)."
        paragraphs.append("<b>"+label+" ("+tx(when(effective,day))+" CT).</b> "+tx(item["display"]+assessment))
        for source in item.get("sources",[]):
            url=source.get("url")
            if not url_ok(url) or not nonempty(source,"label"):
                continue
            if urlsplit(url).hostname=="api.the-odds-api.com":
                continue
            if url not in {link for _,link in sources}:
                sources.append((source["label"],url))
    return paragraphs,sources

def make_blocks(card,e,ev,obs):
    day=date.fromisoformat(card["slate_date"]); calls=sorted(card["calls"],key=lambda b:stamp(b["kickoff"]))
    qdata=[]
    for b in calls:
        first=initial_quote(b,card); receipts=obs.get(b["label"],[])
        series=sorted(([first] if first and all(q["utc"]!=first["utc"] for q in receipts) else [])+receipts,key=lambda q:q["utc"])
        latest=series[-1] if series else None
        qdata.append((b,ev.get(identity(b),{}),first,series,latest))
    unavailable=any(not q or q["price"] is None or dec(q["price"])<dec(b["minimum_price"]) for b,_,_,_,q in qdata)
    deck=e.get("deck") or ("Every selection below is conditional on its price and football checks." if calls else "No play qualified on the submitted card. The reasons below are the pregame record.")
    headline=e.get("headline") or ("NFL pregame selections" if calls else "Pass on this slate")
    if unavailable: headline="Check the price before acting";deck="One or more selections failed the latest check or have no verified quote. The original price limits still apply."
    parts=[Block("hero",title=headline,deck=deck),Block("section",title="TL;DR  /  Pregame card")]
    moves=[]
    if calls and not e.get("red_team"):parts.append(Block("small",text="<b>Research only.</b> No independent pregame red-team review was supplied."))
    if calls:parts.append(Block("tablehead"))
    for b,v,first,series,q in qdata:
        pr=q["price"] if q else None; k=q["book"] if q else None
        label=selection(b)
        a=[(tx(label),True),(tx(b["game"])+" · "+tx(when(stamp(b["kickoff"]),day))+" CT",False)]
        if v.get("summary_condition"): a.append((tx(v["summary_condition"]),False))
        elif nonempty(b,"condition"):a.append((tx(b["condition"]),False))
        limit=odds(b["minimum_price"])+" or better"
        if pr is not None:
            bname=tx(book(k));bn=source_link(book(k),q["link"]) if q.get("link") else bname
            col2=[(tx(odds(pr))+" · "+bn,True),(tx(when(q["utc"],day))+" CT",False)]
            good=dec(pr)>=dec(b["minimum_price"])
            col2.append((("Limit: " if good else "PASS · limit: ")+tx(limit),False))
            c3=[(f"${(dec(pr)-1)*10:.2f} net per $10",True),(f"Break-even: {100/dec(pr):.1f}%",False)]
        else:
            col2=[("PASS / NO QUOTE",True),(tx(q["status"] if q else "No verified quote"),False),(tx(limit),False)]
            c3=[("Unavailable",False)]
        parts.append(Block("row",cells=[a,col2,c3]))
        if q and first:
            reference=first["book"]
            prior=v.get("prior_observations",[])
            displayed={}
            for r in prior:
                require(r.get("book") and validprice(r.get("price")) and url_ok(r.get("source_url")) and r.get("source"),"Historical quote requires a sportsbook, time, valid price and named source")
                pt=stamp(r["observed_utc"]);require(pt<first["utc"],"Editorial history must predate the frozen capture")
                if r["book"]==reference:displayed[pt]=(r["price"],r)
            for z in series:
                if reference in z.get("comparison",{}):displayed[z["utc"]]=(z["comparison"][reference],None)
            history=sorted((t,v_[0]) for t,v_ in displayed.items())
            if len(history)>1:
                pts=[v_ for _,v_ in history]; t0,v0=history[0];tn,vn=history[-1]
                extra=displayed[t0][1]
                origin=(" ("+source_link(extra["source"],extra["source_url"])+")") if extra else ""
                st=f"{tx(book(reference))} {odds(v0)} at {when(t0,day)}"+origin
                if min(pts)==max(pts):st+=f" and {when(tn,day)} ({len(pts)} checks)"
                elif v0==vn and len(set(pts))==2:
                    middle_time,middle_price=next((t,v) for t,v in history if v!=v0)
                    st+=f", {odds(middle_price)} at {when(middle_time,day)}, then {odds(vn)} at {when(tn,day)}"
                else:st+=f" to {odds(vn)} at {when(tn,day)} (range {odds(min(pts))} to {odds(max(pts))})"
                moves.append(st)
    counts=Counter(b["event_id"] for b in calls)
    matchups={b["event_id"]:b["game"] for b in calls}
    for event_id,count in counts.items():
        if count>1:
            note=f"{count} selections depend on {tx(matchups[event_id])}. The same score or injury can affect them together."
            parts.append(Block("small",text="<b>Shared game risk.</b> "+note))
    notes=e.get("pass_notes",{});wind=e.get("window_note","")
    for p in card.get("passes",[]):
        msg=tx(notes.get(p["window"],p["reason"]))
        parts.append(Block("small",text="<b>"+tx(p["window"])+" pass.</b> "+msg+(" "+tx(wind) if wind else "")));wind=""
    if wind:parts.append(Block("small",text=tx(wind)))
    if not calls and not card.get("passes"):parts.append(Block("small",text="No selection recorded. No pass rationale was supplied."))
    if card.get("_shortlist"):
        parts.append(Block("shortlist",**card["_shortlist"]))
    for b,v,first,series,q in qdata:
        rich=bool(v); p=v.get("market_probability")
        why=prop_form(b,v,day)+(v.get("football") or b.get("thesis") or "No football rationale supplied.")
        risk=v.get("risk") or " ".join(filter(None,[b.get("counterevidence"),b.get("condition")])) or "No counterargument or personnel check supplied."
        reviewed=card.get("_reviewed_calls",{}).get(gate_key(b),{})
        personnel,personnel_links=replacement_notes(reviewed,b,day)
        ps=[tx(why),*personnel,"<b>What could go wrong.</b> "+tx(risk)]
        ms=[]
        if p is not None and first:
            px=first["price"]
            ms.append(f"At {when(first['utc'],day)}, {v.get('market_label','the market')} implied {p*100:.1f}% without margin. Break-even at {odds(px)} is {100/dec(px):.1f}%.")
            if v.get("show_market_based_return") is True:
                ms.append(f"Market-based expected return: {100*(p*dec(px)-1):+.1f}%.")
        if v.get("market_note"):ms.append(v["market_note"])
        if not ms:ms.append("No supported probability or expected return supplied.")
        ps.append("<b>Price check.</b> "+tx(" ".join(ms)))
        if not rich:ps.append("<b>Evidence coverage.</b> No separate verified recent-form, head-to-head or role breakdown supplied.")
        links=v.get("sources",[]) or ([("Selection source",b["source"])] if url_ok(b.get("source")) else [])
        seen={url for _,url in links}
        links=[*links,*[(label,url) for label,url in personnel_links if url not in seen]]
        parts.append(Block("feature",title=v.get("title") or selection(b),paragraphs=ps,sources=links))
    if calls:
        mv=("; ".join(moves)+". " if moves else "No comparable series supplied. ")
        parts.append(Block("small",text="<b>Line movement.</b> "+mv+"Saved observations only. No verified opener, close or closing-line value."))
    parts.append(Block("small",text="<b>Before kickoff.</b> "+tx(e.get("availability","Record your football judgment and revisions before kickoff. Check the exact terms; log any accepted ticket separately. No ticket is established by this card."))))
    return parts

def layout(parts,scale):
    top=BODY_TOP;bottom=41;space=top-bottom;pages=[];current=[];used=0
    for j,b in enumerate(parts):
        h=drawblock(b,None,top,scale)
        require(h<=space,"A section is too long to publish without cutting evidence")
        group=h
        if b.kind in ("hero","section","tablehead"):
            for n in parts[j+1:]:
                group+=drawblock(n,None,top,scale)
                if n.kind not in ("section","tablehead"):break
        if current and used+group>space:
            pages.append(current);current=[];used=0
        current.append(b);used+=h
    if current:pages.append(current)
    return pages

def render(card,e,ev,obs):
    parts=make_blocks(card,e,ev,obs);options=[]
    for s in (1.035,1.00,.97,.94,.91,.89,.875,.86):
        pages=layout(parts,s);options.append((len(pages),-s,s,pages))
    n,_,scale,pages=min(options,key=lambda x:(x[0],x[1]))
    require(n<=3,"Evidence exceeds the three-page limit; shorten editorial prose. No content was dropped.")
    day=date.fromisoformat(card["slate_date"]); buff=io.BytesIO()
    c=canvas.Canvas(buff,pagesize=letter,invariant=1,pageCompression=1)
    c.setTitle(f"NFL pregame brief | {day:%B %d, %Y}");c.setAuthor("NFL Research Notebook");c.setSubject("Dated conditional selections and football evidence")
    for i,pg in enumerate(pages):
        c.setFillColor(col(PAPER));c.rect(0,0,W,H,fill=1,stroke=0)
        c.setFont("Helvetica-Bold",8.3);c.setFillColor(col(TEAL));c.drawString(X,H-29,"NFL RESEARCH NOTEBOOK")
        c.setFont("Helvetica",8.3);c.setFillColor(col(MUTED));c.drawCentredString(W/2,H-29,day.strftime("%A  /  %d %b %Y").upper())
        c.setFillColor(col(TEAL));c.drawRightString(W-X,H-29,f"{i+1:02d} / {n:02d}");line(c,X,H-39,W-X)
        y=BODY_TOP
        for block in pg:y-=drawblock(block,c,y,scale)
        require(y>=40,"Page overflow")
        line(c,X,32,W-X);c.setFont("Helvetica",8);c.setFillColor(col(MUTED))
        c.drawString(X,19,"PREGAME EDITION  /  All times Central");c.drawRightString(W-X,19,("Conditional selections" if card["calls"] else "No selections")+"  ·  No ticket recorded")
        c.showPage()
    c.save()
    data=buff.getvalue(); reader=PdfReader(io.BytesIO(data));require(len(reader.pages)==n and all(p.extract_text().strip() for p in reader.pages),"Generated PDF failed verification")
    return data,n

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--card",type=Path,required=True);a.add_argument("--evidence",type=Path);a.add_argument("--snapshot",type=Path);a.add_argument("--observations",type=Path);a.add_argument("--output",type=Path,required=True);a.add_argument("--as-of",help="Optional inclusive UTC/offset timestamp for quote observations")
    a.add_argument("--watchlist",type=Path,help="Optional dated canonical ranked shortlist JSON")
    a.add_argument("--reviewed-selections",type=Path,help="Dated picker release carrying decision-level personnel evidence")
    args=a.parse_args();raw=args.card.read_bytes();sha=digest(raw);card=json.loads(raw);validate_card(card);card["_sha"]=sha
    e,ev=evidence_for(card,sha,args.evidence)
    cutoff=stamp(args.as_of) if args.as_of else None
    require(not cutoff or cutoff>=stamp(card["issued_utc"]), "Cutoff precedes the decision")
    card["_shortlist"],ranked_quotes=read_watchlist(card,args.watchlist,cutoff)
    check_capture(args.snapshot,card,ranked_quotes)
    card["_reviewed_calls"]=read_reviewed_calls(card,args.reviewed_selections,args.card.parent)
    data,pages=render(card,e,ev,observations(args.observations,card,cutoff))
    out=args.output;require(out.suffix.lower()==".pdf","Output must have .pdf extension")
    out.parent.mkdir(parents=True,exist_ok=True);tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=out.parent,suffix=".pdf.tmp",delete=False) as f:
            tmp=f.name;f.write(data)
        os.replace(tmp,out)
    finally:
        if tmp and os.path.exists(tmp):os.unlink(tmp)
    print(json.dumps({"pdf":str(out.resolve()),"pages":pages,"bytes":len(data),"sha256":digest(data),"card_sha256":sha}))
if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,TypeError,OverflowError,OSError) as exc:
        print("NFL brief: "+str(exc),file=sys.stderr);sys.exit(2)
