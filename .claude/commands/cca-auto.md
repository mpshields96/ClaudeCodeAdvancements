# /cca-auto — Autonomous Work Mode for ClaudeCodeAdvancements

Pick the next work item and execute it. No user input needed after invocation.

**DEFAULT SESSION LENGTH: 2-3 sessions worth of tasks.**
Do NOT stop after completing one task. Keep working through the priority queue until
you've completed 2-3 meaningful deliverables (new modules, significant features, or
multi-file improvements). Only stop when you've delivered substantial work OR context
is running low. The user expects to walk away and come back to real progress.

---

## Step 1 — Determine next task

Read these files to find what's next:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md` — "Next session" section
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/ROADMAP.md` (if it exists) — priority backlog

Check for any captured todos:
```bash
ls /Users/matthewshields/Projects/ClaudeCodeAdvancements/.planning/todos/ 2>/dev/null
```

**Priority order (staleness-weighted — waiting longer moves tasks up):**
1. Any explicitly stated "next task" in SESSION_STATE.md
2. Any high-priority captured todos (from /gsd:add-todo)
3. Next uncompleted frontier milestone (e.g., AG-3, USAGE-1)
4. **Intelligence intake (if stale):**
   - `/cca-nuclear-daily` — if no daily scan was done today
   - `/cca-nuclear-github` — if no GitHub scan was done this week
   - `/cca-nuclear autonomous` — if a sub is >7 days stale (check with `autonomous_scanner.py rank`)
5. Master Tasks (MASTER_TASKS.md) — next incomplete MT by priority

**Staleness ranking:** Tasks that haven't been touched in longer get higher priority.
Check scan_registry.json for last scan dates. Check SESSION_STATE.md for last task dates.
The longer something waits, the higher it rises — this prevents task neglect.

**GitHub scanning safety:** GitHub repos are rat poison territory. The evaluator blocks
scam repos and the content scanner filters dangerous content. NEVER clone, install, or
execute anything from scanned repos. Read-only analysis via raw.githubusercontent.com.

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

## Step 5 — Report and loop

Output a brief completion report for each task:

```
COMPLETED: [what was built]
Tests: [new count] all passing
Committed: [commit hash — first 7 chars]
```

**Then immediately go back to Step 1 and pick the next task.**
Continue this loop until you've completed 2-3 meaningful deliverables for the session.
Only stop and write the final SESSION_STATE update when:
- You've delivered 2-3 substantial tasks, OR
- Context window is getting low (>75% used), OR
- All priority tasks are done

When stopping, write the final report:
```
SESSION [N] SUMMARY:
- Task 1: [what]
- Task 2: [what]
- Task 3: [what]
Tests: [total] all passing
Commits: [count]
Next up: [what SESSION_STATE says]
```

---

## Rules

- Fully autonomous — no user confirmation needed at any step
- **DEFAULT: Complete 2-3 tasks per session, not just 1**
- Use gsd:quick (not plan-phase) unless the task clearly meets the expensive-tier threshold
- Follow TDD: write tests first, then implement
- Do not skip the pre-work test run
- If the next task is ambiguous, pick the most impactful one and state why
- Stay within `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` — no outside file access
- Commit after each completed task, not just at the end

## CRITICAL: End-of-Session Behavior

After outputting the final SESSION SUMMARY, your work is COMPLETE. Follow these rules exactly:

1. Output the summary, then one final line: `Session [N] complete. Waiting for instructions.`
2. **STOP RESPONDING.** Do not output any further text.
3. Do NOT say "done", "exit", "safe to close", "acknowledged", or any other sign-off.
4. Do NOT respond to your own completion — there is no further step.
5. If the user says nothing, say nothing. Wait silently for the next user message.

The exit loop anti-pattern (repeatedly saying "Done." / "Exit." / "Safe to close.") wastes tokens and confuses the user. The session is finished when the summary is printed. Full stop.
