# BMAD Party Mode — Patterns for MT-21 Hivemind

Source: https://raw.githubusercontent.com/bmadcode/bmad-method/main/src/core-skills/bmad-party-mode/SKILL.md
Captured: 2026-04-06 (Chat 37, 37A research task)

---

## Core Insight: Real Subagents > Roleplay

BMAD party mode uses actual Agent tool spawns so each agent produces a genuinely
independent perspective. This avoids the "convergence problem" — one LLM roleplaying
multiple voices produces artificial consensus even when instructed to disagree.

Our hivemind already uses this pattern (2 CLI sessions = genuinely separate contexts),
which is even more authentic than BMAD's subagent spawns.

---

## Agent Selection Heuristic

- 2 agents: simple questions, focused tasks
- 3 agents: complex topics
- 4 agents: topics needing multiple domain perspectives

**Application for MT-21:** Current 2-chat (desktop + worker) maps well to 2-agent mode.
3-chat would map to 3-agent. BMAD's heuristic validates our staged rollout plan.

---

## Context Passing Pattern (critical for hivemind quality)

Each spawned agent receives:
1. Conversation summary (keep under 400 words — compression threshold)
2. Other agents' responses so far
3. The user message

**Application for MT-21:** Workers need structured context packets, not raw history.
The 400-word summary cap is a good target for our cca_comm.py task assignments.
Keep task descriptions terse + precise. This is why we use cca_comm claim/done/say.

---

## Presentation Rules

- Display each agent's complete response **unabridged and unsummarized**
- Orchestrator may add brief notes flagging disagreements between agents
- Follow-up spawns: any combination (single agent, reactive pairs, full roster)

**Application for MT-21:** Desktop coordinator should present worker output without
heavy editing. The diff/commit is the "complete response." The SESSION_STATE update
is the orchestrator's summary note.

---

## Config Pattern

BMAD uses:
- `_bmad/core/config.yaml` — runtime config
- `_bmad/_config/agent-manifest.csv` — roster of available agents with capabilities

**Application for MT-21:** Our `session_orchestrator.py` + `cca_comm.py` is our
equivalent. Agent manifest pattern is worth adopting — a CSV/JSON listing of
worker capabilities, current load, and claimed scopes.

---

## Key Difference: Process Isolation

BMAD subagents run within same Claude session (separate agent contexts but same
outer conversation). Our hivemind uses fully separate OS processes (2 terminal
sessions). This is stronger isolation — no shared context window at all.

Implication: our workers can't "see" desktop's tool calls unless we explicitly send
them via cca_comm. This is good (prevents cognitive contamination) but requires
deliberate context injection at task assignment time.

---

## MT-21 Next Steps (unblocked by this research)

1. Formalize agent manifest: add roles/capabilities to session_orchestrator.py
2. Adopt 400-word context cap for cca_comm task assignments
3. Implement "reactive pair" pattern: worker sends question → desktop replies same session
4. Consider 3-chat mode after 5 successful 2-chat sessions (BMAD's 3-agent heuristic validates this)
