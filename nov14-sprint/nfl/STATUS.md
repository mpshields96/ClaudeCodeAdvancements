# NFL lane status (R1), paper only

Updated 2026-11-15T05:16:40Z (from `date -u`). Owner: NFL lane session (Claude, Fable 5.2).
Paper and research only. Nothing here places a bet, opens an account or moves money. Paper output never implies a real edge and never authorizes real money.

## Closeout 2026-11-15T10:09:06Z (newest; read this first)

Matthew's wrap notice (10:01:34Z, relayed by Codex): finish the item in hand, hand off, stand down. This lane is finished and handed back. Paper only; no bets, accounts, keys or source pulls. The Sunday PDF, its issued calls and the 09:35:13Z prices were not touched by this lane.

- **Ownership.** `slate/experiment/journal.py`, its tests, `SETTLEMENT_API.md`, `EVALUATION.md` and `slate/experiment/data/` belong to Codex <codex-thread>. This lane no longer edits them.
- **Verified and committed (local, not pushed).** Commit 7303268: blind public comparator carrier (`slate/experiment/comparator.py`, 27 tests OK, chain of 4 rows intact) and the role-hypothesis carrier (`slate/experiment/role_check.py`, 15 tests OK, spec matches journal row H3fb769df). A second local commit carries this file, the older lane files this session made and the corrected evidence note.
- **Comparator result.** Three public calls observed by Codex were frozen before kickoff. The registered comparator, Rodeero_, is recorded as missing for the 2026-11-15 slate. Only Codex can observe Reddit.
- **Role hypothesis.** Public history does not back the Warren four-targets forecast: 44 of 84 after a dip (52.4%), 156 of 258 with no dip (60.5%), 200 of 342 for all eligible cases (58.5%, includes the 84 dip cases), 2 of 7 on the strict pattern. Counterargument only; no call, price or rule changed. Note: `slate/experiment/ROLE_HYPOTHESIS_EVIDENCE.md` (figures corrected about 10:10Z after Codex review).
- **Hand-off file for Codex <codex-thread>:** `~/Documents/Codex/2026-11-15/nfl-weekly-release-integration/work/from-claude/COMPARATOR_AND_ROLE_CHECK_HANDOFF.md`.
- **Open, not this lane's:** Codex <codex-thread> signoff on the two helpers; any later Rodeero_ call seen before kickoff; results into `comparator.py result` and `role_check.py record` after the finals.
- **Left uncommitted on purpose:** `data/raw/games.csv` and `data/raw/DATASETS.md` (third-party downloads; `MANIFEST.json` holds the source and hash), `real/inputs/` (byte copies of Codex captures), lock files, `self-learning/` strays, `BEST_BETS_SUN_NOV15.*` and everything under `slate/` that other writers own.
- **No real blocker.** Everything below is older history.

## Restart update: the ledger now rests on real teams, real games and real prices

Matthew's 120-minute window: 2026-11-15T04:41:26Z to 06:41:26Z. His correction: "I don't care about fake paper data. Use real teams and real events and in fact, let's prepare to obtain real data."

### Tonight, for Matthew (three lines)

1. Nothing to bet and nothing to start. This lane is paper only, and the four frozen rules showed no edge in the backtest.
2. To see the real slate, open `nov14-sprint/nfl/real/REAL_WEEK10.md`: 14 real week 10 games, the real DraftKings lines and prices read Saturday, and what each frozen rule does with them.
3. Nothing is scored yet, because no priced game has been played. After Sunday's games, one fresh scoreboard capture from Codex and one command settle the 44 priced rows on paper. That needs a new work window from you. Nothing is scheduled.

### What is real

- **14 real games** of 2026 week 10, with teams and kickoff times, from Codex's scoreboard capture (source as written in the file: "DraftKings Sports Scores, search_games_v1", page `https://www.nfl.com/schedules/2026/by-week/week-10`, captured 2026-11-14T22:51:42Z).
- **1 real final**: WAS 24 at NYG 21.
- **78 real price rows for 13 games**: DraftKings as shown on the public ESPN scoreboard, read 2026-11-14T22:53:42Z (moneyline, spread and total, both sides).
- **44 rule rows hold a real price.** Each was written to the real ledger at 2026-11-15T05:03:38Z as a price read before kickoff. None is a closing line, and the ledger keeps them out of every closing-line comparison.
- **All 52 ledger rows match the real source.** The ledger was generated Saturday from the nflverse schedule file. The separately captured real source gives the same decision, side, line and price on all 44 priced rows, and the same decision on the 8 rows where the rule has no side.
- **Every row carries its source URL and retrieval time** (`real/week10_games.csv`, `week10_finals.csv`, `week10_prices.csv`, `week10_rule_scores.csv`). Settlement rows will carry the result source, its URL and its retrieval time too.
- **The two captures are archived** byte for byte in `real/inputs/`, so the run can be repeated even if the originals are overwritten.

Rule rows (4 frozen rules x 14 games = 56):

| Status | Rows |
|---|---|
| real price recorded, awaiting final | 44 |
| no price, not scored (WAS at NYG) | 4 |
| rule has no side here, nothing to price (REST_EDGE, equal rest) | 8 |
| scored at the real price | 0 |

Ledger, observed 2026-11-15T05:16:39Z: 11 takes (all unsettled), 41 passes, 4 refusals, 44 real price observations, 0 closing-line observations, paper P&L +0.0000 units, stop rule not active.

### What is missing

- **Finals for the 13 priced games.** First kickoff 2026-11-15T14:30Z, last 2026-11-17T01:15Z. Until then nothing can be scored.
- **Any price for WAS at NYG.** The capture holds no book reference for it. Its four rule rows say "no price, not scored" and are held back from settle. No price was invented.
- **True closing lines.** The prices were read about 16 hours before the first Sunday kickoff. An exact close only counts on the identical line.
- **Louisiana availability (checked 2026-11-15T05:29Z to 05:31Z against primary pages).** The book is licensed in Louisiana. The captured prices are still not verified as Louisiana prices.
  - **DraftKings is on the state regulator's licensee list.** Louisiana Gaming Control Board, page headed "Licensed Wagering Platforms in Louisiana", https://lgcb.dps.louisiana.gov/licensed-platforms/, retrieved 2026-11-15T05:29:27Z. Exact wording of the entry, under the heading "Sportsbooks": "DK Crown Holdings, Inc. d/b/a DraftKings (B016503468)". The page's opening line: "The following is a list of all licensed wagering platforms in Louisiana." The page carries no date and says nothing about mobile betting or parishes. It was read through the page reader, which uses a small model. DraftKings was also on this list when it was read at 2026-11-14T21:18:01Z.
  - **Its mobile book is listed too.** Louisiana Gaming Control Board, 30th Annual Report to the Louisiana State Legislature (its tables cover fiscal year 7/1/2024 to 6/30/2025), https://lgcb.dps.louisiana.gov/media/avxl0yu3/30th-annual-report-to-the-louisiana-state-legislature-4.pdf, retrieved 2026-11-15T05:30:21Z, PDF SHA-256 `2c812a5d9bde696698d34a3a1bc6bef9ed6243d1b8279bfb6141b4aa84f412a7`, read from the page images of printed pages 33, 35 and 36. Page 35 says the listed licensees and platform providers "have been awarded licenses and permits to conduct sports wagering in Louisiana". The table row on page 36 reads: licensee "Golden Nugget Lake Charles", retail provider "DraftKings", mobile provider "DraftKings". DraftKings is the retail provider only (mobile column "None") at Bally's Baton Rouge, Live! Casino & Hotel Louisiana and The Queen Baton Rouge. This is a fiscal-year report, so it can lag the current list.
  - **Parish rules matter.** Same report, page 35, under "Sports Wagering Requirements and Prohibitions": "A person must be physically located in a parish that has approved a proposition authorizing sports wagering." Page 33: "Fifty-five (55) out of sixty-four (64) parishes" voted in favor on November 3, 2020. The nine named as voting no are Caldwell, Catahoula, Franklin, Jackson, LaSalle, Sabine, Union, West Carroll and Winn. Page 35 also requires age 21 or over, and an account with the operator for a wager placed by website or mobile app. Matthew's parish is not on record in this lane, so that check is his. No official record was found on 2026-11-14 of a parish changing status since 2020; that was not rechecked tonight.
  - **Not confirmed.** DraftKings' own pages returned HTTP 403 on both tries (`sportsbook.draftkings.com/help/sports-betting/where-is-sports-betting-legal` at 05:29:27Z and `sportsbook.draftkings.com/where-is-draftkings-sports-available` at 05:30:29Z). They were not read, and the block was not worked around. The State Police Gaming Division list was not checked. No primary page shows that the prices in the capture are the ones DraftKings shows a customer in Louisiana: they were read from a public ESPN display, the book's own update time is unknown, and prices may move.
  - **The data flag stays as captured.** Every price row still says `local_availability_verified: false`. That field belongs to Codex's capture and describes the price rows. A license for the book does not verify those rows, and this lane does not edit Codex's capture.
  - **Nothing changes tonight.** Nothing to bet. The ledger stays paper. Kalshi-style event contracts stay unavailable in Louisiana. This is research, not legal advice, and licensing can change, so the board's list should be reread before anyone acts.
- **Real finals through the scoring path.** The after-the-game path is tested with invented fixture scores in temporary folders (28 checks). It has not yet run on a real final that has a price.
- **Codex's independent retest** of `real_intake.py` and of the two ledger patches. Asked in `NEEDS_FROM_CODEX.md`.
- **Player props.** This intake loads game spreads and totals only. Codex's prop captures were not loaded in this unit.

### Rules this intake enforces

- A rule row is scored only where the source holds a real price for that exact side and line. Otherwise it says "no price, not scored".
- A price is recorded against a ledger pick only when side and line are identical. A different line is reported as "line differs, not recorded". No other line is substituted.
- A final reaches the ledger only when every rule row of that game is backed by a real price that matches the ledger row. Other finals are held back and named in the output.
- A game is final only when the source says `ScoresOfficial`, both scores are present, and the capture time is after kickoff. If the two captures disagree on a final, it is not used.
- The frozen rules were not touched: `rules.py` and `frozen_rules.json` have the same SHA-256 as before the restart.

### Entry points for the real data

Run from the CCA root (`~/Projects/ClaudeCodeAdvancements`). System `python3` 3.9.6, standard library only.

Dry run. Reads the two captures, writes the reports in `nov14-sprint/nfl/real/`, writes nothing to the ledger:

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/real_intake.py --scoreboard nov14-sprint/codex/real-intake/nfl-scoreboard.json --lines nov14-sprint/codex/real-intake/nfl-public-lines.json
```

Apply. Also records the real prices on identical ledger picks and gives backed finals to settle. Safe to repeat; a second run records nothing new:

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/real_intake.py --scoreboard nov14-sprint/codex/real-intake/nfl-scoreboard.json --lines nov14-sprint/codex/real-intake/nfl-public-lines.json --apply
```

Last real run, 2026-11-15T05:14:24Z, exit 0: `14 games, 1 finals, 13 games with a real price, 78 price rows`; `0 real prices recorded on identical contracts, 44 already there, 0 refused, 0 not recorded because the line differs; settle: settle not run; 1 final(s) held back from settle, no real price on the identical ledger contract: 2026_10_WAS_NYG`.

After the games (new scoreboard capture, original price capture):

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/real_intake.py --scoreboard <new scoreboard capture> --lines nov14-sprint/nfl/real/inputs/nfl-public-lines.20261114T225342Z.json --apply
```

Adverse command that must be refused (exit 2, writes nothing): the same command with `--now 2026-11-17T07:00:00Z`. The pretend clock is for tests and is refused on the real ledger and the real output folder.

### Self-tests

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/tests/fixtures/selftest_paper_ledger.py
```

Observed 2026-11-15T05:16:39Z: `SELFTEST: 57 checks, 0 failed`. It was 52 before the restart. The 5 new checks cover the two ledger patches.

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/tests/fixtures/selftest_real_intake.py
```

Observed 2026-11-15T05:16:39Z: `SELFTEST real_intake: 28 checks, 0 failed`. It runs in temporary folders, uses the archived real price capture with invented after-the-game scores, and checks that the real ledger and the real output folder are byte for byte unchanged.

### What changed in code during the restart

- `paper_ledger.py`: `settle` copies `source`, `source_url` and `retrieved_at_utc` from the results file into each settlement row. `close --not-a-close` records a real price read before kickoff, excluded from closing-line comparisons.
- `real_intake.py`: new.
- `tests/fixtures/selftest_real_intake.py`: new. `tests/fixtures/selftest_paper_ledger.py`: 5 checks added.
- Unchanged: `rules.py`, `frozen_rules.json`, `backtest.py`, `RULES.md`, `LEGAL_CHANNELS.md`, the report, and `ledger/ledger.jsonl` (append-only; its 52 rows have the same SHA-256 as before the restart).

### Fingerprints (SHA-256, taken at 2026-11-15T05:14:24Z)

| File | SHA-256 |
|---|---|
| `real_intake.py` | `cdc28e866c85c4e02333a03ef627fc0ea65897b9163c35696f36ca5d8029ae53` |
| `paper_ledger.py` | `a22f4d83595d67b786696d26e075cae1acff4eb31436e6e793897ba63b481e60` |
| `rules.py` | `383162ccd3b98da0bcb3eaf45f5cd7b67f419e3f71bf39ccda5f9b3297be9de5` |
| `frozen_rules.json` | `fe927f41d5f7dbd0e6ec45482f016029b333c6b1f3852eba920fbc0b8c606fef` |
| `tests/fixtures/selftest_paper_ledger.py` | `0e07c1af41d3836a4cc3c293476ac51933d009c5614c60c86c5a354a58f55cce` |
| `tests/fixtures/selftest_real_intake.py` | `178a7334fd84d7614e45a3f7ea058785f2bff7981d284fbae2a912a44e6454ee` |
| `ledger/ledger.jsonl` (52 rows) | `9e1e8c43a6ebf979d98bc266fd0b5c21c3dd67021e2702134da83ebc3e6e788d` |
| `ledger/observations.jsonl` (44 rows) | `4e49f588381d251d380362dd968e531dc0af753e4db5e7e9442ada3afad2d309` |
| `real/inputs/nfl-scoreboard.20261114T225142Z.json` | `f6fa22769799e21af1e76155a3583f99c6c77a6e56916c874e0151815958ad19` |
| `real/inputs/nfl-public-lines.20261114T225342Z.json` | `206d164be40574fa78cb9a1fca8f0db3b3c8d8ef0a5b56431f3f975682d60e9e` |

### Open asks

`NEEDS_FROM_CODEX.md` holds the exact asks: a fresh scoreboard capture after each game window, no overwrite of the price capture, a WAS at NYG price only if a free legal source has one, and an independent retest.

---

# Earlier status, written 2026-11-14T22:29:15Z, before the restart

Kept as written. It is still the record for the backtest, the frozen rules, Matthew's own picks and the legal channels. Where it and the restart update above differ, the restart update is current.

Owner: NFL lane session (Claude, Fable 5.2). All times UTC, 2026-11-14, taken from `date -u`.
Paper and research only. Nothing here places a bet, opens an account or moves money. Paper output never implies a real edge and never authorizes real money.

## The short version

- **No demonstrated edge.** Four mechanical rules were written down before any test, tuned on 2006-2022 and tested once on 2023-2025. None passed.
- **A paper ledger exists for this weekend** (2026 week 10): 11 paper takes, 41 passes, 4 refusals for the Thursday game that had already kicked off. Generated 21:43:02Z.
- **The ledger works for Matthew's own picks**: a personal take or pass with his reason, the exact line, the exact American price, the book and the time he read it. Player props are entered by hand.
- **The spread-sign fault Codex found is fixed** in `paper_ledger.py` (22:00Z). Codex has not yet confirmed its retest.

## Entry points

Run from a clean shell at the CCA root (`~/Projects/ClaudeCodeAdvancements`). System `python3` is 3.9.6, standard library only.

Normal command (read-only, exit 0):

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/paper_ledger.py status
```

Observed 22:03:12Z: `Takes: 11 (unsettled 11)   Passes: 41   Rejections: 4`, `STOP RULE: not active (limit 10.0u drawdown)`, exit 0.

Adverse command that must be rejected (writes nothing, exit 2):

```bash
env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/paper_ledger.py --now 2026-11-10T00:00:00Z generate
```

Observed 22:03:12Z: `REFUSED NOW_OVERRIDE_NOT_ALLOWED: --now is only allowed with --fixture or --ledger-dir (the real ledger always uses the system clock)`, exit 2. The real ledger was still 52 picks and 4 rejections afterwards.

Other commands:

| What | Command (prefix each with `env -i PATH=/usr/bin:/bin python3 -I nov14-sprint/nfl/`) | Observed |
|---|---|---|
| Backtest and replay check | `backtest.py` | 22:00:58Z: "No demonstrated edge", "Replay check: held-out numbers MATCH the first evaluation of 2026-11-14T21:24:22Z", exit 0 |
| Backtest self-test | `backtest.py --selftest` | 22:00:40Z: 25 checks, 0 failed |
| Backtest, tampered data | `backtest.py --data <changed copy of games.csv>` | `REFUSED INPUT_HASH_MISMATCH`, exit 2 |
| Ledger self-test | `tests/fixtures/selftest_paper_ledger.py` | 22:00:26Z: "SELFTEST: 52 checks, 0 failed", exit 0. Uses temp ledgers; checks the real ledger is unchanged. |
| This weekend's games | `paper_ledger.py slate` | 14 games, 2026 week 10, read-only |
| Log your own pick | `paper_ledger.py add --game-id 2026_10_NE_DET --rule MANUAL-v1 --action take --reason "..." --market spread --side home --line=-2.5 --price=-110 --quote-ts <UTC> --source "<book>"` | see the refusal table below |
| Record a closing price | `paper_ledger.py close --pick-id <id> --price <p> --line=<same line> --source "<book>" --quote-ts <UTC>` | |
| Settle finished games | `paper_ledger.py settle --results-file <csv> --results-ts <UTC>` | csv needs `game_id,home_score,away_score` |
| Settle one prop by hand | `paper_ledger.py settle-manual ...` | props only |

Add `--ledger-dir <empty folder>` (and, there only, `--now <UTC>`) to try anything without touching the real ledger.

Matthew's own route is the coordinator's Paper Desk (`nov14-sprint/Paper Desk.command`), a browser form that calls this same CLI. I did not build it and did not retest it after the spread fix. A static price helper for the -170 to +150 question is at `nov14-sprint/odds/price_helper.html` (coordinator's file, not checked by me).

## Refusal checks observed at 22:27:20Z

Scratch ledger, `--now 2026-11-14T22:30:00Z`, manual `add` on NE@DET unless noted. The real ledger was unchanged (52 and 4 lines).

| Case | Result | Exit |
|---|---|---|
| Normal take, home -2.5 at -110 | `ACCEPTED TAKE 8a51b056fc04def9`, "DET -2.5 wins the bet only if DET wins the game by more than 2.5 points" | 0 |
| The same take again | `REJECTED DUPLICATE_PICK` | 2 |
| Quote time 14.5 hours old | `REJECTED STALE_LINE` (max 12 hours) | 2 |
| Quote time after decision time | `REJECTED FUTURE_DATED_INPUT` | 2 |
| Stake 2 | `REJECTED STAKE_OVER_CAP` (cap 1 unit) | 2 |
| Total with no line | `REJECTED MISSING_LINE` | 2 |
| WAS@NYG, already played | `REJECTED KICKOFF_PASSED` (kickoff 2026-11-13T01:15:00Z) | 2 |
| Price +200 or -180, outside -170 to +150 | Accepted and flagged, not refused. Stored with `price_in_band=false`; prints "note: price -180 is outside the manual band -170 to +150 (recorded price_in_band=false)" (22:28:56Z). | 0 |

Earlier checks, same session: relisted prop (54.5 then 60.5, same player) saved as two picks; 54.5 a second time `DUPLICATE_PICK`; a 60.5 close on the 54.5 pick `CONTRACT_MISMATCH`; early prop settlement `SETTLE_BEFORE_KICKOFF` (21:48Z). The coordinator ran 20 cases independently at 21:36Z (`nov14-sprint/COORDINATOR_CHECKS.md`).

## What was built

All inside `nov14-sprint/nfl/`.

| File | What it is |
|---|---|
| `LEGAL_CHANNELS.md` | Where Matthew could act himself in Louisiana, checked against official sources |
| `data/raw/games.csv` | nflverse game archive. URL `https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv`, retrieved 21:16:58Z, 2,190,038 bytes, 7,548 rows, SHA-256 `44f6ba50a76303869229be8fdad82d124e77f24f50c90c319fbc245dd34120a0`. Data only; no code was downloaded or run. |
| `RULES.md` | Pre-registration, written 21:20:46Z, before the first backtest run at 21:24:22Z. Ten variants in four families. |
| `rules.py` | The rules and the grading function, shared by the backtest and the ledger |
| `backtest.py` | Train 2006-2022, held-out 2023-2025, hash-checked input, replay check |
| `frozen_rules.json` | The four variants frozen at 21:24:22Z |
| `VARIANT_LOG.jsonl` | Every variant of every run, failed ones included. 80 lines at 22:03Z: four runs of 20. Each further run adds 20. |
| `results/` | Report text, results JSON, and the first held-out evaluation |
| `paper_ledger.py` | The paper ledger CLI. SHA-256 at 22:03Z `0c87aef156650f7a77b24fc81c55eacbf7505b210fb02b0482d75e20b45d9574` |
| `ledger/` | The real ledger: `ledger.jsonl` (52 lines), `rejections.jsonl` (4 lines). Append-only. |
| `tests/fixtures/` | Ledger self-test and its fixture rules |
| `build_report.py`, `report/NFL_Paper_Desk.pdf` | Four-page results sheet, rendered 21:52Z |

## Backtest result

Priced at -110: a win is +0.9091 units, a loss -1, break-even 52.38%. Pass test, set in advance: training ROI above zero and the held-out 95% win-rate interval entirely above 52.38%.

| Frozen rule | Held-out bets | W-L-P | Win rate | ROI | Passes scored (W-L-P on the rule's side) |
|---|---|---|---|---|---|
| HOME_DOG-v1.T7 | 63 | 38-23-2 | 62.30% | +18.33% | 753 (362-374-17) |
| BIG_DOG-v1.T10 | 79 | 33-45-1 | 42.31% | -18.99% | 737 (353-366-18) |
| REST_EDGE-v1.D6 | 69 | 33-35-1 | 48.53% | -7.25% | 747 (116-116-3) |
| HIGH_TOTAL_UNDER-v1.T47 | 218 | 108-108-2 | 50.00% | -4.50% | 598 (292-303-3) |

- All four: **no demonstrated edge**. HOME_DOG-v1.T7 looks best but its interval is 49.75% to 73.39% (46.35% to 75.96% adjusted for four rules), which includes break-even. One-sided p 0.077; times four, 0.31. Sixty-three bets is a small sample.
- Baselines on the held-out seasons: always home -4.09%, always underdog -7.36%, always under -5.80%.
- A separate reviewer agent reimplemented the test: "numbers reproduce". Codex's own reimplementation also matched all four (its relay, 21:3xZ).
- Things a reader should know:
  - The held-out seasons are now spent. Any new rule tested on them is no longer a clean test.
  - Two held-out looks were not logged at the time: the reviewer's one `--no-write` run and one REST_EDGE-D3 sensitivity look. `--no-write` now logs. I did not add this note to `RULES.md`.
  - The rules were proposed by a model that may remember recent NFL seasons. That is a reason to trust the forward 2026 ledger more than the backtest.
  - The archive's spread line has no stated source or time. It is not verified as a closing line.

## The paper ledger

- Generated rows: 13 remaining week-10 games times four frozen rules. Takes per rule: HIGH_TOTAL_UNDER 6, HOME_DOG 3, BIG_DOG 1, REST_EDGE 1. Each row has the rule version, line, price, source, file retrieval time, paper stake and decision time. Passes are logged with the side the rule would have taken, so they get scored too.
- These takes come from rules that failed the test. The ledger tracks them on paper. It is not a recommendation.
- Stop rule, stated before any result: no new takes once paper drawdown reaches 10 units (`STOP_RULE_ACTIVE`).
- Identity of a pick: game, rule version, market, player and stat, side, line. A relisted prop at a new yardage is a new pick. An exact retry is refused.
- Whole-command refusals (exit 2, nothing written) include `LEDGER_CORRUPT`, `INPUT_HASH_MISMATCH`, `NOW_OVERRIDE_NOT_ALLOWED`, `FROZEN_RULES_INVALID`, `NO_SLATE`.

### Closing prices

Enforced in `cmd_close` in `paper_ledger.py`:
- A close needs `--line` when the pick has a line (`MISSING_LINE`). A different line is refused (`CONTRACT_MISMATCH`). A 60.5 price is never attached to a 54.5 ticket; if the original line is gone, nothing is recorded, and that is "exact close missing".
- A quote from before the pick's decision time, or from kickoff onward, is saved as an "other observation" with `exact_close_eligible: false` and the reason. `status` counts it separately.
- Repeated closes on one ticket are all kept. **The tool computes no closing-line value and selects no observation.** If someone computes one later, the intended choice is the latest exact-close candidate by quote time. That choice is not enforced in code.

### Spread sign fix (Codex's release blocker)

- Fault: a personal spread was graded in the archive's convention. Home -2.5, home wins 21-20, graded WIN +0.9091.
- Fix: a personal spread is stored with `line_convention: ticket_handicap` and graded as the picked side's margin plus the typed handicap. Rule rows are stored with `nflverse_home_favored_positive` and graded by `rules.grade`, unchanged. `rules.py` was not edited.
- Observed 21:59Z in a scratch ledger with a made-up final of NE 20, DET 21: the same ticket now settles `loss pnl=-1.0000u`; away +2.5 wins; the rule rows on that game grade as before.
- Rows without the field are handled explicitly: a personal row is treated as a ticket handicap, a rule row as the archive line, and settlement prints a NOTE and records which was assumed. An unknown value is refused `UNGRADEABLE`.
- All 52 rows in the real ledger are rule rows written before the fix, so they settle in the archive convention with that NOTE. The real ledger was not rewritten.
- Self-test additions: home wins by less than its handicap, a push, away favorite, away underdog, a control over 12 rule spread rows, rows without the field, unknown convention.
- **Not verified:** Codex's browser-to-settlement retest. I sent readiness at 22:00Z.

## Limits and what is not done

- **Team markets only for generated rows.** nflverse `games.csv` has spreads, totals and moneylines. I found no free, legal source of player-prop prices, so props are typed in by hand, their prices are Matthew's word, and they settle by hand with `settle-manual`.
- **Generated prices are archived observations.** The file has no sportsbook quote time. The 12-hour check on generated rows measures the age of the downloaded file only. It does not show a line is fresh, offered or available at a Louisiana book. The CLI says this on `generate` and `status`.
- **Out-of-range prices are flagged, not refused.**
- **No settlement has run on the real ledger.** No remaining week-10 game has been played. Settling needs final scores in a csv after the games; a fresh nflverse download is not automated.
- **No closing-line value is computed.**
- **A close on a rule row must use the archive's number and sign** (for example NYJ's home row carries -7.5, meaning NYJ is a 7.5-point underdog). The CLI prints this, but it is easy to get wrong.
- **The results sheet PDF predates the spread fix.** Its worked example is a prop, so nothing in it is wrong, but it does not explain the two spread conventions.
- No price at any licensed book was checked for any pick: no sign-in, no account.
- Reddit returned 403 and was not bypassed. Codex's prop-tracking thread is a lead only.

## Legal channels (detail in `LEGAL_CHANNELS.md`)

- The Louisiana Gaming Control Board lists 10 sportsbook licenses; its 30th Annual Report names 8 mobile brands (Bet365, Fanatics, DraftKings, Caesars, BetRivers, BetMGM, FanDuel, theScore Bet).
- Mobile betting is not allowed in the nine parishes that voted no in 2020 (Caldwell, Catahoula, Franklin, Jackson, LaSalle, Sabine, Union, West Carroll, Winn).
- Event-contract and prediction-market products are excluded across brands.
- Correction to the brief: Kalshi sued first (KalshiEX LLC v. Murrill, W.D. La., 1:26-cv-04476, filed 2026-10-23). The Attorney General's suit of 2026-11-12 is known to me from secondary sources only.

## Mapping to R1 ("full speed ahead on NFL betting")

| Matthew's words, as carried in the sprint | What exists | State |
|---|---|---|
| NFL betting, legal channel only | `LEGAL_CHANNELS.md` | Done, official sources cited |
| Honest test of whether a rule has an edge | `RULES.md`, `backtest.py`, results | Done, independently reproduced. Answer: no demonstrated edge. |
| Paper picks for the next slate, passes included | `ledger/`, `paper_ledger.py generate` | Done, 11 takes and 41 passes |
| His own process: watch, judge roles, prices from +150 to -170 | `paper_ledger.py add` and the coordinator's Paper Desk form | Works; price outside the range is flagged |
| Props relisted at a new yardage keep both tickets | contract identity, `close` checks | Works; verified by Codex and the coordinator |
| Settle later | `settle`, `settle-manual` | Built and tested on made-up scores only |
| Spread tickets graded as a bettor reads them | spread sign fix | Fixed; Codex retest pending |

---
STATUS.md written 2026-11-14T22:29:15Z by the NFL lane session. Real ledger at that time: 52 picks, 4 rejections, unsettled. No commits, pushes, installs, accounts or bets were made by this lane.
