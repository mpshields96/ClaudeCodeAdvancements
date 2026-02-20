# MASTER_ROADMAP.md — ClaudeCodeAdvancements
# Objective session-by-session execution plan with start prompts.
# Last updated: Session 3 — 2026-02-20
# Source: Validated against r/ClaudeCode, r/ClaudeAI, r/vibecoding community pain points,
#         Anthropic 2026 Agentic Coding Trends, SWE-Bench Pro data.

---

## Why This Document Exists

Sessions burn tokens re-establishing context. This file gives each session:
1. Exactly what to build (no ambiguity)
2. A copy-paste start prompt (no ramp-up)
3. The validation test (definition of done)
4. The community evidence (why it matters)

Do not deviate from session order unless a blocker is hit. If blocked, skip to the next
session and note the blocker in SESSION_STATE.md.

---

## Completion Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete — code + tests passing |
| 🔄 | In progress |
| [ ] | Not started |
| ⛔ | Blocked — see notes |

---

## Phase 1: Memory System (Frontier 1) — MAKE IT USABLE END-TO-END

### Session 4 — MEM-3: Retrieval MCP Server ✅ Priority: CRITICAL

**Why:** MEM-1 (schema) + MEM-2 (capture) are inert without retrieval. The memory system
is currently write-only. Users on r/ClaudeCode consistently cite "Claude forgets everything"
as the #1 pain point. MEM-3 closes the loop.

**What to build:** A local MCP server (Python stdlib only) that exposes two tools:
- `search_memory` — keyword search over stored memories for current project
- `load_memories` — load all memories for current project, sorted by confidence + recency

The server runs on `localhost:7842`, starts automatically, registered in Claude Code MCP config.

**Files:**
- `memory-system/mcp_server.py` — HTTP server + tool handlers
- `memory-system/tests/test_mcp_server.py` — smoke tests

**Definition of done:** Claude can call `search_memory("hooks")` and get back relevant
memories from `~/.claude-memory/claudecodeadvancements.json`.

**Start prompt (copy-paste at session open):**
```
Read PROJECT_INDEX.md, SESSION_STATE.md, memory-system/CLAUDE.md.
Run: python3 memory-system/tests/test_memory.py && python3 spec-system/tests/test_spec.py
Confirm 63/63 passing.

Building MEM-3: local MCP server for memory retrieval.
Files: memory-system/mcp_server.py + memory-system/tests/test_mcp_server.py
Two tools: search_memory (keyword search) + load_memories (full project load).
Python stdlib only. Port 7842. No external dependencies.
Start with /spec:requirements for mcp_server.py.
```

---

### Session 5 — MEM-4: /handoff Slash Command [ ] Priority: HIGH

**Why:** Context compaction silently destroys in-progress work. r/ClaudeCode threads on
"Claude forgot what we were doing after /compact" have hundreds of upvotes. A structured
handoff document written BEFORE compaction preserves exactly what matters.

**What to build:** Slash command that generates a `HANDOFF.md` snapshot:
- Current task (what was being built, where it stopped)
- Key decisions made this session
- Files modified (with one-line descriptions)
- Exact next step (copy-paste resumption prompt)
- Open questions that weren't resolved

**Files:**
- `.claude/commands/handoff.md` — slash command instructions

**Definition of done:** Running `/handoff` produces a `HANDOFF.md` that a fresh Claude
session can read to resume work without re-reading the full transcript.

**Start prompt:**
```
Read PROJECT_INDEX.md, SESSION_STATE.md.
Run both test suites — confirm 63+ tests passing.

Building MEM-4: /handoff slash command.
File: .claude/commands/handoff.md
This is a behavior-instruction markdown file (not Python).
It instructs Claude to generate HANDOFF.md before /compact or session end.
Model it on spec-system/commands/implement.md structure.
No code to write — just the command specification.
```

---

### Session 6 — MEM-5: CLI Memory Viewer [ ] Priority: MEDIUM

**Why:** Users cannot currently inspect or clean their memory store. Stale or wrong memories
silently corrupt future sessions. A simple CLI viewer closes this gap.

**What to build:** `python3 memory-system/cli.py` with three modes:
- Default: list all memories for current project (table format)
- `--search [query]`: keyword filter
- `--delete [id]`: remove a specific memory by ID

**Files:**
- `memory-system/cli.py`
- `memory-system/tests/test_cli.py`

**Definition of done:** `python3 memory-system/cli.py --search hooks` returns all memories
with "hooks" in their content. `--delete mem_xxx` removes it from the JSON store.

**Start prompt:**
```
Read PROJECT_INDEX.md, SESSION_STATE.md, memory-system/CLAUDE.md.
Run both test suites — confirm passing.

Building MEM-5: CLI memory viewer.
Files: memory-system/cli.py + memory-system/tests/test_cli.py
Three modes: list all, --search [query], --delete [id]
Python stdlib only. Reads ~/.claude-memory/[project-slug].json
Start with /spec:requirements for cli.py.
```

---

## Phase 2: Spec System Registration (Frontier 2) — MAKE IT DISCOVERABLE

### Session 7 — SPEC-6: Register Slash Commands [ ] Priority: HIGH

**Why:** The spec system commands exist as markdown files but aren't registered as Claude
Code slash commands. Users can't invoke `/spec:requirements` yet — they'd have to know the
file path. Registration makes them first-class commands.

**What to build:** Project-level slash command wrappers in `.claude/commands/`:
- `spec-requirements.md` — wraps `spec-system/commands/requirements.md`
- `spec-design.md` — wraps `spec-system/commands/design.md`
- `spec-tasks.md` — wraps `spec-system/commands/tasks.md`
- `spec-implement.md` — wraps `spec-system/commands/implement.md`

Each wrapper reads the source command file and delegates to it.

**Definition of done:** Typing `/spec:requirements` in a Claude Code session triggers the
15-question Socratic interview.

**Start prompt:**
```
Read PROJECT_INDEX.md, SESSION_STATE.md, spec-system/CLAUDE.md.
Run both test suites — confirm passing.

Building SPEC-6: register spec-system slash commands in .claude/commands/
Files: .claude/commands/spec-requirements.md, spec-design.md, spec-tasks.md, spec-implement.md
These are thin wrappers that load and execute the spec-system/commands/ source files.
No Python. No tests needed (slash commands are behavior files).
Model on existing spec-system/commands/ file structure.
```

---

## Phase 3: Context Monitor (Frontier 3) — PREVENT SILENT DEGRADATION

### Session 8 — CTX-1: Context Meter Hook [ ] Priority: HIGH

**Why:** Claude Code has no real-time context usage indicator. Users only discover they're
near the limit when output quality degrades silently. r/ClaudeAI threads show this is a
top-3 complaint. The transcript JSONL approach (confirmed feasible in Session 2) makes
this buildable without access to the API internals.

**What to build:** PostToolUse hook that:
1. Reads the transcript JSONL at `transcript_path`
2. Estimates token usage from message character counts (heuristic: ~4 chars/token)
3. Injects a context warning when estimated usage > 70%

**Files:**
- `context-monitor/hooks/context_meter.py`
- `context-monitor/tests/test_context_meter.py`

**Definition of done:** Hook fires after every tool use, estimates context %, and injects
"[context-monitor] ~75% context used. Consider /handoff before continuing." when above threshold.

**Start prompt:**
```
Read PROJECT_INDEX.md, SESSION_STATE.md, context-monitor/CLAUDE.md, context-monitor/research/EVIDENCE.md.
Run both test suites — confirm passing.

Building CTX-1: context meter hook.
Files: context-monitor/hooks/context_meter.py + context-monitor/tests/test_context_meter.py
PostToolUse hook. Reads transcript_path JSONL. Estimates token usage (~4 chars/token heuristic).
Injects warning at 70% and 90% thresholds.
Python stdlib only. Start with /spec:requirements.
```

---

### Session 9 — CTX-2: Compaction Guard [ ] Priority: HIGH

**Why:** /compact destroys in-progress work silently. The guard detects when compaction is
about to happen and fires /handoff first. Directly addresses the r/ClaudeCode "compact wiped
my session" complaint.

**What to build:** PreToolUse hook that intercepts any action when context > 85%, prompts
the user to run `/handoff` first, and injects the reminder as `additionalContext`.

**Files:**
- `context-monitor/hooks/compaction_guard.py`
- Updated `context-monitor/tests/test_context_meter.py`

**Start prompt:**
```
Read PROJECT_INDEX.md, SESSION_STATE.md, context-monitor/CLAUDE.md.
Run all test suites.

Building CTX-2: compaction guard hook.
File: context-monitor/hooks/compaction_guard.py
PreToolUse hook. Fires when context estimate > 85%.
Injects: "[context-monitor] Context near limit. Run /handoff before continuing."
Uses permissionDecision: "allow" + additionalContext (warn-only, not blocking).
```

---

## Phase 4: Agent Guard (Frontier 4) — PREVENT MULTI-AGENT CONFLICTS

### Session 10 — AG-1: Ownership Manifest [ ] Priority: HIGH

**Why:** Parallel Claude Code sessions (increasingly standard in 2026 per r/vibecoding) cause
file conflicts with no warning. Two agents editing the same file produce silent overwrites.
An ownership manifest prevents this at the tool-call level.

**What to build:** `/agent:claim` slash command that writes an `AGENT_MANIFEST.md` file
declaring which files are owned by which agent session. The PreToolUse hook checks this
manifest before allowing Write/Edit.

**Files:**
- `.claude/commands/agent-claim.md` — slash command
- `agent-guard/hooks/ownership_guard.py` — PreToolUse hook
- `agent-guard/tests/test_ownership_guard.py`

**Definition of done:** If Agent A claims `main.py` and Agent B tries to write to `main.py`,
the hook injects a warning: "[agent-guard] main.py is claimed by Agent A. Confirm before proceeding."

**Start prompt:**
```
Read PROJECT_INDEX.md, SESSION_STATE.md, agent-guard/CLAUDE.md, agent-guard/research/EVIDENCE.md.
Run all test suites.

Building AG-1: agent ownership manifest.
Files: .claude/commands/agent-claim.md + agent-guard/hooks/ownership_guard.py + tests
/agent:claim writes AGENT_MANIFEST.md declaring file ownership for this session.
ownership_guard.py is a PreToolUse hook: checks manifest before Write/Edit, warns if conflict.
Python stdlib only. Start with /spec:requirements.
```

---

## Phase 5: Usage Dashboard (Frontier 5) — TOKEN + COST VISIBILITY

### Session 11 — USAGE-1: Token Counter [ ] Priority: MEDIUM

**Why:** Claude Code's $50–200/month cost is opaque. No real-time view of where tokens go.
r/ClaudeAI weekly threads on "unexpected bill" are consistent. Transcript JSONL contains
all the data needed to build an accurate post-session counter.

**What to build:** Stop hook that reads the session transcript, counts tokens per tool call
type, and appends a usage summary to `~/.claude-usage/[date].json`.

**Files:**
- `usage-dashboard/hooks/token_counter.py`
- `usage-dashboard/tests/test_token_counter.py`

**Start prompt:**
```
Read PROJECT_INDEX.md, SESSION_STATE.md, usage-dashboard/CLAUDE.md, usage-dashboard/research/EVIDENCE.md.
Run all test suites.

Building USAGE-1: session token counter.
Files: usage-dashboard/hooks/token_counter.py + tests
Stop hook. Reads transcript_path JSONL. Counts approximate tokens per tool type.
Appends summary to ~/.claude-usage/YYYY-MM-DD.json
Python stdlib only. Start with /spec:requirements.
```

---

### Session 12 — USAGE-2: Cost Dashboard (Streamlit) [ ] Priority: MEDIUM

**Why:** Raw JSON usage logs are not human-readable. A simple Streamlit dashboard turns the
data into a weekly burn rate view — the thing users actually need to manage costs.

**What to build:** `python3 usage-dashboard/dashboard.py` — Streamlit app reading
`~/.claude-usage/*.json` and showing: daily token usage, cost estimate (at $3/$15 per MTok),
breakdown by tool type, week-over-week trend.

**Files:**
- `usage-dashboard/dashboard.py`
- `usage-dashboard/requirements.txt` (Streamlit is the one justified external dep here)

**Start prompt:**
```
Read PROJECT_INDEX.md, SESSION_STATE.md, usage-dashboard/CLAUDE.md.
Run all test suites.

Building USAGE-2: Streamlit cost dashboard.
File: usage-dashboard/dashboard.py
Reads ~/.claude-usage/*.json produced by USAGE-1 token_counter.py
Shows: daily token usage, cost estimate ($3/$15 per MTok input/output), tool breakdown, weekly trend.
Streamlit is justified here (visual dashboard warrants it). requirements.txt: streamlit only.
Start with /spec:requirements.
```

---

## Research Refresh Schedule

Before sessions 8, 10, and 12, re-check community direction:

**Search targets:**
- `r/ClaudeCode` — "most upvoted past month" — look for new pain points
- `r/ClaudeAI` — "Claude Code" flair — check for new hook capabilities in releases
- `r/vibecoding` — "workflow" or "multi-agent" — new patterns emerging

**What to look for:**
- New Claude Code features that change what's buildable (new hook types, MCP updates)
- Pain points that have grown in upvotes since Session 1 research
- Community-built tools that overlap with planned work (don't duplicate)
- New Anthropic announcements (A2A protocol, MCP updates)

**If a significant new pain point is found:** Add it to ROADMAP.md with evidence before
building. Do not pivot mid-session — finish the current session task first.

---

## Objective Priority Rationale

This order is not arbitrary. It follows the dependency graph and impact/effort ratio:

1. **MEM-3 first** — memory is write-only without it. Highest leverage: completes Frontier 1.
2. **MEM-4 next** — handoff command is a force multiplier for all future sessions.
3. **SPEC-6** — makes the already-built spec system actually usable via slash commands.
4. **CTX-1/2** — context degradation is the #2 community complaint after memory loss.
5. **AG-1** — multi-agent workflows are growing but still early in 2026.
6. **USAGE-1/2** — cost visibility is important but not blocking any development workflow.

Reverse this order only if community research reveals a higher-urgency pain point.

---

## Definition of "Shipped"

A frontier is shipped when:
- All planned sub-tasks complete with passing tests
- Hook/command registered in a real Claude Code config (not just the file existing)
- At least one session used it live and it worked
- MODULE_CLAUDE.md updated with any gotchas found in real use

A session is complete when:
- SESSION_STATE.md updated
- All new files committed
- `git push` run
- Next session start prompt is accurate

---

## Current Completion Summary

| Session | Task | Status |
|---------|------|--------|
| 1 | Foundation + research | ✅ |
| 2 | MEM-1, MEM-2, SPEC-1–5 | ✅ |
| 3 | GitHub, housekeeping, MASTER_ROADMAP | ✅ |
| 4 | MEM-3: retrieval MCP server | [ ] |
| 5 | MEM-4: /handoff command | [ ] |
| 6 | MEM-5: CLI memory viewer | [ ] |
| 7 | SPEC-6: register slash commands | [ ] |
| 8 | CTX-1: context meter hook | [ ] |
| 9 | CTX-2: compaction guard | [ ] |
| 10 | AG-1: ownership manifest | [ ] |
| 11 | USAGE-1: token counter | [ ] |
| 12 | USAGE-2: cost dashboard | [ ] |
