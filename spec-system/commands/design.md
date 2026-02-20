# /spec:design

Generate a `design.md` from an approved `requirements.md`. No code yet.

## Precondition Check

Before starting, verify:
1. `requirements.md` exists in the project root (or path the user specifies)
2. The file contains `Status: APPROVED` — not DRAFT

If requirements.md is missing: "Run `/spec:requirements` first to define what we're building."
If status is DRAFT: "Requirements haven't been approved yet. Review `requirements.md` and say 'approved' when ready."

---

## What This Command Does

Reads the approved `requirements.md` and produces a `design.md` — the architectural blueprint. Design covers HOW the system works, not the code itself.

**Design is about decisions, not implementation.**

You review and approve `design.md` before tasks are generated.

---

## Design Sections to Generate

Read the requirements carefully. Then generate `design.md` with these sections:

### 1. Architecture Overview
- What are the major components? (2–6 components for most features)
- How do they relate to each other? (data flow, dependencies)
- One-paragraph prose description + a simple ASCII diagram if helpful

### 2. Key Design Decisions
For each significant architectural choice, document:
- **Decision**: What was chosen
- **Alternatives considered**: What else was considered
- **Rationale**: Why this choice over the alternatives

Minimum 3 decisions. Maximum 8. These are the entries most likely to become HIGH-confidence memories.

Examples of good decisions:
- Storage: SQLite vs JSON vs in-memory
- Delivery: hook vs CLI vs MCP server vs slash command
- Dependencies: stdlib vs external package (with justification)
- Error handling strategy: fail-fast vs graceful degradation

### 3. File Structure
The target file layout for this feature. One line per file with a comment.

```
module-name/
├── main.py          # Entry point / orchestration
├── store.py         # Data persistence only
├── hooks/
│   └── trigger.py  # Hook handler
└── tests/
    └── test_main.py
```

**Rule**: Every file has a comment describing its single responsibility. If you can't write the comment, the file shouldn't exist yet.

### 4. Data Structures
Any key data structures (classes, dicts, JSON schemas) that the implementation will use.
Reference the memory system schema as a model for how to define these.
No code — just the shape and field definitions.

### 5. External Interfaces
What does this feature touch outside its own files?
- Files it reads/writes (paths)
- Environment variables it uses
- Other modules it imports from
- Claude Code hooks it registers
- APIs it calls (if any)

### 6. What This Design Does NOT Include
Explicit exclusions — things that won't be built in this version, even if they seem natural.
This prevents scope creep during implementation.

### 7. Open Questions
Any design questions that couldn't be resolved from requirements alone. These need answers before implementation starts. If there are none, write "None — ready to implement."

---

## After Generating design.md

Say: **"Here is your `design.md`. Review the key decisions section especially carefully — those choices will shape everything that follows. When you're satisfied, say 'approved' and we'll generate `tasks.md`. Still no code yet."**

Do NOT generate tasks.md yet. Do NOT suggest implementation order. Do NOT write any code.

---

## Output Template

```markdown
# Design: [Feature Name]
Generated: [YYYY-MM-DD]
Requirements: requirements.md (APPROVED)
Status: DRAFT — not yet approved

---

## Architecture Overview

[One paragraph. What are the components and how do they connect?]

[ASCII diagram if the component relationships benefit from visual representation]

---

## Key Design Decisions

### Decision 1: [Topic]
- **Chosen:** [What was decided]
- **Alternatives:** [What else was considered]
- **Rationale:** [Why this over alternatives]

[Repeat for each decision — minimum 3, maximum 8]

---

## File Structure

```
[module-name]/
├── [file.py]     # [single responsibility]
```

---

## Data Structures

### [Structure Name]
[Field definitions — name, type, purpose. No code syntax required.]

---

## External Interfaces

- **Files read:** [paths]
- **Files written:** [paths]
- **Environment variables:** [names and purpose]
- **Imports from:** [module names]
- **Hooks registered:** [hook event names]
- **External APIs:** [none, or list]

---

## Not In This Design

[List of explicit exclusions for this version]

---

## Open Questions

[Questions that need resolution before implementation, or "None — ready to implement."]

---

## Approved
[ ] Approved by user on [date]
```

---

## Rules for This Command

- Never write code in design.md
- Never suggest "here's how you'd implement this" — that's tasks.md territory
- If a design decision is unclear from requirements, make a reasonable choice and note it in Open Questions
- When the user says "approved": update `Status: DRAFT` → `Status: APPROVED`, fill in date
- Design.md should be readable by a developer who has never seen the requirements — it stands alone
