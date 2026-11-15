"""Read-only repro: venue labels (nflverse vs saved ESPN lastFiveGames) and a
pass/fail acceptance check for the open G2 and G6 items.

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B <this file>
Writes nothing. Imports no engine module. No network.
"""
import csv
import json
import os

N = os.path.expanduser("~/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl")
S = N + "/slate"
SUMS = S + "/inputs/espn-summary.20261115T065600Z"

# ESPN uses a few different abbreviations from nflverse.
ALIAS = {"WSH": "WAS", "LAR": "LA", "JAX": "JAX"}


def nv(t):
    return ALIAS.get(t, t)


games = {}
for r in csv.DictReader(open(N + "/data/raw/games.csv")):
    if r["season"] == "2026" and r["home_score"]:
        games[(r["home_team"], r["away_team"], r["gameday"])] = r


def find(team, opp, date):
    """Return (nflverse home team, location) for team vs opp within a day of date."""
    y, m, d = (int(x) for x in date.split("-"))
    hits = []
    for (h, a, g), r in games.items():
        if {h, a} == {team, opp}:
            gy, gm, gd = (int(x) for x in g.split("-"))
            if gy == y and gm == m and abs(gd - d) <= 1:
                hits.append((h, r["location"], g))
    return hits


print("1. Venue: ESPN lastFiveGames atVs against nflverse home_team")
seen = set()
disagree = []
total = 0
for f in sorted(os.listdir(SUMS)):
    if not f.startswith("event_"):
        continue
    d = json.load(open(SUMS + "/" + f))
    for t in d.get("lastFiveGames", []):
        team = nv(t["team"]["abbreviation"])
        for e in t["events"]:
            opp = nv(e["opponent"]["abbreviation"])
            date = e["gameDate"][:10]
            key = (team, opp, date)
            if key in seen:
                continue
            seen.add(key)
            hits = find(team, opp, date)
            if not hits:
                continue
            total += 1
            espn_home = team if e["atVs"] == "vs" else opp
            h, loc, g = hits[0]
            if h != espn_home:
                disagree.append((team, e["atVs"], opp, date, "nflverse home=" + h, loc))
print("   compared", total, "team-games; disagreements", len(disagree))
for row in disagree:
    print("   ", *row)

print("2. Steelers official page (saved 07:25:00Z) on the first PIT-CIN meeting")
vis = open(S + "/inputs/steelers-matchup.20261115T072500Z/visible.txt").read()
for needle in ("first meeting in Cincinnati", "Week 8"):
    i = vis.find(needle)
    print("   ", repr(needle), "found:", i >= 0, "|", " ".join(vis[max(0, i - 60):i + 90].split()) if i >= 0 else "")
wk3 = [r for k, r in games.items() if {k[0], k[1]} == {"PIT", "CIN"}]
for r in wk3:
    print("    nflverse:", r["week"], r["gameday"], r["away_team"], "at", r["home_team"], r["location"], r.get("stadium"))

print("3. Engine-output fields only (historical, superseded by r6_review_evidence.py at 07:52Z)")
print("    The G2/G6 fix landed in results/sunday_20261115_review_evidence.json and Sunday NFL.html,")
print("    not in selections.json or BEST_BETS_SUN_NOV15.md, so FAIL below is expected. Judge acceptance with r6.")
sel = json.load(open(S + "/results/sunday_20261115_selections.json"))
card = open(N + "/BEST_BETS_SUN_NOV15.md").read()
w = [c for c in sel["calls"] if c.get("subject") and "Warren" in c["subject"]][0]
ra = w["recent_appearances"]
g2a = bool(ra.get("retrieved_utc")) and bool(ra.get("saved_link") or ra.get("raw_sha256"))
late_keys = [k for k in sel if "source" in k and "window" in k] + [k for k in sel.get("window_notes", {}) if "source" in k]
g2b = bool(late_keys)
named = {p: (p in card and p in json.dumps(w)) for p in ("Freiermuth", "Harmon")}
g6 = all(named.values())
print("    G2a Warren game log has retrieved_utc and a saved copy or hash:", "PASS" if g2a else "FAIL")
print("    G2b afternoon pass figures carry a source field:", "PASS" if g2b else "FAIL", late_keys)
print("    G6 Warren call and card name Freiermuth and Harmon:", "PASS" if g6 else "FAIL", named)
