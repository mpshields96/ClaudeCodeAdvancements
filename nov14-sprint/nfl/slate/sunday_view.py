from datetime import timedelta
from html import escape
from urllib.parse import urlsplit,quote
from sunday_extras import watchlist,movement,personnel_at_call,personnel_summary
from sunday_card import S,L,central,window
import sunday_quotes as oq
def h(t):return escape(str(t),quote=True)
def link(url,text):
    try: u=urlsplit(url or "")
    except ValueError: return ""
    return f'<a href="{h(url)}" rel="noreferrer noopener" target="_blank">{h(text)} ↗</a>' if u.scheme=="https" and u.hostname and not u.username and not u.password else ""
def odds(n):return f"{n:+d}".replace("-","−") if type(n) is int else "—"
def pct(p):return "Unknown" if p is None else f"{100*p:.1f}%"
STYLE="""
:root{--ink:#162b38;--soft:#536772;--blue:#145875;--paper:#fbf9f3;--line:#d3d9d7;--green:#215343;--rust:#864327}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,Arial,sans-serif}main{max-width:1040px;margin:auto;padding:2.1rem clamp(1rem,4vw,3.5rem) 5rem}header{border-top:5px solid var(--ink);padding-top:1.1rem}h1,h2,h3{font-family:Charter,Georgia,serif;line-height:1.14;margin:.45em 0}h1{font-size:clamp(2.5rem,6vw,4.4rem);letter-spacing:-.04em}h2{font-size:1.75rem}h3{font-size:1.3rem}p{margin:.5rem 0}.eyebrow,th{color:var(--soft);font-weight:700;letter-spacing:.1em;font-size:.72rem;text-transform:uppercase}.sub,small{color:var(--soft)}.bar{display:flex;flex-wrap:wrap;gap:.65rem;align-items:center;margin:1.15rem 0}.bar form{margin:0}a{color:var(--blue)}button,.btn{display:inline-block;background:var(--blue);color:white;font-size:.91rem;font-weight:650;border:0;border-radius:.35rem;padding:.65rem .95rem;text-decoration:none;cursor:pointer}.secondary,.btn.secondary{border:1px solid var(--line);background:transparent;color:var(--ink)}button:focus-visible,summary:focus-visible{outline:3px solid #ba7406}.band{padding:.85rem 1rem;border-left:4px solid var(--blue);background:#edf3f4;margin:.85rem 0}.notice{background:#fff1d8;border-color:#976c26}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,19rem),1fr));gap:1rem;margin:1rem 0}.card{display:flex;flex-direction:column;background:#fffefa;border:1px solid var(--line);border-radius:.6rem;padding:1.15rem}.call{font-size:1.45rem;margin:.4rem 0 1rem}.quote,.pass{padding:.7rem .85rem;border-left:3px solid var(--green);background:#eaf2ec}.pass{border-color:var(--rust);background:#f8eee6}.quote p,.pass p{font-size:.88rem}.status{font-weight:750}.terms{display:grid;grid-template-columns:1fr 1fr;gap:.55rem;margin:.65rem 0}.terms label{font-size:.75rem;color:var(--soft);display:block}.section{margin:2rem 0;border-top:2px solid var(--ink);padding-top:1rem}.row{border-top:1px solid var(--line);padding:.6rem 0}details{border-top:1px solid var(--line);margin-top:.8rem;padding:.6rem 0}summary{cursor:pointer;font-weight:650;color:var(--blue)}table{border-collapse:collapse;width:100%;font-size:.89rem}th,td{text-align:left;vertical-align:top;padding:.5rem .3rem;border-bottom:1px solid var(--line)}.scroll{overflow:auto}input,select,textarea{font:inherit;max-width:100%;width:100%;padding:.45rem;border:1px solid #9daaad;background:white;border-radius:.25rem}textarea{height:4.7rem}form label{display:block;margin:.6rem 0}.small{font-size:.86rem}.mono{font-variant-numeric:tabular-nums}.tag{font-size:.76rem;font-weight:700;color:var(--blue)}.record{font-size:.88rem;white-space:pre-wrap;overflow-wrap:anywhere}.right{text-align:right}.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr));gap:1rem}ul{padding-left:1.3rem}footer{color:var(--soft);margin-top:2rem;font-size:.85rem}a,button{touch-action:manipulation}@media(max-width:600px){main{padding:1rem 1rem 3rem}th,td{padding:.35rem .2rem}.bar button,.bar .btn{font-size:.84rem}.call{font-size:1.35rem}}
"""
NAMES=oq.verify_card.BOOK_NAMES
def html_page(title,body,script=""):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+h(title)+'</title><style>'+STYLE+'</style><main>'+body+'</main>'+script+'</html>'
def form(path,label,token,cls="secondary"):
    return f'<form method="post" action="{h(path)}"><input type="hidden" name="token" value="{h(token)}"><button class="{cls}">{h(label)}</button></form>'
def view(card,snap,obs,*,token="",notice="",state=None,controls="",reports=None,price_slate=None):
    reports=reports or []; active=bool(token); now=oq.utc()
    rev_path=S/"results/sunday_20261115_review_evidence.json"
    try:extra=oq.read(rev_path)
    except (ValueError,OSError):extra={}
    if extra.get("capture_sha256")!=card.get("snapshot_sha256") or (extra and oq.when(extra["issued_utc"])!=oq.when(card["issued_utc"])):extra={}
    body="""<header><span class="eyebrow">Sunday field notes &nbsp; / &nbsp; Week 10 · November 15, 2026</span><h1>Sunday NFL card</h1>
    <p class="sub">The calls, the price that makes each playable, and the football questions still open.</p></header>"""
    if notice: body+=f'<p role="status" class="band notice">{h(notice)}</p>'
    source={"saved":"Saved observation · offline","reused":"Recent shared check · no new request","live":"Odds API exact-line check","failed":"Feed unavailable"}.get(obs["source"],"Saved observation")
    estimate=oq.estimate(card,now)
    balance=obs["credits_remaining"]
    if active:
        body+='<div class="bar">'+form("/refresh","Check exact prices",token,"")+form("/pdf","Export short PDF",token)+'<a class="btn secondary" href="#experiment">Pregame notebook</a><a class="btn secondary" href="/scorecard">After the games</a><a class="btn secondary" href="/weeks">Other Sundays</a></div>'
    body+=f'<p class="small sub">{h(source)}: {h(central(obs["checked_utc"]))} ({h(obs["checked_utc"])}). This check used {h(obs["credits_used"] if obs["credits_used"] is not None else "unconfirmed")} free credits. Last reported balance: {h(balance if balance is not None else "unknown")}.</p>'
    if not active: body+='<p class="band">Saved, read-only card. Open <b>Open Sunday NFL.command</b> on this Mac to recheck prices, record a view or generate the PDF.</p>'
    if active: body+=f'<small>Up to {estimate} credits for a fresh check. Reopening within two minutes reuses the same observation. No background polling.</small>'
    if len({c["event_id"] for c in card["calls"]})<len(card["calls"]):
        body+='<p class="band">Same-game selections share game risk. A change in score, pace or personnel can affect both picks.</p>'
    body+='<div class="cards">'
    quotes={q["contract_id"]:q for q in obs["quotes"]}
    for c in card["calls"]:
        e=c["engine"]; q=quotes[oq.identity(c)]
        w={"early":"Munich / noon","late":"Afternoon","night":"Sunday night"}[c["bucket"]]
        started=oq.when(c["kickoff"])<=now
        expired=not 0<=(now-oq.when(obs["checked_utc"])).total_seconds()<=oq.FRESH
        status=q["status"]
        if started:status="Game started"
        elif expired and status in ("Price qualifies","Pass at this price"):status="Saved observation only"
        own=(state or {}).get(oq.identity(c))
        eligible=active and status=="Price qualifies" and own not in ("pass","alternative")
        badge={"Price qualifies":"Price meets floor · verify lineup","Pass at this price":"Pass · price below floor","Could not verify the live quote":"Pass · price unverified","Exact line unavailable at qualifying odds":"Pass · exact line unavailable","Game started":"Closed · game started","Saved observation only":"Saved quote · recheck before use"}.get(status,"Pass · unavailable")
        body+=f'<article class="card"><span class="eyebrow">{h(w)} · {h(central(c["kickoff"]))}</span><h2 class="call">{h(c["label"])}</h2>'
        body+=f'<div data-deadline="{min(oq.when(obs["checked_utc"]).timestamp()+oq.FRESH,oq.when(c["kickoff"]).timestamp()) if eligible else 0}" class="{"quote" if eligible else "pass"}"><span class="status">{h(badge)}</span>'
        if "price" in q: body+=f'<p><b>{h(q["sportsbook"])} {odds(q["price"])}</b> · book update {h(central(q["book_updated_utc"]))}</p>'
        if eligible and q.get("book_event_link"):body+='<p>'+link(q["book_event_link"],"Official event page")+'</p>'
        if own:body+=f'<p><strong>Your pregame view: {h(own)}.</strong> The original call remains on record.</p>'
        body+='</div>'
        if c["event_id"]=="3c71d515b726f1096aabb435badb83fd" and c["market"]=="h2h":
            body+='<p class="small"><b>Independent review: pass at −166.</b> Claude agrees Kansas City is likelier to win but sees too little return for the price.</p>'
        if c["subject"]=="Jaylen Warren" and c["market"]=="player_reception_yds" and c["point"]==22.5:
            body+='<p class="small"><b>Independent review: conditional lean.</b> Warren cleared today’s line in 4 of his last 5 and 7 of 8 current-season appearances; he beat the actual historical lines in 6 of 8. Only BetMGM quoted exactly 22.5 in the frozen capture. Its two sides implied 50% without the margin; there was no second book at this line.</p>'
        body+=f'<div class="terms"><div><label>Minimum acceptable</label><b>{odds(c["minimum_price"])} or better</b></div><div><label>Original observation</label><b>{h(NAMES[c["observed_book"]])} {odds(c["observed_price"])}</b></div></div>'
        body+=f'<p><b>Why:</b> {h(c["rationale"])}</p><p><b>Check before kickoff:</b> {h(c["condition"])}</p>'
        body+=personnel_at_call(c)
        risk=c["risk"].replace(c["condition"],"").strip()
        body+=f'<p><b>What could go wrong:</b> {h(risk)}</p><details><summary>Price, evidence and value</summary><p>Original break-even: {h(pct(e["break_even"]))}. Other-book estimate at this exact line: {h(pct(e.get("market_probability") if e.get("other_two_sided_books",0)>0 else None))}. Model win estimate: {h(pct(e.get("model_estimate")))}.</p>'
        add=extra.get("by_call",{}).get(e["id"],{})
        for k in ("display","appearance_display"):
            if add.get(k):body+=f'<p><b>Pregame evidence:</b> {h(add[k])}</p>'
        if add.get("players"):body+=" "+link(add["players"][0]["source_url"],"Reported game designations")
        comp=q.get("comparison",{})
        if comp: body+='<p>Exact prices at the check: '+', '.join(h(NAMES.get(k,k))+" "+odds(v) for k,v in comp.items())+'.</p>'
        roi=e.get("reference_return_per_unit_decided") if e.get("other_two_sided_books",0)>0 else None
        if roi is None: body+='<p>No independently priced expected return is available for this exact contract.</p>'
        else: body+=f'<p>Peer-price estimate: {roi*100:+.1f}¢ per $1 at the original price, excluding pushes. This is a comparison with other books, not measured profit.</p>'
        for mv in e.get("price_observations",[])[:2]: body+=f'<p>{h(NAMES.get(mv["book"],mv["book"]))}: first observed {odds(mv["earliest_observed_price"])} at {h(central(mv["earliest_observed_utc"]))}; later {odds(mv["latest_observed_price"])} at {h(central(mv["latest_observed_utc"]))}. Neither is a verified opener or closing price.</p>'
        body+=' '.join(link(u,"Team evidence") for u in c.get("sources",[]))+'</details></article>'
    body+='</div>'
    for w,label in [("early","Morning / noon"),("late","Afternoon"),("night","Sunday night")]:
        if not any(c["bucket"]==w for c in card["calls"]):body+=f'<div class="band"><b>{label}: Pass.</b> {h(card["window_notes"].get(w,"No released selection.").removeprefix("Pass. "))}</div>'
    body+=f'<small>Decisions frozen {h(central(card["issued_utc"]))} ({h(card["issued_utc"])}). Market coverage: five Louisiana books in this feed; your book can offer different terms. No ticket is created by a price check.</small>'
    half=extra.get("by_window",{}).get("late",{})
    if half:body+='<details><summary>Afternoon pass: first-half scores</summary><p>'+h(half["display"])+'</p><p>Arizona points: '+", ".join(str(x["points"]) for x in half["arizona_points_scored"])+'.</p></details>'
    body+=movement(card)+watchlist(card)+personnel_summary(snap,active)
    body+='<section class="section"><span class="eyebrow">Field guide</span><h2>The Sunday slate</h2><p>Munich is a neutral-site game. There is no selection there. The earliest observed price is not necessarily the opener.</p>'
    use=price_slate or snap
    body+=f'<details><summary>Games and market coverage · {len(use["games"])} pregame games in snapshot</summary><p class="small">Observed {h(use["captured_utc"])}. Frozen decisions remain tied to their original slate.</p><div class="scroll"><table><tr><th>Chicago kickoff</th><th>Matchup</th><th>Books</th><th>Markets</th></tr>'
    by_id={g["id"]:g for g in use["event_odds"]}
    for g in sorted(use["games"],key=lambda g:g["commence_time"]):
        bs=g["bookmakers"]+by_id.get(g["id"],{}).get("bookmakers",[])
        markets={m["key"] for b in bs for m in b["markets"]}
        match=h(g["away_team"])+" at "+h(g["home_team"])
        if active:match=f'<a href="/game/{h(g["id"])}">{match}</a>'
        body+=f'<tr><td>{h(central(g["commence_time"]))}</td><td>{match}</td><td>{len({b["key"] for b in bs})}</td><td>{len(markets)}</td></tr>'
    body+='</table></div>'
    if active:body+='<p class="small">A complete new snapshot can use up to 75 free credits for 12 games. A capture less than 15 minutes old is reused. This does not issue new bets.</p>'+form("/slate","Get detailed slate · up to 75 credits",token)
    body+='</details></section>'
    if controls:body+='<section class="section" id="experiment"><span class="eyebrow">Prospective experiment</span><h2>Pregame notebook</h2>'+controls+'</section>'
    if reports:
        body+='<section class="section"><span class="eyebrow">Evidence</span><h2>Review the card</h2><ul>'+''.join(f'<li><a href="{h(url)}">{h(label)}</a></li>' for label,url in reports)+'</ul></section>'
    body+='<footer>Source: The Odds API and the credited team reports. A conditional selection, observed odds, and an accepted ticket are three different records. Matthew submits any wager himself.</footer>'
    script="""<script>function expire(){document.querySelectorAll('[data-deadline]').forEach(x=>{if(+x.dataset.deadline&&Date.now()/1000>+x.dataset.deadline){x.className='pass';x.querySelector('.status').textContent='Saved quote · recheck before use';x.querySelectorAll('a').forEach(a=>a.remove());x.dataset.deadline=0}})}expire();setInterval(expire,3000)</script>"""
    return html_page("Sunday NFL card · November 15",body,script)
