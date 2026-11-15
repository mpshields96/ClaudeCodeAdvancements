"""Front door for other Sundays; engine and write-once review supplied by weekly/."""
from datetime import timedelta
from html import escape as h
from pathlib import Path
from sunday_card import S,central,CT
from sunday_view import html_page,form,odds
from sunday_intake import ROOT,day_value
import sunday_quotes as oq
def chooser(token):
    day=oq.utc().astimezone(CT).date(); next_sunday=day+timedelta(days=(6-day.weekday())%7)
    if str(next_sunday)<"2026-11-22":next_sunday=day_value("2026-11-22")
    body='<a href="/">← November 15 card</a><header><span class="eyebrow">NFL Field Notes</span><h1>Choose a Sunday</h1><p>Start with its own schedule and prices. A new date starts with no reviewed calls.</p></header><section class="section"><h2>Saved Sundays</h2><ul><li><a href="/">November 15 · released card and experiment</a></li>'
    if ROOT.is_dir():
        for p in sorted(ROOT.iterdir()):
            if p.is_dir() and (p/"schedule.json").is_file() and (p/"odds.json").is_file():
                try:day_value(p.name)
                except ValueError:continue
                body+=f'<li><a href="/week/{h(p.name)}">{h(p.name)} · open this edition</a></li>'
    body+=f'</ul></section><section class="section"><h2>Prepare a different Sunday</h2><p>This retrieves a public schedule and the free main markets (moneyline, spread and game total). Up to three free credits for a new date; reopening a saved date costs zero. Missing props and partial books are labeled.</p><form method="post" action="/week/acquire"><input type="hidden" name="token" value="{h(token)}"><label>Sunday date<input required type="date" name="date" min="2026-11-22" value="{next_sunday}"></label><button>Open dated slate</button></form></section>'
    return html_page("Choose a Sunday",body)
def base_page(day,token,notice=""):
    day=day_value(day);folder=ROOT/str(day)
    if not (folder/"odds.json").is_file():return chooser(token)
    sched=oq.read(folder/"schedule.json");od=oq.read(folder/"odds.json")
    expected=[e for e in sched["events"] if oq.when(e["date"]).astimezone(CT).date()==day]
    body=f'<a href="/weeks">← All Sundays</a><header><span class="eyebrow">NFL Field Notes · dated edition</span><h1>Sunday, {h(day.strftime("%B %-d"))}</h1><p>Reference slate captured {h(central(od["captured_utc"]))}. {len(expected)} games on the independent schedule; {len(od["games"])} events returned by the price feed.</p></header>'
    if od.get("team_history_warning"):body+='<p class="band">'+h(od["team_history_warning"])+'</p>'
    if notice:body+=f'<p class="band">{h(notice)}</p>'
    return folder,od,body
def page(day,token,notice="",observation=None):
    import sunday_week_review
    v=base_page(day,token,notice)
    if isinstance(v,str):return v
    folder,od,body=v
    ready=sunday_week_review.render(day,token,observation)
    if ready is not None:return html_page(str(day)+" NFL slate",body+ready)
    body+='<p class="band">Dated intake · no released calls. The November 15 selections and limits do not apply.</p>'
    body+='<section class="section"><h2>Saved games</h2><div class="scroll"><table><tr><th>Kickoff</th><th>Matchup</th><th>Books quoted</th></tr>'
    for g in sorted(od["games"],key=lambda x:x["commence_time"]):
        body+=f'<tr><td>{h(central(g["commence_time"]))}</td><td>{h(g["away_team"])} at {h(g["home_team"])}</td><td>{len(g["bookmakers"])}</td></tr>'
    body+='</table></div><p class="small">Player props, first-half lines and team totals were not requested by this main-markets capture. No probability or football rationale is inferred from a missing market.</p></section>'
    return html_page(str(day)+" NFL slate",body)
