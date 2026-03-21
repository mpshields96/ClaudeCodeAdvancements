# 3-Chat Orchestration Gap Analysis
# Created: S107 (2026-03-21)
# Purpose: Identify what desktop needs to manage 3 chats WITHOUT constant manual checking

---

## The S105 Problem (Root Cause)

Desktop tried to manage 2 CLI chats while doing its own work. Result:
- Constant context-switching between "check inbox" / "send task" / "read bridge" / "do own work"
- Desktop spent more time orchestrating than producing
- Terminal chats died silently (API auth issue) — desktop didn't notice for a long time
- Token burn was excessive — orchestration overhead exceeded the value of parallelism

## What Exists Today

| Module | LOC | Purpose | Automated? |
|--------|-----|---------|------------|
| `cca_comm.py` | 417 | Task assignment, inbox, scope claims, status | Manual CLI calls |
| `chat_detector.py` | 259 | Duplicate session detection | Pre-launch only |
| `crash_recovery.py` | 256 | Orphaned scope cleanup | Manual trigger |
| `hivemind_session_validator.py` | 242 | Cycle validation + Phase 1 gates | Manual trigger |
| `hivemind_metrics.py` | 176 | Metrics persistence | Manual trigger |
| `overhead_timer.py` | 125 | Coordination overhead measurement | Manual trigger |
| `worker_task_tracker.py` | 205 | Incomplete task detection | Manual trigger |
| `launch_worker.sh` | 77 | Worker launch + auth fix | One-shot script |
| `launch_kalshi.sh` | 70 | Kalshi chat launch + auth fix | One-shot script |
| `queue_hook.py` | ? | Queue injection on UserPromptSubmit | Automated (hook) |

**Key insight**: Everything is manual-trigger except `queue_hook.py`. Desktop has to remember to run `python3 cca_comm.py inbox`, `status`, `context` etc. There's no background loop checking worker health.

## What's Missing (Gaps)

### Gap 1: No Worker Health Monitoring
**Problem**: Desktop doesn't know if a worker died until it manually checks.
**Need**: A lightweight background check that runs periodically (every 5-10 min) and alerts desktop if a worker is unresponsive or crashed.
**Approach**: Could use `crash_recovery.py` + process checking as a periodic hook or cron. Alert via cca_comm.py message to desktop.

### Gap 2: No Automatic Inbox Processing
**Problem**: Desktop must manually run `python3 cca_comm.py inbox` to see worker reports.
**Need**: The queue_hook.py already injects queue context on UserPromptSubmit — but this only fires when Matthew types something. For fully autonomous mode, desktop needs to check inbox as part of its work loop.
**Approach**: `/cca-auto-desktop` should include inbox checks between tasks. This is a skill/command change, not a code change.

### Gap 3: No Orchestration Budget Enforcement
**Problem**: Desktop spends unbounded time on orchestration, crowding out real work.
**Need**: A rule or mechanism that limits orchestration to 10-15% of desktop's context.
**Approach**: Track orchestration actions (inbox checks, task sends, bridge reads) and cap them. Could be as simple as "check inbox max once per task completion" rule in the /cca-auto-desktop skill.

### Gap 4: No Bridge File Sync Automation
**Problem**: CCA_TO_POLYBOT.md exists in both projects but they diverge. Manual copy is error-prone.
**Need**: Either a sync script or a single source of truth.
**Approach Options**:
  a) Symlink (polybot copy → CCA copy) — simplest but requires one-time setup
  b) Sync script that copies on cca-wrap — automated but adds another moving part
  c) Single location + both chats read from same path — cleanest but requires scope changes

### Gap 5: No Rate Limit Awareness
**Problem**: 3 Opus chats during peak hours could hit rate limits.
**Need**: Desktop should know current time relative to peak/off-peak and adjust behavior.
**Approach**: Simple time check in launch scripts or /cca-auto-desktop. During peak: don't launch worker, or use Sonnet model for worker.

### Gap 6: Desktop Coordination Loop Structure
**Problem**: /cca-auto-desktop has no structured coordination loop — it's "pick task, do task, repeat" with manual orchestration interspersed.
**Need**: A structured loop:
  1. Check inbox (30 seconds max)
  2. If worker done: assign next task, ack completion
  3. If worker stuck/dead: note it, don't try to fix mid-work
  4. Do own task (the bulk of time)
  5. After own task: commit, then goto 1

This is the CORE fix. The loop structure prevents context-switching mid-task.

---

## Priority Order for Fixes

1. **Gap 6: Loop structure** — Most impactful. Change /cca-auto-desktop to have structured coordination rounds between tasks. No code needed, just skill redesign.
2. **Gap 2: Inbox in loop** — Flows naturally from Gap 6. Inbox check is step 1 of each loop iteration.
3. **Gap 1: Worker health** — Add process check to inbox step. If worker process gone, log it and don't assign new tasks.
4. **Gap 4: Bridge sync** — Simplest: add copy step to /cca-wrap. One line: `cp CCA_TO_POLYBOT.md ../polymarket-bot/CCA_TO_POLYBOT.md`.
5. **Gap 5: Rate limits** — Time check in launch scripts. Low priority.
6. **Gap 3: Budget enforcement** — Track naturally from Gap 6 loop. If inbox check + task send takes >2 minutes, skip and move on.

---

## Implementation Plan

This is multi-session work (per Matthew S107 directive). Phases:

### Phase A: Redesign /cca-auto-desktop skill (THIS SESSION or next)
- Read current skill, identify where orchestration lives
- Add structured coordination rounds between tasks
- Add inbox check + task assignment as first step of each round

### Phase B: Add worker health check (next session)
- Extend `crash_recovery.py` or `chat_detector.py` to check if worker process is alive
- Integrate into coordination round step 1

### Phase C: Bridge sync automation (following session)
- Add copy step to /cca-wrap-desktop
- Or create symlink (simpler, one-time)

### Phase D: Dry run (Phase 4 of gameplan)
- Launch all 3, test the improved loop
- Measure: what % of desktop context was orchestration vs real work?

---

## Success Criteria

The 3-chat system is READY when:
1. Desktop spends < 15% of context on orchestration
2. Worker deaths are detected within 10 minutes
3. Bridge round-trip works end-to-end
4. All 3 chats wrap cleanly without orphaned processes
5. Matthew can leave the computer and come back to find everything still running correctly
