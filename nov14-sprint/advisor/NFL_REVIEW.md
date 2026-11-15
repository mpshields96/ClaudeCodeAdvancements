# Advisor review v2: NFL card for Sunday, Nov 15 (final freeze 07:29:44Z)

Written 07:36Z by bot-advisor (local_abcc3d7a). It is read-only: I edited no worker files, and there are no tickets or orders. My scripts live in `advisor/repros/` and write nothing. I made no network calls, live odds checks or new sports calls. Desk, journal and PDF acceptance belong to Codex and are not scored here.

**Final freeze: PASS.** The three engine files match the freeze hashes, the rules hash is unchanged, both calls are the same as at the 07:08:57Z review, the run was before the first kickoff, and there are 0 tickets.

**Second pass on the three open checks:**

| Check | v1 (07:22Z) | v2 (07:36Z) | One line |
|---|---|---|---|
| M5. Health marked known, estimated or unknown | FAIL | **PASS** | Each call carries labelled evidence: price known; football judgment estimated; probability estimated; participation and fill unknown; club report known; and, for KC, the source disagreement known. |
| G2. No unsourced odds, injury or stat values | NOT YET | **NOT YET (narrow)** | The Chiefs and Steelers pages are saved and their hashes match. Still open: the Warren game log has no retrieval time or saved copy, and the afternoon pass's halftime figures have no source at all. |
| G6. Unknowns labelled, open statuses named | NOT YET | **NOT YET (one item)** | KC names its open questionables (Ott, Delane). The Warren call names none of Pittsburgh's: Freiermuth (TE) and Harmon (DT) are Questionable in the slate file and missing from the card. |

**The benchmark shows no proven edge.** Both calls sit below break-even at the market's own estimate. Over 135 decided 2026 games the market beat the model (log loss 0.6223 vs 0.6306), and the fitted blend puts 100% weight on the market. These are process picks, not value bets.

## Files reviewed (hashed 07:33Z)

| File | sha256 (first 16) | mtime |
|---|---|---|
| `nfl/BEST_BETS_SUN_NOV15.md` | 2d5c3b370c8260f0 | 07:32:07Z |
| `nfl/BEST_BETS_SUN_NOV15.html` | 91f957541dd9a7b1 | 07:32:07Z |
| `nfl/slate/results/sunday_20261115_selections.json` | 4e68284cd801d4e5 | 07:32:07Z |
| `nfl/slate/results/sunday_20261115_candidates.json` | 6885d506c57b84b6 | 07:32:07Z |
| `nfl/slate/frozen_picker.json` | a5000e7da2de2e59 (frozen 07:29:44Z) | 07:29:44Z |
| `nfl/slate/picker.py` | 5771a47f31a13731, which matches the freeze | 07:29:44Z |
| `nfl/slate/selection_markets.py` | 91bbfbab0af9460e, which matches the freeze | 07:25:45Z |
| `nfl/slate/selection_decisions.py` | 6898d72cca26951d, which matches the freeze | 07:25:45Z |
| `nfl/slate/PAST_ONLY_TEST.md` | a62dfa80e393b463 | 07:29:45Z |
| `nfl/slate/FOOTBALL_RED_TEAM.md` | 09d2588136d3c649 | 07:31:40Z |
| `nfl/slate/slate_20261115.json` | 8de8f4ae6efc881f | 07:22:09Z |

If any of these changes after 07:36Z, this review is out of date for that file. The three earlier candidate files were kept as `*.superseded_<sha>.json`, which is good provenance. The empty `.picker-write.lock` is still present.

**The calls:**
- **KC ML at DraftKings, -166.** KC at ATL, 18:00Z.
- **Jaylen Warren over 22.5 receiving yards at BetMGM, -115.** PIT at CIN, 01:20Z on Nov 16.
- **Afternoon:** pass.

## The second pass, item by item

Every command below runs from any folder, uses absolute paths and writes nothing.

**Repro A (freeze, sources, evidence labels, Warren counts, open statuses):**
`/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r4_final_freeze.py`

| # | Claim on the card | Expected | Observed (Repro A unless noted) | Result |
|---|---|---|---|---|
| F1 | The final freeze precedes scoring and kickoff | Code hashes match the freeze, and the run is before 14:30Z | All 3 MATCH. Rules 383162cc unchanged. Run 07:32:07Z, decision 07:08:57Z, 0 tickets | PASS |
| F2 | Saved Chiefs and Steelers pages (card lines 29 and 57) | HTTP 200, a retrieval time, and a hash that matches the file | Both 200. Retrieved 07:24:59Z and 07:25:00Z. Both hashes MATCH (6ef05c5d…, b7baa35e…) | PASS |
| F3 | Walker OUT on the Saturday report vs the older league table (lines 29-31) | The team page says Out, and the card labels the disagreement | The saved chiefs.com text reads "Kenneth Walker - Groin - DNP \| Game Status: Out". Line 31 is labelled "Known · source discrepancy" and cites the 07:14:50Z nfl.com table | PASS |
| F4 | Unresolved game-day inactives | Each call says that inactives are unverified and gives an estimated time | KC 16:30Z, Warren 23:50Z, both "estimate, 90 minutes before kickoff". `official_inactives_verified` false. Final participation unknown | PASS |
| F5 | Warren 4/5 and 7/8 over 22.5, consecutive current-season appearances (line 59) | The counts follow from the appearance list, with denominators | Values 27, 34, 49, 33, 87, 28, 36, 0 (2026, 8 appearances, no gap other than the bye). 4/5 and 7/8 recomputed. Denominators shown ("8 available") | PASS |
| F6 | 6/8 at the then-posted lines (line 61) | Computed against each game's own line and labelled unverified | 6/8 recomputed (weeks 6 and 8 were unders, at 28.5 and 22.5). The card says the historical books, times and payouts are unverified | PASS |
| F7 | Engine tests | All pass, with no bytecode written into slate/ | `redteam/test_engine_ids.py`: 26 OK. `tests/test_picker_grading.py`: 4 OK. No new `__pycache__` | PASS. I found 26 + 4 tests, not 26 + 10. The 10-test set was not found in `nfl/slate/`, so I can't score it |
| F8 | G2: the Warren game log is sourced | `source_url` plus `retrieved_utc`, or a saved copy | The URL is present. `retrieved_utc`: MISSING. No saved copy under `inputs/` | **NOT YET**, LOW. The values are internally consistent, but I did not verify them against an independent saved copy |
| F9 | G2: afternoon pass figures ("Arizona stayed under 6.5 before halftime four times in nine games…", line 39) | A source for each figure, and a clear period and market | No source field anywhere for the late window. "Under 6.5 before halftime" doesn't say whether it is a team first-half total or points allowed | **NOT YET**, LOW. It is a pass, so no money depends on it, but it is still an unsourced stat |
| F10 | G6: open statuses named for the Warren call | The card names PIT's still-open designations before inactives | Slate file: Pat Freiermuth TE Questionable, Derrick Harmon DT Questionable. On card: neither | **NOT YET**, MEDIUM. Freiermuth's status changes Pittsburgh's short-target share, and that bears directly on a Warren receiving prop |

Command for F7: `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl/slate/redteam/test_engine_ids.py`, then the same with `.../nfl/slate/tests/test_picker_grading.py`. Each prints "OK".

## Material remaining defects, ranked

These are findings for Codex, the single writer. I edited none of them.

**D1. HIGH: both calls lose money at the market's own estimate, and the model adds nothing.**
- **The claim:** both calls are below break-even, and no edge is shown.
- **The command:** `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r2_prices.py`
- **Expected:** a pick that clears break-even, or a card that plainly says it doesn't.
- **Observed:**
  - KC needs 62.41% at -166, and the market estimate is 61.16% (the median of 4 peers), so it returns -1.99% per unit.
  - Warren needs 53.49% at -115, and the estimate is 50.0%, so it returns -6.52% per unit.
  - The card does say this (lines 21, 23, 51 and 124): "No calibrated advantage has been established." It is therefore disclosed rather than wrong.
- **What Matthew should take from it:** "best under the rules" does not mean "profitable".

**D2. HIGH: Warren's 50.0% is not an estimate that he goes over 22.5.**
- **The claim:** the figure is BetMGM's own line with its margin removed, from one book, with 0 peers. A book prices its own line close to 50% by construction.
- **The command:** r2, as above (it prints the five lines).
- **Expected:** labelled "not estimable from the capture", or a note that every other book's line is higher.
- **Observed:**
  - BetMGM 22.5 at -115/-115 (.5000). DraftKings 23.5 (.4958). FanDuel 25.5 (.5000). theScore Bet 25.5 (.4797). BetRivers 27.5 (.5010). The peer median line is 25.5.
  - P(over 22.5) is therefore probably above 50% by an amount nobody has measured.
  - Both the -6.52% and any "edge" figure are unmeasured. The only real value on offer is line shopping at the one outlier book.
  - The card labels the figure "Estimated · offering book only, 0 peer books", which is honest about the source but invites a reading as a probability.

**D3. MEDIUM: Warren's football case leans on games played without Dowdle.**
- **The claim:** the headline (line 45) rests on 7/8 and on the first meeting (3 catches, 49 yards). Both include weeks 3-5, when Rico Dowdle was out.
- **The command:** `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r1_football.py`
- **Expected:** the split by Dowdle's role, shown next to 7/8.
- **Observed:**
  - Since Dowdle returned (weeks 6-8), Warren is over in 2 of 3: 28, 36, 0.
  - The first meeting was week 3, without Dowdle.
  - Line 53 gives the 46% route share and the zero-yard game, but not the 2/3 split or the fact that the first meeting came without Dowdle.
  - Freiermuth's open status (F10) is the other piece a sharp pregame bettor would check here.

**D4. MEDIUM: the gap between paper and a real ticket.**
- **The claim:** the card cannot yet tell Matthew whether a real ticket at these terms exists.
- **The command:** r2, as above. The fields are `local_availability_verified`, `settlement_terms`, `minimum_price` and `condition` in `selections.json`.
- **Expected:** a usable minimum, a recheck instruction, Louisiana availability, and named house rules and a grading source.
- **Observed:**
  - **Capture vs offer.** The quotes are from 06:55Z, about 11 h before KC's kickoff and about 18 h before Warren's.
  - **Single-book outliers.** These are the most likely prices to move:
    - DraftKings -166 is the best KC price, but DraftKings' own margin-removed number (.5996) is the lowest of the five books.
    - BetMGM 22.5 is the only 22.5 on the board.
  - **Minimums.** Each minimum equals the captured price, so there is zero slack.
    - KC's minimum of -166 is already worse than the fair price of about -157.5 (from the 61.16% estimate).
    - The card's Warren term is "exact 22.5 at -115, else pass". That is stricter than the red team's, which also allows 23.5 at -110 or better. Codex should pick one and state it.
  - **Recheck.** The card gives the estimated inactives times. It does not say "re-quote the price before submitting", and odds that change at submit are not addressed.
  - **Louisiana.** `local_availability_verified: false` for DraftKings and BetMGM. This can't be checked offline.
  - **House rules.** "House rules unknown". The moneyline includes overtime, and a tie depends on the book's rule. The prop needs Warren active, and void rules vary by book.
  - **Grading source.** The paper record doesn't name one (for example, the nfl.com box score for the prop).

**D5. LOW: wording and labels.**
- Line 23 gives "60.9%" while line 17 gives "61.2%". Line 27 explains the difference: 60.9% is the median of all 5 books and 61.2% is the median of the 4 peers. Line 23 should carry the label too.
- The controls table (line 121) reads "over 38.5 game points" with no game named.
- "Aaron Rodgers starts" (line 53) is an inference. The saved Steelers page describes his play, and he is not on the injury list, but no club page says he starts. Label it estimated.

**D6. LOW: the red team page has one small rounding difference.**
- ~~Line 81 says "ATL is 1-3 at home". It is 1-4.~~ **Retracted 07:42Z: the red team is right.** ATL's week 9 game against CIN (17-34) was played at the Bernabeu, and nflverse marks it `location = Neutral`. ATL is 1-3 in actual home games. My r1 counted neutral sites as home games; it now marks them "N".
- "KC 25.3" rounds 25.25 the other way from the card (25.2).
- Check 6 is now correctly shown as PASS on the final freeze.

## Matthew's five preserved points

1. **One Sunday cannot show an edge.** The card says so (lines 112 and 124).
2. **The 06:55Z capture is stale.** A recheck before kickoff is needed, and Codex owns any credit spend for it.
3. **The props have no player-level past-only test.** The prop model's basis is "unknown"; the card says "model's estimate is unavailable".
4. **The -200 to +200 band is a presentation filter, not an edge.**
5. **There is no OAPI.docx key route.** Claude reads only the shared capture.

## Requirements fit (Codex owns the PDF, desk and journal)

| Requirement | Card |
|---|---|
| TL;DR with matchup, kickoff, bet and threshold, odds, book, quote time, conditions, passes | Yes (lines 5-9; quote time in lines 21 and 51) |
| A "bet value" column in the TL;DR saying what it measures | Missing. The per-unit return is in the body, not the TL;DR |
| Last 5 / last 10 as consecutive current-season appearances with denominators | Yes for Warren (line 59) |
| Today's line shown separately from then-posted lines | Yes (lines 59 vs 61) |
| Team records and H2H | Records yes. H2H shows the last meeting only |
| Matthew's pregame football judgment field, with revisions kept | Not on the card; belongs to the desk and journal (Codex) |
| Earliest observation kept separate from a verified opener | Yes (lines 33 and 63) |
| CLV and EV as information only | Yes (lines 21 and 126) |
| Independent pregame red team | Linked (line 102) |
| Matthew places any wager himself | Yes. There are 0 tickets, and the card is advisory |
| PDF of 1-3 pages | Not scored here (Codex) |

## The ID and price repros (all PASS)

| Repro | Command | Expected | Observed |
|---|---|---|---|
| Contract IDs | `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r3_ids.py` | Two players on the same line, full game vs first half, and team totals all get distinct ids; the opposite side pairs within the same player; ":" is escaped; 3 and 3.0 give one key | All true. `A%3AOver` is escaped. `spreads::T:3` for both 3 and 3.0. No `__pycache__` |
| 61.2% vs 60.9% | r2 | Two distinct, labelled numbers | 0.61164 (4 peers) and 0.60924 (all 5). Reconciled; wording in D5 |
| 135 vs 136 | r1 | The decided count excludes ties | 136 scored, 1 tie, 135 decided. Reconciled |
| Warren from 0 peers | r2 | Flagged | See D2 |

## Superseded, and corrections to my own earlier notes

- v1 (07:22Z) scored engine 25d32a60 and card ac95f03a. Its M5 FAIL and its G2 "pages not saved" finding are fixed by the 07:24:59Z and 07:25:00Z saves and the evidence labels.
- I **retract** an interim note from r2 that said the Warren call had "line: None". My script read the wrong key. The line is in `point` (22.5), and `condition` says to pass if the exact threshold disappears.

## Re-check at 07:37:50Z (coordinator request, Matthew's last-5/10 rule)

- **No release after the one reviewed above.** At 07:37:50Z, picker.py `5771a47f31a13731`, selection_decisions.py `6898d72cca26951d` and selection_markets.py `91bbfbab0af9460e` are unchanged since 07:29:44Z. The selections, card md and card html are unchanged since 07:34:01Z (`4e68284c`, `2d5c3b37`, `91f95754`). I re-ran r4. Its output matches v2: **M5 PASS, G2 NOT YET (narrow), G6 NOT YET (one item).**
- **Last-5/10 rule: PASS for Warren.** The rule is consecutive current-season games, against today's line, with the available n shown and no padding from earlier seasons. Pittsburgh played 8 games in 2026, weeks 1-8 (nflverse `games.csv`), with a bye in week 9. The 8 dates in `recent_appearances` match those games one for one, from 2026-09-13 to 2026-11-01. There is no 2025 padding. The card shows "5 available" and "8 available" against 22.5, which is today's line.
  - Command: `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B -c 'import csv,sys; [print(r["week"],r["gameday"]) for r in csv.DictReader(open(sys.argv[1])) if r["season"]=="2026" and "PIT" in (r["home_team"],r["away_team"]) and r["home_score"]]' /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl/data/raw/games.csv`
- **The 0-yard game on 2026-11-01 is a real appearance (resolved 07:42Z).** The saved official Steelers page (`steelers-matchup.20261115T072500Z`, hash matches) says "Warren rushed for 143 yards on 17 carries in Week 8". Week 8 is CLE at PIT on Nov 1, so he was active and the card is right to count the 0. The receiving values themselves still rest on the unsaved nfl.com game log, which is G2a.

## Follow-up at 07:43Z: acceptance repro for the open items, and a venue check

The open items are fixes the engine owner (Codex 7d2e) has to make, so I wrote a pass/fail check rather than leaving them as a list. Once a new release lands, anyone can run it:

`/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r5_venue_and_g2g6.py`

| Item | Passes when | Now (07:43Z) |
|---|---|---|
| G2a | Warren's `recent_appearances` carries `retrieved_utc` and a saved copy (`saved_link` or `raw_sha256`) | FAIL |
| G2b | The afternoon pass's figures carry a source field | FAIL |
| G6 | The Warren call's evidence and the card both name Freiermuth (TE) and Harmon (DT) as Questionable | FAIL |

**Venue check (new, LOW).**
- **Labels agree.** r5 compared 120 team-games in the saved ESPN `lastFiveGames` with nflverse. The only three disagreements are games nflverse marks Neutral: HOU-JAX on 10-18, PIT-NO on 10-25 and CIN-ATL on 11-08 at the Bernabeu. No home or away label is wrong. Because of this check I retracted my D6 point on ATL's home record (above), and r1 now marks neutral sites "N".
- **One source disagreement that changes no call.** The saved Steelers page says Warren ran for 127 yards "in the first meeting in Cincinnati". nflverse records week 3 as CIN at PIT, played at Acrisure Stadium. The card's line 98 gives only the score (CIN 27, PIT 30) with no venue, so nothing on the card depends on which source is right. I can't settle it without a network call.

## Final acceptance at 07:52Z: the G2/G6 supplement on the product surfaces

The rows above are history. They scored the engine output (`selections.json`) and the markdown card, before the supplement existed. The supplement doesn't change the engine. It's a separate file, `results/sunday_20261115_review_evidence.json` (07:43:34Z, sha `6b99a766`). The front door is `Sunday NFL.html` (07:45:38Z, sha `f823e80a`), and `sunday_view.py` (07:45:37Z, sha `2acd8d49`) renders it. The engine code is unchanged from the 07:29:44Z freeze: picker `5771a47f`, decisions `6898d72c`, markets `91bbfbab`.

Repro: `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r6_review_evidence.py`. It is read-only, makes no network calls, and imports no engine or view module. Result: **23 of 23 checks pass**.

| Item | Result | What I checked myself |
|---|---|---|
| Binding | PASS | The capture digest `2a50d695` is the same in four places: Final_Decisions, Sunday_Card, selections and the evidence file. The issued time is 07:08:57Z in all of them. `sunday_card.released()` attaches each selections entry as `c["engine"]`, and the view looks up `by_call[e["id"]]`. The evidence is keyed only on the exact original call `48e497c2…:full_game:player_reception_yds:Jaylen%20Warren:Over:22.5`. The KC call has no entry, which is correct. If the capture or the issued time differed, the view would drop the evidence. |
| G2a, Warren's game log | PASS | Week 8, 2026-11-01, CLE 6 at PIT 27, game `2026_08_CLE_PIT`, home QB Aaron Rodgers. **17 rushes for 143 yards and 1 catch for 0 yards.** I read this from the saved log row (`17, 143, …, 1, 0`), whose hash `217b65f9` matches. The nfl.com source is recorded as retrieved 07:09:24Z with status 200 and HTML digest `af1314df`. Against 22.5, the last 5 are 4/5 and the last 10 are 7/8 (only 8 appearances exist). Both equal the saved log, newest first. |
| G2b, the afternoon-pass figures | PASS, one LOW | The source is nflverse 2026 pbp (`b29cf0cc`, the hash matches). I recounted from that file, using the score on the last quarter-2 play of each REG game in weeks 1-9. **Arizona scored: 9 games, [13, 7, 6, 17, 7, 9, 6, 3, 3], under 6.5 in 4/9. The Rams allowed: 9 games, [10, 3, 0, 20, 13, 9, 6, 9, 10], under 6.5 in 3/9.** Every game ID and value equals the evidence file. LOW: `retrieved_utc` is null. The file discloses this and gives the local file time, 06:55:54Z. |
| G6, Freiermuth and Harmon | PASS on the page | Pat Freiermuth (TE, illness) and Derrick Harmon (DT, foot) are both Questionable. The saved ESPN summary for event 401873064 names both. Its hash `0a47e53c` is in that folder's MANIFEST, and it was retrieved 07:14:57Z. |
| Page | PASS | The saved `Sunday NFL.html` contains, verbatim: the Freiermuth/Harmon text, the Week 8 appearance text, the first-half display text, and "Arizona points: 13, 7, 6, 17, 7, 9, 6, 3, 3." These sit under the Warren card's "Price, evidence and value" details, with a link to the reported game designations. |
| Tests (I ran them) | PASS | `tests/test_picker_grading.py`: **Ran 4 tests, OK**. `redteam/test_engine_ids.py`: **Ran 26 tests, OK**. That test confirms the engine files are unchanged and that odds_feed, sunday_quotes and verify_card aren't loaded. Both ran with `-I -B`. I count 30. I ran nothing else and claim no other total. |

**What I didn't verify, and the LOW notes**
- I checked the live view by reading its code and the saved render. I didn't run it, because `sunday_view.py` imports `sunday_quotes`, which I'm not allowed to load. The saved page is the 07:45:38Z render.
- The page gives the count for the Rams (3/9) but doesn't list their nine values. Those are in the evidence file only. LOW.
- `BEST_BETS_SUN_NOV15.md` (07:40:28Z) still doesn't name Freiermuth or Harmon. So r5's old G6 check still prints FAIL for the markdown card. The HTML front door has them. If the markdown or the PDF is also a user surface, the same one-line note belongs there. LOW. The fix is the engine owner's; I can't edit the card.
- r5 Part 3 checks fields in `selections.json`, so its G2a and G2b lines still print FAIL. That check is superseded by r6. The fix went into the supplement file, not the engine output.
- The selections re-ran at 07:40:26Z with the code hashes unchanged, the same capture and decided time, and 0 tickets.

Verdict at 07:52Z: **G2 PASS and G6 PASS on the product surfaces.** Two LOW notes are open: the Rams list isn't on the page, and the markdown card doesn't name the two players. The bets themselves are unchanged. KC at −166 is a pass. Warren over 22.5 is a lean only at −115 or better, after the inactives. No proven edge.

## Last-5/10 clarification at 07:58Z (relayed by the props reviewer, local_b9abf01d)

The rule, as relayed from Matthew: last 5 and last 10 mean consecutive 2026 appearances only. Don't pad with 2025 games. Show the available n. Keep the count against today's line apart from the count against the line actually posted for each game.

- **Correction to my own wording.** The last-5/10 paragraph above says the rule is consecutive games "against today's line". That is wrong. The rule is consecutive current-season appearances. Today's-line counts and actual-line counts are two separate measures, shown side by side. My F5 and F6 rows already keep them apart, so no figure changes.
- **Recount.** Both measures come from `recent_appearances.entries` in `results/sunday_20261115_selections.json`, 8 appearances, sorted by date.

  | Window | Over today's 22.5 | Over that game's own posted line (Stat Sniper; books and quote times unverified) |
  |---|---|---|
  | Last 3 | 2/3 | 1/3 |
  | Last 5 | 4/5 | 3/5 |
  | All 8 (n=8, so this is the available "last 10") | 7/8 | 6/8 |

  - The misses against the posted lines were week 6 (28 against 28.5) and week 8 (0 against 22.5).
  - The 4/5 and 7/8 counts describe his box scores against a number that wasn't posted for those games. They don't show that he beat the market. The actual-line measure is weaker in his latest games, at 3/5 and 1/3. I agree with the props reviewer's dissent on this.
  - Command: `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B -c 'import json,sys; e=sorted([c for c in json.load(open(sys.argv[1]))["calls"] if c.get("subject")=="Jaylen Warren"][0]["recent_appearances"]["entries"],key=lambda r:r["date"]); [print(n, sum(r["value"]>22.5 for r in e[-n:]), sum(r["value"]>r["prior_line"] for r in e[-n:]), len(e[-n:])) for n in (3,5,8)]' /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl/slate/results/sunday_20261115_selections.json`
- **My review left out the 3/5 actual-line count for the last five.** It is added here.
- **LOW, owner's fix (Codex 7d2e).** The page's "Independent review: conditional lean" paragraph is at `sunday_view.py` line 61 (hash `2acd8d490ad40389`; PROP_REVIEW cites line 56) and appears once in `Sunday NFL.html`. It gives "beat the actual historical lines in 6 of 8" with no source label and no last-five figure.
  - Suggested wording, for the owner to decide: "against each game's own posted line (Stat Sniper, books and quote times unverified) he was over in 6 of 8 and 3 of his last 5."
  - I did not edit the file.
- **Calls unchanged.** Warren stays a lean only, at BetMGM -115 or better, after the inactives. KC ML at -166 stays a pass. There is no proven edge. G2 and G6 stay PASS.

## PDF brief against the reissued watchlist at 08:01Z (coordinator's optional check)

- **Files:**
  - `pdf_export/Sunday_NFL_Brief.pdf`, 07:40:55Z, hash `5c977322`.
  - `results/sunday_20261115_watchlist.json`, reissued 07:45:31Z, hash `3e6d10df`.
- **Command:** `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r7_pdf_vs_watchlist.py`. It reads the PDF text with the standard library only and imports nothing from the builder.
- **Result:** `TOTAL 15 of 15 checks pass`. No mismatch.

| Check | Result |
|---|---|
| The reissue adds only `appearance_evidence`. Every other key equals the 07:38:26Z issue | PASS |
| `appearance_evidence` hash `7f202c76` = `props_20261115.json` | PASS |
| Ranked at 1:38 am CT and quoted at 12:55 am CT (07:38:26Z and 06:55Z, UTC-6) | PASS |
| Ranks 1-5: label, price, book, Formal/Watch, volatility, risk tag and kickoff all match, in rank order | PASS (5 rows) |
| Two formal calls (early 1, night 1). The afternoon is a pass | PASS |
| Warren on today's line: "4 of his last 5 games and 7 of 8" | PASS |
| Warren on each game's own line: "beat 6 of 8 actual prior lines", labelled unverified | PASS |

LOW notes. None of these is counted or a mismatch with the watchlist:
- The own-line count for the last five (3 of 5) isn't shown. Only the 8-game count is. This is the same note as for the page.
- Freiermuth and Harmon aren't named in the PDF. The HTML front door names them.
- The week 8 context (17 rushes for 143 yards) isn't shown. The PDF says only "zero receiving yards last game".
- **The PDF lags its own evidence file.** `pdf_export/evidence/2026-11-15.json` was changed at 08:01:29Z, after the PDF was built. Its KC title is now "Can Kansas City keep running without Walker?", which the PDF doesn't contain. A rebuild is due from the owner. Rerun r7 against the new PDF when it lands.

## Inactive-list handoff: Gemini public research, checked against the official page at 08:10Z

Request (agent relay of Matthew's ask): use the user-wide Gemini research MCP from Claude, natively, on one public question about when inactive lists reach the referee. Verify the original page, keep the handoff apart from any sportsbook updating its offer, and send the result to the release owner and the Codex advisor.

- **Native tool:** `mcp__gemini-public-research__research_public_question`. I loaded it with ToolSearch and called it at about 08:06Z, after a `date -u` stamp of 08:06:19Z. It returned an answer, not an error.
- **Inputs:** one public question, with no file, no project data and no account detail. The tool takes only a question string. I chose no paid option, and the tool has none to choose.
- **Question sent:** "What does official NFL Football Operations (operations.nfl.com) say about when each club's inactive player list must be given to the referee before kickoff? Please give the official NFL URL and quote the relevant rule or policy text, including the deadline (for example, how many minutes before kickoff)."

### What Gemini said

- Each club's inactive list reaches the Referee 90 minutes before the scheduled kickoff, at the 90-minute officiating meeting in the officials' locker room.
- Club PR representatives deliver the Game Day Administration Report to the Referee. It includes the inactive list, the players designated for C2P helmet components, and any players or coaches wearing microphones.
- Its cited URLs:
  - `operations.nfl.com/gameday/the-officials/list-of-game-day-jobs/`
  - `operations.nfl.com/gameday/the-game-day-experience/game-and-stadium-prep/`
  - RotoWire and FactsDesk, both secondary.
- Gemini said itself that it couldn't retrieve the meeting heading word for word. Its "90 minutes" figure came from indexed search summaries.

### My check of the original page

- **Gemini's two NFL URLs return HTTP 404** (WebFetch, about 08:07Z). The `/gameday/` path also returns 404. These links are stale.
- **Current official page:** https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep. I found it with a web search limited to operations.nfl.com and fetched it at about 08:09Z. The page shows no last-updated date.
- **What it says:**
  - Under the "90-minute officiating meeting" heading, the Referee and the other game officials meet in their locker room "One hour and 30 minutes prior to kickoff".
  - Both teams' PR directors and the TV network representatives attend.
  - Game Day Administration Reports are exchanged there. Each report includes the club's inactive list, its C2P helmet designations and its microphone wearers.
  - Item 6 of the page's list of what the meeting does says that club PR representatives deliver that report to the Referee.
- **Verdict on Gemini:** the core claim is confirmed. The list goes to the Referee at the meeting 90 minutes before kickoff. Two corrections:
  - the cited URLs are stale;
  - the page says when the handoff happens. It doesn't word it as a "must submit by" deadline, so that framing is Gemini's inference.
  - I did not check its secondary sources.

### Referee handoff versus a sportsbook updating its offer

- **The NFL page covers only the handoff inside the stadium**, from club PR to the Referee at the 90-minute meeting.
- **The page doesn't say when the list is made public.** It also doesn't mention sportsbooks. I have not verified when any club or the league posts its list.
- **A sportsbook updating its offer is a separate event.** That covers re-pricing, suspending, pulling or voiding a prop. Each book does it on its own clock under its own house rules. It is not the NFL handoff. I have not verified any book's timing.
- **For our calls:** "after the inactives" means after the public list has been seen and the price has been re-checked at that book. The Referee handoff alone doesn't meet that condition. The handoff time is only the earliest point at which the official list exists.

### Handoff time for each ranked row

Each handoff time is the kickoff minus 90 minutes, using the watchlist's `kickoff` fields. CT is UTC-6.

| Rank | Call | Kickoff | Referee handoff |
|---|---|---|---|
| 1 | Jaylen Warren over 22.5 receiving yards (formal) | 01:20Z Nov 16 (7:20 pm CT Sun) | 23:50Z (5:50 pm CT) |
| 2 | Kansas City to win (formal) | 18:00Z (12:00 pm CT) | 16:30Z (10:30 am CT) |
| 3 | First half, Detroit under 13.5 (watch) | 14:30Z (8:30 am CT) | 13:00Z (7:00 am CT) |
| 4 | Indianapolis under 20.5 (watch) | 18:00Z (12:00 pm CT) | 16:30Z (10:30 am CT) |
| 5 | Brock Bowers over 58.5 receiving yards (watch) | 21:05Z (3:05 pm CT) | 19:35Z (1:35 pm CT) |

- The page gives one standard pregame schedule. I didn't check exceptions for special games, such as the 8:30 am CT kickoff.
- **Calls unchanged.**
  - Warren is still a lean only, at BetMGM -115 or better, after the public inactives and a fresh quote.
  - KC ML at -166 is still a pass.
  - There is no proven edge.

**Relay receipt.** I queued the result with `codex queue --thread <id> --message <text> --resume`. Both threads queued the message. Neither resumed: the CLI warned that no local daemon was running.

| Recipient | Thread | Queued at | Message id |
|---|---|---|---|
| Release owner | `01a1de30-b81b-7811-827b-af5dbd9cd9f6` | 08:11:59Z | `01a1de43-6137-7af3-a0d5-74ba4998f56b` |
| Codex advisor | `01a1de02-799a-7373-aa82-c639510bd088` | 08:12:00Z | `01a1de43-61c9-7ab0-b2dc-ce7718ca9c5d` |

## Window recheck at 09:34Z: M5, G2/G6, print edition, paper versus real cash, same-game disclosure

This covers the 09:23:32-11:23:32Z window that Matthew opened, as relayed by Codex 01a1de0b-7734. I wrote no application file. The owners were writing between 09:26Z and 09:32Z, so I read the files after they settled: selections 09:31:28Z, journal.py 09:32:06Z, PDF 09:32:55Z.

**Commands** (read-only, no network, import no engine, view, journal or PDF-builder module):

- `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r8_print_disclosure_paper.py`, result `TOTAL 30 of 30 checks pass` at 09:34:34Z.
- `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r6_review_evidence.py`, result `TOTAL 23 of 23 checks pass` at 09:34:39Z.

| Gap | Verdict | What I checked |
|---|---|---|
| M5 evidence labels | PASS | Both calls label each item known, estimated or unknown. Price is known, football judgment and probability are estimated, participation and fill are unknown. Health keeps `final_participation` unknown and `official_inactives_verified` false. Both are still bound to capture `2a50d695…` and the 07:08:57Z issue. |
| G2/G6 | PASS | r6 is unchanged at 23 of 23 against the current files. |
| Print edition | PASS | The front-door PDF is the NFL_Live brief, and the builder copy now has the same hash (`1f17a419…`), so the earlier lag is gone. All five Top 5 rows match the watchlist on price, book, status, volatility, risk tag and kickoff, in rank order. Each TL;DR prints the 08:50Z saved quote at its time: KC -162 at DraftKings and Warren -115 at BetMGM, both 2:50 am CT. Limits, net per $10 and break-even are recomputed exactly (61.8% and $6.17; 53.5% and $8.70). Warren's counts carry n and fewer than 10 played: 4 of 5 and 7 of 8 at today's 22.5, and 6 of 8 at each game's own line, labelled unverified. |
| Paper versus real cash | PASS | The PDF says BEST SAVED QUOTE, Conditional selections, No ticket recorded, Log your read and any ticket, and Louisiana availability is unverified. It claims no opener, close or closing-line value. The `/` page footer keeps a conditional selection, observed odds and an accepted ticket apart, and says Matthew submits any wager himself. `selections.json` has no tickets. The journal now stores Matthew's accepted price, the offered price (for information only, never graded), stake, a required placement time and the issued minimum. Its ticket table marks a ticket "[below the issued minimum]" or "[different line from the bot's …]". This closes the journal side of RED_TEAM row 36. Real accepted terms stay unknown until Matthew enters a ticket, by design. |
| Same-game disclosure | PASS (not owed today) | The two calls are in two games, the five watchlist rows are in five games, and no call carries `shared_game_risk`. The PDF prints no false shared-game line. |

**Remaining regression for the owner (not a fail today).** `sunday_view.py`, which serves the `/` Sunday page, has no shared-game line. `pdf_export/brief.py`, `selection_release.py` and `sunday_week_release.py` do. Under the 08:06Z policy of up to two distinct contracts per Chicago window, a same-game pair could be issued, and then the PDF would disclose it but the page would not. The fix belongs to the release owner, 01a1de30: render the call's `shared_game_risk` text (already set by `selection_release.py`) on the `/` page. Repro: r8 section 3 prints the render-path table.

**Notes, LOW and unchanged.**

- r7's five row checks now fail only because the column became STATUS / RISK and the word "risk" left each row. That is a layout change, not content. Use r8, which checks tokens.
- The TL;DR shows the 2:50 am quote (-162) while the Top 5 and the price-check panel still show the 12:55 am quote (-166). Each carries its own time, so this is not a fail.
- The PDF still doesn't name Freiermuth or Harmon (the page does), and it doesn't show the own-line 3 of 5 or the week 8 line of 17 rushes for 143 yards.

**My verdicts are unchanged.** The product's two formal calls are KC to win (limit -166) and Warren over 22.5 receiving yards (limit -115). As reviewer I still rate KC at -166 a pass, and Warren a lean only at BetMGM -115 or better after the inactives. Neither is a proven edge. Paper only.

**Relay receipt.** Queued with `codex queue --thread <id> --message <text> --resume`. Both queued. Neither resumed: no local daemon was running.

| Recipient | Thread | Queued at | Message id |
|---|---|---|---|
| Release owner | `01a1de30-b81b-7811-827b-af5dbd9cd9f6` | 09:35:22Z | `01a1de8f-b474-7021-bb0e-6527222345be` |
| Codex advisor | `01a1de02-799a-7373-aa82-c639510bd088` | 09:35:22Z | `01a1de8f-b4bf-7722-968e-708f1a70758c` |

No message went to the engine writer (7d2e) or the journal owner (0b-7734): neither has an open item from this recheck.

## Final release recheck at 09:46Z: the issued PDF and the static page

This checks the release Matthew already has. I wrote no application file. The calls, the 09:35:13Z prices and each file's single writer are unchanged.

**What I checked**

- The final PDF has the same bytes in all three places: `outputs/Sunday NFL Brief.pdf` (now a copy, not a link, 09:41:01Z), the NFL_Live brief and the builder copy. sha `0d89417e916eb337…`.
- The static page `outputs/Sunday NFL.html` (09:41:01Z, sha `cf2363e50f15be33…`) was read as text only.
- The prices come from the 09:35:13Z observation `final-release-20261115T093513Z.json`. Its source is live, and it used 2 credits, leaving 408.

**Commands** (read-only, no network, import no application module):

- `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r8_print_disclosure_paper.py`, result `TOTAL 43 of 43 checks pass` at 09:46:36Z.
- `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/advisor/repros/r6_review_evidence.py`, result `TOTAL 23 of 23 checks pass` at 09:46Z.

**What changed in r8 since 09:34Z**

- The front-door check now compares bytes instead of requiring a link.
- The observation picker also reads `final-release-` files.
- The shared-game pattern now includes the page's wording, "Same-game".
- There are new checks for the final same-game policy.
- A new section 5 reads the static page.

| Gap | Verdict | What I checked |
|---|---|---|
| M5 evidence labels | PASS | Unchanged: every item is labelled known, estimated or unknown, and the calls are still bound to capture `2a50d695…` and the 07:08:57Z issue. |
| G2/G6 | PASS | r6 23 of 23. |
| Print edition | PASS | The TL;DR shows the 09:35:13Z quotes at 3:35 am CT. KC: -166 at DraftKings, limit -166, $6.02 net per $10, break-even 62.4%. Warren: -115 at BetMGM, limit -115, $8.70 net per $10, break-even 53.5%. Both still meet their limits. The five Top 5 rows match the 09:36:16Z watchlist in rank order, including the new risk tags "PIT inactives / shared targets" and "QB change / recheck inactives". Warren's counts carry n. |
| Static page (normal path) | PASS | Both cards show the book update at 3:34 am CT (DraftKings −166, BetMGM −115) and "Minimum acceptable … or better". The 3:35 am CT price-history row shows both as "Price qualifies". The page also says "Saved quote · recheck before use", "No ticket is created by a price check", and "Only rows marked formal call are on the issued card". |
| Paper versus real cash | PASS | The PDF and page labels are unchanged. The journal still stores the accepted price, the offered price (information only), stake, placement time and the issued-minimum comparison. |
| Same-game disclosure (final policy: allowed with the shared-risk disclosure) | PASS | Today's two calls are in two games and the five watchlist rows are in five games, so no line is owed and none is printed. All four render paths have the disclosure: the PDF, the release report, the `/` page and the week pages. The `/` page prints "Same-game selections share game risk…" whenever two calls share an `event_id` (`sunday_view.py` lines 39-40). |
| No opposing same-subject formal picks at any threshold | PASS | Each (event, market, subject) has one side: KC h2h, and Warren receiving yards Over. The enforcement tests belong to nfl-slate-data. |

**Correction to my 09:34Z open item: withdrawn.** At 09:34Z I reported that `sunday_view.py` had no shared-game line. My pattern searched only for "Shared game", but the page says "Same-game", so the check could not have found it. The line is in commit `54a53a9` (09:37:03Z). It renders on the same condition as the week pages. Nothing is owed by the release owner.

**LOW notes (not fails)**

- Beside the 3:35 am observation, the page says "This check used 0 free credits". The observation itself used 2; the 0 counts only the offline reread. Owner's call on wording.
- The page's Warren review still says "beat the actual historical lines in 6 of 8". It has no source label and no own-line last-five figure (see my 07:59Z note).
- The PDF still doesn't name Freiermuth or Harmon (the page does).

**My verdicts are unchanged.** As reviewer I rate KC at -166 a pass. Warren is a lean only, at BetMGM -115 or better, after the inactives. Neither is a proven edge. Paper only. My scope is verified and finished.

**Relay receipt (correction).** Queued 09:47:23Z with `codex queue --thread <id> --message <text> --resume`. Both messages were queued but neither thread resumed, because no local daemon was running.

| Recipient | Thread | Message id |
|---|---|---|
| Release owner | `01a1de30-b81b-7811-827b-af5dbd9cd9f6` | `01a1de9a-b4d4-7573-99f6-fb393b6fdeac` |
| Codex advisor | `01a1de02-799a-7373-aa82-c639510bd088` | `01a1de9a-b566-7c00-a437-1a16bb9aa8ca` |

## Book grading rules versus paper (10:02Z, relay ff1c)

**On disk first.** I found no saved house-rules text. The issued card says "house rules unknown" and "void rules depend on book" (`issued_picker_20261115.py:1335-1336`). STATUS.md records DraftKings 403s at 05:29:27Z and 05:30:29Z.

**Sources.**

- **DK online (unavailable).** The official DraftKings online rules page, https://sportsbook.draftkings.com/help/general-betting-rules/general-rules, returned HTTP 403 at about 09:53Z. I didn't work around it.
- **DK Louisiana retail.** "Betting Rules DraftKings Sportsbook at Golden Nugget, Version 13 - 03/07/2025": https://goldennugget.com/globalassets/lake-charles/_pdfs/draftkings-gnlc-retail-house-rules-v13.pdf, retrieved 09:54Z.
  - It governs the Golden Nugget Lake Charles retail book under the Louisiana State Police Gaming Enforcement Division.
  - It never mentions mobile or online betting. Treat it as Louisiana DraftKings *retail* rules. Nothing I found shows they govern the DK app.
- **BetMGM Louisiana.** These are BetMGM's official Louisiana help pages, read with no sign-in from 09:58Z to 10:02Z. The pages show no date.
  - The Management Rules page requires bettors to be physically present in Louisiana.
  - Quotes come through WebFetch's page summary. Re-read the page before relying on the exact wording.
- **Leads only, not rules.** Gemini (it gave vertexaisearch redirect links and no headings), the BetMGM blog, Action Network and RotoGrinders.

| Book | Item | URL and section | Paraphrase | Label |
|---|---|---|---|---|
| DK | 2-way moneyline, overtime | GNLC v13, "Market Rules > Money Line" (p.7) | The Money Line is a 2-way market and includes overtime. | Supported: Louisiana retail |
| DK | Tie after overtime | GNLC v13, "Football > General Rules" (p.49) | "In 2-way markets, push rules apply"; all bets include overtime unless stated otherwise. A tie therefore pushes. | Supported: Louisiana retail |
| DK | Receiving yards: action, no snap, DNP | GNLC v13, "Football > Player Props" (p.51-52) | The player must take part in at least one play, special teams included. If he is listed inactive or did not play, the bet is void. Settled on official NFL game statistics when DK settles the market. | Supported: Louisiana retail |
| DK | Stat corrections | GNLC v13, "Football > Settlement Rules" (p.54) | Player markets settle once the game is final and official stats are available. A stat change after settlement does not re-settle the bet. | Supported: Louisiana retail |
| DK | Injury exception | GNLC v13, Football section | No exception found. A player who takes one play has action. Gemini's "Early Exit" promo is not in v13 and is unverified. | Supported (no exception): Louisiana retail |
| BetMGM | Moneyline, overtime | https://help.la.betmgm.com/en/sports-help/sports-house-rules/football-wager-types-and-rules, "Football Wager Rules > Money Line" | The team must win, and overtime periods count in the final score. | Supported: Louisiana online |
| BetMGM | Tie on the full-game moneyline | Same page; also https://help.la.betmgm.com/en/sports-help/sports-house-rules/general-sportsbook-rules | Neither Louisiana page states it. Only "Winning Margin" calls a wagering tie "no action". The MA filing (3/28/2025) defines a push only for a spread or total. | Unavailable for Louisiana. The blog says it pushes (lead only). |
| BetMGM | Receiving yards: action, no snap, DNP | Football page, "Football Player Props" | The player must play at least one snap. The bet is cancelled if he is listed inactive. A QB must start. | Supported: Louisiana online |
| BetMGM | Stat corrections | https://help.la.betmgm.com/en/sports-help/sports-house-rules/obvious-errors-and-resettlement, "Re-settlement" | Markets generally settle shortly after the event. BetMGM may amend a settlement if the official result differs. No stat-change cutoff is stated. | Supported: Louisiana online |
| BetMGM | Injury exception | Football page, "BetMGM Bet Defense" | Applies only to eligible bets on a single NFL game. Eligible bets carry an icon on the betslip, and the bet must be accepted before the first quarter ends. It covers eligible player props conditioned on positive performance, such as an Over. If a player exits during the first quarter with an official injury and doesn't return, an affected bet is cancelled, and the original stake comes back in its original form within 72 hours of market settlement. A bet already unconditionally decided before the exit settles normally. Unders settle as wins. A player who returns is no longer covered. BetMGM decides which props are eligible. Re-read 10:08Z. | Supported: Louisiana online |

**Paper versus books for the two frozen calls** (`journal.py settle()`, read only):

1. **KC moneyline at DK -166.**
   - The journal grades a margin of 0 as a push. DK's Louisiana retail rules agree.
   - The journal uses whatever final score is recorded. Both books count overtime, so the recorder must enter the final score including overtime.
   - Stat corrections don't apply to this bet.
2. **Warren Over 22.5 receiving yards at BetMGM -115.**
   - **DNP or inactive.** Both books void. The journal voids only through a manual `record_void` with a source; otherwise the grade is "unknown". It has no one-snap test.
   - **Stat corrections.** The journal takes the latest recorded value, with no cutoff. That matches BetMGM's right to amend. It does not match DK's "no re-settlement", which would only matter for a DK prop.
   - **Bet Defense: a ticket refund, not a paper void.** This bullet was corrected at 10:09Z on the journal owner's ruling (Codex 01a1de0b, who read Louisiana Football Rules lines 103 and 108-112). I re-read the same section at 10:08Z, and it agrees. The 10:02Z version recommended a `record_void` on the paper call; that recommendation is withdrawn.
     - The issued paper result keeps its original conventions. Bet Defense is account- and ticket-specific, so it is not a reason to void the paper call.
     - The only time it changes anything: Matthew's accepted betslip shows the Bet Defense icon, and BetMGM actually returns the stake. Then use the existing per-ticket settlement or refund for that ticket only.
     - Not every first-quarter exit is refunded. The exit must meet the rule: an official injury, ruled out with no return. The stake comes back in its original form. A bet already unconditionally decided before the exit settles normally.
     - A genuine, separately documented market-wide void is a different case, and this bullet doesn't cover it.

This was a finding for the journal owner, not an edit. The owner has ruled on Bet Defense (see the corrected bullet). No paper grade has changed. Current quotes and selections stand. Nothing in this section was signed in, bought or bet.

### Correction: DraftKings mobile versus retail (10:06Z, after Codex 01a1de0b's check)

The table above is unchanged. This section narrows what its DK labels mean.

**What Codex found, relayed and not read by me.** Both DraftKings pages returned HTTP 403 to my fetch at 10:05Z. I didn't work around that.

- **Mobile Louisiana terms:** https://sportsbook.draftkings.com/legal/la-terms-of-use. Codex reports that these terms explicitly incorporate DraftKings' general house rules.
- **Generic rules page:** https://sportsbook.draftkings.com/help/general-betting-rules/general-rules. Codex reports that it says a two-way market includes overtime and that a final tie between two options pushes.
  - The copy of that page Codex was served identifies West Virginia, not Louisiana.

**DraftKings: three sources, three different scopes.**

| Source | What it covers | Two-way moneyline and overtime | Tie in a two-way market | Player props, stat corrections, injury |
|---|---|---|---|---|
| LA mobile terms of use | Louisiana mobile; incorporates the house rules by reference | Not stated in the terms themselves | Not stated in the terms themselves | Not stated in the terms themselves |
| Generic DK general rules, as Codex read it | Not Louisiana-specific; the served copy names West Virginia | Includes overtime | Pushes | Not relayed. Unavailable to me (403). |
| Golden Nugget Lake Charles retail v13 PDF | Louisiana retail only; no mention of mobile | Includes overtime (p.7) | Pushes (p.49) | The rows above (p.51-54) |

**Corrected DK labels.**

- **Overtime and tie, for the DK mobile book:** Supported by the generic DraftKings rule. Per Codex, the Louisiana mobile terms incorporate that rule. The only copy of it seen today was served for West Virginia, so no Louisiana-specific mobile text is confirmed.
- **Overtime and tie, for DK retail:** Supported by the Louisiana retail rules (the PDF). They don't establish the mobile rules.
- **DK props, stat corrections and injury:** Supported for Louisiana retail only. For DK mobile they are unavailable. No frozen call depends on them, because Warren is a BetMGM bet.

**What this changes for the KC moneyline at DK -166: nothing in the grade.** The journal grades a margin of 0 as a push and takes whatever final score is recorded, including overtime. The generic DK rule and the Louisiana retail rules both agree with that. One qualification remains: this rests on the generic page, not on Louisiana mobile wording. If Matthew bets on the app, the rule that binds is the one his app shows him. Checking that is his own step, and it needs a sign-in.

**BetMGM: agreed with Codex.** The Louisiana landing page, https://help.la.betmgm.com/en/sports-help/sports-house-rules, contains only the Management Rules. My earlier note cites it for one thing only: a bettor must be physically present in Louisiana. Every BetMGM grading row in the table cites a subpage (football wager rules, obvious errors and re-settlement, general sportsbook rules). No BetMGM label changes.
