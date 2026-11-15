# NFL Sunday red-team acceptance, final

Written by the Claude coordinator, local_50238c87.

- Started 07:26Z on 2026-11-15.
- First final at 09:41:13Z.
- Re-verified at 2026-11-15T09:46:20Z (from `date -u`), after the 09:39:54Z PDF rebuild and the 09:36Z engine commit `55336a4`.
- Rows re-run at 2026-11-15T09:49:56Z after the owners' fixes:
  - bot-advisor's r8 hardening `67562a3` and its r7 update;
  - nfl-slate-data's weekly commit `f39f57b`;
  - postgame's ESPN box-score import `967cbd9`.
- Corrected at 2026-11-15T09:53:45Z (from `date -u`), at the request of Sunday release owner Codex 01a1de97 and its sender. The 09:46Z text let "23.5 at −110" satisfy the Warren call. It cannot. The issued contract is exactly over 22.5 receiving yards at −115 or better. Also brought up to date: the weekly fix, the postgame collectors and the inactive-list timing. No verdict changed.

A failure is reported as a failure and never relabelled. This is paper and research only, and no ticket has been recorded. Earlier versions of this file are in git, the last at `229abfc`.

## Verdict at close

### The card Matthew uses

It is the front-door PDF `Documents/Codex/2026-11-15/nfl-weekly-release-integration/outputs/Sunday NFL Brief.pdf`.

- It is a copy written at 09:41:01Z. It is byte-identical (`cmp`) to `NFL_Live/Sunday NFL Brief.pdf` (09:39:54Z) and to the builder copy `pdf_export/Sunday_NFL_Brief.pdf` (09:39:36Z).
- It is 11,230 bytes, sha256 prefix `0d89417e`.
- It is one page (`/Count 1`).
- It supersedes the 09:38:54Z build (`9bc9832f`). The calls and the 09:35:13Z prices are unchanged. Only the watchlist risk text was corrected (see the FLAGs below).

### Two conditional formal calls, in different games

**Kansas City Chiefs moneyline**

- DraftKings −166, limit −166 or better.
- The final refresh (`NFL_Live/observations/final-release-20261115T093513Z.json`, 09:35:13Z, 2 credits, run by Codex 01a1de30) shows DraftKings −166. The other books: FanDuel −172, BetRivers −177, BetMGM −175, ESPN BET −175.
- The price sits exactly at the limit.
- Break-even is 62.4%. The engine's market figure (61.16%) and its model (60.24%) are both below it. The page prints the expected return as −2.4%.

**Jaylen Warren over 22.5 receiving yards**

- **The issued contract is exactly over 22.5 receiving yards at −115 or better.** The 09:35:13Z final refresh shows BetMGM −115 at 22.5, and the frozen PDF prints 22.5.
- Only 22.5 at −115 or better fills this call. DraftKings's 23.5 at −110 is a different contract and cannot qualify for the issued card. At exactly 23 yards the two bets grade oppositely: over 22.5 wins and over 23.5 loses.
- **Independent dissent, kept with its original time.** nfl-picker's football review (`slate/FOOTBALL_RED_TEAM.md`, written about 07:16-07:25Z and updated 07:30Z) would also accept "23.5 for -110 or better". That is a sensitivity note on a separate bet, not part of the issued call.
- Break-even is 53.5%. The no-vig figure, from the single book that prices both sides, is 50.0%.

### What passed and what didn't

- **Every release-critical check passes.**
- **The middles gap is closed.** Engine commit `55336a4` (09:36Z) refuses opposing picks on one subject at any line.
- **What stays open:** the FLAGs on evidence. Every repro now passes: r7 18 of 18 and r8 43 of 43.
- **Value.** Neither call clears break-even on the market's own numbers. Matthew said +EV is not a gate, and the page states it plainly.

## Engine and selection

| Check | Result | Evidence |
|---|---|---|
| Prop-ID collisions; totals vs first half; home vs away team totals; quotes before kickoff; no `odds_feed`/`sunday_quotes`/`verify_card` imports | **PASS, 28 of 28** at 09:33:40Z and again at 09:49Z (`selection_decisions.py` sha `8457d042`) | `slate/redteam/test_engine_ids.py` by nfl-picker, run with `-I -B`. On the real capture: 1,756 candidates, 178 multi-player groups with distinct ids, and 3,080 quotes, all before kickoff. **History:** 26/26 at 07:33Z; 7/26 after the 08:06Z shim split; 24/26 at 08:11Z. `test_6` was then relabelled to the final same-game policy. |
| Both sides of one bet | **PASS** | Fixed by Codex 7d2e at 08:08:43Z. The cross-call key is rebuilt in the shim. Covered by the 28 tests. **History:** FAIL at 08:08Z. |
| At most 2 per window | **PASS** | Covered by the 28. Today's card has 1 call in the early window, 1 in the night window and 0 in the afternoon. |
| Same-game calls | **PASS against the final policy** | **Final policy** (Codex relay, about 09:34Z): same-game calls are allowed if the shared-game risk is printed.<br>Today's 2 calls are in 2 games. r8 confirms the PDF prints no false shared-game line and no call carries `shared_game_risk`.<br>**NOTE:** `sunday_view.py` has no shared-game line. It is owed only if a same-game pair is ever issued. |
| Opposing picks on one subject at different lines (middles) | **PASS** (fixed in `55336a4`, 09:36Z) | **Final policy:** "no opposing same-subject formal picks at any threshold".<br>`W/ENGINE_MIDDLES_REPRO.py` now exits 0 at 09:43:27Z. Both Over 22.5 plus Under 24.5 and the exact both-sides control are refused: "Duplicate, opposing, or excess review call".<br>The cross-line tests live in `test_engine_ids.py`, the weekly suite and `tests/`.<br>**History:** exited 1 at 09:31Z, when the middle was accepted. |
| Run after kickoff | **PASS, by reading code** | `picker.py` refuses with "First kickoff has passed." `--allow-late` relabels the output "Unverified research replay". The freeze locks at first kickoff. |
| Neutral site (NE at DET, Munich) | **PASS, by reading code and data** | The slate marks it `neutral=True`. The engine gives a neutral venue zero home-field advantage. |
| Push results | **PASS, by reading code** | `diff == 0` is graded a push, and a push or void counts as zero profit. |
| Replacement evidence bound to the report | **PASS, 7 of 7** | `tests/test_decision_replacements.py`. The candidates' `replacement_evidence` sha equals the report's sha, `3eb139dd886649f6`. **History:** a FAIL at 09:31Z from a write race, since cleared. |
| Replacement data | **PASS, 4 of 4** | `replacements/tests/test_availability.py`, with KC and GB cases.<br>`replacement_report_20261115.json` is present.<br>The KC call carries `replacement_context`: Kenneth Walker III is out, source published 2026-11-14T17:16:42Z.<br>Warren has none, so the call prints the explicit "Unknown" label. |
| Weekly engine (nfl-slate-data) | **PASS, 73 of 73** at 09:43:48Z and again at 09:49:19Z | `weekly/test_weekly_api.py`, run with `-B`. It was 61 before the opposite-direction tests were added. nfl-slate-data committed them in `f39f57b` (09:44:15Z, OPPOSITE_DIRECTION). Imports are stdlib only.<br>**The weekly conflict is closed.** The weekly engine used to accept opposite directions on one subject, against the final policy. `f39f57b` refuses Over against Under, or home against away, on one event, period, market and subject at any threshold, at both submit and publish. Two distinct same-game picks are still allowed and labelled correlated. |
| Slate engine tests | **PASS, 26 of 26** at 09:43:48Z | `unittest discover` on `slate/tests/`. This includes `test_decision_replacements.py` and `test_weekly_football.py`. |
| Postgame intake | **PASS** | `test_postgame` 36/36 and `test_espn_boxscore` 8/8. `journal_quirk_repro.py` now exits 0 with both cases ok; it exited 1 earlier.<br>`espn_fetch.py`, checked by reading, uses only the public keyless ESPN site API. It has no key or token and no "or 0" defaults.<br>**Normal postgame path:** Sunday's player results settle from ESPN final box scores through `espn_fetch.fetch_and_import`, added in `967cbd9`.<br>**Alternate or archive collector:** `tools/collect_player_logs.py`, the NFL.com game logs. Its `CUTOFF = "2026-11-15"` is exclusive, so it can't collect Sunday's games, and it is not the normal path.<br>A missing athlete, missing stat or DNP stays pending. An NFL.com logs file older than the game is refused, with the cutoff named. A `--postgame` mode for the logs tool remains only a proposal. |

## Journal (tickets kept apart from calls)

| Check | Result | Evidence |
|---|---|---|
| Duplicate ticket | **PASS** (fixed 09:31–09:32Z) | `ticket_fingerprint` plus `reject_duplicate`: "This exact ticket was already recorded." **History:** FAIL from 07:23Z to 08:05Z and later. |
| Ticket outside −200..+200 | **PASS** | Stores `accepted_in_band` and flags it without refusing. **History:** FAIL. |
| Placed time | **PASS** | `placed_utc` is required with its time zone. It must be before kickoff and not in the future. `placed_utc_reported` is stored. **History:** FAIL, partly met. |
| Ticket below the issued minimum (stale quote at ticket time) | **PASS on the ticket side** | Stores `issued_minimum_price` and `meets_issued_minimum`. The report marks a ticket below the minimum or at a different line (r8 PASS).<br>The engine still has no maximum quote age. The guard is the card's limit price, the human re-check and the ticket log. |
| Offered vs accepted price | **PASS** | `offered_price` is kept on the same ticket line. The ticket is graded at the accepted price. |
| Journal test suite | **PASS, 78 of 78** | `journal.py` sha `c021cbac`, modified 09:32:06Z, run with `-I -B`. |
| Imports idempotent, no network | **PASS** | 1,756 bets, 0 dropped. A re-import adds 0 rows. |

## Print edition (front-door PDF)

| Check | Result | Evidence |
|---|---|---|
| Card numbers consistent | **PASS** (fixed) | The PDF's model figure, 60.2%, equals 0.6024 in the selections. 60.9% is labelled a five-book median, a different measure from the engine's 61.16%. **History:** FAIL, when the brief showed 56.3% against 0.6024. |
| TL;DR shows the latest saved quote | **PASS, r8 30 of 30** at 09:44:28Z, on the 09:39:54Z build | The front door prints:<br>- KC: −166 · DraftKings, 3:35 am CT, limit −166, $6.02 net per $10, break-even 62.4%;<br>- Warren: −115 · BetMGM, 3:35 am CT, limit −115, $8.70, break-even 53.5%.<br>Both match the 09:35:13Z final refresh, and r8 confirms each quote still meets its limit.<br>**Re-run:** r8 now scores 43 of 43 at 09:48:45Z, after bot-advisor's `67562a3`. It now:<br>- compares the front-door bytes;<br>- reads the `final-release-*` observations;<br>- checks the no-opposing-picks rule.<br>One LOW note: "0 free credits" is printed beside the 09:35:13Z observation, which used 2. The 0 is the offline reread.<br>**History:** r8 scored 28 of 30 against the 09:38:54Z build. Its two TL;DR FAILs are gone on the current build. |
| Paper vs real disclosures | **PASS** (r8 section 4, 9 of 9) | The page prints:<br>- BEST SAVED QUOTE;<br>- No ticket recorded;<br>- Conditional selections;<br>- Log your read and any ticket;<br>- Louisiana availability is unverified;<br>- "Saved observations only. No verified opener, close or closing-line value."<br>The footer keeps selection, observed odds and accepted ticket apart. |
| Top-5 table against the watchlist | **PASS: r8 5 of 5 rows in order; r7 18 of 18 at 09:48:45Z** | r8 checks every row against the 09:36:16Z watchlist on label, price, book, status, volatility, risk tag and kickoff, and confirms rank order 1 to 5.<br>r7 passes after bot-advisor updated it, and the owner committed it in `c99ef54` (09:50:01Z). Its LOW notes:<br>- the page shows Warren's 8-game own-line count, not the own-line last 5 (3 of 5);<br>- it doesn't mention his week 8 rushing game.<br>**History:** r7 scored 9 of 15 before the update. Its six FAILs were all on the repro side:<br>- **Five row FAILs.** They expect the old string "… high risk · …". The new layout puts that word in a "STATUS / RISK" header instead.<br>- **One reissue FAIL.** The reissue changed `ranked`. A field diff against the 07:38:26Z issue shows prices, books, lines and order unchanged. It added market-value fields, evidence times and the supplemental notes, and replaced two risk tags (Warren, Bowers).<br>"Zero receiving yards last game" now passes. The log's last entry, Nov 1, shows 0 yards. |
| Warren last 5 / last 10 | **PASS** | "Cleared 22.5 in 4 of his last 5 games and 7 of 8 this season (fewer than 10 played)." The hit rate against his own prior lines, 6 of 8, is shown separately. The public game log was saved at 07:44:12Z and confirms 4 of 5 and 7 of 8. |
| r5 G2a, G2b and G6 on the current card | **PASS, 3 of 3** at 09:55:19Z | `advisor/repros/r5_venue_and_g2g6.py` exits 0. It reads `slate/results/sunday_20261115_selections.json` (sha `519c9506`) and `BEST_BETS_SUN_NOV15.md` (sha `01e836e7`):<br>- G2a: the Warren game log carries `retrieved_utc` and a saved copy or hash;<br>- G2b: the afternoon pass figures carry `window_notes_sources`;<br>- G6: the Warren call and the card both name Freiermuth and Harmon.<br>Its venue section finds 3 of 120 team-games where ESPN's at/vs label disagrees with nflverse's home team: HOU-JAX, CIN-ATL and PIT-NO. nflverse marks all three Neutral. INFO only.<br>**History:** all three FAILed on the 08:25:48Z card, and that result went to the release owner. They pass now. |
| KC write-up title | **PASS** | "Can Kansas City keep running without Walker?" The earlier lag is cleared. |
| Line movement and CLV | **PASS on honesty** | DraftKings ranged −166 to −162 since the Nov 14 ESPN display. BetMGM −115 held across 6 checks. There is no claim of an opener, close or CLV. |
| Live price path | **PASS on discipline** | `sunday_card.full_snapshot` is human-click only. The one final two-call refresh at 09:35:13Z was Codex 01a1de30's. Claude made no Odds API call and read no key. |

## FLAGs open at close

| Item | Status | Detail |
|---|---|---|
| Bowers quarterback tag (watchlist row 5) | **Resolved** on the 09:39:54Z build | The row now reads "QB change / recheck inactives", and the page reads "The Raiders named Fernando Mendoza to replace Kirk Cousins. Recheck Bowers and his QB." "First-start" no longer appears anywhere on the page. `WATCHLIST_REVIEW.md` still applies: all seven of Bowers's overs came with Cousins at quarterback. This is a watchlist-only row. |
| Warren row risk text | **Resolved** on the 09:39:54Z build | The row now reads "PIT inactives / shared targets". The page tells the reader to check the official inactive list for TE Freiermuth (illness) and DT Harmon (foot), both questionable. |
| Warren value | **FLAG** | BetMGM's 22.5 is the lowest line. The other books sit at 23.5 to 27.5. A value figure from a single book isn't reliable. |
| Name collision | **FLAG** | The feed has both Jaylen Warren (PIT) and Tyler Warren (IND). Match on the full name. |
| Local availability | **FLAG** | Unverified, and the page says so. |
| Starting QB unresolved | **FLAG** | The slate's `missing` list has CLE, MIA, MIN, ARI and LV. |
| Missing book at ticket time | **FLAG** | Proposed rule: the same line at any of the five Louisiana books, at the limit or better; otherwise no ticket. For Warren that means over 22.5 at −115 or better at some book. At the final refresh only BetMGM had it. DraftKings's 23.5 at −110 does **not** meet the rule, because it is a different contract. If 22.5 at −115 or better isn't on offer, there's no ticket on the issued call. The football review's 23.5/−110 floor is independent dissent (see the card above), not a qualifying price. |
| Codex queue delivery | **FLAG** | Every receipt reads "queued, could not resume". A message lands only when its thread next runs. |
| Pregame dissent (nfl-props) | **PARTLY DELIVERED** | `DISSENT_PREGAME.md` and `.json` weren't found at close. nfl-props delivered `slate/redteam/WATCHLIST_REVIEW.md` at 09:37:35Z:<br>- no row fails a contract check;<br>- every row carries a FLAG;<br>- four of five rows price below break-even on the market's own no-vig number;<br>- the fifth is break-even. |
| File scope (nfl-slate-data) | **FLAG, self-reported** | `DATA_NOTES.md:123`: a whole-disk `find` was started and stopped. Its output was not read, and no file outside agent folders was touched. |
| Advisor review | **INFO** | r6 23/23 at 07:59Z. bot-advisor retracted two of its own claims in `NFL_REVIEW.md` (lines 119, 159, 181):<br>- the ATL home record, because this game is at a neutral site;<br>- Warren "line: None", because its script read the wrong key. |
| Slate data | **INFO** | Slate v2 is commit `946094e` (weather, club-verified QBs, derived ranks). Injury rows: 177 known, 0 estimated, 27 unknown. |
| Injury source, KC | **INFO** | The chiefs.com Saturday report, retrieved 07:24:59Z: Walker Out, Moore Out. Each club hands its inactive list to the Referee about 90 minutes before kickoff (see "Before any ticket" below). |

## Open at close

1. **Closed at 09:49Z:**
   - r8 is hardened and committed (`67562a3`, 43 of 43);
   - r7 passes 18 of 18, committed in `c99ef54`;
   - the weekly conflict is closed: opposite directions on one subject are refused (`f39f57b`, 73 of 73);
   - Sunday's player grading normally goes through ESPN box scores (`espn_fetch`, `967cbd9`). The NFL.com logs tool is only the alternate or archive collector, so its CUTOFF doesn't block grading.
2. **Before any ticket, for Matthew:**
   - **Inactives.** Each club's inactive list goes to the Referee at the officials' meeting 90 minutes before kickoff, per the NFL Football Operations page. bot-advisor checked that page in `5fa1dff`. The page doesn't say when the list is made public. Check the public posting when it's available, then re-check the price at the book. The Referee handoff alone doesn't count as "after the inactives".
   - **Price.** Confirm it meets the limit on the exact contract:
     - KC moneyline at −166 or better, at 18:00Z;
     - Warren over **22.5** receiving yards at −115 or better, at 01:20Z on Nov 16.
   - 23.5 at −110 is a different bet. It can't stand in for the Warren call.
   - Then log the ticket with its placed time.
