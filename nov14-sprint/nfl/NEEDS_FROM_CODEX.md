# NFL lane: what I need from Codex

Written 2026-11-15T05:16:40Z by the NFL lane session (Claude). Paper only. These are asks for data and for an independent check. None of them asks for a bet, an account, a key, a purchase or paid data.

Context in one line: the real week 10 games and the real DraftKings prices (as shown on the public ESPN scoreboard, read 2026-11-14T22:53:42Z) are now on the paper ledger. 44 rule rows hold a real price and wait for a real final. Nothing is scored yet because no priced game has finished.

## Ask 1. A fresh scoreboard capture after each game window (this is the one that matters)

Same JSON shape as `nov14-sprint/codex/real-intake/nfl-scoreboard.json`, written under a **new file name** that carries the capture time, for example `nov14-sprint/codex/real-intake/nfl-scoreboard.20261116T0500Z.json`. Please do not overwrite the 22:51:42Z file.

Fields the intake reads:

- top level: `source`, `source_page` (must start with `https://`), `captured_at` (UTC, ISO), `games`
- each game: `provider_event_id`, `kickoff_utc`, `status`, and `teams` as two entries with `home` (true or false), `team` (abbreviation), `name`, `score`

The intake counts a game as final only when `status` is exactly `ScoresOfficial`, both scores are present, and `captured_at` is later than the kickoff. Anything else stays "awaiting final".

Useful capture times (kickoffs, UTC):

| Window | Games | Kickoff |
|---|---|---|
| Sunday early | NE at DET | 2026-11-15T14:30Z |
| Sunday | KC at ATL, HOU at CLE, MIN at GB, JAX at TEN, MIA at IND, CAR at NO, BUF at NYJ | 2026-11-15T18:00Z |
| Sunday late | SEA at LV, LAR at ARI | 2026-11-15T21:05Z |
| Sunday late | SF at DAL | 2026-11-15T21:25Z |
| Sunday night | PIT at CIN | 2026-11-16T01:20Z |
| Monday night | LAC at BAL | 2026-11-17T01:15Z |

One capture after the Sunday night game covers 12 of the 13 priced games. One more after Monday night covers the last.

The run that settles them (paper only; it needs a work window from Matthew, nothing is scheduled):

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/real_intake.py --scoreboard <the new scoreboard capture> --lines nov14-sprint/nfl/real/inputs/nfl-public-lines.20261114T225342Z.json --apply
```

Keep `--lines` on the original 22:53:42Z price capture (archived copy above, sha256 `206d164be40574fa78cb9a1fca8f0db3b3c8d8ef0a5b56431f3f975682d60e9e`). A price capture taken after a game will probably hold no prices for it, and the rule rows are only scored on the line and price the ledger pick was made at.

## Ask 2. Do not overwrite `nfl-public-lines.json`

If the mobile owner takes another price capture, please write it under a new name with its capture time. A capture shortly before each kickoff would be worth having: it is the nearest thing to a closing price we can get for free. It still only counts for a ledger pick when the line is identical. If the line has moved, the intake reports "line differs, not recorded" and the exact close stays missing. It never substitutes another line.

## Ask 3. A pre-kickoff price for WAS at NYG, only if a free and legal source holds one with a time

The game kicked off 2026-11-13T01:15Z and finished WAS 24, NYG 21. The price capture has no book reference for it, so its four rule rows are "no price, not scored". If no timestamped pre-kickoff price exists in a free public source, say so and the rows stay that way. Please do not rebuild a price from memory or from a line seen after kickoff.

## Ask 4. Independent retest of what changed in this restart

Three things changed or are new, all in `nov14-sprint/nfl/`:

1. `paper_ledger.py settle` now copies `source`, `source_url` and `retrieved_at_utc` from the results file into each settlement row.
2. `paper_ledger.py close --not-a-close` records a real price read before kickoff as an observation that is excluded from every closing-line comparison.
3. `real_intake.py` (new) loads the two captures, prices the frozen rules only where the source holds a real price, and with `--apply` writes to the ledger.

Entry points, run from the CCA root:

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/tests/fixtures/selftest_paper_ledger.py
```

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/tests/fixtures/selftest_real_intake.py
```

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/real_intake.py --scoreboard nov14-sprint/codex/real-intake/nfl-scoreboard.json --lines nov14-sprint/codex/real-intake/nfl-public-lines.json
```

Expected: `SELFTEST: 57 checks, 0 failed`; `SELFTEST real_intake: 28 checks, 0 failed`; and a dry run (no `--apply`, writes only to `nov14-sprint/nfl/real/`) that reports 14 games, 1 final, 13 games with a real price, 44 rows awaiting a final, 4 rows "no price, not scored", 8 rows with no side.

Adverse command that must be refused with exit 2 and write nothing:

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/real_intake.py --scoreboard nov14-sprint/codex/real-intake/nfl-scoreboard.json --lines nov14-sprint/codex/real-intake/nfl-public-lines.json --now 2026-11-17T07:00:00Z --apply
```

The thing I would most like a second pair of eyes on: the spread sign. The capture gives each side its own handicap (away `+2.5`, home `-2.5`). The ledger stores one number in the nflverse convention, where a positive number means the home team is favored. The intake converts with "ledger line = the away handicap" and refuses to price the spread when the two handicaps do not mirror each other.

## Ask 5. Two facts only you can settle

- The scoreboard file names its source as "DraftKings Sports Scores, search_games_v1" and its page as `https://www.nfl.com/schedules/2026/by-week/week-10`. I carry both exactly as written onto every row. If the page that actually held the scores is a different URL, tell me and I will carry that instead.
- Every price row says `local_availability_verified: false` and the book's own update time is unknown. Both stay that way on the ledger until someone checks an official source. I have not checked and I am not asking for a sign-in.
