#!/usr/bin/env python3
"""Demo of the postgame intake on SAVED, real, completed pre-Sunday results, against a scratch journal.

Nothing here touches experiment/data/ or the network. The scratch journal lives in a new temp dir.

Real, saved inputs (read only):
  * nov14-sprint/nfl/real/inputs/nfl-public-lines.20261114T225342Z.json  (Codex's ESPN public capture;
    Washington Commanders at New York Giants, Nov 12, STATUS_FINAL 24-21, no halftime in the file)
  * nov14-sprint/nfl/data/raw/games.csv, row 2026_05_IND_PIT (Colts 22 at Steelers 34, Oct 11), transcribed
    here into a manual intake file with the CSV's sha256 as provenance
  * nov14-sprint/nfl/slate/tools/official_player_logs_20261115.json  (NFL.com game logs; both Warrens, week 5)

DEMO FIXTURE (invented): the two pregame price captures that give the scratch journal something to grade.
Their lines and -110 prices are made up for wiring only. They are not real quotes and not picks.

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B demo.py [--keep]
Writes postgame/DEMO_RESULT.json (the CLI's JSON summary for both runs, plus how each fixture bet grades).
"""
import contextlib
import csv
import io
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
import postgame as P  # noqa: E402

NFL = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ARCHIVE = os.path.join(NFL, "real", "inputs", "nfl-public-lines.20261114T225342Z.json")
GAMES_CSV = os.path.join(NFL, "data", "raw", "games.csv")
LOGS = os.path.join(NFL, "slate", "tools", "official_player_logs_20261115.json")
TEAMS = {"IND": "Indianapolis Colts", "PIT": "Pittsburgh Steelers"}


def ou(key, point, player=""):
    outs = [{"name": s, "price": -110, "point": point} for s in ("Over", "Under")]
    for o in outs:
        if player:
            o["description"] = player
    return {"key": key, "outcomes": outs}


def h2h(home, away):
    return {"key": "h2h", "outcomes": [{"name": home, "price": -110}, {"name": away, "price": -110}]}


def fixture(ev_id, home, away, kickoff, captured, markets):
    quote = J.stamp(J.parse_utc(captured) - __import__("datetime").timedelta(minutes=5))
    for m in markets:
        m["last_update"] = quote
    return {"DEMO_FIXTURE": "invented lines and prices for wiring only; not real quotes, not picks",
            "captured_utc": captured,
            "games": [{"id": ev_id, "commence_time": kickoff, "home_team": home, "away_team": away,
                       "bookmakers": [{"key": "demo_fixture", "last_update": quote, "markets": markets}]}]}


def transcribe_ind_pit(out_path):
    with open(GAMES_CSV, newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("game_id") == "2026_05_IND_PIT"]
    if len(rows) != 1:
        raise SystemExit("games.csv has %d rows for 2026_05_IND_PIT; demo stopped" % len(rows))
    r = rows[0]
    sha = J.sha256_file(GAMES_CSV)
    doc = {"captured_utc": J.stamp(J.utc_now()),
           "note": "Transcribed by demo.py from games.csv row 2026_05_IND_PIT (espn %s). No halftime column." % r["espn"],
           "finals": [{"home_team": TEAMS[r["home_team"]], "away_team": TEAMS[r["away_team"]],
                       "kickoff_utc": "2026-10-11T17:00:00Z", "home_score": int(r["home_score"]),
                       "away_score": int(r["away_score"]), "status": "final",
                       "source": "nflverse games.csv row %s, espn %s (games.csv sha256 %s)"
                                 % (r["game_id"], r["espn"], sha[:12])}]}
    with open(out_path, "w") as fh:
        json.dump(doc, fh, indent=1)
    return {"game_id": r["game_id"], "espn": r["espn"], "gameday": r["gameday"], "gametime": r["gametime"],
            "away": r["away_team"], "away_score": r["away_score"], "home": r["home_team"],
            "home_score": r["home_score"], "games_csv_sha256": sha}


def cli_json(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = P.main(args + ["--json"])
    return code, json.loads(out.getvalue())


def main(argv=None):
    keep = "--keep" in (argv or sys.argv[1:])
    for path in (ARCHIVE, GAMES_CSV, LOGS):
        if not os.path.exists(path):
            print("Saved input missing: %s. Demo stopped; nothing fetched." % path)
            return 1
    tmp = tempfile.mkdtemp(prefix="postgame-demo-")
    data, inputs = os.path.join(tmp, "data"), os.path.join(tmp, "inputs")
    os.makedirs(inputs)
    journal = J.Journal(data)
    caps = [
        fixture("401872985", "Pittsburgh Steelers", "Indianapolis Colts", "2026-10-11T17:00:00Z",
                "2026-10-11T16:00:00Z",
                [ou("totals", 44.5), ou("totals_h1", 21.5), h2h("Pittsburgh Steelers", "Indianapolis Colts"),
                 ou("player_rush_yds", 70.5, "Jaylen Warren"), ou("player_reception_yds", 20.5, "Jaylen Warren"),
                 ou("player_receptions", 3.5, "Jaylen Warren"), ou("player_reception_yds", 45.5, "Tyler Warren"),
                 ou("player_rush_yds", 0.5, "Tyler Warren")]),
        fixture("401873052", "New York Giants", "Washington Commanders", "2026-11-13T01:15:00Z",
                "2026-11-13T00:30:00Z",
                [ou("totals", 45.5), ou("totals_h1", 22.5), h2h("New York Giants", "Washington Commanders")]),
    ]
    for i, cap in enumerate(caps):
        path = os.path.join(inputs, "DEMO_FIXTURE_capture_%d.json" % i)
        with open(path, "w") as fh:
            json.dump(cap, fh, indent=1)
        J.import_capture(journal, path, J.parse_utc(cap["captured_utc"]))
    manual = os.path.join(inputs, "manual_ind_pit_from_games_csv.json")
    csv_row = transcribe_ind_pit(manual)
    paths = [ARCHIVE, manual, LOGS]
    before = dict((p, J.sha256_file(p)) for p in paths)
    args = ["--data", data] + paths
    code1, first = cli_json(args)
    print(P.render(first))
    code2, second = cli_json(args)
    state = J.State(journal)
    grades = []
    for r in state.predictions:
        result, detail = J.settle(r, state)
        grades.append({"game": r["game"], "bet": r["label"], "result": result, "detail": detail})
    unchanged = all(J.sha256_file(p) == before[p] for p in paths)
    result = {
        "what": "postgame intake demo on saved real pre-Sunday results; scratch journal in a temp dir",
        "fixture_warning": "the pregame lines and -110 prices are invented for wiring only (DEMO FIXTURE)",
        "real_inputs": [{"path": p, "sha256": before[p]} for p in paths],
        "games_csv_row": csv_row,
        "cli": "/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B postgame/postgame.py --data <tmp>/data "
               + " ".join(os.path.relpath(p, os.path.join(HERE, "..")) for p in paths),
        "first_run": {"exit_code": code1, "summary": first},
        "second_run": {"exit_code": code2, "recorded_finals": len(second["recorded_finals"]),
                       "recorded_players": len(second["recorded_players"]),
                       "already_recorded": second["already_recorded"], "pending": len(second["pending"]),
                       "refused": len(second["refused"])},
        "grades_of_fixture_bets": grades,
        "journal_verify_problems": journal.verify()[1],
        "inputs_unchanged": unchanged,
        "scratch_dir_kept": tmp if keep else None,
    }
    with open(os.path.join(HERE, "DEMO_RESULT.json"), "w") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)
    print("second run: exit %d, %d new, %d already recorded" % (
        code2, len(second["recorded_finals"]) + len(second["recorded_players"]), second["already_recorded"]))
    for g in grades:
        print("  %-8s %s | %s (%s)" % (g["result"], g["game"], g["bet"], g["detail"]))
    print("inputs unchanged: %s; journal verify problems: %s" % (unchanged, result["journal_verify_problems"]))
    if not keep:
        shutil.rmtree(tmp)
    return code1


if __name__ == "__main__":
    sys.exit(main())
