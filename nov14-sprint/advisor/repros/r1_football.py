"""Read-only repro: re-derive the card's football claims from saved data. Writes nothing."""
import os
import csv, json
ROOT = os.path.expanduser("~/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl")
G = ROOT + "/data/raw/games.csv"
L = ROOT + "/slate/tools/official_player_logs_20261115.json"
rows = [r for r in csv.DictReader(open(G)) if r["season"] == "2026" and r["game_type"] == "REG"]
done = [r for r in rows if r["home_score"] not in ("", "NA")]
print("2026 REG rows:", len(rows), "with scores:", len(done))
wk19 = [r for r in done if int(r["week"]) <= 9]
ties = [r for r in wk19 if r["home_score"] == r["away_score"]]
noml = [r for r in wk19 if r["home_moneyline"] in ("", "NA") or r["away_moneyline"] in ("", "NA")]
print("weeks 1-9 scored:", len(wk19), "ties:", len(ties), [(r["week"], r["away_team"], r["home_team"]) for r in ties],
      "missing ML:", len(noml), [(r["week"], r["away_team"], r["home_team"]) for r in noml])
print("week 10 scored before Sunday:", [(r["gameday"], r["away_team"], r["home_team"]) for r in done if r["week"] == "10"])

def team(t):
    out = []
    for r in sorted(done, key=lambda r: int(r["week"])):
        if t not in (r["home_team"], r["away_team"]):
            continue
        home = r["home_team"] == t
        pf, pa = (int(r["home_score"]), int(r["away_score"])) if home else (int(r["away_score"]), int(r["home_score"]))
        # Neutral-site games (nflverse location == "Neutral") are neither home nor away.
        ha = "N" if r["location"] == "Neutral" else ("H" if home else "A")
        out.append((int(r["week"]), ha, r["away_team"] if home else r["home_team"], pf, pa))
    return out
for t in ("KC", "ATL", "PIT", "CIN"):
    g = team(t)
    w = sum(pf > pa for *_, pf, pa in g); l = sum(pf < pa for *_, pf, pa in g); d = len(g) - w - l
    split = lambda ha: (sum(1 for x in g if x[1] == ha and x[3] > x[4]), sum(1 for x in g if x[1] == ha and x[3] < x[4]))
    last = lambda n: (sum(x[3] > x[4] for x in g[-n:]), len(g[-n:]))
    print(t, "record %d-%d-%d" % (w, l, d), "PF/G %.3f PA/G %.3f" % (sum(x[3] for x in g) / len(g), sum(x[4] for x in g) / len(g)),
          "home W-L", split("H"), "away W-L", split("A"), "last5 wins", last(5), "last10 wins", last(10))
    print("   games:", g)
h2h = [r for r in csv.DictReader(open(G)) if {r["home_team"], r["away_team"]} in ({"KC", "ATL"}, {"PIT", "CIN"}) and r["home_score"] not in ("", "NA")]
for pair in ({"KC", "ATL"}, {"PIT", "CIN"}):
    m = [r for r in h2h if {r["home_team"], r["away_team"]} == pair]
    m.sort(key=lambda r: (int(r["season"]), int(r["week"])))
    print("H2H", sorted(pair), "n=%d" % len(m), "last 5:", [(r["season"], r["week"], r["away_team"], r["away_score"], r["home_team"], r["home_score"]) for r in m[-5:]])

logs = json.load(open(L))
print("logs captured", logs["captured_utc"], "cutoff", logs["cutoff_exclusive"])
for name in ("Jaylen Warren", "Rico Dowdle", "Kenneth Walker III"):
    p = logs["players"].get(name)
    if not p:
        print(name, "NOT IN players"); continue
    lg = logs["logs"].get(p["log_url"])
    print(name, p["team_name"], p["position"], p["roster_status"], "source", lg["source"]["retrieved_utc"], lg["source"]["http_status"])
    print("   headers", lg["headers"])
    for gm in lg["games"]:
        print("  ", gm)
