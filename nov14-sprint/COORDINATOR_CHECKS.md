# Coordinator's own checks (Nov 14 sprint)

Run by the coordinator session `local_50238c87` from a clean shell (`env -i PATH=/usr/bin:/bin`, `/usr/bin/python3` 3.9.6). Scratch ledgers live in the coordinator's scratchpad, so no lane file was written. These are checks the coordinator ran, not the lanes' own claims.

## NFL (checked 21:36Z)

Entry points: `nfl/backtest.py --selftest` and `nfl/paper_ledger.py` (`slate`, `generate`, `add`, `close`, `status`), with `--ledger-dir <scratch> --now 2026-11-14T21:40:00Z`.

| Case | Input | Result |
|---|---|---|
| Selftest | `backtest.py --selftest` | 25 checks, 0 failed |
| Slate | `slate` | 14 games for 2026 week 10. Labels the prices as archived, with the sportsbook quote time unknown. States team markets only. |
| Normal take | NE@DET spread home −2.5, −110 | ACCEPTED |
| Duplicate | the same take again | REJECTED DUPLICATE_PICK, exit 2 |
| Stale | quote 13.7 h old | REJECTED STALE_LINE |
| Future-dated | quote after decision time | REJECTED FUTURE_DATED_INPUT |
| Over cap | stake 2 | REJECTED STAKE_OVER_CAP |
| Past kickoff | WAS@NYG | REJECTED KICKOFF_PASSED |
| Wrong rule id | `HOME_DOG-v1.T7` via `add` | REJECTED RULE_NOT_MANUAL |
| Empty reason | `--reason ""` | REJECTED MISSING_REASON |
| Bad timestamp | `2026-11-14 21:30` | REJECTED BAD_TIMESTAMP |
| Unknown game | made-up id | REJECTED UNKNOWN_GAME |
| Out-of-range price | +200 and −180 | Accepted, recorded `price_in_band=false` with a visible note. It is not refused. |
| Relisted threshold | prop over 54.5, then 60.5, same player | Both accepted as separate picks |
| Same threshold again | prop over 54.5 a second time | REJECTED DUPLICATE_PICK |
| Prop without player | no `--selection` | REJECTED MISSING_SELECTION |
| Wrong-line close | 60.5 price on the 54.5 ticket | REJECTED CONTRACT_MISMATCH |
| Future close | close quote after decision time | REJECTED FUTURE_DATED_INPUT |
| Generate | `generate` | 11 takes, 41 passes, 4 refused (the game already kicked off) |
| Generate again | rerun | 0 added, 52 duplicates refused (idempotent) |

Limits seen:
- A second `close` on the same ticket is appended as another observation, not refused.
- Rule-generated takes come from the four frozen rules, and every one of them failed the held-out test. So the forward ledger tracks them on paper only; it is not a recommendation.
- Player props have no data source. They are hand-entered and their prices aren't verified.

## Paper Desk (checked 21:40Z to 21:52Z)

Entry point: double-click `Paper Desk.command`, which runs `/usr/bin/python3 desk/desk_server.py --open`. The coordinator built it, so these checks are not independent; Codex tests the buttons, restart and packaging. Test runs used `--port 8790 --ledger-dir <scratch>`.

| Case | Input | Result |
|---|---|---|
| Normal take | NE@DET spread home −2.5, −110, stake 1 | Ledger ACCEPTED |
| Normal pass | CAR@NO total over 48.5 | Ledger ACCEPTED, no stake sent |
| Prop | over 54.5 with player and stat | Ledger ACCEPTED |
| Flag-shaped text | source `--stake=9`, reason `--rule=X` | Stored as plain text. Each value is passed as one `--opt=value` argument, so text can't become a flag. |
| Duplicate, stale, future, over cap, past kickoff | the same cases as the NFL table | Ledger REJECTED with the same codes, and the page shows the refusal |
| Bad price, wrong side, blank reason, prop without player, made-up game id | form values | Refused at the desk ("NOT SENT"), and the ledger is not called |
| Missing session key | POST without `X-Desk-Token` | 403 |
| Wrong Host header | `Host: evil.example` | 403 |
| Path escape | `/../../etc/passwd`, and the same with `%2e%2e` | 404 both times. Files are served only from inside nov14-sprint, and only with known extensions. |
| Browser click-through | load the slate, fill in the form, Log decision | Take accepted, and the ledger id was shown on the page |
| Settle and Show my ledger | buttons | Both run and show the ledger's own output |
| Second launch | `existing_desk(8790)` while the desk runs; `existing_desk(8799)` with nothing there | True, then False. With `--open`, the first case opens the running desk instead of starting a second server. The logic was checked; the double-click wasn't clicked. |
| Source files | GET `/desk/desk_server.py` | 404. A `.py` file is never served. |

Limits seen:
- Until the NFL spread-sign repair lands, Settle grades a manual spread with the wrong sign. Codex found this: home −2.5 graded as a win when the home team won by 1.
- The TV buttons fill in from `desk/tv_actions.json` once the replay runner is released. Until then, the panel says so.

## TV bot retest of the 22:23Z code (checked 22:26:47Z to 22:26:49Z)

A fresh scratch copy of `tvbot/` was run from a clean shell. The coordinator did not write the bot, so this check is independent of the lane.

| Case | Result |
|---|---|
| Replay of the synthetic 60-minute bars | +$227.88 net (+$270.30 before costs, minus $25.42 spread and $17.00 commission). 8 round trips: 6 won, 2 lost. Worst fall $469.58. 50 units open at the end. Buy-and-hold on the same bars: +$72.99. |
| Rerun on the same ledger | 0 accepted, 630 refused as `duplicate_bar` |
| Adverse cases | 28 of 28 refused as expected |
| Cost sweep | x0 +$270.30, x1 +$227.88 (the replay figure), x2 +$185.47, x4 +$100.63, x8 −$69.03. It falls steadily as costs rise. |

These are synthetic bars, so this is a single sample and does not show an edge. None of the bars came from TradingView.

## Paper Desk: Trading and Practice tabs (checked 22:05Z to 22:20Z, test desk on port 8791)

| Case | Result |
|---|---|
| POST without `X-Desk-Token` | 403 |
| Trading decide with a bad choice, a blank reason or the wrong packet id | NOT RECORDED |
| Trading pass, normal | Recorded in `trading_decisions.jsonl` |
| The same decision again | Refused as a duplicate |
| GET `/api/practice` | 8 untouched decisions. The question carries no outcome fields: no fill, no P&L, no later bars. Bar 73 is left out because it was already reviewed. |
| Practice decide with a wrong id | Refused |
| Practice follow | Recorded in `practice_decisions.jsonl` |
| The same practice answer again | Refused |
| Reveal after answering | Bar 123. The bot's trip ran from bar 125 to 129 and lost $154.20, then the daily loss limit stopped it. The next question is bar 154. |
| In the browser | Chart hidden until you answer. Reveal, chart, tiles and form all show. Fixed during the check: the reveal said "bought 50" for a 48-unit buy, and the chart's last marker label was clipped at the right edge. |

## Review kit and price helper (checked 22:10Z to 22:30Z)

- `review/review_kit.py`:
  - `prepare` refuses a packet that is not synthetic, mentions TradingView data, carries an outcome field, or whose bars run past the decision;
  - `attach` refuses an answer that has the wrong packet id or verdict, or authority text that is not exact;
  - `show` flags an answer whose hash no longer matches.
  - `review/PKT-7069f9b05f2a/` holds both RECORDED answers. Claude challenges: the recorded fill time comes 7 seconds before the decision. Astra agrees: the rule was followed and the EMAs match to 6 decimals.
- `odds/price_helper.html`, checked by hand against the formulas:
  - −110 needs 52.4%; at 55% that is +$5.00 per $100 and about 1,387 bets to show it;
  - −170 needs 63.0% and +150 needs 40.0%;
  - with both sides at −170 and +150, the vig remover gives 3.0% overround.
  - Nothing leaves the page.
- Links on `START_HERE.html`: every local link resolves except `Video_Review/video-review.html` and `Paper_Desk_Field_Guide.pdf`, which Codex's release copy adds. Desk 8790 served every linked file with 200. A bare folder link returns 404 on the desk but opens as a file:// folder.

## Limits, updated 22:30Z

- The NFL lane reports the spread-sign fault fixed in `nfl/paper_ledger.py` at 22:00Z. At 22:30:28Z the coordinator ran the lane's own `tests/fixtures/selftest_paper_ledger.py` on a scratch copy: 52 checks, 0 failed, exit 0. That includes home −2.5 winning 21–20, which now settles as a LOSS (−1 unit), plus push, away favourite and away underdog cases, and 12 rule rows that settle as before. The test is the lane's own and no browser-to-settlement path was run, so Codex's retest is still pending. The NFL table above predates the fix.
- `existing_desk` second-launch logic was checked in code, not by double-clicking.
- Every result here is paper or synthetic. None shows a real edge or authorizes real money.

## TV bot concurrent-replay lock (checked 22:32:48Z to 22:32:51Z)

A scratch copy of `tvbot/`, from a clean shell:
- Two `replay --fresh` runs started together: both exited 0.
- A plain `replay` and a `replay --fresh` started together: both exited 0.
- All four runs ended at net +$227.88, with 17 orders and 17 fills.
- `decisions.jsonl` held 630 rows, every id unique.

The coordinator did not exercise the BUSY path (exit 4); the lane reports it at 22:15Z to 22:16Z. Codex's retest was requested at 22:33Z (`codex/RECEIPT_*_tv_lock_retest.txt`).

## TV lane close-out and Fable follow-up (coordinator, 22:37Z)

- **TV lane close-out:** tvbot/STATUS.md was updated at 22:34:28Z. The lane says these runs came after its last code edit at 22:27:10Z, which changed review status only:
  - rerun at 22:27:11Z;
  - sweep at 22:30:32Z (x1 +227.88, x2 +185.47);
  - adverse test at 22:32:52Z, 28 of 28;
  - a fresh-context run at 22:30:17Z: net +227.88, the ledger matched on 34 rows, and all 630 decisions were unique. Receipt: tvbot/receipts/fresh_reviewer_20261114T223428Z.md.

  These are the lane's figures; the coordinator didn't rerun them. Still open: Matthew's approve-or-pass gate, the result page, and an outside retest of the 22:23Z and 22:27Z changes.
- **Desk copy caveat (lane's claim, not compared):** review/PKT-7069f9b05f2a was copied before the lane rewrote the packet at 22:27:10Z. The lane says only review_status and published_utc differ.
- **Fable follow-up:** at 22:37:10Z one fresh Fable 5.2 subagent was started on codex/fable-followup/inputs/, which holds PKT-a4e48b82b984 and bars up to seq 123. Before the spawn, the coordinator confirmed:
  - the data is synthetic;
  - the bars end at the decision bar;
  - the packet holds no outcome and no other answer.

  The receipt is codex/fable-followup/MODEL_SELECTION_RECEIPT.txt. The reviewer was told to read only those two files; nothing technically enforced it.
- **Fable follow-up result (22:44Z):** the reviewer ran 22:37:20Z to 22:43:17Z. Every turn in its transcript is claude-fable-5-2, and the transcript shows exactly two Read calls, both on the inputs. Verdict: agree, with 8 of 8 arithmetic items matching. Its main concern is that earliest_fill_seq 124 is likely wrong and 125 is the first qualifying bar, the same fault type as 74 against 75 in the other packet. Raw answer: codex/fable-followup/FABLE_RAW_ANSWER.txt. Sent to Codex as msg 01a1dc3b (codex/RECEIPT_20261114T224400Z_fable_followup.txt); the message was queued, and delivery is not confirmed.

## Restart, 120-minute one-shot session (2026-11-15T05:17:16Z)
- Matthew's own words: HUMAN_DIRECT_20261115T044126Z_RESTART_120MIN.txt. The window is 04:41:26Z to 06:41:26Z.
- Codex: queued msg 01a1dd82 on thread 01a1dbe0. Asks: restart its chats, name the release and desk owner, exercise the user path at about 06:00Z. Receipts: codex/TO_CODEX_*_restart_120min.txt and RECEIPT_*.
- Lanes restarted by SendMessage, with deliverables due 05:50Z:
  - tvbot-lead (local_2bd925d2): real-data adapter that fails closed, earliest_fill fix, risk and leak fix, result page and gate, START_TONIGHT.md.
  - nfl-lead (local_1c8ba33b): real games from codex/real-intake.
  - reddit-research (local_462cb9ef): reddit/REAL_DATA_SOURCES.md, due 05:40Z.
- Advisor started: bot-advisor, local_abcc3d7a, a fresh Opus chat in the shared checkout that writes only advisor/. Pass 1 (rubric) is due 05:15Z; I send pass 2 at about 05:50Z.
- 05:27:35Z midpoint:
  - Advisor pass 1 is in advisor/ACCEPTANCE_RUBRIC.md: 22 checks, 2 FAIL (B4 repeat run loses bars; A5 STATUS stale), C4 not yet sent.
  - tvbot-lead got B4, A5, A1 and D2, due 06:05Z.
  - reddit-research got verbatim Twelve Data terms and header auth, due 06:00Z.
  - nfl-lead got the Louisiana DraftKings availability check from a primary page, due 06:00Z.
  - Codex got queued msg 01a1ddac: a user-path run at about 06:05Z, and NFL captures for the next window.
  - A draft of START_TONIGHT.md was sent to Matthew's phone with SendUserFile.
- 06:35:22Z close-out (window ends 06:41:26Z):
  - tvbot B4, A5, A1 and D2 landed at 05:33-05:36Z: paper --fresh, a REAL FILE DOES NOT LINE UP refusal, and unset TD_KEY.
  - The reddit addendum at 05:35Z has verbatim Twelve Data terms and documented header auth. START_TONIGHT still uses the URL key form; header auth is in REAL_DATA_SOURCES.md.
  - NFL: DraftKings is on the LGCB licensee list. Price rows are still local-unverified.
  - Codex at 06:34Z: release ZIP owner 01a1dc37; desk 01a1dbe0; mobile NFL intake 01a1d874. It is running the user path; verdict pending.
  - NOT DONE: advisor pass 2 (no time left after the fixes). No real file run. Final START_TONIGHT sent to Matthew's phone. Nothing committed. Lanes idle; no work after 06:41Z.

## 20261115T065651Z coordinator: NFL one-shot start
- 06:40Z START_TONIGHT (b) corrected per Codex source verdict before the hard stop.
- 06:42Z started nfl-slate-data (Sonnet), nfl-props (Sonnet), nfl-picker (Opus) on nfl/slate/BRIEF.md. bot-advisor asked for trading pass 2 + NFL review. Codex queued (RECEIPT_20261115T065651Z_nfl_oneshot.txt).

## 20261115T070716Z coordinator: picker handed to Codex
- 06:5xZ: nfl-slate-data, nfl-props and nfl-picker hit the 5-hour limit (reset 09:40Z, after the 08:59:53Z sprint end). nfl-lead also failed. No worker output after picker.py 06:51Z and the past-only test 06:54Z.
- 07:04Z Codex: 01a1de05-7d2e is the only picker writer; 01a1de05-7985 owns the inputs. Claude stops writing picker.py and the inputs.
- picker.py left as found (61,222 bytes). Past-only test: market wins (weight 1.00); top-2 ML by model rating is the only small-sample lead.
- Design notes + concerns to Codex: msg 01a1de08-5fe5 (RECEIPT_20261115T070716Z_picker_handoff.txt).
- Claude never read OAPI.docx and holds no key.
- NOT DONE by Claude: band, windows, line-shopping loader, hypothesis/challenge/ticket workflow, guard tests, picks page. All now Codex's. bot-advisor idle, ready for NFL_REVIEW.md once a picks path is posted.
- Coordinator has compacted 3+ times; stands down after this note. A successor needs: this section, the handoff file above, advisor/PASS2_TRADING.md.

## 20261115T071400Z coordinator: NFL roster corrected, single engine writer

- Observed at 07:12-07:13Z: picker.py was rewritten to 42,499 bytes (sha prefix bc6f909563c1fb52), split into selection_markets.py and selection_decisions.py. A grep found no odds_feed, urllib.request, http.client or socket import in the three files. `selection_markets.key_for` carries event, period, market, subject, side and line. That should fix the prop-ID collision on the old engine at lines 708 and 768. NOT ACCEPTED: no test yet.
- Ownership, per the 07:13Z Codex relay:
  - Codex 7d2e is the sole engine writer.
  - Codex 01a1dc37 owns Final_Decisions.json (present, 07:09Z, 2,495 bytes).
  - Codex 01a1de0b owns integration and UI.
  - The roster is in nfl/slate/ASSIGNMENTS_0712Z.md. My 07:12Z draft, which made nfl-picker the writer after a handback, is withdrawn. No Claude session edited picker.py.
- Briefs queued to the four workers at 07:14Z (message ids 879f85f7, f0d82615, b6b710f8, a797cc67). Due: nfl-picker repros 07:45Z, nfl-lead tests 07:40Z, slate-data 07:45Z, props dissent 08:00Z, red-team acceptance 08:40Z.
- ACK queued to Codex 01a1de0b (01a1de0e-0845) and 7d2e (01a1de0e-08dd). Receipts: codex/RECEIPT_20261115T071343Z_ack_*.txt.
- First work from the workers is NOT yet verified. Their briefs are queued behind turns already in progress.
