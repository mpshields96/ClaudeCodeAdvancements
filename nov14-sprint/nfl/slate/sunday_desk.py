"""Sunday's reviewed NFL card, served only on this Mac. No unattended feed calls."""
import argparse
from hashlib import sha256
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import os
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs,urlsplit
import webbrowser
sys.path.insert(0,str(Path(__file__).resolve().parent))
import sunday_quotes as oq
from sunday_card import S,L,released,full_snapshot
from sunday_view import h,html_page,view
import sunday_notebook as notebook
import sunday_markets
import sunday_scoreboard
import sunday_week_ui
import sunday_intake
import sunday_week_review
import sunday_week_release as week_release

REPORTS={
    "selection":("Football review and ranked slate",S.parent/"BEST_BETS_SUN_NOV15.html"),
    "dissent":("Independent football dissent",S/"FOOTBALL_RED_TEAM.md"),
    "evidence":("The case for and against the finalists",L/"Matchup_Review.md"),
    "benchmark":("Past-only test versus the market",S/"PAST_ONLY_TEST.md"),
    "prop":("Role and workload review",S/"PROP_REVIEW.md"),
    "redteam":("Independent release review",S.parent.parent/"advisor/NFL_REVIEW.md"),
}
def reports():return [(n,"/evidence/"+k) for k,(n,p) in REPORTS.items() if p.is_file()]
def snapshot(path):
    c,s=released(); o=oq.check(c,mode="saved")
    content=view(c,s,o,controls=notebook.summary(c))
    tmp=path.with_suffix(".html.tmp"); tmp.write_text(content);os.replace(tmp,path)
def generate_pdf():
    gen=S/"pdf_export/generate_brief"; pdf=L/"Sunday NFL Brief.pdf"
    if not gen.is_file():raise ValueError("PDF generator is not ready.")
    with oq.lock(S/"results/pdf-export"):
        proc=subprocess.run([str(gen),"--card",str(L/"Sunday_Card.json"),"--output",str(pdf),"--snapshot",str(L/"sunday-odds.json"),"--observations",str(L/"observations")],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
        if proc.returncode or not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF-"):raise ValueError("PDF could not be generated. The card is still available.")
        return pdf.read_bytes()
class Desk:
    def __init__(self,mode,weekly=False):
        self.c=self.s=self.obs=None
        if not weekly:self.c,self.s=released();self.obs=oq.check(self.c,mode=mode)
        self.week_obs={};self.token=secrets.token_urlsafe(30);self.slate=None;self.updated=time.monotonic();self.guard=threading.RLock()
    def historic(self):
        if self.c is None:self.c,self.s=released();self.obs=oq.check(self.c,mode="saved")
    def render(self,notice=""):
        self.historic()
        return view(self.c,self.s,self.obs,token=self.token,notice=notice,state=notebook.current_views(self.c),controls=notebook.controls(self.c,self.token),reports=reports(),price_slate=self.slate)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,body,*,status=200,mime="text/html; charset=utf-8",attach=None):
        if isinstance(body,str):body=body.encode()
        self.send_response(status);self.send_header("Content-Type",mime);self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.send_header("Referrer-Policy","same-origin")
        self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; img-src data:")
        if attach:self.send_header("Content-Disposition",'attachment; filename="'+attach+'"')
        self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
    def score_flash(self,day):
        ident,msg=getattr(self.server,"score_flash",(None,""))
        if ident==day:self.server.score_flash=(None,"");return msg
        return ""
    def valid_host(self):
        if self.headers.get("Host")!=self.server.host:
            self.reply("Local access only.",status=403);return False
        return True
    def do_GET(self):
        if not self.valid_host():return
        path=urlsplit(self.path).path; desk=self.server.desk; desk.updated=time.monotonic()
        if path=="/weeks":self.reply(sunday_week_ui.chooser(desk.token));return
        if path.startswith("/week/"):
            try:
                bits=path.split("/");day=str(sunday_intake.day_value(bits[2]))
                if len(bits)==5 and bits[3]=="brief":
                    entry=next((p for k,_,p in week_release.archive(day) if k==bits[4]),None)
                    if not entry:raise ValueError("Unknown dated brief.")
                    self.reply(entry.read_bytes(),mime="application/pdf",attach=day+"-NFL-Brief.pdf")
                elif len(bits)==4 and bits[3]=="scorecard":
                    cur=week_release.get_release(day)
                    if not cur:raise ValueError("No published edition.")
                    self.reply(sunday_scoreboard.scoreboard(cur['sunday_card'],desk.token,self.score_flash(day),root=week_release.paths(cur)[3]))
                elif len(bits)==3:self.reply(sunday_week_ui.page(day,desk.token,observation=desk.week_obs.get(day)))
                else:raise ValueError("Unknown dated page.")
            except (ValueError,TypeError,KeyError,OSError):self.reply("Date unavailable or unverified.",status=404)
            return
        if path=="/scorecard":
            try:
                desk.historic();self.reply(sunday_scoreboard.scoreboard(desk.c,desk.token,self.score_flash("2026-11-15")))
            except (ValueError,TypeError,KeyError,OSError):self.reply("Journal evidence cannot be verified.",status=503)
            return
        if path=="/":
            try:self.reply(desk.render())
            except (ValueError,KeyError,OSError,TypeError):self.reply("The card cannot be verified; no actionable calls.",status=503)
            return
        if path.startswith("/game/"):
            try:
                desk.historic();self.reply(sunday_markets.page(desk.slate or desk.s,path.split("/")[-1]))
            except (ValueError,KeyError):self.reply("Unknown game or invalid capture.",status=404)
            return
        if path.startswith("/evidence/"):
            itm=REPORTS.get(path.split("/")[-1])
            if itm and itm[1].is_file():
                title,p=itm
                if p.suffix==".html":self.reply(p.read_bytes());return
                self.reply(html_page(title,'<a href="/">← Sunday card</a><h1>'+h(title)+'</h1><div class="record">'+h(p.read_text())+'</div>'));return
        self.reply("Not found.",status=404)
    def do_POST(self):
        if not self.valid_host():return
        desk=self.server.desk;desk.updated=time.monotonic()
        origin=self.headers.get("Origin")
        if origin and origin!="http://"+self.server.host and not (origin=="null" and self.headers.get("Sec-Fetch-Site")=="same-origin"):self.reply("Local request required.",status=403);return
        try:length=int(self.headers["Content-Length"])
        except (ValueError,TypeError):length=0
        if not 0<length<=12000 or not self.headers.get("Content-Type","").startswith("application/x-www-form-urlencoded"):
            self.reply("Invalid form.",status=400);return
        try:fields={k:v[0] for k,v in parse_qs(self.rfile.read(length).decode(),max_num_fields=30).items() if len(v)==1}
        except ValueError:self.reply("Invalid form.",status=400);return
        if not secrets.compare_digest(fields.pop("token",""),desk.token):
            self.reply("Reopen your local card.",status=403);return
        path=urlsplit(self.path).path
        with desk.guard:
            try:
                if path in ("/week/review","/week/annotate"):
                    date=(sunday_week_review.submit if path=="/week/review" else sunday_week_review.annotate)(fields);self.send_response(303);self.send_header("Location","/week/"+date);self.end_headers();return
                if path=="/week/club":
                    day=week_release.save_bulletin(fields)
                    self.send_response(303);self.send_header("Location","/week/"+day);self.end_headers();return
                if path=="/week/availability":
                    day=str(sunday_intake.day_value(fields.get("date","")));week_release.availability(day,fetch=True)
                    self.send_response(303);self.send_header("Location","/week/"+day);self.end_headers();return
                if path=="/week/preview":
                    day=str(sunday_intake.day_value(fields.get("date","")));pdf=week_release.preview(day)
                    self.reply(pdf.read_bytes(),mime="application/pdf",attach=day+"-NFL-Scouting.pdf");return
                if path=="/week/publish":
                    date=str(sunday_intake.day_value(fields.get("date","")));pdf=week_release.publish(date)
                    self.reply(pdf.read_bytes(),mime="application/pdf",attach=date+"-NFL-Brief.pdf");return
                if path=="/week/check":
                    date=str(sunday_intake.day_value(fields.get("date","")));cur=week_release.get_release(date)
                    if not cur or cur["sunday_card_sha256"]!=fields.get("cardsha"):raise ValueError("The reviewed card changed. Reopen it before checking prices.")
                    desk.week_obs[date]=week_release.check(date)
                    self.send_response(303);self.send_header("Location","/week/"+date);self.end_headers();return
                if path in ("/week/reacquire","/week/details"):
                    folder,_,_=sunday_intake.acquire(fields.get("date",""),fresh=True,detailed=path=="/week/details",include_history=True)
                    self.send_response(303);self.send_header("Location","/week/"+folder.name);self.end_headers();return
                if path=="/week/acquire":
                    folder,_,_=sunday_intake.acquire(fields.get("date",""),include_history=True)
                    self.send_response(303);self.send_header("Location","/week/"+folder.name);self.end_headers();return
                if path in ("/postgame/import","/ticket/settle"):
                    day=fields.get("date","2026-11-15")
                    if day=="2026-11-15":
                        desk.historic();c=desk.c;root=None
                    else:
                        day=str(sunday_intake.day_value(day));cur=week_release.get_release(day)
                        if not cur:raise ValueError("No published edition.")
                        c=cur['sunday_card'];root=week_release.paths(cur)[3]
                    msg=sunday_scoreboard.import_public(c,root) if path=="/postgame/import" else sunday_scoreboard.report_settlement(fields,root)
                    self.server.score_flash=(day,msg)
                    self.send_response(303);self.send_header("Location","/scorecard" if day=="2026-11-15" else "/week/"+day+"/scorecard");self.end_headers();return
                if path in ("/opinion","/ticket") and fields.get("date"):
                    day=str(sunday_intake.day_value(fields["date"]));cur=week_release.get_release(day)
                    if not cur:raise ValueError("No published edition.")
                    notebook.submit(path,fields,cur['sunday_card'],root=week_release.paths(cur)[3])
                    self.send_response(303);self.send_header("Location","/week/"+day+"/scorecard");self.end_headers();return
                desk.historic()
                if path=="/pdf":
                    self.reply(generate_pdf(),mime="application/pdf",attach="Sunday-NFL-Brief.pdf");return
                if path=="/refresh":
                    desk.obs=oq.check(desk.c);msg="Exact contract check complete. See each price and lineup condition below."
                elif path=="/slate":
                    desk.slate,src,cost=full_snapshot(L/"observations");msg=f"Detailed slate: {src}; {cost} free credits used. Browse games and coverage below."
                elif path in ("/opinion","/ticket"):
                    msg=notebook.submit(path,fields,desk.c)
                else:self.reply("Not found.",status=404);return
                # POST/redirect/GET protects the notebook from browser refresh replay.
                self.server.flash=msg;self.send_response(303);self.send_header("Location","/result"+("#experiment" if path in ("/opinion","/ticket") else ""));self.send_header("Content-Length","0");self.end_headers()
            except (ValueError,KeyError,OSError,RuntimeError,subprocess.SubprocessError) as exc:
                safe=str(exc) if type(exc) is ValueError and len(str(exc))<=220 and "http" not in str(exc) else "Could not complete this action. No confirmation was recorded."
                if path.startswith("/week/"):
                    self.reply(html_page("Dated review",'<p class="band">'+h(safe)+'</p><a href="/weeks">Return to saved Sundays</a>'),status=422)
                else:self.reply(desk.render(safe),status=422)
class DeskHandler(Handler):
    def do_GET(self):
        if urlsplit(self.path).path=="/result":
            if not self.valid_host():return
            self.reply(self.server.desk.render(getattr(self.server,"flash","")));return
        super().do_GET()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--saved",action="store_true",help="open offline with the last observation")
    ap.add_argument("--date",help="Open a different Sunday without rechecking the November 15 card");ap.add_argument("--no-browser",action="store_true",help="print local URL without opening a tab");ap.add_argument("--snapshot",type=Path,help="write a read-only HTML card without fetching")
    ap.add_argument("--check",action="store_true",help="one normal exact check, print JSON and exit");ap.add_argument("--port",type=int,default=0)
    args=ap.parse_args()
    if args.snapshot:snapshot(args.snapshot);print(args.snapshot);return 0
    explicit=args.date or str(oq.utc().astimezone(sunday_intake.CENTRAL).date())
    is_weekly=explicit!="2026-11-15" and not args.check
    if args.date and is_weekly:sunday_intake.day_value(args.date)
    d=Desk("saved" if args.saved else "normal",weekly=is_weekly)
    if args.check:print(oq.json.dumps(d.obs,indent=2));return 0
    http=ThreadingHTTPServer(("127.0.0.1",args.port),DeskHandler);http.timeout=5;http.desk=d;http.host="127.0.0.1:"+str(http.server_port)
    start=("/week/"+args.date if args.date else "/weeks") if is_weekly else "/"
    url="http://"+http.host+start;print("Sunday NFL card: "+url,flush=True)
    print("No background price requests. Close this Terminal or press Control-C to stop.",flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:
        while time.monotonic()-d.updated<1500:http.handle_request()
    except KeyboardInterrupt:pass
    finally:http.server_close()
    return 0
if __name__=="__main__":
    try:sys.exit(main())
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print("Card unavailable: frozen decisions, observations, or the matching engine output could not be validated ("+type(exc).__name__+"). No actionable quote shown.",file=sys.stderr);sys.exit(2)
