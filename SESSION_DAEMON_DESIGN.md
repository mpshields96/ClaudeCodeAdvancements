# Session Daemon — Design Document
# MT-29: Tmux-Based Auto-Spawn Session Manager
# Created: S110 (2026-03-21)
# Status: DESIGN PHASE — multi-chat build, NOT a single-session rush job
#
# Matthew directive (S110): "This is NOT something to build within 1 chat.
# That's a very careful and delicate tool to develop over several chats so
# that we properly and cleanly execute it the right way."

---

## 1. Problem Statement

Today, CCA sessions are entirely manual:
- Matthew must open Terminal, type `claude`, run `/cca-init`, run `/cca-auto`
- Worker chats must be launched manually via `bash launch_worker.sh`
- Kalshi chats must be launched manually via `bash launch_kalshi.sh`
- If a session crashes, nobody notices until manual check
- If a session wraps, nobody starts the next one

The session daemon solves the #1 force multiplier gap: **automatic session lifecycle management**.

---

## 2. What the Daemon Does (and Does NOT Do)

### Does:
- Watches for session endings (via tmux pane exit or wrap markers)
- Auto-spawns replacement sessions when a session wraps
- Detects crashed sessions and cleans up (scope release, stale queue messages)
- Respects peak hours (fewer chats during peak, more during off-peak)
- Logs all actions to a structured audit trail
- Provides a CLI for manual control (start, stop, status, kill)

### Does NOT:
- Make betting decisions (financial operations stay in Kalshi bot)
- Modify any code files (it's a supervisor, not a worker)
- Override safety rules (cardinal rules still apply)
- Run without explicit human activation (no auto-start on boot)
- Spawn more than the configured max chats (hard limit)

---

## 3. Architecture

```
┌─────────────────────────────────────────────────┐
│                 session_daemon.py                │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  Watcher  │  │ Spawner  │  │ Health Check │ │
│  │          │  │          │  │              │ │
│  │ Monitors │  │ Launches │  │ Detects dead │ │
│  │ tmux     │  │ new      │  │ sessions via │ │
│  │ panes    │  │ sessions │  │ chat_detector│ │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘ │
│       │              │               │          │
│       ▼              ▼               ▼          │
│  ┌──────────────────────────────────────────┐  │
│  │            Session Registry              │  │
│  │  (which chats should be running,         │  │
│  │   their configs, current PIDs)           │  │
│  └──────────────────────────────────────────┘  │
│                      │                          │
│                      ▼                          │
│  ┌──────────────────────────────────────────┐  │
│  │            Audit Logger                  │  │
│  │  (all spawn/kill/crash events logged)    │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ tmux:cca │  │tmux:kal1 │  │tmux:kal2 │
   │ desktop  │  │ main bot │  │ research │
   └──────────┘  └──────────┘  └──────────┘
```

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| Session Registry | `session_registry.py` | Tracks intended vs actual sessions |
| Daemon Loop | `session_daemon.py` | Main event loop (check, spawn, cleanup) |
| Tmux Manager | `tmux_manager.py` | Tmux session/pane creation and monitoring |
| Audit Logger | Built into daemon | Structured JSONL log of all actions |

### Existing Infrastructure (reused, NOT rewritten)

| Module | Role in Daemon |
|--------|---------------|
| `chat_detector.py` | Process health detection |
| `crash_recovery.py` | Orphaned scope cleanup |
| `peak_hours.py` | Rate limit awareness |
| `cca_comm.py` | Queue message sending |
| `session_pacer.py` | Wrap timing decisions |

---

## 4. Session Registry

The registry defines what sessions SHOULD be running. It's a JSON config that the daemon reads.

```json
{
  "version": 1,
  "max_total_chats": 3,
  "sessions": [
    {
      "id": "cca-desktop",
      "type": "cca",
      "role": "desktop",
      "command": "claude /cca-init",
      "auto_restart": true,
      "restart_delay_seconds": 30,
      "env": {"CCA_CHAT_ID": "desktop"},
      "priority": 1
    },
    {
      "id": "kalshi-main",
      "type": "kalshi",
      "role": "main",
      "command": "claude /kalshi-main",
      "auto_restart": true,
      "restart_delay_seconds": 60,
      "env": {},
      "cwd": "/Users/matthewshields/Projects/polymarket-bot",
      "priority": 2
    },
    {
      "id": "kalshi-research",
      "type": "kalshi",
      "role": "research",
      "command": "claude /kalshi-research",
      "auto_restart": true,
      "restart_delay_seconds": 60,
      "env": {},
      "cwd": "/Users/matthewshields/Projects/polymarket-bot",
      "priority": 3
    }
  ],
  "peak_hours": {
    "max_chats": 2,
    "deprioritize": ["kalshi-research"]
  }
}
```

### Registry Rules

1. `max_total_chats` is a hard ceiling — daemon NEVER exceeds this
2. During peak hours, `peak_hours.max_chats` takes precedence
3. Sessions launch in priority order (lower = higher priority)
4. `auto_restart: false` = run once, don't respawn after wrap
5. `restart_delay_seconds` = cool-down between death and respawn (prevents rapid cycling)

---

## 5. Tmux Integration

The daemon manages a single tmux session called `cca-workspace` with named windows.

```bash
# Daemon creates this structure:
tmux new-session -d -s cca-workspace -n daemon    # Daemon runs here
tmux new-window -t cca-workspace -n cca-desktop   # CCA Desktop
tmux new-window -t cca-workspace -n kalshi-main   # Kalshi Main
tmux new-window -t cca-workspace -n kalshi-research  # Kalshi Research
```

### Tmux Manager Responsibilities

1. **Create**: Create named windows and start claude processes
2. **Monitor**: Check if pane process is alive (`tmux list-panes -t window -F '#{pane_pid}'`)
3. **Kill**: Send graceful shutdown signal, then kill if needed
4. **Capture**: Read recent pane output for health diagnostics

### Health Detection via Tmux

```bash
# Check if a pane's process is still running:
tmux list-panes -t cca-workspace:cca-desktop -F '#{pane_pid} #{pane_dead}'
# pane_dead = 1 means the process exited

# Capture last N lines for diagnostics:
tmux capture-pane -t cca-workspace:cca-desktop -p -S -20
# Look for "Session wrapped" or error messages
```

### Why Tmux (not Terminal.app tabs)

| Terminal.app | Tmux |
|-------------|------|
| No programmatic process monitoring | `list-panes` with PID + dead status |
| AppleScript fragile (-1719 errors) | Scriptable via tmux CLI |
| Can't read pane output | `capture-pane` reads last N lines |
| Can't survive SSH disconnect | Persists across terminal closures |
| Matthew already uses it (dev-start) | Familiar pattern |

---

## 6. Daemon Loop

The daemon runs a simple poll loop (not event-driven):

```python
while running:
    # 1. Health check — are expected sessions alive?
    for session in registry.sessions:
        if session.auto_restart and not tmux.is_alive(session.id):
            log_event("session_died", session.id)
            crash_recovery.release_orphaned_scopes(session.role)
            if should_respawn(session):
                spawn_with_delay(session)

    # 2. Peak hours adjustment
    if peak_hours.is_peak():
        enforce_peak_limits()  # Pause low-priority sessions

    # 3. Sleep until next check
    time.sleep(check_interval_seconds)  # Default: 60s
```

### Key Design Decisions

1. **Poll, not event-driven**: Simpler, more debuggable, and tmux doesn't offer clean event hooks. 60-second polling is cheap.

2. **Graceful degradation**: If the daemon itself crashes, sessions keep running (they're independent tmux windows). The daemon is a supervisor, not a dependency.

3. **No auto-start on boot**: The daemon must be explicitly started by Matthew. This prevents uncontrolled spawning after a reboot.

4. **Restart delay**: After a session dies, wait `restart_delay_seconds` before respawning. This prevents rapid crash-restart loops from burning API credits.

5. **Max restart count**: Per-session limit (default: 5 per hour). After hitting the limit, mark session as "failed" and alert.

---

## 7. Safety Guarantees

### Cardinal Rules (daemon-specific)

1. **Never spawn more than `max_total_chats`** — Hard limit. No override.
2. **Never auto-start without human activation** — `python3 session_daemon.py start` is the only entry point.
3. **Never kill a session without reason** — Only on explicit request or peak-hours deprioritization.
4. **Log everything** — Every spawn, kill, restart, health check logged with timestamp.
5. **Fail open** — If the daemon crashes, sessions continue running independently.
6. **Respect ANTHROPIC_API_KEY unset** — All spawned sessions must NOT have ANTHROPIC_API_KEY in env (Max subscription, not API credits).

### Rate Limit Safety

```
Peak hours (8 AM - 2 PM ET weekdays):
  - max_chats = 2
  - No agent spawns in CCA sessions
  - Deprioritize lowest-priority sessions

Off-peak / weekends:
  - max_chats = 3
  - Full agent capabilities
```

### Financial Safety

The daemon NEVER:
- Reads or modifies Kalshi bot configuration
- Places or cancels bets
- Accesses financial APIs or databases
- Modifies trading parameters

It only launches the Kalshi chat processes — the bot's own safety rules govern trading.

---

## 8. CLI Interface

```bash
# Start the daemon (foreground for testing, -d for background)
python3 session_daemon.py start
python3 session_daemon.py start -d  # Daemonize

# Stop gracefully (let sessions finish, don't kill them)
python3 session_daemon.py stop

# Stop and kill all managed sessions
python3 session_daemon.py stop --kill-sessions

# Show status
python3 session_daemon.py status
# Output:
# Session Daemon: RUNNING (PID 12345, uptime 2h 15m)
# Sessions:
#   cca-desktop    ALIVE  (PID 23456, uptime 1h 50m, context 45%)
#   kalshi-main    ALIVE  (PID 34567, uptime 2h 10m)
#   kalshi-research ALIVE  (PID 45678, uptime 2h 10m)
# Peak hours: OFF (next peak in 4h 20m)
# Restarts today: 2 (cca-desktop x1, kalshi-research x1)

# Manually restart a specific session
python3 session_daemon.py restart cca-desktop

# Pause auto-restart for a session (manual override)
python3 session_daemon.py pause kalshi-research

# Resume auto-restart
python3 session_daemon.py resume kalshi-research

# View audit log
python3 session_daemon.py log
python3 session_daemon.py log --last 20
```

---

## 9. Audit Log Format

```jsonl
{"ts":"2026-03-21T10:00:05","event":"daemon_started","pid":12345}
{"ts":"2026-03-21T10:00:06","event":"session_spawned","session":"cca-desktop","pid":23456}
{"ts":"2026-03-21T10:00:07","event":"session_spawned","session":"kalshi-main","pid":34567}
{"ts":"2026-03-21T12:15:30","event":"session_died","session":"cca-desktop","exit_code":0,"reason":"clean_wrap"}
{"ts":"2026-03-21T12:16:00","event":"session_spawned","session":"cca-desktop","pid":56789,"restart_count":1}
{"ts":"2026-03-21T14:00:00","event":"peak_hours_started","action":"paused kalshi-research"}
{"ts":"2026-03-21T14:00:01","event":"session_paused","session":"kalshi-research","reason":"peak_hours"}
```

Storage: `~/.cca-session-daemon.log` (JSONL, append-only)

---

## 10. Implementation Phases

### Phase 1: Design (THIS SESSION — S110)
- Write this design document
- Review existing infrastructure
- Identify integration points
- NO CODE

### Phase 2: Session Registry + Tmux Manager (next session)
- `session_registry.py` — Config loading, session tracking, state persistence
- `tmux_manager.py` — Create/monitor/kill tmux windows
- Tests for both (target: 40+ tests)
- NO daemon loop yet — just the building blocks

### Phase 3: Daemon Loop (following session)
- `session_daemon.py` — Poll loop, health checking, spawn/restart logic
- Integration with existing crash_recovery.py and chat_detector.py
- Tests including simulated session death/restart scenarios
- CLI interface (start/stop/status)

### Phase 4: Integration Testing (separate session)
- Dry run: start daemon, let it manage 2 sessions
- Verify restart on clean wrap
- Verify crash detection and scope cleanup
- Verify peak hours behavior
- Measure: does it actually save Matthew time?

### Phase 5: Hardening (separate session)
- Max restart limits
- Graceful shutdown on SIGTERM/SIGINT
- PID file for daemon singleton enforcement
- Log rotation (don't fill disk)

---

## 11. Open Questions (resolve in Phase 2+)

1. **Should the daemon run inside tmux or outside?**
   Option A: Daemon is the first window in the tmux session (self-hosted)
   Option B: Daemon runs as a background process outside tmux
   Leaning: Option A — if someone kills the tmux session, daemon dies too (fail-safe)

2. **How to detect "clean wrap" vs "crash"?**
   Option A: Check exit code (0 = clean, non-zero = crash)
   Option B: Look for wrap markers in pane output
   Option C: Check for SESSION_RESUME.md timestamp
   Leaning: Option A + C combined

3. **Should the daemon manage Kalshi sessions directly or delegate to launch_kalshi.sh?**
   Option A: Daemon does tmux management directly (consistent)
   Option B: Daemon calls launch_kalshi.sh (reuses existing auth fixes)
   Leaning: Option A — but must replicate ANTHROPIC_API_KEY unset logic

4. **What happens when Matthew is at the computer?**
   The daemon should step back when Matthew is actively using a session.
   Detection: If a session has had user input in the last N minutes, don't auto-restart it.
   This prevents the daemon from fighting with Matthew's manual session management.

---

## 12. Success Criteria

The session daemon is COMPLETE when:
1. Matthew types one command to start all sessions
2. Sessions auto-restart after clean wraps
3. Crashed sessions are detected within 2 minutes
4. Orphaned scopes are released on crash detection
5. Peak hours reduce active chats automatically
6. The daemon itself is restartable without side effects
7. All actions are logged in the audit trail
8. Matthew can leave the computer for 8+ hours and return to find sessions still cycling

---

## 13. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rapid restart loop burns API credits | HIGH | Max restart count (5/hour), restart delay (30-60s) |
| Daemon crashes and sessions stop cycling | MEDIUM | Sessions continue independently; daemon restarts clean |
| Daemon spawns too many sessions during peak | HIGH | Hard `max_total_chats` limit; peak hours override |
| API key accidentally set in spawned session | HIGH | Explicit `unset ANTHROPIC_API_KEY` before every spawn |
| Stale scope claims from crashed sessions | MEDIUM | Integrate crash_recovery.py into health check loop |
| Tmux not installed | LOW | Check at daemon start, fail with clear error |

---

## References

- ORCHESTRATION_GAPS.md — Gap analysis that motivated this design
- S103_STRATEGIC_VISION.md — Strategic context for automation
- launch_worker.sh, launch_kalshi.sh — Existing launch patterns
- chat_detector.py, crash_recovery.py — Existing health tooling
- session_pacer.py — Session timing decisions
- peak_hours.py — Rate limit awareness
