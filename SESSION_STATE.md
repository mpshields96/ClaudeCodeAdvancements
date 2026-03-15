# ClaudeCodeAdvancements — Session State
# Update at end of every session before closing.

---

## Current State (as of Session 9 — 2026-03-15)

**Phase:** Wrap-up session. Sessions 7+8 work is complete but uncommitted. Must commit before new code.
**Next session starts at:** `git add` + commit all untracked files from sessions 7+8, then AG-3 or USAGE-1.

---

## CRITICAL: Uncommitted Work From Sessions 7+8

All files below exist on disk and tests pass, but have never been committed. Commit first:

```bash
git add agent-guard/hooks/credential_guard.py
git add agent-guard/ownership.py
git add agent-guard/tests/test_credential_guard.py
git add agent-guard/tests/test_ownership.py
git add context-monitor/hooks/
git add context-monitor/statusline.py
git add context-monitor/tests/
git add memory-system/cli.py
git add memory-system/tests/test_cli.py
git add reddit-intelligence/
git add .claude/commands/ag-ownership.md
git add .claude/commands/cca-auto.md
git add .claude/commands/cca-init.md
git add .claude/commands/cca-review.md
git add .claude/commands/cca-wrap.md
git add .claude/commands/reddit-intel/
git add .claude/commands/reddit-research.md
git add FINDINGS_LOG.md
git add .claude/settings.local.json
git add CLAUDE.md
git add SESSION_STATE.md
```

Then commit with a message covering sessions 7+8 deliverables.

---

## What Was Done in Session 9

Wrap-only session. No new code. Confirmed 404/404 tests passing across 13 suites.

---

## What Was Done in Session 8 (2026-03-08)

### CTX-4: Auto-Handoff Stop Hook (complete — 27 tests)

**File:** `context-monitor/hooks/auto_handoff.py`

**What it does:**
- Runs at session end (Stop hook)
- If context zone is `critical` → blocks exit, asks Claude to run `/handoff`
- If context zone is `red` → warns to stderr (non-blocking by default)
- If `HANDOFF.md` was written in the last 5 minutes → always allows exit (anti-loop)
- Silent pass-through for green/yellow/unknown

**Anti-loop mechanism:** `handoff_is_fresh(path, max_age_minutes)` checks mtime.

**Output format (Stop hook):**
- Allow: `{}`
- Block: `{"decision": "block", "reason": "..."}`

**Environment variables:**
- `CLAUDE_CONTEXT_STATE_FILE` — state file (default: `~/.claude-context-health.json`)
- `CLAUDE_CONTEXT_HANDOFF_PATH` — HANDOFF.md path (default: `./HANDOFF.md`)
- `CLAUDE_CONTEXT_HANDOFF_AGE` — max age minutes before re-triggering (default: 5)
- `CLAUDE_CONTEXT_HANDOFF_RED` — set "1" to also block on red zone
- `CLAUDE_CONTEXT_HANDOFF_DISABLED` — set "1" to disable

**Wired:** `Stop` hook in `.claude/settings.local.json`

---

### CTX-5: Compaction Anchor Hook (complete — 22 tests)

**File:** `context-monitor/hooks/compact_anchor.py`

**What it does:**
- Runs as PostToolUse hook (alongside meter.py)
- Every N tool calls (default: 10), writes `.claude-compact-anchor.md` to project root
- File contains: context zone/%, session ID prefix, last tool called, instructions to re-read SESSION_STATE.md after compaction
- Stores `turn_count` as a machine-parseable comment for round-trip integrity
- Atomic write via temp file

**Key functions:**
- `should_write(turn_count, write_every)` — True at turn 0 and every N turns
- `build_anchor_content(state, tool_name, turn_count, session_id)` — builds markdown
- `load_anchor_turn_count(path)` — reads back `<!-- turn_count: N -->` from anchor

**Environment variables:**
- `CLAUDE_CONTEXT_STATE_FILE` — state file path
- `CLAUDE_CONTEXT_ANCHOR_PATH` — anchor file path (default: `./.claude-compact-anchor.md`)
- `CLAUDE_CONTEXT_ANCHOR_EVERY` — write interval in turns (default: 10)
- `CLAUDE_CONTEXT_ANCHOR_DISABLED` — set "1" to disable

**Wired:** second hook in `PostToolUse` array in `.claude/settings.local.json`

---

### MEM-5: CLI Memory Viewer (complete — 28 tests)

**File:** `memory-system/cli.py`

**Usage:**
```bash
python3 memory-system/cli.py list                           # Current project memories
python3 memory-system/cli.py list --project myapp          # Specific project
python3 memory-system/cli.py list --global                 # Global memories
python3 memory-system/cli.py list --all                    # All projects
python3 memory-system/cli.py list --confidence HIGH        # Filter by confidence
python3 memory-system/cli.py list --type decision          # Filter by type
python3 memory-system/cli.py search "SQLite"               # Keyword/tag search
python3 memory-system/cli.py delete mem_20260219_143022_abc  # Delete by ID
python3 memory-system/cli.py purge                         # Remove expired memories
python3 memory-system/cli.py stats                         # Summary counts
```

**TTL by confidence:** HIGH=365 days, MEDIUM=180 days, LOW=90 days

---

### AG-2: Ownership Manifest (complete — 27 tests)

**Files:** `agent-guard/ownership.py`, `agent-guard/tests/test_ownership.py`, `.claude/commands/ag-ownership.md`

**What it does:**
- CLI tool: `python3 agent-guard/ownership.py`
- Reads last N git commits (default: 20), maps which files were changed by which session
- Detects "conflict risk" files — those appearing in 2+ commits in the window
- Shows uncommitted changes (files in-flight this session)
- Outputs Markdown report with columns: File | Last Session | Date | Commit
- Session label extraction: recognizes "AG-1:", "CTX-3:", "Session 6:" prefixes in commit subjects
- Available as `/ag-ownership` slash command

**Options:** `--commits N`, `--hours N`, `--conflicts-only`, `--output PATH`

---

### CTX-3: Alert Hook (complete — 24 tests)

**File:** `context-monitor/hooks/alert.py`

PreToolUse hook. Silent for cheap tools (Read/Glob/Grep/TodoWrite). Warns before expensive tools (Agent/WebSearch/WebFetch/Bash/Write/Edit) in red/critical zones. Opt-in blocking via `CLAUDE_CONTEXT_ALERT_BLOCK=1`.

---

### CTX-2: Statusline (complete)

**File:** `context-monitor/statusline.py`

Reads native `context_window.used_percentage` from stdin JSON (Claude Code provides this natively). ANSI-colored bar: `CTX [======    ] 45% ok   | $0.02 | Sonnet`. Wired in `~/.claude/settings.json` globally.

---

### CTX-1: Context Meter Hook (complete — 36 tests)

**Files:**
- `context-monitor/hooks/meter.py` — PostToolUse hook
- `context-monitor/tests/test_meter.py` — 36 tests

**What it does:**
1. Reads session transcript JSONL after every tool call
2. Extracts total prompt tokens from `entry["message"]["usage"]` (assistant entries)
3. Computes % of configured window (default 200k)
4. Classifies: green (<50%) / yellow (50–70%) / red (70–85%) / critical (≥85%)
5. Writes state atomically to `~/.claude-context-health.json`

**Transcript path derivation:**
```python
project_hash = os.getcwd().replace('/', '-')  # e.g. '-Users-matthewshields-...'
path = ~/.claude/projects/<project_hash>/<session_id>.jsonl
```

---

### AG-3: Credential-Extraction Guard (complete — 40 tests)

**File:** `agent-guard/hooks/credential_guard.py`

PreToolUse hook. Flags Bash commands that could extract env vars, read .env files, or exfiltrate credentials.

---

### reddit-intel plugin (complete — 43 tests)

**Files:** `reddit-intelligence/` — full plugin including reddit_reader.py, test suite, commands.

---

## What Was Done in Session 7

### reddit-intel Claude Code Plugin (complete)

`.claude/commands/reddit-intel/` contains symlinks to `reddit-intelligence/commands/ri-*.md`.
Available in this project as `/reddit-intel:ri-scan`, `/reddit-intel:ri-read`, `/reddit-intel:ri-loop`.

---

## What Was Done in Session 6

### AG-1: Mobile Approver iPhone Hook (complete — 36 tests)
- `agent-guard/hooks/mobile_approver.py` — PreToolUse hook using ntfy.sh
- Sends push notification to iPhone with Allow/Deny action buttons on lock screen
- Claude waits up to 60s for response; fails open if no network or no topic configured

### Reddit Scout + browse-url global skill (complete)

---

## Frontier Status

| Frontier | Module | Status | Tests | Next Action |
|----------|--------|--------|-------|-------------|
| 1: Persistent Memory | memory-system/ | MEM-1 ✅ MEM-2 ✅ MEM-3 ✅ MEM-4 ✅ MEM-5 ✅ | 94/94 | Frontier complete |
| 2: Spec System | spec-system/ | SPEC-1–6 ✅ | 26/26 | Frontier complete |
| 3: Context Monitor | context-monitor/ | CTX-1 ✅ CTX-2 ✅ CTX-3 ✅ CTX-4 ✅ CTX-5 ✅ | 109/109 | Frontier complete |
| 4: Agent Guard | agent-guard/ | AG-1 ✅ AG-2 ✅ AG-3 ✅ | 103/103 | Frontier nearly complete |
| 5: Usage Dashboard | usage-dashboard/ | Research ✅ Code [ ] | — | USAGE-1: token counter |

---

## Total Test Count

| Module | Tests | Status |
|--------|-------|--------|
| memory-system (capture) | 37 | 37/37 passing |
| memory-system (mcp_server) | 29 | 29/29 passing |
| memory-system (cli) | 28 | 28/28 passing |
| spec-system | 26 | 26/26 passing |
| research (reddit_scout) | 29 | 29/29 passing |
| agent-guard (mobile_approver) | 36 | 36/36 passing |
| agent-guard (ownership) | 27 | 27/27 passing |
| agent-guard (credential_guard) | 40 | 40/40 passing |
| context-monitor (meter) | 36 | 36/36 passing |
| context-monitor (alert) | 24 | 24/24 passing |
| context-monitor (auto_handoff) | 27 | 27/27 passing |
| context-monitor (compact_anchor) | 22 | 22/22 passing |
| reddit-intelligence (reader) | 43 | 43/43 passing |
| **Total** | **404** | **404/404 passing** |

---

## Key Architecture Decisions (cumulative)

| Decision | Rationale |
|----------|-----------|-
| Memory capture via Stop hook | Stop has `last_assistant_message` — better context than PostToolUse alone |
| Transcript JSONL for explicit memory | `transcript_path` in Stop payload; explicit user "remember/always/never" → HIGH confidence |
| 8-char UUID suffix for memory IDs | 3-char caused collisions at 100 rapid-fire creates. 8-char is collision-resistant. |
| SPEC_GUARD_MODE env var | Default warn-only — never surprises user. Opt-in blocking. |
| `hookSpecificOutput.permissionDecision` | PreToolUse ONLY event using hookSpecificOutput. Top-level `block` silently fails. |
| Stop hook block format | `{"decision": "block", "reason": "..."}` — NOT hookSpecificOutput (different from PreToolUse) |
| Spec system is slash commands | Zero-infrastructure, user-invoked. Only the guard is a hook. |
| Local-first storage (`~/.claude-memory/`) | User owns data. No external dependency. Privacy by default. |
| Transcript format | `entry["message"]["usage"]` for assistant entries. `input + cache_read + cache_create = total`. |
| `--project` per subparser | argparse subparsers don't inherit parent parser options — must add to each subcommand |

---

## Open Items

### USAGE-1: Token counter dashboard
- macOS menu bar app UX (or Streamlit)
- Thinking token visibility (Opus blindsides Pro users)
- Per-session cost tracking

---

## Session 10 Start Protocol

1. **FIRST ACTION:** Commit all untracked files from sessions 7+8 (see CRITICAL section above)
2. Run all 13 test suites — confirm 404/404
3. Read SESSION_STATE.md (this file)
4. Choose: USAGE-1 (token counter) or additional AG-4 work
5. State what you're building before touching any file
