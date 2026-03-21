# /cca-init — ClaudeCodeAdvancements Session Startup

Run the full session startup ritual. No user input needed — execute every step autonomously.
After init completes, if Matthew says nothing or runs /cca-auto, proceed to autonomous work immediately.

---

## Step 1 — Orient (parallel reads)

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
for f in $(find . -name "test_*.py" -type f | sort); do
  echo "=== $f ==="
  python3 "$f" 2>&1 | tail -1
done
```

---

## Step 2.5 — Check cross-chat inbox

Read the Kalshi cross-chat inbox for pending requests:

```bash
cat ~/.claude/cross-chat/POLYBOT_TO_CCA.md 2>/dev/null | grep -c "Status: PENDING"
```

If there are PENDING requests, include them in the briefing under "CROSS-CHAT INBOX:".
These should be prioritized during /cca-auto (1/3 session allocation for Kalshi work).
Also check if CCA_TO_POLYBOT.md has unread responses that need attention.

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
Stale processes (no chat ID) should also be flagged.
If crashed workers are detected, run `python3 crash_recovery.py run` to auto-recover orphaned scopes.

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
