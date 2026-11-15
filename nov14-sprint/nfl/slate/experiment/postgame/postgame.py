#!/usr/bin/env python3
"""Postgame intake: saved public results -> the existing journal, through its own interface.

Owner: postgame writer session (assigned by the nov14-sprint coordinator, 2026-11-15 07:34Z).
Paper only. This module makes no network call, imports no odds feed and writes nothing itself:
every result goes in through journal.record_final or journal.record_player_result.

Inputs are saved, public, keyless captures (one or more JSON files):
  * the ESPN public-lines capture made by Codex (dict with "games", each with "teams"/"final_score");
  * a final ESPN event summary with team/athlete IDs and fully named box-score columns;
  * a raw ESPN scoreboard response (dict with "events");
  * an NFL.com game-log capture like tools/official_player_logs_*.json ("players" + "logs");
  * a manual file: {"captured_utc": ..., "finals": [...], "players": [...]} (see README.md).

Rules (from the 07:34Z assignment):
  * A player is matched by exact full name, plus a team that is one of the event's two teams,
    plus the event. Anything else (alias, two matches, no row) stays PENDING. The one allowance is the
    trailing dot of a final Jr/Sr/II/III/IV/V ("Brian Thomas Jr" = "Brian Thomas Jr."); the suffix
    itself must still be there on both sides.
  * A missing stat, a DNP or a null stays PENDING. It is never recorded as zero. A real 0 is recorded.
  * A team final is recorded only when the source says final and the journal's earliest-final time
    (kickoff + 150 minutes) has passed. A file that says final before that time is refused.
  * A player result is recorded only after the game's team final is in the journal and the log row's
    score agrees with it.
  * An existing final or player result that differs is never overwritten: that is a refusal.

The strict ESPN final test is adapted from the agent-made desk_scores.py (find_final):
~/Documents/Codex/2026-11-14/nfl-trading-session-review/outputs/Paper_Desk/nfl/desk_scores.py
sha256 a931d8ae1cb6f1859a4df1cbeab2cd75857fd7bd6457b1a017b702518bccfdda. Its live fetch is not copied.

Python 3.9, standard library only. Run with: /usr/bin/python3 -I postgame.py --data DIR [FILE ...]
"""
from __future__ import print_function

import argparse
import datetime
import fcntl
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT = os.path.dirname(HERE)
if EXPERIMENT not in sys.path:
    sys.path.insert(0, EXPERIMENT)

import journal as J  # noqa: E402  (the existing journal; read-only to this module's author)

INBOX = os.path.join(HERE, "inbox")
FUTURE_SLACK = datetime.timedelta(minutes=5)
KICKOFF_MATCH = datetime.timedelta(hours=6)
LOCAL_SHIFT = datetime.timedelta(hours=5)   # kickoff UTC -> US calendar date of the game
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
SCORE = re.compile(r"^\d{1,3}$")
LOG_RESULT = re.compile(r"^\s*([WLT])\s+(\d{1,3})\s*-\s*(\d{1,3})")
NO_VALUE = ("", "-", "--", "dnp", "inactive", "out", "n/a", "na", "none", "null")

# NFL.com game-log layouts (exact header tuples) -> journal market -> column index.
LAYOUTS = {
    ("REC", "YDS", "AVG", "LNG", "TD", "ATT", "YDS", "AVG", "LNG", "TD", "FUM", "LOST"):
        {"player_receptions": 0, "player_reception_yds": 1, "player_rush_attempts": 5, "player_rush_yds": 6},
    ("ATT", "YDS", "AVG", "LNG", "TD", "REC", "YDS", "AVG", "LNG", "TD", "FUM", "LOST"):
        {"player_rush_attempts": 0, "player_rush_yds": 1, "player_receptions": 5, "player_reception_yds": 6},
    ("COMP", "ATT", "YDS", "AVG", "TD", "INT", "SCK", "SCKY", "RATE", "ATT", "YDS", "AVG", "TD", "FUM", "LOST"):
        {"player_pass_completions": 0, "player_pass_attempts": 1, "player_pass_yds": 2, "player_pass_tds": 4,
         "player_rush_attempts": 9, "player_rush_yds": 10},
}
SUPPORTED = sorted(set(m for layout in LAYOUTS.values() for m in layout))


class Refusal(Exception):
    pass


# ---------------------------------------------------------------- small helpers

def _n(s):
    return J.norm_text(s)


SUFFIXES = ("jr", "sr", "ii", "iii", "iv", "v")


def _name_key(s):
    """The journal's name key, with only the trailing dot of a final generational suffix dropped.

    "Brian Thomas Jr" and "Brian Thomas Jr." compare equal. "Brian Thomas" never equals either one:
    the suffix itself is kept, and nothing else about the name is loosened.
    """
    words = _n(s).split(" ")
    if len(words) > 1 and words[-1].endswith(".") and words[-1][:-1] in SUFFIXES:
        words[-1] = words[-1][:-1]
    return " ".join(words)


def _num(value):
    """A stat as float, or None when it is missing, a DNP marker or not a plain number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text.lower() in NO_VALUE or not NUMBER.match(text):
        return None
    return float(text)


def _score(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and value != int(value):
        return None
    text = str(int(value)) if isinstance(value, (int, float)) else str(value).strip()
    return int(text) if SCORE.match(text) else None


def _utc(text):
    return J.parse_utc(text) if text else None


def _game_date(kickoff):
    return (kickoff - LOCAL_SHIFT).date().isoformat()


def _short(path):
    return os.path.basename(path)


# ---------------------------------------------------------------- reading the saved captures

def _espn_final(status):
    """Strict ESPN final test, adapted from desk_scores.find_final."""
    kind = (status or {}).get("type") or {}
    ok = kind.get("completed") is True and kind.get("state") == "post" and kind.get("name") == "STATUS_FINAL"
    return ok, kind.get("name") or kind.get("description") or "no status"


def _h1_from_linescores(lines):
    if not isinstance(lines, list) or len(lines) < 2:
        return None
    vals = []
    for item in lines[:2]:
        v = item.get("value",item.get("displayValue")) if isinstance(item, dict) else item
        v = _num(v)
        if v is None or v != int(v) or v < 0:
            return None
        vals.append(int(v))
    return vals[0] + vals[1]


# ESPN box-score category and machine keys, independent of displayed column order.
ESPN_MARKETS = {
    "receiving": {"receivingYards": "player_reception_yds", "receptions": "player_receptions"},
    "rushing": {"rushingYards": "player_rush_yds", "rushingAttempts": "player_rush_attempts"},
    "passing": {"passingYards": "player_pass_yds", "passingTouchdowns": "player_pass_tds",
                "passingAttempts": "player_pass_attempts", "completions": "player_pass_completions"},
}


def _espn_summary(doc, out, tag, receipt):
    header = doc["header"]
    eid = str(header.get("id") or "")
    comps = header.get("competitions") or []
    if not eid.isdigit() or len(comps) != 1 or str(comps[0].get("id")) != eid:
        raise Refusal("ESPN summary has an ambiguous event identity")
    if (header.get("league") or {}).get("slug") != "nfl":
        raise Refusal("ESPN summary is not identified as NFL")
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=" + eid
    if receipt and receipt["url"] != url:
        raise Refusal("ESPN summary event ID differs from the request")
    comp = comps[0]
    kick = J.stamp(J.parse_utc(comp["date"]))
    sides = {t["homeAway"]:t for t in comp["competitors"]}
    if set(sides) != {"away","home"} or len(comp["competitors"]) != 2:
        raise Refusal("ESPN summary lacks a unique home and away side")
    teams = {str(t["team"]["id"]):t["team"]["displayName"] for t in sides.values()}
    if len(teams) != 2 or len(set(teams.values())) != 2:
        raise Refusal("ESPN summary duplicates a team")
    h, a = sides["home"], sides["away"]
    final, status = _espn_final(comp["status"])
    score = dict(home_score=_score(h.get("score")), away_score=_score(a.get("score")))
    matchup = dict(espn_event_id=eid, kickoff_utc=kick, home_team=h["team"]["displayName"],
                   away_team=a["team"]["displayName"], **score)
    out.update(shape="espn_boxscore", captured=_utc(receipt.get("retrieved_utc")) if receipt else None)
    source = "%s (%s)" % (url,tag)
    out["games"].append(dict(matchup,final=final,status=status,source=source,finished_utc=None,
                             h1_home=_h1_from_linescores(h.get("linescores")),h1_away=_h1_from_linescores(a.get("linescores"))))
    if not final or None in score.values():
        return out
    identities = {}
    for tb in doc["boxscore"].get("players") or []:
        team = tb.get("team") or {}
        tid = str(team.get("id") or "")
        if tid not in teams or _n(team.get("displayName")) != _n(teams[tid]):
            raise Refusal("Team in ESPN player box does not match game header")
        for group in tb.get("statistics") or []:
            category = group.get("name")
            cols = group.get("keys") or []
            for entry in group.get("athletes") or []:
                athlete = entry.get("athlete") or {}
                name = athlete.get("displayName") or athlete.get("fullName")
                aid = str(athlete.get("id") or "")
                if not name or not aid.isdigit():
                    continue
                identities.setdefault(_name_key(name),set()).add((tid,aid))
                if category not in ESPN_MARKETS or not cols or len(set(cols)) != len(cols):
                    continue
                values = entry.get("stats") or []
                if len(values) != len(cols) or entry.get("didNotPlay") or entry.get("notActive"):
                    continue
                if str(entry.get("status","")).strip().lower() in NO_VALUE[3:] or athlete.get("active") is False:
                    continue
                fields = dict(zip(cols, values))
                if category == "passing" and "completions/passingAttempts" in fields:
                    combined = str(fields["completions/passingAttempts"])
                    if re.fullmatch(r"\d+/\d+",combined):
                        made, attempts = combined.split("/")
                        if int(made) <= int(attempts):
                            fields.setdefault("completions",made)
                            fields.setdefault("passingAttempts",attempts)
                for stat, market in ESPN_MARKETS[category].items():
                    val = fields.get(stat)
                    if val is None or not re.fullmatch(r"-?\d+",str(val).strip()):
                        continue
                    val = int(val)
                    if val < 0 and not market.endswith("_yds"):
                        continue
                    out["players"].append(dict(matchup,player=name,athlete_id=aid,team=teams[tid],market=market,
                        value=val,source="%s; ESPN athlete %s, %s.%s" % (source,aid,category,stat)))
    out["players"] = [p for p in out["players"] if len(identities[_name_key(p["player"])])==1]
    return out


def read_capture(path, receipt=None):
    """Return {"shape", "captured", "games": [...], "players": [...]} in one plain form."""
    try:
        doc = J.load_json(path)
    except Exception as err:  # unreadable or not JSON
        raise Refusal("%s: cannot read it as JSON (%s)" % (_short(path), err))
    sha = J.sha256_file(path)
    if receipt:
        endpoint = receipt.get("url") or ""
        is_board = re.fullmatch(r"https://site\.api\.espn\.com/apis/site/v2/sports/football/nfl/scoreboard\?dates=\d{8}",endpoint)
        is_box = re.fullmatch(r"https://site\.api\.espn\.com/apis/site/v2/sports/football/nfl/summary\?event=\d+",endpoint)
        if not isinstance(doc,dict) or not ((is_board and isinstance(doc.get("events"),list))
                  or (is_box and isinstance(doc.get("header"),dict) and isinstance(doc.get("boxscore"),dict))):
            raise Refusal("Public response does not match the requested ESPN endpoint")
    if receipt and (receipt.get("sha256") != sha or receipt.get("http_status") != 200 or receipt.get("error")):
        raise Refusal("Raw ESPN file does not match the successful fetch receipt")
    tag = "file %s, sha256 %s" % (_short(path), sha[:12])
    out = {"path": os.path.abspath(path), "sha256": sha, "games": [], "players": []}
    if isinstance(doc, dict) and isinstance(doc.get("header"),dict) and isinstance(doc.get("boxscore"),dict):
        return _espn_summary(doc,out,tag,receipt)
    if isinstance(doc, dict) and isinstance(doc.get("logs"), dict) and isinstance(doc.get("players"), dict):
        out["shape"] = "nflcom_game_logs"
        out["captured"] = _utc(doc.get("captured_utc"))
        cut = doc.get("cutoff_exclusive")
        out["cutoff"] = cut if isinstance(cut, str) and cut else None
        for key, p in doc["players"].items():
            if not isinstance(p, dict) or not p.get("team_name"):
                continue
            log = doc["logs"].get(p.get("log_url")) or {}
            name = log.get("official_name") or p.get("name") or key
            layout = LAYOUTS.get(tuple(log.get("headers") or ()))
            src = log.get("source") if isinstance(log.get("source"), dict) else {}
            page = src.get("final_url") or src.get("source_url") or p.get("log_url")
            where = "%s (NFL.com game log retrieved %s, page sha256 %s; %s)" % (
                page, src.get("retrieved_utc") or "?", str(src.get("sha256") or "?")[:12], tag)
            for g in log.get("games") or []:
                out["players"].append({
                    "player": name, "team": p["team_name"], "date": g.get("date"), "opponent": g.get("opponent"),
                    "result": g.get("result"), "values": g.get("values"), "layout": layout,
                    "source": where if page else None})
        return out
    if isinstance(doc, dict) and isinstance(doc.get("events"), list):
        out["shape"] = "espn_scoreboard"
        out["captured"] = _utc(receipt["retrieved_utc"] if receipt else doc.get("captured_utc"))
        source_url = receipt["url"] if receipt else doc.get("source_url") or "ESPN scoreboard"
        for ev in doc["events"]:
            comp = ((ev.get("competitions") or [{}])[0]) or {}
            final, status = _espn_final(comp.get("status") or ev.get("status"))
            teams = dict((c.get("homeAway"), c) for c in comp.get("competitors") or [])
            home, away = teams.get("home") or {}, teams.get("away") or {}
            out["games"].append({
                "home_team": (home.get("team") or {}).get("displayName"),
                "away_team": (away.get("team") or {}).get("displayName"),
                "espn_event_id": str(ev.get("id") or ""), "kickoff_utc": ev.get("date"), "final": final, "status": status,
                "home_score": _score(home.get("score")), "away_score": _score(away.get("score")),
                "h1_home": _h1_from_linescores(home.get("linescores")),
                "h1_away": _h1_from_linescores(away.get("linescores")),
                "finished_utc": None, "source": "%s (ESPN scoreboard, %s)" % (source_url, tag)})
        return out
    rows = doc.get("games") if isinstance(doc, dict) else None
    if isinstance(rows, list) and rows and all(isinstance(g, dict) and isinstance(g.get("teams"), dict) for g in rows):
        out["shape"] = "espn_public_lines"
        out["captured"] = _utc(doc.get("capture_complete_utc") or doc.get("captured_utc"))
        for g in rows:
            fs, half = g.get("final_score") or {}, g.get("halftime") or g.get("h1_score") or {}
            out["games"].append({
                "home_team": g["teams"].get("home"), "away_team": g["teams"].get("away"), "event": g.get("event_id"),
                "kickoff_utc": g.get("kickoff_utc"), "final": g.get("state") == "STATUS_FINAL",
                "status": g.get("state") or "no status",
                "home_score": _score(fs.get("home")), "away_score": _score(fs.get("away")),
                "h1_home": _score(half.get("home")), "h1_away": _score(half.get("away")),
                "finished_utc": g.get("finished_utc"),
                "source": "%s (ESPN public lines capture, %s)" % (g.get("source_url") or "ESPN", tag)})
        return out
    if isinstance(doc, dict) and (isinstance(doc.get("finals"), list) or isinstance(doc.get("players"), list)):
        out["shape"] = "manual"
        out["captured"] = _utc(doc.get("captured_utc"))
        for g in doc.get("finals") or []:
            if not isinstance(g, dict):
                continue
            out["games"].append({
                "home_team": g.get("home_team"), "away_team": g.get("away_team"), "event": g.get("event"),
                "kickoff_utc": g.get("kickoff_utc"),
                "final": str(g.get("status") or "").strip().lower() in ("final", "status_final"),
                "status": g.get("status") or "no status",
                "home_score": _score(g.get("home_score")), "away_score": _score(g.get("away_score")),
                "h1_home": _score(g.get("h1_home")), "h1_away": _score(g.get("h1_away")),
                "finished_utc": g.get("finished_utc"),
                "source": "%s (manual intake, %s)" % (g.get("source") or "", tag) if g.get("source") else None})
        for p in doc.get("players") or []:
            if not isinstance(p, dict):
                continue
            out["players"].append({
                "player": p.get("player"), "team": p.get("team"), "event": p.get("event"),
                "home_team": p.get("home_team"), "away_team": p.get("away_team"),
                "market": p.get("market"), "period": p.get("period"), "value": p.get("value"), "status": p.get("status"),
                "source": "%s (manual intake, %s)" % (p.get("source"), tag) if p.get("source") else None})
        return out
    raise Refusal("%s: not a shape this intake reads (ESPN lines, ESPN scoreboard, NFL.com logs, manual)"
                  % _short(path))


# ---------------------------------------------------------------- what the journal still needs

def needs_of(state):
    """Per event: whether a first-half score is needed, and the player props to settle."""
    out = {}
    for r in state.predictions:
        ident = r["identity"]
        ev = out.setdefault(ident["event_id"], {"h1": False, "players": set(), "player_periods": set()})
        base = J.base_market(ident["market"])
        if base.startswith("player_"):
            if ident["period"] == "game":
                ev["players"].add((J.norm_text(ident["subject"]), " ".join(ident["subject"].split()), base))
            else:
                ev["player_periods"].add((J.norm_text(ident["subject"]),ident["subject"],ident["market"]))
        elif ident["period"] == "h1":
            ev["h1"] = True
    return out


def _match_event(state, home, away, kickoff_text, event=None):
    """Journal event ids for exact team names (and kickoff within 6 hours when the file gives one)."""
    if event and event in state.events:
        ev = state.events[event]
        if home is None or (_n(home) == _n(ev["home_team"]) and _n(away) == _n(ev["away_team"])):
            return [event]
        return []
    kick = None
    if kickoff_text:
        try:
            kick = J.parse_utc(kickoff_text)
        except Exception:
            kick = None
    hits = []
    for ev_id, ev in state.events.items():
        if _n(home) != _n(ev["home_team"]) or _n(away) != _n(ev["away_team"]):
            continue
        if kick is not None and abs(kick - J.parse_utc(ev["kickoff_utc"])) > KICKOFF_MATCH:
            continue
        hits.append(ev_id)
    return hits


# ---------------------------------------------------------------- the intake

def _espn_matches(state, home, away, kickoff_text, espn_id):
    if not home or not away or not kickoff_text:
        return []
    try:
        kick = J.parse_utc(kickoff_text)
    except J.JournalError:
        return []
    hits = _match_event(state,home,away,kickoff_text)
    return [eid for eid in hits if J.parse_utc(state.events[eid]["kickoff_utc"]) == kick
            and (not (espn_id and str(eid).isdigit()) or str(eid)==str(espn_id))]


def import_from_public(journal_dir, paths=None, now=None, receipts=None):
    """Serialize result checks and additions across concurrent imports of the same journal."""
    if not os.path.isdir(journal_dir):
        return _import(journal_dir,paths,now,receipts)
    fd = os.open(journal_dir,os.O_RDONLY)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        return _import(journal_dir,paths,now,receipts)
    finally:
        os.close(fd)


def _import(journal_dir, paths, now, receipts):
    """Record every final and player number the saved captures prove; report what stays pending.

    journal_dir: the journal's --data directory. paths: capture files (default: every *.json in
    postgame/inbox/). now: the clock (default: the journal's utc_now()). Returns a summary dict
    whose "exit_code" is 0 (nothing pending), 2 (some items pending) or 1 (a refusal or error).
    """
    now = now or J.utc_now()
    journal = J.Journal(journal_dir)
    summary = {"journal_dir": os.path.abspath(journal_dir), "now_utc": J.stamp(now), "inputs": [],
               "recorded_finals": [], "recorded_players": [], "already_recorded": 0,
               "pending": [], "refused": [], "notes": []}
    if paths is None:
        paths = sorted(glob.glob(os.path.join(INBOX, "*.json")))
        if not paths:
            summary["notes"].append("No saved captures in %s." % INBOX)
    try:
        state = J.State(journal)
    except J.JournalError as err:
        summary["refused"].append({"what": "journal", "reason": str(err)})
        return _finish(summary)
    caps = []
    for path in paths:
        try:
            cap = read_capture(path,(receipts or {}).get(os.path.abspath(path)))
        except Refusal as err:
            summary["refused"].append({"what": _short(path), "reason": str(err)})
            continue
        except Exception as err:  # a malformed field (bad time, wrong type): refuse the file, never guess
            summary["refused"].append({"what": _short(path), "reason": "cannot read it: %s" % err})
            continue
        if cap["captured"] is not None and cap["captured"] > now + FUTURE_SLACK:
            summary["refused"].append({"what": _short(path), "reason": "captured %s, after the clock here (%s)"
                                       % (J.stamp(cap["captured"]), J.stamp(now))})
            continue
        caps.append(cap)
        summary["inputs"].append({"path": cap["path"], "sha256": cap["sha256"], "shape": cap["shape"],
                                  "captured_utc": J.stamp(cap["captured"]) if cap["captured"] else None,
                                  "games": len(cap["games"]), "player_rows": len(cap["players"])})
    needs = needs_of(state)
    why = {}   # (event_id, item) -> reason it is still pending

    # Resolve disagreement before the first append; input order cannot choose a score.
    matched = []
    full_scores, half_scores = {}, {}
    for cap in caps:
        for g in cap["games"]:
            if cap["shape"] in ("espn_scoreboard","espn_boxscore"):
                hits = _espn_matches(state,g.get("home_team"),g.get("away_team"),g.get("kickoff_utc"),g.get("espn_event_id"))
            else:
                hits = _match_event(state, g.get("home_team"), g.get("away_team"), g.get("kickoff_utc"), g.get("event"))
            if len(hits) != 1:
                if len(hits) > 1:
                    summary["notes"].append("%s at %s matches %d journal games; left alone."
                                            % (g.get("away_team"), g.get("home_team"), len(hits)))
                continue
            ev_id = hits[0]
            matched.append((ev_id,g,cap))
            full = g.get("home_score"),g.get("away_score")
            half = g.get("h1_home"),g.get("h1_away")
            if not g["final"] or None in full:
                continue
            full_scores.setdefault(ev_id,set()).add(full)
            if None not in half:
                half_scores.setdefault(ev_id,set()).add(half)
    conflicts = {eid for eid,values in full_scores.items() if len(values)>1 or len(half_scores.get(eid,()))>1}
    for eid in sorted(conflicts):
        why[(eid,"final score")] = "public final or first-half scores conflict"
        summary["refused"].append(dict(what=state.events[eid]["game"],reason=why[(eid,"final score")]))
    for ev_id,g,cap in matched:
        if ev_id not in conflicts:
            _take_final(journal, state, ev_id, g, cap, now, summary, why)
            state = J.State(journal)

    # 2. player numbers, only for games whose team final is now in the journal
    for ev_id, need in sorted(needs.items()):
        ev = state.events[ev_id]
        for key,subject,market in sorted(need["player_periods"]):
            if (ev_id,key,market) not in state.player_results:
                summary["pending"].append(dict(event_id=ev_id, game=ev["game"], item="%s %s" % (subject,market),
                                              reason="A period-specific player stat is required."))
        if ev_id in conflicts:
            continue
        for key, subject, market in sorted(need["players"]):
            item = "%s %s" % (subject, market)
            found = _find_player(state, ev_id, ev, key, market, caps)
            old = state.player_results.get((ev_id, key, market))
            if old is not None:
                if found[0] == "ok" and float(found[1]) != float(old["value"]):
                    summary["refused"].append({"what": "%s, %s" % (ev["game"], item), "reason":
                                               "journal already has %g; %s says %g. Not overwritten; check by hand"
                                               % (old["value"], found[2], found[1])})
                elif found[0] == "pending" and ("disagree" in found[1] or "ambiguous" in found[1]):
                    summary["refused"].append({"what": "%s, %s" % (ev["game"],item),"reason":found[1]})
                elif found[0] == "ok":
                    summary["already_recorded"] += 1
                continue
            if found[0] != "ok":
                why[(ev_id, item)] = found[1]
                continue
            _status, value, source, team = found
            try:
                J.record_player_result(journal, ev_id, subject, market, value, source, now)
            except J.JournalError as err:
                summary["refused"].append({"what": "%s, %s" % (ev["game"], item), "reason": str(err)})
                continue
            summary["recorded_players"].append({"event_id": ev_id, "game": ev["game"], "player": subject,
                                                "team": team, "market": market, "value": value, "source": source})
            state = J.State(journal)

    # 3. what is still open, from the journal itself
    for ev_id, need in sorted(needs.items()):
        ev = state.events[ev_id]
        final = state.scores.get(ev_id)
        if not final:
            summary["pending"].append({"event_id": ev_id, "game": ev["game"], "item": "final score",
                                       "reason": why.get((ev_id, "final score"), "no saved capture shows this game final")})
        elif need["h1"] and final.get("h1_home") is None:
            summary["pending"].append({"event_id": ev_id, "game": ev["game"], "item": "first-half score",
                                       "reason": why.get((ev_id, "first-half score"), "no halftime score in the saved captures")})
        for key, subject, market in sorted(need["players"]):
            if (ev_id, key, market) not in state.player_results:
                item = "%s %s" % (subject, market)
                summary["pending"].append({"event_id": ev_id, "game": ev["game"], "item": item,
                                           "reason": why.get((ev_id, item), "no saved capture has this player's number")})
    return _finish(summary)


def _take_final(journal, state, ev_id, g, cap, now, summary, why):
    ev = state.events[ev_id]
    label = ev["game"]
    earliest = J._earliest_final(J.parse_utc(ev["kickoff_utc"]))
    if not g["final"]:
        why[(ev_id, "final score")] = "not final in %s (status %s)" % (_short(cap["path"]), g["status"])
        return
    if g["home_score"] is None or g["away_score"] is None:
        why[(ev_id, "final score")] = "final in %s but a score is missing" % _short(cap["path"])
        return
    try:
        proof = _utc(g.get("finished_utc")) if g.get("finished_utc") else cap["captured"]
    except Exception:
        why[(ev_id, "final score")] = "unreadable finished_utc in %s" % _short(cap["path"])
        return
    if now < earliest or (proof is not None and proof < earliest):
        summary["refused"].append({"what": label, "reason": "source says final at %s, but the game cannot be "
                                   "final before %s; nothing recorded" % (J.stamp(proof or now), J.stamp(earliest))})
        return
    if not g.get("source"):
        why[(ev_id, "final score")] = "the row has no source"
        return
    h1h, h1a = g.get("h1_home"), g.get("h1_away")
    if (h1h is None) != (h1a is None):
        h1h = h1a = None
    old = state.scores.get(ev_id)
    if old:
        if (old["home_score"], old["away_score"]) != (g["home_score"], g["away_score"]):
            summary["refused"].append({"what": label, "reason": "journal already has %d-%d; %s says %d-%d. "
                                       "Not overwritten; check by hand" % (old["away_score"], old["home_score"],
                                                                         _short(cap["path"]), g["away_score"], g["home_score"])})
            return
        if old.get("h1_home") is not None:
            if h1h is not None and (old["h1_home"], old["h1_away"]) != (h1h, h1a):
                summary["refused"].append({"what": label, "reason": "first-half score differs from the journal's; "
                                           "not overwritten"})
            else:
                summary["already_recorded"] += 1
            return
        if h1h is None:
            summary["already_recorded"] += 1
            return
    try:
        J.record_final(journal, ev_id, g["home_score"], g["away_score"], g["source"], now, h1_home=h1h, h1_away=h1a)
    except J.JournalError as err:
        summary["refused"].append({"what": label, "reason": str(err)})
        return
    summary["recorded_finals"].append({"event_id": ev_id, "game": label, "away_score": g["away_score"],
                                       "home_score": g["home_score"], "h1": None if h1h is None else [h1a, h1h],
                                       "source": g["source"]})
    if h1h is None:
        why[(ev_id, "first-half score")] = "halftime not in %s" % _short(cap["path"])


def _find_player(state, ev_id, ev, key, market, caps):
    """("ok", value, source, team) when the captures prove one number, else ("pending", reason)."""
    final = state.scores.get(ev_id)
    if not final:
        return ("pending", "the game's final score is not in the journal yet")
    teams = {_n(ev["home_team"]): "home", _n(ev["away_team"]): "away"}
    kickoff = J.parse_utc(ev["kickoff_utc"])
    want = _name_key(key)
    found = []
    for cap in caps:
        for p in cap["players"]:
            if _name_key(p.get("player")) != want or _n(p.get("team")) not in teams:
                continue
            if cap["shape"] == "espn_boxscore":
                if (p["market"] != market or _n(p["home_team"]) != _n(ev["home_team"])
                    or _n(p["away_team"]) != _n(ev["away_team"]) or kickoff != J.parse_utc(p["kickoff_utc"])
                    or (str(ev_id).isdigit() and str(ev_id)!=p["espn_event_id"])):
                    continue
                if (p["home_score"],p["away_score"]) != (final["home_score"],final["away_score"]):
                    return ("pending","ESPN player box score disagrees with the recorded final")
            elif cap["shape"] == "manual":
                if p.get("event"):
                    if str(p["event"]) != ev_id:
                        continue
                elif (_n(p.get("home_team")), _n(p.get("away_team"))) != (_n(ev["home_team"]), _n(ev["away_team"])):
                    continue
                if p.get("market") != market or p.get("period") not in (None,"game"):
                    continue
            else:
                if p.get("date") != _game_date(kickoff) or not _opponent_ok(p, ev, teams):
                    continue
            found.append((cap, p))
    if not found:
        day = _game_date(kickoff)
        logs = [c for c in caps if c["shape"] == "nflcom_game_logs"]
        if logs and all(c.get("cutoff") and day >= c["cutoff"] for c in logs):
            return ("pending", "the NFL.com logs file stops before this game (cutoff_exclusive %s); "
                               "it needs logs collected after the game" % min(c["cutoff"] for c in logs))
        return ("pending", "no row with this exact full name, a team in this game and this game's date")
    people = set(_n(p["team"]) for _c, p in found)
    if len(people) > 1:
        return ("pending", "ambiguous: this full name appears on both teams")
    values = []
    for cap, p in found:
        if cap["shape"] in ("manual","espn_boxscore"):
            if str(p.get("status") or "").strip().lower() in NO_VALUE[3:] + ("pending",):
                return ("pending", "marked %s in %s" % (p.get("status"), _short(cap["path"])))
            v = _num(p.get("value"))
        else:
            if p.get("layout") is None:
                return ("pending", "unknown NFL.com log layout for this player")
            col = p["layout"].get(market)
            if col is None:
                return ("pending", "the NFL.com log for this player has no %s column" % market)
            vals = p.get("values") or []
            if not any(x is not None for x in vals):
                return ("pending", "no stats in the game row (DNP or not posted)")
            m = LOG_RESULT.match(p.get("result") or "")
            if not m:
                return ("pending", "cannot read the game result in the log row")
            side = teams[_n(p["team"])]
            mine, theirs = ((final["home_score"], final["away_score"]) if side == "home"
                            else (final["away_score"], final["home_score"]))
            if (int(m.group(2)), int(m.group(3))) != (mine, theirs):
                return ("pending", "log row score %s disagrees with the journal's final" % p.get("result"))
            v = _num(vals[col]) if col < len(vals) else None
        if v is None:
            return ("pending", "stat missing in %s (kept pending, never zero)" % _short(cap["path"]))
        if not p.get("source"):
            return ("pending", "the row has no source")
        values.append((v, p["source"], p["team"]))
    if len(set(v for v, _s, _t in values)) > 1:
        return ("pending", "sources disagree: %s" % ", ".join("%g" % v for v, _s, _t in values))
    value, source, team = values[0]
    return ("ok", value, source, team)


def _opponent_ok(p, ev, teams):
    opp = str(p.get("opponent") or "").strip()
    away = opp.startswith("@")
    nick = _n(opp.lstrip("@"))
    side = teams[_n(p["team"])]
    if (side == "away") != away or not nick:
        return False
    other = ev["home_team"] if side == "away" else ev["away_team"]
    return _n(other) == nick or _n(other).endswith(" " + nick)


def _finish(summary):
    summary["exit_code"] = 1 if summary["refused"] else (2 if summary["pending"] else 0)
    return summary


# ---------------------------------------------------------------- command line

def render(summary):
    lines = ["Postgame intake at %s into %s" % (summary["now_utc"], summary["journal_dir"])]
    for i in summary["inputs"]:
        lines.append("  read %s (%s, sha256 %s)" % (_short(i["path"]), i["shape"], i["sha256"][:12]))
    for f in summary["recorded_finals"]:
        lines.append("  final: %s, %d-%d%s" % (f["game"], f["away_score"], f["home_score"],
                                               "" if f["h1"] is None else ", half %d-%d" % tuple(f["h1"])))
    for p in summary["recorded_players"]:
        lines.append("  player: %s (%s) %s = %g" % (p["player"], p["team"], p["market"], p["value"]))
    if summary["already_recorded"]:
        lines.append("  already in the journal (same values): %d" % summary["already_recorded"])
    for p in summary["pending"]:
        lines.append("  PENDING %s: %s (%s)" % (p["game"], p["item"], p["reason"]))
    for r in summary["refused"]:
        lines.append("  REFUSED %s: %s" % (r["what"], r["reason"]))
    for n in summary["notes"]:
        lines.append("  note: %s" % n)
    lines.append("exit %d" % summary["exit_code"])
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Record saved public postgame results in the journal.")
    ap.add_argument("--data", default=J.DEFAULT_DATA, help="the journal's data directory")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    ap.add_argument("paths", nargs="*", help="saved capture files (default: postgame/inbox/*.json)")
    args = ap.parse_args(argv)
    summary = import_from_public(args.data, paths=args.paths or None)
    print(json.dumps(summary, indent=2, sort_keys=True) if args.json else render(summary))
    return summary["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
