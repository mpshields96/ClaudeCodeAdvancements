"""Extract named inactives from the NFL's archived 2026 Weeks 1–9 HTML reports."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen


ROOT = "https://www.nfl.com/news/"
PAGES = {
    1: ROOT+"inactive-reports-sunday-week-1-2026-nfl-season",
    2: ROOT+"nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026",
    3: ROOT+"nfl-week-3-inactives-players-ruled-out-sunday-14-games-2026",
    4: ROOT+"nfl-week-4-inactives-players-ruled-out-sunday-14-games-2026",
    **{k: ROOT+"nfl-week-%d-inactives-players-ruled-out-sunday-2026-season" % k for k in range(5,10)}
}
OUTPUT = Path(__file__).with_name("official_appearance_sources_20261115.json")
CLUB_REPORTS = [
    (1,"seahawks","Tory Horton","https://www.seahawks.com/news/nick-emmanwori-tory-horton-inactive-for-seahawks-opener-vs-patriots"),
    (1,"49ers","Jordan Watkins","https://www.49ers.com/news/tatum-bethune-jordan-watkins-out-vs-rams-inactives-for-week-1-sfvslar"),
    (1,"rams","Tutu Atwell","https://www.therams.com/news/ty-simpson-tutu-atwell-and-cj-daniels-among-rams-inactives-for-week-1-vs-49ers-in-australia-2026"),
    (4,"saints","Noah Fant","https://www.neworleanssaints.com/news/new-orleans-saints-inactives-atlanta-falcons-2026-nfl-week-4-gameday"),
    (7,"falcons","Olamide Zaccheaus","https://www.atlantafalcons.com/news/atlanta-falcons-week-7-inactives-vs-san-francisco-49ers"),
    (8,"packers","Kaleb Johnson","https://www.packers.com/news/packers-panthers-week-8-inactives-oct-29-2026"),
]


def load(item):
    week, url = item
    with urlopen(Request(url,headers={"User-Agent":"nfl-slate-data-paper-research/1.0"}),timeout=12) as r:
        body = r.read()
    obs = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    assert obs < "2026-11-15T14:30:00Z"
    html = body.decode()
    teams = {}
    for tag,lis in re.findall(r"<h3[^>]*>([^<]{2,30})</h3>\s*<ul[^>]*>(.*?)</ul>", html, re.S):
        names = []
        for li in re.findall(r"<li[^>]*>(.*?)</li>", lis, re.S):
            v=unescape(re.sub(r"<[^>]*>","",li))
            v=re.sub(r"\s*\(.*?\)","",v).strip()
            if " " in v:
                names.append(v.split(" ",1)[1].strip())
        if names:
            teams[tag.strip().lower()] = names
    if not teams:
        raise ValueError("Archived inactive table missing: "+url)
    return str(week), {"source_url":url, "retrieved_utc":obs,"sha256":sha256(body).hexdigest(),"teams":teams}


if __name__ == "__main__":
    previous=json.loads(OUTPUT.read_bytes()) if OUTPUT.exists() else {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows={str(week):previous[str(week)] for week in PAGES if str(week) in previous}
        rows.update(pool.map(load,[(w,u) for w,u in PAGES.items() if str(w) not in rows]))
    articles=[]
    for week,club,name,url in CLUB_REPORTS:
        with urlopen(Request(url,headers={"User-Agent":"nfl-slate-data-paper-research/1.0"}),timeout=12) as response:
            body=response.read()
        assert name.lower() in unescape(re.sub(r"<[^>]+>","",body.decode())).lower()
        articles.append({"week":week,"club":club,"player":name,"source_url":url,
                         "retrieved_utc":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
                         "sha256":sha256(body).hexdigest()})
    rows["club_inactives"]=articles
    tmp=OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows,indent=1)+"\n")
    tmp.replace(OUTPUT)
