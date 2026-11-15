"""Read-only extensions for the published Sunday card: watchlist and observations."""
from pathlib import Path
from html import escape as h
from functools import lru_cache
from datetime import datetime,timezone
from sunday_card import L,S,central
import sunday_quotes as oq
def odds(n):return ("%+d"%n).replace("-","−")
def text(v):return h(str(v))
def movement(card,root=None):
    root=Path(root or L/"observations")
    # Only immutable observations with this exact fingerprint are considered.
    ids,fp=oq.keys(card);records=[]
    orig=root/oq.ORIG_FILE
    if orig.is_file() and oq.digest(orig)==oq.ORIG_OBS and oq.digest(L/"Sunday_Card.json")==oq.ORIG_CARD:
        old=oq.read(L/"Sunday_Card.json");oldids,oldfp=oq.keys(old)
        if oldfp==fp:
            ob=oq.read(orig)
            records.append((ob["checked_utc"],dict(zip(oldids,ob["quotes"]))))
    for p in sorted(root.glob("exact-observation-*.json")):
        try:
            o=oq.read(p)
            if o.get("fingerprint")==fp and set(o.get("by_contract",{}))==set(ids):
                records.append((o["checked_utc"],o["by_contract"]))
        except (ValueError,KeyError,TypeError,OSError):continue
    if not records:return ""
    r='<details><summary>Price history for the two exact calls</summary><p class="small">Each row is an observed best exact price. A different book is a new comparison, not same-book line movement. The final pregame close is unknown.</p><div class="scroll"><table><tr><th>Observed (CT)</th>'+''.join('<th>'+text(c["label"])+'</th>' for c in card["calls"])+'</tr>'
    for tm,qs in sorted(records,key=lambda x:x[0]):
        r+='<tr><td>'+text(central(tm))+'</td>'
        for k in ids:
            q=qs[k];r+='<td>'+((text(q.get("sportsbook",q.get("book","")))+" "+odds(q["price"])+' · '+text(q["status"])) if oq.price(q.get("price")) else text(q.get("status","unverified")))+'</td>'
        r+='</tr>'
    return r+'</table></div></details>'
@lru_cache(maxsize=2)
def _data(file,mtime,sha):
    d=oq.read(Path(file))
    if d["slate_date"]!="2026-11-15" or d["capture_sha256"]!=sha:raise ValueError("Stale watchlist")
    rows=d["ranked"]
    if len(rows)!=5 or [x["rank"] for x in rows]!=list(range(1,6)) or len({x["id"] for x in rows})!=5:raise ValueError("Incomplete watchlist")
    return d
def watchlist(card):
    path=S/"results/sunday_20261115_watchlist.json"
    if not path.is_file():return ""
    try:
        d=_data(str(path),path.stat().st_mtime_ns,card["snapshot_sha256"])
        ids={c["engine"]["id"] for c in card["calls"]}
        if any((row["id"] in ids)!=(row["status"]=="formal_call") or not oq.price(row["price"]) for row in d["ranked"]):raise ValueError("Unverifiable watchlist labels")
        supplement = d.get("supplement") or {}
        published = supplement.get("published_utc")
        show_notes = bool(published and oq.when(published) <= oq.utc())
        r = ('<section class="section"><h2>Five bets worth a look</h2>'
             '<p>Ranked ' + text(central(d["ranked_utc"])) + '. '
             'Only the two formal calls receive a separate price recheck.</p>')
        if show_notes:
            r += ('<p>Price review ' + text(central(published)) + '. The gap is the market’s estimated chance '
                  'minus the chance needed to break even at the original quote, in percentage points.</p>')
        r += ('<div class="scroll"><table><tr><th>#</th><th>Matchup and exact bet</th>'
              '<th>Captured price</th><th>Status and risk</th>')
        if show_notes:
            r += '<th>Market value at capture</th>'
        r += '</tr>'
        for row in d["ranked"]:
            stat = "Formal call" if row["id"] in ids else "Watchlist only"
            risk = text(row["risk_tag"])
            if show_notes and row.get("supplemental_risk"):
                risk += ('<details><summary>Personnel update</summary><small>Evidence as of '
                         + text(central(row["evidence_utc"])) + '</small><p>' + text(row["supplemental_fit"])
                         + '</p><p>' + text(row["supplemental_risk"]) + '</p></details>')
            r += (f'<tr><td>{row["rank"]}</td><td><b>{text(row["label"])}</b><br>{text(row["game"])} · '
                  f'{text(central(row["kickoff"]))}</td><td>{text(row["sportsbook"])} {odds(row["price"])}'
                  f'<br><small>{text(central(row["observed_utc"]))}</small></td><td><b>{stat}</b> · '
                  f'{text(row["volatility"])}<br>{risk}</td>')
            if show_notes:
                gap = f'{row["market_value_gap_pp"]:+.2f}'.replace("-", "−")
                r += (f'<td><b>{text(row["market_value_label"])}</b> · {gap} pp'
                      '<details><summary>Price basis</summary>' + text(row["market_value_detail"]) + '</details></td>')
            r += '</tr>'
        return r+'</table></div></section>'
    except (ValueError,KeyError,OSError,TypeError):return '<p class="band notice">The watchlist could not be matched to this card; no extra selections shown.</p>'


def personnel_at_call(call):
    """An exact decision's later football review never changes its frozen terms."""
    from sunday_view import link
    rows=call.get('engine',{}).get('replacement_context',[])
    if not isinstance(rows,list):rows=[]
    out=[]
    for r in rows:
        if not isinstance(r,dict) or not r.get('display'):continue
        try:
            when=oq.when(r['effective_as_of_utc'])
            if when>oq.utc() or when>=oq.when(call['kickoff']) or r.get('event_id',call['event_id'])!=call['event_id']:continue
        except (KeyError,TypeError,ValueError):continue
        sources=[link(s.get('url'),s.get('label','Football source')) for s in r.get('sources',[]) if isinstance(s,dict) and s.get('url') and 'api.the-odds-api.com' not in str(s.get('url'))]
        out.append('<div class="band"><b>Personnel review · '+text(central(r['effective_as_of_utc']))+'</b><br>'+text(r['display'])+(' <small>'+' · '.join(x for x in sources if x)+'</small>' if any(sources) else '')+'</div>')
    return ''.join(out) or '<p class="small"><b>Personnel coverage:</b> no verified replacement assessment attached to this selection. Recheck current inactives and roles before use.</p>'

def personnel_game(snapshot,eid):
    """Display dated team, player and paired market observations; missing is unknown."""
    from sunday_view import NAMES,link
    name=snapshot['day'];rep=S/'replacements'/('replacement_report_'+name.replace('-','')+'.json')
    note='<p class="small">No dated replacement review for this team or matchup. An unreviewed roster is not a clean injury report.</p>'
    if not rep.is_file():return note
    try:
        d=oq.read(rep);g=d['by_event'].get(eid);off=next(x for x in snapshot['games'] if x['id']==eid)
        if not g or d['schema_version']!='replacement_report/1' or oq.when(d['as_of_utc'])>=oq.when(off['commence_time']) or oq.when(d['as_of_utc'])>oq.utc():return note
        if {g['event']['home_team'],g['event']['away_team']}!={off['home_team'],off['away_team']}:return note
        body='<section class="section"><span class="eyebrow">Personnel · dated supplemental review</span><h2>Who absorbs the missing work?</h2><p>Posted player lines show what the books offered. They do not establish equal efficiency or how much an absence changed the team’s chance to win.</p>'
        for team,record in g['teams'].items():
            ctx=record.get('replacement_context',{});body+='<h3>'+text(team)+'</h3>'
            if record.get('screen_status')=='unknown_absence' or not record.get('absences'):
                body+=note;continue
            body+='<p><b>Availability:</b> '+text(', '.join(str(a['player'])+' ('+str(a['status'])+')' for a in record['absences']))+'.</p>'
            if ctx.get('qualifier'):body+='<p class="band">'+text(ctx['qualifier'])+'</p>'
            for p in record.get('candidates',[]):
                body+='<article><b>'+text(p['player'])+'</b> · versus starter: '+text(p.get('vs_starter','unknown'))+'.'
                stats=p.get('market',{}).get('stats',{})
                for key,label in [('rush_attempts','rush attempts'),('rush_yds','rush yards'),('rec_yds','receiving yards')]:
                    stat=stats.get(key,{})
                    if not isinstance(stat,dict):continue
                    bs=stat.get('books',[])
                    rows=[(b.get('book'),b.get('line'),b.get('over'),b.get('under')) for b in bs if isinstance(b,dict) and b.get('line') is not None]
                    if rows:
                        labels=[text(NAMES.get(b,b))+' '+text(l)+' ('+odds(o)+' / '+odds(u)+')' for b,l,o,u in rows if type(o) is int and type(u) is int]
                        if labels:body+='<br><small>'+text(label.capitalize())+' · threshold (over / under): '+', '.join(labels)+'</small>'
                comp=p.get('components',{})
                for key,label in [('workload','Workload'),('efficiency','Efficiency'),('team_expectation','Team points')]:
                    v=comp.get(key,{})
                    if v.get('basis'):body+='<br><small><b>'+text(label)+': '+text(v.get('label','unknown'))+'.</b> '+text(v['basis'])+'</small>'
                condition=p.get('availability') or {}
                if condition.get('status'):body+='<br><small>Availability: '+text(condition['status'])+'.</small>'
                for ev in p.get('role_evidence',[])[:2]:
                    if isinstance(ev,dict) and ev.get('text'):
                        src=ev.get('source') or {};url=src.get('url') if isinstance(src,dict) else None
                        body+='<br><small>'+text(ev['text'])+(' '+link(url,'Source') if url else '')+'</small>'
                body+='</article>'
        return body+'</section>'
    except (KeyError,ValueError,TypeError,OSError,StopIteration):return note


def personnel_summary(snapshot,interactive):
    """Point readers to the actual set of covered matchups, never imply full slate coverage."""
    date=snapshot['day'];p=S/'replacements'/('replacement_report_'+date.replace('-','')+'.json')
    if not p.is_file():return ''
    try:
        d=oq.read(p);games={g['id']:g for g in snapshot['games']};items=[]
        if d['schema_version']!='replacement_report/1' or oq.when(d['built_utc'])>oq.utc():return ''
        for eid,v in d['by_event'].items():
            if eid not in games or not any(t.get('absences') and t.get('screen_status') in ('screened','unknown_next_man') for t in v['teams'].values()):continue
            game=games[eid];gt=v['event']
            if (gt['home_team'],gt['away_team'],oq.when(gt['commence_utc']))!=(game['home_team'],game['away_team'],oq.when(game['commence_time'])):continue
            if oq.when(d['built_utc'])>=oq.when(gt['commence_utc']):continue
            for team,t in v['teams'].items():
                c=t.get('replacement_context',{})
                if not t.get('absences') or not c.get('qualifier'):continue
                players=', '.join(x['player'] for x in t.get('candidates',[]) if x.get('player'))
                items.append((eid,team,c['qualifier'],players))
        if not items:return ''
        n=len({x[0] for x in items});body='<section class="section"><span class="eyebrow">Pregame personnel supplement</span><h2>Replacing an absent starter</h2><p>'+str(n)+' of '+str(len(games))+' matchups have a sourced replacement review. For the rest, replacement impact is unreviewed. A substantial workload can be priced into player props while the change in team scoring remains unknown.</p>'
        for eid,team,short,players in items:
            title='<a href="/game/'+text(eid)+'">'+text(team)+'</a>' if interactive else text(team)
            body+='<details><summary>'+title+' · '+text(players)+'</summary><p>'+text(short)+'</p></details>'
        return body+'</section>'
    except (ValueError,KeyError,TypeError,OSError):return ''
