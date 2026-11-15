"""Read the one journal; keep real tickets, decisions and comparisons distinct."""
from html import escape as h
from datetime import timedelta
from sunday_card import S,L,central
from sunday_view import html_page,form
import sunday_notebook as nb
import sunday_quotes as oq
def scoreboard(card,token,notice="",root=None):
    day=card['slate_date']; weekly=day!="2026-11-15"
    j=nb.api(); log=j.Journal(root or j.DEFAULT_DATA); st=j.State(log)
    body='<a href="/">← Sunday card</a><header><span class="eyebrow">Decision review · November 15</span><h1>After the games</h1><p>Read what was actually decided before kickoff, what the scoreboard supports, and how your own accepted ticket differed.</p></header>'
    if weekly:body=body.replace('href="/"','href="/week/'+day+'"').replace("November 15",day)
    if notice:body+='<p class="band">'+h(notice)+'</p>'
    if not st.first_by_role("call"):
        return html_page("After the games",body+'<p class="band">No released calls have been imported into the experiment journal yet. There are no results to grade.</p>')
    grade=j.evaluate(st);sc=grade["score"]
    def row(title,b,unit="flat units"):
        decided=b["win"]+b["loss"]+b["push"]+b.get("void",0)
        value=(f'{b["units"]:+.2f} '+unit) if decided else "Pending" if b["unknown"] else "—"
        return f'<tr><td>{h(title)}</td><td>{b["win"]}–{b["loss"]}–{b["push"]}</td><td>{b["unknown"]}</td><td>{h(value)}</td></tr>'
    body+='<section class="section"><h2>Recommendations and personal decisions</h2><p>Wins–losses–pushes. Unreported outcomes stay pending; a missing player stat never becomes a zero.</p><div class="scroll"><table><tr><th>Stream</th><th>Record</th><th>Pending</th><th>Net</th></tr>'
    for key,title in [("bot_calls","Original calls · one hypothetical unit each"),("your_takes","Pregame personal takes"),("your_alternatives","Pregame alternatives")]:body+=row(title,sc[key])
    if sc["your_tickets"]:
        for unit,data in sc["your_tickets"].items():body+=row("Tickets reported by Matthew · score-based estimate",data,unit)
    else:body+='<tr><td>Tickets reported by Matthew</td><td colspan=3>No accepted ticket recorded.</td></tr>'
    body+='</table></div>'
    for unit,bucket in sc.get('confirmed_ticket_returns',{}).items():
        if not bucket['confirmed_count']:body+='<p>Actual cash: not yet reported by the operator. Unconfirmed tickets contribute no cash figure.</p>';continue
        body+=f'<p><b>Operator-confirmed returns:</b> {bucket["confirmed_count"]} reported · {bucket["pending_count"]} pending · stake {bucket["confirmed_stake"]:.2f}, gross returned {bucket["gross_return"]:.2f}, net {bucket["net_return"]:+.2f} {h(unit)}.</p>'
    body+='</section><section class="section"><h2>Prespecified comparisons</h2>'
    for m in grade.get('controls',[]):
        def outcome(text):return 'pending' if text=='unknown' else h(text)
        body+=f'<p><b>{h(m["label"])}</b> ({m["price"]:+d}): {outcome(m["result"])}. Matched before kickoff: <b>{h(m["control_label"])}</b> ({m["control_price"]:+d}): {outcome(m["control_result"])}. The comparison is never a ticket or a third call.</p>'
    if not grade.get('controls'):body+='<p>No separately registered role comparison for this edition.</p>'
    b=sc["benchmarks"]
    body+='<div class="scroll"><table><tr><th>Policy</th><th>Record</th><th>Pending</th><th>Net</th></tr>'
    for k,title in [("moneyline_favorites_in_band","All moneyline favorites in the price band"),("top_favorite_per_window_in_band","Top in-band favorite per window"),("price_matched_controls","Other exact contracts matched by price and market")]:
        if k in b:body+=row(title,b[k])
    body+='</table></div></section>'
    body+='<section class="section"><h2>Individual calls</h2>'
    for c in grade["calls"]:body+=f'<p><b>{h(c["label"])}</b> · {h(c["result"].replace("unknown","pending"))}</p>'
    if grade.get('decisions'):
        body+='<h3>Your pregame judgments</h3>'
        for d in grade['decisions']:
            body+=f'<p><b>{h(d["action"].title())}: {h(d["label"])}</b> · {h(d["reason"])}<br>Original: {h(d["bot_result"].replace("unknown","pending"))}. Your choice: {h(d["your_label"])} · {h(d["result"].replace("unknown","pending"))}.</p>'
    if grade.get('tickets'):
        body+='<h3>Reported tickets and actual terms</h3>'
        for t in grade['tickets']:
            offered=("%+d"%t["offered_price"]) if t.get("offered_price") else "unknown"
            net=('pending' if t['units'] is None else '%+.2f %s'%(t['units'],t['stake_unit']))
            flag=' · outside original price band' if not oq.price(t['price']) else ''
            floor=t.get("issued_minimum_price")
            if t["line_differs"]:
                flag+=' · different accepted line'
            elif floor and t.get("meets_issued_minimum") is False:
                flag+=' · below original minimum '+format(floor,'+d')
            placed=t.get("placed_utc_reported")
            times=("Accepted "+central(placed) if placed else "Acceptance time unreported")+" · recorded "+central(t["recorded_utc"])+(" after kickoff" if not t.get("recorded_before_kickoff",True) else "")
            body+=f'<p><b>{h(t["label"])}</b> · {h(t["book"])} · offered {offered}, accepted {t["price"]:+d}{flag}; {t["stake"]:g} {h(t["stake_unit"])}.<br>{h(times)}.<br>Original: {h(t["bot_label"])} {t["bot_price"]:+d}. Score-based estimate: {h(t["result"].replace("unknown","pending"))} · {h(net)}. </p>'
            settle=t.get('settlement')
            if settle:
                body+=f'<p><b>Actual operator return:</b> {settle["gross_return"]:.2f} {h(t["stake_unit"])} including stake; net {t["actual_net"]:+.2f}. {h(settle["outcome"].capitalize())} · self-reported.</p>'
            else:body+='<p><b>Actual operator return:</b> unreported. A box-score estimate is not a statement of cash paid.</p>'
            if t.get('ticket_id'):
                from sunday_week_review import hidden
                fields=hidden('token',token)+hidden('date',day)+hidden('ticket_id',t['ticket_id'])
                if settle:fields+=hidden('prior_sha',settle['sha'])
                options=''.join('<option value="'+k+'">'+v+'</option>' for k,v in [('win','Win'),('loss','Loss'),('push','Push'),('void','Void'),('refund','Refund'),('cashout','Cash out'),('adjustment','Adjustment'),('other','Other')])
                body+='<details><summary>'+('Correct' if settle else 'Record')+' this ticket’s book settlement</summary><form method="post" action="/ticket/settle">'+fields+'<label>Amount the operator returned, including stake ('+h(t['stake_unit'])+')<input required name="gross_return" type="number" min="0" step="0.01"></label><label>What did the book report?<select name="outcome" required><option value="">Choose</option>'+options+'</select></label><label>Note'+(' (required for corrections)' if settle else ' (optional)')+'<input name="note" maxlength="400" '+('required' if settle else '')+'></label><label><input type="checkbox" style="width:auto" required name="confirmed" value="yes"> I checked this exact ticket’s settled amount.</label><button>Save reported return</button></form></details>'
    if grade.get('research'):
        body+='<h3>Rules we tested</h3>'
        for r in grade['research']:
            body+=f'<details><summary>{h(r["status"].capitalize())} · {h(r["title"])}</summary><p>{h(r["summary"])}</p></details>'
    body+='<p>Closing-price comparison needs the same book, market, side and exact threshold at a defensible pregame close. An overnight check is not a close.</p>'
    if any(oq.utc()>=oq.when(c["kickoff"])+timedelta(minutes=150) for c in card["calls"]):
        if (S/"experiment/postgame").is_dir():body+='<form method="post" action="/postgame/import"><input type="hidden" name="token" value="'+h(token)+'"><input type="hidden" name="date" value="'+h(day)+'"><button>Check public finals and player results</button></form>'
    else:body+='<p class="band">No released game is due for a public final yet. The import button becomes available 150 minutes after the first selected kickoff.</p>'
    body+='</section>'
    return html_page("Sunday scorecard",body)


def import_public(card,root=None,*,clock=oq.utc):
    from datetime import timedelta
    from pathlib import Path
    import importlib
    import sys
    j=nb.api();root=Path(root or j.DEFAULT_DATA)
    starts=[oq.when(c['kickoff']) for c in card.get('calls',[])]
    if not starts or min(starts)+timedelta(minutes=150)>clock():
        raise ValueError('There is no released game due for a public final yet. No request was made.')
    folder=S/'experiment/postgame'
    if str(folder) not in sys.path:sys.path.insert(0,str(folder))
    fetch=importlib.import_module('espn_fetch')
    with oq.lock(root/'public-import'):
        result=fetch.fetch_and_import(str(root),save_root=str(root/'public-captures'))
    r=result.get('fetch',{}).get('requests',[]);checked=sum(x.get('error') is None for x in r)
    message=f"Public results: {checked} of {len(r)} source requests succeeded; {len(result['recorded_finals'])} new finals, {len(result['recorded_players'])} new player results. {len(result['pending'])} items remain pending."
    if result['refused']:message+=' '+str(len(result['refused']))+' source or data checks were refused; existing records are preserved.'
    return message

def report_settlement(fields,root=None):
    import math
    if fields.get("confirmed")!="yes":raise ValueError("Check the settled amount against the specific ticket first.")
    j=nb.api();log=j.Journal(root or j.DEFAULT_DATA)
    if not hasattr(j,'record_settlement'):raise ValueError("Ticket reconciliation is not available in this journal version.")
    try:amount=float(fields["gross_return"])
    except (ValueError,KeyError):raise ValueError("Enter the actual gross return including stake.") from None
    if not math.isfinite(amount) or amount<0:raise ValueError("Gross return must be zero or greater.")
    try:j.record_settlement(log,fields.get('ticket_id',''),amount,fields.get('outcome',''),oq.utc(),confirmed=True,prior_sha=fields.get('prior_sha') or None,note=fields.get('note','').strip(),by='matthew')
    except j.JournalError as exc:raise ValueError(str(exc)[:210]) from None
    return "Recorded the book’s return for this ticket. The original selection grade remains separate."
