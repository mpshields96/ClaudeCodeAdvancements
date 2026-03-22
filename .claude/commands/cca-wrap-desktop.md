# /cca-wrap-desktop — Desktop Coordinator Session Wrap-Up

Run the full session wrap ritual. You are the desktop coordinator — you own all shared docs.
Fully autonomous — no confirmation needed at any step.

---

## Step 1 — Run all tests + write cache

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
for f in $(find . -name "test_*.py" -type f | sort); do
  echo "=== $f ==="
  python3 "$f" 2>&1 | tail -1
done
```

All must pass before updating docs. Count total tests.

After all tests pass, write the cache for next session's fast init:

```bash
python3 init_cache.py write --session S98
```

---

## Step 2 — Check worker inbox + shutdown workers

```bash
python3 cca_comm.py inbox
```

Incorporate any worker completion summaries into the session record.

Then **shut down all active workers** so they don't linger:
```bash
python3 cca_comm.py shutdown cli1
python3 cca_comm.py shutdown cli2
```

This sends CRITICAL SHUTDOWN signals. Workers will run /cca-wrap-worker and exit.
Workers that are already stopped will simply have unread shutdown messages (harmless).

### Step 2.5 — Validate hivemind session (if workers were active)

If any worker was active this session, validate the hivemind cycle:

```bash
python3 -c "
import hivemind_session_validator as hsv
result = hsv.validate_session('cli1')
print(f'Hivemind validation: {result[\"verdict\"]}')
print(f'  Task assigned: {result[\"task_assigned\"]}')
print(f'  Task completed: {result[\"task_completed\"]}')
print(f'  Conflicts: {result[\"conflicts\"]}')
print(f'  Scope released: {result[\"scope_released\"]}')
hsv.record_session(SESSION_NUMBER, result)  # Replace SESSION_NUMBER
print(hsv.format_for_init())
"
```

Also measure queue throughput (Phase 2 metric — target 50+ msgs/session):

```bash
python3 -c "
import cca_comm
stats = cca_comm.get_queue_stats()
print(f'Queue throughput: {stats[\"total_messages\"]} messages')
print(f'  By sender: {stats[\"by_sender\"]}')
print(f'  By category: {stats[\"by_category\"]}')
met = 'MET' if stats['total_messages'] >= 50 else 'NOT MET'
print(f'  Phase 2 target (50+): {met}')
"
```

Record the verdict in SESSION_STATE.md under the session summary.

---

## Step 2.6 — Sync bridge file (if CCA_TO_POLYBOT.md was updated)

If `CCA_TO_POLYBOT.md` was modified this session, sync it to the polymarket-bot project
so the Kalshi chat gets fresh content at its next startup:

```bash
if git diff --name-only HEAD~5 | grep -q CCA_TO_POLYBOT; then
    cp CCA_TO_POLYBOT.md /Users/matthewshields/Projects/polymarket-bot/CCA_TO_POLYBOT.md
    echo "Bridge synced: CCA_TO_POLYBOT.md -> polymarket-bot/"
else
    echo "Bridge file unchanged — no sync needed"
fi
```

This is safe (CCA_TO_POLYBOT.md is a CCA-authored file, not a polybot-owned file).
Skip if the file wasn't touched.

---

## Step 2.7 — APF checkpoint (hit_rate_tracker)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 self-learning/hit_rate_tracker.py report 2>/dev/null || echo "hit_rate_tracker not available"
```

Record APF% in session summary. Target: 40%. Compare to last session.

---

## Step 2.8 — APF session snapshot (trend tracking)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 self-learning/apf_session_tracker.py snapshot S<SESSION_NUMBER> 2>/dev/null || echo "apf_session_tracker not available"
python3 self-learning/apf_session_tracker.py status 2>/dev/null || true
```

Replace `<SESSION_NUMBER>` with actual session number. Appends to `~/.cca-apf-snapshots.jsonl`.

---

## Step 3 — Self-assessment (be brutally honest)

```
SESSION WRAP — [session number] — [today's date]

WINS:
- [Concrete deliverables, new tests, features shipped]
- [Include worker contributions if any]

LOSSES:
- [Time wasted, bugs, circles, abandoned work]

GRADE: [A/B/C/D]
- A = shipped working code with tests, no regressions
- B = made progress, minor issues
- C = spent most time on overhead or debugging
- D = net negative — broke things or wasted the session

ONE THING next session must do differently:
[specific, actionable]
```

---

## Step 4 — Update SESSION_STATE.md

Update with:
- Session number incremented
- Date
- What was completed (bullets with file names)
- Worker contributions (if any)
- New test count
- What's next (specific task)

---

## Step 5 — Append to CHANGELOG.md

Append (NEVER overwrite):

```
## Session [N] — [YYYY-MM-DD]

**What changed:**
- [bullet per change, with file names]

**Why:**
- [motivation]

**Tests:** [N]/[N] passing

**Lessons:**
- [anything learned]

---
```

---

## Step 6 — Capture learnings

Append to LEARNINGS.md if applicable. Follow severity escalation rules (1->2->3).

---

## Step 7 — Self-learning journal

```bash
python3 self-learning/journal.py log session_outcome \
    --session [SESSION_NUMBER] --domain general \
    --outcome [success/partial/failure] \
    --notes "[summary]" \
    --learnings '[]'
```

Run reflection:
```bash
python3 self-learning/reflect.py --brief
```

### Step 7.5 — Persist wrap assessment + tips

Log the session grade and wins/losses for trend tracking:

```bash
python3 wrap_tracker.py log [SESSION_NUMBER] [GRADE] \
    --wins [WIN_BULLET_1] [WIN_BULLET_2] ... \
    --losses [LOSS_BULLET_1] ... \
    --tests [TOTAL_TEST_COUNT]
```

Extract any advancement tips from this session and persist them:

```bash
python3 tip_tracker.py add "[TIP_TEXT]" --source cca-desktop --session S[SESSION_NUMBER]
```

---

## Step 8 — Update PROJECT_INDEX.md

If new files were created, add them. If not, skip.

---

## Step 9 — Stage and display diff

```bash
git status && git diff --stat
```

Show what will be committed. Do NOT commit automatically.

---

## Step 9.5 — Check for stale worker sessions

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/chat_detector.py status
```

If any worker sessions are still running after desktop wrap, flag them:
- Send shutdown signal: `python3 cca_comm.py shutdown cli1` (or cli2)
- Note in resume prompt that stale workers may need manual cleanup

---

## Step 9.8 — Send session-end notification (MT-22)

Send a push notification so Matthew knows the autonomous session has finished:

```bash
python3 context-monitor/session_notifier.py wrap --auto --session S[SESSION_NUMBER] --grade [GRADE]
```

This reads task count and elapsed time from the session pacer state file and pushes
a notification to Matthew's iPhone via ntfy.sh. Requires `MOBILE_APPROVER_TOPIC`
env var to be set. Fails silently if not configured — never blocks wrap.

---

## Step 9.9 — Generate session handoff file (multi-chat sessions)

If this was a multi-chat session (2-chat or 3-chat), generate a standardized handoff file:

```bash
python3 handoff_generator.py generate \
    --session [SESSION_NUMBER] \
    --mode [solo|2chat|3chat] \
    --worker-task "[SUGGESTED_TASK_1]" \
    --worker-task "[SUGGESTED_TASK_2]" \
    --desktop-focus "[SUGGESTED_DESKTOP_FOCUS]" \
    --trial-run [TRIAL_RUN_NUMBER_OR_0]
```

This reads SESSION_STATE.md + git log to auto-generate `SESSION_HANDOFF_S{N}.md`.
Commit the handoff file — it serves as the next session's briefing.

For solo sessions, skip this step (the resume prompt in Step 10 is sufficient).

---

## Step 10 — Resume prompt

Output AND write to `SESSION_RESUME.md`:

```
RESUME PROMPT (copy-paste into next CCA session):
---
Run /cca-init. Last session was [N] on [date].
[What was completed.] [What's next.]
Tests: [N]/[N] passing. Git: [clean/uncommitted].
---
```

---

## Rules

- Fully autonomous — execute every step
- Tests MUST pass before updating docs
- CHANGELOG.md is append-only
- Self-assessment must be honest
- Resume prompt is the most important output — never skip it
