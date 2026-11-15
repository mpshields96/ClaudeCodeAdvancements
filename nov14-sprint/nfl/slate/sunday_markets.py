"""Browse exact contracts for any game without an additional external request."""
from sunday_view import html_page,h,odds,NAMES
from sunday_card import central,S
from compare_books import contract_prices
import sunday_quotes as oq
MARKETS={"h2h":"Moneyline","spreads":"Spread","totals":"Game total","totals_h1":"First-half total","team_totals":"Team total","team_totals_h1":"First-half team total","player_pass_yds":"Passing yards","player_rush_yds":"Rushing yards","player_reception_yds":"Receiving yards"}
def page(snapshot,eid):
    events=[g for g in snapshot["games"] if g["id"]==eid]
    if len(events)!=1:raise ValueError("Game is not in this capture.")
    g=events[0];other=[a for a in snapshot["event_odds"] if a["id"]==eid]
    rows=contract_prices(dict(games=[g],event_odds=other,captured_utc=snapshot["captured_utc"]))
    name=g["away_team"]+" at "+g["home_team"]
    body='<a href="/">← Sunday card</a><header><span class="eyebrow">'+h(central(g["commence_time"]))+'</span><h1>'+h(name)+'</h1></header>'
    body+=f'<div class="band"><b>Observed market board.</b> Captured {h(snapshot["captured_utc"])}. These are reference prices. Selecting a row does not add a bet to the released card.</div>'
    data=S/"slate_20261115.json"
    if data.is_file():
        team=next((t for t in oq.read(data)["games"] if t["odds_event_id"]==eid),None)
        if team:
            if team["neutral"]:body+='<p><b>Neutral venue.</b> No home-field advantage assigned here.</p>'
            body+='<div class="two">'
            for which in ("away","home"):
                t=team["teams"][which];body+=f'<article class="card"><span class="eyebrow">{h(t["games_played"])} completed games</span><h3>{h(t["name"])}</h3><p>{h(t["su"])} straight up · {h(t["ats"])} against the spread</p><p>{h(t["pf_per_game"])} points scored / {h(t["pa_per_game"])} allowed per game.</p></article>'
            body+='</div>'
            hh=team.get("h2h",[])
            if hh:
                recent=max(hh,key=lambda x:x.get("gameday",""));body+=f'<p>Most recent recorded meeting ({h(recent["gameday"])}): {h(recent["away"])} {h(recent["away_score"])}, {h(recent["home"])} {h(recent["home_score"])}. Personnel can change between meetings.</p>'
            body+='<p>Game-day inactives were unavailable in the frozen team file.</p>'
    from sunday_extras import personnel_game
    body+=personnel_game(snapshot,eid)
    body+=f'<section class="section"><h2>Compare exact lines</h2><p>{len(rows)} qualifying contract sides. Search by player, team, market or line. Best is limited to the −200 to +200 band; all exact book quotes are shown.</p><label>Find a contract<input id="filter" type="search" placeholder="e.g. receiving yards or team total"></label><div class="scroll"><table><thead><tr><th>Contract</th><th>Best in band</th><th>Exact book prices</th></tr></thead><tbody>'
    for r in sorted(rows,key=lambda r:(r["market"],r["subject"],r["side"],r["point"] or 0)):
        label=" · ".join(str(x) for x in [MARKETS.get(r["market"],r["market"]),r["subject"],r["side"],r["point"]] if x is not None and x!="")
        prices=", ".join(NAMES.get(b,b)+" "+odds(x["price"]) for b,x in sorted(r["all_prices"].items()))
        body+=f'<tr><td>{h(label)}</td><td>{h(NAMES[r["book"]])} {odds(r["price"])}</td><td>{h(prices)}</td></tr>'
    body+='</tbody></table></div></section>'
    return html_page(name,body,"<script>let f=document.getElementById('filter');f.oninput=()=>{let s=f.value.toLowerCase();for(const r of document.querySelectorAll('tbody tr'))r.hidden=!r.innerText.toLowerCase().includes(s)&&!r.textContent.toLowerCase().includes(s)}</script>")
