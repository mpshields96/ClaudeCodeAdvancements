# Postgame intake

The Sunday scorecard's **Check public finals and player results** action fetches the ESPN NFL scoreboard for due dates and the final box scores needed by the journal. The importer records results through the journal's own interface. Each raw response has its request URL, retrieval time and SHA-256 in the capture manifest.

## Fetch from the scorecard or replay saved files

The button calls `espn_fetch.fetch_and_import(journal_dir, save_root=directory)`. The fetcher selects games whose kickoff was at least 150 minutes ago and checks ESPN's completed status. Its player parser requires the NFL event header, both team identities, exact kickoff, a named athlete and a numeric cell in the matching statistic category. Recorded game and halftime scores must agree across the batch. A missing athlete, missing stat or DNP stays pending. A displayed numeric zero can settle. Separate imports of the same journal serialize the check and append.

To replay captured files without a network request, call `postgame.import_from_public(journal_dir, paths=[...])`. The manual acquisition and offline import use the same result writer. Full-game box-score values apply only to full-game contracts. A period-specific contract requires its own evidence.

- `journal_dir` is the journal's data directory. The live one is `experiment/data/`.
- `paths` is a list of saved capture files. Leave it as `None` to read `experiment/postgame/inbox/*.json`. An empty inbox records nothing and lists everything as pending.
- `now` is a timezone-aware `datetime` that sets the clock. Leave it as `None` for the current UTC time. Tests use it; the button should not.
- `summary["exit_code"]` uses the same codes as the CLI.

CLI:

```
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B \
  nov14-sprint/nfl/slate/experiment/postgame/postgame.py \
  [--data DIR] [--json] [FILE ...]
```

| Argument | Meaning |
|---|---|
| `--data DIR` | The journal data directory. The default is the journal's own default, `experiment/data/`. |
| `--json` | Print the summary as JSON instead of text lines. |
| `FILE ...` | Saved capture files. With none, it reads `postgame/inbox/*.json`. |

| Exit | Meaning |
|---|---|
| 0 | Everything the journal needs is recorded, or already was. |
| 2 | Something was recorded or nothing changed, but at least one item is still PENDING. This is the normal result on game day. |
| 1 | At least one REFUSED item: an unreadable or unknown file, a capture dated after the clock, a "final" claimed too early, or a result that conflicts with the journal. Nothing was written for that item. Other items in the same run may still have been recorded. |

The text output has one line per item: `final: ...`, `player: ...`, `PENDING ...`, `REFUSED ...`, `note: ...`, then `exit N`.

The JSON summary has these keys: `journal_dir`, `now_utc`, `inputs` (path, sha256, shape, captured_utc, games, player_rows), `recorded_finals`, `recorded_players` (each with its source), `already_recorded` (a count), `pending` (event_id, game, item, reason), `refused` (what, reason), `notes` and `exit_code`.

Running it twice is safe. A value that is already recorded and matches counts as `already_recorded`. A value that differs is REFUSED and never overwritten; check it by hand. The journal is append-only and hash-chained, so a wrong recorded result cannot be rewritten here. Take it to the journal owner. `journal.py void` only voids a bet; it does not change a result.

## Files it reads

It detects the shape from the file's contents.

| Shape | Typical producer (not run by this intake) | Gives |
|---|---|---|
| `espn_public_lines` | `nov14-sprint/codex/real-intake/capture_week.py` (Codex), e.g. `nfl/real/inputs/nfl-public-lines.*.json` | finals when `state == "STATUS_FINAL"`; halftime only if the file has `halftime` or `h1_score` |
| `espn_scoreboard` | a saved ESPN scoreboard JSON (`{"events": [...]}`) | finals when `completed` is true, `state` is `post` and `name` is `STATUS_FINAL`; halftime from the first two linescores |
| `espn_boxscore` | ESPN NFL event summary | verified team, athlete and named full-game passing, rushing and receiving statistics |
| `nflcom_game_logs` | `nfl/slate/tools/collect_player_logs.py` | player receiving, rushing and passing numbers per game |
| `manual` | a person or the button's form | finals and player rows typed in, each with a source |

Manual file, for anything the public files lack:

```json
{
  "captured_utc": "2026-11-16T03:00:00Z",
  "finals": [
    {"home_team": "Pittsburgh Steelers", "away_team": "Indianapolis Colts",
     "kickoff_utc": "2026-10-11T17:00:00Z", "home_score": 34, "away_score": 22,
     "h1_home": 17, "h1_away": 10, "status": "final", "finished_utc": "2026-10-11T20:10:00Z",
     "source": "where the numbers came from (page or file)"}
  ],
  "players": [
    {"player": "Jaylen Warren", "team": "Pittsburgh Steelers", "event": "<journal event id>",
     "market": "player_rush_yds", "value": 101, "status": "played",
     "source": "where the number came from"}
  ]
}
```

- Team names must be the journal's full names. A final may give `event` (the journal event id) in place of names. A kickoff, if given, must be within 6 hours of the journal's.
- A player row needs `event`, or exact `home_team` and `away_team`. Its `status` may be `dnp`, `inactive` or `pending`, and any of those keeps the item pending.
- `h1_home`, `h1_away` and `finished_utc` are optional.

## Matching rules

- **Game:** the exact home and away teams and exact kickoff for ESPN scoreboards and box scores. The legacy transcription matcher uses a six-hour tolerance when the source supplies a kickoff. Reversed home and away do not match. Neither does a rematch weeks apart. A capture game that matches more than one journal game is left alone, with a note.
- **Player:** the exact full name (spaces collapsed, case ignored), plus a team in this game, plus this event. The one allowance is the trailing dot of a final Jr, Sr, II, III, IV or V: "Brian Thomas Jr" matches "Brian Thomas Jr.". The suffix itself must be on both sides, so "Travis Etienne Jr." does not match "Travis Etienne", and Jr never matches Sr. Jaylen Warren (PIT) and Tyler Warren (IND) are told apart by team. For NFL.com logs the event is the row whose date is the game's local date and whose opponent and home/away flag fit the journal game. The log's W/L score must also agree with the journal's final.
- **Market:** it uses the journal's base market (`player_reception_yds`, `player_receptions`, `player_rush_yds`, `player_rush_attempts`, `player_pass_yds`, `player_pass_completions`, `player_pass_attempts`, `player_pass_tds`). ESPN uses category and machine-named statistic keys. NFL.com columns come from three exact NFL.com header layouts (receiving first, rushing first, passing). An unknown layout stays pending.

## What stays PENDING (never zero, never a guess)

- A game not final in any file, or no file for it.
- A first-half score the file does not give. Neither `games.csv` nor the saved ESPN lines capture has halftime. ESPN scoreboard linescores do.
- An overtime final whose ESPN status name is not exactly `STATUS_FINAL`. This errs toward waiting. Add it with a manual file.
- Any player result before the game's final score is in the journal.
- A player with no row for the game. That covers a DNP, a stat not yet posted, and a row whose stats are all blank.
- A blank or `-` stat. NFL.com leaves rushing blank for a receiver with no carries. That stays pending, not zero; record a true 0 by hand if the gamebook shows one. A printed `0` is recorded as 0.
- A name on more than one team in the game, a name that is not exact, or two files that disagree. A suffix present on one side only ("Deebo Samuel" vs "Deebo Samuel Sr.") or an alias ("Zonovan Knight" vs "Bam Knight") counts as not exact. Record those by hand.
- An NFL.com logs file whose `cutoff_exclusive` is on or before the game's date. The reason names the cutoff, because such a file cannot hold the game.
- Quarter and second-half periods. The journal does not grade them.

Hand entry uses the journal's own commands:

```
journal.py --data DIR player-result EVENT --player "NAME" --market player_rush_yds --value 0 --source "gamebook ..."
journal.py --data DIR final EVENT --home 34 --away 22 [--h1-home 17 --h1-away 10] --source "..."
```

## What it REFUSES

- A "final" before the journal's earliest possible final, kickoff plus 150 minutes. It checks both the clock now and the file's `finished_utc` (or, without that, its capture time). So a real Sunday settlement cannot happen until the game has actually ended, by status and by time.
- A capture dated after the clock, plus 5 minutes of slack.
- A file it cannot read, or one in an unknown shape.
- A final or halftime score, or a player number, that differs from what the journal already holds.

## Sunday, after the games

1. Get fresh public files saved by their own tools. This intake makes no calls.
   - `collect_player_logs.py` can't produce Sunday's logs yet, for three reasons. It exits after 2026-11-15T14:30Z. Its `CUTOFF = "2026-11-15"` is exclusive. And `--reuse` never refetches a saved log URL, so a reuse run returns the pregame rows. A `--postgame` mode is proposed to its owner, through the coordinator, in the shared note `POSTGAME_LOGS_CUTOFF_0815Z.md`. It writes a new file, refuses `--reuse`, uses cutoff 2026-11-16 and leaves the pregame freeze alone. Until that lands, every player item stays pending with the cutoff named as the reason.
2. Run the button or the CLI with those files against `experiment/data/`.
3. Fill the remaining pending items by hand with `journal.py`, then run `journal.py report` or `grade`.

Dry run against a temp copy of the real journal (`experiment/data/` was only read):

- 12 games need a final. All are on 2026-11-15 local time; the last kicks off at 01:20Z on Nov 16.
- 195 players across 255 player items: 159 `player_reception_yds`, 72 `player_rush_yds`, 24 `player_pass_yds`.
- No first-half and no part-game player items.
- 189 of the 195 players match an NFL.com log by exact name and team in `official_player_logs_20261115.json`.
- The other 6 stay pending; record them by hand:
  - no NFL.com roster match: Cam Sample, Elijah Dotson and Malik Taylor;
  - NFL.com spells the name differently: Travis Etienne Jr. ("Travis Etienne"), Deebo Samuel ("Deebo Samuel Sr.") and Zonovan Knight ("Bam Knight").
- At about 08:02Z I added invented finals for all 12 games to the temp copy and ran it with the current logs file. All 12 finals were recorded. All 255 player items stayed pending, each with the reason "the NFL.com logs file stops before this game (cutoff_exclusive 2026-11-15)".

## Journal quirk (for the journal owner)


`journal_quirk_repro.py` shows both in a temp dir. It exits 1 while either is present and 0 once fixed, and gives the suggested change in its docstring. It was sent to the journal owner (Claude nfl-lead) at about 08:00Z.

```
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B nov14-sprint/nfl/slate/experiment/postgame/journal_quirk_repro.py
```

## Demo

`demo.py` runs on saved, real, completed pre-Sunday results against a scratch journal in a new temp dir, and deletes the dir afterwards unless you pass `--keep`. The pregame lines and -110 prices it puts in the scratch journal are invented, labelled `DEMO_FIXTURE`, so that something can be graded. They are not real quotes and not picks.

```
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B nov14-sprint/nfl/slate/experiment/postgame/demo.py
```

Real inputs (read only, sha256):

- `nfl/real/inputs/nfl-public-lines.20261114T225342Z.json` (206d164be405...): Washington at the Giants, Nov 12, STATUS_FINAL 24-21.
- `nfl/data/raw/games.csv` (44f6ba50a763...), row `2026_05_IND_PIT`: Colts 22 at Steelers 34, Oct 11. Transcribed into a manual file in the temp dir.
- `nfl/slate/tools/official_player_logs_20261115.json` (217b65f973a1...): NFL.com week 5 logs for both Warrens.

Result at 08:01Z (`DEMO_RESULT.json`), exit 2:

- Both finals were recorded.
- Five player numbers were recorded, each matched to the right Warren:
  - Jaylen Warren (PIT): 101 rushing yards, 87 receiving yards, 6 receptions.
  - Tyler Warren (IND): 83 receiving yards, 1 rushing yard.
- Both first-half scores stayed pending, because neither file has halftime.
- The second run found all 7 values already recorded, with 0 new.
- The journal verified clean and the inputs were unchanged.
- The fixture bets graded as expected, and the first-half bets stayed `unknown`.

## Tests

```
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B nov14-sprint/nfl/slate/experiment/postgame/test_postgame.py -v
```

36 tests, all in temp dirs. They cover:

- the two Warrens, aliases, the same name on both teams, DNP, blank stats and a real zero;
- the suffix dot both ways, and a missing or different suffix staying pending;
- a logs file cut off before the game;
- a score that disagrees, the wrong home/away flag, players before the final;
- not final, too early by clock, by capture time and by `finished_utc`, and a future capture;
- halftime missing or added later, conflicts, idempotence, a rematch, reversed teams, an unknown shape;
- exit codes, the empty inbox, only journal files being written, and no network code in the source.

## Provenance

The ESPN reading logic was adapted from `desk_scores.py`, sha256 a931d8ae1cb6f1859a4df1cbeab2cd75857fd7bd6457b1a017b702518bccfdda. Its live fetch was not copied.

## Standing rule for every handoff

Last 5 and last 10 mean a player's consecutive current-season games, measured against today's line.

- Show the available n.
- Never pad with last season.
- Keep the own-line hit rate separate.
- Team L5/L10 is optional.

Paper only: no bets, keys or Odds API, and `odds_feed` is never imported.
