# agent-guard — Module Rules

## What This Module Does
Prevents parallel Claude Code agents from overwriting each other's work via a lightweight file-ownership coordination layer.

## The Problem It Solves (Validated)
- Parallel agent workflows (tmux + git worktrees, Claude Agent Teams) are increasingly standard practice
- There is no native mechanism to prevent agents from overwriting each other's files
- Current workaround: users hard-code file ownership rules in CLAUDE.md — brittle and error-prone
- Claude Squad, Uzi, and CCPM attempt partial solutions but none fully solve conflict detection
- Explicitly requested in team-workflow threads across r/ClaudeCode

## Delivery Mechanism
1. **Manifest**: `/agent:assign` slash command generates `.agent-manifest.json`
2. **Hook**: PreToolUse intercepts Write/Edit calls and checks ownership
3. **Locks**: `.agent-[name].lock` files prevent concurrent access
4. **Reporter**: PostToolUse logs near-misses for review

## Architecture Rules

**Ownership Model:**
- File ownership is declared via glob patterns in `.agent-manifest.json`
- Patterns follow the same syntax as `.gitignore` (fnmatch)
- An agent can own multiple patterns; a pattern is owned by one agent
- Unowned files: any agent can write (with a soft warning if two agents wrote recently)
- Ownership is per-session by default (can be persisted for multi-day projects)

**Conflict Levels:**
- **BLOCK**: target file is explicitly owned by a different agent → deny Write/Edit
- **WARN**: target file is unowned but was written by another agent < 5 minutes ago → warn + confirm
- **PASS**: target file is owned by current agent or unowned with no recent conflict → allow

**What "Agent Name" Means:**
- Agent name is set as an environment variable: `CLAUDE_AGENT_NAME=agent_a`
- If not set, guard operates in WARN-only mode (no blocking)
- Name is short, alphanumeric: `agent_a`, `frontend`, `api_team`, etc.

## File Structure
```
agent-guard/
├── CLAUDE.md                   # This file
├── commands/
│   └── assign.md               # /agent:assign slash command (AG-1)
├── hooks/
│   ├── conflict_check.py       # PreToolUse: ownership check (AG-2)
│   └── reporter.py             # PostToolUse: near-miss logger (AG-4)
├── lock_protocol.py            # Lock file management (AG-3)
├── tests/
│   └── test_agent_guard.py
└── research/
    └── EVIDENCE.md
```

## Non-Negotiable Rules
- **No blocking in WARN mode** — never prevent work when name is unset
- **Lock files must be released on session end** — Stop hook releases all locks
- **Manifest file (`.agent-manifest.json`) lives in project root** — not in this module
- **Zero dependencies beyond Python stdlib + fnmatch** — must work without installing anything
- **Conflict reporter is read-only** — never modifies files, only logs

## Build Order
1. AG-1: `commands/assign.md` — manifest generation command
2. AG-2: `hooks/conflict_check.py` — PreToolUse ownership check
3. AG-3: `lock_protocol.py` — lock file acquire/release
4. AG-4: `hooks/reporter.py` — near-miss logger
