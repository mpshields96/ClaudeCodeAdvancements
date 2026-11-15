# Advisor pass 2: trading rubric (about 07:00Z, 2026-11-15)

Scored against the current files. Checks were run at 06:58:53Z on a fresh scratch copy (adv3, `gate/` and `real/` removed) with `/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I`. The session window ended at 06:41:26Z. Score only; nothing was fixed.

Result: 18 PASS, 0 FAIL, 4 NOT YET (B2, B5, C4 and B6).

| Check | Score | One line of evidence |
|---|---|---|
| A1 | PASS | `replay --fresh --expect` exit 0, ledger MATCH 34 rows (sha256 `86ba83acc1ad29d8`), net +227.88, 17/17 plan check. The hash change is explained at `tvbot/STATUS.md:54-69`: fill rows are unchanged, and dropping the 2 new fields gives back `cc1b3657`. |
| A2 | PASS | 87 tests OK and adverse 28 of 28 (adv3, 06:58Z). |
| A3 | PASS | `codex/NOV15_USER_PATH.json`: `gate --config smaller_size.json` gives code 2, NOT RECORDED, and shows 33.19 / 33.2%. |
| A4 | PASS | Codex's Dia check rendered the page, with the synthetic label and "READ THIS FIRST ... not evidence of an edge" visible. Still missing: the 8x-cost figure (−69.03) is not on the page (`STATUS.md:88`). |
| A5 | PASS | `STATUS.md:13-117` matches the code. One stale paragraph remains: `STATUS.md:79-84` still describes the key-in-URL fetch that was removed at 06:40Z. The fix is at line 694, but line 17 says the earlier section wins. |
| B1 | PASS | `paper --fresh --config smaller_size.json` with no source: exit 2, NO REAL SOURCE. The gate is checked before any bar is read (`bot/run.py:1076-1082`). |
| B2 | NOT YET | The terms were checked and the open points are listed. But `codex/NOV15_SOURCE_VERDICT.md:3` says no source clears the hourly SPY workflow, so Matthew has no source to get yet. |
| B3 | PASS | Unchanged. The market-shaped template tests are in `tests/test_real_feed.py` (38 OK). |
| B4 | PASS | `refetch_conflicts` (`bot/run.py:1042-1106`) refuses before any bar is read. Mutation check: with the refusal disabled, 2 of 38 tests fail, and the backup check at `run.py:1111-1116` still exits 2. Limits are disclosed at `STATUS.md:45-52`: a bar missing mid-day goes undetected, and `--fresh` re-decides history. It has not been run on a real file. |
| B5 | NOT YET | The label code exists (`bot/page.py:561-563`). No real file has been run (`START_TONIGHT.md:101-124`, `NOV15_USER_PATH.json`). |
| B6 | NOT YET | Superseded by the NFL one-shot. That is scored separately in `advisor/NFL_REVIEW.md`. DraftKings prices stay `local_availability_verified: false` (`nfl/slate/BRIEF.md:20`). |
| C1 | PASS | Short version at `START_TONIGHT.md:9-22`. |
| C2 | PASS | 158 lines (was 183). Line 7 says the steps happen on the Mac, and the commands are exact (`:41`, `:60`, `:67`). |
| C3 | PASS | Only Matthew's steps remain: look at the page, the gate, and a source decision. What isn't built is listed at `START_TONIGHT.md:151-158`. |
| C4 | NOT YET | A draft (05:27Z) and the 05:37Z version were sent. `COORDINATOR_CHECKS.md:157` lists "Final START_TONIGHT sent to Matthew's phone" as NOT DONE. The 06:40Z version has not been sent. |
| C5 | PASS | Success notes in each step. Refusal help at `START_TONIGHT.md:126-138`, including "REAL FILE DOES NOT LINE UP" at `:87-92`. |
| D1 | PASS | The trading bot has no network imports. Note for NFL: the new `nfl/slate/tools/props_fetch_espn.py` uses urllib against keyless public ESPN endpoints. That is checked in the NFL review. |
| D2 | PASS | The fetch with the key in the URL is gone: `START_TONIGHT.md` has no apikey, curl or TD_KEY. The key scan of `nov14-sprint` is clean, and `real/` is gitignored (`tvbot/.gitignore:2`). |
| D3 | PASS | `START_TONIGHT.md:18-19` and `:147`. The export refusal is tested. |
| D4 | PASS | No event contracts anywhere. NFL picks now come from a new request (via Codex relay, which is not proof Matthew typed it). See `NFL_REVIEW.md`. |
| D5 | PASS | `git log --since=2026-11-15T04:41Z` was empty at 06:58Z. I saw no installs or schedules. Re-scored at 07:46Z under the new local-commit rule: still PASS. Three explicit-folder local commits, no push, no legacy files (`ACCEPTANCE_RUBRIC.md`, last section). |
| D6 | PASS | Writes are inside `nov14-sprint/`. Stray `.claude-compact-anchor.md` files (in `nov14-sprint/` and `nfl/slate/tools/`) come from legacy CTX-5 hooks. They are agent-made and harmless. |

## What's left, ranked

1. C4 (coordinator): send the 06:40Z `START_TONIGHT.md` to the phone.
2. B2 and B5 (Matthew or vendor): pick a source that clears the hourly SPY workflow. Until then there can be no real run.
3. Tidy-ups: `STATUS.md:79-84` (stale key paragraph) and the 8x-cost figure on `RESULT.html`.
