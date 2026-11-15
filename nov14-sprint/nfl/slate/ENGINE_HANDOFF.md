# Sunday NFL picker handoff

Updated November 15, 2026 at 07:33 UTC. Codex chat 01a1de05-7d2e-7050-b922-7b693464df4c owns picker.py, selection_markets.py, selection_decisions.py, the freeze, its regression tests and the generated NFL card. Claude's corrected ASSIGNMENTS_0712Z.md confirms the single writer. Technical release owner 01a1de0b-7734-7342-a71b-d7ef4fffeada owns the launcher and integration. Release owner 01a1dc37-64b4-7093-ba7b-25e09229fbb1 owns the issued review. The original supervisor handed off and parked. Sprint hard stop 08:59:53 UTC. The picker reads agent-made saved data locally.

## Verified entry point

From the sprint root, run:

    /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -IB nfl/slate/picker.py slate --odds /Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json

The archived snapshot completed at 06:55:06 UTC. Its SHA-256 is 2a50d6951366342f8656ee01e113c44cceff0acdfa027ea933f9286c0c73d56f. The adjacent Final_Decisions.json matches this digest. The engine checks its 07:08:57 UTC issuance time, exact contract, book floor, direction, window maximum and distinct game. The call requires an in-band offer at or above the personal price floor. A neighboring review from a different capture is inapplicable. An explicit --decisions file with a mismatched hash is rejected. Without a bound review the page clearly labels the provisional screen. The feed and exact-price verification stay with the release owner.

The standard outputs are nfl/BEST_BETS_SUN_NOV15.md, nfl/BEST_BETS_SUN_NOV15.html, nfl/slate/results/sunday_20261115_selections.json and nfl/slate/results/sunday_20261115_candidates.json. The small record's calls array is compatible with verify_card.py. The full record retains all 1,756 unique exact contracts from 3,080 quoted sides, including 36 outside the personal price band. It includes each book's retrieval and provider-update times, comparable prices, 12 matchup joins and 1,460 player contract-side joins. IDs include event, period, market, player/team, side and exact line.

## Decisions and evidence

The review selects Kansas City to win at Atlanta at noon Chicago, DraftKings −166 or better, no afternoon selection, and Jaylen Warren over exactly 22.5 receiving yards at Cincinnati at 7:20 p.m. Chicago, BetMGM −115 or better. The record preserves the original involvement and quarterback conditions. Its market-only controls and provisional screen are comparisons. It contains zero tickets. No personally offered odds, accepted stake, closing price, game result or profit was observed by this worker.

Each selected record contains known, estimated and unknown evidence. KC's Saturday team publication lists Walker, Moore and Woods out, Ott and Delane questionable; the league report had Walker questionable. Final inactives remain unknown. KC's four other books imply 61.2% versus 60.9% across all five and a 62.4% break-even. The independent football reviewer would pass at −166. Warren's single exact-line book implies 50.0% versus 53.5% break-even. Other receiving-yard thresholds cannot supply a peer probability at 22.5.

Matthew's latest definition of last five/ten applies mainly to consecutive **current-season player appearances**, keeping verified zeros and showing the available denominator. Warren is 4/5 and 7/8 at today's 22.5 in those windows. The eight paired third-party historical thresholds produce 6/8 with historical bookmaker/timestamp unknown. The two calculations are independent of ticket economics.

The 07:29:44 UTC pregame freeze binds code, parameters, hypothesis and controls. picker.py SHA-256 5771a47f31a13731efd64cbbda31c47a35c23d26560680dafb1a40a0d015df11. Rule development and the separate release review had access to Sunday's prices before this freeze. Claim only a prospective outcome test. The expanded official evidence supplemented the issued review later. Previous records are preserved, and same-evidence reruns keep the recorded decision timestamp. Team and player context cannot replace a quoted price.

The clean historical window is 2026 completed regular-season Weeks 1–9, with 136 completed games and 135 decided, priced moneylines. Market log loss was 0.6223, independent model 0.6306. The 2023–25 comparison remains. Predictions for all games on a date are made before that date's results update the model. The nine-Sunday unrestricted historical ranking is too small and differs from the live cross-market rule.

## Reproduction and downstream ownership

    /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -IB nfl/slate/picker.py backtest
    /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -IB nfl/slate/redteam/test_engine_ids.py
    /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -IB nfl/slate/tests/test_picker_grading.py

The independent engine suite passed 26 tests, including 178 same-line player groups, two calls from distinct games, after-kickoff exclusion, both sides of a proposition and exact price bounds. All four settlement regressions passed. The saved pregame CSV grades 0 of 1,756 candidates. Ten additional worker checks exercised the real release overlay, dates, band, neutral venue, cutoff and absence of same-day score leakage. The real legacy --lines formats also ran in isolated output folders. The Nov 14 single-book display supplied 74 contracts, without enough other books for the provisional screen. The 360-side Nov 15 normalized game feed supplied 108 game contracts. Neither was mixed into the canonical live selection pool. The earlier ESPN display appears only as labeled, same-book historical movement.

A different run may use --out-dir DIR --report-dir DIR. Run freeze only for a deliberate pre-kickoff rule revision. --replace archives a superseded decision dataset before publishing. Reproducing calls requires the same bound overlay and snapshot. Decisions use event_id, market, subject, side, point, minimum_price, rationale, risk, optional condition and source URLs, plus top-level author, decided_utc, capture_sha256 and window_notes keyed early/late/night.

Claude's workflow owner provides the separate journal, challenge, ticket and matched-control settlement. The report/PDF owner follows the exact standing requirements in /Users/matthewshields/Documents/Codex/2026-11-15/nfl-edge-advisor/outputs/Matthew_NFL_and_Trading_Report_Requirements.md. The one-page PDF is at nfl/slate/pdf_export/Sunday_NFL_Brief.pdf. Launch integration, final paper-versus-real reconciliation, and supervised sportsbook use have separate owners. The trading review is separate. No dedicated Your Dot messaging tool was exposed here. The technical owner has the final files and the request for Claude bot-advisor's targeted re-review.

## Top five and supplemental evidence

The separate 07:38:26 UTC editorial ranking uses five distinct games from the documented review pool. It retains the two issued calls and marks the three others watchlist only. Run `/usr/bin/python3 -IB nfl/slate/build_watchlist.py` for nfl/slate/results/sunday_20261115_watchlist.json. The one-page PDF and the production HTML desk were independently checked against all five exact ranked contracts. The original watchlist is archived. The current sheet also identifies the subsequent player appearance input v2 SHA-256 7f202c76572738e0329e8c9721fbaacee06333008748a019d05880c380b50980. It verifies Warren and Bowers' consecutive 2026 appearance samples. The snapshot, freeze and formal floors are unchanged.

The separate nfl/slate/results/sunday_20261115_review_evidence.json provides Pittsburgh's open questionables, the saved official log receipt for Warren's one catch for zero yards, and the nine halftime scores underlying each Arizona/Rams figure. The technical owner renders it on the detail surface. The full local play-by-play archive has a verified SHA and no network retrieval receipt. Its local modification time is marked separately.

## Reusable weekly screen and supplementary personnel review

The weekly market API and `weekly_football.enrich(screen)` run offline on the actual November 22 schedule and the 07:34:18 UTC edition. The archive ends November 12, with Week 9 the latest fully scored week. Both sides' year-to-date and recent team form, intervening games, venue treatment and uncertainty are attached by event. The model agrees with five distinct in-band opportunities in this edition. The corrected two-contract-per-window shortlist includes two early and two late. The two late contracts share NYJ–LAC and carry a shared-game caution. All five potential bets are watchlist opportunities until separate human review. Potential rows use the same eligibility with unique contract IDs and no per-window cap. Run `/usr/bin/python3 -IB nfl/slate/tests/test_weekly_football.py` from the sprint root.

The issued source at commit a6f4383 is preserved byte-for-byte as `issued_picker_20261115.py`. The normal `picker.py` command uses those actual bytes and the original helper hashes for freeze verification. An additional release layer attaches pregame supplementary evidence to the issued contract after selection. The evidence intake and display are separate from the 07:08:57 UTC call and 07:29:44 UTC rule freeze. The official floors, offers, forecasts and conditions remain pinned in the historical record. The final source-bound replay and test counts appear below.


## Current review eligibility and research

The live per-window limit is two distinct contracts, including two from one game. Duplicate and opposing sides of the same proposition and a third selection in a window remain disallowed. The frozen Nov 15 release uses its historical validation helper, preserved as `issued_selection_decisions_20261115.py` with SHA-256 6898d72cca26951dab4b86d36587618eb93b8b528dba7c12d74750b39535d608. An isolated normal CLI replay selected two different contracts from the same Sunday night game and returned mutual links and a shared-game caution. It used a synthetic review on real captured prices and did not create a formal call. The historical release remains KC / afternoon pass / Warren.

Gemini public research located the NFL Next Gen Stats team's [expected rushing yards methodology](https://www.nfl.com/news/next-gen-stats-intro-to-expected-rushing-yards), which Codex independently verified. NFL compares actual gains to expected rushing gains conditional on blocker and defender tracking at handoff. Raw yards per carry for different workloads is descriptive. It cannot isolate a player's effect on team win probability. No new tracking observations were incorporated into this slate.

The weekly availability importer reads the source owner's saved, schedule-bound feed by ESPN event ID, team, kickoff and retrieval time. `enrich(..., inputs_root=...)` supports a different inputs folder. Nov 22 currently has no Week 11 designations. When an Out/Doubtful listed-first player lacks a matched review of that same player on that team, the specific unresolved players and source times are exposed and that game's full-game team shortlist is held. This check changes no team rating. The real saved Week 10 Minnesota/Green Bay case exercises independently missing players. The normal portable historical CLI selects `release_data/sunday-odds.json` when present and no source override is supplied.

## Release check, November 15, 09:36 UTC

The normal offline picker reissued the two original paper calls with the producer’s final 09:28:45 UTC role source. SHA-256 digests:

| File | SHA-256 |
| --- | --- |
| replacements/replacement_report_20261115.json | 3eb139dd886649f6267de003d7ff5399868c4a1e67b1588f1ab0871b20f7159a |
| results/sunday_20261115_candidates.json | ae6f1781efbaa846f803c70cdb6469ddeb536541beffcd8a24f1ca5b6dd5047e |
| results/sunday_20261115_selections.json | 519c9506d143113ff7cb1334e496dbd987d6c1935bc45ebdf5df445ad51ffdd3 |
| selection_release.py | 245814a5bf4ed0c4800130716f053ad8908f9cc5b5c15cd609d2367672fd6e88 |
| selection_decisions.py | 8457d0422a9cb4a88866824530a38a2dc285fa5602dcefbbe732f60c48567dad |

The release owner kept two distinct formal picks per Chicago window, including contracts in the same game. The edited-review shim rejects opposing directions for the same event, period, market and subject across all thresholds. Its cross-call checks run before any candidate is updated. Two permitted calls sharing a game carry linked IDs and a shared-risk note. Operator commentary can still discuss both sides. Native weekly writer d0efdc45 owns the equivalent dated intake and tests. Release owner 01a1de30 owns final quote verification, PDF integration and publication.

The red-team suite passed 28 tests. It covers all five exact-line conflicts and the three requested differing-line cases in both input orders, plus distinct subjects, periods, and allied same-game calls. The real input had 1,756 contracts and 178 player groups sharing an otherwise identical descriptor. Four grading tests, seven selection attachment tests and seven weekly football tests passed. The weekly check now holds an unassessed listed-first or source-backed operator-identified material absence even when another player on that team has an assessed replacement. An ordinary unconfirmed role qualifies the projection. No injury coefficient is applied. The club-note join uses the screen generation timestamp.

The 11 separate entry-point checks are in `/Users/matthewshields/Documents/Codex/2026-11-15/sunday-nfl-canonical-entry/work/check_selection.py`. They cover release card and floors, identity across subject/period, bounds and better quote, neutral venue and weeks, two calls and pass, invalid floor/hash/ID/period/window limit, same-game correlation, unaccepted quotes, half/prop settlement, stale scoring CSV and date-level leakage. Run with `/usr/bin/python3 -IB <check_selection.py> nfl/slate/picker.py <saved-sunday-odds.json>`. All 11 passed. They are separate from the four settlement tests.

Both historical r5 and current r6 evidence checks pass (3/3 and 23/23). The saved official Warren page SHA-256 is 0c9afd1347344c25d22b5d63195c8141ae5c62a17bf76cdfb61e742690e38328, retrieved 07:44:13 UTC. The pass identifies the play-by-play source, digest, and local timestamp. Its original network retrieval time is unknown. The formal Warren row and Markdown name questionable Pat Freiermuth and Derrick Harmon. Each call still has zero accepted tickets.

Fresh successor 01a1de8d-ba6e-7ef2-acd4-469573427c06 verified and accepted the watchlist and downstream release handoff. It owns the dated personnel/value supplement to the original 07:38:26 UTC ranks. No follow-up development is needed to use the Sunday paper card. The integrator owns closeout in Matthew’s renewed session ending 11:23:32 UTC.
