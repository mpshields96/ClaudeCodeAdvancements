"""Browser adapter for Claude's single, append-only Sunday experiment journal."""
from html import escape as h
import importlib.util
import inspect
import math
from pathlib import Path
import threading
from sunday_card import S,L,central
import sunday_quotes as oq
_J=None
def api():
    global _J
    if _J is None:
        path=S/"experiment/journal.py"
        spec=importlib.util.spec_from_file_location("nfl_sunday_experiment",str(path))
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);_J=mod
    return _J
def cid(call):
    return api().candidate_id(call["event_id"],call["market"],call["subject"],call["point"],call["side"])
def summary(c):
    if c.get("slate_date")!="2026-11-15":return "<p>The dated notebook compares the first published record for each contract with your pregame judgment and any ticket you report.</p>"
    ctr=oq.read(L/"Matched_Role_Control.json")
    text='<p>A prospective experiment keeps the original calls, your football judgment, and your actual tickets separate. One Sunday cannot establish an edge.</p>'
    if ctr.get("matched") and ctr.get("capture_sha256")==c["snapshot_sha256"]:
        row=ctr["selected"]
        text+=f'<p><b>Role comparison, never a third selection:</b> {h(row["subject"])} {h(row["side"].lower())} {row["point"]:g} receiving yards, {row["observed_price"]:+d} at BetMGM. The same-price control is compared with Warren after the games. Neither a settled result nor a closing price is available here.</p>'
    return text
def controls(card,token,root=None):
    lead=summary(card); j=api(); log=j.Journal(root or j.DEFAULT_DATA)
    try:st=j.State(log)
    except (ValueError,OSError,j.JournalError):return lead+'<p class="band notice">Notebook cannot verify its history. Entries are disabled.</p>'
    calls=st.first_by_role("call")
    if any(cid(c) not in calls for c in card["calls"]):return lead+'<p class="band">The journal has not imported this released card. Entries are disabled.</p>'
    opts=''.join(f'<option value="{cid(c)}">{h(c["label"])}</option>' for c in card["calls"])
    if not opts:return lead+'<p>No released calls to annotate.</p>'
    hidden=f'<input type="hidden" name="token" value="{h(token)}">'
    if card.get("slate_date")!="2026-11-15":
        hidden+=f'<input type="hidden" name="date" value="{h(card["slate_date"])}">'
    select=f'<label>Frozen selection<select name="cid">{opts}</select></label>'
    pool=st.first_by_role("pool")
    alt_opts=''.join(f'<option value="{h(k)}">{h(v["game"])} · {h(v["label"])}</option>' for k,v in pool.items() if oq.when(v["kickoff_utc"])>oq.utc())
    lead+=f'<p><b>{len(pool):,}</b> exact contracts in the saved pool · {len(st.hypotheses)} preregistered hypotheses · {len(st.decisions)} recorded views · {len(st.tickets)} reported tickets.</p>'
    for hyp in st.hypotheses:lead+=f'<details><summary>Pregame hypothesis · {h(hyp["hypothesis_id"])}</summary><p>{h(hyp["text"])}</p><small>Recorded {h(hyp["recorded_utc"])}</small></details>'
    lead+=f'''<div class="two"><details><summary>Record or revise my football view</summary><form method="post" action="/opinion">{hidden}{select}
    <label>My judgment<select name="action"><option value="take">I'd take the released bet</option><option value="pass">I'd pass</option><option value="alternative">I prefer another contract</option></select></label>
    <label>Alternative only: search a team, player or contract ID<input name="alt" list="contracts" autocomplete="off"></label><datalist id="contracts">{alt_opts}</datalist>
    <label>What changes the game?<textarea required minlength="3" maxlength="700" name="reason" placeholder="Role, injury, matchup or game script"></textarea></label>
    <label><input name="revise" value="yes" type="checkbox" style="width:auto"> This revises my earlier view</label><button>Save pregame view</button></form></details>
    <details><summary>Record a ticket I already placed</summary><p class="small">Self-reported terms. No sportsbook account is connected. These fields never submit an order.</p>
    <form method="post" action="/ticket">{hidden}{select}
    <label>Book shown on ticket<select name="book">''' + ''.join(f'<option>{h(n)}</option>' for n in ["DraftKings","FanDuel","BetMGM","BetRivers","theScore Bet","bet365","Caesars","Fanatics"]) + '''</select></label>
    <label>Offered American odds<input name="offered" required type="number" step="1" placeholder="e.g. -110"></label>
    <label>Accepted American odds<input name="accepted" required type="number" step="1" placeholder="e.g. -115"></label>
    <label>Accepted line, if different (yards or points)<input name="point" type="number" step="any"></label>
    <label>Amount actually staked, USD<input name="stake" type="number" step="0.01" min=".01" required></label>
    <label>Time accepted · Chicago local time<input name="placed" type="datetime-local" required step="1"></label>
    <label><input type="checkbox" name="confirmed" value="yes" required style="width:auto"> I already placed this ticket myself</label>
    <button>Save ticket record</button></form></details></div>'''
    journal_rows=[]
    for x in st.decisions[-4:]:journal_rows.append((x["recorded_utc"],"View: "+x["action"]+" · "+x["reason"]))
    for x in st.tickets[-4:]:
        placed=central(x["placed_utc_reported"]) if x.get("placed_utc_reported") else "unknown"
        journal_rows.append((x["recorded_utc"],"Reported ticket: "+x["book"]+" "+str(x["price"])+" · $"+str(x["stake"])+" · accepted "+placed))

    if journal_rows:lead+='<details><summary>Recent personal records</summary>'+''.join(f'<p>Recorded {h(central(ts))} · {h(s)}</p>' for ts,s in sorted(journal_rows,reverse=True))+'</details>'
    return lead
def american(t):
    i=int(t)
    if not 100<=abs(i)<=100000:raise ValueError("Enter valid American odds, such as -115 or +105.")
    return i
def submit(path,fields,card,root=None,clock=oq.utc):
    from datetime import datetime
    from sunday_card import CT
    j=api();log=j.Journal(root or j.DEFAULT_DATA);now=clock()
    c=next((c for c in card["calls"] if cid(c)==fields.get("cid")),None)
    if c is None:raise ValueError("Select a released contract.")
    target=cid(c)
    try:
        # Separate from journal's append lock: serialize validation+append across desk processes.
        with oq.lock(Path(log.dir)/"desk-intake"):
            st=j.State(log)
            if target not in st.first_by_role("call"):raise ValueError("This released call is missing from the journal.")
            if path=="/opinion":
                action=fields.get("action");reason=fields.get("reason","").strip();alt=fields.get("alt")
                if len(reason)>700 or not reason:raise ValueError("Enter your own brief football reason.")
                if alt and alt not in st.first_by_role("pool"):raise ValueError("Choose the exact alternative from the saved list.")
                r=j.record_decision(log,target,action,reason,now,by="matthew",alt=alt,revise=fields.get("revise")=="yes")
                return "Saved your pregame view. The original selection stays unchanged."
            if path!="/ticket" or fields.get("confirmed")!="yes":raise ValueError("Confirm this is a ticket you already placed.")
            book=fields["book"]
            if book not in {"DraftKings","FanDuel","BetMGM","BetRivers","theScore Bet","bet365","Caesars","Fanatics"}:raise ValueError("Choose the book on the ticket.")
            offered=american(fields["offered"]); accepted=american(fields["accepted"]);stake=float(fields["stake"])
            if not math.isfinite(stake) or stake<=0:raise ValueError("Enter the actual positive USD stake.")
            raw=datetime.fromisoformat(fields["placed"])
            if raw.tzinfo is not None:raise ValueError("Use Chicago local time for this field.")
            placed=raw.replace(tzinfo=CT).astimezone(oq.UTC)
            if placed>now or placed>=oq.when(c["kickoff"]) or placed<oq.when(card["issued_utc"]):
                raise ValueError("Ticket time must follow the released call, precede kickoff, and cannot be in the future.")
            point=float(fields["point"]) if fields.get("point") else None
            if point is not None and (not math.isfinite(point) or abs(point)>1000):raise ValueError("Invalid accepted line.")
            effective=point if point is not None else c["point"]
            if any(t["cid"]==target and t["book"]==book and t["price"]==accepted and t["point"]==effective and abs(t["stake"]-stake)<1e-9 and t.get("placed_utc_reported") and oq.when(t["placed_utc_reported"])==placed for t in st.tickets):
                raise ValueError("This exact ticket was already recorded.")
            kwargs=dict(point=point,placed_utc=oq.stamp(placed),note=f"Offered American price {offered:+d}; accepted {accepted:+d}. Self-reported, never provider-verified.")
            if "offered_price" in inspect.signature(j.record_ticket).parameters:kwargs["offered_price"]=offered
            j.record_ticket(log,target,book,accepted,stake,now,**kwargs)
            return "Recorded the ticket you reported. It is scored separately from the model call."
    except j.JournalError as ex:raise ValueError(str(ex)[:210]) from None


def current_views(card,root=None):
    j=api(); records=j.Journal(root or j.DEFAULT_DATA).read("decisions"); by={r["cid"]:r["action"] for r in records if r.get("pregame") and r.get("by")=="matthew"}
    return {oq.identity(c):by.get(cid(c)) for c in card["calls"]}
