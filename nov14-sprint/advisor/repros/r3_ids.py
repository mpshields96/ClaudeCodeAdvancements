"""Read-only repro: contract-ID identity on the frozen engine (selection_markets.py, unmodified).
Synthetic capture in memory only. sys.dont_write_bytecode keeps __pycache__ out of slate/. Writes nothing."""
import sys, json, hashlib
sys.dont_write_bytecode = True
SLATE = "/Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl/slate"
print("selection_markets sha256", hashlib.sha256(open(SLATE + "/selection_markets.py", "rb").read()).hexdigest()[:16])
sys.path.insert(0, SLATE)
import selection_markets as sm

E, OBS, UPD, KICK = "E1", "2026-11-15T06:55:00Z", "2026-11-15T06:54:00Z", "2026-11-15T18:00:00Z"
def mk(key, outs):
    return {"key": key, "last_update": UPD, "outcomes": outs}
O = lambda n, pt, pr, d=None: dict(name=n, point=pt, price=pr, **({"description": d} if d else {}))
book = {"key": "betmgm", "title": "BetMGM", "last_update": UPD, "markets": [
    mk("player_reception_yds", [O("Over", 22.5, -115, "Player A"), O("Under", 22.5, -115, "Player A"),
                                O("Over", 22.5, -120, "Player B"), O("Under", 22.5, -110, "Player B")]),
    mk("totals", [O("Over", 44.5, -110), O("Under", 44.5, -110)]),
    mk("totals_h1", [O("Over", 44.5, -105), O("Under", 44.5, -115)]),
    mk("team_totals", [O("Over", 20.5, -110, "Home Team"), O("Under", 20.5, -110, "Home Team"),
                       O("Over", 20.5, -125, "Away Team"), O("Under", 20.5, +105, "Away Team")]),
    mk("team_totals_h1", [O("Over", 20.5, -110, "Home Team"), O("Under", 20.5, -110, "Home Team")]),
]}
event = {"id": E, "commence_time": KICK, "home_team": "Home Team", "away_team": "Away Team", "bookmakers": [book]}
capture = {"captured_utc": OBS, "observations": [{"endpoint": "events/%s/odds" % E, "observed_utc": OBS}],
           "games": [], "event_odds": [event]}
groups, stats, skipped = sm.collect(capture, None, (), {E: True}, "2026-11-15T07:00:00Z")
print("collect: %d groups, skipped %s" % (len(groups), skipped))
ids = [g["id"] for g in groups]
print("all ids distinct:", len(ids) == len(set(ids)))
def one(**kw):
    m = [g for g in groups if all(g[k] == v for k, v in kw.items())]
    assert len(m) == 1, (kw, len(m)); return m[0]
cases = [
    ("two players, same game/market/side/line",
     dict(provider_market="player_reception_yds", subject="Player A", outcome="Over", line=22.5),
     dict(provider_market="player_reception_yds", subject="Player B", outcome="Over", line=22.5)),
    ("totals vs totals_h1, same line/side",
     dict(provider_market="totals", outcome="Over", line=44.5), dict(provider_market="totals_h1", outcome="Over", line=44.5)),
    ("home vs away team_totals, same line/side",
     dict(provider_market="team_totals", subject="Home Team", outcome="Over"), dict(provider_market="team_totals", subject="Away Team", outcome="Over")),
    ("team_totals vs team_totals_h1, same team/line/side",
     dict(provider_market="team_totals", subject="Home Team", outcome="Over"), dict(provider_market="team_totals_h1", subject="Home Team", outcome="Over")),
]
for name, a, b in cases:
    ga, gb = one(**a), one(**b)
    qa, qb = ga["quotes"]["betmgm"], gb["quotes"]["betmgm"]
    print("%-52s distinct=%s  A %+d (opp %+d, no-vig %.4f) period=%s | B %+d (opp %+d, no-vig %.4f) period=%s" % (
        name, ga["id"] != gb["id"], qa["price"], qa["opposite_price"], qa["market_no_vig"], ga["period"],
        qb["price"], qb["opposite_price"], qb["market_no_vig"], gb["period"]))
# Opposite-side pairing must stay within the same subject: Player B Over -120 pairs with Player B Under -110, not Player A.
gb = one(provider_market="player_reception_yds", subject="Player B", outcome="Over", line=22.5)
print("Player B over pairs with its own under:", gb["quotes"]["betmgm"]["opposite_price"] == -110)
# Delimiter injection: a subject containing ':' must not alias another contract.
print("quote() escapes ':' ->", sm.key_for(E, "player_reception_yds", "A:Over", "x", 1.0))
print("line formatting 3 vs 3.0 vs -0.0:", sm.key_for(E, "spreads", "", "T", 3), sm.key_for(E, "spreads", "", "T", 3.0), sm.line_number("-0.0"))
