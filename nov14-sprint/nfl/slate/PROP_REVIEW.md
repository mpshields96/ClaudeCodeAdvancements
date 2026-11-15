# Sunday Nov 15 2026 NFL props review (paper, advisory only)

Written 2026-11-15T07:48:28Z by the props researcher session (nfl-props). Nobody places anything. No key, no price requests, no orders, no new network requests while writing this. Scope set by Matthew's reset message: assess actionable prop evidence from the existing 06:55:06Z shared feed and the already collected player form, reconcile identity, market, period and line, record what is missing, report to Codex. I did not touch `props_20261115.json` (the data integrator owns it); I only read it.

Labels used below: **known** = read from a cited file with its retrieval time; **estimated** = my arithmetic or a model output; **unknown** = not in any file I have.

> **How to read the form numbers (Matthew's clarification, relayed 2026-11-15 about 07:25Z).** "Last 5 games" and "last 10 games" mean a player's **consecutive current-season (2026) appearances**, chiefly for player props. Everywhere in this file: 2026 regular-season games only, newest first, **nothing padded from 2025**, and the games actually available are shown (no player in the form file has more than 9, so "last 10" means all of them, and Warren's is 8). Two different measures are kept apart and never added together:
> 1. **Today's-line count (retro-fit).** How many of those past games would have cleared the line posted *today*. Descriptive. The line did not exist when the games were played. Example: Warren over 22.5 in 4 of his last 5 and 7 of 8.
> 2. **Record against the lines actually posted then.** Each game against the line posted for that game. Example: Warren 6 of 8. It exists in this review for **Warren only**, from a third-party archive whose books and quote times are unverified.
>
> Neither is a forecast probability and neither is a calibrated or past-only test.

## 1. Verdict

1. **No prop passes as a calibrated or past-only-tested pick. I did not beat the market in a past-only test.** A past-only test needs historic lines for many players and games. The only historic lines I know of are Stat Sniper's per-game prior lines for Warren (8 games, another chat's collection, books and quote times unverified, not fetched or checked by me against the source page). Eight games for one player is not a test. For the other 254 player-market rows I found no historic lines. There is also no sourced outcome distribution to price a cross-line shift.
2. **One conditional candidate, and it is Codex's call, not mine:** Jaylen Warren Over 22.5 receiving yards at BetMGM -115 (Pittsburgh at Cincinnati, kickoff 2026-11-16T01:20Z). Codex wrote it into `Final_Decisions.json` (decided 07:08:57Z) with the conditions "Aaron Rodgers starts and Warren retains his passing-down role. Pass if workload is restricted or the exact threshold disappears." I did not re-derive that call; I checked the line and the form behind it. **Decision on that one prop: act only if all four conditions in section 5 hold at kickoff minus 90 minutes; otherwise pass.**
3. **Dissent on how strong the Warren case is (props researcher).** The headline "4 of his last 5 and 7 of 8 over 22.5" is a today's-line count (a retro-fit): it applies a threshold that did not exist to games played against other lines. It describes his box scores. It does not show he beat what the market asked of him. The one measure that uses the lines actually posted is third-party and unverified, and it is **weaker**: 6 of 8 overall, **3 of 5 in his last five and 1 of 3 in his last three**, with the two misses in weeks 6 (28 against 28.5) and 8 (0 against 22.5), both among his three latest games. Both measures rest on 8 games. The 95% intervals (estimated) run 53% to 98% for 7 of 8 and 41% to 93% for 6 of 8; both include the 53.5% break-even at -115. The integrator's appearance sources (second-hand: I read its stored extracts, not the web pages) list Rico Dowdle as **inactive in weeks 3, 4 and 5** (NFL.com inactives articles for weeks 3 and 5, the NFL gamebook for week 4), exactly the weeks of Warren's 49, 33 and 87 (mean 56.3); in the five weeks Dowdle played (1, 2, 6, 7, 8) Warren's receiving yards were 27, 34, 28, 36 and 0 (mean 25.0, median 28), which is 4 of 5 over 22.5 and 3 of 5 on the prior lines (my arithmetic, **estimated**). His 0 in week 8 came in a 27 to 6 win in which he ran 17 times for 143 yards (the integrator's log). Whether Dowdle plays today is **unknown** to me (final inactives about 23:50Z). I would call this a thin, unproven lean at best, not an edge, and the market evidence below does not add support.
4. **The market itself shows no free edge.** Across 247 rows I found no cross-book pair that locks a profit (smallest combined implied probability 1.0064, median 1.0543, none below 1.000), and the best available price on a side is never better than the same-line book-average fair price (largest gap -0.0031 with 2+ books posting that line).
5. **Only 18 of 255 player-market rows pass every market-quality gate** (identity resolved, 4+ books on one line, no injury flag, DraftKings line confirmed by ESPN). Those gates are about data quality. They say nothing about whether the line is wrong. Most rows have 5 books on 5 different lines, so the "line" depends on which book you read.
6. **Data that could be misread is listed in section 10** for Matthew, including a field name in the integrator's file that reads like historic lines but is today's-line counts.

## 2. Sources and hashes

All times UTC. Hashes are SHA-256 of the files as they sit now (checked 2026-11-15T07:48:28Z).

| Input | Path (under the repo, `nov14-sprint/nfl/slate/` unless absolute) | Captured | SHA-256 |
|---|---|---|---|
| Shared Sunday odds feed (5 Louisiana books: draftkings, fanduel, betmgm, espnbet = theScore Bet, betrivers) | `/Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json` | 2026-11-15T06:55:06Z | 2a50d6951366342f8656ee01e113c44cceff0acdfa027ea933f9286c0c73d56f |
| ESPN core propBets for DraftKings (lines only, no prices; 874 files, 24 roster files with injury entries) | `inputs/props-espn-propbets.20261115T065800Z/` (MANIFEST.json) | 2026-11-15T06:58:56Z | MANIFEST sha256 cbee7a6b7f5fd69034f90659da05cffcb13da235d1fa9a3af8d72806c0533874 |
| Integrator's NFL.com game-log form file (191 player logs, 191 career pages, all 2026 regular season, last game included 2026-11-09, cutoff exclusive 2026-11-15) | `tools/official_player_logs_20261115.json` | logs 07:08:54Z to 07:09:25Z, careers 07:10:55Z to 07:11:54Z, file rebuilt 07:37:36Z (it now also carries `alias_source` and `confirmed_no_stats_by_player`) | 217b65f973a1b35e053fe786c96ba168544a56540e52593fac9b11a1d01e1119 (I first analysed earlier builds, da4549ed… and f3b3062e…; the form numbers differ from the latest build only by the derived-zero rule in appendix L) |
| NFL.com week-10 injury page (another session's capture) | `inputs/nfl-com-injuries-reg10.20261115T071450Z/nfl_injuries_reg10.html` (https://www.nfl.com/injuries/league/2026/reg10, HTTP 200, 401090 bytes) | 2026-11-15T07:14:50Z | 1d52e7f200cffb958f37b989f1cefe8c1d1ecfd66bc4b9b5428ac62d4c9c03da |
| Integrator's props file, read only | `props_20261115.json` (version 2, available true, 1038 props, 98 excluded) | built 2026-11-15T07:38:37Z | 7f202c76572738e0329e8c9721fbaacee06333008748a019d05880c380b50980 |
| Integrator's appearance sources (club and NFL inactives pages and gamebook rows, stored extracts; used for the inactive and derived-zero labels; I did not open the pages) | `tools/official_appearance_sources_20261115.json` and `tools/appearance_gamebook_rows_20261115.json` | retrieval times are inside each entry (Steelers entry 07:28:18Z) | 911d33f5897f5dbca5f3ba5b429a4bf702768f634b2623d61eafc3fd37c14043 and 70252f41e5f4d8a6d39915d4c170718bc964e18763618b98b1834c58dd9d8461 |
| Warren's prior-line rows (Stat Sniper, third party; **collected by another chat, not by me, not re-fetched**) | `pdf_export/evidence/2026-11-15.json`, `calls[1].recent_appearances.entries` (8 rows: appearance, date, value, prior_line; the file's `prior_line_source_url` names the Stat Sniper page and `source_url` names the NFL.com game log). The file changed while I worked (its layout and sha moved; I re-read it at 07:37Z and the 8 rows are the same). It also now carries role text for Warren, quoted in section 5, which I did not verify. `FOOTBALL_RED_TEAM.md` line 35 cites `results/sunday_20261115_candidates.json` for the same rows (not opened by me) and says the books and quote times are not verified. Source page named there: https://statsniper.com/leagues/nfl/player/jaylen-warren/props/receiving-yards/ | not stated in the rows | file sha 356c5b6651c059ccc22ae83e29e0d831632404e28453f72743bf43754d18de5a (as read 07:37Z; an earlier read was 8f19c754…) |
| Codex's review and decision (reported, not re-derived) | `/Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/Matchup_Review.md` and `Final_Decisions.json` | decided 07:08:57Z | not hashed by me |

My own scripts (all offline, stdlib only, Python 3.9 safe, run as `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I`):

| Script | SHA-256 |
|---|---|
| `tools/props_review.py` | 68d3bd15c523580db7b168e7a1fe77f6e2a8853a19e8ac90500ac7c24ff3bc61 |
| `tools/props_review_tables.py` | 449fcc1d83588f2eaae3af0d2660a21aaf1fe003d785da5d205cd941b5cfc3b0 |
| `tools/props_review_stats.py` | aad5e5823233d602d0c6732a0a48c5bf2470264db80ab8a35397d1dfc5cb3b9b |
| `tools/props_form_check.py` | 5e5ffadc045773fa7d7ad8a164c8e800213af2fc048c5069ae195697b9111f47 |
| `tools/props_injury_xcheck.py` | 978815077a9c190dc6fab9a02eb2b56fcb005198ea7a5733d963a9ca36ed2d24 |
| `tools/props_xcheck_integrator.py` | 210a07cab05b5bf7a86fec36e2a58cb5cf5773d561027fb5802c862176e55454 |

The ESPN lines-only capture was made earlier by this session under the original brief (public keyless pages, no prices). The review scripts read files only. The `espnbet` key in the feed is theScore Bet; I label it **tSB** so it is not confused with ESPN, which is only the source of the DraftKings line check.

## 3. Reconciliation: identity, market, period, line

**Identity (known, 250 of 255 rows matched by name to an ESPN roster).**
- The feed lists one Cardinals running back under two names: "Zonovan Knight" at DraftKings, BetMGM, tSB and BetRivers, and "Bam Knight" at FanDuel. ESPN's Arizona roster (06:58Z capture) has exactly one Knight, "Bam Knight" (athlete 4427728). ESPN's DraftKings propBets for that athlete read receiving 5.5 and rushing 31.5, which are exactly the lines the feed shows for DraftKings under "Zonovan Knight" (5.5 and 31.5). The integrator also aliases the two names, citing an azcardinals.com article (sha 4ee798a5…, which I have not opened). I treat them as one player: **strongly indicated, not verified from the article** (same book, market and line on both sides, one Knight on the roster, plus the integrator's alias source). Merged, rushing is a 5-book ladder (28.5 BetRivers, 29.5 BetMGM and FanDuel, 30.5 tSB, 31.5 DraftKings) and receiving a 4-book ladder (5.5 DraftKings, 6.5 BetMGM, tSB, FanDuel). My `dup_flags` check only catches the same spelling twice, so it could not see this; every other unmatched name is listed below and none has a same-team twin.
- Still unresolved, not guessed: Elijah Dotson, Malik Taylor, Cam Sample (the integrator's NFL.com lookup also fails to find a unique roster match for all three; it excludes them as `identity_unverified`).
- Counts: 255 rows (24 passing yards, 159 receiving, 72 rushing). 0 duplicate flags, 0 unmatched events.

**Market (known).** Three markets only: `player_pass_yds`, `player_rush_yds`, `player_reception_yds`, all full game. They map to ESPN's "(incl. overtime)" yardage types. Overtime treatment at the other four books is **unknown**. There is no anytime touchdown, receptions, longest or alternate-line market in the feed.

**Period (known).** Full game only. No first-half or quarter markets in the feed.

**Line (known).**
- DraftKings feed line against the latest ESPN current line: 239 rows comparable, 237 identical, 2 different (Dohnte Meyers 20.5 in the feed, 19.5 on ESPN; Samaje Perine 4.5 and 5.5). Eight rows have no DraftKings quote in the feed; nine matched rows have no ESPN DraftKings row.
- Books disagree on the line: the median spread between the lowest and highest line on a row is 2.0 yards (maximum 11). Only 19 rows have all books on one line; 19 rows have 4+ books on one line.
- Books per row: 1 book: 8 rows; 2: 7; 3: 17; 4: 52; 5: 171.
- ESPN `lastUpdated` stamps cannot be used for freshness: 67 of 243 unique line records carry a time later than the capture minute (latest 09:56Z, which is in the future of the capture). Treat ESPN timing as unreliable; the feed's 06:55:06Z is the only price time I trust.
- Median hold (the book's built-in margin) by book: DraftKings 5.7%, FanDuel 6.1%, tSB 6.9%, BetMGM 7.0%, BetRivers 7.2%.

## 4. What the market data does and does not say

- Same-line consensus P(over) (vig-free, averaged over books on that exact line) sits near 0.50 for almost every row. Taking the best posted price on each side against that consensus gives a gap of at most -0.0031 (2+ books), -0.0067 (3+ books), -0.0067 (4+ books). No positive gap. This is a check for a free price; it is not a view on who is right.
- Cross-book lock check (Over at one book, Under at another, Over line not above Under line): 247 rows checked, 0 below 1.000. Closest is MarShawn Lloyd rushing (tSB Over 11.5 at +115 with DraftKings Under 11.5 at -118), sum 1.0064. Before limits, rules and the **unverified** Louisiana availability of any book or market, nothing is free.
- Wide ladders (for example 22.5 to 27.5 on Warren) show books disagree, but without a sourced outcome distribution I cannot turn a gap between lines into an expected value, so I do not claim a middle or a shift is profitable.
- The 18 all-gate rows are listed in section G of the appendix; I do not rank them.

## 5. The Codex-named props

Form figures come from the integrator's NFL.com game logs: consecutive 2026 games, week:yards, newest first, no 2025 games, all available games shown. A dash is a game row with no stat line in my parse (the integrator's file labels each such game inactive, or a derived zero where it verified the player appeared); I leave it out of averages, so my counts can differ from the integrator's by its derived zeros (appendix L). "Over today's modal line" is the retro-fit count (today's line applied to past games), not a record against historic lines. Form is descriptive and, with a handful of games, noisy.

### Jaylen Warren, receiving yards (PIT at CIN)

- **Ladder (known, feed 06:55:06Z):** 22.5 BetMGM -115/-115; 23.5 DraftKings -110/-114; 25.5 tSB -105/-125 and FanDuel -113/-113; 27.5 BetRivers -115/-114. The 22.5 line is posted at **one** book. DraftKings (ESPN) opened at 26.5 and is now 23.5.
- **Measure 1: today's-line count (known, retro-fit).** Consecutive 2026 games, all 8 available, nothing from 2025: 8:0 7:36 6:28 5:87 4:33 3:49 2:34 1:27. Over 22.5: **last 5 = 4 of 5** (0, 36, 28, 87, 33), **all available (last 10 = 8 games) = 7 of 8**. The one miss is week 8 at 0 yards. Mean 36.8, median 33.5, last three mean 21.3. The integrator's own counts at DraftKings 23.5 are the same (last 5: 4 over, 1 under; last 10, 8 rows: 7 over, 1 under).
- **Measure 2: record against the line posted at the time (third party, unverified, 8 games).**

  | Appearance | Date | Yards (NFL.com log) | Prior line (Stat Sniper) | Result |
  |---|---|---|---|---|
  | 1 | 2026-09-13 | 27 | 19.5 | over |
  | 2 | 2026-09-20 | 34 | 18.5 | over |
  | 3 | 2026-09-27 | 49 | 26.5 | over |
  | 4 | 2026-10-01 | 33 | 26.5 | over |
  | 5 | 2026-10-11 | 87 | 22.5 | over |
  | 6 | 2026-10-18 | 28 | 28.5 | **under** |
  | 7 | 2026-10-25 | 36 | 25.5 | over |
  | 8 | 2026-11-01 | 0 | 22.5 | **under** |

  **6 of 8 overall (this is Codex's figure; I recount it from the rows), 3 of 5 in the last five, 1 of 3 in the last three** (my arithmetic on the same rows, **estimated**). Prior lines ranged 18.5 to 28.5, mean about 23.8. Yards in all 8 rows equal my NFL.com game-log yards (**known**, I compared them). What is **unknown**: which book posted each prior line, when it was quoted (pregame, or a later snapshot), and whether the archive's lines are the same book-by-book. I did not open the Stat Sniper page; I read the rows another chat stored.
- **How the two fit together.** 7 of 8 says most of his games would have cleared a 22.5 bar. 6 of 8 says he beat what the market asked of him in six of eight. The second bears on whether the market misprices him, and it is the less certain of the two and the weaker one in recent weeks.
- **Break-even at -115 is 53.5% (known arithmetic).** With 8 games a 95% Wilson interval is roughly 53% to 98% for 7 of 8 and 41% to 93% for 6 of 8 (**estimated**, my arithmetic). Both sit on or around break-even at the low end, so the sample cannot tell a 54% prop from a 90% one.
- **Against it:** DraftKings moved 3 yards lower since open and the ladder tops out at 27.5, so the market is not treating his mean (36.8) as his level. Why is **unknown**. Week 8 (0) and the last-three mean (21.3) point the same way. The integrator's quarterback context covers six teams and Pittsburgh is not one of them, so a Rodgers-starts check for today is not in its file. Its `team_starting_qb` field lists Aaron Rodgers for all 8 Pittsburgh games this season (nflverse games.csv, retrieved 2026-11-14T21:16:58Z; second-hand, I did not open the CSV); that says nothing about today.
- **Role (the part that matters most; none of it verified by me).** The integrator's appearance fields (**known** as stored; I read the extracts, not the pages) mark Dowdle **inactive in weeks 3, 4 and 5** (basis: NFL.com inactives articles for weeks 3 and 5, https://www.nfl.com/news/nfl-week-3-inactives-players-ruled-out-sunday-14-games-2026 and https://www.nfl.com/news/nfl-week-5-inactives-players-ruled-out-sunday-2026-season, and the NFL gamebook PDF for week 4) and played in weeks 1, 2, 6, 7 and 8 (weeks 6 to 8: 7, 9 and 15 carries, with 3 and 6 catches in weeks 6 and 7 and none in week 8). Warren's three largest games (49, 33, 87) are exactly the three weeks Dowdle was inactive, and the Stat Sniper prior lines were also higher in two of them (26.5, 26.5; the third was 22.5). Week 8, his 0-yard game: 17 carries for 143 yards and one catch for 0 in a 27 to 6 win, a rush-heavy script (integrator's log). Another chat's evidence file (`pdf_export/evidence/2026-11-15.json`, Warren call) says: "Since Rico Dowdle returned, Warren has run 46% of routes and drawn 10% of targets," citing a steelers.com "Matt's Stats Week 10" article that I did not open, and that "Only BetMGM offered 22.5". I have no snap, route or target data of my own. So the 7 of 8 and the 6 of 8 mix a period without Dowdle and a period with him, and the market line sits closer to the second. **Whether Warren keeps a passing-down role against Cincinnati is unknown.**
- **Injuries:** Warren is not on the ESPN roster injury list (06:58:49Z) and not on the NFL.com page (07:14:50Z). That is "not on the report", not "healthy"; Pat Freiermuth (PIT) is on ESPN as Questionable. Final inactives are due about 90 minutes before kickoff, which is about 23:50Z for this game.
- **The four conditions for the one decision:** (1) Rodgers is confirmed as the starter; (2) Warren is not on the inactive list and not restricted; (3) the 22.5 line is still available at -115 or better (Codex: pass if the exact threshold disappears; at 23.5 the form counts above are the same, but that is a different price and a different decision, which I have not assessed); (4) the personal price and Louisiana availability are confirmed, which the integrator marks `personal_price_verified: false` and I cannot confirm. If any fails, pass.

### The other props Codex named (none is a pick; one line each)

Form column = games over today's modal line (retro-fit), consecutive 2026 games with a stat line, all available shown. No historic lines are available for any of these.

| Prop (game) | Ladder in the feed | Form (known, retro-fit) | Read |
|---|---|---|---|
| Rico Dowdle receiving (PIT at CIN) | 13.5 to 15.5; DK opened 14.5 | played 5 of 8 weeks (inactive weeks 3 to 5, second-hand), median 9.0, 2 of 5 over 13.5 | Form does not support the over; mean 16.4 is carried by one 45 |
| Joe Burrow rushing (PIT at CIN) | 6.5 to 7.5; DK 6.5 to 7.5 | 6 of 8 over 6.5, mean 9.6 | Form leans over at 6.5; DK moved up to 7.5; nothing sourced beyond that |
| Joe Burrow passing | 289.5 to 293.5; DK 286.5 to 291.5 | 3 of 8 over 289.5, mean 298.2, median 276.5 | Two 400+ games lift the mean; median is below the line |
| Emmett Johnson rushing (KC at ATL) | 72.5 to 75.5; DK open 9.5, now 72.5 | 0 of 8 over; best game 34, mean 13.9 | **Largest form-versus-line gap in the screen.** The open of 9.5 may be a placeholder; I cannot tell |
| Emmett Johnson receiving | 24.5 to 27.5; DK open 12.5, now 27.5 | 2 of 8 over 24.5, mean 29.6 (one 128) | Same pattern, smaller |
| John Metchie III receiving (CAR at NO) | 6.5 to 9.5; DK open 12.5, now 7.5 | 6 of 6 over; every game above the whole ladder | Market far below form; reason unexplained (Xavier Legette is Questionable on both sources, which does not explain it) |
| Jordan Love passing (MIN at GB) | 249.5 to 256.5 | 7 of 9 over 254.5, mean 290.9 | Nothing flagged |
| Brock Bowers receiving (SEA at LV) | 58.5 to 61.5; DK 56.5 to 58.5 | 7 of 7 over; range 70 to 116, mean 94.0 | Market far below form; no injury on either source; reason unexplained |
| Jaxon Smith-Njigba receiving | 87.5 to 90.5 | 7 of 9 over 89.5, mean 115.1 | Nothing flagged |

**Johnson and the Chiefs backfield (inference, not fact).** NFL.com lists Chiefs running backs Kenneth Walker III (groin, did not practise, Questionable) and Jaydn Ott (hamstring, Questionable). That is **known**. A link to Johnson's lines (72.5 rushing against a season mean of 13.9) is **my inference**: the role link is unverified, and the integrator's flag for Johnson reads "no adverse designation found", which does not see teammates.

**Form-versus-line screen (appendix section J).** Five rows have every one of at least six consecutive 2026 games on one side of the whole ladder (Ty Johnson rushing, Emmett Johnson rushing and Jaylen Wright rushing below it; Metchie and Bowers receiving above it). I did not rank the other 250 rows on form, because screening 255 rows by the biggest gap is multiple-comparison mining, and the market may be pricing role, injury or game script that box scores do not show. These are research prompts only, and they are retro-fit counts against today's lines.

## 6. Injuries (ESPN roster against the NFL.com page)

- Seventeen prop rows carry an ESPN roster flag at 06:58:49Z: A. St. Brown, A.J. Brown, Stevenson (two props), Vaki, Wilson, Cooper, Mitchell, Legette, Etienne (two), Boston, Addison, Bell (Doubtful), Spears, Allen, Freiermuth. All are Questionable except Bell.
- Of the 15 flagged players, 14 are also on the NFL.com page with the same game status. **Freiermuth (PIT, receiving 24.5) is on ESPN only**: ESPN says Questionable as of 2026-11-14T17:39Z and NFL.com shows no row at 07:14:50Z. The two disagree and I cannot tell which is newer.
- The NFL.com page lists players on the week-10 injury report, including practice-only rows with no game status. 36 prop players are on it with no ESPN flag (for example Goff, Maye, Mahomes, Rice, Kelce, Hubbard, Kamara, Taylor, Stafford, Smith-Njigba, McCaffrey, Washington); almost all are Full or Limited Participation with no game designation. Absence from the page means "not on the report at 07:14:50Z", not "healthy".
- The integrator used an earlier NFL.com capture (06:57:08Z, sha 3d6bb616…). Mine differs only in timing.
- Final inactives are not in any file. They come about 90 minutes before each kickoff: the first kickoff is 14:30Z, so the first inactives land near 13:00Z.

## 7. Comparison with the integrator's `props_20261115.json`

- **Quotes reconcile exactly.** Every (player, market, book, line) quote in my read of the feed is in the integrator's file (1038 in `props`, 98 in `excluded_props`), 1136 of 1136, with identical Over and Under prices. The integrator has no quote I lack. Its exclusion reasons (68 `game_status_pending`, 3 `identity_unverified`, 30 `no_verified_recent_yardage`; the 3 identity rows also carry the yardage reason, so the reasons are not exclusive) are its own rules; I did not re-derive them.
- **Form counts reconcile, and every difference is a documented rule difference.** At the DraftKings line, my over/under counts across each player's available consecutive 2026 games (at most 10) equal the integrator's for 198 of 244 comparable rows. In the other 46 the over counts are equal and the integrator's under count is higher by exactly its `included_derived_zeros` (games it verified the player appeared in, from game stats, a gamebook or a club source, but where the page has no stat line; it counts them as 0) less any games where only the market cell is blank beside other filled cells (I already count those as 0). 46 of the 46 fit that rule exactly. It is a rule difference, not an error: the integrator's rule is the better one because it rests on a verified appearance, and it leaves verified inactive games out, as I do. See appendix section L.
- **A naming risk in the integrator's file:** each prop carries `historical_results_at_current_line` with `last_5` and `last_10`. Those are today's-line counts on 2026 log rows (the retro-fit), not results against historic lines, and `last_10` is "all available 2026 games, at most 9". See section 10.
- **What the integrator's per-player flags miss:** teammate injuries and role (Johnson above), and a Pittsburgh quarterback context entry (Warren above).
- **Open flag on its side:** `personal_price_verified` is false, so no price in either file is confirmed available to Matthew.
- The integrator notes that multi-book quotes are not independent observations (books copy one another). I agree and treat the 5-book ladders as one noisy read, not five.

## 8. Missing, by label

**Unknown (not in any file I have):**
- Historic prop lines for anyone but Warren. For Warren: which book and which quote time each Stat Sniper prior line carries, and whether the archive matches the line a bettor could actually get. Without historic lines there is no past-only test against the market.
- A sourced outcome distribution for any stat, so no EV for a cross-line shift or a middle.
- Final inactives and starting quarterbacks (Rodgers for Pittsburgh in particular).
- Louisiana availability of each book and market, and the price Matthew would actually get.
- Anytime touchdown, receptions and alternate-line markets (not in the feed).
- Overtime treatment at books other than DraftKings.
- Whether the integrator's appearance classification (inactive versus derived zero) is right in every case: it is its own sourcing, which I did not open, and I only reconciled my counts to it.
- Why Warren, Johnson, Metchie and Bowers lines sit where they do against their form; Warren's passing-down role and his route and target share (the 46% and 10% figures are another chat's, from a steelers.com article I did not open); whether Dowdle plays today.
- The unresolved identities after the Knight merge: Dotson, Taylor, Sample. (The Knight alias source is the integrator's; I did not open it.)
- Travis Hunter's receiving form: the integrator supplies `hunter_receiving` box-score rows (some "Derived zero"); my script does not handle his defensive-table layout and I did not merge them.
- Whether the Freiermuth difference (ESPN Questionable, NFL.com no row) is stale data on one side.
- ESPN `lastUpdated` reliability (67 of 243 records are timestamped after capture).
- Whether any other chat's team-level "last 5 / last 10" stays inside 2026 (I checked player form only; see section 10).

**Estimated (mine):** the 95% intervals on Warren's 7 of 8 and 6 of 8; Warren's 3 of 5 and 1 of 3 on prior lines (my arithmetic on Stat Sniper rows I did not collect); every form mean, median and over-count (descriptive, not predictive); vig-free consensus probabilities (book-average of per-book vig-free implied probabilities).

**Known (cited above):** the prices and lines in the feed; the DraftKings lines on ESPN; the game logs and season totals (244 of 244 players with a season total reconcile: the sum of the game-log yards equals the career-page total, 0 mismatches; 5 have no season total); Warren's 8 game yards agree between NFL.com and the Stat Sniper rows; the injury statuses at their stamps.

## 9. Before kickoff (cheap checks that would change the picture)

1. Re-read the feed for the Warren ladder (is 22.5 still at BetMGM, at what price?). This needs a fresh price capture, which this task did not authorize; it is the integrator's or Codex's call.
2. Pittsburgh and Cincinnati inactives (about 23:50Z) and the Rodgers start.
3. Kansas City inactives (about 16:30Z) before any Chiefs prop.
4. Carolina and New Orleans inactives (about 16:30Z) before Metchie or Legette.

## 10. Data that could be misread (passed to Matthew, last-5/10 clarification)

Matthew's rule: last 5 and last 10 are consecutive current-season player appearances, chiefly for props; do not pad from 2025; show today's-line results apart from results against historic lines. I checked the files below against it. These are other sessions' files, so I list them and did not edit them.

| Where | What it shows | Why it could be misread | Suggested fix (owner decides) |
|---|---|---|---|
| `props_20261115.json`, each prop's `historical_results_at_current_line` with `last_5` and `last_10` (built by `tools/build_props.py` line 333) | Over and under counts of the player's 2026 games against **today's** line | Reads like a record against historic lines. `last_10` is really "all available 2026 games, at most 9". | A `basis` note on the field: "today's line applied to consecutive 2026 games; not historic lines" |
| `sunday_view.py` line 56 (the Warren paragraph in `Sunday NFL.html`) | 4 of last 5 and 7 of 8 at 22.5, then "beat the actual historical lines in 6 of 8" | The two measures are separated, which is right. But the 6 of 8 is not labelled third party and unverified there, and the last-five figure on actual lines (3 of 5) is not shown | Add "(Stat Sniper, books and quote times unverified)" and the 3 of 5 |
| `FOOTBALL_RED_TEAM.md` line 11 (summary row) | "Over 22.5 in 4 of his last 5 and 7 of 8 this season; 6 of 8 against each game's own line" | Compressed. Lines 144 to 157 of the same file label the measures correctly; the summary row does not say the 4/5 and 7/8 are today's-line counts or that the 6/8 is unverified | Label the three counts in the row |
| `Matchup_Review.md`, "How Warren performed against each week's line" | 7 of 8 at today's 22.5; 6 of 8 against each prior game's line; says the archive has no verified quote time or book and that neither is a forecast probability | Correctly worded. Included so you can see the label is there | None |
| `INPUT_HANDOFF.md` line 25 (team-level `Sunday_matchup_checks.json`) | "last five and available last ten for each team" | I did not check whether the team counts stay inside 2026 (`PDF_EDITORIAL.md` records that an earlier team last-10 crossed into 2025 and was withdrawn). Matthew's clarification is chiefly about player props, so team figures should say "2026, n=…" | Label every team count with season and n |
| My own appendix section I | "Over modal line" counts for all rows | Retro-fit counts against today's modal line; relabelled in this file | Already relabelled |
| Derived zeros in `historical_results_at_current_line` (`included_derived_zeros`, `yards_basis`) | The integrator counts a game where it verified the player appeared but the page shows no stat line as 0 yards; I leave an all-empty row out | `last_5` and `last_10` then include games with no stat line, so "n games" is appearances, not stat lines. Under counts differ from mine in 46 of 244 rows, all explained (appendix L) | Keep the rule, and print the derived-zero count beside each count in any report |

---

# Appendix: generated tables

Sections A to H come from `props_review_tables.py`, I and J from `props_form_check.py`, K from `props_injury_xcheck.py`, L from `props_xcheck_integrator.py`. Prices are American odds. `tSB` = theScore Bet (feed key `espnbet`). Sections I and J use consecutive 2026 games only and count them against today's line.


### A. Quarterback passing-yards lines (24 starters, full game)

| Game | QB | Line (books at that line) | Other lines | Over best | Under best | Consensus P(over) | Flags |
|---|---|---|---|---|---|---|---|
| New England Patriots at Detroit Lions | Jared Goff | 268.5 (2) | 265.5 (1), 267.5 (1), 272.5 (1) | FD -113 | tSB -110 | 0.505 | - |
| New England Patriots at Detroit Lions | Drake Maye | 258.5 (1) | 260.5 (1), 261.5 (1), 263.5 (1), 264.5 (1) | BR -136 | BR -106 | 0.528 | - |
| Buffalo Bills at New York Jets | Josh Allen | 235.5 (2) | 232.5 (1), 233.5 (1), 234.5 (1) | DK -112 | DK -112 | 0.500 | DK-vs-ESPN line not confirmed |
| Buffalo Bills at New York Jets | Geno Smith | 221.5 (1) | 223.5 (1), 224.5 (1), 225.5 (1) | FD -113 | FD -113 | 0.500 | - |
| Carolina Panthers at New Orleans Saints | Bryce Young | 243.5 (1) | 247.5 (1), 248.5 (1), 249.5 (1), 251.5 (1) | MGM -125 | MGM -105 | 0.520 | - |
| Carolina Panthers at New Orleans Saints | Tyler Shough | 252.5 (3) | 250.5 (2) | FD -113 | FD -113 | 0.500 | - |
| Houston Texans at Cleveland Browns | C.J. Stroud | 244.5 (2) | 241.5 (1), 245.5 (2) | FD -113 | FD -113 | 0.500 | - |
| Houston Texans at Cleveland Browns | Deshaun Watson | 208.5 (2) | 201.5 (1), 209.5 (1), 210.5 (1) | FD -113 | FD -113 | 0.500 | - |
| Jacksonville Jaguars at Tennessee Titans | Trevor Lawrence | 246.5 (2) | 240.5 (1), 242.5 (1), 247.5 (1) | DK -111 | DK -113 | 0.499 | - |
| Jacksonville Jaguars at Tennessee Titans | Cam Ward | 195.5 (2) | 194.5 (1), 198.5 (1), 200.5 (1) | DK -111 | DK -113 | 0.499 | - |
| Kansas City Chiefs at Atlanta Falcons | Patrick Mahomes | 237.5 (1) | 238.5 (1), 239.5 (1), 240.5 (1), 245.5 (1) | tSB -115 | tSB -115 | 0.500 | - |
| Kansas City Chiefs at Atlanta Falcons | Michael Penix Jr. | 217.5 (2) | 215.5 (1), 219.5 (2) | DK -113 | DK -111 | 0.501 | - |
| Miami Dolphins at Indianapolis Colts | Daniel Jones | 185.5 (2) | 178.5 (1), 183.5 (1), 187.5 (1) | tSB -110 | DK -112 | 0.495 | - |
| Miami Dolphins at Indianapolis Colts | Kyle McCord | 158.5 (2) | 157.5 (1), 161.5 (1), 162.5 (1) | FD -113 | FD -113 | 0.498 | - |
| Minnesota Vikings at Green Bay Packers | Jordan Love | 254.5 (2) | 249.5 (1), 251.5 (1), 256.5 (1) | tSB -110 | DK -111 | 0.496 | - |
| Minnesota Vikings at Green Bay Packers | Kirk Cousins | 226.5 (2) | 232.5 (2) | BR -115 | BR -114 | 0.500 | - |
| Los Angeles Rams at Arizona Cardinals | Matthew Stafford | 212.5 (2) | 209.5 (1), 211.5 (1), 220.5 (1) | tSB -105 | FD -113 | 0.490 | - |
| Los Angeles Rams at Arizona Cardinals | Carson Beck | 172.5 (1) | 175.5 (1), 177.5 (1), 179.5 (1) | DK -112 | DK -112 | 0.500 | - |
| Seattle Seahawks at Las Vegas Raiders | Drew Lock | 202.5 (3) | 203.5 (1), 205.5 (1) | tSB -110 | DK -112 | 0.497 | - |
| Seattle Seahawks at Las Vegas Raiders | Fernando Mendoza | 177.5 (1) | 180.5 (1), 182.5 (1), 184.5 (1), 188.5 (1) | BR -114 | BR -117 | 0.497 | - |
| San Francisco 49ers at Dallas Cowboys | Dak Prescott | 273.5 (2) | 269.5 (1), 270.5 (1), 272.5 (1) | tSB -110 | DK -113 | 0.494 | - |
| San Francisco 49ers at Dallas Cowboys | Brock Purdy | 259.5 (2) | 256.5 (1), 261.5 (2) | BR -117 | tSB -105 | 0.512 | - |
| Pittsburgh Steelers at Cincinnati Bengals | Joe Burrow | 289.5 (2) | 291.5 (1), 292.5 (1), 293.5 (1) | FD -113 | FD -113 | 0.500 | - |
| Pittsburgh Steelers at Cincinnati Bengals | Aaron Rodgers | 240.5 (3) | 238.5 (1), 241.5 (1) | DK -112 | DK -112 | 0.500 | DK-vs-ESPN line not confirmed |

### B. Injury-flagged props (ESPN roster status at 06:58:49Z, before final inactives)

| Game | Player | Market | Status (ESPN, as of) | Modal line |
|---|---|---|---|---|
| New England Patriots at Detroit Lions | Amon-Ra St. Brown | rec yds | Questionable (2026-11-13T16:45Z) | 82.5 |
| New England Patriots at Detroit Lions | A.J. Brown | rec yds | Questionable (2026-11-13T16:58Z) | 50.5 |
| New England Patriots at Detroit Lions | Rhamondre Stevenson | rec yds | Questionable (2026-11-13T17:07Z) | 21.5 |
| New England Patriots at Detroit Lions | Rhamondre Stevenson | rush yds | Questionable (2026-11-13T17:07Z) | 46.5 |
| New England Patriots at Detroit Lions | Sione Vaki | rush yds | Questionable (2026-11-13T17:45Z) | 12.5 |
| Buffalo Bills at New York Jets | Garrett Wilson | rec yds | Questionable (2026-11-14T17:18Z) | 60.5 |
| Buffalo Bills at New York Jets | Omar Cooper Jr. | rec yds | Questionable (2026-11-14T17:15Z) | 36.5 |
| Buffalo Bills at New York Jets | Adonai Mitchell | rec yds | Questionable (2026-11-14T17:20Z) | 34.5 |
| Carolina Panthers at New Orleans Saints | Xavier Legette | rec yds | Questionable (2026-11-14T18:56Z) | 11.5 |
| Carolina Panthers at New Orleans Saints | Travis Etienne Jr. | rec yds | Questionable (2026-11-14T21:11Z) | 10.5 |
| Carolina Panthers at New Orleans Saints | Travis Etienne Jr. | rush yds | Questionable (2026-11-14T21:11Z) | 30.5 |
| Houston Texans at Cleveland Browns | Denzel Boston | rec yds | Questionable (2026-11-13T18:34Z) | 43.5 |
| Minnesota Vikings at Green Bay Packers | Jordan Addison | rec yds | Questionable (2026-11-13T21:17Z) | 49.5 |
| Miami Dolphins at Indianapolis Colts | Chris Bell | rec yds | Doubtful (2026-11-13T22:10Z) | 13.5 |
| Jacksonville Jaguars at Tennessee Titans | Tyjae Spears | rush yds | Questionable (2026-11-13T20:43Z) | 9.5 |
| Los Angeles Rams at Arizona Cardinals | Davis Allen | rec yds | Questionable (2026-11-14T00:18Z) | 13.5 |
| Pittsburgh Steelers at Cincinnati Bengals | Pat Freiermuth | rec yds | Questionable (2026-11-14T17:39Z) | 24.5 |

### C. Identity not resolved (name absent from both ESPN rosters at capture; not guessed)

- Elijah Dotson, Kansas City Chiefs at Atlanta Falcons, rec yds, books posting: 1, lines: 29.5
- Malik Taylor, Buffalo Bills at New York Jets, rec yds, books posting: 1, lines: 15.5
- Zonovan Knight, Los Angeles Rams at Arizona Cardinals, rec yds, books posting: 3, lines: 5.5, 6.5
- Zonovan Knight, Los Angeles Rams at Arizona Cardinals, rush yds, books posting: 4, lines: 28.5, 29.5, 30.5, 31.5
- Cam Sample, Pittsburgh Steelers at Cincinnati Bengals, rec yds, books posting: 1, lines: 4.5

### D. Thin coverage (2 books or fewer)

- Elijah Dotson (Kansas City Chiefs at Atlanta Falcons), rec yds, 1 book(s): tSB
- Geno Smith (Buffalo Bills at New York Jets), rush yds, 2 book(s): DK; FD
- Malik Taylor (Buffalo Bills at New York Jets), rec yds, 1 book(s): tSB
- Ray Davis (Buffalo Bills at New York Jets), rush yds, 1 book(s): tSB
- Ty Johnson (Buffalo Bills at New York Jets), rush yds, 1 book(s): tSB
- Trevor Etienne (Carolina Panthers at New Orleans Saints), rush yds, 2 book(s): DK; FD
- Foster Moreau (Houston Texans at Cleveland Browns), rec yds, 2 book(s): MGM; DK
- Myles Price (Minnesota Vikings at Green Bay Packers), rec yds, 2 book(s): DK; FD
- Kirk Cousins (Minnesota Vikings at Green Bay Packers), rush yds, 2 book(s): DK; FD
- Chris Bell (Miami Dolphins at Indianapolis Colts), rec yds, 1 book(s): BR
- Tyjae Spears (Jacksonville Jaguars at Tennessee Titans), rush yds, 2 book(s): DK; FD
- Bam Knight (Los Angeles Rams at Arizona Cardinals), rec yds, 1 book(s): FD
- Bam Knight (Los Angeles Rams at Arizona Cardinals), rush yds, 1 book(s): FD
- Deebo Samuel (San Francisco 49ers at Dallas Cowboys), rush yds, 2 book(s): DK; FD
- Cam Sample (Pittsburgh Steelers at Cincinnati Bengals), rec yds, 1 book(s): tSB

### E. DraftKings line mismatches, feed 06:55Z against ESPN 06:58Z

- Dohnte Meyers (Pittsburgh Steelers at Cincinnati Bengals), rec yds: feed DK 20.5; ESPN current 19.5, open 20.5, ESPN lastUpdated 2026-11-15T09:56Z
- Samaje Perine (Pittsburgh Steelers at Cincinnati Bengals), rec yds: feed DK 4.5; ESPN current 5.5, open 4.5, ESPN lastUpdated 2026-11-15T09:56Z

### F. In the ESPN DraftKings capture but not in the shared feed (full-game yards and the matching feed markets only)

0 ESPN rows. By market: {}.

### F2. Cross-book lock check (Over at one book, Under at another, Over line not above Under line)

247 rows checked. Smallest combined implied probability 1.0064 (below 1.000 would be a guaranteed profit before limits, rules and the unverified Louisiana availability); median 1.0543; rows below 1.000: 0.

| Closest five | Over | Under | Sum |
|---|---|---|---|
| MarShawn Lloyd, rush yds (Minnesota Vikings @ Green Bay Packers) | tSB 11.5 @ +115 | DK 11.5 @ -118 | 1.0064 |
| Bhayshul Tuten, rec yds (Jacksonville Jaguars @ Tennessee Titans) | MGM 11.5 @ -120 | tSB 11.5 @ +110 | 1.0216 |
| Ben Yurosek, rec yds (Minnesota Vikings @ Green Bay Packers) | BR 9.5 @ -110 | FD 9.5 @ +100 | 1.0238 |
| Daniel Jones, rush yds (Miami Dolphins @ Indianapolis Colts) | BR 7.5 @ -110 | tSB 7.5 @ +100 | 1.0238 |
| Germie Bernard, rec yds (Pittsburgh Steelers @ Cincinnati Bengals) | DK 49.5 @ -111 | tSB 49.5 @ +100 | 1.0261 |

### G. Passed every gate (identity, 4+ books on the line, no injury flag, DraftKings equals ESPN)

18 of 255 rows. These are market-quality gates only. They say nothing about whether the line is wrong.

| Game | Player | Market | Line (books) | Over best | Under best | P(over) consensus |
|---|---|---|---|---|---|---|
| Carolina Panthers @ New Orleans Saints | Chuba Hubbard | rec yds | 18.5 (4) | FD -113 | FD -113 | 0.501 |
| Carolina Panthers @ New Orleans Saints | Devaughn Vele | rec yds | 29.5 (4) | DK -113 | DK -111 | 0.503 |
| Houston Texans @ Cleveland Browns | C.J. Stroud | rush yds | 8.5 (4) | FD -113 | tSB -110 | 0.502 |
| Houston Texans @ Cleveland Browns | Dylan Sampson | rush yds | 18.5 (4) | BR -110 | DK -109 | 0.501 |
| Jacksonville Jaguars @ Tennessee Titans | Brenton Strange | rec yds | 35.5 (4) | DK -112 | MGM -111 | 0.502 |
| Jacksonville Jaguars @ Tennessee Titans | Chimere Dike | rec yds | 29.5 (4) | DK -109 | FD -113 | 0.498 |
| Jacksonville Jaguars @ Tennessee Titans | Tony Pollard | rec yds | 8.5 (4) | DK -113 | DK -111 | 0.500 |
| Kansas City Chiefs @ Atlanta Falcons | Michael Penix Jr. | rush yds | 7.5 (4) | MGM -111 | DK -107 | 0.501 |
| Miami Dolphins @ Indianapolis Colts | Daniel Jones | rush yds | 7.5 (4) | BR -110 | tSB +100 | 0.509 |
| Miami Dolphins @ Indianapolis Colts | Jaylen Wright | rush yds | 12.5 (4) | DK -105 | MGM -110 | 0.499 |
| Minnesota Vikings @ Green Bay Packers | Aaron Jones | rec yds | 10.5 (4) | BR -112 | DK -108 | 0.503 |
| Minnesota Vikings @ Green Bay Packers | Jordan Love | rush yds | 3.5 (4) | FD -113 | DK -107 | 0.509 |
| Los Angeles Rams @ Arizona Cardinals | Elijah Higgins | rec yds | 19.5 (4) | DK -107 | FD -113 | 0.496 |
| Seattle Seahawks @ Las Vegas Raiders | Jadarian Price | rec yds | 11.5 (4) | BR -110 | DK -110 | 0.498 |
| Seattle Seahawks @ Las Vegas Raiders | Zach Charbonnet | rec yds | 9.5 (4) | DK -108 | FD -113 | 0.499 |
| Seattle Seahawks @ Las Vegas Raiders | Mike Washington Jr. | rush yds | 26.5 (4) | FD -113 | FD -113 | 0.500 |
| San Francisco 49ers @ Dallas Cowboys | Brock Purdy | rush yds | 19.5 (4) | DK -112 | DK -112 | 0.500 |
| Pittsburgh Steelers @ Cincinnati Bengals | Ja'Marr Chase | rec yds | 89.5 (4) | DK -112 | DK -112 | 0.501 |

### H. Props named in Codex's Matchup_Review.md: the feed ladder for each (price shown as Over / Under)

| Player, market | Ladder in the 06:55Z feed (line: book over/under) | DraftKings on ESPN: open to current | ESPN roster status |
|---|---|---|---|
| Jaylen Warren, rec yds (Pittsburgh Steelers @ Cincinnati Bengals) | 22.5: MGM -115/-115; 23.5: DK -110/-114; 25.5: tSB -105/-125, FD -113/-113; 27.5: BR -115/-114 | 26.5 to 23.5 | none listed |
| Rico Dowdle, rec yds (Pittsburgh Steelers @ Cincinnati Bengals) | 13.5: DK -110/-114, FD -113/-113; 14.5: MGM -111/-120, tSB -105/-125; 15.5: BR -113/-118 | 14.5 to 13.5 | none listed |
| Joe Burrow, rush yds (Pittsburgh Steelers @ Cincinnati Bengals) | 6.5: BR -114/-117, tSB -125/-105, FD -113/-113; 7.5: MGM -110/-120, DK -110/-114 | 6.5 to 7.5 | none listed |
| Joe Burrow, pass yds (Pittsburgh Steelers @ Cincinnati Bengals) | 289.5: tSB -115/-115, FD -113/-113; 291.5: DK -112/-112; 292.5: MGM -115/-115; 293.5: BR -114/-117 | 286.5 to 291.5 | none listed |
| Emmett Johnson, rush yds (Kansas City Chiefs @ Atlanta Falcons) | 72.5: DK -113/-111; 73.5: MGM -115/-115, FD -113/-113; 74.5: tSB -110/-120; 75.5: BR -115/-114 | 9.5 to 72.5 | none listed |
| Emmett Johnson, rec yds (Kansas City Chiefs @ Atlanta Falcons) | 24.5: MGM -120/-110, BR -118/-113, tSB -130/+100; 25.5: FD -113/-113; 27.5: DK -109/-115 | 12.5 to 27.5 | none listed |
| John Metchie III, rec yds (Carolina Panthers @ New Orleans Saints) | 6.5: MGM -120/-110; 7.5: DK -108/-117, FD -113/-113; 9.5: tSB +120/-155 | 12.5 to 7.5 | none listed |
| Jordan Love, pass yds (Minnesota Vikings @ Green Bay Packers) | 249.5: BR -114/-117; 251.5: FD -113/-113; 254.5: DK -113/-111, tSB -110/-120; 256.5: MGM -105/-125 | 253.5 to 254.5 | none listed |
| Brock Bowers, rec yds (Seattle Seahawks @ Las Vegas Raiders) | 58.5: BR -113/-118, DK -114/-110, FD -113/-113; 59.5: tSB -115/-115; 61.5: MGM -115/-115 | 56.5 to 58.5 | none listed |
| Jaxon Smith-Njigba, rec yds (Seattle Seahawks @ Las Vegas Raiders) | 87.5: MGM -115/-115; 88.5: FD -113/-113; 89.5: BR -114/-117, tSB -120/-110; 90.5: DK -110/-114 | 89.5 to 90.5 | none listed |

### I. Form against today's posted line (nfl.com 2026 game logs captured by the integrator, 07:08Z to 07:11Z; descriptive retro-fit, not a test)

Per-game values are consecutive 2026 regular-season games, most recent first, as `week:yards`; no 2025 games are added, and every available game is shown (no player has more than 9, so "last 10" means all of them). A dash means no stat line that week (inactive, not used or not targeted; the page does not say which). The hit count applies TODAY's modal line to those past games (a retro-fit: the line posted for each game at the time is not used) out of games with a stat line.

| Player, market (game) | Modal line today (books) | Games with stat line | Per game, newest first | Mean / median / last 3 | Games over today's modal line (retro-fit) | Season total check |
|---|---|---|---|---|---|---|
| Jaylen Warren, rec yds (Pittsburgh Steelers @ Cincinnati Bengals) | 25.5 (2 books) | 8 of 8 | 8:0 7:36 6:28 5:87 4:33 3:49 2:34 1:27 | 36.8 / 33.5 / 21.3 | 7 of 8 | log sum equals season total |
| Rico Dowdle, rec yds (Pittsburgh Steelers @ Cincinnati Bengals) | 13.5 (2 books) | 5 of 8 | 8:0 7:45 6:9 5:- 4:- 3:- 2:22 1:6 | 16.4 / 9.0 / 18.0 | 2 of 5 | log sum equals season total |
| Joe Burrow, rush yds (Pittsburgh Steelers @ Cincinnati Bengals) | 6.5 (3 books) | 8 of 8 | 9:7 8:10 7:12 5:10 4:6 3:13 2:-1 1:20 | 9.6 / 10.0 / 9.7 | 6 of 8 | log sum equals season total |
| Joe Burrow, pass yds (Pittsburgh Steelers @ Cincinnati Bengals) | 289.5 (2 books) | 8 of 8 | 9:271 8:462 7:292 5:190 4:428 3:282 2:207 1:254 | 298.2 / 276.5 / 341.7 | 3 of 8 | log sum equals season total |
| Emmett Johnson, rush yds (Kansas City Chiefs @ Atlanta Falcons) | 73.5 (2 books) | 8 of 8 | 9:34 8:15 7:0 6:6 4:0 3:17 2:15 1:24 | 13.9 / 15.0 / 16.3 | 0 of 8 | log sum equals season total |
| Emmett Johnson, rec yds (Kansas City Chiefs @ Atlanta Falcons) | 24.5 (3 books) | 8 of 8 | 9:0 8:128 7:17 6:18 4:10 3:0 2:20 1:44 | 29.6 / 17.5 / 48.3 | 2 of 8 | log sum equals season total |
| John Metchie III, rec yds (Carolina Panthers @ New Orleans Saints) | 7.5 (2 books) | 6 of 8 | 9:40 8:14 7:20 6:24 4:37 3:19 2:- 1:- | 25.7 / 22.0 / 24.7 | 6 of 6 | log sum equals season total |
| Jordan Love, pass yds (Minnesota Vikings @ Green Bay Packers) | 254.5 (2 books) | 9 of 9 | 9:372 8:288 7:274 6:276 5:367 4:197 3:312 2:145 1:387 | 290.9 / 288.0 / 311.3 | 7 of 9 | log sum equals season total |
| Brock Bowers, rec yds (Seattle Seahawks @ Las Vegas Raiders) | 58.5 (3 books) | 7 of 9 | 9:111 8:92 7:73 6:70 5:110 4:86 3:116 2:- 1:- | 94.0 / 92.0 / 92.0 | 7 of 7 | log sum equals season total |
| Jaxon Smith-Njigba, rec yds (Seattle Seahawks @ Las Vegas Raiders) | 89.5 (2 books) | 9 of 9 | 9:51 8:118 7:150 6:134 5:102 4:76 3:128 2:155 1:122 | 115.1 / 122.0 / 106.3 | 7 of 9 | log sum equals season total |
| Chuba Hubbard, rec yds (Carolina Panthers @ New Orleans Saints) | 18.5 (4 books) | 8 of 8 | 9:17 8:38 7:27 6:1 4:7 3:28 2:11 1:38 | 20.9 / 22.0 / 27.3 | 4 of 8 | log sum equals season total |
| Devaughn Vele, rec yds (Carolina Panthers @ New Orleans Saints) | 29.5 (4 books) | 8 of 8 | 9:17 7:54 6:42 5:26 4:54 3:39 2:64 1:69 | 45.6 / 48.0 / 37.7 | 6 of 8 | log sum equals season total |
| C.J. Stroud, rush yds (Houston Texans @ Cleveland Browns) | 8.5 (4 books) | 8 of 8 | 9:20 7:4 6:5 5:5 4:12 3:10 2:29 1:15 | 12.5 / 11.0 / 9.7 | 5 of 8 | log sum equals season total |
| Dylan Sampson, rush yds (Houston Texans @ Cleveland Browns) | 18.5 (4 books) | 3 of 4 | 9:21 8:7 7:45 1:- | 24.3 / 21.0 / 24.3 | 2 of 3 | log sum equals season total |
| Brenton Strange, rec yds (Jacksonville Jaguars @ Tennessee Titans) | 35.5 (4 books) | 8 of 8 | 9:22 8:55 6:44 5:68 4:95 3:32 2:17 1:23 | 44.5 / 38.0 / 40.3 | 4 of 8 | log sum equals season total |
| Chimere Dike, rec yds (Jacksonville Jaguars @ Tennessee Titans) | 29.5 (4 books) | 6 of 8 | 8:71 7:0 6:- 5:28 4:15 3:3 2:- 1:7 | 20.7 / 11.0 / 33.0 | 1 of 6 | log sum equals season total |
| Tony Pollard, rec yds (Jacksonville Jaguars @ Tennessee Titans) | 8.5 (4 books) | 8 of 8 | 8:20 7:26 6:0 5:0 4:2 3:22 2:1 1:-1 | 8.8 / 1.5 / 15.3 | 3 of 8 | log sum equals season total |
| Michael Penix Jr., rush yds (Kansas City Chiefs @ Atlanta Falcons) | 7.5 (4 books) | 7 of 9 | 9:50 8:11 7:-1 6:1 5:8 4:-2 3:-2 2:- 1:- | 9.3 / 1.0 / 20.0 | 3 of 7 | log sum equals season total |
| Daniel Jones, rush yds (Miami Dolphins @ Indianapolis Colts) | 7.5 (4 books) | 9 of 9 | 9:11 8:7 7:13 6:30 5:4 4:2 3:5 2:10 1:4 | 9.6 / 7.0 / 10.3 | 4 of 9 | log sum equals season total |
| Jaylen Wright, rush yds (Miami Dolphins @ Indianapolis Colts) | 12.5 (4 books) | 6 of 8 | 9:- 8:5 7:8 5:11 4:7 3:- 2:11 1:-1 | 6.8 / 7.5 / 8.0 | 0 of 6 | log sum equals season total |
| Aaron Jones, rec yds (Minnesota Vikings @ Green Bay Packers) | 10.5 (4 books) | 8 of 8 | 9:5 8:18 7:0 5:4 4:34 3:34 2:0 1:0 | 11.9 / 4.5 / 7.7 | 3 of 8 | log sum equals season total |
| Jordan Love, rush yds (Minnesota Vikings @ Green Bay Packers) | 3.5 (4 books) | 9 of 9 | 9:13 8:0 7:0 6:12 5:6 4:-8 3:0 2:0 1:0 | 2.6 / 0.0 / 4.3 | 3 of 9 | log sum equals season total |
| Elijah Higgins, rec yds (Los Angeles Rams @ Arizona Cardinals) | 19.5 (4 books) | 7 of 9 | 9:11 8:10 7:17 6:28 5:57 4:19 3:20 2:- 1:- | 23.1 / 19.0 / 12.7 | 3 of 7 | log sum equals season total |
| Jadarian Price, rec yds (Seattle Seahawks @ Las Vegas Raiders) | 11.5 (4 books) | 5 of 5 | 9:54 8:8 3:7 2:8 1:6 | 16.6 / 8.0 / 23.0 | 1 of 5 | log sum equals season total |
| Zach Charbonnet, rec yds (Seattle Seahawks @ Las Vegas Raiders) | 9.5 (4 books) | 2 of 3 | 9:9 8:6 7:- | 7.5 / 7.5 / n/a | 0 of 2 | log sum equals season total |
| Mike Washington Jr., rush yds (Seattle Seahawks @ Las Vegas Raiders) | 26.5 (4 books) | 9 of 9 | 9:-3 8:83 7:27 6:43 5:5 4:18 3:54 2:7 1:41 | 30.6 / 27.0 / 35.7 | 5 of 9 | log sum equals season total |
| Brock Purdy, rush yds (San Francisco 49ers @ Dallas Cowboys) | 19.5 (4 books) | 8 of 8 | 9:40 7:5 6:28 5:6 4:29 3:34 2:30 1:29 | 25.1 / 29.0 / 24.3 | 6 of 8 | log sum equals season total |
| Ja'Marr Chase, rec yds (Pittsburgh Steelers @ Cincinnati Bengals) | 89.5 (4 books) | 8 of 8 | 9:155 8:141 7:62 5:77 4:27 3:98 2:75 1:12 | 80.9 / 76.0 / 119.3 | 3 of 8 | log sum equals season total |

### J. Form-versus-market conflict screen (research prompt only, not picks)

Rows with at least 6 consecutive 2026 games with a stat line where every one of those games sits on one side of the entire posted ladder across all books (today's lines applied to past games; a retro-fit). 5 rows: 2 with every game above the highest posted line, 3 with every game below the lowest. A conflict means the market is pricing something the box scores do not show (role, injury, matchup, game script) or the form is stale. It does not say which, and nothing here shows the market is the side that is wrong.

| Player, market (game) | Ladder (low to high) | Games | Range of games | Mean | Direction |
|---|---|---|---|---|---|
| Ty Johnson, rush yds (Buffalo Bills @ New York Jets) | 5.5 to 5.5 | 6 | 0 to 4 | 1.8 | every game below the lowest posted line |
| John Metchie III, rec yds (Carolina Panthers @ New Orleans Saints) | 6.5 to 9.5 | 6 | 14 to 40 | 25.7 | every game above the highest posted line |
| Emmett Johnson, rush yds (Kansas City Chiefs @ Atlanta Falcons) | 72.5 to 75.5 | 8 | 0 to 34 | 13.9 | every game below the lowest posted line |
| Jaylen Wright, rush yds (Miami Dolphins @ Indianapolis Colts) | 12.5 to 12.5 | 6 | -1 to 11 | 6.8 | every game below the lowest posted line |
| Brock Bowers, rec yds (Seattle Seahawks @ Las Vegas Raiders) | 58.5 to 61.5 | 7 | 70 to 116 | 94.0 | every game above the highest posted line |


### K. Injury cross-check: ESPN roster status (06:58:49Z) against the NFL.com week-10 injury page (07:14:50Z)

The NFL.com page lists players on the week-10 injury report. A row with a practice status and no game status carries no game designation. A player absent from the page is not on the report, which is not the same as confirmed healthy. Final inactives come about 90 minutes before each kickoff and are not in either source.

Prop players with an ESPN flag: 15; also on the NFL.com page: 14; on ESPN only: 1. On the NFL.com page without an ESPN flag: 36.

**On both sources**

| Player | Props in the feed | ESPN status | NFL.com row as parsed |
|---|---|---|---|
| Amon-Ra St. Brown | rec yds | Questionable (2026-11-13T16:45Z) | Amon-Ra St. Brown WR Rib Limited Participation in Practice Questionable |
| A.J. Brown | rec yds | Questionable (2026-11-13T16:58Z) | A.J. Brown WR Ankle, Knee Limited Participation in Practice Questionable |
| Rhamondre Stevenson | rec yds, rush yds | Questionable (2026-11-13T17:07Z) | Rhamondre Stevenson RB Knee Limited Participation in Practice Questionable |
| Sione Vaki | rush yds | Questionable (2026-11-13T17:45Z) | Sione Vaki RB Ankle Limited Participation in Practice Questionable |
| Garrett Wilson | rec yds | Questionable (2026-11-14T17:18Z) | Garrett Wilson WR Concussion Full Participation in Practice Questionable |
| Omar Cooper Jr. | rec yds | Questionable (2026-11-14T17:15Z) | Omar Cooper Jr. WR Ankle Full Participation in Practice Questionable |
| Adonai Mitchell | rec yds | Questionable (2026-11-14T17:20Z) | Adonai Mitchell WR Knee Full Participation in Practice Questionable |
| Xavier Legette | rec yds | Questionable (2026-11-14T18:56Z) | Xavier Legette WR Knee Full Participation in Practice Questionable |
| Travis Etienne Jr. | rec yds, rush yds | Questionable (2026-11-14T21:11Z) | Travis Etienne RB Hamstring Full Participation in Practice Questionable |
| Denzel Boston | rec yds | Questionable (2026-11-13T18:34Z) | Denzel Boston WR Toe Limited Participation in Practice Questionable |
| Jordan Addison | rec yds | Questionable (2026-11-13T21:17Z) | Jordan Addison WR Thumb Limited Participation in Practice Questionable |
| Chris Bell | rec yds | Doubtful (2026-11-13T22:10Z) | Chris Bell WR Knee Did Not Participate In Practice Doubtful |
| Tyjae Spears | rush yds | Questionable (2026-11-13T20:43Z) | Tyjae Spears RB Knee Full Participation in Practice Questionable |
| Davis Allen | rec yds | Questionable (2026-11-14T00:18Z) | Davis Allen TE Oblique Limited Participation in Practice Questionable |

**On ESPN only (NFL.com shows no designation at 07:14:50Z; the two sources disagree and I cannot tell which is newer)**

- Pat Freiermuth (rec yds): ESPN Questionable as of 2026-11-14T17:39Z

**On the NFL.com page with no ESPN flag**

| Player | Props in the feed | NFL.com row as parsed |
|---|---|---|
| Jared Goff | pass yds, rush yds | Jared Goff QB Full Participation in Practice |
| Drake Maye | pass yds, rush yds | Drake Maye QB Full Participation in Practice |
| Hunter Henry | rec yds | Hunter Henry TE Limited Participation in Practice |
| Patrick Mahomes | pass yds, rush yds | Patrick Mahomes QB Full Participation in Practice |
| Rashee Rice | rec yds | Rashee Rice WR Full Participation in Practice |
| Travis Kelce | rec yds | Travis Kelce TE Full Participation in Practice |
| Xavier Worthy | rec yds | Xavier Worthy WR Full Participation in Practice |
| Dalton Kincaid | rec yds | Dalton Kincaid TE Full Participation in Practice |
| Chuba Hubbard | rec yds, rush yds | Chuba Hubbard RB Full Participation in Practice |
| Alvin Kamara | rec yds, rush yds | Alvin Kamara RB Full Participation in Practice |
| Noah Fant | rec yds | Noah Fant TE Full Participation in Practice |
| Trevor Etienne | rush yds | Trevor Etienne RB Full Participation in Practice |
| Tank Dell | rec yds | Tank Dell WR Full Participation in Practice |
| Harold Fannin Jr. | rec yds | Harold Fannin Jr. TE Full Participation in Practice |
| Woody Marks | rec yds, rush yds | Woody Marks RB Full Participation in Practice |
| Savion Williams | rec yds | Savion Williams WR Limited Participation in Practice |
| Jonathan Taylor | rec yds, rush yds | Jonathan Taylor RB Full Participation in Practice |
| Jaylen Wright | rush yds | Jaylen Wright RB Full Participation in Practice |
| Jakobi Meyers | rec yds | Jakobi Meyers WR Limited Participation in Practice |
| Bhayshul Tuten | rec yds, rush yds | Bhayshul Tuten RB Limited Participation in Practice |
| Tony Pollard | rec yds, rush yds | Tony Pollard RB Full Participation in Practice |
| Chris Rodriguez Jr. | rush yds | Chris Rodriguez Jr. RB Limited Participation in Practice |
| Matthew Stafford | pass yds, rush yds | Matthew Stafford QB Full Participation in Practice |
| Tyler Higbee | rec yds | Tyler Higbee TE Limited Participation in Practice |
| Colby Parkinson | rec yds | Colby Parkinson TE Full Participation in Practice |
| Bam Knight | rec yds, rush yds | Bam Knight RB Full Participation in Practice |
| Drew Lock | pass yds, rush yds | Drew Lock QB Limited Participation in Practice |
| Jaxon Smith-Njigba | rec yds | Jaxon Smith-Njigba WR Full Participation in Practice |
| AJ Barner | rec yds | AJ Barner TE Full Participation in Practice |
| Rashid Shaheed | rec yds | Rashid Shaheed WR Full Participation in Practice |
| George Pickens | rec yds | George Pickens WR Full Participation in Practice |
| Deebo Samuel | rec yds, rush yds | Deebo Samuel Sr. WR Full Participation in Practice |
| Demarcus Robinson | rec yds | Demarcus Robinson WR Full Participation in Practice |
| Christian McCaffrey | rec yds, rush yds | Christian McCaffrey RB Full Participation in Practice |
| Brevyn Spann-Ford | rec yds | Brevyn Spann-Ford TE Full Participation in Practice |
| Darnell Washington | rec yds | Darnell Washington TE Full Participation in Practice |


### L. Cross-check of the integrator's props_20261115.json (version 2, built 2026-11-15T07:38:37Z) against my read of the same 06:55:06Z feed

Quotes: 1136 (player, market, book, line) quotes in my read; 1136 found in the integrator's file (1038 in `props`, 98 in `excluded_props`); 0 missing; 0 with a different Over or Under price; the integrator has 1136 quotes, 0 of them not in my read.

Form counts at the DraftKings line (last 10 games): 244 compared; 198 identical; 46 different. A difference is expected where the integrator counts a verified appearance with no stat line as a derived zero and I leave that game row out: its over count equals mine and its under count is higher by its derived-zero count less any games where only the market cell is blank beside other filled cells (I already count those as 0 yards). 46 of the 46 differences fit that rule exactly; 69 rows in all carry derived zeros.

| Player, market | DK line | Mine over/under | Integrator over/under | Integrator unreported rows | Integrator derived zeros | Blank-market rows I already count as 0 | Fits the rule |
|---|---|---|---|---|---|---|---|
| Isaac TeSlaa, rec yds | 14.5 | 3/4 | 3/5 | 0 | 1 | 0 | yes |
| Rashee Rice, rec yds | 55.5 | 2/3 | 2/4 | 0 | 1 | 0 | yes |
| Olamide Zaccheaus, rec yds | 8.5 | 1/6 | 1/7 | 0 | 1 | 0 | yes |
| Omar Cooper Jr., rec yds | 37.5 | 3/1 | 3/2 | 0 | 1 | 0 | yes |
| Mason Taylor, rec yds | 15.5 | 4/2 | 4/3 | 0 | 1 | 0 | yes |
| John Metchie III, rec yds | 7.5 | 6/0 | 6/1 | 0 | 1 | 0 | yes |
| Noah Fant, rec yds | 6.5 | 5/1 | 5/2 | 0 | 1 | 0 | yes |
| Dylan Sampson, rec yds | 23.5 | 3/0 | 3/1 | 0 | 1 | 0 | yes |
| Jerry Jeudy, rec yds | 17.5 | 6/2 | 6/3 | 0 | 1 | 0 | yes |
| Foster Moreau, rec yds | 2.5 | 5/1 | 5/3 | 0 | 2 | 0 | yes |
| Dylan Sampson, rush yds | 18.5 | 2/1 | 2/2 | 0 | 1 | 0 | yes |
| Gavin Bartholomew, rec yds | 22.5 | 1/2 | 1/7 | 0 | 5 | 0 | yes |
| Myles Price, rec yds | 10.5 | 1/3 | 1/7 | 0 | 4 | 0 | yes |
| Ben Yurosek, rec yds | 10.5 | 1/2 | 1/3 | 0 | 2 | 1 | yes |
| Kaleb Johnson, rush yds | 29.5 | 3/3 | 3/4 | 0 | 1 | 0 | yes |
| Greg Dulcich, rec yds | 32.5 | 4/3 | 4/4 | 0 | 1 | 0 | yes |
| Deion Burks, rec yds | 17.5 | 1/6 | 1/8 | 0 | 3 | 1 | yes |
| Kevin Coleman Jr., rec yds | 16.5 | 2/5 | 2/6 | 0 | 2 | 1 | yes |
| Anthony Gould, rec yds | 16.5 | 0/1 | 0/6 | 0 | 5 | 0 | yes |
| Ashton Dulin, rec yds | 14.5 | 2/2 | 2/3 | 0 | 2 | 1 | yes |
| Ollie Gordon II, rec yds | 6.5 | 2/5 | 2/6 | 0 | 3 | 2 | yes |
| Ollie Gordon II, rush yds | 75.5 | 3/4 | 3/5 | 0 | 1 | 0 | yes |
| Chimere Dike, rec yds | 29.5 | 1/5 | 1/7 | 0 | 2 | 0 | yes |
| Gunnar Helm, rec yds | 28.5 | 1/6 | 1/7 | 0 | 1 | 0 | yes |
| Calvin Ridley, rec yds | 14.5 | 2/4 | 2/5 | 0 | 1 | 0 | yes |
| Nate Boerkircher, rec yds | 10.5 | 4/3 | 4/4 | 0 | 1 | 0 | yes |
| Brian Thomas Jr, rec yds | 9.5 | 4/3 | 4/4 | 0 | 1 | 0 | yes |
| Josh Cameron, rec yds | 6.5 | 4/2 | 4/4 | 0 | 2 | 0 | yes |
| Tyler Higbee, rec yds | 35.5 | 3/5 | 3/6 | 0 | 1 | 0 | yes |
| Konata Mumpfield, rec yds | 29.5 | 1/7 | 1/8 | 0 | 1 | 0 | yes |
| Tutu Atwell, rec yds | 28.5 | 1/4 | 1/5 | 0 | 1 | 0 | yes |
| Reggie Virgil, rec yds | 23.5 | 2/1 | 2/3 | 0 | 2 | 0 | yes |
| Elijah Higgins, rec yds | 19.5 | 3/4 | 3/6 | 0 | 2 | 0 | yes |
| CJ Daniels, rec yds | 12.5 | 0/0 | 0/3 | 0 | 3 | 0 | yes |
| Davis Allen, rec yds | 12.5 | 4/4 | 4/5 | 0 | 2 | 1 | yes |
| Devin Duvernay, rec yds | 11.5 | 1/1 | 1/8 | 0 | 7 | 0 | yes |
| Simi Fehoko, rec yds | 10.5 | 1/2 | 1/8 | 0 | 7 | 1 | yes |
| Jalen Nailor, rec yds | 11.5 | 4/3 | 4/4 | 0 | 1 | 0 | yes |
| Tory Horton, rec yds | 6.5 | 4/2 | 4/4 | 0 | 2 | 0 | yes |
| Jack Bech, rec yds | 5.5 | 3/0 | 3/2 | 0 | 2 | 0 | yes |
| Jordan Watkins, rec yds | 24.5 | 3/1 | 3/3 | 0 | 2 | 0 | yes |
| Brevyn Spann-Ford, rec yds | 22.5 | 2/6 | 2/7 | 0 | 1 | 0 | yes |
| Kyle Juszczyk, rec yds | 7.5 | 4/2 | 4/3 | 0 | 2 | 1 | yes |
| Germie Bernard, rec yds | 49.5 | 2/5 | 2/6 | 0 | 1 | 0 | yes |
| Mike Gesicki, rec yds | 24.5 | 4/3 | 4/4 | 0 | 1 | 0 | yes |
| Drew Sample, rec yds | 5.5 | 2/2 | 2/6 | 0 | 4 | 0 | yes |


---

## Reproduce (offline, read-only, stdlib only)

```
cd nov14-sprint/nfl/slate
py() { /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I "$@"; }
FEED=/Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json
py tools/props_review.py $FEED inputs/props-espn-propbets.20261115T065800Z ../real/inputs/nfl-public-lines.20261114T225342Z.json review.json
py tools/props_review_stats.py review.json
py tools/props_review_tables.py review.json tables.md                                      # sections A to H
py tools/props_form_check.py review.json tools/official_player_logs_20261115.json form.md  # sections I, J
py tools/props_injury_xcheck.py review.json inputs/nfl-com-injuries-reg10.20261115T071450Z/nfl_injuries_reg10.html inj.md   # section K
py tools/props_xcheck_integrator.py review.json props_20261115.json tools/official_player_logs_20261115.json integ.md       # section L
```

`tools/props_fetch_espn.py` and `tools/props_parse_covers.py` made the ESPN lines-only capture and a Covers parse that was not used for any figure above. Nothing in this review writes to `props_20261115.json`, `slate_20261115.json` or the integrator's `tools/` files.
