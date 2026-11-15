"""Render the weekly owner's screen; submit human reviews against their displayed edition."""
from html import escape as h
import importlib
import json
from pathlib import Path
import sys
from sunday_card import S,central
from sunday_view import form,odds,NAMES
from sunday_intake import day_value
def api():
    p=S/"weekly/weekly_api.py"
    if not p.is_file():return None
    sys.path.insert(0,str(p.parent)) if str(p.parent) not in sys.path else None
    return importlib.import_module("weekly_api")
def val(v):return h(str(v),quote=True)
def hidden(name,v):return f'<input type="hidden" name="{val(name)}" value="{val(v)}">'
def windows(screen):return screen["windows"]
def lines(win):
    return [(g,c) for g in win["games"] for c in g.get("contracts",[]) if c.get("reviewable")]
def make_form(win,sc,token,state):
    w=win["name"];day=sc["date"]; edition=sc["edition"]
    fields=hidden("token",token)+hidden("date",day)+hidden("window",w)+hidden("sha",edition["sha256"])+hidden("captured",edition["captured_utc"])
    if state.get("row_id"):fields+=hidden("supersedes",state["row_id"])
    options='<option value="">Choose an exact contract</option>'
    for game,c in lines(win):
        b=c.get("best_in_band") or c["best"]
        options+=f'<option value="{val(c["id"])}">{val(game["away"]["abbr"])}–{val(game["home"]["abbr"])} · {val(c["label"])} · {odds(b["price"])} {val(NAMES.get(b["book"],b["book"]))}</option>'
    html=f'<details><summary>Record a pregame review · {val(w)}</summary><p>Choose no play or up to two distinct contracts. Two picks in the same game can depend on the same score or game script. Leaving a window alone keeps it unreviewed.</p><form method="post" action="/week/review">{fields}<label>Decision<select name="decision"><option value="">Choose a decision</option><option value="no_play">Explicit no play</option><option value="calls">Record exact selection(s)</option></select></label><label>Window note<input name="note" maxlength="450" placeholder="Why take or pass?"></label>'
    for n in range(2):
        html+=f'<details><summary>{"First selection" if n==0 else "Optional second selection"}</summary><label>Exact line<select name="id{n}">{options}</select></label><label>Minimum American price<input name="floor{n}" type="number" step="1" placeholder="e.g. -115"></label>'
        for f,lab in [("rationale","Football case"),("risk","Strongest counterargument"),("condition","What must still be true at kickoff?"),("source","Supporting source URL (optional)")]:
            html+=f'<label>{lab}<input name="{f}{n}" maxlength="650"></label>'
        html+='</details>'
        html+=f'<label>Personnel for selection {n+1}<select name="personnel{n}"><option value="unknown">Availability or replacement impact unverified</option><option value="checked">Checked current status; no material unresolved absence</option><option value="unresolved">Material absence; replacement role or impact unresolved</option><option value="assessed">Material absence assessed in my rationale and risk</option></select></label>'
    return html+'<button>Save my dated review</button></form></details>'
def render(day,token,observation=None):
    import sunday_week_release as rel
    day=str(day)
    week=api()
    if week is None:return None
    sc=week.screen(str(day)); rev=week.list_reviews(str(day));states=rev.get("window_states",{})
    body='<div class="band"><b>Provisional screen.</b> Market quotes are observations, not new picks. Only explicit decisions count as reviewed.</div>'
    missing=list(sc.get("missing",[]))+list(sc.get("warnings",[]))
    if missing:body+='<p class="small">'+val(" · ".join(str(x) for x in missing))+'</p>'
    if not rev.get("chain_ok"):raise ValueError("The dated review history failed verification.")
    body+=rel.card_panel(day,token,observation)+rel.injuries_panel(day,token)+rel.football_screen(sc)
    body+=rel.action('/week/reacquire',day,token,'Update team scores and main lines · up to 3 free credits')
    body+=rel.action('/week/preview',day,token,'Export provisional scouting PDF · no decisions recorded')
    n=sum(len(w['games']) for w in windows(sc))
    body+='<details><summary>Player props, first-half and team-total markets</summary><p>Explicitly request the provider’s six detailed market types plus main lines. Games and books may not offer all markets. Each captured edition remains archived.</p>'+rel.action('/week/details',day,token,'Get detailed markets · up to '+str(3+6*n)+' free credits')+'</details>'
    for win in windows(sc):
        w=win["name"];state=states.get(w,{})
        if isinstance(state,str):state={"state":state}
        body+=f'<section class="section"><span class="eyebrow">{val(w)} window</span><h2>{val(win.get("label",w))}</h2><p>Decision: <b>{val(state.get("state","unreviewed").replace("_"," "))}</b>.</p><details><summary>Browse {len(lines(win))} eligible contract sides</summary><div class="scroll"><table><tr><th>Game / time</th><th>Eligible exact contract</th><th>Best quote</th></tr>'
        for g,c in lines(win):
            b=c.get("best_in_band") or c["best"];body+=f'<tr><td>{val(g["away"]["abbr"])}–{val(g["home"]["abbr"])} · {val(g["kickoff_ct"])}</td><td>{val(c["label"])}</td><td>{odds(b["price"])} {val(NAMES.get(b["book"],b["book"]))}</td></tr>'
        body+='</table></div></details>'+(make_form(win,sc,token,state) if win.get("state")!="closed" else "<p>Pregame review closed.</p>")+'</section>'
    any_review=any((x.get("state","") if isinstance(x,dict) else str(x)) in ("calls","no_play") for x in states.values())
    body+=annotations_form(sc,token)
    if any_review:
        body+='<div class="bar"><form method="post" action="/week/publish">'+hidden("token",token)+hidden("date",day)+'<button>Generate reviewed card and PDF</button></form></div>'
    return body
def submit(fields):
    from urllib.parse import urlsplit
    week=api();day=str(day_value(fields["date"]));w=fields["window"]
    if week is None:raise ValueError("Dated review module unavailable.")
    sc=week.screen(day); e=sc["edition"]
    if fields["sha"]!=e["sha256"] or fields["captured"]!=e["captured_utc"]:raise ValueError("This edition was refreshed. Review the displayed current prices before saving.")
    win=next((v for v in windows(sc) if v["name"]==w),None)
    if win is None:raise ValueError("Unknown window.")
    opts={c["id"]:c for _,c in lines(win)}
    games={c["id"]:g for g,c in lines(win)}
    decision=fields.get("decision");calls=[]
    if decision not in ("calls","no_play"):raise ValueError("Choose a decision or leave the window unreviewed.")
    for n in range(2):
        idx=fields.get("id"+str(n))
        if not idx:continue
        if idx not in opts:raise ValueError("The contract is not in this reviewed market window.")
        if decision!="calls":raise ValueError("Clear selected contracts to record a no-play window.")
        c=opts[idx];r={k:c[k] for k in ("event_id","market","side","subject","point")}
        r["minimum_price"]=int(fields.get("floor"+str(n),"0"))
        for k in ("condition","rationale","risk"):
            r[k]=fields.get(k+str(n),"").strip()
            if not r[k] or len(r[k])>650:raise ValueError("Each call needs a brief football case, risk, and condition.")
        src=fields.get("source"+str(n),"").strip()
        if src and (urlsplit(src).scheme!="https" or not urlsplit(src).hostname):raise ValueError("Use a public HTTPS source link.")
        role=fields.get("personnel"+str(n),"unknown")
        if role not in ("unknown","checked","unresolved","assessed"):raise ValueError("Unknown personnel review.")
        if role in ("assessed","checked") and not src:raise ValueError("Cite your dated personnel source or leave personnel unverified.")
        add={"unknown":"Availability and replacement impact unverified; confirm before use.","unresolved":"Material absence: replacement role or impact unresolved. Hold this call pending verification.","assessed":"A material absence was reviewed; revisit the cited role evidence before kickoff.","checked":"Reviewer checked current personnel. Recheck final inactives."}[role]
        from sunday_week_release import availability
        game=games[idx];avail=availability(day).get('by_event',{}).get(str(game.get('espn_event_id')),{}).get('records',[])
        starters=[v for v in avail if v.get('starter_status')=='listed_first']
        if starters:
            facts=', '.join(x['player']+' ('+x['status']+')' for x in starters)
            add+=' Dated starter designations: '+facts+'. Check the latest team report and expected replacements.'
        for bulletin in avail:
            if bulletin.get("origin")=="operator_bulletin" and bulletin.get("reported_material"):
                add+=" Club bulletin dated "+bulletin["published"]+": "+bulletin["player"]+" ("+bulletin["status"]+"). "+bulletin["role"]+" Verify the latest role and final inactives."
        r["condition"]+=" "+add
        r["sources"]=[src] if src else [];calls.append(r)
    if len(calls)==2 and calls[0]["event_id"]==calls[1]["event_id"]:
        if all(calls[0].get(k)==calls[1].get(k) for k in ("market","side","point","subject")):raise ValueError("Choose two distinct contracts; the same bet cannot count twice.")

    payload={"api":"weekly/1","date":day,"author":"matthew","author_kind":"human","edition":{"sha256":e["sha256"],"captured_utc":e["captured_utc"]},"windows":{w:{"decision":decision,"note":fields.get("note","")[:450]}},"calls":calls,"supersedes":fields.get("supersedes"),"late":False}
    if decision=="calls" and not calls:raise ValueError("Select one or two exact contracts.")
    try:week.submit_review(day,payload)
    except week.Refused as err:raise ValueError(str(err)[:210]) from None
    return day


def annotations_form(sc,token):
    w=api();rows=w.list_annotations(sc['date'])
    if not rows.get('chain_ok'):raise ValueError('Independent note history failed verification.')
    out=['<section class="section"><h2>Independent review</h2><p>Record a reviewer’s concern, support or observation. A note does not issue a call. Use the actual reviewer’s name and source; authorship is self-reported.</p>']
    for a in rows['rows']:
        out.append('<p><b>'+val(a['author'])+' ('+val(a['author_kind'])+') · '+val(a['stance'])+'</b> · '+val(central(a['received_utc']))+('<br>After kickoff · retrospective.' if a['received_after_kickoff'] else '')+'<br>'+val(a['text'])+'</p>')
    fields=hidden('token',token)+hidden('date',sc['date'])+hidden('sha',sc['edition']['sha256'])+hidden('captured',sc['edition']['captured_utc'])
    opts='<option value="">Entire dated slate</option>'+''.join('<option value="'+val(c['id'])+'">'+val(c['label'])+'</option>' for win in sc['windows'] for _,c in lines(win))
    out+=['<details><summary>Add a sourced review note</summary><form method="post" action="/week/annotate">'+fields+'<label>Applies to<select name="contract">'+opts+'</select></label><label>Reviewer type<select required name="kind"><option value="">Choose</option>'+''.join('<option>'+k+'</option>' for k in w.AUTHOR_KINDS)+'</select></label><label>Actual reviewer name<input name="author" required maxlength="80"></label><label>Position<select name="stance"><option value="concern">Concern</option><option value="supports">Supports</option><option value="info">Information only</option></select></label><label>What did the reviewer find?<textarea name="text" required maxlength="450"></textarea></label><label>Supporting HTTPS link (optional)<input name="source" type="url"></label><button>Save attributed review note</button></form></details></section>']
    return ''.join(out)

def annotate(fields):
    w=api();day=str(day_value(fields['date']));ed=w.screen(day)['edition']
    if ed['sha256']!=fields.get('sha') or ed['captured_utc']!=fields.get('captured'):raise ValueError('This edition changed. Reopen the current review.')
    su=fields.get('source','').strip();cid=fields.get('contract')
    try:w.annotate(day,dict(date=day,author_kind=fields.get('kind'),author=fields.get('author'),stance=fields.get('stance'),text=fields.get('text'),sources=[su] if su else [],scope={'contract_id':cid} if cid else {},edition=dict(sha256=ed['sha256'],captured_utc=ed['captured_utc'])))
    except w.Refused as exc:raise ValueError(str(exc)[:210]) from None
    return day
