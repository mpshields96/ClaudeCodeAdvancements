# context-monitor — Module Rules

## What This Module Does
Provides real-time context health monitoring and automated protection against context rot and the compaction bug.

## The Problem It Solves (Validated)
- Context rot: output quality degrades measurably as context fills, but users have no signal
- Community standard "compact at 60%" is manually tracked — no automation
- The compaction bug: CLAUDE.md rules are silently forgotten after auto-compact fires (100% compliance → 100% violation, binary)
- "Overconfident junior with amnesia" — the most cited characterization of long-session failures

## Delivery Mechanism
1. **Status line**: real-time context health display in Claude Code status bar
2. **PreToolUse hook**: alert before expensive calls when context is high
3. **Stop hook**: auto-generate handoff document when threshold exceeded
4. **Compaction guard**: generate a compact CLAUDE.md digest immune to compaction loss

## Architecture Rules

**Context Health Thresholds (configurable, sensible defaults):**
- Green zone: 0–50% — full effectiveness, no action
- Yellow zone: 50–70% — warn user, suggest /compact before complex tasks
- Red zone: 70–85% — alert before every tool use, recommend immediate handoff
- Critical: >85% — auto-trigger handoff document generation

**What a Handoff Document Contains:**
- Current task: what we were building, where we left off
- Decisions made this session: architectural choices, rejected approaches
- Next steps: specific, ordered, actionable
- Files modified: list of all writes this session
- Open questions: anything unresolved
- NOT: full conversation log, code snippets, rationale beyond one sentence

**Compaction Guard Philosophy:**
The CLAUDE.md compaction guard is a distillation, not a copy. It answers: "What are the 10 things Claude is most likely to forget after compaction?" Those 10 things get stored externally and injected into every session start.

## File Structure
```
context-monitor/
├── CLAUDE.md                   # This file
├── hooks/
│   ├── meter.py                # PostToolUse: read context % → local state (CTX-1)
│   ├── alert.py                # PreToolUse: warn at threshold (CTX-3)
│   └── auto_handoff.py         # Stop: generate handoff at 80%+ (CTX-4)
├── statusline.md               # Status line config (CTX-2)
├── compaction_guard.py         # CLAUDE.md digest generator (CTX-5)
├── tests/
│   └── test_context.py
└── research/
    └── EVIDENCE.md
```

## Non-Negotiable Rules
- **Thresholds are configurable — no hardcoded magic numbers in production code**
- **Handoff documents are written to the project folder, not a temp location**
- **Compaction guard never stores credentials from CLAUDE.md (scan and strip)**
- **All alerts are non-blocking by default — warn, don't stop**
- **The meter hook must be lightweight — < 10ms overhead per tool call**

## Build Order
1. CTX-1: `hooks/meter.py` — read context %, write to state file
2. CTX-2: `statusline.md` — status line integration (reads from state file)
3. CTX-3: `hooks/alert.py` — threshold warning (reads from state file)
4. CTX-4: `hooks/auto_handoff.py` — auto-handoff at critical threshold
5. CTX-5: `compaction_guard.py` — CLAUDE.md digest for compaction resistance

## Key Technical Question (Resolve Before Building)
Does Claude Code's hook payload expose context window usage percentage?
- Check: hook input schema for PreToolUse / PostToolUse / Stop
- If yes: read directly from hook input
- If no: estimate from cumulative token counting (fallback approach)
