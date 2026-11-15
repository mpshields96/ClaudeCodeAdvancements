# Role hypothesis H3fb769df: public evidence and a base-rate check

Written 2026-11-15 about 10:00Z by Claude (NFL research lane). Information only. It changes no call, price, line or live rule, adds no bet and makes no profit claim. The Sunday PDF and its 09:35:13Z prices are untouched.

**Correction, 2026-11-15 about 10:10Z (raised by Codex review).** The first version called rules C and D "controls" and set 200 of 342 (58%) beside the dip cases as if it were the no-dip group. Rules C and D count every eligible case, the dip cases included. The distinct no-dip comparison is 156 of 258 (60.5%), against 44 of 84 (52.4%) after a dip and 2 of 7 on the strict pattern. The script, its single run and its result file are unchanged; only the labels and this subtraction are new. The reading is the same.

## Short version

- The forecast under test is already registered in the journal (H3fb769df, text hash `3fb769df...c658`): if Aaron Rodgers starts and Jaylen Warren takes an offensive snap at Cincinnati, Warren draws at least four targets.
- Its stated premise checks out against the public weekly file: Warren's targets in his eight 2026 games were 6, 4, 4, 6, 6, 4, 4, 2.
- **The base rate does not back the forecast.** In 2022-2025, running backs with a steady target role who then had a game of two or fewer targets drew four or more in their next game 44 times in 84 (52.4%, Wilson 95% 42% to 63%). Backs with the same role and no such dip did it 156 times in 258 (60.5%, Wilson 95% 54% to 66%). All eligible cases together, dip or not, were 200 of 342 (58.5%); that total includes the 84 dip cases. So there is no sign of a bounce-back after a quiet game, and four or more targets after a dip is roughly a coin flip.
- The closest analogs to Warren (seven straight games of four or more, then a dip) went 2 for 7. That sample is too small to lean on in either direction.
- This is a counterargument to carry beside the Warren write-up, not a reason to change it. The test of the forecast itself is the game: `role_check.py` holds the fixed pass/fail rule and grades it after the final.

## The premise, from public data

Source: nflverse weekly player stats, 2026 file (weeks 1-10, 9,534 rows). Jaylen Warren, player id 00-0037228, RB, PIT, regular season:

| Week | Opp | Targets | Rec | Rec yards | Carries | Dowdle row that week |
|---|---|---|---|---|---|---|
| 1 | ATL | 6 | 5 | 27 | 10 | yes (5 targets, 8 carries) |
| 2 | NE | 4 | 2 | 34 | 11 | yes (2, 7) |
| 3 | CIN | 4 | 3 | 49 | 17 | no |
| 4 | CLE | 6 | 3 | 33 | 17 | no |
| 5 | IND | 6 | 6 | 87 | 15 | no |
| 6 | TB | 4 | 2 | 28 | 14 | yes (4, 7) |
| 7 | NO | 4 | 3 | 36 | 18 | yes (6, 9) |
| 8 | CLE | 2 | 1 | 0 | 17 | yes (0, 15) |

Pittsburgh has no rows in week 9 (30 teams played; a bye), and week 10 so far holds only the Thursday game. So these eight games are every Pittsburgh game to date.

Two plain observations, no inference drawn: Warren cleared 22.5 receiving yards in 7 of his 8 games. In the five games where Rico Dowdle has a stat row Warren's targets were 6, 4, 4, 4, 2; in the three where Dowdle has none they were 4, 6, 6. "No row" means no recorded stat; why was not checked.

## The base-rate check

Rules were written into the script before its first and only run. No tuning.

- Population: running backs, regular season, appearances ordered by week inside one player-season.
- "Prior seven" are the seven appearances before the dip game. The outcome is the appearance after the dip game.
- Outcome: four or more targets. Secondary, information only: more than 22.5 receiving yards.

| Rule | What it selects | Cases | 4+ targets next game | Wilson 95% | Over 22.5 rec yards |
|---|---|---|---|---|---|
| A | prior seven each 4+, then a game of 2 or fewer (Warren's exact pattern) | 7 | 2 (29%) | 8% to 64% | 2 (29%) |
| B | prior seven average 4.0+, then a game of 2 or fewer | 84 | 44 (52.4%) | 42% to 63% | 33 (39%) |
| C | all eligible for A: prior seven each 4+, eighth game of any size (includes the 7 rule-A cases) | 31 | 19 (61%) | 44% to 76% | 14 (45%) |
| D | all eligible for B: prior seven average 4.0+, eighth game of any size (includes the 84 rule-B cases) | 342 | 200 (58.5%) | 53% to 64% | 165 (48%) |
| C minus A | distinct no-dip comparison for A, by subtraction | 24 | 17 (71%) | 51% to 85% | 12 (50%) |
| D minus B | distinct no-dip comparison for B, by subtraction | 258 | 156 (60.5%) | 54% to 66% | 132 (51%) |

The seven rule-A cases: Ekeler 2022 (15 targets next game), McCaffrey 2025 (8), and five misses: Jacobs 2023 (2), Robinson 2024 (2), Achane 2024 (0), Achane 2025 (1), Jeanty 2025 (2).

2026 weeks 1-10 with Warren left out, listed separately: rule B 2 of 2 (Kyren Williams, Bijan Robinson); rules A and C no cases; rule D 3 of 3 (the two rule-B cases plus one no-dip case).

## Limits

- Small samples, above all rule A. The intervals treat cases as independent, and one player-season can supply several, so the true uncertainty is wider.
- The 22.5-yard column applies Warren's line to other players. It is not an estimate of this prop's chance.
- The check knows nothing about this game: the opponent, the game script, Rodgers, or how Pittsburgh splits the backfield with Dowdle. It cannot test the personnel story behind the forecast.
- One rule set, chosen by Claude before looking. Other reasonable rules could move the numbers.
- Late-season cases include teams resting players in weeks 17 and 18.

## How the forecast gets graded after the game

`role_check.py` mirrors the journal hypothesis by id and text hash and refuses to grade before kickoff (2026-11-16T01:20Z). After the final, from the public box score:

```
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B role_check.py record --id H3fb769df \
  --set rodgers_started=yes --set warren_offensive_snaps=N --set warren_targets=N \
  --set warren_receptions=N --set warren_receiving_yards=N --set warren_longest_reception=N \
  --set early_exit=no --final-utc 2026-11-16T04:30:00Z --source-ref "<box score link>" \
  --recorded-by "<who>"
```

Verdicts: `supported` (4+ targets), `contradicted` (3 or fewer, even if one long catch wins the over), `condition_unmet` (Rodgers did not start or Warren took no snap), `unknown` (a number is missing). The 22.5-yard prop is shown beside the verdict as separate arithmetic; the journal grades the prop.

## Sources

- Public data: nflverse `stats_player` release, https://github.com/nflverse/nflverse-data/releases/tag/stats_player , as downloaded by Codex into its `nfl-receiving-role-test/work/raw/` folder (read only here). sha256 prefixes: 2022 `ad426c3fe5bf1cc3`, 2023 `f19cb71a5de0dce7`, 2024 `3ddc45a84f759aa3`, 2025 `e5e0615b3d96a3ea`, 2026 `19789406c2bc142b`.
- Script and result: `role_baserate.py` (sha256 `9d02320e56ab...`), `role_baserate_result.json` (every rule-A and rule-B case is listed in it).
- The forecast's own source note is Codex's `independent-public-evidence-20261115.md`; its citations are Codex's and were not re-verified here.
