# NFL mechanical rules: pre-registration (ruleset v1)

- **Written:** 2026-11-14T21:20:46Z (from `date -u`), before `backtest.py` existed or ran. No rule result had been seen.
- **What had been seen at this point:** row counts per season, which columns are filled, the sign of `spread_line`, the mean of `result - spread_line` over all games (0.061), and the 2026 schedule rows for weeks 10 to 12. Nothing by rule, side or threshold.
- **Code:** `rules.py` holds the exact logic. `backtest.py` runs it. `paper_ledger.py` uses the frozen choice going forward.

## Data
- File: `data/raw/games.csv` from `https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv`, retrieved 2026-11-14T21:16:58Z, 2,190,038 bytes, SHA-256 `44f6ba50a76303869229be8fdad82d124e77f24f50c90c319fbc245dd34120a0` (`data/raw/MANIFEST.json`).
- Games used: regular season only (`game_type == REG`) with a final score and the needed line.
- **Which line.** The nflverse `spread_line` and `total_line` columns. The source's own column notes (`data/raw/DATASETS.md`) call them "the spread line for the game" and "the total line for the game". They do not name the sportsbook or the capture time. They are commonly treated as a near-closing consensus number, but that is UNVERIFIED here. One number per game; no line history.
- **Price.** Every bet is priced at the standard **-110** on both sides: a win pays +0.9091 units per unit risked, a loss costs 1 unit, a push returns the stake. Break-even win rate is 110/210 = **52.38%**.

## Foreknowledge boundary
- Decision time for the historical test is "at the recorded line, before kickoff".
- A rule may read only: `spread_line`, `total_line`, `away_rest`, `home_rest` (rest days are a schedule fact).
- A rule may not read scores, `result`, `total`, `overtime`, weather (`temp`, `wind`), QB or coach fields, or anything from a later game.
- No Claude judgment on any historical game. A model can remember past results, which would contaminate the test. Only this frozen code is tested.

## Rule families and every variant (10 in total)
| Family | Bet | Variants (version ids) |
|---|---|---|
| HOME_DOG | Home team against the spread when it is an underdog of at least T points | `HOME_DOG-v1.T1`, `HOME_DOG-v1.T3`, `HOME_DOG-v1.T7` |
| BIG_DOG | The underdog (home or away) against the spread when the spread is at least T points | `BIG_DOG-v1.T7`, `BIG_DOG-v1.T10`, `BIG_DOG-v1.T14` |
| REST_EDGE | The team with at least D more rest days, against the spread | `REST_EDGE-v1.D3`, `REST_EDGE-v1.D6` |
| HIGH_TOTAL_UNDER | Under the total when the total is at least T | `HIGH_TOTAL_UNDER-v1.T47`, `HIGH_TOTAL_UNDER-v1.T50` |

Any other game is a **pass** for that rule. Passes are counted and scored on the rule's default side (the "shadow" side), so the report shows whether the filter picked better games than the ones it skipped.

Known simplification: neutral-site games are not treated differently (the rule code does not read `location`).

## Periods
- **Training (choose on):** seasons 2006 to 2022.
- **Held out (evaluate once):** seasons 2023 to 2025.
- **Untouched:** season 2026. It is used only by the forward paper ledger.

## Selection, fixed in advance
1. Run all 10 variants on training only.
2. In each family keep the variant with the highest training ROI at -110, among variants with at least 150 training bets. Ties go to the first in the list above.
3. Write the four chosen variants to `frozen_rules.json`. That file is the freeze. If it already exists, `backtest.py` checks that the recomputed choice matches it and stops if it does not.
4. Only then score the four frozen variants on the held-out seasons, once. The other six variants are never scored on held-out data.

## What counts as an edge, fixed in advance
A frozen variant shows an edge only if **both** hold:
- its training ROI at -110 is above zero, and
- the lower end of its held-out 95% Wilson interval for the win rate (pushes excluded) is above 52.38%.

Four families are tested, so the report also shows the stricter 98.75% interval (Bonferroni for four tests). Anything else is reported as **no demonstrated edge**. A positive held-out ROI whose interval includes break-even is not an edge.

## Reported for every scored variant
Bets, wins-losses-pushes, win rate, ROI after vig at -110, a 95% interval for the win rate (Wilson) and for ROI (bootstrap, 10,000 resamples, seed 20261114), passes, and the shadow record of the passes.

## Context only (never used for selection)
- Baselines on both periods: always home, always underdog, always under.
- Sensitivity on held-out: the frozen variants priced at the file's own recorded odds (`home_spread_odds`, `away_spread_odds`, `under_odds`) in place of -110.

## Variant log
`backtest.py` appends every variant it scores, good or bad, to `VARIANT_LOG.jsonl` with the run time. A changed parameter is a new version id and a new log line. After this run the 2023 to 2025 seasons are spent: any later rule can only be judged on forward data stamped before kickoff.

## Paper ledger rules, fixed in advance
- The ledger applies the four frozen variants to the next slate and records a take or a pass for every game and rule. It tracks them forward whether or not the backtest showed an edge; a paper pick is not a claim of edge.
- Paper stake: 1 unit per take. Cap: 1 unit per pick.
- **Stop rule:** when settled paper results are 10 units or more below their running peak, or 10 units down in total, no new take is accepted.
- Rejected: a kickoff that has passed, a missing or stale line (older than 12 hours at decision time), a future-dated input, a stake over the cap, a duplicate pick.
