# Compaction Protection Protocol — Design Document

**Task:** 10A (S243, Chat 10)
**Status:** DESIGN
**Author:** CCA S243

---

## Problem Statement

When Claude Code compacts the conversation context (auto or manual), the LLM loses
awareness of the current task, modified files, and session progress. The existing
PostCompact hook (CTX-7) writes a generic recovery digest ("re-read SESSION_STATE.md"),
but this requires Claude to spend multiple turns re-reading files to restore awareness.

**The compaction bug** (confirmed via leaked CC source, 2026-03-31): `compact.ts` diffs
tool discovery lists against `[]` instead of `preCompactDiscoveredTools`, injecting
80-100K tokens of redundant tool definitions into every compacted context. We cannot
fix this server-side bug, but we can minimize the recovery cost on our end.

**Cost of the gap:** Without task-specific recovery, Claude spends 3-8 turns (and
10-30K tokens) re-orienting after compaction. With specific state preserved, recovery
drops to 1 turn.

---

## Design

### Architecture

```
PreCompact hook ──→ snapshot.json ──→ PostCompact hook ──→ recovery digest
  (captures state)    (on disk)       (reads snapshot)     (stdout → Claude)
```

Two hooks work as a pair:
1. **PreCompact** (`pre_compact.py`) — captures external state to a JSON snapshot
2. **PostCompact** (`post_compact.py`) — already exists, enhanced to read the snapshot

### What PreCompact Captures

The PreCompact hook runs BEFORE compaction fires. It has access to the filesystem
and environment but NOT to the conversation itself. It captures external signals:

| Source | Data | Why |
|--------|------|-----|
| `~/.claude-context-health.json` | zone, pct, tokens, turns, window | Pre-compaction health for logging |
| `git status --short` | Modified/untracked files list | Know what Claude was editing |
| `git diff --stat` | Lines changed per file | Scope of work in progress |
| `TODAYS_TASKS.md` | Current TODO items | Task awareness restoration |
| `SESSION_STATE.md` (first 50 lines) | Session number, current work | Session context |
| `.claude-compact-anchor.md` | Last anchor state | Continuity breadcrumb |
| Environment: `CCA_CHAT_ID` | Chat role (desktop/cli1/cli2) | Multi-chat awareness |
| stdin payload | session_id, transcript_path, cwd | Standard hook fields |

**What it does NOT capture:**
- Conversation content (inaccessible from hook)
- Full file contents (too large, can be re-read)
- Design decisions (use /handoff for that)

### Snapshot Format

Written atomically to `~/.claude-compaction-snapshot.json`:

```json
{
  "version": 1,
  "timestamp": "2026-03-31T16:00:00Z",
  "trigger": "auto",
  "session_id": "abc123...",
  "cwd": "/Users/matthewshields/Projects/ClaudeCodeAdvancements",
  "chat_role": "desktop",
  "context_health": {
    "zone": "red",
    "pct": 72,
    "tokens": 144000,
    "turns": 45,
    "window": 200000
  },
  "git_status": [
    "M  context-monitor/hooks/pre_compact.py",
    "M  context-monitor/hooks/post_compact.py",
    "?? context-monitor/tests/test_pre_compact.py"
  ],
  "git_diff_stat": "3 files changed, 180 insertions(+), 12 deletions(-)",
  "todays_tasks_todos": [
    "10A. Design Compaction Protection Protocol [TODO]",
    "10B. Build Compaction Protection [TODO]"
  ],
  "session_header": "Session 243 | Chat 10 | 2026-03-31",
  "anchor_content": "Zone: red (72% of 200k tokens)"
}
```

### PostCompact Enhancement

The existing `post_compact.py` (CTX-7) is enhanced to:

1. Check for `~/.claude-compaction-snapshot.json`
2. If found, build a **specific** recovery digest instead of the generic one
3. Include: git status, current tasks, session context, pre-compaction zone
4. Delete the snapshot after reading (one-time use, prevents stale data)

Enhanced recovery digest example:

```markdown
# Context Compaction Recovery
_Compaction: automatic at 2026-03-31 16:00 UTC_
_Session: S243 Chat 10 (desktop)_

## Pre-Compaction State
- Context was at **red zone** (72%, 144K tokens, 45 turns)
- Working in: /Users/matthewshields/Projects/ClaudeCodeAdvancements

## Files Modified (git status)
- M  context-monitor/hooks/pre_compact.py
- M  context-monitor/hooks/post_compact.py
- ?? context-monitor/tests/test_pre_compact.py

## Current Tasks (from TODAYS_TASKS.md)
- 10A. Design Compaction Protection Protocol [TODO]
- 10B. Build Compaction Protection [TODO]

## Recovery Steps
1. Re-read CLAUDE.md for project rules
2. Re-read SESSION_STATE.md for full session context
3. Run `git diff` on modified files to see your in-progress work
4. Continue with the tasks listed above
```

### Performance Budget

- PreCompact: < 500ms total
  - State file read: ~1ms
  - git status: ~50ms
  - git diff --stat: ~50ms
  - File reads (tasks, session, anchor): ~10ms
  - JSON write: ~1ms
- PostCompact: unchanged (~5ms, already fast)

### Failure Modes

| Failure | Behavior |
|---------|----------|
| PreCompact can't write snapshot | Silent fail — PostCompact falls back to generic digest |
| Snapshot file corrupted | PostCompact ignores it, uses generic digest |
| No git repo in cwd | git fields empty, everything else works |
| TODAYS_TASKS.md missing | tasks field empty |
| Very old snapshot (>1hr) | PostCompact ignores it (staleness guard) |

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLAUDE_PRECOMPACT_DISABLED` | unset | Set "1" to disable PreCompact hook |
| `CLAUDE_COMPACTION_SNAPSHOT_PATH` | `~/.claude-compaction-snapshot.json` | Snapshot location |

PostCompact reads the same `CLAUDE_COMPACTION_SNAPSHOT_PATH` env var.

### Hook Wiring

Add to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/context-monitor/hooks/pre_compact.py"
          }
        ]
      }
    ]
  }
}
```

PostCompact is already wired. No changes needed there — only the Python code changes.

### What This Does NOT Fix

- **The server-side compact.ts bug** (diffs against `[]`): This wastes 80-100K tokens
  inside the compacted context itself. We cannot patch this from hooks. Only Anthropic
  can fix this by diffing against `preCompactDiscoveredTools` instead of `[]`.
- **CLAUDE.md rule amnesia**: Compaction may lose CLAUDE.md instructions. The recovery
  digest tells Claude to re-read CLAUDE.md, but doesn't inject the rules directly
  (that would be too large for stdout).
- **Conversation reasoning**: The hook can't capture Claude's internal reasoning chain.
  Only the compact_summary (AI-generated) preserves a summary of the conversation.

### What This DOES Fix

- **Task continuity**: Claude immediately knows what files are modified and what tasks
  remain, without spending 3-8 turns re-reading files.
- **Git awareness**: Modified file list prevents Claude from re-reading unchanged files
  or missing in-progress edits.
- **Multi-chat awareness**: Chat role preserved, preventing hivemind confusion.
- **Quantified recovery**: Pre-compaction health data enables tracking compaction
  frequency and severity in the self-learning journal.

---

## Test Plan

1. Snapshot write/read round-trip (unit)
2. Missing/corrupt snapshot graceful degradation (unit)
3. Staleness guard (>1hr old snapshot ignored) (unit)
4. Git status parsing with various states (unit)
5. TODAYS_TASKS.md parsing with edge cases (unit)
6. Enhanced recovery digest format validation (unit)
7. PostCompact reads and deletes snapshot (integration)
8. Full PreCompact → PostCompact cycle (integration)

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `context-monitor/hooks/pre_compact.py` | CREATE — PreCompact hook |
| `context-monitor/hooks/post_compact.py` | MODIFY — read snapshot, enhanced digest |
| `context-monitor/tests/test_pre_compact.py` | CREATE — unit tests |
| `context-monitor/tests/test_post_compact.py` | MODIFY — add snapshot integration tests |
| `.claude/settings.local.json` | MODIFY — add PreCompact hook wiring |
