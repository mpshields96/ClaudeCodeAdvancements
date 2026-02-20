# /spec:tasks

Generate `tasks.md` — an ordered, atomic task list — from an approved `design.md`.

## Precondition Check

Before starting, verify:
1. `requirements.md` exists with `Status: APPROVED`
2. `design.md` exists with `Status: APPROVED`

If either is missing or DRAFT: "Both requirements.md and design.md must be approved first."

---

## What This Command Does

Reads the approved `design.md` and decomposes it into an ordered list of atomic, testable, committable tasks. Each task is a unit of work that:
- Does exactly one thing
- Has a clear pass/fail test
- Results in a git commit
- Takes no more than ~500 lines of code to implement

---

## Task Generation Rules

### What Makes a Good Task
- **Atomic**: one file added or one function written, not "build the module"
- **Testable**: a specific assertion that proves it works ("function returns None for empty input")
- **Ordered**: every task depends only on tasks above it — no circular dependencies
- **Bounded**: if a task would take > 500 lines, split it
- **Named**: verb-first names ("Write the schema", "Build the capture hook", "Add the CLI viewer")

### Task Ordering Principle
Bottom-up: foundations before features, schema before code, storage before logic, logic before UI.
Never order tasks so that task N requires something task N+1 will build.

### Mandatory First Task
Task 1 is always: **"Set up the module structure"** — create the directory, add an empty `__init__.py` if needed, create the test file, verify imports work.

### Mandatory Last Task
Final task is always: **"Run full smoke tests and confirm all pass"** — this is the promotion gate.

---

## Task Format

Each task in `tasks.md` uses this format:

```markdown
### Task N: [Verb-first name]
**File(s):** [file path(s) to create or modify]
**What to build:** [2–4 sentences describing exactly what to implement]
**Test:** [One specific assertion that proves this task is done]
**Commit message:** [Proposed git commit message]
**Status:** [ ]
```

---

## Output Template

```markdown
# Tasks: [Feature Name]
Generated: [YYYY-MM-DD]
Design: design.md (APPROVED)
Status: DRAFT — not yet approved

Progress: 0 / N tasks complete

---

## Task List

### Task 1: Set up module structure
**File(s):** `[module-name]/`, `[module-name]/__init__.py`, `[module-name]/tests/`
**What to build:** Create the directory structure from design.md. Add an empty `__init__.py`. Create an empty test file. Verify `python3 -c "import [module]"` runs without error.
**Test:** `python3 -c "from [module] import [main_class]"` exits with code 0.
**Commit message:** "scaffold [module-name] directory structure"
**Status:** [ ]

---

### Task 2: [Next task]
**File(s):** ...
**What to build:** ...
**Test:** ...
**Commit message:** ...
**Status:** [ ]

---

[... remaining tasks ...]

---

### Task N: Run full smoke tests
**File(s):** No new files
**What to build:** Run `python3 [module-name]/tests/test_[module].py` and verify all tests pass. Fix any failures before marking complete.
**Test:** Test runner exits with code 0. Output shows "OK" with N tests.
**Commit message:** "all [module-name] smoke tests passing ([N] tests)"
**Status:** [ ]

---

## Approved
[ ] Approved by user on [date]
```

---

## After Generating tasks.md

Count the tasks. Say: **"Here is your `tasks.md` with N tasks. Review the order — does each task depend only on what comes before it? When you're satisfied, say 'approved' and we'll begin implementing task by task with `/spec:implement`."**

Do NOT begin implementing. Do NOT write any code.

---

## Rules for This Command

- Maximum 20 tasks per tasks.md. If more are needed, the scope is too large — split into two features.
- Never write code in tasks.md — only descriptions of what to build
- Every task must have a test — "it works" is not a test
- When the user says "approved": update Status DRAFT → APPROVED, fill date
- Tasks.md is the contract for `/spec:implement` — be precise
