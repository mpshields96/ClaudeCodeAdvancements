# ClaudeCodeAdvancements — Project Index
# Generated: 2026-02-19 (Session 1) | Last updated: 2026-02-20 (Session 2)
# Read this first each session — ~94% token reduction vs reading source files

---

## Quick Orientation

| What | Where |
|------|-------|
| Project rules + scope boundaries | `CLAUDE.md` |
| Feature backlog + priorities | `ROADMAP.md` |
| Current state + session resume | `SESSION_STATE.md` |
| This file | `PROJECT_INDEX.md` |

---

## Project Mission

Build the next significant advancements for Claude Code users — grounded in validated community demand, not speculation. Five frontiers, ordered by impact and feasibility.

**NOT a betting project. Zero overlap with Titanium.**

---

## Five Frontiers — Status Overview

| # | Module | What It Solves | Status |
|---|--------|----------------|--------|
| 1 | `memory-system/` | Every session starts from zero | Research |
| 2 | `spec-system/` | Unstructured prompting = poor architecture | Research |
| 3 | `context-monitor/` | Silent context rot + compaction bug | Research |
| 4 | `agent-guard/` | Parallel agents overwrite each other | Research |
| 5 | `usage-dashboard/` | No real-time token/cost visibility | Research |

---

## Module Summaries

### memory-system/
**Solves:** The #1 most-demanded missing feature in Claude Code — every session starts with zero knowledge of previous work.

**Delivery mechanism:** Claude Code hook (PostToolUse / Stop) + local MCP server for retrieval.

**Key constraint:** Local-first. No external APIs for storage. Human-readable format.

**Sub-tasks:**
- MEM-1: Memory schema design
- MEM-2: Capture hook (PostToolUse/Stop)
- MEM-3: Retrieval MCP server
- MEM-4: Compaction-resistant handoff command
- MEM-5: CLI memory viewer

---

### spec-system/
**Solves:** Unstructured prompting → architectural debt. Enforces Requirements → Design → Tasks → Implement.

**Delivery mechanism:** Claude Code slash commands (`/spec:requirements`, `/spec:design`, `/spec:tasks`, `/spec:implement`).

**Key constraint:** No external dependencies. Plain Markdown output. User approves before proceeding.

**Sub-tasks:**
- SPEC-1: `/spec:requirements` — Socratic interview → `requirements.md`
- SPEC-2: `/spec:design` — `requirements.md` → `design.md`
- SPEC-3: `/spec:tasks` — `design.md` → `tasks.md` (atomic, testable tasks)
- SPEC-4: `/spec:implement` — task-by-task execution with commits
- SPEC-5: PreToolUse hook — warn if Write fires without approved spec

---

### context-monitor/
**Solves:** Silent context rot (output degrades at 70%+ context), compaction bug (CLAUDE.md rules forgotten post-compact).

**Delivery mechanism:** Claude Code status line + PreToolUse/Stop hooks.

**Key constraint:** No external dependencies. Configurable thresholds. Hook-based only.

**Sub-tasks:**
- CTX-1: PostToolUse context meter hook → local state file
- CTX-2: Status line display (color-coded health indicator)
- CTX-3: Threshold alert hook (configurable %)
- CTX-4: Auto-handoff document at 80% threshold
- CTX-5: Compaction-guard CLAUDE.md digest generator

---

### agent-guard/
**Solves:** Parallel Claude Code agents overwriting each other's work (no native coordination mechanism).

**Delivery mechanism:** Git-based lock files + PreToolUse hook intercepting Write/Edit.

**Key constraint:** Zero dependencies beyond git. Works with any parallel agent setup (tmux, Agent Teams, worktrees).

**Sub-tasks:**
- AG-1: `/agent:assign` — file ownership manifest (`.agent-manifest.json`)
- AG-2: PreToolUse conflict check hook
- AG-3: Lock file protocol (`.agent-[name].lock`)
- AG-4: Conflict reporter (near-miss log + session summary)

---

### usage-dashboard/
**Solves:** No real-time token/cost visibility — power users hit weekly caps mid-week with no warning.

**Delivery mechanism:** PostToolUse hook → local SQLite + CLI viewer (+ optional Streamlit UI).

**Key constraint:** Local only. Works within Claude Code's observable API surface.

**Sub-tasks:**
- USAGE-1: PostToolUse token counter hook → SQLite
- USAGE-2: Session aggregator
- USAGE-3: CLI viewer (`python3 usage-dashboard/cli.py`)
- USAGE-4: PreToolUse threshold alert
- USAGE-5: Streamlit dashboard (after CLI is stable)

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| External packages | Anthropic SDK only (where needed), stdlib-first |
| Storage | Local JSON + SQLite (no cloud) |
| Delivery | Claude Code hooks + slash commands + MCP |
| UI (optional) | Streamlit (existing pattern from Titanium) |
| Tests | pytest (stdlib) |

---

## File Access Rule

**Read + Write:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` only.
**Forbidden:** Any path outside this folder. Absolute. No exceptions.

---

## Session Resume Checklist

1. Read this file (PROJECT_INDEX.md)
2. Read `SESSION_STATE.md` — current state, last work, open items
3. Read `CLAUDE.md` — project rules
4. Check status column above — pick up where Session State says
5. Read module-level `CLAUDE.md` for the frontier you're working on
6. Run smoke tests if any exist
7. State what you're building before touching any file
