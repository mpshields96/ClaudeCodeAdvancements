# Sunday watchlist red team (read-only), November 15, 2026

Reviewer: Claude "nfl-props" worker. Stamped 2026-11-15T09:37:35Z (`/bin/date -u`). Paper and advisory only. Nobody places anything.
Reviewed: `results/sunday_20261115_watchlist.json` (ranked_utc 2026-11-15T07:38:26Z, file sha256 prefix 3e6d10dffeed) against the saved five-book feed `sunday-odds.json` (captured 2026-11-15T06:55:06Z, sha256 prefix 2a50d6951366).
Not touched: the watchlist, the feed, the engine, the picker or any price. No request for a price was made. This file is the only write.
Labels: **K** known/sourced, **E** estimated (arithmetic shown), **U** unknown. Times are UTC. Event ids are not repeated here.

## 1. Verdicts

No row FAILS a contract check. Every row carries at least one FLAG, so the list is usable as a watchlist and not as five clean calls. **Four of the five rows price below break-even on the market's own no-vig number (E).** The fifth is break-even to the second decimal. The coordinator had named three rows (1, 3, 5); rows 2 and 4 are also on the list below.

| # | Contract | Row | Overall | One-line reason |
|---|---|---|---|---|
| 1 | Jaylen Warren over 22.5 receiving yards, BetMGM −115 | formal | **FLAG** | Contract exact. Single book at that line, 3.49 points below break-even, role cut since the Dowdle return, conditions not printed on the row. |
| 2 | Kansas City Chiefs to win, DraftKings −166 | formal | **FLAG** | Contract exact. 1.25 points below break-even, sitting at the stated price ceiling; the replacement-role effect on win probability is unknown. |
| 3 | Detroit first-half team total under 13.5, BetMGM −105 | watchlist only | **FLAG** | Contract exact. 1.22 points below break-even; the 6 of 8 and 5 of 9 counts rest on an undated play-by-play source; not covered by the football red team. |
| 4 | Indianapolis team total (full game) under 20.5, BetMGM −102 | watchlist only | **FLAG (minor)** | Contract exact. Break-even within 0.02 points. "Lost receiving personnel" has no dated source and the trade date is U. |
| 5 | Brock Bowers over 58.5 receiving yards, BetRivers −113 | watchlist only | **FLAG** | Contract exact, denominators true. 2.84 points below break-even; every one of the seven overs came with Kirk Cousins at quarterback. |

## 2. Contract checks (all five rows)

Method: for each row I looked up the event, book, market, period, participant, side, point and price in the feed's `games` and `event_odds` lists and compared with the row. K for every cell below.

| # | Market / period / participant | Side & point | Book & price | In −200..+200 | observed_utc | Before kickoff | provider_updated_utc | Result |
|---|---|---|---|---|---|---|---|---|
| 1 | player_reception_yds, full game, Jaylen Warren | Over 22.5 | betmgm −115 | yes | 06:55:06Z | yes (kickoff Nov 16 01:20Z) | 06:54:41Z | PASS |
| 2 | h2h, full game, team side Kansas City | n/a | draftkings −166 | yes | 06:55:04Z | yes (18:00Z) | 06:53:59Z | PASS |
| 3 | team_totals_h1, first half, Detroit Lions | Under 13.5 | betmgm −105 | yes | 06:55:04Z | yes (14:30Z) | 06:54:08Z | PASS |
| 4 | team_totals, full game, Indianapolis Colts | Under 20.5 | betmgm −102 | yes | 06:55:05Z | yes (18:00Z) | 06:54:40Z | PASS |
| 5 | player_reception_yds, full game, Brock Bowers | Over 58.5 | betrivers −113 | yes | 06:55:05Z | yes (21:05Z) | 06:54:40Z | PASS |

- **Capture floor:** all five were observed 06:55:04Z to 06:55:06Z, inside the "06:55Z capture or later" window and before every kickoff. PASS.
- **Participant and period conflation:** none found. Row 3 is the Detroit first-half team total, not the first-half game total and not Detroit's full-game total. Row 4 is the Colts full-game team total, not the first-half 10.5 line. The row-4 history (last four scores 20, 10, 7, 23) is full-game, which matches the contract. Row 1 and row 5 are player receiving yards, and both logs are the same participant and the same stat. PASS.
- **Duplicates:** five different games, five different contracts, one per game. No duplicate. PASS.
- **Staleness of the captured price:** the prices are the 06:55Z snapshot, now about 2 h 40 min old at stamp time (E). The watchlist says each row "requires a personal recheck" and expires at its kickoff. That is the right label. I did not re-request any price, so I cannot say what each price is now (U).

## 3. Price check, row by row

Break-even = implied probability of the offered price. Market probability = the watchlist's own number, which is a no-vig average of the other books' two-sided quotes where any exist. Gap = market minus break-even, in percentage points. A negative gap means the price needs more wins than the market's own margin-free estimate supports.

| # | Break-even (K) | Market probability (K, per watchlist) | Basis the watchlist states | Gap (E) | Books at exact line / other two-sided |
|---|---|---|---|---|---|
| 1 | 53.49% | 50.00% | offering book only | −3.49 | 1 / 0 |
| 2 | 62.41% | 61.16% | other books | −1.25 | 5 / 4 |
| 3 | 51.22% | 50.00% | other books | −1.22 | 4 / 3 |
| 4 | 50.50% | 50.52% | other books | +0.02 | 3 / 2 |
| 5 | 53.05% | 50.21% | other books | −2.84 | 3 / 2 |

- **"Unknown when only one book" (your check):** row 1 is the only row with one book at the exact line. The watchlist labels its basis "offering book only", prints 0 other books, and its fit text says "the only exact-line quote needs 53.5%". That is the honest label. PASS. But the printed 50.00% is MGM's own symmetric −115/−115 margin-free number. It is not independent confirmation of a fair price and should not be read as a market consensus. The other books post different lines: DraftKings 23.5 at −110, and others 24 to 25.5 (K, feed).
- **Row 3 cross-check (E, recomputed from the per-book prices):** the four-book margin-free under is MGM 49.22%, DraftKings 50.00%, theScore Bet 47.97%, FanDuel 50.41%. The median of all four is 49.61%, which matches the 49.6% in `Matchup_Review.md`. The watchlist's 50.00% is the median of the three books other than MGM. Both are labelled correctly. Against the four-book median the gap is −1.61, a little worse than the −1.22 on the row.
- **Row 4 cross-check (E):** MGM's own two-sided no-vig on its under is 48.56% (−102 under, −115 over). The row's 50.52% comes from the other two books and is the better basis. On either number the price is at or below fair. Only DraftKings has no full-game team total.
- **Row 5 cross-check (E):** BetRivers' own two-sided no-vig on the over is 49.50% (−113 over, −118 under), so the gap against its own margin is −3.55. The row's −2.84 uses the other books.
- **Row 2:** `Matchup_Review.md` sets the ceiling at −166 and says "keep the price ceiling at −166". The row is exactly at that ceiling. `FOOTBALL_RED_TEAM.md` says PASS on price with fair about −156 (that file's figure; I did not rebuild it), or label it a process pick. The independent benchmark in the Matchup Review is 56.3% (K, that file) against 62.41% break-even.
- **Disclosure gap (FLAG, rows 3 and 5):** the fit text for rows 1 and 2 says the price is worse than the market ("needs 53.5%", "needs more wins than the peer estimate"). The fit text for rows 3 and 5 does not say so. Row 3 prints only "The best exact under is −105". Row 5 does not mention the price at all. The numbers are in the break_even and market_probability fields, so nothing is hidden, but a reader of the PDF line would not see that these two also price below fair. Suggest printing the gap beside every row.

## 4. Ranking method, status clarity, volatility honesty

- **Ranking method named (your check): PASS.** `method` and `method_type` state an editorial ranking of the football case plus exact-price comparison, "a price or historical hit rate alone cannot determine rank", one contract per game, and "no statistical variance was estimated". It does not claim a model, an EV rank or a probability rank. Because four of five rows price below break-even, the editorial order is a football-first order, and the PDF should say so in one sentence next to the list. The `method` text does say it; the page layout may not.
- **Status clarity: PASS with a FLAG.** Rows 1 and 2 are `formal_call: true`, rows 3 to 5 are `watchlist_only` and `formal_call: false`. `formal_call_counts` reads early 1, night 1, late 0, which matches: the Chiefs (noon) is early, Warren (7:20 p.m.) is night, and nothing is formal in the 3:05 p.m. window (Bowers is watchlist only). FLAG: row 1's formal status is conditional in `FOOTBALL_RED_TEAM.md` ("only at 22.5 at −115 or better, or 23.5 at −110 or better, after the inactives", about 23:50Z for that game, E from the 90-minute rule). The row says "conditional case" and carries the tag "PIT inactives / shared targets", but the numeric condition itself is not printed on it.
- **Volatility and risk-tag honesty: PASS.** Volatility is stated as qualitative. High for Warren, Detroit first half and Bowers; Moderate for Kansas City and Indianapolis. Each tag names a real driver that I could source: shared targets, injured starters, short half, short fields, first-start quarterback. I would not downgrade any of them. If anything Kansas City's "Moderate" is generous given the unknown backfield effect (section 6), but I have no number that says it should be higher.

## 5. Row findings

### Row 1. Warren over 22.5 receiving yards (MGM −115). FLAG

- **Hit rate against today's line (K):** NFL.com game log, retrieved 07:09:24Z. Last 5 consecutive current-season games: **4 of 5** (weeks 4 to 8: 33, 87, 28, 36, 0). Last 10 not available; only eight games exist, so **7 of 8** (adds weeks 1 to 3: 27, 34, 49). Season average 36.75 over 8 games. Never padded with last season.
- **Against each game's own prior line (third party, books and quote times unverified, U):** Stat Sniper shows 6 of 8 overall, 3 of 5 in the last five, 1 of 3 in the last three (`PROP_REVIEW.md` lines 96 to 100; `Matchup_Review.md` repeats 6 of 8). Kept separate from the 22.5 count above. The week-6 miss was 28 against a 28.5 line.
- **Role (K, Steelers.com retrieved 07:25:00Z, publication time U):** since Rico Dowdle returned, Warren ran 46% of routes with a 10% target share. His most recent game was 0 yards (one catch for zero on two targets).
- **TE news (K, ESPN 2026-11-14T17:39Z):** Pat Freiermuth (illness) and Harmon are questionable. Darnell Washington had 94 yards in week 8, when Warren had 0. Freiermuth being out would help Warren's target share in principle; this is an interpretation, not a sourced rate.
- **Price:** one book at 22.5 (MGM). Wilson interval on 7 of 8 is about 53% to 98% (`PROP_REVIEW.md`; I did not recompute it). Both football reviews keep a conditional case only.
- **Missing from the row:** the numeric condition (22.5 at −115 or better, or 23.5 at −110 or better, after inactives) and the 46% route and 10% target figures. The fit text mentions only that Dowdle "shares passing work".
- **Falsifier:** Freiermuth plays, Dowdle takes the passing-down snaps, or the line moves up at MGM.

### Row 2. Kansas City to win (DK −166). FLAG

- **Price:** five-book moneylines at capture: DraftKings −166, FanDuel −172, MGM −175, theScore Bet −175, BetRivers −186 (K, feed, updated 06:53:59Z to 06:54:59Z). DK is the best price. See section 3 for the gap and the ceiling.
- **Roles (K unless noted):** Kenneth Walker III is OUT (NFL.com story 2026-11-14T17:16:42Z). Emmett Johnson has 26 carries for 111 yards over eight 2026 appearances and never more than eight in one game; he has no sample of leading a backfield. Three books posted 16.5 carries for Johnson (observed about 07:52Z; DK over −116 / under −110; MGM and theScore over −120 / under −110; no-vig about 50.6% to 51.0% for 17 or more). His rushing line runs 72.5 to 75.5 across five books. Left tackle Jaylon Moore is OUT. Jaydn Ott is questionable and Nate Carter was elevated from the practice squad. Goal-line and passing-down roles are unconfirmed.
- **What the market already contains (E):** the capture is after the Walker downgrade, so the −166 already prices Walker's absence. A pre-news price does not exist in the capture, so the marginal effect of the absence on win probability is U. The replacement screen records it as unknown and adjusts nothing (`replacement_context`: win_probability_adjustment null, auto_upgrade false).
- **Historical check from Codex's cross-check (K, that file):** across 2022 to 2025 the next back led or tied his team's backs in carries in 17 of 23 qualifying games, and team RB rushing yards fell in 14 of the 23. That is a challenge to any automatic injury rule, not a repricing.
- **Green Bay committee (separate game, same replacement logic, K):** Josh Jacobs is OUT. Chris Brooks was activated Nov 14 and is questionable. The Nov 10 depth chart lists MarShawn Lloyd above Kaleb Johnson, but the Nov 13 team reporter's read is that Johnson has moved ahead. That is the reporter's interpretation and not a dated club statement. Same-book rush lines: Kaleb Johnson 28.5 to 29.5, Lloyd 10.5 to 11.5. On Nov 8 Johnson had 14 carries for 68 yards, Pierre Strong eight for 22 and Jacobs four for five, but Green Bay led 42 to 21 entering the fourth quarter and half of Johnson's yards came on one 34-yard run. Outcome: **committee_possible**. Nothing auto-upgrades or downgrades a call. No Green Bay row is on the watchlist.
- **Falsifier:** the final inactives (about 16:30Z for a noon kickoff, E) show a different healthy back set, or Johnson's carries stay at or below single digits into the second quarter.

### Row 3. Detroit first-half team total under 13.5 (MGM −105). FLAG

- **Claim traced:** "Detroit stayed below 13.5 in six of eight first halves, and New England allowed fewer than 14 in five of nine" comes from `Matchup_Review.md` ("Detroit stayed under in 6/8, New England allowed fewer than 14 in 5/9"), which cites nflverse play-by-play. The source has no capture time in that file, so the counts carry **no UTC time (U)**. I did not download the play-by-play (a download needs Matthew's OK) and I did not recompute the counts. They are therefore unverified by me.
- **Period:** the Matchup Review heads this row "Detroit first-half team total under 13.5", so the period matches the contract. Scores are whole numbers, so "fewer than 14" and "below 13.5" are the same event. Whether the New England "5/9" count is first-half or full-game points is not stated in the cell I read (U). PASS on the contract, FLAG on that count.
- **Context (K, Matchup Review):** neutral-site Munich game; center Cade Mays OUT; Amon-Ra St. Brown questionable; Patriots corner Carlton Davis OUT, which helps Detroit's passing game. The review's own verdict is "Mixed evidence on a neutral field".
- **Game environment (K, feed):** Detroit −2.5 with a game total of 49.5, moneylines −145 to −148. That implies about 26.0 Detroit points (E, (49.5 + 2.5) / 2), so a first-half line of 13.5 is about half the implied game total. The market has priced the under near fair; the row is a close call, not a mispricing.
- **Coverage gap (FLAG):** `FOOTBALL_RED_TEAM.md` has no Detroit section. This row has the Matchup Review's note and the release reviewer's pass, and no independent football red team.
- **Falsifier:** St. Brown active, or Detroit scores on its first two drives.

### Row 4. Indianapolis team total under 20.5, full game (MGM −102). FLAG (minor)

- **Claim traced:** "stayed under in three of its last four": Matchup Review lists the last four Colts scores as 20, 10, 7 and 23 (three at or below 20 against a 20.5 line). Season: 20.4 points per game, 4 of 9 below 20.5. At home: 23, 19, 20, 23, so 2 of 4 under. Miami opponents: 2 of 8 below 20.5 for the season, 1 of 4 in the last four. All K per that file; the order of the last four and the dates are not given.
- **"Lost receiving personnel" (your check):** the claim is supported by the Matchup Review's naming of the trades of Keenan Allen and Josh Downs (who drew 14 of Daniel Jones's 34 attempts last week), Alec Pierce on injured reserve and Mo Alie-Cox OUT. The sources are Colts preview, injury and depth-chart pages that carry **no dates in the review (U)**, and the **trade date is U**. If the trades preceded the last four games, the "3 of 4" already reflects the lost players. If they were mid-window, the sample straddles the change. Daniel Jones's passing yards in the last three games (108, 144, 180) are K per that file.
- **Offsetting facts (K):** Miami starts rookie Kyle McCord in his first game, center Aaron Brewer is out, Zach Sieler is lost. Miami gave up at least 100 team rushing yards in six of eight games. A short-field or defensive touchdown counts toward the team total.
- **Game environment (K, feed):** Indianapolis −3.5 to −4.5, game total 37.5. A 37.5 total with Indianapolis favored implies a team total near the 20.5 line, so there is no cushion either side.
- **Reviews:** Matchup Review "Pass at −102 BetMGM"; `FOOTBALL_RED_TEAM.md` "PASS (agrees with Codex), condition +100 or better, full-game market only". The row's own price is −102, so it does not meet the red team's +100 condition. FLAG.
- **Falsifier:** an early Indianapolis defensive or special-teams touchdown, or Miami turning over inside its own 40.

### Row 5. Bowers over 58.5 receiving yards (BetRivers −113). FLAG

- **"Five of five and all seven" (your check): PASS on the numbers.** NFL.com game log (retrieved 07:09:17Z): weeks 5 to 9 = 110, 70, 73, 92, 111 (last 5 consecutive, **5 of 5**, minimum 70); adding week 4 = 86 and week 3 = 116 gives **7 of 7**. Season average 94.0 over seven games. No padding from last season. The log has blank rows for Weeks 1 and 2. **The reason is U**: the saved logs file has no entry for Bowers in its confirmed-no-stats list, and the Raiders injury page I saw lists only older headlines. A DNP, an injury or a roster move are all possible.
- **Quarterback (your LV QB conflict): resolved, with one open time-zone caveat.** Raiders.com "Fernando Mendoza named Raiders starting quarterback" shows **published Nov 10, 2026, 3:07 PM (time zone not stated, so no UTC time)**; the saved copy, retrieved 07:20:03Z, has published null. General manager John Spytek named Mendoza the starter ahead of Week 10. Kirk Cousins was traded to Minnesota for a 2027 third-round pick; **the trade date is U**. The club says Mendoza's prior NFL passing came in relief, so this is effectively his first NFL start. All seven overs came with Cousins. There is no Mendoza-throwing-to-Bowers sample: **n = 0 (K)**. That is the main reason this row stays watchlist only.
- **Availability (K):** raiders.com Week 10 injury report, **published Nov 13, 2026, 2:05 PM (time zone not stated)**: Bowers is not listed. Dont'e Thornton (WR, back) is questionable. Ian Thomas (TE, ankle) and Trey Zuhn (G) are full with no designation. No quarterbacks are listed. Final inactives are U until about 19:35Z (E).
- **Opponent (K, Matchup Review):** Seattle held entire opposing tight-end groups to 42.1 yards per game, but the last three groups managed 88, 65 and 73, each above Bowers' 58.5 line, though they are group totals and not one player. Seattle quarterback Sam Darnold, left tackle Charles Cross and guard Quenton Nelson are out. The Matchup Review's verdict is "Pass on Bowers... at these prices".
- **Fit text check:** the watchlist fit text does state the first-start quarterback fact and the 42.1 figure, so the quarterback risk is disclosed. It omits the 88, 65 and 73 recent trend, which would be the supportive side of the evidence, and it omits the price gap (section 3). FLAG, completeness only.
- **Game environment (K, feed):** Seattle −6.5, total 40.5, Las Vegas moneyline +225 to +245. A trailing home team with a low total is a pass-leaning script, which helps the over, but 40.5 caps the offence.
- **Falsifier:** Bowers is inactive or limited, Mendoza is replaced early, or Las Vegas is held near its implied 17.0 points (E, (40.5 − 6.5) / 2) or lower.

## 6. What the owners should do (routes, with the repro)

1. **Watchlist owner (the integrated release owner):** print the gap beside rows 3 and 5, add the numeric Warren condition (22.5 at −115 or better; 23.5 at −110 or better; after the inactives at about 23:50Z), and add the Bowers 88, 65, 73 trend. Repro: compare `ranked[*].break_even` with `ranked[*].market_probability` in the watchlist, and read lines 40 to 44 of `build_watchlist.py` for the fit text.
2. **Row 4:** the red team's condition is +100 or better and the row's price is −102. Either say the price is outside that condition or leave it off the list.
3. **Row 3 and row 4 sources:** attach a retrieval time and the play-by-play file (or its hash) that produced "6 of 8", "5 of 9" and "3 of 4", and the date of the Colts trades. Until then these are U. A download needs Matthew's OK; I did not do it.
4. **Row 5:** if the PDF keeps this on the list, show "n = 0 with Mendoza" next to the 7 of 7.
5. **After inactives:** recheck rows in kickoff order. Rows 3 and 4 and 2 first (about 13:00Z and 16:30Z), then Bowers (about 19:35Z), then Warren (about 23:50Z). All times E from the standard 90-minute rule.

## 7. Limits of this review

- I did not re-request any price. Everything is the 06:55Z snapshot.
- I did not recompute the play-by-play counts (rows 3 and 4) or the Stat Sniper history (row 1).
- Dated pages from raiders.com and NFL.com show a local time without a zone. I report them as published, without converting.
- Third-party history and reporter interpretation are labelled as such and never merged with sourced counts.
- Past hit rates are not forecasts. A paper pass here does not authorize anything, and Matthew places any wager himself.
