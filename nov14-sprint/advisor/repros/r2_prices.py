"""Read-only repro: map each call to the exact contract in the shared capture; break-even and margin removal. Writes nothing."""
import json
from statistics import median
CAP = "/Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json"
SEL = "/Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl/slate/results/sunday_20261115_selections.json"
cap = json.load(open(CAP))
dec = lambda p: 1 + (p / 100 if p > 0 else 100 / abs(p))
imp = lambda p: 1 / dec(p)
fair = lambda a, b: imp(a) / (imp(a) + imp(b))
print("captured_utc", cap["captured_utc"], "books_requested", cap["books_requested"])
titles = {}
for coll in ("games", "event_odds"):
    for e in cap[coll]:
        for b in e["bookmakers"]:
            titles[b["key"]] = b.get("title")
print("book keys -> titles", titles)

def find(coll, team_pair):
    for e in cap[coll]:
        if {e["home_team"], e["away_team"]} == team_pair:
            return e
kc = find("games", {"Kansas City Chiefs", "Atlanta Falcons"})
print("\nKC@ATL id", kc["id"], kc["away_team"], "at", kc["home_team"], kc["commence_time"])
rows = []
for b in kc["bookmakers"]:
    for m in b["markets"]:
        if m["key"] == "h2h":
            o = {x["name"]: x["price"] for x in m["outcomes"]}
            k, a = o["Kansas City Chiefs"], o["Atlanta Falcons"]
            rows.append((b["key"], k, a, fair(k, a), m.get("last_update")))
for r in sorted(rows, key=lambda r: -dec(r[1])):
    print("  %-10s KC %+d ATL %+d  no-vig KC %.4f  overround %.4f  upd %s" % (r[0], r[1], r[2], r[3], imp(r[1]) + imp(r[2]) - 1, r[4]))
best = max(rows, key=lambda r: dec(r[1]))
peers = [r[3] for r in rows if r[0] != best[0]]
print("  best", best[0], best[1], "break-even %.5f (=%d/%d)" % (imp(best[1]), abs(best[1]), abs(best[1]) + 100))
print("  median 4 peers (engine market_probability) %.5f" % median(peers), " median all 5 (consensus_including_offer) %.5f" % median([r[3] for r in rows]))
print("  return/unit at peer median %.5f" % (median(peers) * dec(best[1]) - 1))
print("  fair American at peer median %.1f" % (-100 * median(peers) / (1 - median(peers))))

pc = find("event_odds", {"Pittsburgh Steelers", "Cincinnati Bengals"})
print("\nPIT@CIN event id", pc["id"], pc["commence_time"])
names = set()
for b in pc["bookmakers"]:
    for m in b["markets"]:
        for x in m["outcomes"]:
            d = x.get("description") or ""
            if "Warren" in d or "Dowdle" in d:
                names.add((m["key"], d))
            if m["key"] == "player_reception_yds" and d == "Jaylen Warren":
                print("  %-10s %-6s %5s %+d  upd %s" % (b["key"], x["name"], x["point"], x["price"], m.get("last_update")))
print("  name variants seen:", sorted(names))
wl = {}
for b in pc["bookmakers"]:
    for m in b["markets"]:
        if m["key"] == "player_reception_yds":
            o = {(x["name"], x["point"]): x["price"] for x in m["outcomes"] if x.get("description") == "Jaylen Warren"}
            for (s, pt), pr in o.items():
                if s == "Over" and ("Under", pt) in o:
                    wl[b["key"]] = (pt, pr, o[("Under", pt)], fair(pr, o[("Under", pt)]))
for k, v in sorted(wl.items(), key=lambda kv: kv[1][0]):
    print("  %-10s line %.1f over %+d under %+d no-vig over %.4f" % (k, *v))
print("  BetMGM over -115 break-even %.5f (=115/215), return at 0.50 %.5f" % (imp(-115), 0.5 * dec(-115) - 1))
print("  peer lines all above 22.5:", all(v[0] > 22.5 for k, v in wl.items() if k != "betmgm"), " median peer line", median([v[0] for k, v in wl.items() if k != "betmgm"]))

sel = json.load(open(SEL))
print("\nselections.json calls vs capture:")
for c in sel.get("selections", sel.get("calls", [])):
    print("  ", {k: c.get(k) for k in ("id", "book", "price", "minimum_price", "point", "period", "market", "subject", "outcome", "side", "market_probability", "break_even", "other_two_sided_books", "condition")})
    print("   health:", {k: (c.get("health") or {}).get(k) for k in ("report_status", "player_availability", "official_inactives_verified", "inactives_expected_utc")})
