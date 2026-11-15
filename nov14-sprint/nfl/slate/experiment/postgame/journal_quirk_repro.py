#!/usr/bin/env python3
"""Repro for the journal owner: part-game player props are graded on full-game numbers.

Read-only toward journal.py; everything is written to a new temp dir that is deleted afterwards.
The pregame line and -110 prices are an invented DEMO FIXTURE, not real quotes and not picks.

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B journal_quirk_repro.py
Exit 1 while either quirk is present, 0 once journal.py is fixed.

Quirk A. settle() looks player props up by base market only, so a first-half bet
         (player_rush_yds_h1 Over 30.5) is graded "win" on the player's full-game 101 yards.
Quirk B. record_player_result() stores base_market(market), so a first-half number typed by hand
         (`player-result ... --market player_rush_yds_h1 --value 12`) lands as the FULL-GAME
         player_rush_yds result and then grades the full-game bet (Over 70.5 -> "loss" on 12).

Suggested change in journal.py (owner's call):
  * settle(), player branch: `if per != "game": return "unknown", "%s player props are not graded by
    this tool" % PERIOD_NAMES.get(per, per)` before the lookup.
  * record_player_result(): refuse a market whose period is not "game" (raise JournalError), or key
    the result by (base, period) and look it up the same way in settle().
"""
import datetime
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
for d in (os.path.dirname(HERE), HERE):
    if d not in sys.path:
        sys.path.insert(0, d)

import journal as J  # noqa: E402

UTC = datetime.timezone.utc
KICK = datetime.datetime(2026, 10, 11, 17, 0, tzinfo=UTC)
CAP = KICK - datetime.timedelta(hours=1)
LATER = KICK + datetime.timedelta(hours=6)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ou(key, point, player):
    return {"key": key, "last_update": iso(CAP - datetime.timedelta(minutes=5)),
            "outcomes": [{"name": s, "price": -110, "point": point, "description": player}
                         for s in ("Over", "Under")]}


def grades(journal):
    state = J.State(journal)
    out = {}
    for r in state.predictions:
        if r["identity"]["side"] == "Over":
            out[r["identity"]["market"]] = J.settle(r, state)
    return out


def main():
    tmp = tempfile.mkdtemp(prefix="journal-quirk-")
    try:
        journal = J.Journal(os.path.join(tmp, "data"))
        cap = {"DEMO_FIXTURE": "invented line and prices for this repro only",
               "captured_utc": iso(CAP),
               "games": [{"id": "E-PIT", "commence_time": iso(KICK), "home_team": "Pittsburgh Steelers",
                          "away_team": "Indianapolis Colts",
                          "bookmakers": [{"key": "demo_fixture", "last_update": iso(CAP - datetime.timedelta(minutes=5)),
                                          "markets": [ou("player_rush_yds", 70.5, "Jaylen Warren"),
                                                      ou("player_rush_yds_h1", 30.5, "Jaylen Warren")]}]}]}
        path = os.path.join(tmp, "DEMO_FIXTURE_capture.json")
        with open(path, "w") as fh:
            json.dump(cap, fh)
        J.import_capture(journal, path, CAP)
        J.record_final(journal, "E-PIT", 34, 22, "repro", LATER)

        # A: only the full-game number (101) is recorded; the first-half bet should stay unknown.
        J.record_player_result(journal, "E-PIT", "Jaylen Warren", "player_rush_yds", 101, "repro full game", LATER)
        a = grades(journal)
        quirk_a = a["player_rush_yds_h1"][0] != "unknown"
        print("A  h1 bet with only the full-game 101 recorded: %s (%s)  -> %s"
              % (a["player_rush_yds_h1"][0], a["player_rush_yds_h1"][1], "QUIRK" if quirk_a else "ok"))

        # B: a fresh journal where someone types a first-half number (12) for the h1 market.
        shutil.rmtree(os.path.join(tmp, "data"))
        journal = J.Journal(os.path.join(tmp, "data"))
        J.import_capture(journal, path, CAP)
        J.record_final(journal, "E-PIT", 34, 22, "repro", LATER)
        try:
            J.record_player_result(journal, "E-PIT", "Jaylen Warren", "player_rush_yds_h1", 12,
                                   "repro first half", LATER)
            refused = False
        except J.JournalError as err:
            refused = True
            print("B  first-half number refused: %s  -> ok" % err)
        quirk_b = False
        if not refused:
            stored = J.State(journal).player_results
            keys = sorted(k[2] for k in stored)
            b = grades(journal)
            quirk_b = b["player_rush_yds"][0] != "unknown"
            print("B  first-half 12 typed for player_rush_yds_h1 is stored as %s; full-game bet grades %s (%s)  -> %s"
                  % (keys, b["player_rush_yds"][0], b["player_rush_yds"][1], "QUIRK" if quirk_b else "ok"))
        print("journal.py sha256 %s" % J.sha256_file(J.__file__))
        return 1 if (quirk_a or quirk_b) else 0
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    sys.exit(main())
