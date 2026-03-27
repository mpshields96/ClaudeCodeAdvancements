# Codex Learnings

This file stores durable lessons Codex should reuse across CCA sessions.
It is intentionally lightweight: stable heuristics, recurring gotchas, and
workflow rules that improve execution without duplicating Claude Code's larger
memory system.

## Stable Rules

- Read `AGENTS.md` and `SESSION_STATE.md` before substantive CCA work
- In CCA, read `TODAYS_TASKS.md` when present
- Default to budget-conscious reasoning; recommend high only when the task has hidden complexity or expensive failure
- Use branch-first workflow for normal coding tasks
- Use git commit messages as the primary durable handoff to Claude Code
- Do not update Claude-owned state files unless Matthew explicitly asks
- Read broadly for context, write narrowly in assigned scope

## Current Workflow Heuristics

- One focused task or one branch per chat is the sweet spot
- When the branch changes or the conversation becomes mixed, start a fresh chat
- If Claude Code is actively moving a code path, prefer adjacent support work or docs over conflicting edits
- If direct inter-agent messaging is unavailable, commits and concise relay notes are the bridge

## Reuse Targets From CCA

- `SESSION_RESUME.md` and `SESSION_STATE.md` define the init ritual
- `TODAYS_TASKS.md` is the daily priority override when present
- CCA's wrap/autoloop model is best mirrored as: init -> focused work loop -> concise wrap -> commit handoff
- Self-learning value comes from distilled patterns, not copying every internal mechanism

## Learned So Far

### 2026-03-27

- Multiple ROM files in `pokemon-agent/` do not define the active target; anchor on explicit assignment and current repo state
- Narrow, repo-local permissions plus branch-first workflow are safer and more useful than broad machine-wide access
- When git state looks inconsistent, verify with `git status`, `git log`, and explicit branch checks before assuming local changes still need to be committed
