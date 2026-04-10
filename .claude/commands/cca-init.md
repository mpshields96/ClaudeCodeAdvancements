# /cca-init — ClaudeCodeAdvancements Session Startup

Run the session startup ritual. No user input needed — execute every step autonomously.
After init completes, if Matthew says nothing or runs /cca-auto, proceed to autonomous work immediately.

---

## Step 0 — Start session timer (MT-36)

Start the per-step timing instrumentation so real data accumulates. Extract the session
number from SESSION_STATE.md and start the timer before doing anything else:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
SESSION_NUM=$(python3 -c "
import re
with open('SESSION_STATE.md') as f: c = f.read()
m = re.search(r'Session (\d+)', c)
print(int(m.group(1))+1 if m else 145)
")
python3 session_timer.py start "$SESSION_NUM"
python3 session_timer.py mark init:startup init
```

This runs before slim or full mode. Each subsequent step marks its own timing boundary.
If session_timer fails, continue — timing is non-blocking.

---

## DEFAULT: Slim Mode (approved S99b — 2 trials, 74% faster, 0 quality issues)

Slim init is the DEFAULT startup path. It replaces the 10-minute full init with a ~1 minute
automated startup. Approved by init_benchmarker.py verdict after 2 independent trials:
- Trial 1 (S99a): 4 min to first commit, 7 commits, 96 tests, 0 quality issues
- Trial 2 (S99b): 3 min to first commit, 8 commits, 74 tests, 0 quality issues

**Backtrack path:** Full trial data in `.cca-init-benchmarks.jsonl`. Git history preserves
the old full-init behavior. Run `python3 init_benchmarker.py compare` to review any time.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 session_timer.py mark init:slim_init init
python3 slim_init.py
```

This runs: SESSION_STATE parse + 10-suite smoke test + priority_picker recommend.

If slim_init.py outputs READY:
1. **SKIP Steps 1 through 3** — slim_init already ran smoke tests, priority picker,
   todays_tasks scan, MT proposals, meta-learning, timeline, etc. Do NOT re-run them.
2. **SKIP Steps 2.5 through 2.95** — cross-chat comms, wrap trend, timeline, todays_tasks,
   MT proposals, session outcomes are ALL handled by slim_init's output. Do NOT duplicate.
3. **SKIP Step 3** (resurfacer) — informational only, not worth the context cost.
4. Go directly to Step 3.5 (reset pacer) → Step 4 (git status) → Step 4.5 (chat detector)
   → Step 4.9 (close timer) → Step 5 (briefing using slim_init output).
5. The cross-chat check (Step 2.5) is the ONE exception — run it only if the resume prompt
   mentions pending Kalshi requests. Otherwise skip it too.

**Fall through to full mode ONLY when:**
- slim_init.py reports BLOCKED (smoke test failed)
- Matthew explicitly requests full init (`/cca-init --full`)
- First session after major structural changes (new module layout, moved files)

---

## FALLBACK: Full Mode — Step 1 — Orient (parallel reads)

Read these three files in parallel:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/PROJECT_INDEX.md`
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md`
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE.md`

Extract and note:
- Current frontier being worked on
- Last session number and date
- Next planned work item
- Total test count expected

---

## Step 2 — Verify tests (cache-accelerated)

Check the test cache first. If fresh, skip the full run. If stale, run smoke tests.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 session_timer.py mark init:tests test
python3 init_cache.py summary
```

**If cache is FRESH:** Report cached counts and move on. No need to run tests.

**If cache is STALE or NO CACHE:** Run the smoke test (10 critical suites, ~15s):

```bash
python3 init_cache.py smoke
```

If smoke passes, proceed. If smoke fails, run the failing suite individually to diagnose.

**Full suite** (only if smoke fails or explicitly requested):

```bash
python3 parallel_test_runner.py --workers 8
```

This runs all 223 suites in ~26s (vs ~110s serial). Never use the serial for loop.

---

## Step 2.5 — Cross-chat comms check (Kalshi bot + Codex)

Run the unified action board for a structured comms summary:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 session_timer.py mark init:enrichment init
python3 cross_chat_board.py brief
```

Include in the briefing:
- **CROSS-CHAT INBOX:** Any URGENT items from the board get priority in /cca-auto
- **COMMS STATE:** Flag if CCA → Kalshi delivery is >2 days old (board shows this automatically)
- If URGENT items exist, plan to address them before other MT work this session

**Codex comms check (if leagues6-companion work was done last session):**

Use the canonical CCA-local bridge files. Do not silently switch to a separate
repo-local bridge path unless Matthew explicitly changes the protocol.

```bash
tail -60 /Users/matthewshields/Projects/ClaudeCodeAdvancements/CODEX_TO_CLAUDE.md 2>/dev/null
```

Include in briefing under **CODEX INBOX:**
- Any COMPLETE entries since last session (what Codex built while CCA was away)
- Any ACTION NEEDED items (Codex blocked or asking a question)
- Gate status from last Codex build — if FAILED, that's session priority #1

**After reading — write PRE-FLIGHT to CLAUDE_TO_CODEX.md (mandatory, do not skip):**

Append a PRE-FLIGHT entry to `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md`
acknowledging what Codex completed and stating what CCA plans to do this session. Format:

```
## [YYYY-MM-DD UTC] — S[N] PRE-FLIGHT — [one-line scope summary]

**Status:** ACTION NEEDED — read before your next leagues6 session
**Scope:** `leagues6-companion/` — [what CCA is touching]

**Acknowledging Codex deliveries (from CODEX_TO_CLAUDE.md):**
- [COMPLETE item 1]: [brief description]
- [COMPLETE item 2]: [brief description]
- (If no new COMPLETE entries since last PRE-FLIGHT: "No new Codex deliveries since last session")

**Test count baseline entering S[N]:**
- Tests: [N] passed (local verify), [0/N] failures
- Gate: validate.py → [PASSED/FAILED]
- Git: [last commit hash] ([session label])

**CCA S[N] planned scope:**
1. [task 1]
2. [task 2]
...

**Open questions for Codex (if any):**
- [question or "None"]
```

Skip the PRE-FLIGHT only if leagues6-companion work is explicitly NOT happening this session.

---

## Step 2.7 — Check wrap trend, pending tips, and hivemind status

Show session quality trend, pending advancement tips, and hivemind Phase 1 status:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 wrap_tracker.py trend 2>/dev/null
python3 tip_tracker.py pending 2>/dev/null | head -10
python3 -c "import hivemind_session_validator as hsv; print(hsv.format_for_init())" 2>/dev/null
```

If wrap trend shows "declining", flag it prominently in the briefing.
If there are pending tips, include the top 3 under "PENDING TIPS:" in the briefing.
Include hivemind status line in the briefing (shows Phase 1 gate progress).

---

## Step 2.8 — Session timeline (last 5 sessions)

Show a compact history of the last 5 sessions for quick context:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 session_timeline.py recent 5
```

Include the output in the briefing under "RECENT SESSIONS:". If no data, skip silently.

---

## Step 2.9 — TODAYS_TASKS.md check (PRIMARY) + priority picker (SECONDARY)

**TODAYS_TASKS.md is the authoritative daily task list (Matthew directive S178).**
Read it and show all remaining TODO items in the briefing. These are the ONLY tasks
to work on until ALL are marked [DONE]. Do NOT use priority_picker or MASTER_TASKS
to override TODAYS_TASKS.md — those are for AFTER all TODOs are complete.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
echo "=== TODAY'S TASKS (AUTHORITATIVE) ==="
grep -n "TODO\]" TODAYS_TASKS.md 2>/dev/null || echo "ALL DONE — fall through to priority picker"
echo ""
echo "=== PRIORITY PICKER (use only after all TODOs done) ==="
python3 priority_picker.py init-briefing --session $(python3 -c "
import re
with open('SESSION_STATE.md') as f: c = f.read()
m = re.search(r'Session (\d+)', c)
print(int(m.group(1))+1 if m else 125)
")
```

Include TODAYS_TASKS TODO items prominently in the briefing under "TODAY'S WORK:".
Priority picker output goes under "NEXT (after today's tasks):" — informational only.

---

## Step 2.92 — MT proposals from findings (MT-41)

Surface any new MT proposals synthesized from FINDINGS_LOG BUILD verdicts:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 mt_originator.py --briefing 2>/dev/null
```

If proposals are returned (score >= 30.0), include them in the briefing under
"MT PROPOSALS:". These represent community-validated BUILD findings that don't map
to any existing MT — potential new work items. If no proposals meet the threshold,
skip silently.

---

## Step 2.95 — Session outcome insights (Get Smarter)

Show learnings from past session outcomes so this session starts smarter:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 session_outcome_tracker.py backfill 2>/dev/null | tail -1
python3 session_outcome_tracker.py init-briefing --last 10
```

Include the output in the briefing under "SESSION INSIGHTS:". If no data or only
"No outcome data", skip silently. If recommendations exist, they should inform
task selection during /cca-auto.

---

## Step 2.97 — Surface recent corrections (mistake-learning)

Show recent error corrections so this session avoids repeating past mistakes:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 self-learning/resurfacer.py corrections --days 7 2>/dev/null
```

If corrections are returned, include them in the briefing under "RECENT CORRECTIONS:".
These are auto-captured error→fix patterns from past sessions. If no corrections, skip silently.

---

## Step 3 — Surface relevant findings (resurfacer)

After reading SESSION_STATE.md (Step 1), determine the current work context:
- What module/frontier is being worked on?
- What MT tasks are next?

Run the resurfacer to surface past findings relevant to the upcoming work:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
# Surface by next MT task (extract from SESSION_STATE next actions)
python3 self-learning/resurfacer.py FINDINGS_LOG.md --mt MT-<N> --limit 5 2>/dev/null
# Surface by module if working on a specific frontier
python3 self-learning/resurfacer.py FINDINGS_LOG.md --module <module-name> --limit 5 2>/dev/null
```

If findings are returned, include the top 3-5 in the briefing under a "RELEVANT FINDINGS:" section.
If no findings match or FINDINGS_LOG.md doesn't exist, skip silently.

---

## Step 3.5 — Reset session pacer

Reset the session pacer so it tracks this session's duration from now:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/context-monitor/session_pacer.py reset
```

This ensures /cca-auto's pacing decisions use accurate timing for this session.

---

## Step 4 — Check git status

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && git status --short && git log --oneline -5
```

Note any uncommitted changes or work-in-progress from a previous session.

---

## Step 4.5 — Check for duplicate chat sessions

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/chat_detector.py status
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/crash_recovery.py status
```

If duplicates are detected, include a WARNING line in the briefing.

### Register this session with the orchestrator

```bash
CCA_ROLE="${CCA_CHAT_ID:-desktop}"
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/session_orchestrator.py register "$CCA_ROLE"
```

This enables auto-launch detection for 3-chat mode. Deregistered automatically at wrap.
Stale processes (no chat ID) should also be flagged.
If crashed workers are detected, run `python3 crash_recovery.py run` to auto-recover orphaned scopes.

---

## Step 4.9 — Close init timer step (MT-36)

Close the last timing step so the init duration is recorded:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 session_timer.py done 2>/dev/null || true
```

The session timer remains active for /cca-auto to add code/test/doc steps.
It will be finalized by /cca-wrap's `finish` call.

---

## Step 5 — Display session briefing

Output a concise briefing in this exact format:

```
CCA SESSION [N+1] — [today's date]

Tests: [passed]/[total] [OK or FAILING]
Git: [clean / N uncommitted files]
Last session: [date] — [what was done]

NEXT UP: [specific next work item from SESSION_STATE]

RELEVANT FINDINGS: [top 3-5 resurfaced findings if any match, otherwise omit this section]

Ready to work. Run /cca-auto for autonomous mode, or describe what to build.
```

Where [N+1] is the next session number (one more than what SESSION_STATE shows).

---

## Rules

- Execute all steps autonomously — do not ask for confirmation
- If any test suite fails, report it prominently but continue startup
- Do not modify any files during init — read-only operation
- Keep the briefing under 15 lines
- If /cca-auto follows immediately, do NOT repeat the test run — init already verified tests pass
