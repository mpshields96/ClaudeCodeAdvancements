"""Read-only repro for the final-freeze second pass (M5, G2, G6).

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B <this file>
Writes nothing. Imports no engine module.
"""
import hashlib
import json
import os

N = "/Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl"
S = N + "/slate"


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load(path):
    with open(path) as fh:
        return json.load(fh)


fp = load(S + "/frozen_picker.json")
print("1. freeze", fp["frozen_utc"], "rules", fp["rules_sha256"][:16])
for name, want in sorted(fp["code_sha256"].items()):
    got = sha(S + "/" + name)
    print("   ", name, "frozen", want[:16], "now", got[:16], "MATCH" if got == want else "DIFFERENT")

sel = load(S + "/results/sunday_20261115_selections.json")
print("   run", sel["run_utc"], "decided", sel["decided_utc"], "tickets", len(sel["tickets"]))
print("   first kickoff 2026-11-15T14:30:00Z; run before it:", sel["run_utc"] < "2026-11-15T14:30:00Z")

print("2. saved club pages")
for d in ("chiefs-injury.20261115T072459Z", "steelers-matchup.20261115T072500Z"):
    meta = load(S + "/inputs/" + d + "/source.json")
    got = sha(S + "/inputs/" + d + "/source.html")
    print("   ", d, meta["status"], meta["retrieved_utc"], "sha", "MATCH" if got == meta["raw_sha256"] else "DIFFERENT")
vis = open(S + "/inputs/chiefs-injury.20261115T072459Z/visible.txt").read()
i = vis.find("Kenneth Walker")
print("    chiefs Saturday text near Walker:", " ".join(vis[i:i + 160].split()))

print("3. evidence items per call: label, retrieved_utc, saved copy")
for c in sel["calls"]:
    print("   ", c["subject"] or c["book"] + " " + c["market"])
    for e in c["evidence"]:
        print("      ", e["kind"], e["label"], "retrieved:", e.get("retrieved_utc", "-"), "saved:", e.get("saved_link", "-"))
    h = c["health"]
    print("       health", h["report_status"], h["player_availability"], "inactives verified", h["official_inactives_verified"], h["inactives_expected_utc"])

w = sel["calls"][1]
ra = w["recent_appearances"]
vals = [e["value"] for e in ra["entries"]]
line = ra["current_line"]
print("4. Warren", vals, "line", line)
print("    last5 over", sum(v > line for v in vals[-5:]), "/", len(vals[-5:]), "| last10 over", sum(v > line for v in vals[-10:]), "/", len(vals[-10:]))
print("    at then-posted lines", sum(e["value"] > e["prior_line"] for e in ra["entries"]), "/", len(ra["entries"]),
      "| books and times verified:", ra["historical_books_and_quoted_times_verified"])
print("    game log source", ra["source_url"], "| retrieved_utc:", ra.get("retrieved_utc", "MISSING"))
print("    dates", [e["date"] for e in ra["entries"]])

slate = load(S + "/slate_20261115.json")
card = open(N + "/BEST_BETS_SUN_NOV15.md").read()
print("5. open PIT/CIN designations in slate, and whether the card names them")
for g in slate["games"]:
    if "CIN" in (g.get("home"), g.get("away")):
        for inj in g["injuries"]:
            if inj["status"] in ("Questionable", "Doubtful"):
                last = inj["player"].split()[-1]
                print("   ", inj["team"], inj["player"], inj["position"], inj["status"], "| on card:", last in card)
print("6. afternoon note:", sel["window_notes"]["late"])
print("   afternoon note has a source field:", any(k in sel for k in ("window_sources", "late_sources")))
