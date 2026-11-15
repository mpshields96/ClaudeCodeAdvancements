"""Capture official public roster and completed player-game HTML for the 2026-11-15 slate."""
import os
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.parse import urljoin
import unicodedata


BASE = "https://www.nfl.com"
CUTOFF = "2026-11-15"
HERE = Path(__file__).resolve().parent
ODDS = Path(os.path.expanduser("~/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json"))
DEFAULT = HERE / "official_player_logs_20261115.json"
SUFFIX = re.compile(r"\s+(?:jr|sr|ii|iii|iv|v)\.?$", re.I)
ALIASES = {"Zonovan Knight": "Bam Knight"}
ALIAS_SOURCE = "https://www.azcardinals.com/news/zonovan-knight-having-a-bam-good-time-in-cardinals-backfield"
DANIELS_REPORT = "https://www.therams.com/news/really-encouraged-by-his-development-rams-coaches-and-teammates-looking-forward-to-cj-daniels-jr-getting-more-opportunities-in-week-10"
ROLE_SOURCES = {
    "MIA": ("Kyle McCord", "Miami identifies McCord as its first-time starter with Malik Willis injured.",
            "https://www.miamidolphins.com/news/top-quotes-dolphins-travel-to-indianapolis-with-a-new-quarterback-new-captain"),
    "ARI": ("Carson Beck", "Arizona identifies Beck as its first-time starter after Gardner Minshew's season-ending injury.",
            "https://www.azcardinals.com/news/for-starters-carson-beck-ready-to-play-first-game-against-rams"),
    "LV": ("Fernando Mendoza", "Las Vegas named Mendoza the starter after trading Kirk Cousins. His prior NFL passing came in relief.",
           "https://www.raiders.com/news/fernando-mendoza-named-raiders-starting-quarterback"),
    "MIN": ("Kirk Cousins", "Minnesota named newly acquired Cousins the starter. His 2026 game rows through Week 9 came with Las Vegas.",
            "https://www.vikings.com/news/kirk-cousins-starting-packers-week-10-game-2026"),
    "SEA": ("Drew Lock", "Seattle prepared Lock for a second straight start with Sam Darnold ruled out. Lock was limited by oblique and elbow injuries.",
            "https://www.seahawks.com/news/drew-lock-confident-and-optimistic-heading-into-sunday-s-game-other-seahawks-updates"),
    "CLE": ("Deshaun Watson", "Cleveland says Watson returns after Shedeur Sanders started Week 9. Watson had cleared concussion protocol.",
            "https://www.clevelandbrowns.com/news/deshaun-watson-set-to-start-week-10-against-the-texans"),
}


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def norm(name):
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", SUFFIX.sub("", value))


def cell_text(cell):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", cell)).split())


def cells(row):
    return [cell_text(cell) for cell in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", row, re.S | re.I)]


def capture(url):
    is_stats = re.fullmatch(r"https://www\.nfl\.com/(teams/[a-z0-9-]+/roster|players/[a-z0-9-]+/stats/(?:logs/2026/|career))", url)
    is_box = re.fullmatch(r"https://www\.jaguars\.com/game-day/2026/reg-week[1-9]/[a-z0-9-]+/box-score", url)
    if not (is_stats or is_box or url in {ALIAS_SOURCE,DANIELS_REPORT} or url in {r[2] for r in ROLE_SOURCES.values()}):
        raise ValueError("Unexpected public HTML URL")
    req = Request(url, headers={"User-Agent": "nfl-slate-data-paper-research/1.0", "Accept": "text/html"})
    source = {"source_url": url}
    try:
        with urlopen(req, timeout=15) as response:
            if response.headers.get_content_type() != "text/html":
                raise ValueError("Expected an HTML page")
            body = response.read()
            source.update(retrieved_utc=stamp(), http_status=response.status,
                          final_url=response.geturl(), sha256=sha256(body).hexdigest())
            return source, body.decode("utf-8")
    except Exception as exc:
        source.update(retrieved_utc=stamp(), http_status=getattr(exc, "code", None), error=str(exc))
        return source, ""


def roster(team):
    url = BASE + "/teams/" + team.lower().replace(" ", "-") + "/roster"
    source, html = capture(url)
    players = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, re.S):
        link = re.search(r'href="(/players/[a-z0-9-]+/)"[^>]*>([^<]+)</a>', row)
        columns = cells(row)
        if link and len(columns) >= 4:
            players.append({"name": cell_text(link[2]), "player_path": link[1],
                            "position": columns[2], "roster_status": columns[3], "team_name": team})
    return team, {"source": source, "players": players}


def player_log(entry):
    url = urljoin(BASE, entry["player_path"]) + "stats/logs/2026/"
    source, html = capture(url)
    out = {"source": source, "official_name": entry["name"], "games": [], "headers": []}
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    if not title or not cell_text(title[1]).endswith(" 2026 Logs Stats | NFL.com"):
        out["error"] = "Player-specific 2026 game log missing"
        return url, out
    profile_name = cell_text(title[1]).split(" 2026 Logs Stats | NFL.com")[0]
    if norm(profile_name) != norm(entry["name"]):
        out["error"] = "Roster and log name disagree"
        return url, out
    match = re.search(r">Regular Season</h3>.*?<table\b[^>]*>(.*?)</table>", html, re.S | re.I)
    if not match:
        out["error"] = "Regular-season table missing"
        return url, out
    rows = [cells(r) for r in re.findall(r"<tr\b[^>]*>(.*?)</tr>", match[1], re.S)]
    headers = rows[0]
    if headers[:4] != ["WK", "Game Date", "OPP", "RESULT"]:
        out["error"] = "Unrecognized game log columns"
        return url, out
    out["headers"] = headers[4:]
    for row in rows[1:]:
        if len(row) != len(headers) or not row[0].isdigit() or not re.fullmatch(r"[WLT]\s+\d+\s*-\s*\d+", row[3]):
            continue
        date = datetime.strptime(row[1], "%m/%d/%Y").date().isoformat()
        if date >= CUTOFF or not date.startswith("2026-"):
            continue
        out["games"].append({"date": date, "week": int(row[0]), "opponent": row[2], "result": row[3],
                             "values": [v or None for v in row[4:]]})
    out["games"].sort(key=lambda x: x["date"], reverse=True)
    if len({g["date"] for g in out["games"]}) != len(out["games"]):
        raise ValueError("Duplicate official game-log date")
    return url, out


def season_total(entry):
    url = urljoin(BASE, entry["player_path"]) + "stats/career"
    source, html = capture(url)
    out = {"source": source, "official_name": entry["name"], "categories": {}}
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    if not title or norm(entry["name"]) not in norm(cell_text(title[1])):
        out["error"] = "Official player page identity unavailable"
        return url, out
    for tbl in re.findall(r"<table\b[^>]*>(.*?)</table>", html, re.S):
        rows = [cells(r) for r in re.findall(r"<tr\b[^>]*>(.*?)</tr>", tbl, re.S)]
        if not rows or rows[0][:3] != ["YEAR", "TEAM", "G"]:
            continue
        columns = rows[0]
        if columns[3:6] == ["ATT", "COMP", "PCT"]:
            market, volume = "player_pass_yds", "ATT"
        elif columns[3:5] == ["ATT", "YDS"]:
            market, volume = "player_rush_yds", "ATT"
        elif columns[3:5] == ["REC", "YDS"]:
            market, volume = "player_reception_yds", "REC"
        else:
            continue
        checked = []
        for values in rows[1:]:
            if len(values) == len(columns) and values[0] == "2026":
                row = dict(zip(columns, values))
                checked.append({"team_name": row["TEAM"], "games_played": int(row["G"]) if row["G"] else None,
                                "yards": int(row["YDS"].replace(",", "")) if row["YDS"] else None,
                                "volume": int(row[volume]) if row[volume] else None})
        if checked:
            out["categories"][market] = checked
    return url, out


def team_role(item):
    code, (player, message, url) = item
    source, html = capture(url)
    if player.lower() not in cell_text(html).lower():
        raise ValueError("Team role source missing player " + player)
    dates = re.findall(r'<time\b[^>]*datetime="([^"]+)"', html)
    return code, {"expected_starter": player, "context": message, "published": dates[0] if dates else None, **source}


def hunter_receiving(game):
    opp = game["opponent"].lstrip("@").lower()
    teams = ["jaguars", opp] if game["opponent"].startswith("@") else [opp, "jaguars"]
    url = "https://www.jaguars.com/game-day/2026/reg-week%d/%s/box-score" % (game["week"], "-at-".join(teams))
    source, html = capture(url)
    line = {"date": game["date"], "receptions": None, "yards": None, "basis": "unreported", **source}
    completions = None
    for table in re.findall(r"<table\b[^>]*>(.*?)</table>", html, re.S):
        raw = [r for r in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S) if cell_text(r)]
        rows = [cells(r) for r in raw]
        if not rows:
            continue
        if rows[0][1:2] == ["CP/ATT"] and "/team/players-roster/trevor-lawrence/" in table:
            completions = sum(int(r[1].split("/")[0]) for r in rows[1:])
        if rows[0][:3] != ["Player", "REC", "YDS"] or "/team/players-roster/" not in table:
            continue
        # Game center links home-club players, but use a known Jacksonville receiver to identify the team table independently.
        if not any(n in table for n in ["/team/players-roster/parker-washington/", "/team/players-roster/brenton-strange/"]):
            continue
        for r, raw_row in zip(rows[1:], raw[1:]):
            if "/team/players-roster/travis-hunter/" in raw_row:
                line.update(receptions=int(r[1]), yards=int(r[2]), basis="Official receiving box-score row.")
                break
        if line["yards"] is None and completions == sum(int(r[1]) for r in rows[1:]) and game["values"][0] is not None:
            line.update(receptions=0, yards=0,
                        basis="Derived zero: Hunter has defensive participation and the team receiving rows account for all completions.")
        return game["date"], line
    return game["date"], line


def run(output, previous=None):
    if stamp() >= "2026-11-15T14:30:00Z":
        raise SystemExit("The first kickoff has passed. Use the saved pregame capture.")
    odds = json.loads(ODDS.read_bytes())
    old = json.loads(previous.read_bytes()) if previous else {}
    teams = sorted({g[k] for g in odds["event_odds"] for k in ("home_team", "away_team")})
    rosters = dict(old.get("rosters", {}))
    logs = dict(old.get("logs", {}))
    totals = dict(old.get("season_totals", {}))
    with ThreadPoolExecutor(max_workers=3) as pool:
        rosters.update(pool.map(roster, [t for t in teams if t not in rosters]))
        players = {}
        for g in odds["event_odds"]:
            names = {o["description"] for b in g["bookmakers"] for m in b["markets"]
                     if m["key"].startswith("player_") for o in m["outcomes"]}
            pool_members = rosters[g["home_team"]]["players"] + rosters[g["away_team"]]["players"]
            for name in sorted(names):
                ident = ALIASES.get(name, name)
                matches = [p for p in pool_members if norm(p["name"]) == norm(ident)]
                if len(matches) == 1:
                    entry = matches[0].copy()
                    entry["log_url"] = urljoin(BASE, entry["player_path"]) + "stats/logs/2026/"
                    if name in ALIASES:
                        entry["name_alias_source_url"] = ALIAS_SOURCE
                    players[name] = entry
                else:
                    players[name] = {"error": "No unique NFL.com roster match", "matches": matches}
        needed = {p["log_url"]: p for p in players.values() if "log_url" in p and p["log_url"] not in logs}
        logs.update(pool.map(player_log, needed.values()))
        needed_totals = {urljoin(BASE, p["player_path"]) + "stats/career": p for p in players.values() if "player_path" in p}
        totals.update(pool.map(season_total, [p for url, p in needed_totals.items() if url not in totals]))
        roles = old.get("quarterback_context_by_team") or dict(pool.map(team_role, ROLE_SOURCES.items()))
        hunter_games = logs[players["Travis Hunter"]["log_url"]]["games"]
        hunter = old.get("hunter_receiving") or dict(pool.map(hunter_receiving, hunter_games))
        alias_source = old.get("alias_source") or capture(ALIAS_SOURCE)[0]
        no_stats=old.get("confirmed_no_stats_by_player",{})
        if "CJ Daniels" not in no_stats:
            source,html=capture(DANIELS_REPORT)
            if "six offensive snaps and did not record any stats" not in cell_text(html):
                raise ValueError("Daniels usage report could not be verified")
            no_stats["CJ Daniels"]={**source,"basis":"Rams report no stats and six offensive snaps over Weeks 7 through 9, after six games inactive."}
    doc = {"captured_utc": stamp(), "cutoff_exclusive": CUTOFF, "rosters": rosters, "players": players,
           "logs": logs, "season_totals": totals, "quarterback_context_by_team": roles,
           "hunter_receiving": hunter, "alias_source": alias_source, "confirmed_no_stats_by_player":no_stats}
    tmp = output.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, separators=(",", ":"), allow_nan=False) + "\n")
    tmp.replace(output)
    print(len(teams), "teams;", len(players), "posted names;", len(logs), "official player logs")
    print("Unmatched:", [name for name, p in players.items() if "error" in p])
    print("Log issues:", [(p["official_name"], p.get("error", "zero final rows")) for p in logs.values() if not p["games"]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--reuse", type=Path)
    args = parser.parse_args()
    run(args.output, args.reuse)
