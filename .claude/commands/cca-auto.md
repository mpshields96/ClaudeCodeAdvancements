# /cca-auto — Autonomous Work Mode for ClaudeCodeAdvancements

Pick the next work item and execute it. No user input needed after invocation.

---

## Step 1 — Determine next task

Read these files to find what's next:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md` — "Next session" section
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/ROADMAP.md` (if it exists) — priority backlog

Check for any captured todos:
```bash
ls /Users/matthewshields/Projects/ClaudeCodeAdvancements/.planning/todos/ 2>/dev/null
```

**Priority order:**
1. Any explicitly stated "next task" in SESSION_STATE.md
2. Any high-priority captured todos (from /gsd:add-todo)
3. Next uncompleted frontier milestone (e.g., AG-3, USAGE-1)

State what you're going to work on before starting.

---

## Step 2 — Run tests first

Run the full test suite to confirm everything is green before making changes:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && python3 -m pytest --tb=short -q 2>/dev/null || for f in $(find . -name "test_*.py" -type f); do python3 "$f" 2>&1 | tail -1; done
```

If tests fail, fix them before proceeding with new work.

---

## Step 3 — Execute via gsd:quick

Use `/gsd:quick` to execute the selected task. This provides:
- Atomic commits
- State tracking
- TDD workflow (tests first, then implementation)

Follow the project's architecture rules:
- One file = one job
- Stdlib-first (no external packages without justification)
- Tests before promotion from research/
- Hook-based delivery where applicable

---

## Step 4 — Update session state

After completing the task:

1. Update `SESSION_STATE.md` with:
   - What was completed
   - New test counts
   - What's next

2. Update `PROJECT_INDEX.md` if new files were created

3. Commit everything with a clear message

---

## Step 5 — Report

Output a brief completion report:

```
COMPLETED: [what was built]
Tests: [new count] all passing
Committed: [commit hash — first 7 chars]
Next up: [what SESSION_STATE now says is next]
```

---

## Rules

- Fully autonomous — no user confirmation needed at any step
- Use gsd:quick (not plan-phase) unless the task clearly meets the expensive-tier threshold
- Follow TDD: write tests first, then implement
- Do not skip the pre-work test run
- If the next task is ambiguous, pick the most impactful one and state why
- Stay within `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` — no outside file access
