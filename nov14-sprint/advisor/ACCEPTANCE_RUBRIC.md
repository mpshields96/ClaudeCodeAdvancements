# Acceptance rubric: Matthew's 120-minute one-shot bot session

Advisor: bot-advisor (Claude, independent reviewer, local_abcc3d7a). I review; I don't build.
Window: 2026-11-15 04:41:26Z to 06:41:26Z. Pass 1 written at about 05:30Z (due 05:15Z, late).
Authority: `nov14-sprint/HUMAN_DIRECT_20261115T044126Z_RESTART_120MIN.txt`, plus Matthew's correction
quoted at `nfl/STATUS.md:8`: "I don't care about fake paper data. Use real teams and real events and
in fact, let's prepare to obtain real data."

Scores: **PASS**, **PASS-WITH-EXCEPTIONS** (usable tonight, exception named), **FAIL**, or
**NOT YET** (due later in the window). Evidence comes from my own runs on scratch copies of `tvbot/`
taken at about 05:18Z and 05:24Z, using `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I`.

---

## The rubric

Each of Matthew's asks maps to criteria a reviewer can check by running a command or reading a line.

### A. "A one-shot best attempt at the trading bot"

| ID | Pass check |
|---|---|
| A1 | One documented command runs the bot end to end and reproduces the expected ledger (`run.py replay --fresh --expect` exits 0, fill timing checks out, ledger MATCH). |
| A2 | It fails safe: the unit tests pass and the adverse suite passes in full. |
| A3 | The approve-or-pass gate works for Matthew and refuses an agent shell. |
| A4 | The result page reads plainly. Synthetic figures are marked. It shows risk per trade, buy-and-hold and costs. |
| A5 | The lane's STATUS file matches the code, so Matthew or a successor isn't misled. |

### B. "Real data, not fake paper data; prepare to obtain real data"

| ID | Pass check |
|---|---|
| B1 | The bot reads real bars only from a file Matthew fetched. It fails closed with no source. It refuses TradingView exports, unclosed bars, out-of-order rows and an agent as approver. |
| B2 | One named source. Cost and terms are checked against the vendor's own pages. Open terms points are listed, with the person who decides them. |
| B3 | The real-file path has been exercised with a market-shaped file (trading hours, weekends, the clock change) through the shipped template and the engine. |
| B4 | The documented repeat run (fetch again Monday, run again) gives correct results, or refuses loudly. |
| B5 | A real run is labelled honestly: "REAL BARS, PAPER ONLY", buy-and-hold beside it, the variant count, and "not evidence of an edge". |
| B6 | NFL: real teams, real events and real prices with their source named. Nothing to bet, and Louisiana availability is stated. |

### C. "What's left to do tonight to start it", readable on mobile

| ID | Pass check |
|---|---|
| C1 | One list exists with a short version first. |
| C2 | Every step gives the exact command and says where it happens (the Mac's Terminal, or a phone or browser). |
| C3 | Only Matthew's own steps remain (signup, key, gate, sign-off). Nothing is left half-built by an agent. |
| C4 | The list actually reaches his phone: the coordinator's chat reply carries the short version, and the file is sent with SendUserFile or an artifact. A path on the Mac doesn't count. |
| C5 | Each step says what success looks like and what to do when the bot refuses. |

### D. Hard limits respected

| ID | Pass check |
|---|---|
| D1 | Paper only: no broker code and no network calls in the bot or the NFL code. |
| D2 | No key in any file. Matthew handles the key in Terminal, and `real/` stays out of git. |
| D3 | TradingView values never enter the model or the ledger. The Pine script is for eyes only, and an export is refused. |
| D4 | No Louisiana event contracts. NFL has nothing to bet. |
| D5 | No installs, schedules or pushes since 04:41Z. A local commit is allowed when it holds only the committer's own verified files, named by explicit paths. It fails D5 if it uses `git add -A`, `git add .` or `commit -a`, or commits another owner's file or a legacy dirty file (for example `pokemon-agent/*.sav` or `self-learning/journal.jsonl`). The commit part of this rule changed at about 07:40Z, by coordinator relay. |
| D6 | File scope: writes only in agent-made folders. |

---

## Current score (about 05:30Z)

| ID | Score | Evidence |
|---|---|---|
| A1 | PASS-WITH-EXCEPTIONS | Scratch run at 05:18Z: `replay --fresh --expect` exit 0, 17 orders, 17 fills, timing yes, net +227.88, MATCH on 34 rows. **Exception:** the expected ledger was regenerated at 05:06:22Z, three minutes after the `bot/engine.py` edit at 05:03:10Z. Its sha256 changed from `cc1b365708da1aba` (`tvbot/receipts/fresh_reviewer_20261114T223428Z.md:19`) to `86ba83acc1ad29d8`. Net, rows and fills are unchanged, so this proves determinism, not that the edit kept the old behaviour. The lead must say which fields changed and why. |
| A2 | PASS | 84 tests OK on the 05:24Z copy. Adverse suite 28 of 28 (05:18Z). |
| A3 | PASS | `gate` from an agent shell: exit 2, NOT RECORDED. The screen shows one stopped trade at about 79.98 (80% of the 100 daily limit) and offers the smaller size. |
| A4 | PASS-WITH-EXCEPTIONS | `tvbot/RESULT.html` (05:19:52Z): every figure is labelled TEST ONLY; buy-and-hold +72.99; costs itemised; "not evidence of an edge". **Exception:** the cost-stress figure (−69.03 at 8x costs, in `SPRINT.md`) isn't on the page. |
| A5 | **FAIL** | `tvbot/STATUS.md` was last written 22:35Z Nov 14. Lines 333–343 still say the gate and the result page are NOT DONE; both exist and work. |
| B1 | PASS | `paper` with no source: exit 2 and the one message. The gate is checked before any bar is read (`bot/run.py:1041-1048`). Refusals are covered in `tests/test_real_feed.py`. |
| B2 | PASS-WITH-EXCEPTIONS | Twelve Data Basic, $0 (`reddit/REAL_DATA_SOURCES.md:151`). Three terms points are still open (evaluation-only trial, one-person "internal use", storage). No ruling yet; `tvbot/START_TONIGHT.md:96-100` says plainly the call is Matthew's. Nobody has run the request. |
| B3 | PASS | `tests/test_real_feed.py:249-284`: weekday hourly bars, nights and weekends missing, the Nov 1 clock change, run through the template and the engine; timing and plan checks clean. |
| B4 | **FAIL** | The repeat path in `START_TONIGHT.md:76-79` ("fetch the file again and run step 5 again") loses or ignores bars without refusing. Scratch check with made-up prices, script at `advisor/repeat_run_check.py <scratch copy of tvbot> <slide>`: (1) a longer file with the same start accepts 35 of 35 new bars (correct); (2) the oldest 7 rows dropped, which happens whenever the vendor's `outputsize=5000` cap slides the window: **28 of 35 new bars accepted, 7 lost**, with every old bar rejected as `conflicting_duplicate` and the feed still reported accepted; (3) the same row count, a full-cap re-fetch: **0 new bars accepted**, feed accepted. Cause: `real_feed` numbers `seq` from 1 on every conversion, and the engine keys bar identity on `seq` (`bot/engine.py:403-411`), so after a slide, old numbers point at different bars. Tonight's first run, on an empty state folder, isn't affected. |
| B5 | PASS-WITH-EXCEPTIONS | `bot/page.py:561-563`: REAL label and "One run on one file is still not evidence of an edge". Buy-and-hold uses the same tile (`page.py:224-229`), and `paper` prints the variant count. **Exception:** no real file has been run yet (`START_TONIGHT.md:181-182` says so), and the cost stress is not shown. |
| B6 | PASS-WITH-EXCEPTIONS | `nfl/STATUS.md`: 14 real week-10 games, 1 final (WAS 24 at NYG 21), 78 real DraftKings price rows via ESPN, 44 priced rule rows, 0 scored. `local_availability_verified: false` (line 42). Codex's retest is pending. |
| C1 | PASS | `tvbot/START_TONIGHT.md` (05:18:50Z), short version at lines 6–19. |
| C2 | PASS-WITH-EXCEPTIONS | Line 4: "The steps themselves happen on the Mac". Every command is exact and copyable. **Exception:** it is 183 lines long. On a phone, the coordinator's reply should carry the short version below. The signup step (b1) could be done on the phone but isn't marked. |
| C3 | PASS | Lines 18–19. The only steps left are Matthew's: look at the page, the gate, and optionally the signup, key, fetch and sign-off. |
| C4 | **NOT YET** | Nothing has been sent to the phone yet. This is the coordinator's job before 06:41Z. |
| C5 | PASS | "What you will see" at lines 66–71; refusals at lines 153–163. |
| D1 | PASS | No network imports in `tvbot/bot` or the NFL code (scan at 05:19Z). No broker code. |
| D2 | PASS-WITH-EXCEPTIONS | The key scan of `nov14-sprint` is clean, `tvbot/.gitignore` ignores `real/`, and the key is read with `read -s`. **Advisory:** `START_TONIGHT.md:121` puts the key in the URL (`apikey=${TD_KEY}`), so it shows in the process list while curl runs and in the vendor's request logs. Consider header auth if Twelve Data accepts it (I haven't verified that) and adding `unset TD_KEY` after step 4. |
| D3 | PASS | `START_TONIGHT.md:15-16` and line 172. The export refusal is covered in `tests/test_real_feed.py:239-242`. |
| D4 | PASS-WITH-EXCEPTIONS | NFL: "nothing to bet or start". Availability is flagged as unverified, not claimed. |
| D5 | PASS | `git log --since=2026-11-15T04:41Z` is empty. I saw no schedules or installs. |
| D6 | PASS-WITH-EXCEPTIONS | All writes I saw are inside `nov14-sprint/`. A stray `nov14-sprint/.claude-compact-anchor.md` (05:18Z) came from a legacy CTX-5 hook in my own session (7500889f). It is agent-made and harmless. I won't touch it because it's outside `advisor/`; the coordinator may remove it. |

**Overall at 05:30Z:** usable tonight in paper mode with synthetic bars, and ready for real bars once
Matthew does his steps. One real defect remains on the documented repeat path (B4). The STATUS file is
stale (A5), and delivery to the phone is still to come (C4).

---

## Top gaps, ranked (owner, then the smallest fix)

1. **C4, the coordinator: put the list on Matthew's phone.** Paste the short version below into the
   reply and send `tvbot/START_TONIGHT.md` with SendUserFile (or as an artifact).
2. **B4, tvbot-lead: the repeat run silently loses bars.** The smallest safe fix for tonight:
   (a) `START_TONIGHT.md:76-79` says to add `--fresh` to `paper` every time a new file is fetched;
   (b) `run.py paper` exits 2 with a plain message when any `conflicting_duplicate` appears, rather than
   reporting the feed accepted; (c) a test built from my scratch script (cases 2 and 3). The durable fix
   is a `seq` derived from the bar's own open time, which also gives a real check for a missing
   intraday bar, which today goes undetected.
3. **A5, tvbot-lead: rewrite `tvbot/STATUS.md`** to match the code at 05:3xZ: gate done, page done,
   real path done, the B4 status, entry points as in `START_TONIGHT.md`.
4. **A1, tvbot-lead: one paragraph on the ledger change.** The hash went from `cc1b3657` to `86ba83ac`
   after the 05:03Z engine edit. Say which fields changed (for example, a new label or a fill-plan field)
   and confirm that no prices, quantities or costs moved.
5. **B2, Codex at about 06:00Z, or leave it explicitly to Matthew:** the three Twelve Data terms points.
   `START_TONIGHT.md` already says the call is his, so this does not block.
6. **A4 and B5, optional:** show the cost-stress figure (net at 8x costs) on the page for both the
   synthetic and real sections.
7. **D2, advisory:** header auth if supported, and `unset TD_KEY`.
8. **B6, nfl-lead and Codex:** the retest, and keep "availability unverified" visible.

Closed since earlier reviews: the packet's earliest fill now reads `earliest_fill_seq: 75`
(`tvbot/packets/PKT-291c26718608.json`), and `cooldown_bars: 3` is in the packet (line 70).
I didn't find a MISSED_FILL label in `bot/*.py`; the lead should confirm whether it was dropped or renamed.

---

## Draft short version for the phone (the coordinator may paste it)

> Tonight, on the Mac's Terminal (not a Claude chat). All of it is paper; no order is possible.
> 1. `cd ~/Projects/ClaudeCodeAdvancements`, then `/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py replay --fresh` (test bars; should end at +227.88).
> 2. `open nov14-sprint/tvbot/RESULT.html` and read "Read this first" and Risk.
> 3. Gate: `... run.py gate --config nov14-sprint/tvbot/config/smaller_size.json`, then type `APPROVE PAPER ONLY` or `PASS`.
> 4. Optional real bars: sign up for Twelve Data Basic yourself (stop if it asks for a card), then follow section (b) of `START_TONIGHT.md`. Three terms points are open; the call is yours.
> 5. `... run.py paper --config nov14-sprint/tvbot/config/smaller_size.json`. With no source it prints one message and stops.
> NFL: nothing to bet tonight.

## Pass 2 (about 05:50Z)

I'll re-score `tvbot/START_TONIGHT.md`, `tvbot/STATUS.md`, `tvbot/RESULT.html`,
`reddit/REAL_DATA_SOURCES.md` and `nfl/STATUS.md` against this rubric with file:line evidence,
and re-run the B4 scratch check against any fix. (Done: scored in `advisor/PASS2_TRADING.md`.)

## D5 re-score under the new commit rule (07:46Z)

**PASS.** I checked `git log --since=2026-11-15T04:41Z` at 07:45:18Z and found three local commits:

| Commit | UTC | Paths |
|---|---|---|
| `946094e` nfl-slate-data | 07:37:49Z | 109 files, all under `nov14-sprint/nfl/slate/`: `inputs/`, `slate_20261115.json`, `DATA_NOTES.md` and two `tools/` scripts |
| `501353b` CCA coordinator | 07:43:01Z | 7 relay and receipt files under `nov14-sprint/codex/` and `nov14-sprint/` |
| `eb5b532` CCA coordinator | 07:44:09Z | 2 relay and receipt files under `nov14-sprint/codex/` |

- None of the three commits contains a legacy dirty file. `pokemon-agent/pokemon_crystal.sav`, `self-learning/journal.jsonl`, `session_timings.jsonl` and `.queue_hook_last_check` are still uncommitted.
- Nothing was pushed: `origin/main` is still at `10ccd01` (2026-04-12), and `main` is 182 commits ahead.
- Each commit's subject names its owner, and its paths sit inside that owner's folder.
- I can't see from git whether `-A` or explicit paths were used. However, none of the commits swept up a dirty file from outside its folder, which is what `-A` would have done here.
