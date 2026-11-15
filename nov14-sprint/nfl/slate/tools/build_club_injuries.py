#!/usr/bin/env python3
"""Build nfl/slate/slate_20261115_club_injuries.json from the two saved club-site captures.

Additive file. It does NOT change slate_20261115.json, whose sha256 is pinned by other owners' result files.
Join key to the slate: event_id + team + normalized player name.

Run (absolute paths):
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I /.../slate/tools/build_club_injuries.py \
     --slate /.../slate/slate_20261115.json \
     --chiefs-dir /.../slate/inputs/chiefs-injury.20261115T072459Z \
     --steelers-dir /.../slate/inputs/steelers-matchup.20261115T072500Z \
     --out /.../slate/slate_20261115_club_injuries.json

Rules (same as build_slate.py): stdlib only, no network, nothing from memory. A value that cannot be read from
a saved page is left None or listed in `missing`. Evidence labels: known = read from a cited page;
derived = a join or comparison computed here from known values; unknown = absent or the sources conflict.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TEAM_HEADERS = {"Kansas City Chiefs": "KC", "Atlanta Falcons": "ATL"}
PRACTICE = {
    "DNP": "Did not participate in practice",
    "LP": "Limited participation in practice",
    "FP": "Full participation in practice",
}
ENTRY = re.compile(r"^(?P<pos>[A-Z]{1,3}) (?P<name>.+?) - (?P<inj>.+?)(?: - (?P<prac>DNP|LP|FP))?(?: \|)?$")
GAME = re.compile(r"^\|? ?Game Status: (?P<g>.+?)\s*$")
SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v"}
LEGEND = {
    "known": "read from a cited source",
    "derived": "join or comparison computed by this builder from known values; formula stated",
    "unknown": "missing or sources conflict",
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_name(name):
    s = name.lower().replace("*", "")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return " ".join(t for t in s.split() if t not in SUFFIX)


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f]


def parse_chiefs(lines):
    """Return (entries, notes). entries: dict team -> day -> list of rows in page order."""
    out, team, day, last, notes = {}, None, None, None, []
    printed = {}
    started = False
    for raw in lines:
        t = raw.strip()
        if not t:
            continue
        if t in TEAM_HEADERS:
            team, day, last, started = TEAM_HEADERS[t], None, None, True
            out.setdefault(team, {})
            continue
        if t.startswith("Published:") or t.startswith("Updated:"):
            printed[t.split(":", 1)[0].lower()] = t.split(":", 1)[1].strip()
            continue
        if not started:
            continue
        if t == "Practice Status":
            break
        if t in DAYS:
            day, last = t, None
            out[team].setdefault(day, [])
            continue
        if day is None:
            continue
        m = GAME.match(t)
        if m and last is not None:
            g = m.group("g")
            last["game_status_printed"] = g
            last["game_status"] = None if g == "--" else g
            continue
        m = ENTRY.match(t)
        if m:
            row = {
                "position": m.group("pos"),
                "player_printed": m.group("name"),
                "player": m.group("name").replace("*", "").strip(),
                "injury_printed": m.group("inj"),
                "practice_code": m.group("prac"),
                "game_status_printed": None,
                "game_status": None,
            }
            out[team][day].append(row)
            last = row
    return out, printed


def newest_day(by_day):
    have = [d for d in DAYS if by_day.get(d)]
    return have[-1] if have else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", required=True)
    ap.add_argument("--chiefs-dir", required=True)
    ap.add_argument("--steelers-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--facts", required=True, help="JSON file of hand-entered matchup facts (see tools/club_matchup_facts_20261115.json)")
    a = ap.parse_args(argv)

    slate = json.load(open(a.slate, encoding="utf-8"))
    slate_sha = sha(a.slate)
    games = {frozenset((g["home"], g["away"])): g for g in slate["games"]}

    sources, problems = [], []

    def source(sid, role, d):
        meta = json.load(open(os.path.join(d, "source.json"), encoding="utf-8"))
        html = os.path.join(d, "source.html")
        vis = os.path.join(d, "visible.txt")
        hs = sha(html)
        sources.append({
            "id": sid, "role": role, "url": meta["source_url"], "retrieved_utc": meta["retrieved_utc"],
            "http_status": meta["status"], "raw_sha256_recorded": meta["raw_sha256"],
            "source_html_sha256": hs, "recorded_hash_matches_source_html": hs == meta["raw_sha256"],
            "visible_txt_sha256": sha(vis), "local_dir": d,
        })
        if hs != meta["raw_sha256"]:
            problems.append("%s: source.html sha256 differs from the recorded raw_sha256" % sid)
        return meta, vis

    cmeta, cvis = source("CL1", "chiefs.com Week 10 injury report (Chiefs Public Relations)", a.chiefs_dir)
    smeta, svis = source("CL2", "steelers.com Matt's Stats Week 10 at Bengals (matchup article, no injury table)", a.steelers_dir)

    entries, printed = parse_chiefs(read_lines(cvis))
    game_kc = games[frozenset(("KC", "ATL"))]
    game_pit = games[frozenset(("PIT", "CIN"))]

    # slate lookup by team + normalized name
    slate_rows = {}
    for r in game_kc["injuries"]:
        slate_rows[(r["team"], norm_name(r["player"]))] = r

    club_reports, drops, summary = [], [], {"rows": 0, "agree": 0, "differs": 0, "club_only": 0, "club_no_designation": 0}
    for team in ("KC", "ATL"):
        by_day = entries.get(team, {})
        latest = newest_day(by_day)
        if latest is None:
            problems.append("no rows parsed for %s" % team)
            continue
        history = {}
        for d in DAYS:
            for r in by_day.get(d, []):
                history.setdefault(norm_name(r["player"]), []).append({
                    "day": d, "practice": r["practice_code"], "game_status": r["game_status"],
                    "injury": r["injury_printed"]})
        rows = []
        for r in by_day[latest]:
            key = norm_name(r["player"])
            sr = slate_rows.get((team, key))
            club_gs = r["game_status"]
            cmp_ = {"slate_row_found": sr is not None}
            if sr is None:
                cmp_["relation"] = "club_only"
                summary["club_only"] += 1
            else:
                st = {
                    "nfl_com_game_status": (sr.get("nfl_com") or {}).get("game_status"),
                    "codex_health_status": (sr.get("codex_health") or {}).get("status"),
                    "espn_status": (sr.get("espn") or {}).get("status"),
                }
                cmp_.update(st)
                other = {v for v in st.values() if v}
                if club_gs is None:
                    cmp_["relation"] = "club_no_designation"
                    summary["club_no_designation"] += 1
                elif other and other == {club_gs}:
                    cmp_["relation"] = "agrees"
                    summary["agree"] += 1
                else:
                    cmp_["relation"] = "differs"
                    summary["differs"] += 1
            rows.append({
                "team": team,
                "player": r["player"],
                "player_printed": r["player_printed"],
                "position": r["position"],
                "injury": r["injury_printed"],
                "report_day": latest,
                "practice_code": r["practice_code"],
                "practice_status": PRACTICE.get(r["practice_code"]),
                "game_status": club_gs,
                "game_status_printed": r["game_status_printed"],
                "label": "known",
                "source_id": "CL1",
                "week_history_newest_first": list(reversed(history[key])),
                "slate_comparison": cmp_,
                "slate_comparison_label": "derived (join on event_id + team + normalized name; compare game_status text)",
            })
            summary["rows"] += 1
        # players on an earlier day but absent from the newest day's list
        for key, hist in history.items():
            if hist[-1]["day"] != latest:
                drops.append({"team": team, "player_normalized": key, "last_listed_day": hist[-1]["day"],
                              "last_listed": hist[-1], "newest_report_day": latest, "label": "derived",
                              "note": "listed on an earlier day, not on the newest day's list; the page does not say why"})
        club_reports.append({
            "team": team,
            "event_id": game_kc["event_id"],
            "newest_report_day": latest,
            "days_listed": [d for d in DAYS if by_day.get(d)],
            "rows": rows,
        })

    # facts file: hand-entered from visible.txt, each verified against the saved text
    facts_doc = json.load(open(a.facts, encoding="utf-8"))
    vis_text = " ".join(" ".join(read_lines(svis)).split())
    lines_sv = read_lines(svis)
    facts = []
    for f in facts_doc["facts"]:
        anchor = " ".join(f["anchor"].split())
        found = anchor in vis_text
        if not found:
            problems.append("fact %s: anchor not found in visible.txt" % f["id"])
        ln = next((i + 1 for i, x in enumerate(lines_sv) if " ".join(f["anchor"].split()[:4]) in " ".join(x.split())), None)
        g = {k: v for k, v in f.items() if k not in ("anchor", "rf")}
        if f.get("rf"):
            rf = f["rf"]
            g["recent_form"] = {
                "n": rf["n"], "hits": rf["hits"], "denominator": rf["denominator"],
                "season": str(slate["season"]),
                "unit": "games as the article words it",
                "window_basis": "the article says 'games' or 'weeks'; it does not say team games or the player's own appearances",
                "line_based": False,
                "meets_player_appearance_rule": "unknown",
            }
        g.update({"label": "known", "source_id": "CL2", "anchor_found_in_visible_txt": found, "visible_txt_line": ln,
                  "verification": "club-stated, not independently checked against game logs"})
        facts.append(g)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "built_utc": now,
        "slate_date": slate["slate_date"],
        "season": slate["season"],
        "purpose": "Official club-site injury rows and a club matchup article for two Nov 15 games, as an ADDITIVE file. "
                   "Paper and advisory only.",
        "relationship_to_slate": {
            "slate_file": "nfl/slate/slate_20261115.json",
            "slate_sha256": slate_sha,
            "rule": "The slate file is not edited: other owners' result files pin its sha256. Readers join on event_id + team + normalized player name.",
        },
        "label_legend": LEGEND,
        "sources": sources,
        "club_reports": club_reports,
        "club_report_printed_timestamps": {
            "published": printed.get("published"), "updated": printed.get("updated"),
            "note": "Printed by the page with no time zone, and 'Updated' is earlier than 'Published'. "
                    "Treat the retrieval time as the as-of time. The Chiefs report is the Saturday list; the Falcons list on the page stops at Friday.",
        },
        "dropped_from_newest_list": drops,
        "comparison_summary": summary,
        "matchup_game": {
            "event_id": game_pit["event_id"], "home": game_pit["home"], "away": game_pit["away"],
            "kickoff_utc": game_pit["kickoff_utc"],
            "article_date_printed": "Nov 12, 2026 at 10:00 AM",
            "article_note": "A club writer's pregame stat article. It has no injury table, so it yields no injury rows.",
            "source_inconsistency": "The article says the first meeting was at Acrisure Stadium, and also places Warren's 127 rushing yards "
                                     "'in Cincinnati'. The venue is not carried here.",
        },
        "matchup_facts": facts,
        "recent_form_rule": "Standing rule: last-5/last-10 means a player's consecutive current-season appearances, never padded with 2025. "
                            "Facts below that carry recent_form state n, season and the denominator exactly as the article gives them; "
                            "none is line-based, and none is a player-appearance window unless the article says so (meets_player_appearance_rule).",
        "missing": [
            "Falcons Saturday report: the page stops at Friday for ATL.",
            "Steelers and Bengals official injury tables: no club report was captured for PIT@CIN (NFL.com rows already in the slate cover them).",
            "Final inactives: released about 90 minutes before each kickoff; every Questionable and Doubtful status is still open.",
            "Meaning of the asterisk on Omarr Norman-Lott and of NIR: the page prints them without a definition.",
        ],
        "problems": problems,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({"out": a.out, "rows": summary, "facts": len(facts), "drops": len(drops), "problems": problems}, indent=1))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
