"""Dated field notes, archive and quote checks for expressly reviewed Sunday cards."""
from html import escape
from pathlib import Path
import json
import re
import subprocess
from hashlib import sha256
from sunday_card import S,central
from sunday_view import NAMES,odds
import sunday_quotes as oq
import sunday_week_review as review
import weekly_football

def esc(v):
    return escape(str(v), quote=True)

def present_form(f):
    if not f.get('n'):return 'no scored games'
    return '%d–%d%s through %d games, %.1f scored and %.1f allowed per game' % (f['w'],f['l'],('–%d'%f['t']) if f['t'] else '',f['n'],f['pf_per_game'],f['pa_per_game'])

def game_note(ctx):
    if not ctx:return 'No verified football context for this matchup.'
    return ' · '.join(('%s: %s' % (ctx[side].get('team') or side,present_form(ctx[side]['form']))) for side in ('away','home'))

def enriched(sc):
    from sunday_intake import history_for
    return weekly_football.enrich(sc,games_path=history_for(sc['date'],sc['edition']))

def football_screen(sc):
    f=enriched(sc); out=['<section class="section"><span class="eyebrow">For review · not issued bets</span><h2>What the football numbers suggest</h2>']
    for t in f['warnings']:out.append('<p>'+esc(t)+'</p>')
    if f.get('ranked_potentials',f['shortlist']):
        out+=['<p>Full-game market-favorite comparison. Review any eligible exact contract below, including a plus-money underdog or a single-book prop. An unknown probability is not a reason to remove it from human review.</p><div class="scroll"><table><tr><th>Rank / potential play</th><th>Captured offer</th><th>Market / football / break-even</th></tr>']
        for r in f.get('ranked_potentials',f['shortlist'])[:5]:
            out.append('<tr><td>%d. %s</td><td>%s %s</td><td>%.1f%% / %.1f%% / %.1f%%</td></tr>'%(r['rank'],esc(r['label']),esc(NAMES.get(r['book'],r['book'])),odds(r['price']),r['market_probability']*100,r['model_probability']*100,r['break_even']*100))
        out+=['</table></div><details><summary>How this list was ranked</summary><p>'+esc(f.get('ranked_method','Distinct games ranked by market probability, then football estimate. The review shortlist is separately limited to two per window.'))+'</p></details>']
    else:out+=['<p>No contracts met the provisional screening criteria.</p>']
    out+=['<details><summary>Team form, venue and coverage by game</summary>']
    for w in sc['windows']:
        for g in w['games']:
            ctx=f['by_event'].get(g['event_id'],{})
            out.append('<p><b>'+esc(g['away']['abbr']+'–'+g['home']['abbr'])+'</b> · '+esc(g['kickoff_ct'])+(' · Neutral site: '+esc(g['venue']) if g.get('neutral_site') else '')+'<br>'+esc(game_note(ctx))+'<br><small>'+esc(' '.join(ctx.get('caveats',[])+g.get('missing',[])))+'</small></p>')
    out+=['</details></section>'];return ''.join(out)

def get_release(day):
    week=review.api()
    try:return week.current_card(day)
    except week.Refused as ex:
        if ex.code=='NO_CARD':return None
        raise ValueError('Published card failed verification.') from None

def paths(meta):
    # Re-resolve moving machines through the actual pinned capture digest.
    w=review.api();day=meta['date'];ed=w.resolve_edition(day,meta['capture_sha256'])
    if oq.digest(ed['path'])!=meta['capture_sha256']:raise ValueError('Pinned source changed.')
    base=Path(meta['current_path']).parent
    return base,Path(ed['path']),base/'observations',base/'journal'

def archive(day):
    w=review.api();base=w.PUBLISHED/day/'briefs'
    rows=[]
    if base.is_dir():
        for m in sorted(base.glob('*.json'),reverse=True):
            if not re.fullmatch(r'[0-9TZ-]+-[0-9a-f]{12}\.json',m.name):continue
            data=oq.read(m); pdf=m.with_suffix('.pdf')
            if pdf.is_file() and data.get('date')==day and oq.digest(pdf)==data.get('pdf_sha256'):
                rows.append((m.stem,data,pdf))
    return rows

def check(day):
    cur=get_release(day)
    if not cur or not cur['sunday_card']['calls']:raise ValueError('There are no published selections to check for this date.')
    return oq.check(cur['sunday_card'],root=paths(cur)[2])

def action(url,day,token,lab,extra=''):
    return '<form method="post" action="'+url+'">'+review.hidden('token',token)+review.hidden('date',day)+extra+'<button>'+esc(lab)+'</button></form>'

def card_panel(day,token,obs=None):
    meta=get_release(day)
    if not meta:return ''
    card=meta['sunday_card'];base,cap,obroot,journal=paths(meta)
    out=['<section class="section"><span class="eyebrow">Published record</span><h2>Reviewed card · '+esc(day)+'</h2><p>Issued '+esc(central(card['issued_utc']))+' · exact capture '+esc(central(card['earliest_snapshot']))+'.</p>']
    if meta['card']['review_head_sha256']!=review.api().verify(day)['head_sha256'] or meta['card'].get('annotation_head_sha256')!=review.api().verify_annotations(day)['head_sha256']:
        out+=['<p class="band">Newer review entries have not been published. This is the last published version.</p>']
    if card['calls']:
        if len({c['event_id'] for c in card['calls']})<len(card['calls']):out+=['<p class="band">Shared game: two selections can win or lose on the same sequence. Count that exposure together.</p>']
        valid=(obs or {}).get('selection_fingerprint')==oq.keys(card)[1]
        if not valid:obs=oq.check(card,root=obroot,mode='saved') if obroot.is_dir() else None
        for idx,c in enumerate(card['calls']):
            out+=['<article><b>'+esc(c['label'])+'</b> · '+esc(central(c['kickoff']))+'<br>'+esc(NAMES.get(c['observed_book'],c['observed_book']))+' '+odds(c['observed_price'])+' observed; floor '+odds(c['minimum_price'])+'.<br>'+esc(c['thesis'])+'<br><b>Risk:</b> '+esc(c['counterevidence'])+'<br><b>Only if:</b> '+esc(c['condition'])+'</article>']
            if obs:
                q=obs['quotes'][idx];status=q['status']
                if oq.when(c['kickoff'])<=oq.utc():status='Game started'
                elif (oq.utc()-oq.when(obs['checked_utc'])).total_seconds()>oq.FRESH and 'price' in q:status='Saved observation only'
                out+=['<small>Exact check: '+esc(status)+(' · '+esc(q['sportsbook'])+' '+odds(q['price']) if 'price' in q else '')+' · '+esc(central(obs['checked_utc']))+'</small>']
        out+=[action('/week/check',day,token,'Recheck only these exact prices',review.hidden('cardsha',meta['sunday_card_sha256']))]
    for p in card.get('passes',[]):out+=['<p><b>'+esc(p['window'])+' · pass.</b> '+esc(p['reason'])+'</p>']
    if card.get('unreviewed_windows'):out+=['<p>Unreviewed: '+esc(', '.join(card['unreviewed_windows']))+'.</p>']
    saved=archive(day)
    current_rank=next((p.with_suffix('.ranked.json') for _,r,p in saved if r['card_sha256']==meta['sunday_card_sha256']),None)
    if current_rank and current_rank.is_file():
        out+=['<h3>Five potential bets in the published brief</h3><p>Reviewed calls first, then provisional full-game candidates. Exact prices are from the pinned edition.</p><ol>']
        for q in oq.read(current_rank)['ranked']:
            out+=['<li>'+esc(q['label'])+' · '+esc(NAMES.get(q['book'],q['book']))+' '+odds(q['price'])+' · <b>'+('Formal call' if q['status']=='formal_call' else 'Watchlist only')+'</b></li>']
        out+=['</ol>']
    for key,r,p in saved:out+=['<p><a href="/week/'+day+'/brief/'+key+'">Download issued PDF · '+esc(central(r['generated_utc']))+'</a></p>']
    if journal.is_dir():
        import sunday_notebook as nb
        out+=['<p><a href="/week/'+day+'/scorecard">Compare this edition’s decisions and results</a></p>']
        out+=['<details><summary>My dated notebook</summary>'+nb.controls(card,token,root=journal)+'</details>']
    out+=['</section>'];return ''.join(out)

def evidence(sc,football,card,meta):
    contracts={c['id']:(g,c) for w in sc['windows'] for g in w['games'] for c in g['contracts']}
    fields=('event_id','market','subject','side','point')
    formal={tuple(c[k] for k in fields) for c in card['calls']}
    # Formal reviews may concern a plus-money underdog, own-book-only prop, team or half market.
    # Keep those ahead of the full-game market-favorite screen; never infer missing probabilities.
    ranked=[];used=set();now=oq.utc()
    def add(g,c,book,price,updated,is_formal,risk):
        sig=(c['event_id'],c['market'],c.get('subject',''))
        if sig in used or len(ranked)>=5 or oq.when(g['kickoff_utc'])<=now:return
        used.add(sig)
        ranked.append(dict({k:c[k] for k in fields},rank=len(ranked)+1,label=c['label'],game=g['away']['abbr']+' at '+g['home']['abbr'],kickoff=g['kickoff_utc'],observed_utc=sc['edition']['captured_utc'],provider_updated_utc=updated,book=book,price=price,status='formal_call' if is_formal else 'watchlist_only',volatility='High',risk_tag=risk))
    exact={tuple(c[k] for k in fields):(g,c) for g,c in contracts.values()}
    for b in card['calls']:
        g,c=exact[tuple(b[k] for k in fields)]
        add(g,c,b['observed_book'],b['observed_price'],b['book_updated_utc'],True,'Check conditions')
    for r in football.get('ranked_potentials',football['shortlist']):
        g,c=contracts[r['id']];sig=tuple(c[k] for k in fields)
        add(g,c,r['book'],r['price'],r['provider_updated_utc'],sig in formal,'Lineup unverified')
    e=dict(card_sha256=meta['sunday_card_sha256'],slate_date=sc['date'],headline='Reviewed Sunday card' if formal else 'Reviewed windows · no picks',deck='Selections, passes and unresolved windows from the dated pregame review.',window_note=('Unreviewed: '+', '.join(card['unreviewed_windows'])+'.') if card['unreviewed_windows'] else '',calls=[])
    for b in card['calls']:
        ctx=football['by_event'].get(b['event_id'],{})
        _,contract=exact[tuple(b[k] for k in fields)]
        anns=[a for a in meta.get('card',{}).get('annotations',[]) if a.get('edition',{}).get('sha256')==meta['capture_sha256'] and a['scope'].get('contract_id')==contract['id'] and not a.get('received_after_kickoff')]
        separate=[a for a in anns if a.get('author_kind') in ('claude','codex','human','other') and a.get('author','').strip().lower() not in ('matthew','self','me')]
        dissent=' '.join('Review by %s (%s, %s; %s): %s'%(a['author'],a['author_kind'],a['stance'],central(a['received_utc']),a['text'][:350]) for a in separate[-2:])
        if separate:e.setdefault('_covered',[]).append(contract['id'])
        peer_n=len({q['book'] for q in contract['quotes'] if q['book']!=b['observed_book'] and q.get('fresh')})
        market_note=('Only the offering book quoted this exact contract; independent price probability and EV unknown.' if not peer_n else 'At least one other book quoted this contract; independent win probability and EV are unverified.')
        roles=ctx.get('replacement_context',[])
        roletext=' '.join(x['display'] for x in roles if x.get('display'))
        corr=''
        e['calls'].append(dict({k:b[k] for k in fields},football=b['thesis']+' '+game_note(ctx)+'.',risk=' '.join([b['counterevidence'],b['condition'],roletext,corr,dissent]).strip(),market_note=market_note+' '+(' '.join(football['warnings'][:1])),sources=[('Review source',b['source'])] if b.get('source') else []))
    if card['calls'] and len(set(e.pop('_covered',[])))==len(card['calls']):e['red_team']='Attributed pregame review note for each exact selection.'
    return e,dict(slate_date=sc['date'],capture_sha256=meta['capture_sha256'],ranked_utc=oq.stamp(now),ranked=ranked)

def publish(day):
    w=review.api()
    try:meta=w.publish(day)
    except w.Refused as e:raise ValueError(str(e)[:210]) from None
    meta=w.current_card(day);card=meta['sunday_card'];base,cap,obs,jroot=paths(meta);p=base/'briefs'
    with oq.lock(p):
        sc=w.screen(day,edition=meta['capture_sha256']);f=enriched(sc);e,rank=evidence(sc,f,card,meta)
        # A snapshot of the evidence accompanies each read-only version.
        issue=oq.stamp(oq.utc()); sha=meta['sunday_card_sha256'];obs.mkdir(parents=True,exist_ok=True)
        fp=oq.keys(card)[1];rc=obs/('exact-'+fp+'.json');obs_sha=oq.digest(rc) if rc.is_file() else None
        for key,m,pdf in archive(day):
            if m['card_sha256']==sha and m.get('reviewed_card_sha256')==meta['card_sha256'] and m.get('observation_sha256')==obs_sha:return pdf
        key=issue.replace(':','')+'-'+sha256(oq.packed([sha,meta['card_sha256'],obs_sha])).hexdigest()[:12]
        pdf=p/(key+'.pdf');context=p/(key+'.evidence.json');ranking=p/(key+'.ranked.json')
        oq.atomic(context,e);oq.atomic(ranking,rank)
        gen=[str(S/'pdf_export/generate_brief'),'--card',meta['history_sunday_card_path'],'--snapshot',str(cap),'--observations',str(obs),'--evidence',str(context),'--watchlist',str(ranking),'--output',str(pdf)]
        proc=subprocess.run(gen,capture_output=True,timeout=60)
        if proc.returncode or not pdf.is_file() or not pdf.read_bytes().startswith(b'%PDF-'):raise ValueError('PDF generation failed. The reviewed card remains saved; check the PDF runtime and retry.')
        import sunday_notebook as nb
        j=nb.api(); ledger=j.Journal(str(jroot));now=oq.utc()
        j.import_capture(ledger,str(cap),now)
        # The journal accepts the actual observed price/book, distinct from the user's minimum.
        journal_source=p/(key+'.calls.json')
        oq.atomic(journal_source,dict(decided_utc=card['issued_utc'],calls=[dict(b,price=b['observed_price'],book=b['observed_book']) for b in card['calls']],source_card_sha256=sha))
        ingested=j.import_calls(ledger,str(journal_source),now,late=True)
        if ingested['refused']:raise ValueError('The dated journal could not match the published calls.')
        oq.atomic(p/(key+'.json'),dict(date=day,generated_utc=issue,card_sha256=sha,reviewed_card_sha256=meta['card_sha256'],capture_sha256=meta['capture_sha256'],observation_sha256=obs_sha,pdf_sha256=oq.digest(pdf)))
        return pdf

def preview(day):
    """Export the actual current scouting list without recording a decision or touching the ledger."""
    import tempfile
    w=review.api(); sc=w.screen(day); f=enriched(sc)
    ed=w.resolve_edition(day,sc['edition']['sha256'])
    when=oq.stamp(oq.utc()); out=w.PUBLISHED/day/'scouting'; out.mkdir(parents=True,exist_ok=True)
    games=sum(len(win['games']) for win in sc['windows'])
    card=dict(slate_date=day,issued_utc=when,earliest_snapshot=ed['captured_utc'],snapshot_sha256=ed['sha256'],calls=[],passes=[],unreviewed_windows=[])
    with tempfile.TemporaryDirectory(dir=out) as temp:
        p=Path(temp);cp=p/'preview-card.json';oq.atomic(cp,card)
        meta={'capture_sha256':ed['sha256'],'sunday_card_sha256':oq.digest(cp)}
        e,rank=evidence(sc,f,card,meta)
        e.update(headline='Weekly scouting list',deck=f'{games} matchups · provisional ranks only. This preview does not issue bets or record a pass.',window_note='These rankings are research candidates. Check the dated reviewed card for actual calls, if one has been published.',availability=' '.join(f['warnings']) or 'Check current injuries and exact book offers before deciding.')
        for row in rank['ranked']:row['status']='watchlist_only'
        ep=p/'evidence.json';rp=p/'ranks.json';oq.atomic(ep,e);oq.atomic(rp,rank)
        dest=out/(day+' NFL Scouting.pdf')
        proc=subprocess.run([str(S/'pdf_export/generate_brief'),'--card',str(cp),'--snapshot',str(ed['path']),'--evidence',str(ep),'--watchlist',str(rp),'--output',str(dest)],capture_output=True,timeout=60)
        if proc.returncode or not dest.is_file():raise ValueError('Weekly scouting PDF could not be generated.')
        return dest

def availability(day,*,fetch=False):
    import sunday_availability as src
    api=review.api()
    import sunday_club_news as club
    schedule=api.load_schedule(str(day))
    data=(src.capture if fetch else src.read)(str(day),schedule,api.INPUTS)
    return club.merged(str(day),schedule,api.INPUTS,data)

def save_bulletin(fields):
    import sunday_club_news as club
    from sunday_intake import day_value
    day=str(day_value(fields["date"])); w=review.api()
    club.store(day,w.load_schedule(day),w.INPUTS,fields)
    return day

def bulletin_form(day,token,events):
    import sunday_club_news as club
    options=[]
    for eid,event in events.items():
        if oq.when(event["kickoff_utc"])<=oq.utc():continue
        for team in event["teams"]:
            options.append('<option value="'+esc(eid+'/'+team)+'">'+esc(team+' · '+' at '.join(event["teams"]))+'</option>')
    if not options:return ''
    fields=review.hidden("token",token)+review.hidden("date",day)
    return ('<details><summary>Add a dated club bulletin</summary><p>Use the club or NFL source when a game designation changes. Your note is saved with the time you entered it.</p>'
            '<form method="post" action="/week/club">'+fields+
            '<label>Team and game<select required name="club_team"><option value="">Choose</option>'+''.join(options)+'</select></label>'
            '<label>Player<input name="player" maxlength="90" required></label><label>Position, if known<input name="position" maxlength="20"></label>'
            '<label>Designation in the source<select required name="designation"><option value="">Choose</option>'+''.join('<option>'+esc(v)+'</option>' for v in club.STATUSES)+'</select></label>'
            '<label>Publication date on source<input type="date" required name="published"></label>'
            '<label>Official club or NFL source<input name="source" type="url" required maxlength="1500"></label>'
            '<label>Role or remaining uncertainty<textarea name="role" required maxlength="350"></textarea></label>'
            '<label><input type="checkbox" style="width:auto" name="material" value="yes"> This player’s availability materially affects the matchup.</label>'
            '<button>Save dated bulletin</button></form></details>')

def injuries_panel(day,token):
    a=availability(day);by=a.get('by_event',{});status=a.get('league_status',a['status'])
    labels={'no_week_data':'No report rows for this NFL week yet','stale':'Saved report is stale; refresh before using it','not_captured':'No dated capture yet','ok':'Dated report available'}
    out=['<details><summary>Check reported absences and possible replacements</summary><p><b>'+esc(labels.get(status,status.replace('_',' ')))+'</b> · League feed '+('observed '+esc(central(a['captured_utc'])) if a.get('captured_utc') else 'time unknown')+'. An absence in the news can be newer than this feed. Check the club’s latest injury bulletin and the final inactive list.</p>']
    for e in by.values():
        if not e.get('records'):continue
        out+=['<h3>'+esc(' at '.join(e['teams']))+'</h3>']
        for r in e['records']:
            if r.get("origin")=="operator_bulletin":
                prior=" League feed also listed "+esc(r["previous_feed_status"])+"." if r.get("previous_feed_status") else ""
                out+=['<p><b>'+esc(r["player"]+" · "+r["status"])+'</b> · '+esc(r["team"])+' · Operator-entered club bulletin. '+esc(r["role"])+prior+
                      ' <a href="'+esc(r["source_url"])+'" rel="noreferrer">Official source dated '+esc(r["published"])+'</a> · entered '+esc(central(r["observed_utc"]))+
                      ('. Marked material by the reviewer.' if r["reported_material"] else '.')+'</p>']
                continue
            names=', '.join(x['player']+' ('+str(x['rank'])+')' for x in r.get('candidates',[]) if x.get('player'))
            out+=['<p><b>'+esc(r['player'])+' · '+esc(r['status'])+'</b> · '+esc(r['position'])+', '+esc(r['team'])+'. '+('Listed first on the dated depth chart. ' if r.get('starter_status')=='listed_first' else 'Starter status unverified. ')+('Depth candidates only: '+esc(names)+'.' if names else 'No replacement identified.')+' Workload, efficiency and the effect on team prices require separate evidence.</p>']
    out+=['<p class="small">'+esc(' '.join(a.get('limitations',[])))+'</p>',action('/week/availability',str(day),token,'Check public injury data · no Odds API credits'),bulletin_form(day,token,by),'</details>']
    return ''.join(out)
