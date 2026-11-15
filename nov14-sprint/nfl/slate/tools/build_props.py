"""Build the November 15 player prop input offline from the captured public evidence."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
import unicodedata


HERE = Path(__file__).resolve().parent
SLATE = HERE.parent
INPUTS = SLATE / "inputs"
FORM = HERE / "official_player_logs_20261115.json"
ODDS = Path("/Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json")
MARKETS = {"player_reception_yds", "player_pass_yds", "player_rush_yds"}
INACTIVE = {"Out", "Injured Reserve", "Reserve/Injured", "Suspended", "Physically Unable to Perform"}
PENDING = {"Questionable", "Doubtful"}
FIRST_KICKOFF = "2026-11-15T14:30:00Z"
CLUBS = dict(zip(
    "49ers Bears Bengals Bills Broncos Browns Buccaneers Cardinals Chargers Chiefs Colts Commanders Cowboys Dolphins Eagles Falcons Giants Jaguars Jets Lions Packers Panthers Patriots Raiders Rams Ravens Saints Seahawks Steelers Texans Titans Vikings".split(),
    "SF CHI CIN BUF DEN CLE TB ARI LAC KC IND WAS DAL MIA PHI ATL NYG JAX NYJ DET GB CAR NE LV LAR BAL NO SEA PIT HOU TEN MIN".split()))


def norm(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = re.sub(r"\s+(?:jr|sr|ii|iii|iv|v)\.?$", "", name)
    return re.sub("[^a-z0-9]", "", name)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load_source(folder, filename):
    path = INPUTS / folder / filename
    manifest = json.loads((path.parent / "MANIFEST.json").read_bytes())
    item, = [row for row in manifest["files"] if row["file"] == filename]
    if item["http_status"] != 200 or digest(path) != item["sha256"] or item["retrieved_utc"] >= FIRST_KICKOFF:
        raise ValueError("Invalid pregame source " + str(path))
    return path, {"source_url": item["url"], "retrieved_utc": item["retrieved_utc"], "sha256": item["sha256"]}


def official_report(nicknames):
    path, source = load_source("nfl-com-injuries-probe.20261115T065708Z", "nfl_injuries_reg10.html")
    rows = {}
    tables = re.findall(r'class="d3-o-section-sub-title"><span>(.*?)</span>.*?<table\b[^>]*>(.*?)</table>',
                        path.read_text(), re.S)
    seen_teams = set()
    for nickname, table in tables:
        if nickname not in nicknames:
            continue
        team = nicknames[nickname]
        seen_teams.add(team)
        for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S):
            cells = [" ".join(unescape(re.sub(r"<[^>]+>", "", cell)).split()) for cell in
                     re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) != 5:
                continue
            player, pos, injury, practice, status = cells
            key = (team, norm(player))
            assert key not in rows
            rows[key] = {"source": "NFL.com Week 10 injury report", "player": player, "position": pos,
                         "injury": injury or None, "practice": practice or None,
                         "game_status": status or None, **source}
    assert seen_teams == set(nicknames.values())
    return rows, source


def capture_health():
    summaries = {}
    codes = {}
    nicknames = {}
    espn = defaultdict(list)
    audit_sources = defaultdict(list)
    for p in sorted((INPUTS / "espn-summary.20261115T065600Z").glob("event_*.json")):
        path, source = load_source(p.parent.name, p.name)
        doc = json.loads(path.read_bytes())
        comp = doc["header"]["competitions"][0]
        teams = {x["homeAway"]: x["team"] for x in comp["competitors"]}
        event = (teams["away"]["displayName"], teams["home"]["displayName"])
        summaries[event] = (str(comp["id"]), comp["date"])
        for team in teams.values():
            codes[team["displayName"]] = team["abbreviation"]
            nicknames[team["name"]] = team["abbreviation"]
            audit_sources[team["abbreviation"]].append(source)
        for group in doc.get("injuries", []):
            for row in group["injuries"]:
                key = (group["team"]["abbreviation"], norm(row["athlete"]["displayName"]))
                espn[key].append({"source": "ESPN game injury summary", "game_status": row["status"],
                                  "report_utc": row.get("date"), **source})
    assert len(summaries) == 12 and len(codes) == 24
    official, official_src = official_report(nicknames)
    league_file, league_source = load_source("probe-injury-endpoints.20261115T065648Z", "site_league_injuries.json")
    for team in json.loads(league_file.read_bytes())["injuries"]:
        code = codes.get(team["displayName"])
        if not code:
            continue
        for row in team["injuries"]:
            espn[code, norm(row["athlete"]["displayName"])].append(
                {"source": "ESPN league injury report", "game_status": row["status"],
                 "report_utc": row.get("date"), **league_source})
    for path in sorted((INPUTS / "espn-depthcharts.20261115T065829Z").glob("team_*.json")):
        path, source = load_source(path.parent.name, path.name)
        doc = json.loads(path.read_bytes())
        code = doc["team"]["abbreviation"]
        audit_sources[code].extend([official_src, league_source, source])
        statuses = set()
        for formation in doc["depthchart"]:
            for slot in formation["positions"].values():
                for a in slot.get("athletes", []):
                    for injury in a.get("injuries", []):
                        statuses.add((norm(a["displayName"]), injury["status"], injury.get("date")))
        for player, status, report_time in sorted(statuses):
            espn[code, player].append({"source": "ESPN depth chart", "game_status": status,
                                       "report_utc": report_time, **source})
    return summaries, codes, official, espn, audit_sources


def health_for(code, name, official, espn, roster_status):
    key = code, norm(name)
    report = official.get(key)
    observations = ([report] if report else []) + espn.get(key, [])
    game_status = report.get("game_status") if report else None
    adverse = {r["game_status"] for r in observations if r["game_status"] in INACTIVE | PENDING}
    # An ESPN 'Active' tag may describe recovery from a past injury or roster membership.
    # An ACT roster entry is compatible with a game-specific designation of Out.
    if not code:
        status = "identity_unverified"
    elif len(adverse) > 1 or (report and not game_status and adverse):
        status = "conflicting_status"
    elif adverse & INACTIVE or (roster_status and roster_status != "ACT"):
        status = "reported_unavailable"
    elif adverse & PENDING:
        status = "game_status_pending"
    else:
        status = "no_adverse_designation_found"
    return status, {"roster_status": roster_status, "official_game_status": game_status,
                    "official_report_listed": report is not None, "practice": report.get("practice") if report else None,
                    "observations": observations, "final_inactives_verified": False}


def segments(headers):
    result = {}
    for i, h in enumerate(headers):
        if h == "COMP" and headers[i:i+3] == ["COMP", "ATT", "YDS"]:
            result["player_pass_yds"] = (i+2, i+1, "pass_attempts")
        elif h == "ATT" and headers[i:i+2] == ["ATT", "YDS"] and not (i > 0 and headers[i-1] == "COMP"):
            result["player_rush_yds"] = (i+1, i, "rush_attempts")
        elif h == "REC" and headers[i:i+2] == ["REC", "YDS"]:
            result["player_reception_yds"] = (i+1, i, "receptions")
    return result


def numeric(value):
    return int(value.replace(",", "")) if value is not None else None


def historical_games():
    raw = SLATE.parent / "data" / "raw"
    source, = [x for x in json.loads((raw / "MANIFEST.json").read_bytes())["files"] if x["path"] == "data/raw/games.csv"]
    path = raw / "games.csv"
    assert digest(path) == source["sha256"]
    index = {}
    with path.open(newline="") as src:
        for row in csv.DictReader(src):
            if row["season"] != "2026" or row["game_type"] != "REG" or row["gameday"] >= "2026-11-15" or not row["home_score"]:
                continue
            for side, other in [("home", "away"), ("away", "home")]:
                team, opp = row[side+"_team"], row[other+"_team"]
                pf, pa = int(row[side+"_score"]), int(row[other+"_score"])
                key = row["gameday"], int(row["week"]), "LAR" if opp == "LA" else opp, pf, pa
                assert key not in index
                index[key] = {"game_id": row["game_id"], "game_team": "LAR" if team == "LA" else team,
                              "opponent_team": key[2], "starting_qb": row[side+"_qb_name"] or None}
    return index, {"source_url": source["url"], "retrieved_utc": source["retrieved_at_utc"], "sha256": source["sha256"]}


def appearance_sources():
    reports = json.loads((HERE/"official_appearance_sources_20261115.json").read_bytes())
    books = json.loads((HERE/"appearance_gamebook_rows_20261115.json").read_bytes())
    indexed = {}
    for game, item in books["games"].items():
        for p in item["players"]:
            assert p["all_sections_present"] and p["state"] in {"lineup","substitution","inactive","did_not_play"}
            indexed[(game,norm(p["name"]))] = (p["state"],item["source_url"])
    inactive = {}
    clubs = {k.lower():v for k,v in CLUBS.items()}
    for w, item in reports.items():
        if not w.isdigit():
            continue
        for club, names in item["teams"].items():
            if club in clubs:
                for name in names:
                    inactive[int(w),clubs[club],norm(name)] = item["source_url"]
    for item in reports["club_inactives"]:
        inactive[item["week"],clubs[item["club"]],norm(item["player"])] = item["source_url"]
    return indexed,inactive


def participation(game, name, raw_stats, book, unavail, full_season, source):
    entry=book.get((game["game_id"],norm(name)))
    inactive_url=unavail.get((game["week"],game["game_team"],norm(name)))
    if entry:
        label,url=entry
        return ("played" if label in {"lineup","substitution"} else label, "NFL gamebook "+label, url)
    if inactive_url:
        return "inactive","NFL or team inactives",inactive_url
    if any(v is not None for v in raw_stats):
        return "played","NFL.com reported individual game statistics",source["source_url"]
    if full_season:
        return "played","NFL.com season games played equals all completed player-log rows",source["source_url"].replace("logs/2026/","career")
    raise ValueError("Unresolved participation: "+name+" "+str(game["game_id"]))


def player_form(capture, player, market, history, team, appearances_sources):
    p = capture["players"][player]
    if "log_url" not in p:
        return {"last_games": [], "season_log": [], "season_avg": None, "source_url": None,
                "limitations": ["No unique player match on either official game roster."]}
    log = capture["logs"][p["log_url"]]
    season_url = p["log_url"].replace("logs/2026/", "career")
    totals = capture["season_totals"][season_url]
    rows = totals["categories"].get(market, [])
    # Official career tables show one row per team when a player changed teams during a season.
    # Refuse duplicate team rows or an unexpected aggregate row rather than double counting.
    recognized = rows and len({r["team_name"] for r in rows}) == len(rows) and all(
        r["team_name"] not in ("", "TOTAL", "2TM", "3TM") and r["games_played"] is not None for r in rows)
    published_games = sum(r["games_played"] for r in rows) if recognized else None
    yards = sum(r["yards"] for r in rows) if recognized and all(r["yards"] is not None for r in rows) else None
    volume = sum(r["volume"] for r in rows) if recognized and all(r["volume"] is not None for r in rows) else None
    all_categories_games = {sum(r["games_played"] for r in ss) for ss in totals["categories"].values()
                            if ss and all(r["games_played"] is not None for r in ss)}
    columns = segments(log["headers"])
    supplemental = capture.get("hunter_receiving", {}) if player == "Travis Hunter" and market == "player_reception_yds" else {}
    games = []
    for g in log["games"]:
        values = g["values"]
        workload = {}
        for key, (yi, vi, vname) in columns.items():
            workload[key] = numeric(values[yi])
            workload[vname] = numeric(values[vi])
        supplemental_row = supplemental.get(g["date"])
        if supplemental_row:
            workload[market] = supplemental_row["yards"]
            workload["receptions"] = supplemental_row["receptions"]
            workload["supplemental_source"] = supplemental_row
        pf, pa = map(int, re.findall(r"\d+", g["result"]))
        opp = CLUBS[g["opponent"].lstrip("@")]
        matched = history.get((g["date"], g["week"], opp, pf, pa), {})
        item = {"date": g["date"], "week": g["week"], "opponent": g["opponent"], "result": g["result"],
                      "game_id": matched.get("game_id"), "game_team": matched.get("game_team"),
                      "opponent_team": opp, "team_starting_qb": matched.get("starting_qb"),
                      "yards": workload.get(market), **workload}
        status,basis,source=participation(item,p["name"],values,*appearances_sources,
                                          all_categories_games == {len(log["games"])},log["source"])
        item.update(participation=status,participation_basis=basis,participation_source_url=source)
        games.append(item)
    known = [g["yards"] for g in games if g["yards"] is not None]
    volume_name = {"player_pass_yds": "pass_attempts", "player_rush_yds": "rush_attempts",
                   "player_reception_yds": "receptions"}[market]
    appearances = sum(g["participation"]=="played" for g in games)
    for g in games:
        if g["participation"]!="played" and g["yards"] is not None:
            raise ValueError("Nonparticipant with reported yards: "+player+" "+str(g["game_id"]))
    zero_support=None
    club_zero=capture.get("confirmed_no_stats_by_player",{}).get(p["name"])
    if club_zero and market=="player_reception_yds":
        yards,volume=0,0
        zero_support=club_zero["source_url"]
    known_volumes=[g.get(volume_name) for g in games if g.get(volume_name) is not None]
    if volume is not None and sum(known_volumes)==volume and yards is not None and sum(known)==yards:
        zero_support=zero_support or totals["source"]["source_url"]
    for g in games:
        if g["participation"]=="played" and g["yards"] is None and zero_support and not g.get(volume_name):
            g.update(yards=0,**{market:0,volume_name:0})
            g["yards_basis"]="Derived zero: verified appearance; all season attempts/receptions and yards already accounted for."
            g["zero_reconciliation_url"]=zero_support
    season_avg=round(yards/appearances,3) if appearances and yards is not None else None
    played=[g for g in games if g["participation"]=="played"]
    last=played[:4]
    known=[g["yards"] for g in played if g["yards"] is not None]
    limitations = []
    if market not in columns and not supplemental:
        limitations.append("Official player log does not display this market's stat category.")
    if season_avg is None:
        limitations.append("Official season total or games-played denominator unavailable.")
    if any(g["yards"] is None for g in last):
        limitations.append("At least one proven appearance has unverified market yardage and remains unknown.")
    if published_games is not None and published_games != appearances:
        limitations.append("The career table's games field differs from verified game-by-game participation. The appearance denominator uses the audited game rows.")
    discrepancy = yards is not None and (market in columns or bool(supplemental)) and sum(known) != yards
    if discrepancy:
        limitations.append("Sum of numeric official game rows differs from the official season total.")
    if len(rows) > 1:
        limitations.append("Season aggregate spans multiple team stints.")
    if any(g["game_team"] and g["game_team"] != team for g in games):
        limitations.append("The player's prior game rows include another team. Inspect game_team before using history.")
    if any(g["game_id"] is None for g in games):
        limitations.append("At least one log row lacks a verified nflverse game-team match.")
    if supplemental:
        limitations.append("Individual receiving rows come from Jaguars official box scores. Any derived zero has its participation and completion checks recorded in the row.")
    return {"last_games": last, "season_log": games, "last_games_basis": "Most recent four consecutive 2026 regular-season appearances, including verified zeros.",
            "recent_reported_yards_games": sum(g["yards"] is not None for g in last),
            "reported_yards_in_last_four_team_games": sum(g["yards"] is not None for g in games[:4]),
            "season_log_rows": len(games), "season_reported_yards_games": len(known),
            "season_games_played": appearances, "season_yards": yards, "season_volume": volume,
            "volume_stat": volume_name, "season_avg": season_avg, "season_by_team": rows,
            "season_avg_basis": "Official season yardage divided by verified 2026 regular-season appearances.",
            "career_table_games_as_published":published_games,
            "source_url": log["source"]["source_url"], "retrieved_utc": log["source"]["retrieved_utc"],
            "sha256": log["source"]["sha256"], "season_source": totals["source"],
            "season_log_yards_disagree": discrepancy, "limitations": limitations}


def line_history(games, line):
    windows = {}
    played=[g for g in games if g["participation"]=="played"]
    for n in (5, 10):
        recent = played[:n]
        known = [g["yards"] for g in recent if g["yards"] is not None]
        windows["last_" + str(n)] = {"requested_rows": n, "available_rows": len(recent), "reported_yardage_rows": len(known),
                                     "season":2026,"basis":"Consecutive current-season appearances, newest first.",
                                     "weeks":[g["week"] for g in recent],
                                     "yards":[g["yards"] for g in recent],
                                     "included_derived_zeros": sum((g.get("yards_basis") or g.get("supplemental_source", {}).get("basis", "")).startswith("Derived zero") for g in recent),
                                     "unreported": len(recent)-len(known), "over": sum(v > line for v in known),
                                     "under": sum(v < line for v in known), "push": sum(v == line for v in known)}
    return windows


def quotes(odds):
    for game in odds["event_odds"]:
        for book in game["bookmakers"]:
            for market in book["markets"]:
                if market["key"] not in MARKETS:
                    continue
                grouped = defaultdict(dict)
                for index, outcome in enumerate(market["outcomes"]):
                    side = outcome["name"]
                    pair = grouped[outcome["description"], outcome["point"]]
                    if side in pair or side not in ("Over", "Under") or abs(outcome["price"]) < 100:
                        raise ValueError("Duplicate or invalid quote side")
                    pair[side] = (outcome["price"], index)
                for (name, line), pair in grouped.items():
                    yield game, book, market, name, line, pair


def build():
    odds = json.loads(ODDS.read_bytes())
    capture = json.loads(FORM.read_bytes())
    summaries, codes, official, espn, audit_sources = capture_health()
    history, history_source = historical_games()
    appearance_evidence=appearance_sources()
    observed = {x["endpoint"]: x["observed_utc"] for x in odds["observations"]}
    props, excluded = [], []
    source_coverage = defaultdict(Counter)
    traits = {}
    for g, b, m, name, line, pair in quotes(odds):
        oid, kick = g["id"], g["commence_time"]
        team_pair = (g["away_team"], g["home_team"])
        eid, kick2 = summaries[team_pair]
        parse = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
        assert parse(kick) == parse(kick2)
        time = observed["events/" + oid + "/odds"]
        assert m["last_update"] <= time < kick and capture["captured_utc"] < FIRST_KICKOFF
        typ = m["key"]
        p = capture["players"][name]
        code = codes.get(p.get("team_name"))
        if code:
            assert p["team_name"] in team_pair
        key = eid, name, typ
        if key not in traits:
            form = player_form(capture, name, typ, history, code, appearance_evidence)
            status, health = health_for(code, p.get("name", name), official, espn, p.get("roster_status"))
            reasons = []
            if status != "no_adverse_designation_found":
                reasons.append(status)
            if not form.get("reported_yards_in_last_four_team_games"):
                reasons.append("no_verified_recent_yardage")
            if form.get("season_log_yards_disagree"):
                reasons.append("season_log_discrepancy")
            traits[key] = form, status, health, reasons
        form, status, health, shared_reasons = traits[key]
        reasons = list(shared_reasons)
        if set(pair) != {"Over", "Under"}:
            reasons.append("one_sided_quote")
        op = pair.get("Over", (None, None))[0]
        un = pair.get("Under", (None, None))[0]
        endpoint = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events/" + oid + "/odds"
        row = {"event_id": eid, "event_espn_id": eid, "odds_event_id": oid, "kickoff_utc": kick,
               "player": name, "official_player_name": p.get("name"), "team": code, "position": p.get("position"),
               "player_identity_url": p.get("log_url"), "name_alias_source_url": p.get("name_alias_source_url"),
               "market": typ, "line": line, "over_price": op, "under_price": un,
               "over_american_price": op, "under_american_price": un, "book": b["title"], "book_key": b["key"],
               "book_reported": b["title"], "observed_utc": time, "checked_utc": time, "book_update_utc": m["last_update"],
               "source_url": endpoint, "source_file": str(ODDS), "local_availability_verified": False,
               "personal_price_verified": False, "availability": status, "health": health,
               "eligible_for_form_review": not reasons, "exclusion_reasons": reasons,
               "roster_source": capture["rosters"][p["team_name"]]["source"] if code else None,
               "player_form": form, "historical_results_at_current_line": line_history(form["season_log"], line)}
        (excluded if reasons else props).append(row)
        source_coverage[eid]["book_player_market_line_pairs"] += 1
        source_coverage[eid]["posted_sides"] += len(pair)
        source_coverage[eid]["excluded" if reasons else "eligible_for_form_review"] += 1
    all_rows = props + excluded
    coverage = {"games": len(source_coverage), "posted_player_labels": len({r["player"] for r in all_rows}),
                "matched_official_players": len({r["player_identity_url"] for r in all_rows if r["player_identity_url"]}),
                "paired_or_partial_quotes": len(all_rows), "posted_sides": sum(x["posted_sides"] for x in source_coverage.values()),
                "eligible_quotes": len(props), "excluded_quotes": len(excluded),
                "availability_by_quote": dict(Counter(r["availability"] for r in all_rows)),
                "exclusion_counts_nonexclusive": dict(Counter(reason for row in excluded for reason in row["exclusion_reasons"])),
                "by_event_espn_id": dict(source_coverage)}
    assert coverage["games"] == 12
    assert len({(x["odds_event_id"], x["book_key"], x["player"], x["market"], x["line"]) for x in all_rows}) == len(all_rows)
    return {"built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "version": 2, "available": bool(props), "why_not": None if props else "No eligible two-sided quotes",
            "coverage": coverage, "price_capture": {"source_file": str(ODDS), "sha256": digest(ODDS),
            "captured_utc": odds["captured_utc"], "personal_price_verified": False},
            "official_workload_capture": {"source_file": str(FORM), "sha256": digest(FORM), "captured_utc": capture["captured_utc"]},
            "historical_game_team_source": history_source,
            "appearance_sources": [{"source_file":str(HERE/name),"sha256":digest(HERE/name)} for name in ("official_appearance_sources_20261115.json","appearance_gamebook_rows_20261115.json")],
            "quarterback_context_by_team": capture["quarterback_context_by_team"],
            "posted_name_alias_evidence": capture["alias_source"],
            "health_sources_by_team": dict(audit_sources),
            "notes": ["props contains matched, two-sided markets with at least one observed market yardage in the last four log rows and no unresolved adverse status or detected season/log conflict. Inspect sample size and recent role before using a row.",
                      "excluded_props preserves the remaining prices and distinct reasons. Every game precedes official final inactives.",
                      "Every quote is a captured public US-book reference. The personally available price, market rules and Louisiana availability require an independent check.",
                      "Multiple books on one player/market or the same game's correlated markets are not independent observations. Use the official identity URL to group posted aliases.",
                      "Last-five/last-ten windows contain consecutive 2026 regular-season player appearances only, with verified zeros retained and DNP/inactive dates separately labeled. Current posted thresholds and historical game-specific lines are separate measures. No prior season is appended.",
                      "These inputs supply observations, not forecasts, calibrated win rates or an estimated betting advantage."],
            "props": props, "excluded_props": excluded}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=SLATE / "props_20261115.json")
    args = parser.parse_args()
    doc = build()
    temp = args.output.with_suffix(".tmp")
    temp.write_text(json.dumps(doc, separators=(",", ":"), allow_nan=False) + "\n")
    temp.replace(args.output)
    print(json.dumps(doc["coverage"], indent=2))
