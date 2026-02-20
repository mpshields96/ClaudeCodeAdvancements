# spec-system — Module Rules

## What This Module Does
Enforces and scaffolds spec-driven development: Requirements → Design → Tasks → Implement.
Prevents the most common architecture failure mode: coding before thinking.

## The Problem It Solves (Validated)
- Unstructured prompting consistently produces code that passes immediate tests but creates architectural debt
- The spec-first workflow is the #1 recommended workflow tip across r/ClaudeCode and r/vibecoding
- Token optimization via spec-first reduces redundant fetching by 60-80% (measured)
- Amazon Kiro formalizes this for enterprise; no open tool exists for individual Claude Code users
- SWE-Bench Pro: best models score 23.3% on long-horizon tasks — the root cause is poor upfront specification

## Delivery Mechanism
Slash commands (`.claude/commands/`) — zero infrastructure, immediately usable:
- `/spec:requirements` → interview → `requirements.md`
- `/spec:design` → `design.md`
- `/spec:tasks` → `tasks.md`
- `/spec:implement` → task-by-task execution
- PreToolUse hook → warn if Write fires without spec

## Architecture Rules

**The Spec Sequence (non-negotiable order):**
1. `requirements.md` — WHAT it does, WHO uses it, WHAT are the constraints, WHAT are failure modes
2. `design.md` — HOW it works (architecture, decisions, structure) — NOT implementation
3. `tasks.md` — ordered atomic tasks, each ~500 lines max, each testable, each committable
4. Implementation — one task at a time, commit after each

**What a good task looks like:**
- Atomic: does ONE thing
- Testable: has a clear pass/fail criterion
- Bounded: ~100-500 lines of code maximum
- Committable: represents a clean git checkpoint
- Ordered: depends only on tasks above it in the list

**What is NOT a task:**
- "Build the authentication system" (too large)
- "Write tests" (must be paired with the feature it tests)
- "Set up the project" (not atomic)

## File Structure
```
spec-system/
├── CLAUDE.md                   # This file
├── commands/
│   ├── requirements.md         # /spec:requirements slash command (SPEC-1)
│   ├── design.md               # /spec:design slash command (SPEC-2)
│   ├── tasks.md                # /spec:tasks slash command (SPEC-3)
│   └── implement.md            # /spec:implement slash command (SPEC-4)
├── hooks/
│   └── validate.py             # PreToolUse: warn if Write fires without spec (SPEC-5)
├── templates/
│   ├── requirements.template.md
│   ├── design.template.md
│   └── tasks.template.md
├── tests/
│   └── test_spec.py
└── research/
    └── EVIDENCE.md
```

## Non-Negotiable Rules
- **User must approve requirements.md before design.md is generated**
- **User must approve design.md before tasks.md is generated**
- **User must approve tasks.md before implementation starts**
- **No code is written during requirements or design phases**
- **Implementation runs one task at a time — not the whole list at once**
- **Each task gets a git commit before the next task starts**

## Build Order
1. SPEC-1: `commands/requirements.md` — Socratic interview command
2. SPEC-2: `commands/design.md` — design generator from requirements
3. SPEC-3: `commands/tasks.md` — task decomposer from design
4. SPEC-4: `commands/implement.md` — task-by-task executor
5. SPEC-5: `hooks/validate.py` — PreToolUse guard (last, after commands are validated)
