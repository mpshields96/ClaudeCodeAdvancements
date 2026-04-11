# Codex Prime Directive

**Authority:** Matthew explicit directive.
**Intent:** Codex should operate as a real CCA hivemind member, not a parallel side system.

---

## The Directive

**The fastest way for Codex to become CCA is to steal and adopt CCA's proven briefing, self-learning, and workflow tools before building parallel Codex-only systems.**

When a useful capability already exists inside CCA, Codex should default to:

1. Read it
2. Reuse it
3. Surface it in Codex workflow
4. Feed results back into it

Codex should only build a separate Codex-specific mechanism when:
- the CCA mechanism cannot be used safely in Codex
- the CCA mechanism is tightly coupled to Claude-only platform behavior
- adapting the CCA mechanism would be objectively worse than a small Codex shim

---

## What This Means In Practice

### 1. Steal CCA intelligence first

Before inventing a new Codex prompt ritual, memory habit, or wrap process, check whether CCA already has:
- a briefing tool
- a self-learning tracker
- a resurfacer
- a coordination protocol
- a wrap analysis tool
- a session-quality signal

If it exists and is useful, Codex should adopt it.

### 2. Prefer adaptation over duplication

Good:
- Surfacing `wrap_tracker.py trend` inside Codex init
- Surfacing `tip_tracker.py pending` inside Codex auto
- Converting actionable pending tips into immediate follow-through or durable repo rules instead of leaving them as suggestion-only output
- Using `session_outcome_tracker.py init-briefing` to shape Codex task selection
- Using `self-learning/resurfacer.py corrections` to avoid repeated mistakes

Bad:
- Building a second Codex-only trend tracker when `wrap_tracker.py` already solves the problem
- Writing Codex-only task selection heuristics while ignoring `SESSION_RESUME.md`, `TODAYS_TASKS.md`, and CCA learning outputs
- Creating a parallel memory system just because Codex is a different agent

### 3. Feed Codex work back into CCA

Adoption is not read-only. If Codex benefits from CCA systems, Codex should also strengthen them by:
- updating shared CCA session docs when appropriate
- writing durable handoff notes
- logging tips or outcomes when useful
- codifying no-brainer improvements immediately when they are safe, local, and in scope
- extending tests around shared workflow tools

### 4. Build thin Codex shims, not alternate universes

When Codex needs a Codex-specific layer, keep it thin:
- prompt builders
- launch wrappers
- command aliases
- compatibility glue

The thin layer should expose CCA logic, not replace it.

---

## Decision Rule

When Codex is about to build something new, ask:

**"Does CCA already have a tool, tracker, briefing, or learning loop that solves 70%+ of this?"**

If yes:
- adopt it first
- adapt only the missing 30%

If no:
- build the smallest new layer that fits CCA's existing architecture

---

## Anti-Patterns

These violate the directive:

- Building Codex-only process systems because they feel cleaner than learning CCA
- Ignoring CCA's self-learning outputs at init time
- Treating Codex as permanently separate from the CCA hivemind
- Duplicating trackers, prompts, or wrap logic that already exist in CCA
- Letting Codex docs drift away from real CCA workflow behavior

---

## Success Criteria

Codex is following this directive when:
- Codex init surfaces the same high-value learning signals CCA uses
- Codex auto follows CCA task authority and handoff files
- Codex wrap feeds CCA's learning loop instead of only summarizing locally
- Codex-specific code mostly acts as adapters around CCA systems
- New Codex improvements make CCA stronger, not more fragmented

---

## Short Version

**Become CCA by stealing CCA's best internal machinery, not by rebuilding a second CCA next to it.**
