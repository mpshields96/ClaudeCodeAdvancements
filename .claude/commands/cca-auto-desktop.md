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
- Delegate to CLI workers via `cca_comm.py`
- Read bridge files from polymarket-bot (READ-ONLY)

---

## The Loop: COORD → WORK → COORD → WORK → ...

The session follows a strict alternating pattern. Never mix orchestration with task execution.

```
┌─────────────────────────────────────────────────────┐
│ STARTUP (once)                                       │
│   Step 0: Init pacer                                 │
│   Step 1: First coordination round                   │
│   Step 2: Pick first task                            │
│   Step 3: Run tests                                  │
├─────────────────────────────────────────────────────┤
│ LOOP (repeat until pacer says wrap)                  │
│   Step 4: WORK — Execute one task (TDD, commit)      │
│   Step 5: COORD ROUND — 2 min max, then back to work │
│   → If pacer says continue: pick next task, goto 4   │
│   → If pacer says wrap: goto WRAP                    │
├─────────────────────────────────────────────────────┤
│ WRAP                                                 │
│   Run /cca-wrap-desktop                              │
└─────────────────────────────────────────────────────┘
```

---

## Step 0 — Initialize session pacer

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 context-monitor/session_pacer.py reset --max-duration 60
```

---

## Step 0.5 — Auto-launch check (3-chat readiness)

Check if helper sessions need launching based on saved preference:

```bash
python3 session_orchestrator.py plan
```

This shows the current mode, target mode, and any launches needed. If launches
are READY (not blocked by peak hours), execute them:

```bash
python3 session_orchestrator.py launch --task "next worker task from SESSION_STATE"
```

To set the default target mode (persists across sessions):
```bash
python3 session_orchestrator.py set-mode 3chat  # or 2chat, solo
```

**Rules:**
- During peak hours, launches are blocked — solo mode only
- Don't launch if Matthew said "no workers" or "solo" this session
- Worker task should be the top independent task from priority_picker
- If Kalshi main is already running externally, the orchestrator detects it

---

## Step 1 — First Coordination Round

Run the coordination round (see below). On the first round, also check if a daily
intelligence scan is needed:

```bash
python3 -c "import json; d=json.load(open('reddit-intelligence/scan_registry.json')); print(d.get('claudecode',{}).get('last_scan','never'))"
```

If last scan is not today AND we're in off-peak hours: run `/cca-nuclear-daily`.
If peak hours: skip the scan, save tokens.

---

## Step 2 — Determine next task (priority-driven)

```bash
python3 priority_picker.py recommend
```

Use the top recommendation unless SESSION_STATE.md has a blocker or critical item.

**Task selection rules:**
- Work the TOP PICK from priority_picker unless SESSION_STATE has a blocker
- At least 50% of session on actual MT code work, not process/docs
- When assigning worker tasks: pick independent, testable work (test suites, modules)
- Desktop handles: doc updates, intelligence scans, bridge serving, process improvements

---

## Step 3 — Run tests (session start only)

```bash
for f in $(find . -name "test_*.py" -type f | sort); do
  python3 "$f" 2>&1 | tail -1
done
```

If any test fails: fix it before proceeding. After session start, tests run every
2nd coordination round (not every time).

---

## Step 4 — Execute the task (THE BULK OF YOUR TIME)

This is where 85%+ of your context should go. Do real work here.

Use inline TDD:
1. Write tests first
2. Run tests — confirm they fail (red)
3. Write implementation
4. Run tests — confirm they pass (green)
5. Commit with descriptive message

Architecture rules:
- One file = one job
- Stdlib-first (no external packages)
- Tests before promotion
- Stay within `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` ONLY

**DO NOT check inbox, worker status, or pacer during task execution.**
Finish the task, commit, THEN do the coordination round.

---

## Step 5 — Coordination Round (MAX 2 MINUTES)

This is the ONLY place orchestration happens. Run these checks in order.
If the round exceeds 2 minutes of your context, STOP the round and go back to work.

### 5a. Record task completion + check pacer + heartbeat
```bash
python3 context-monitor/session_pacer.py complete "Task Name" --commit <hash>
python3 context-monitor/session_pacer.py check --json
python3 session_orchestrator.py heartbeat desktop
```
- `"action": "continue"` → proceed with 5b-5f, then pick next task
- `"action": "wrap_soon"` → do NOT start a new task, run `/cca-wrap-desktop`
- `"action": "wrap_now"` → stop immediately, run `/cca-wrap-desktop`

### 5b. Check worker inbox (15 seconds max)
```bash
python3 cca_comm.py inbox
```
- If worker reported completion: note it, ack it, queue next task
- If worker reported a problem: note it, don't try to fix it now
- If no messages: move on
- **Front-load tasks**: If worker is idle, queue 2-3 tasks immediately:
```bash
python3 cca_comm.py task cli1 "primary: [next task]"
python3 cca_comm.py say cli1 "also: [follow-up task]"
```

### 5c. Worker health check (10 seconds max — skip if no worker launched)
```bash
python3 crash_recovery.py check 2>&1 | head -5
```
- If worker crashed: note in SESSION_STATE.md, don't relaunch mid-session
- If worker alive: good, move on

### 5d. Bridge check (10 seconds max — only in 3-chat mode)
Only if a Kalshi chat is running:
```bash
cat /Users/matthewshields/Projects/polymarket-bot/POLYBOT_TO_CCA.md 2>/dev/null | head -20
```
- If new content from Kalshi: note it, process at wrap or between tasks
- If no file or no new content: move on

### 5d2. Kalshi task management (15 seconds max — only in 3-chat mode)
Only if a Kalshi main chat is running AND CCA desktop is orchestrating it:
```bash
python3 cca_comm.py status    # Check cross-chat queue status
python3 cca_comm.py inbox km  # Check if Kalshi main reported completion
```
- If Kalshi main completed a task: ack it, queue next from the task catalog
- If Kalshi main is idle (no pending tasks): assign from KALSHI_TASK_CATALOG below
- If Kalshi main is still working: move on
- Task assignment: `python3 cca_comm.py task km "description of task"`

**Kalshi main productive task catalog** (assign in priority order):
1. Process unread bridge items from CCA_TO_POLYBOT.md
2. Run self-learning analysis on recent trades (`python3 self-learning/trade_reflector.py`)
3. Apply new research findings to sniper parameters (specific findings from CCA research)
4. Analyze sniper bucket performance by market type
5. Run Page-Hinkley on recent sniper bet outcomes
6. Execute calibration check on current model parameters

NOTE: polybot-auto must support task-driven work for this to function (out-of-scope for CCA — requires polybot changes). Until polybot-auto is updated, Kalshi main runs independently and this step is a no-op. Track progress in SESSION_STATE.md.

### 5e. Health check (every 2nd round only)
Run full test suite every other coordination round:
```bash
for f in $(find . -name "test_*.py" -type f | sort); do
  python3 "$f" 2>&1 | tail -1
done
```
If any test fails: fix it immediately before the next task.

### 5f. Pick next task
```bash
python3 priority_picker.py recommend
python3 context-monitor/session_pacer.py start "Next Task Name"
```
Then go back to Step 4.

---

## Rules

- FULLY AUTONOMOUS — no user confirmation needed
- Chain tasks continuously
- TDD is mandatory
- Commit after each component
- **Orchestration budget: MAX 15% of context** — if you're spending more, you're doing it wrong
- If blocked, log the blocker to SESSION_STATE.md and move on
- End every response with: `Advancement tip: [one actionable next step]`

## Failure Recovery

If a task fails mid-way (tests won't pass, unexpected error, can't resolve in ~5 min):
1. **Log it**: Add a BLOCKED note to SESSION_STATE.md with the task name and failure reason
2. **Skip it**: Move to the next priority task — do not stall the entire session on one failure
3. **Don't cascade**: Run `git checkout -- .` on uncommitted broken changes if needed to restore clean state
4. **Keep pacing**: The session pacer still ticks — a failed task shouldn't eat the whole time budget

## Matthew Departure Protocol

If Matthew says "leaving the house", "shutting down", or similar:
1. **IMMEDIATELY** turn off the Kalshi bot if running (see KALSHI_3CHAT_GAMEPLAN.md emergency procedures)
2. Then wrap the session cleanly
3. This overrides everything — even mid-task execution
