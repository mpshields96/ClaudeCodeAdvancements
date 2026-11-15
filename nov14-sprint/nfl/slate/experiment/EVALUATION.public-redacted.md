[PUBLIC REDACTED COPY of EVALUATION.md, original sha256 ecbf6cf348ea394171abb2287554895997707d8775b09eafc2fa538d628b9bcd. Public redacted copy. The authentic original stays local; hash pins elsewhere refer to the original. Personal paths and session IDs are replaced; nothing else is changed.]

# Pregame journal: evaluation

Written 2026-11-15T09:32:27Z by `journal.py report`. Journal integrity: OK, every line checks out.

**What this is.** A local record of what the bot said before kickoff, what you decided and why, any ticket you report, and what happened. Original entries are never rewritten. It talks to no sportsbook and places nothing. One unit means one flat stake per bet. Later prices and estimated value are shown for information; they never choose a bet. Nothing here is a profit claim.

## Use it

Run these from the sprint folder. `J` stands for:

    /usr/bin/python3 -I -B nfl/slate/experiment/journal.py

- `J form` asks the questions one at a time.
- `J list chiefs` shows every priced bet matching a word, with its id. `J list --calls` shows the bot's calls.
- `J decide ID take --reason "..."`, or `pass`, or `alternative --alt OTHER_ID`. Must be before kickoff.
- `J hypothesis --text "..." --event chiefs` registers a football hypothesis before kickoff.
- `J ticket ID --book FanDuel --offered-price -115 --price -120 --stake 10 --placed-utc ACTUAL_PLACEMENT_TIME` records a ticket you placed. Replace ACTUAL_PLACEMENT_TIME with the date and time shown on your own ticket, including its timezone. The accepted price is `--price`.
- `J settlement TICKET_ID --gross-return AMOUNT --outcome OUTCOME --confirmed` records what the sportsbook returned, including any refunded stake. Find individual ticket IDs with `J grade`.
- `J control ID CONTROL_ID --rule "..." --book betmgm` pairs a bet with one matched control before kickoff.
- `J research --title "..." --status rejected --summary "..." --evidence PATH` adds a tested idea to the register.
- `J final chiefs --home 20 --away 27 --source "ESPN box score"` records a result. `J report` rewrites this page.

## Where it stands

| Item | Count |
| --- | --- |
| Games loaded | 12 |
| Priced bets kept as controls (every exact line in the capture) | 1756 |
| Bot calls recorded | 2 |
| Bets you added yourself | 0 |
| Hypotheses registered | 2 |
| Your decisions (pregame) | 0 |
| Your tickets | 0 |
| Games with a final | 0 |

Price capture times: 2026-11-15T06:55:06Z. Prices move; each row keeps the time of its own quote.

## Hypotheses

| Id | By | Registered (UTC) | Before kickoff | Hypothesis | sha256 of the text |
| --- | --- | --- | --- | --- | --- |
| H2c8f9912 | picker freeze log (Codex <codex-thread>), first frozen 2026-11-15T07:15:43Z; copied word for word, not entered by Matthew | 2026-11-15T07:48:56Z | yes | Pregame football review plus exact-line shopping may improve prospective one-unit net return over a frozen highest-probability in-band moneyline control per window. Track hit rate, pushes, price and one-unit return separately. Record every pass and retain the same controls even if the reviewer abstains. Grade reviewed picks, the provisional screen and controls as separate groups. Where independent probabilities exist, score their Brier loss against the same-contract market. One Sunday is insufficient to establish an edge. | 2c8f9912b4997adb... |
| H3fb769df | Independent public-evidence analyst (Codex <codex-thread>) | 2026-11-15T08:23:12Z | yes | If Aaron Rodgers starts and Jaylen Warren takes at least one offensive snap against Cincinnati on November 15, 2026, Warren will draw at least four receiving targets. Four to six targets in appearances 1–7 and two in appearance 8 inform this forecast. Three or fewer targets contradict it even if a single long catch wins the 22.5-yard over. If either condition fails, mark the forecast condition unmet. Record any early exit. Source: paper-desk-final-closeout/work/independent-public-evidence-20261115.md (pregame analyst note 08:21 UTC). | 3fb769dfe0b16bad... |

## Bot calls, as first recorded

| Game | Call | Price | Quote time (UTC) | Market's chance | Break-even | Est. value (info) | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Chiefs at Falcons | Kansas City Chiefs to win | -166 at DraftKings | 2026-11-15T06:53:59Z | 60.9% | 62.4% | -2.4% | not graded yet |
| Steelers at Bengals | Jaylen Warren over 22.5 receiving yards | -115 at BetMGM | 2026-11-15T06:54:41Z | 50.0% | 53.5% | n/a | not graded yet |

## Your decisions

None yet.

## Your tickets (only what you reported)

None reported.

## Scorecard (one unit per bet, at the recorded price)

| Group | Won-lost | Win rate | Units |
| --- | --- | --- | --- |
| Bot calls | 0-0, 2 not graded yet | n/a | +0.00 |
| Bets you took | none yet | n/a | +0.00 |
| Your alternatives | none yet | n/a | +0.00 |
| Bets you passed (what they did anyway) | none yet | n/a | +0.00 |
| Bot calls where you chose: take | none yet | n/a | +0.00 |
| Bot calls where you chose: pass | none yet | n/a | +0.00 |
| Bot calls where you chose: alternative | none yet | n/a | +0.00 |
| Bot calls where you chose: no decision | 0-0, 2 not graded yet | n/a | +0.00 |

## Benchmarks from the same slate

| Benchmark | Won-lost | Win rate | Units |
| --- | --- | --- | --- |
| Every moneyline favorite priced inside -200 to +200 | 0-0, 6 not graded yet | n/a | +0.00 |
| Every moneyline favorite at any price | 0-0, 12 not graded yet | n/a | +0.00 |
| Price-matched controls (same market, other games, break-even within 2.5 points) | 0-0, 765 not graded yet | n/a | +0.00 |
| The most likely in-band moneyline in each window (the picker's frozen control) | 0-0, 3 not graded yet | n/a | +0.00 |

Price-matched controls found for the bets acted on: 765. Each is graded once, at its own recorded price, one unit. `J grade` lists every one.

## Later prices (information only)

No later capture has been loaded. If the line moved, there is no later price for the old line, and none is borrowed.

## Matched controls registered before kickoff

| Bet | Recorded price | Result | Matched control (not a bet) | Control price | Control result | Registered |
| --- | --- | --- | --- | --- | --- | --- |
| Jaylen Warren over 22.5 receiving yards (Steelers at Bengals) | -115 at BetMGM | not graded yet | Jonathan Taylor over 21.5 receiving yards (Dolphins at Colts) | -115 at BetMGM | not graded yet | codex, 2026-11-15T07:48:56Z |

A control is a comparison picked by a stated rule before the games. It is graded at its own recorded price and is never a recommendation.
- Rule for Jaylen Warren over 22.5 receiving yards: Use the same original capture, same sportsbook, same exact American price, same market and direction, and a different game on the same Sunday. Require an RB position in nflverse Weeks 1–9 2026 and a threshold within five yards. Select the closest yardage; ties resolve by kickoff, then player name. Use no prior win rate, votes, forecasts or outcome to select. If none qualifies, record unmatched. This is a descriptive comparison and creates no additional bet.

## Research register (ideas tested; kept or retired)

- R97113bb2, REJECTED: Automatic WR/TE receiving-yard bump after two hot target-share games (recorded 2026-11-15T07:48:56Z by experiment owner (Claude nfl-lead), on Codex's evidence). Rule tested: raise a wide receiver's or tight end's five-game average receiving-yard forecast after two games whose target share each beat the preceding five-game average (half the proportional share gain, capped at +25%). REJECTED and retired before it changed any live rule. On the 2025 holdout it flagged 735 of 3,328 WR/TE games and made the forecast worse on them: mean absolute error 21.72 to 23.84 yards, +2.12 worse (week-clustered 95% interval 1.55 to 2.68). The direction was also worse in the separate 2026 sample (341 flagged games, 21.55 to 23.73). Independently reproduced in the Codex study; the experiment owner read the figures in its README and did not rerun the code. Evidence: `~/Documents/Codex/2026-11-15/nfl-receiving-role-test/outputs/ (Receiving_Role_Study.pdf; replication/README.md; protocol saved 2026-11-15 07:08:49 UTC, sha256 f80ad664f1ea93f1499cb8895b0329d3b52c588b23b5451abf775ecebcf5e2b4)`. Scope: Covers only the automatic two-hot-games target-share bump for wide receivers and tight ends. It is different from personnel-specific role changes, and running backs were not tested: the Jaylen Warren receiving call is untested by it. The study has no prop lines or prices, so it supports no win-rate, EV or profit claim and does not justify betting unders. No live rule was changed.

## Honest limits

- One Sunday is a tiny sample. A win rate from a handful of bets says almost nothing; the 95% range shows how wide the doubt is.
- The market's chance is the middle of the books' prices with the bookmaker's margin removed. It is the market's opinion, not proof of value.
- A bet is graded only when a final was entered with a source. First-half bets need the half-time score and player bets need the player's number; otherwise they stay "not graded yet".
- Prices come from a saved capture. Nothing here confirms the price a book would actually offer you in Louisiana at the moment you bet.
- Tickets are only what you report. This tool has no access to any account.
