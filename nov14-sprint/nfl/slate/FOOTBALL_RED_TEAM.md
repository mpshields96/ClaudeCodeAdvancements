# Football red team: Sunday Nov 15 2026 selections

Writer: Claude NFL red-team writer (a side session of sprint-coord local_50238c87). Written 2026-11-15, about 07:16-07:25Z. Updated 07:30Z for the last-5/last-10 rule and two new official sources. Stop time: 08:59:53Z.
Scope: this is paper and advisory work only. It places no orders and contacts no sportsbook. It edits no engine file: `picker.py`, the selection helpers, frozen_picker and BEST_BETS belong to Codex 01a1de05-7d2e. It made no odds call and read no key.

## Verdicts first

| Candidate (exact market) | Saved price | Break-even | Market fair (vig-free median) | My football read | Verdict |
|---|---|---|---|---|---|
| **KC moneyline** at ATL, 18:00Z | DK -166 (only book at -166; others -172 to -186) | 62.4% | 60.9% | About 59-63%, centre about 61% | **PASS on price.** Keep it only as a labelled process pick (see conditions) |
| **Jaylen Warren receiving yards over 22.5**, PIT@CIN, 01:20Z Nov 16 | BetMGM 22.5 at -115 (only book at 22.5) | 53.5% | About 54-55% at 22.5 (the books' consensus line is 24-25.5) | Positive lean, thin edge. Over 22.5 in 4 of his last 5 and 7 of 8 this season; 6 of 8 against each game's own line | **CONDITION**: only at 22.5 for -115 or better, or 23.5 for -110 or better, after the inactives come out |
| **IND team total under 20.5, FULL GAME** (`team_totals`, not the first half), MIA@IND, 18:00Z | BetMGM U -102 (FD -118, theScore -115; DK has no full-game team total) | 50.5% | 50.0% | Roughly a coin flip; the two sides cancel | **PASS** (agrees with Codex). Condition: +100 or better, full-game market only |

All three prices sit inside the -200 to +200 band. None clears the market's fair price by a margin I would trust. Warren is the only one I would keep live, and then only with conditions. On market numbers, KC at -166 is about -2.4% expected value: 0.609 × 1.602 − 1.

**Period check, as asked.** In the saved odds, "IND under 20.5" is the **full-game** `team_totals` market. The IND first-half team total (`team_totals_h1`) is **10.5**:

- Under prices: DK -135, FD -154, BetMGM -135, theScore -140.
- Vig-free under, median of the four books: 55.2%.
- The best under, -135, needs 57.4% to break even.

So the first-half under is also a pass. A ticket that reads "1st Half" is not the full-game call.

## Sources (saved data only, with capture times)

- **Odds.** `/Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json`, captured 06:55:06Z. Per-book `last_update` times run 06:53:50Z to 06:54:59Z.
- **Codex calls.** `Final_Decisions.json` (decided 07:08:57Z), `Sunday_Card.json` and `Matchup_Review.md`, all in the same folder.
- **Player game logs.** `nov14-sprint/nfl/slate/tools/official_player_logs_20261115.json`, captured from NFL.com at 07:09:25Z, with cutoff before Nov 15.
- **Results and lines.** `nov14-sprint/nfl/data/raw/games.csv`, 2026 rows.
- **Injuries.** `nov14-sprint/nfl/slate/inputs/espn-summary.20261115T065600Z/event_401873058.json` (KC@ATL), `event_401873059.json` (MIA@IND) and `event_401873064.json` (PIT@CIN). The newest entry is 2026-11-15T00:25Z.
- **Depth charts.** `nov14-sprint/nfl/slate/inputs/espn-depthcharts.20261115T065829Z/team_{12,1,11,15,23,4}.json`, timestamps 06:57Z.
- **Official team pages, saved 07:25Z (added 07:30Z):**
  - `nov14-sprint/nfl/slate/inputs/chiefs-injury.20261115T072459Z/`, the chiefs.com Week 10 injury report, retrieved 07:24:59Z, HTTP 200.
  - `nov14-sprint/nfl/slate/inputs/steelers-matchup.20261115T072500Z/`, the steelers.com "Matt's Stats" Week 10 page, retrieved 07:25:00Z, HTTP 200.
- **Warren's prior lines:** each game's own receiving-yards line is in `results/sunday_20261115_candidates.json` (`recent_appearances`). The source is statsniper.com, and the file marks the books and quote times as **not verified**.
- **Now verified from the steelers.com page:**
  - Warren's route share and target share since Dowdle's return.
  - The CIN defense's yards after the catch allowed.
- **Still "Codex-sourced, not verified in saved data":** CIN's receiving yards allowed to running backs (32.2 a game), cited in `Matchup_Review.md`.

**Sample rule (Matthew's standing rule, relayed by the coordinator about 07:30Z; an agent relay).**
- "Last 5" and "last 10" mean a player's consecutive games this season, counted against today's line.
- When fewer than 10 games exist, show the sample that does exist. Don't pad with 2025 games.
- Keep the hit rate against each game's own prior line as a separate figure.
- A team last-5 or last-10 is not required.

This file uses no 2025 or other cross-season player games. Its team figures are 2026 only. The one cross-season number is the model's 54-Sunday past-only backtest in section 1. That tests a betting rule; it is not a form sample.
- **Not known from saved data:**
  - inactives (about 16:30Z for the 18:00Z games, about 23:50Z for PIT@CIN);
  - the prices at ticket time;
  - which of these books Matthew can use in Louisiana;
  - each book's house rules.

Codex's numbers I re-derived and found correct:

- KC scores 25.3 and allows 17.9 per game; ATL scores 20.9 and allows 24.8.
- MIA allows 25.0 per game.
- IND scores 20.4 per game and finished under 20.5 in 4 of 9 games (19, 20, 10, 7).
- IND's last four: 20, 10, 7, 23.

---

## 1. KC moneyline (-166 at DraftKings)

### Why it could lose

1. **Price.** The vig-free median across five books is 60.9%, so fair is about -156. A -166 ticket needs 62.4%. Codex's own independent benchmark in `Matchup_Review.md` is 56.3%, which is further below break-even. The past-only test (`PAST_ONLY_TEST.md`) found market log loss beat the model, and the blend weight is 1.00 on the market. Nothing in the saved data says the market is wrong by two points or more.
2. **Health, depth and workload in the run game.**
   - Kenneth Walker III (RB) is **Out** (groin) and Jaydn Ott (RB) is **Questionable** (hamstring), per ESPN at 2026-11-13/14.
   - The official chiefs.com report agrees. Walker did not practice; he was Questionable on Friday and **Out** on Saturday. Ott was limited all week and is Questionable.
   - The depth chart puts Emmett Johnson next. He has had at most 8 carries in any game this year.
   - KC loses starting OT Jaylon Moore (Out, ankle) and DT Peter Woods (Out, neck). DT Omarr Norman-Lott is also **Out** (knee), and CB Mansoor Delane is **Questionable** (shoulder). Both come from the chiefs.com report.
   - The KC passing game carries the load. Rashee Rice missed weeks 4, 6 and 7, and his last two games were 49 and 53 yards.
3. **Road form.** KC is 2-2 away: W 24-10 at MIA, W 30-27 at LV, L 3-20 at SEA, L 24-28 at DEN. It lost two of its last three road games, and against the spread it is 4-4.
4. **ATL's range of outcomes.** ATL's points swing widely: 35 and 45 in weeks 3-4, then 0 at TB and 17 against CIN. Penix's floor is low (wk8: 125 yards, 4 INT), but ATL has a 3-6 team's upside. Bijan Robinson has rushed 100, 76, 63, 61, 86, 145, 194, 72 and 83 yards, so he can keep KC's offense off the field. A moneyline pays nothing for KC's margin, so every close game is a full loss.
5. **Rate vs volume.** KC's season rate (25.3 for, 17.9 against) includes DEN at home, LAC, NYJ, MIA and LV. ATL allowing 24.8 is partly a volume effect from ATL's high-scoring losses (34 to CAR, 31 to CHI, 34 to CIN). These two rates don't tell you KC is 62% or better at ATL; the market already priced them at -3.

### Points in favour (alternate conclusion)

- KC holds a +7.4 points-per-game differential against ATL's -3.9.
- ATL is 1-3 at home (beat SF 29-20; lost to CAR 3-34, BAL 23-30, CHI 23-31).
- ATL's injuries:
  - WR Zachariah Branch is **Out** (hamstring).
  - LB Divine Deablo is **Out** (forearm). ESPN posted that at 2026-11-14T22:57Z. The ATL Friday report on chiefs.com still lists him as Doubtful.
  - Edge rusher James Pearce Jr. is **Questionable** (back). If Pearce sits, KC's lost left tackle hurts less.
  - DT Gervon Dexter Sr. is **Questionable** (illness).
- My shrunk point-differential estimate (halve both teams' differentials, ATL +1.5 for home field, SD 13.5) gives KC by about 4.2, or about 62%. That is break-even, not an edge.
- The only support for playing it is the past-only rule: model-ranked top-2 money-line favourites returned +1.75% held-out over 54 Sundays. That sample is small and was **not tested inside the -200 to +200 band**.

### Verdict

**PASS at -166.** If the release owner keeps it as a process pick, apply these conditions:

- **(a) Mahomes active and starting.** The depth chart shows Mahomes, then Fields.
  - The official chiefs.com report **does list Mahomes**: knee and right elbow. He practised fully all four days and has no game status. Fields (neck) also practised fully and has no status.
  - So Mahomes is expected to play, but he is not injury-free.
  - A moneyline ticket is not voided by a QB change, so check this before placing, not after.
- **(b) KC's receivers are active at inactives:** Rice, Kelce, Worthy and Josh Downs.
  - On the chiefs.com report, Rice (knee), Kelce (ankle) and Worthy (hamstring) practised fully all week with no game status.
  - Downs is not on the report.
- **(c) Price no worse than -166.** Only DK showed -166; FD was -172, BetMGM and theScore -175, BetRivers -186. If DK has moved, there is no -166 ticket.
- **(d) Label it** in the record as "process pick, market EV negative".

**Spread alternatives don't clear their prices either:**

- KC -3 at DK -110: about 50-51% fair, with a push at 3, against 52.4% needed.
- KC -3.5 at FD +100: 47.8% fair against 50% needed.
- The ATL team total under 22.5 at BetMGM -108 is 50.4% fair against 51.9% needed. This is also a pass.

---

## 2. Jaylen Warren receiving yards over 22.5 (BetMGM, -115)

### Why it could lose

1. **Volume, not rate.** Warren's rate is good: 25 catches for 294 yards, 11.8 yards per catch. His volume is small: catches by week, wk1 to wk8, were 5, 2, 3, 3, 6, 2, 3, 1. At two catches he needs about 11 yards a catch, and **a one-catch game loses almost automatically**. Week 8 against CLE was 1 catch for 0 yards, his last game before the week 9 bye.
2. **Workload split since Rico Dowdle returned.**
   - Dowdle has no stats in weeks 3-5 and was back from week 6.
   - Warren's receiving since: 28, 36, 0, so he cleared 22.5 in 2 of 3 games.
   - Before that, weeks 1-5: 27, 34, 49, 33, 87, all five over.
   - Dowdle's receiving since his return: 3-9, 6-45, 0-0. Week 7, with six catches, shows Dowdle can take the passing-down work.
   - **Verified from the saved steelers.com page (07:25Z):** "Since Dowdle returned from injury, Warren has gotten 65% of the snaps, 59% of the rushing share, 46% of the routes, and 10% of the targets."
     - The page gives no game count. The NFL.com logs show Dowdle back from week 6, so this is probably weeks 6-8 (3 games); that count is my inference.
     - At roughly 30-33 Rodgers attempts, 10% means about 3 targets.
   - **Against each game's own prior line, the post-Dowdle games are 1 of 3:** 28 vs 28.5 (under), 36 vs 25.5 (over), 0 vs 22.5 (under).
3. **Competition from the tight end.** In week 8, when Warren had 0 yards, Darnell Washington had 94 receiving yards. Freiermuth is **Questionable** (illness, ESPN 2026-11-14T17:39Z). If he plays, he and Washington take the short-area targets: Freiermuth's last eight were 35, 20, 11, 44, 17, 30, 32 and 46 yards. If he sits, the extra targets probably go to Washington, not necessarily to Warren.
4. **QB and script.**
   - Rodgers threw only 25 attempts in the wk8 27-6 win and 49 in wk6.
   - If PIT leads, it runs. Warren gets carries (60.5-64.5 rushing line), not receiving yards.
   - If PIT trails late, it is unknown from saved data which back plays the two-minute drill.
   - The call assumes Rodgers starts. Rudolph is QB2. A prop usually stands even if the QB changes, so check this before placing.
5. **Market and line.** 22.5 is **one book's outlier**:

   | Book | Line | Over | Under |
   |---|---|---|---|
   | BetMGM | 22.5 | -115 | -115 |
   | DK | 23.5 | -110 | -114 |
   | FD | 25.5 | -113 | -113 |
   | theScore | 25.5 | -105 | -125 |
   | BetRivers | 27.5 | -115 | -114 |

   The books' consensus fair median is about 24-25 yards. That puts the over at 22.5 near 54-55%, against 53.5% needed. **The whole edge is line-shopping at one book**, and the game is about 18 hours after the capture. If BetMGM moves to 23.5 or higher at -115, most of the edge is gone.

### Points in favour (alternate conclusion)

- **Last 5 and last 10, against today's 22.5.** These are consecutive 2026 games from the NFL.com log (captured 07:09Z); PIT's bye was week 9. No 2025 games are added.

  | Sample | Games (receiving yards) | Over 22.5 |
  |---|---|---|
  | Last 5 (wk4-wk8) | 33, 87, 28, 36, 0 | **4 of 5** |
  | Last 10: only 8 games exist (wk1-wk8) | 27, 34, 49, 33, 87, 28, 36, 0 | **7 of 8** |

  - The median of the 8 games is 33.5 yards.
  - At the other books' lines he is 7 of 8 over 23.5 and over 25.5, and 6 of 8 over 27.5. His last 5 are 4 of 5 at each of those lines.
- **Against each game's own prior line (a separate figure): 6 of 8, and 3 of 5 in his last 5.**
  - The prior lines were 19.5, 18.5, 26.5, 26.5, 22.5, 28.5, 25.5 and 22.5.
  - They come from statsniper.com, and the books and quote times are not verified.
  - He missed in week 6 (28 vs 28.5) and week 8 (0 vs 22.5).
- **Against CIN in week 3:** 3 catches for 49 yards (Dowdle didn't play).
- **PIT's receiver room is thin.** Michael Pittman Jr. is on **IR** (foot) and Roman Wilson on **IR** (finger). The depth chart lists Metcalf, Bernard and Skowronek.
- **Game script.** PIT is a 3.5-point underdog with a 49.5 total and a 22.5 team total; CIN allowed 21.9 per game, 36 to TEN in wk8. That favours a passing script.
- **Yards after the catch (verified, steelers.com 07:25Z).**
  - The CIN defense allows 135.3 yards after the catch per game, which ranks last in the league.
  - PIT gains 139.9 a game; only KC gains more.
  - Warren averages 14.2 yards after the catch per reception. That is more than his 11.8 yards per catch, so his catches start behind the line on average: screens and dump-offs.
- **Target volume (verified, same page).** Warren is PIT's second-leading target-getter, behind DK Metcalf.
- CIN's 32.2 receiving yards allowed per game to running backs is still Codex-sourced and not verified in saved data.

### Verdict

**CONDITION, and the best of the three.** Keep it only if all of these hold:

- **(a) Rodgers is active and starting.**
- **(b) Warren is active, and the inactives (about 23:50Z) or news don't show Dowdle taking third downs.** The baseline is the steelers.com figure since Dowdle's return: 46% of routes and 10% of targets. News of a further cut is a pass.
- **(c) The line and price are 22.5 at -115 or better, or 23.5 at -110 or better.**
- **(d) PASS at 24.5 or above** unless the price is plus money.

Record the line as part of the price: "-115" at 24.5 is a different bet from "-115" at 22.5.

---

## 3. IND team total under 20.5, full game (BetMGM, -102)

### Why it could lose

1. **MIA's defense.** MIA allows 25.0 per game. Only 2 of 8 opponents finished under 20.5 against it (MIN 15, DET 19); the others scored 27, 35, 24, 31, 25 and 24. By rate, IND has an easier matchup than its season average suggests.
2. **MIA's offense creates short fields.**
   - Malik Willis (QB) is on **IR** (abdomen), so Kyle McCord starts. He has no stats in any saved 2026 game, so this is a first start.
   - MIA is also without C Aaron Brewer (**Out**, concussion), WR Jared Wayne (**Out**) and CB Darrell Baker Jr. (**Out**). WR Chris Bell is **Doubtful**.
   - Turnovers and three-and-outs give IND extra possessions and short fields.
   - A defensive or return touchdown counts toward the team total. Each book's house rules decide whether overtime counts; check the slip.
3. **Key numbers.** 20 lands under; 21 (three touchdowns) lands over. IND scored exactly 20, 22 and 23 (twice) this year, so the result sits on a knife edge.
4. **Price.** The market's own lines imply IND at about 20.75-21 points:
   - total 37.5;
   - spreads of IND -4.5 at DK and BetRivers, -4 at BetMGM and theScore, -3.5 at FD.

   That is slightly above 20.5. The vig-free under is 48.6% at BetMGM, 50.0% at theScore and 51.0% at FD, for a median of 50.0%. -102 needs 50.5%.

### Points in favour (alternate conclusion: the under is the better football side)

- **The IND offense that scored 20.4 a game no longer exists.**
  - Keenan Allen and Josh Downs both caught passes for IND in week 9 against DAL (4-26 and 3-24). Downs now sits on KC's depth chart.
  - Alec Pierce is on IR. TE Mo Alie-Cox is on **IR**, TE Will Mallory is **Out**, and OT Jalen Travis is **Out**.
  - The starting WRs are Treadwell, Dulin and Gould. Treadwell's last four games: 0, 18, 19 and 21 yards.
  - Codex also cites the trade of guard Quenton Nelson; I did not see that in saved data.
  - So all of IND's 2026 scoring history overstates this week's offense.
- **Daniel Jones's recent passing yards:** 180, 144, 108 (last three).
- **IND has lost 6 straight** and scored 10 and 7 in weeks 7 and 8.
- **Pace.** A 37.5 total and a run-first IND offense mean fewer possessions. Jonathan Taylor averages about 19 carries.

### Verdict

**PASS at -102.** The football case is real but points both ways: IND's depleted receivers against MIA's soft defense plus the short fields McCord may hand over. The market set 20.5, which is about IND's season average, after the trades. If the release owner wants it anyway, apply these conditions:

- **(a) Full-game `team_totals` 20.5 only.** Not the first-half 10.5, and not an alternate 19.5.
- **(b) Price +100 or better.**
- **(c) Check the house rule on overtime.**
- **(d) Jones is starting and McCord is confirmed for MIA.** If MIA switches to Brady Cook, the short-field argument changes, direction unknown.

---

## 4. Paper vs actual manual sportsbook tickets

These are the differences the record must carry, so a paper "win" is not reported as a ticket result:

1. **A capture quote is not an offered price.** The paper price is a 06:53-06:55Z quote. A real ticket is placed hours later: about 11 hours for the 18:00Z games and about 18 hours for PIT@CIN. Log offered and accepted separately (book, line, price, UTC time). Never back-fill the capture price as "taken".
2. **Single-book outliers.** KC -166 existed only at DK, and Warren 22.5 only at BetMGM. If either book has moved, or isn't one Matthew can use in Louisiana, the paper call has **no matching ticket**. Record "not available at terms", not a worse fill. Louisiana availability per book is **not known** from saved data. Don't assume it.
3. **Line and price together.** For props and totals the minimum term is a (line, price) pair. A "min price -115" with no line is incomplete.
4. **Period and market labels.**
   - The slip must read full game for `team_totals`, or 1st Half for `team_totals_h1`. They are different markets with different lines: 20.5 vs 10.5 for IND.
   - A moneyline ticket includes overtime. Team-total overtime handling follows the book's house rule.
5. **No void on QB or role changes.** A moneyline or team total stands if the QB changes, and a player prop usually stands once the player is active. The conditions above (Mahomes, Rodgers, Warren's role, Jones or McCord) must be checked **before** placing. The paper record should note whether the conditions were checked at the inactives.
6. **Price changes at submit.** Real books can re-price or limit at submission ("odds changed"). Only the accepted price goes on the ticket log. A boosted or promo price must not be mixed into the paper record.
7. **Grading source.** Books grade on their official stat feed at the final whistle. A later stat correction may or may not regrade, depending on the book's rule. A paper grade from NFL.com logs can differ, for example a lateral or a reviewed catch. Note the source used.
8. **Pushes.** All three candidates are on .5 lines, so none can push. KC -3, if anyone swaps to the spread, can.

## 5. One-line summary for the release owner

On price, none of the three clears the market by a trustworthy margin. Keep **Warren over 22.5 as CONDITIONAL**: only at 22.5 for -115 or 23.5 for -110, after the inactives. His record against 22.5 is 4 of his last 5 and 7 of 8 this season. Against each game's own line it is 6 of 8, but only 1 of 3 since Dowdle returned. **PASS KC at -166** (fair about -156), or label it a negative-EV process pick. **PASS the IND full-game under 20.5 at -102**: the receiver losses are offset by MIA's 25-points-allowed defense and McCord's first start.

---

## 6. Engine review (added 07:22Z, read-only)

This section checks the engine's reviewed run at 07:15:44Z (`results/sunday_20261115_selections.json`, stage "reviewed", decided at 07:08:57Z, capture sha 2a50d695...). The code was frozen at picker 25d32a60, selection_markets 420009de and selection_decisions 4b75d3ac. The red team edited none of those files.

**Update 07:31Z.** 7d2e re-froze the engine at 07:29:44Z: picker 5771a47f, selection_markets 91bbfbab, selection_decisions 6898d72c. `apply_overlay` now refuses a second call on a game already used ("Release calls must come from different games within a window"). The set of used games covers the whole run, which is stricter than per window and harmless, since each game sits in one window. The re-run reviewed selections (run 07:29:44Z) keep the same two calls, KC ML and Warren over 22.5. The figures below are unchanged.

**Update 09:34Z.** The engine is now a thin layer over a frozen copy. `selection_decisions.py` (04b53885) replays the 07:08:57Z issued review through `issued_selection_decisions_20261115.py` (6898d72c) unchanged, and applies today's rule to any edited review. Picker is f20da0c2 and selection_markets is 91bbfbab. Today's rule, quoted from `CURRENT_POLICY`: "Up to two distinct contracts per Chicago window. Same-game selections share game risk. Formal calls must agree on direction for each event, period, market and subject." So the 07:29Z same-game ban is gone. Two calls on one game are allowed again, and each lists the other in `same_game_contract_ids`. The reviewed selections were re-run at 09:31:27Z and still hold the same two calls on different games: KC ML (early) and Warren over 22.5 (night). No ticket is recorded. The verdicts below stand.

| Window | Engine call | Captured best | Engine's no-vig number | Needs | Red-team verdict |
|---|---|---|---|---|---|
| early | KC moneyline, floor -166 | DK -166 | 61.16% (median of 4 other books) | 62.41% | **PASS on price.** The engine's own numbers show it 1.25 points short. The model estimate is 60.24%, also short. Keep it only as a labelled process pick. |
| late | pass | none | none | none | Agree. |
| night | Jaylen Warren receiving over 22.5, floor -115 | BetMGM -115 | 50.0%, offering book only (0 other two-sided books) | 53.49% | **CONDITION.** No second book supports this price, so the call rests entirely on the football read in section 2. Take it only at 22.5 for -115 or better (or 23.5 for -110 or better) once the inactives are out, and only if Rodgers starts and Warren keeps the passing-down role. |

The engine does not select the IND full-game under 20.5, which matches the PASS in section 3.

**How a reviewed call clears the engine's gate.** The overlay path in `apply_overlay` asks for at least one two-sided book and a price at or better than the floor. It does not need the market to show positive value. So both released calls are below their break-even price on the engine's own market number. That is the release owner's choice, not a bug, but the page should say so in plain words.

**Floors equal the captured price.** With each floor at the captured price, any adverse move means no ticket. DK -170 or BetMGM -120 at 11:30 CT would leave nothing to place. Record "not available at terms", never a worse fill (section 4, items 1-2).

### Engine repro results (`redteam/test_engine_ids.py`, 26 tests)

Runs:
- **07:21:46Z, on the first freeze:** 2 failures, both under check 6.
- **07:31Z, on the 07:29:44Z freeze:** **all 26 pass (OK).** Check 6 is now PASS.
- **About 08:10Z, the coordinator's run on 7d2e's 08:06Z shim:** 7 of 26 failed. Five were check 4: the first shim dropped the opposite-side refusal. Two were check 6, from the deliberate move to the same-game-allowed policy.
- **09:32Z, on the current engine (04b53885 over 6898d72c):** **all 26 pass (OK).** Check 4 is fixed. Commit f4afac5 (08:23Z, another session) relabeled the two check-6 tests to the current policy: `test_6_distinct_contracts_in_one_game_can_share_a_window` and `test_6_full_game_and_first_half_can_coexist_but_exact_duplicates_cannot`.

The table records the first run.

| # | Check | Result |
|---|---|---|
| 1 | Two players on the same game, market, side and line get distinct ids. `collect()` passes the player as `subject`, and the period is in the id. | PASS. On the real capture, 178 groups hold 2+ players and every one keeps distinct ids (1,756 candidates). |
| 2 | totals and totals_h1 on the same line get distinct ids | PASS |
| 3 | Home and away team_totals get distinct ids, and a team total without a team is refused | PASS |
| 4 | Both sides of one proposition are refused: total, moneyline, spread ±3, player prop, team total | PASS |
| 5 | Nothing is selected outside -200 to +200: all-out-of-band, best-in-band shopping, floor bounds, real calls | PASS |
| 6 | At most 2 per window, **from different games** | **FAIL** (the 2-per-window cap passes; the different-games part fails). `apply_overlay` accepts two calls on one game in one window: full-game total plus a player prop, or full-game total plus totals_h1. The real 07:15Z selections comply (KC@ATL early, PIT@CIN night). ENGINE_HANDOFF.md states only "at most two per window", so this is also a gap in the written rule. |
| 7 | A quote at or after kickoff is refused, as is a missing request time or a review decided at or after the first kickoff. A late-game quote stays valid until its own kickoff. | PASS. All 3,080 quotes in the real candidates file were observed before their own kickoff. |

**Observation (not one of the 7 checks).** On the first freeze a same-player middle passed, for example Over 22.5 plus Under 24.5 on one player. The opposite-side key includes the line, so the two calls counted as different propositions. The 07:29:44Z same-game rule blocked it, because both calls are on one game.

**Middles and cross-market hedges (09:33Z probe on the current engine, scratch script, no source edits).**
- **Same-market middles are refused.** The direction rule now covers them: totals Over 45.5 plus Under 47.5 on one game gets "Duplicate, opposing, or excess review call". Both spread sides at ±3 are also refused.
- **Opposite exposure across two markets of one game is still accepted.** Example: the home moneyline plus the away +3. The written rule allows it, because direction is checked per market. By the same rule, read from the code but not probed, a full-game Over with a first-half Under, or a game Over with a team-total Under, would also pass. This is the release owner's call (01a1de30, engine owner 7d2e). It does not touch today's two calls, which are on different games.

Repro command:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I /Users/matthewshields/Projects/ClaudeCodeAdvancements/nov14-sprint/nfl/slate/redteam/test_engine_ids.py -v
```

## 7. Postgame import review (09:34Z, read-only)

Owners: postgame intake, Codex 01a1de05; journal, Codex 01a1de0b. The red team edited none of their files. They were being edited during the review, so these hashes are from 09:30Z: postgame.py 481bd2f5, espn_fetch.py 8bb9380c, test_espn_boxscore.py fc0f20a9, test_postgame.py 591bc4d9, journal.py c021cbac.

| Check | Result |
|---|---|
| Offline tests | **PASS.** test_postgame.py: 36 OK. test_espn_boxscore.py: 8 OK. The tests use temp dirs and a fake opener, and test_postgame checks that the intake source names no network module. |
| Game matching on today's real slate | **PASS.** One public GET of ESPN's scoreboard for 20261115 at 09:30:48Z (HTTP 200, sha256 fec69adf6c7afbcb…). Each of the 12 ESPN games matches exactly one journal game, so all 12 journal games are covered. ESPN's minute-only times ("2026-11-15T18:00Z") parse to the same instant as the journal's kickoffs. A mismatch would fail safe: that game stays pending. |
| Stat keys on a real box score | **PASS.** CLE at PIT, 2026-11-01 (ESPN 401873027, sha256 6388f92421e6d8e5…). ESPN's machine keys are exactly those in `ESPN_MARKETS`, including the combined "completions/passingAttempts". The contract text named column labels; keys are the steadier choice. |
| End to end, real box score through a throwaway journal | **PASS.** The temp dir was deleted afterwards. Final 27-6 and first half 20-6 were recorded with home and away the right way round. Jaylen Warren got 143 rush yards, 0 receiving yards and 1 reception, which matches his NFL.com log. His first-half rush-yards prop stays pending ("A period-specific player stat is required."). An invented absent player stays pending. A second import adds nothing (5 already recorded). Without fetch receipts the box score still records, relying on ESPN's own final status. |
| Period-specific grading in journal.py | **PASS.** `postgame/journal_quirk_repro.py` exits 0: player props are graded on the exact market, period included. |

Findings. None is a failure.
1. **LOW, display (01a1de05).** The summary's `recorded_finals[...]["h1"]` lists [away, home], while the finals otherwise read home first. The stored values are right (h1_home 20, h1_away 6). A label would prevent a misread.
2. **LOW, journal (01a1de0b).** The folded state keeps the last write. A later hand entry (`journal.py final` or `player-result`) with a different number replaces the earlier one for grading, with no warning. The append-only log keeps both. The intake itself refuses conflicting captures, so only hand entries are exposed. Suggest refusing, or flagging, a second differing value unless a revise flag is given, as tickets already do.
3. **Caveat.** A first-half moneyline tie grades as a push. Check the book's half rule before trusting a graded first-half moneyline.

Scratch probes: `espn_real_acceptance.py` and `middle_probe.py` in this session's scratchpad. They are not committed; they import the source read-only and write only to temp dirs.

## 8. Closeout (09:46Z, read-only)

This check runs against the final release. The red team edited no engine, journal, postgame, release or PDF file.

**Final policy.** Codex relayed it through the coordinator at 09:35Z. Same-game picks are allowed with a shared-risk disclosure. No two formal picks on the same subject may point in opposite directions, at any threshold.

| Check | Result |
|---|---|
| Final engine | **PASS.** `selection_decisions.py` is now 8457d042, committed in 55336a4 by another session. It replaces the 04b53885 working copy reviewed in section 6. The rule text is the same as quoted there. Every check in the proposed review runs before any candidate is updated. |
| Red-team suite at 55336a4 | **PASS, 28 OK** (09:44Z; the repro command above also gives 28 OK). The 26 original tests are joined by 2 that another session added in 55336a4. The first refuses opposite directions at different thresholds for a prop, a game total and a spread, in both input orders, and checks that a refusal leaves the candidates untouched. The second allows a different subject, or the same direction at another line, to share a game. |
| "At any threshold" on the real slate | **PASS.** The engine checks direction once for each event, period, provider market and subject. The 09:31:27Z candidate file has 1,756 contracts in nine provider markets: h2h, spreads, totals, totals_h1, team_totals, team_totals_h1, and passing, rushing and receiving yards. None is an alternate-line market. Every threshold of one proposition therefore shares one key, and no opposing pair can slip through under a second market name. Opposite exposure across two different markets is still allowed, for example moneyline against spread or a full-game total against a first-half total. This answers the section 6 question: the policy's per-market wording allows it, and it does not affect today's calls. |
| Final calls against the policy | **PASS.** The selections are 519c9506 (run 09:31:27Z), with the issued 07:08:57Z review replayed unchanged. Kansas City moneyline is at DraftKings −166 (KC at ATL, early window). Jaylen Warren over 22.5 receiving yards is at BetMGM −115 (PIT at CIN, night window). The two calls are on different games and in different windows, so no shared-risk note is needed. They are not on the same subject, so they cannot point in opposite directions. No ticket is recorded. |
| Final PDF matches the calls | **PASS.** `pdf_export/Sunday_NFL_Brief.pdf` is 0d89417e, one page, 11,230 bytes. It shows the same two formal calls at the 3:35 am CT (09:35Z) prices. Each limit equals its price (−166 and −115). The other three rows are labeled Watch, and the footer reads "No ticket recorded". |
| Postgame import, final code | **PASS.** The code is unchanged since the section 7 hashes (postgame.py 481bd2f5, espn_fetch.py 8bb9380c, journal.py c021cbac; last commits 967cbd9 and 4add245). test_postgame 36 OK, test_espn_boxscore 8 OK and the quirk repro exits 0. The real-data acceptance was re-run at 09:45Z on a throwaway journal: PIT 27–6, first half 20–6, Warren 143 rushing, 0 receiving and 1 reception, with two props pending as before. |
| Actual import into the real journal | **None yet, as expected.** `experiment/data/` has no `finals.jsonl`. Today's first kickoff is 14:30Z, so no Nov 15 final exists. Its owner (01a1de05) runs `espn_fetch.py` once after the games end. The red team did not run it against the real journal. |

**For the PDF owner (01a1de0d / 01a1de30), not a failure.** The headline says Claude would pass on Kansas City at −166, but KC is still listed as a formal conditional pick. The PDF's own price check shows a market-based expected return of −2.4%. The disagreement is disclosed, so the main thing for the reader is that KC is the weaker of the two calls.

**Open notes, unchanged from section 7.** These go to their owners through the coordinator: the first-half order label (01a1de05), the journal's last write winning for a hand entry (01a1de0b), and the caveat that a first-half moneyline tie grades as a push. The red-team scope is finished.
