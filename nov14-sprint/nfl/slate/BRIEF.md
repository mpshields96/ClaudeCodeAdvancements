# NFL one-shot: best 1-2 picks for Sunday, Nov 15 2026

Written 2026-11-15 06:41Z by the Claude coordinator (local_<session>). Every NFL worker reads this first.
Request record: `nov14-sprint/HUMAN_RELAY_20261115T064113Z_NFL_ONESHOT.txt` (a Codex relay of Matthew's words).

## What Matthew wants
Pick the best 1 or 2 bets on the Sunday slate. Any market counts: moneyline, spread, total, or a player prop. Base it on the matchup, each team's record, the head-to-head history, how good and how healthy each offense and defense is, and other parameters that matter. +EV is not a hard gate. A +160 underdog can be the pick if it is the most likely correct, best option. He does not want many bets. He wants one or two. Advisory only: nobody places anything.

## The slate (real, from ESPN via Codex's capture)
| UTC kickoff | Game |
|---|---|
| 14:30Z | NE at DET (Munich: nflverse marks it Neutral, so no home-field edge) |
| 18:00Z | KC at ATL, HOU at CLE, MIN at GB, JAX at TEN, MIA at IND, CAR at NO, BUF at NYJ |
| 21:05Z | SEA at LV, LAR at ARI |
| 21:25Z | SF at DAL |
| Nov 16 01:20Z | PIT at CIN (Sunday night) |
Monday LAC at BAL is not on the Sunday slate. WAS at NYG already finished.

## Data already on this Mac (use it, do not re-download)
- **Game prices:** `nov14-sprint/nfl/real/inputs/nfl-public-lines.20261114T225342Z.json`. Under `games[]`, then `book_references[]`: DraftKings ML, spread and total, as shown on ESPN at 22:53:42Z on Nov 14. `local_availability_verified` is false and stays false. This is a display price, not a confirmed Louisiana quote. Codex's mobile owner makes any fresh price capture. Claude does not re-capture game lines.
- **History:** `nov14-sprint/nfl/data/raw/games.csv` (nflverse, sha256 in `data/raw/MANIFEST.json`, retrieved 2026-11-14T21:16Z). It holds every game from 1999, the 2026 season through Thursday of week 10, and the week 10 schedule. Columns include scores, rest days, moneylines, spread_line, total_line, spread and total odds, QB names, coaches, roof, surface, div_game and location. Records, points for and against, H2H, rest and the market baselines all come from this file.
- Read every downloaded file with `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I script.py <path>`. Use stdlib only (system Python 3.9.6, no `X | Y` type syntax). Keep scripts outside any download folder.

## Guards against how betting models usually fail (Matthew's order; binding)
1. **No future information.** Every input carries an as-of time before the game's kickoff. A backtest only uses games before the game being scored, as a walk-forward. Sunday's results are never an input.
2. **No made-up odds, injuries or stats.** Every value carries `source_url` and `retrieved_utc` (or the nflverse row). If you can't get a value, record it in `missing`. Never estimate it or fill it from memory, and never take a number from a model's general knowledge.
3. **No fitting to Sunday.** The picker freezes its rules (`nfl/slate/frozen_picker.json`, with a sha256) before it scores the slate. After 14:30Z, no rule edits for this slate.
4. **No calibrating on winners alone.** Calibrate on all past games, the losses included. Report Brier score or log loss on every game in the test window, not a hand-picked set.
5. **Beat the market in a past-only test, or say so.** Compare the model with a simple market baseline: the vig-free implied probability from the nflverse moneyline, plus the spread and total at their posted numbers. Use walk-forward seasons it was not tuned on. The 2026 season (weeks 1-9) is after the model-writer's training cutoff (June 2026), so it is the cleanest test. Treat 2023-2025 as already seen. If the model doesn't beat the market, the page says so plainly, and the pick's confidence is the market's, not the model's.
6. **Label unknowns.** Each pick's evidence is marked known (sourced), estimated (model output) or unknown (missing). Late inactives come about 90 minutes before each kickoff. Picks made before then say which injury statuses were still open.
7. **One decision per pick.** Each candidate gets one recorded score from one engine run, with no side scripts.
Earlier lessons in `nov14-sprint/reddit/LEADS.md` (themes 4 and 5) and `nov14-sprint/nfl/results/backtest_report.txt` (no frozen rule cleared break-even on held-out 2023-2025) still apply. Don't redo that research.

## Shared files (write only your own)
- `nfl/slate/slate_20261115.json` (owner: nfl-slate-data). Shape:
  `{built_utc, sources:[{url, retrieved_utc, sha256}], games:[{event_id, nflverse_game_id, kickoff_utc, home, away, neutral, odds:{book, observed_utc, source_file, ml:{home, away}, spread:{home_line, home_price, away_line, away_price}, total:{line, over_price, under_price}}, teams:{home:{...}, away:{...}}, h2h:[{season, week, home, away, home_score, away_score}], injuries:[{team, player, position, status, practice, report_utc, source_url}], missing:[...]}]}`.
  Per team: 2026 record (straight-up, against the spread, over/under), points for and against per game, the last 4 games, rest days, QB starter, and any offense or defense stats you can get from a public keyless source, each with `source_url` and `retrieved_utc`.
- `nfl/slate/props_20261115.json` (owner: nfl-props). Shape:
  `{built_utc, available: true|false, why_not, props:[{event_id, player, team, market, line, over_price, under_price, book, observed_utc, source_url, player_form:{last_games:[...], season_avg, source_url}}]}`.
- `nfl/slate/` engine, tests, `frozen_picker.json`, `PAST_ONLY_TEST.md` and the results (owner: nfl-picker).
- `nfl/BEST_BETS_SUN_NOV15.md` and `nfl/BEST_BETS_SUN_NOV15.html` (owner: nfl-picker). Match the style of `nov14-sprint/odds/price_helper.html`: paper `#fcfaf6`, Charter serif, blue `#0e5e8a`.
- Raw captures go in `nfl/slate/inputs/<name>.<UTC>.json`, each in its own new folder, never overwritten.

## Limits (binding)
Paper and advisory only. No bets, accounts, sign-ins, keys, purchases or paid data. Public keyless pages only. If a page returns 403 or needs a login, record that and move on: no bypass, proxy or user-agent trick. Downloading a file (xlsx, zip and the like) needs Matthew's OK. Reading a page or a JSON API response is fine. Touch only files Claude or Codex made. No installs, schedules, pushes or branch switches. Corrected at 07:41Z: local commits of your own verified files, with explicit paths only, are allowed. Don't wrap up with "didn't do X" when there's a viable, appropriate way to finish it. See "Finish the work" in ASSIGNMENTS_0712Z.md. Event contracts (Kalshi and similar) count as unavailable in Louisiana. Don't spend time on licensing side-checks.

## Timing
Data files by about 07:50Z. First runnable picks by about 08:15Z. A refresh after inactives is optional: Codex owns fresh price captures, and nothing is scheduled.
Report to the coordinator with your file paths, what is missing, and what you could not verify.
