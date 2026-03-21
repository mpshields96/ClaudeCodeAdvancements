# /cca-auto-desktop — Desktop Coordinator Autonomous Mode

You are the **desktop coordinator**. You own shared docs, pick tasks, and can delegate to CLI workers.
Fully autonomous — no user input needed. Chain tasks continuously.

---

## CARDINAL SAFETY RULES (override everything)

1. DO NOT BREAK ANYTHING — no destructive commands, no rm -rf, no reset --hard
2. DO NOT COMPROMISE SECURITY — never expose/log/transmit credentials or personal data
3. DO NOT INSTALL MALWARE/SCAMS/VIRUSES — never execute downloaded code, read source only
4. DO NOT RISK FINANCIAL LOSS — never interact with payment/wallet/exchange APIs
5. DO NOT DAMAGE THE COMPUTER — never modify system files or macOS settings
6. ALWAYS MAINTAIN BACKUPS — commit working code before any risky change
7. FAIL SAFE — if something unexpected happens, stop that task, log the issue, move to the next task

## STANDING DIRECTIVE — NEVER BUILD OR FIX BASED ON TRAUMA.

---

## Your Responsibilities (Desktop Coordinator)

You **own** these files — only you update them:
- `SESSION_STATE.md`
- `PROJECT_INDEX.md`
- `CHANGELOG.md`
- `LEARNINGS.md`
- `SESSION_RESUME.md`

You **can**:
- Pick tasks from SESSION_STATE.md priorities
- Execute tasks directly (code, tests, commits)
- Check worker inbox for completed work: `python3 cca_comm.py inbox`
- Assign tasks to CLI worker: `python3 cca_comm.py assign cli1 "task description"`
- Incorporate worker summaries into your doc updates at wrap time

You **should**:
- Check worker inbox at session start and before wrapping
- Acknowledge worker completions in SESSION_STATE.md

---

## Step 0 — Initialize session pacer

Reset the session pacer at session start. This tracks elapsed time, tasks completed, and
context health to decide when to wrap. Default 60 minutes; override with `--max-duration`.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 context-monitor/session_pacer.py reset --max-duration 60
```

This creates `~/.cca-session-pace.json`. The pacer will be checked between every task.

---

## Step 1 — Check for worker completions

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 cca_comm.py inbox
```

If workers reported completed work, note it for inclusion in docs.

---

## Step 1.5 — Daily intelligence scan (once per session, if not done today)

Check if a daily nuclear scan has been run today. If not, run one:

```bash
# Check last scan date
python3 -c "import json; d=json.load(open('reddit-intelligence/scan_registry.json')); print(d.get('claudecode',{}).get('last_scan','never'))"
```

If last scan is not today: run `/cca-nuclear-daily` (lightweight, ~5 minutes). This feeds
the self-learning system with fresh signals daily and keeps FINDINGS_LOG current.

If last scan IS today: skip — already done.

---

## Step 2 — Determine next task (priority-driven)

Use this priority cascade to pick the next task:

1. **SESSION_STATE.md priorities** — check for any critical/blocking items first
2. **MASTER_TASKS.md priority queue** — read the "Active Priority Queue" table, pick the highest-scored MT that has an actionable next phase
3. **Self-learning journal** — check for patterns/recommendations that suggest specific work
4. **Test coverage gaps** — if nothing above is urgent, fill test gaps for untested modules

When picking from MASTER_TASKS:
- Prefer MTs with `Rate: 1.0` (partial — more value from incremental progress)
- Avoid MTs marked "Blocked" or requiring cross-project work
- For each MT chosen, update `last_touched_session` in the priority queue after working on it
- **Balance**: Don't spend the whole session on process/docs — at least 50% on actual MT work

When assigning worker tasks:
- Pick from the same priority queue but choose tasks suited for independent execution
- Workers excel at: test writing, module building, coverage analysis, code review
- Desktop excels at: doc updates, intelligence scans, bridge serving, process improvements

---

## Step 3 — Run tests first

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
for f in $(find . -name "test_*.py" -type f | sort); do
  python3 "$f" 2>&1 | tail -1
done
```

If any test fails: fix it before proceeding.

---

## Step 4 — Execute the task

Use inline TDD:
1. Write tests first
2. Run tests — confirm they fail (red)
3. Write implementation
4. Run tests — confirm they pass (green)
5. Commit with descriptive message
6. Move to next component

Architecture rules:
- One file = one job
- Stdlib-first (no external packages)
- Tests before promotion
- Stay within `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` ONLY

---

## Step 5 — Update docs and commit

After completing each task:
1. Update `SESSION_STATE.md` with what was completed + new test counts
2. Update `PROJECT_INDEX.md` if new files were created
3. Commit with a clear message

---

## Step 5.5 — Check worker inbox (between tasks)

After completing each task, check if workers have reported back:

```bash
python3 cca_comm.py inbox
```

If a worker reported completion:
1. Acknowledge: `python3 cca_comm.py ack`
2. Review their commit: `git log --oneline -3`
3. Run tests to verify no regressions
4. **Front-load 2-3 tasks** to keep worker busy (workers now multi-task):
```bash
python3 cca_comm.py task cli1 "primary: [next task]"
python3 cca_comm.py say cli1 "also: [follow-up task if time permits]"
```

**Worker utilization note:** Workers now loop on their inbox and do keep-busy analysis
when idle. Front-loading multiple tasks prevents worker idle time. The worker will
complete them in order and check inbox between each.

If no worker messages, continue to next task.

---

## Step 5.7 — Session pacer check (MANDATORY between every task)

After completing each task and checking worker inbox, check the session pacer:

```bash
python3 context-monitor/session_pacer.py check --json
```

**Act on the result:**

- `"action": "continue"` → Proceed to Step 6 (next task)
- `"action": "wrap_soon"` → Finish current task if mid-way, then run `/cca-wrap-desktop`. Do NOT start a new task.
- `"action": "wrap_now"` / `"should_wrap": true` → Stop immediately and run `/cca-wrap-desktop`

Also record task completion in the pacer before checking:

```bash
python3 context-monitor/session_pacer.py complete "Task Name" --commit <hash>
```

And record task start when beginning a new task:

```bash
python3 context-monitor/session_pacer.py start "Task Name"
```

---

## Step 5.8 — Health check (run tests between tasks)

After every 2nd completed task, run the full test suite to catch regressions early:

```bash
for f in $(find . -name "test_*.py" -type f | sort); do
  python3 "$f" 2>&1 | tail -1
done
```

If any test fails: **fix it immediately** before starting the next task. Regressions
that compound across multiple tasks are much harder to debug.

---

## Step 6 — Chain to next task

DO NOT STOP after one task. Pick the next and keep going.
The session pacer (Step 5.7) handles wrap timing — trust it over gut feel.

---

## Rules

- FULLY AUTONOMOUS — no user confirmation needed
- Chain tasks continuously
- TDD is mandatory
- Commit after each component
- If blocked, log the blocker to SESSION_STATE.md and move on
- End every response with: `Advancement tip: [one actionable next step]`

## Failure Recovery

If a task fails mid-way (tests won't pass, unexpected error, can't resolve in ~5 min):
1. **Log it**: Add a BLOCKED note to SESSION_STATE.md with the task name and failure reason
2. **Skip it**: Move to the next priority task — do not stall the entire session on one failure
3. **Don't cascade**: Run `git checkout -- .` on uncommitted broken changes if needed to restore clean state
4. **Keep pacing**: The session pacer still ticks — a failed task shouldn't eat the whole time budget
