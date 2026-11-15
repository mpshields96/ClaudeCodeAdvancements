"""Read-only acceptance check for the G2/G6 supplement on the product surfaces.

It reads the review evidence file, the selections the card uses, the issued card,
the saved sources and the saved page, and re-derives every figure it can.

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B <this file>
Writes nothing. Imports no engine or view module. No network.
"""
import csv
import gzip
import hashlib
import json
import os

N = os.path.expanduser("~/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl")
S = N + "/slate"
LIVE = os.path.expanduser("~/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live")
WARREN = "48e497c230e6c9afcb3b600091d28e17:full_game:player_reception_yds:Jaylen%20Warren:Over:22.5"
results = []


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load(path):
    with open(path) as fh:
        return json.load(fh)


def check(name, ok, detail=""):
    results.append(ok)
    print("   ", "PASS" if ok else "FAIL", name, detail)


ev = load(S + "/results/sunday_20261115_review_evidence.json")
sel = load(S + "/results/sunday_20261115_selections.json")
# The view reads the packaged folder when it exists, else the live folder.
L = S + "/release_data" if os.path.isdir(S + "/release_data") else LIVE
card = load(L + "/Sunday_Card.json")
dec = load(L + "/Final_Decisions.json")
cap = sha(L + "/sunday-odds.json")

print("1. Binding to the issued card (the view drops the evidence if these differ)")
check("capture digest = decisions = card = evidence",
      cap == dec["capture_sha256"] == card["snapshot_sha256"] == ev["capture_sha256"], cap[:16])
check("card issued_utc = evidence issued_utc", card["issued_utc"][:19] == ev["issued_utc"][:19], ev["issued_utc"])
check("selections capture and decided time match the card",
      sel["capture_sha256"] == card["snapshot_sha256"] and sel["decided_utc"][:19] == card["issued_utc"][:19])
ids = [c["id"] for c in sel["calls"]]
check("evidence is keyed on the exact original Warren call id", list(ev["by_call"]) == [WARREN] and WARREN in ids)
w = ev["by_call"][WARREN]

print("2. Week 8 appearance")
wk = w["week_8"]
check("evidence: 2026-11-01 vs Browns, 17 rushes for 143, 1 catch for 0",
      (wk["date"], wk["rush_attempts"], wk["player_rush_yds"], wk["receptions"], wk["player_reception_yds"])
      == ("2026-11-01", 17, 143, 1, 0))
src = w["appearance_source"]
check("saved game log hash", sha(src["saved_file"]) == src["saved_file_sha256"], src["saved_file_sha256"][:16])
logs = load(src["saved_file"])
g = logs["logs"][logs["players"]["Jaylen Warren"]["log_url"]]
row = [r for r in g["games"] if r["date"] == "2026-11-01"]
v = row[0]["values"] if row else []
check("saved log row: ATT 17, rush YDS 143, REC 1, rec YDS 0",
      bool(v) and (v[0], v[1], v[5], v[6]) == ("17", "143", "1", "0"), v)
games = {r["game_id"]: r for r in csv.DictReader(open(N + "/data/raw/games.csv"))}
gr = games.get(wk["game_id"], {})
check("nflverse game: CLE 6 at PIT 27, home QB Aaron Rodgers",
      (gr.get("away_score"), gr.get("home_score"), gr.get("home_qb_name")) == ("6", "27", "Aaron Rodgers"))
r5 = w["recent_at_22_5"]
check("last 5 = 4/5 and last 10 = 7/8 over 22.5",
      sum(y > 22.5 for y in r5["last_5"]["yards"]) == 4 and len(r5["last_5"]["yards"]) == 5
      and sum(y > 22.5 for y in r5["last_10"]["yards"]) == 7 and len(r5["last_10"]["yards"]) == 8)
lw = [r["values"][6] for r in sorted(g["games"], key=lambda r: r["date"], reverse=True)]
check("last-10 yards equal the saved log, newest first", [int(x) for x in lw] == r5["last_10"]["yards"], lw)

print("3. Freiermuth and Harmon")
names = {p["player"]: p for p in w["players"]}
check("both named Questionable with causes",
      names.get("Pat Freiermuth", {}).get("status") == "Questionable"
      and names.get("Derrick Harmon", {}).get("status") == "Questionable", {k: names[k]["cause"] for k in names})
sf = w["players"][0]["saved_file"]
man = load(os.path.join(os.path.dirname(sf), "MANIFEST.json"))
check("saved ESPN summary hash is in its MANIFEST", sha(sf) in json.dumps(man), sha(sf)[:16])
summ = json.dumps(load(sf))
check("saved ESPN summary names both players", "Freiermuth" in summ and "Harmon" in summ)
for k in ("team_input",):
    check("team input hash", sha(w[k]["path"]) == w[k]["sha256"])
check("props input hash", sha(ev["props_input"]["path"]) == ev["props_input"]["sha256"])

print("4. Afternoon first-half arrays (recounted from the saved play-by-play)")
late = ev["by_window"]["late"]
check("pbp saved file hash", sha(late["saved_file"]) == late["sha256"], late["sha256"][:16])
half = {}
with gzip.open(late["saved_file"], "rt") as fh:
    for r in csv.DictReader(fh):
        if r["season_type"] != "REG" or r["qtr"] not in ("1", "2") or int(r["week"]) > 9:
            continue
        pid = float(r["play_id"])
        if r["game_id"] not in half or pid > half[r["game_id"]][0]:
            half[r["game_id"]] = (pid, r["home_team"], r["away_team"],
                                  int(float(r["total_home_score"] or 0)), int(float(r["total_away_score"] or 0)))
ari, lar = [], []
for gid, (_, h, a, hs, as_) in sorted(half.items()):
    if "ARI" in (h, a):
        ari.append((gid, hs if h == "ARI" else as_))
    if "LA" in (h, a):
        lar.append((gid, as_ if h == "LA" else hs))
ev_ari = [(x["game_id"], x["points"]) for x in late["arizona_points_scored"]]
ev_lar = [(x["game_id"], x["points"]) for x in late["rams_opponent_points"]]
check("Arizona: 9 games, same values as the evidence", len(ari) == 9 and sorted(ari) == sorted(ev_ari), [p for _, p in ari])
check("Rams allowed: 9 games, same values as the evidence", len(lar) == 9 and sorted(lar) == sorted(ev_lar), [p for _, p in lar])
check("under 6.5: Arizona 4/9, Rams opponents 3/9",
      sum(p < 6.5 for _, p in ari) == 4 and sum(p < 6.5 for _, p in lar) == 3)

print("5. Saved page shows the supplement")
page = open(S + "/Sunday NFL.html").read()
check("Warren display text", w["display"] in page)
check("Week 8 appearance text", w["appearance_display"] in page)
check("first-half display text", late["display"] in page)
check("Arizona points list", "Arizona points: " + ", ".join(str(p) for _, p in ev_ari) in page)
print("    note: the page lists Arizona's nine values; the Rams' nine are in the evidence file only.")

print("TOTAL", sum(results), "of", len(results), "checks pass")
