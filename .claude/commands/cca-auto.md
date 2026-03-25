# /cca-auto — Autonomous Work Mode for ClaudeCodeAdvancements

Pick the next work item and execute it. No user input needed after invocation.

**NEVER STOP WORKING BETWEEN TASKS. This is the #1 rule of /cca-auto.**
After completing a task: commit, then IMMEDIATELY start the next task. Do not output
a summary and wait. Do not ask what to do next. Do not pause for feedback. The user
may be asleep, away, or watching — it does not matter. You are autonomous. If the user
sends a message, address it briefly and KEEP WORKING. Never let a user message become
a reason to pause the work loop.

**DEFAULT SESSION LENGTH: 2-3 tasks worth of work (up to 2 hours autonomous).**
Keep working through the priority queue until you've completed 2-3 meaningful
deliverables. Only stop when session pacer says WRAP SOON/WRAP NOW or context is low.

**MARATHON MODE (2-hour autonomous):** When running for extended periods:
- Re-read SESSION_STATE.md after EVERY completed task (context compaction may lose it)
- Commit after EVERY task (never accumulate >1 task of uncommitted work)
- If a task takes >15 tool calls without progress, SKIP it and log why in SESSION_STATE
- If you hit 3 consecutive errors on the same operation, move to the next task
- Do NOT spawn subagents unless absolutely necessary — they burn 100K+ tokens each

## Session Pacer — Objective Pacing (use between EVERY task)

Run the session pacer after completing each task to decide whether to continue:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/context-monitor/session_pacer.py check
```

**Decisions:**
- `CONTINUE` → Pick next task and keep going
- `WRAP SOON` → Finish current task, then run /cca-wrap
- `WRAP NOW` → Stop immediately, run /cca-wrap

**Task tracking (run at start/end of each task):**
```bash
python3 .../session_pacer.py start "Task name"
python3 .../session_pacer.py complete "Task name" --commit abc1234
```

**At session start, reset the pacer:**
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/context-monitor/session_pacer.py reset
```

The pacer combines context health (from meter.py), elapsed time, task count,
and compaction events into one objective decision. Trust it over vibes.

---

## Step 1 — Determine next task

**TODAYS_TASKS.md FIRST (Matthew directive S178 — overrides S124 priority picker):**

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
echo "=== TODAY'S REMAINING TASKS ==="
grep "TODO\]" TODAYS_TASKS.md 2>/dev/null
```

If TODAYS_TASKS.md has any TODO items: work on the FIRST one. Do not skip it.
Do not use priority_picker to override it. Matthew's daily task list is authoritative.

Kalshi bot tasks in TODAYS_TASKS.md: deliver via CCA_TO_POLYBOT.md, don't implement
in polybot directly (unless the task explicitly says to build in polybot).

**ONLY IF ALL TODOs ARE DONE** — fall through to priority picker:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/priority_picker.py init-briefing --session $(python3 -c "
import re
with open('/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md') as f: c = f.read()
m = re.search(r'Session (\d+)', c)
print(int(m.group(1))+1 if m else 125)
")
```

Then read:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md` — "Next session" section

Check for any captured todos:
```bash
ls /Users/matthewshields/Projects/ClaudeCodeAdvancements/.planning/todos/ 2>/dev/null
```

**Cross-chat bridge**: Check POLYBOT_TO_CCA.md for Kalshi requests.

**Priority order (after TODAYS_TASKS.md is complete):**
1. Priority picker's top recommendation (if not blocked)
2. Any explicitly stated "next task" in SESSION_STATE.md (if picker agrees)
3. Cross-chat requests from POLYBOT_TO_CCA.md
4. Any high-priority captured todos (from /gsd:add-todo)
5. Next uncompleted frontier milestone (e.g., AG-3, USAGE-1)
5. Master Tasks (MASTER_TASKS.md) — next incomplete MT by priority
6. **Intelligence intake (ONLY if scan budget allows):**
   - `/cca-nuclear-daily` — if no daily scan was done today
   - `/cca-nuclear-github` — if no GitHub scan was done this week
   - `/cca-nuclear autonomous` — if a sub is >7 days stale (check with `autonomous_scanner.py rank`)

**SCAN LIMIT (non-negotiable):** Check `strategy.json` → `session.max_consecutive_scan_sessions` (default: 3).
After 3 consecutive scan-heavy sessions, the next 2 sessions MUST be build-focused (writing code,
implementing features, running tests). Count scan sessions by checking CHANGELOG.md — if the last
3 entries are primarily scanning/reviewing, skip all scanning tasks and pick build work instead.
Scanning is research. Building is shipping. We need both, but building takes priority.

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

## Step 3.5 — Cross-chat comms check (every 2nd task)

After every 2nd completed task (tasks 2, 4, 6...), check for Kalshi bot messages:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
echo "=== INCOMING (Kalshi -> CCA) ==="
tail -30 ~/.claude/cross-chat/POLYBOT_TO_CCA.md 2>/dev/null || echo "No incoming"
echo ""
echo "=== LAST CCA DELIVERY ==="
grep "^## \[" ~/.claude/cross-chat/CCA_TO_POLYBOT.md 2>/dev/null | tail -1 || echo "No deliveries"
```

**Actions based on check:**
- New PENDING request? Add to task queue with high priority (Kalshi work gets 1/3 allocation)
- Last CCA delivery >48 hours old? Write a proactive status update NOW:
  - What CCA has been building recently
  - Any findings relevant to Kalshi bot (self-learning improvements, new patterns, etc.)
  - Questions for the Kalshi bot team
- Unanswered question from either side? Surface it and address this task cycle

**Writing updates to CCA_TO_POLYBOT.md:**
```bash
cat >> ~/.claude/cross-chat/CCA_TO_POLYBOT.md << 'DELIVERY'

## [YYYY-MM-DD HH:MM UTC] — UPDATE [N] — [TOPIC]
[Summary of what CCA has done since last update]
[Any relevant findings, tools built, or research done]
[Questions or requests for Kalshi bot team]
Status: DELIVERED
DELIVERY
```

This step is FAST (just reads files). Do not skip it — stale comms means CCA and Kalshi drift apart.

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

**Then IMMEDIATELY go back to Step 1 and pick the next task. DO NOT OUTPUT A SUMMARY
AND WAIT. DO NOT ASK THE USER WHAT TO DO. Just start the next task.**

RE-RUN Step 1 every loop iteration — re-check TODAYS_TASKS.md for remaining TODOs.
Only fall through to priority_picker after ALL TODOs are done.

**ANTI-PATTERN TO AVOID:** Completing a task, writing "Here's what I did..." and then
stopping. This wastes the user's time and context window. The correct pattern is:
commit → re-check TODAYS_TASKS.md → start next task. All in one continuous flow.

Continue this loop until you've completed 2-3 meaningful deliverables for the session.
Only stop and write the final SESSION_STATE update when:
- Session pacer says WRAP SOON or WRAP NOW, OR
- Context window is getting low (>60% used), OR
- All priority tasks are done

**CRITICAL: RESERVE CONTEXT FOR WRAP.** The session pacer handles this objectively.
Run `python3 .../session_pacer.py check` between tasks. When it says WRAP SOON or WRAP NOW,
obey it — it reads the actual context health state from meter.py.
The /cca-wrap ritual needs ~15-20% of context budget (journal, reflection, Skillbook,
Sentinel evolve, strategy validation). The pacer accounts for this.
This applies to /cca-nuclear sessions too — stop scanning and run /cca-nuclear-wrap.

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
