# /cca-init — ClaudeCodeAdvancements Session Startup

Run the full session startup ritual. No user input needed — execute every step autonomously.

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

## Step 2 — Run all test suites

Run every test suite listed in CLAUDE.md. Execute them in parallel where possible:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/memory-system/tests/test_memory.py 2>&1 | tail -1
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/memory-system/tests/test_mcp_server.py 2>&1 | tail -1
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/spec-system/tests/test_spec.py 2>&1 | tail -1
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/research/tests/test_reddit_scout.py 2>&1 | tail -1
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/agent-guard/tests/test_mobile_approver.py 2>&1 | tail -1
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/context-monitor/tests/test_meter.py 2>&1 | tail -1
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/context-monitor/tests/test_alert.py 2>&1 | tail -1
```

Also check for any additional test files that may have been added since SESSION_STATE was last updated:
```bash
find /Users/matthewshields/Projects/ClaudeCodeAdvancements -name "test_*.py" -type f | sort
```

Run any discovered test files not already in the list above.

---

## Step 3 — Check git status

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && git status && git log --oneline -5
```

Note any uncommitted changes or work-in-progress from a previous session.

---

## Step 4 — Display session briefing

Output a concise briefing in this exact format:

```
CCA SESSION [N+1] — [today's date]

Tests: [passed]/[total] [OK or FAILING]
Git: [clean / N uncommitted files]
Last session: [date] — [what was done]

NEXT UP: [specific next work item from SESSION_STATE]

Ready to work. Use /cca-review to evaluate a URL, or describe what to build.
```

Where [N+1] is the next session number (one more than what SESSION_STATE shows).

---

## Rules

- Execute all steps autonomously — do not ask for confirmation
- If any test suite fails, report it prominently but continue startup
- Do not modify any files during init — read-only operation
- Keep the briefing under 10 lines
