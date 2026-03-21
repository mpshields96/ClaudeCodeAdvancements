# Slim Init Trial — Instructions for New Chat

## What This Is

We're testing a faster startup process. Normal init takes ~10 minutes (read 4 large files, run all 109 test suites, count tests). This slim init should take ~3 minutes and produce equal or better code output.

Two separate chats will run this same process. After both complete, Matthew will compare results against normal sessions to decide if slim init becomes the default.

---

## Trial A — Paste This Into a Fresh Chat

```
SLIM INIT TRIAL A — S99a

You are running a timed trial of a faster startup process. Follow these steps EXACTLY.

STEP 1 — ORIENT (30 seconds)
Read only this one file:
/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md

Note the session number (S98), what was done, and what's next.
Do NOT read CLAUDE.md, PROJECT_INDEX.md, or MASTER_TASKS.md — you already have CLAUDE.md loaded by the harness, and the other two are replaced by CLI tools below.

STEP 2 — SMOKE TEST (15 seconds)
Run this one command:
python3 init_cache.py smoke

If all 10 pass, move on. If any fail, run the failing suite individually.

STEP 3 — PICK TASK (5 seconds)
Run:
python3 priority_picker.py recommend

Work the TOP PICK. Do not read MASTER_TASKS.md.

STEP 4 — LAUNCH WORKER
Run:
bash launch_worker.sh

Queue 2-3 test-writing tasks via:
python3 cca_comm.py assign cli1 "task description"

STEP 5 — BUILD
Start coding immediately. TDD. Commit after each component.
Target: maximum code output in 45 minutes.
Skip: reddit scanning, paper scanning, daily intelligence scans, research agent spawns.
Those belong in dedicated research sessions, not production sessions.

STEP 6 — TRACK METRICS
Note these when you wrap:
- Time from chat start to first commit: ___
- Total commits: ___
- Total new tests: ___
- Total LOC shipped: ___
- Any quality issues found: ___

STEP 7 — WRAP
Run /cca-wrap-desktop when done. Write test cache:
python3 init_cache.py write --session S99a

This is Session S99a. Last session was S98 on 2026-03-22.
S98 shipped: priority_picker.py, init_cache.py, test_validate.py, test_doc_drift_checker.py, INSTALL_CLAUDE_CONTROL.md. 4373 tests across 109 suites. Hivemind 7th PASS.

Priority picker says MT-22 (autonomous loop) is top priority.
Stagnating: MT-18 (academic writing, never started), MT-13 (iOS, 49 sessions untouched).
Unblockable: MT-1 (install Claude Control), MT-5 (Claude Pro bridge).
```

---

## Trial B — Paste This Into a Separate Fresh Chat

```
SLIM INIT TRIAL B — S99b

You are running a timed trial of a faster startup process. Follow these steps EXACTLY.

STEP 1 — ORIENT (30 seconds)
Read only this one file:
/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md

Note the session number (S98), what was done, and what's next.
Do NOT read CLAUDE.md, PROJECT_INDEX.md, or MASTER_TASKS.md.

STEP 2 — SMOKE TEST (15 seconds)
Run this one command:
python3 init_cache.py smoke

If all 10 pass, move on. If any fail, run the failing suite individually.

STEP 3 — PICK TASK (5 seconds)
Run:
python3 priority_picker.py recommend

Work the TOP PICK or second-ranked task (avoid duplicating Trial A's work).

STEP 4 — LAUNCH WORKER
Run:
bash launch_worker.sh

Queue 2-3 tasks that are different from Trial A's worker tasks.

STEP 5 — BUILD
Start coding immediately. TDD. Commit after each component.
Target: maximum code output in 45 minutes.
Skip: reddit scanning, paper scanning, daily intelligence scans, research agent spawns.

STEP 6 — TRACK METRICS
Note these when you wrap:
- Time from chat start to first commit: ___
- Total commits: ___
- Total new tests: ___
- Total LOC shipped: ___
- Any quality issues found: ___

STEP 7 — WRAP
Run /cca-wrap-desktop when done. Write test cache:
python3 init_cache.py write --session S99b

This is Session S99b. Last session was S98 on 2026-03-22.
S98 shipped: priority_picker.py, init_cache.py, test_validate.py, test_doc_drift_checker.py, INSTALL_CLAUDE_CONTROL.md. 4373 tests across 109 suites. Hivemind 7th PASS.

Priority picker says MT-22 (autonomous loop) is top priority.
Pick a DIFFERENT task than Trial A to avoid git conflicts.
Stagnating: MT-18 (academic writing), MT-13 (iOS).
Unblockable: MT-1 (Claude Control install), MT-5 (Claude Pro bridge).
```

---

## After Both Trials Complete

Compare these metrics across Trial A, Trial B, and a typical S95-S98 session:

| Metric | Trial A | Trial B | Typical (S95-S98 avg) |
|--------|---------|---------|----------------------|
| Init time (to first commit) | | | ~12-15 min |
| Total commits | | | 5-8 |
| New tests | | | 100-200 |
| LOC shipped | | | 300-600 |
| Quality issues | | | 0 |
| Session duration | | | 45-60 min total |

If both trials match or beat the typical session with no quality issues, slim init becomes the permanent default.

---

## Important Notes

- Do NOT run both trials simultaneously — they'll have git conflicts
- Run Trial A first, let it wrap, then run Trial B
- Both should use /cca-desktop style (desktop + worker)
- The worker launch counts as part of init time, not production time
- "Quality issues" means: broken tests at wrap, missed context that caused wrong code, safety hook violations
