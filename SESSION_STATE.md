# ClaudeCodeAdvancements — Session State
# Update at end of every session before closing.

---

## Current State (as of Session 6 — 2026-02-28)

**Phase:** Active development — AG-1 mobile approver complete. browse-url global skill added.
**Next session starts at:** MEM-5 (CLI memory viewer) OR CTX-1 (context meter hook).

---

## What Was Done in Session 6

### AG-1: Mobile Approver iPhone Hook (complete — built in prior context, committed as AG-1)
- `agent-guard/hooks/mobile_approver.py` — PreToolUse hook using ntfy.sh
- Sends push notification to iPhone with Allow/Deny action buttons on lock screen
- Claude waits up to 60s for response; fails open if no network or no topic configured
- `agent-guard/tests/test_mobile_approver.py` — 36 tests, all passing
- `agent-guard/MOBILE_SETUP.md` — 5-minute iPhone setup guide
- Env vars: `MOBILE_APPROVER_TOPIC`, `MOBILE_APPROVER_TIMEOUT`, `MOBILE_APPROVER_DEFAULT`, `MOBILE_APPROVER_DISABLED`

### Reddit Scout (complete — built in prior context)
- `research/reddit_scout.py` — fetches r/ClaudeAI, r/ClaudeCode, r/vibecoding hot posts
- Relevance scoring, rat poison filtering, frontier mapping, dated JSON output
- `research/tests/test_reddit_scout.py` — 29 tests, all passing
- Integrated into `.claude/prompts/auto-session.md` (runs at start of every autonomous session)

### browse-url Global Skill (complete)
- `.claude/commands/browse-url.md` — slash command using Playwright MCP
- Any Claude Code chat can use `/browse-url [URL]` to open and read any URL in Chrome
- Handles Reddit, GitHub, Streamlit with site-specific extraction guidance
- For global use: copy to `~/.claude/commands/browse-url.md`

---

## What Was Done in Session 5

### MEM-4: /handoff Slash Command (complete)
- `.claude/commands/handoff.md` — behavior instruction file
- Generates structured `HANDOFF.md`: current task, decisions, files modified, open questions, resume prompt
- Resume Prompt section is mandatory — enables fresh session to start without re-reading transcript

### SPEC-6: Slash Command Registration (complete)
- `.claude/commands/spec-requirements.md` → invokes `/spec:requirements`
- `.claude/commands/spec-design.md` → invokes `/spec:design`
- `.claude/commands/spec-tasks.md` → invokes `/spec:tasks`
- `.claude/commands/spec-implement.md` → invokes `/spec:implement`
- All four delegate to `spec-system/commands/` source files

### CLAUDE.md updated
- Test commands now include `test_mcp_server.py` (92 total, was 63)

---

## What Was Done in Session 4

### MEM-3: Retrieval MCP Server (complete — 29/29 tests passing)
- `memory-system/mcp_server.py` — JSON-RPC 2.0 over stdio (correct MCP protocol)
- Two tools: `load_memories` (HIGH by default, opt-in MEDIUM) + `search_memory` (keyword, tag, type)
- Sorted: HIGH before MEDIUM, most recent first within each tier
- `_touch_last_used()` updates recency on every retrieval (atomic save)
- `memory-system/tests/test_mcp_server.py` — 29 tests across all functions

**Registration** (add to `~/.claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "claude-memory": {
      "command": "python3",
      "args": ["/Users/matthewshields/Projects/ClaudeCodeAdvancements/memory-system/mcp_server.py"]
    }
  }
}
```

---

## What Was Done in Session 3

### Housekeeping (complete)
- Fixed GitHub remote URL (was pointing to `experimental-agentic-R-D`, now `ClaudeCodeAdvancements`)
- First push to GitHub successful — 54 objects, all files live at https://github.com/mpshields96/ClaudeCodeAdvancements
- Fixed PROJECT_INDEX.md GitHub URL
- Applied CLAUDE.md additions: confirmed hook facts table, test commands, known gotchas
- Updated SESSION_STATE.md (this file)

### No new code written this session (housekeeping + git setup only)

---

## Frontier Status

| Frontier | Module | Status | Tests | Next Action |
|----------|--------|--------|-------|-------------|
| 1: Persistent Memory | memory-system/ | MEM-1 ✅ MEM-2 ✅ MEM-3 ✅ MEM-4 ✅ MEM-5 [ ] | 66/66 | MEM-5: CLI memory viewer |
| 2: Spec System | spec-system/ | SPEC-1–6 ✅ | 26/26 | CTX-1: context meter hook |
| 3: Context Monitor | context-monitor/ | Research ✅ Code [ ] | — | CTX-1: context meter hook (transcript-based) |
| 4: Agent Guard | agent-guard/ | AG-1 ✅ | 36/36 | AG-2: ownership manifest command |
| 5: Usage Dashboard | usage-dashboard/ | Research ✅ Code [ ] | — | USAGE-1: token counter via transcript |

---

## Total Test Count

| Module | Tests | Status |
|--------|-------|--------|
| memory-system (capture) | 37 | 37/37 passing |
| memory-system (mcp_server) | 29 | 29/29 passing |
| spec-system | 26 | 26/26 passing |
| research (reddit_scout) | 29 | 29/29 passing |
| agent-guard (mobile_approver) | 36 | 36/36 passing |
| **Total** | **157** | **157/157 passing** |

---

## Priority for Session 4

**Start here**: MEM-5 — CLI memory viewer
- `memory-system/cli.py` — list, search, delete memories from terminal
- OR CTX-1 — context meter hook (transcript-based, higher user impact)

**Recommended**: CTX-1 — addresses the #2 community complaint after memory loss
- `.claude/commands/spec-requirements.md` etc. as project-level command wrappers

---

## Key Architecture Decisions (cumulative)

| Decision | Rationale |
|----------|-----------|
| Memory capture via Stop hook | Stop has `last_assistant_message` — better context than PostToolUse alone |
| Transcript JSONL for explicit memory | `transcript_path` in Stop payload; explicit user "remember/always/never" → HIGH confidence |
| 8-char UUID suffix for memory IDs | 3-char caused collisions at 100 rapid-fire creates. 8-char is collision-resistant. |
| SPEC_GUARD_MODE env var | Default warn-only — never surprises user. Opt-in blocking. |
| `hookSpecificOutput.permissionDecision` | PreToolUse ONLY event using hookSpecificOutput. Top-level `block` silently fails. |
| Spec system is slash commands | Zero-infrastructure, user-invoked. Only the guard is a hook. |
| Local-first storage (`~/.claude-memory/`) | User owns data. No external dependency. Privacy by default. |

---

## Open Items

### MEM-3: Retrieval MCP Server
- Local HTTP server exposing `search_memory` + `load_memories` tools
- MCP tool spec format for Claude Code recognition
- Python stdlib `http.server` + `json` — no external deps

### MEM-4: /handoff slash command
- Writes handoff document before /compact
- Format: current task, decisions, next steps, files modified

### MEM-5: CLI memory viewer
- `python3 memory-system/cli.py` — show all memories
- `--search [query]` and `--delete [id]` flags

### SPEC: Register slash commands
- `.claude/commands/spec-requirements.md` etc. as project-level command wrappers

### CTX-1 through CTX-5
- Context monitor unblocked — transcript parsing is the correct approach
- CTX-1: token estimator from transcript JSONL line counts

---

## Session 6 Start Protocol

1. Run all three test suites — confirm 92/92:
   - `python3 memory-system/tests/test_memory.py`
   - `python3 memory-system/tests/test_mcp_server.py`
   - `python3 spec-system/tests/test_spec.py`
2. Read SESSION_STATE.md (this file)
3. Read context-monitor/CLAUDE.md and context-monitor/research/EVIDENCE.md
4. State: "Building CTX-1: context meter hook" before touching any file
