# /spec:implement

Execute tasks from an approved `tasks.md`, one at a time, with a commit after each.

## Precondition Check

Before starting, verify:
1. `tasks.md` exists with `Status: APPROVED`
2. Ask: "Which task number should we start on?" (default: first incomplete task)

If tasks.md is missing or DRAFT: "Run `/spec:tasks` first and approve the task list."

---

## What This Command Does

Reads `tasks.md`, finds the next incomplete task (Status: [ ]), implements it, verifies the test passes, commits, then marks the task complete (Status: [x]).

**One task. One test. One commit. Then stop and show the user what was done.**

---

## Execution Protocol (TDD: Red → Green → Commit)

For each task:

### Step 1 — State what you're doing
"Implementing Task N: [task name]. File(s): [files]. Here's what I'll build: [summary]."

Do not write code until after stating this.

### Step 2 — Write the test FIRST (Red phase)
Write the test(s) specified in the task's "Test" field BEFORE writing any implementation code.
Run the test. It MUST fail. If it passes before implementation exists, the test is not testing
anything real — rewrite it to actually exercise the implementation.

**Why this matters:** Without red-first, tests can pass by accident (wrong assertions, testing
mocks instead of real code, or — worst case — injecting production fixes inside the test itself).

### Step 3 — Implement (Green phase)
Write the minimum code to make the test pass. Nothing more. Nothing less.

If the task says "add function X", add function X. Do not also refactor function Y while you're there.

### Step 4 — Run the test again (Verify green)
Run the specific test from the task's "Test" field. Show the output.

If the test fails: fix the implementation code (NOT the test). Show what changed and why.
Run the test again. Only proceed when it passes.

**Critical:** If you need to change the test to make it pass, explain why. Changing both the
test and implementation simultaneously is a red flag for Goodhart's Law gaming.

### Step 5 — Commit
Run: `git add [specific files from this task only]`
Then: `git commit -m "[task's commit message]"`

Never `git add .` — only stage files from this task.

### Step 6 — Mark complete
Update `tasks.md`: change the task's `**Status:** [ ]` → `**Status:** [x]`
Update the progress counter: `Progress: N / M tasks complete`

### Step 7 — Report and pause
"Task N complete. Committed as [short hash]. [N] of [M] tasks done.

Next task: [Task N+1 name].
Say 'continue' to proceed, or review the code first."

**Always stop after each task and wait for the user to say 'continue'.**
Never chain multiple tasks without user confirmation between them.

---

## When All Tasks Are Complete

After the final task:
"All [N] tasks complete. [Feature name] is implemented.

Here's what was built:
[Bullet list of task names, one line each]

Run `python3 [module-name]/tests/test_[module].py` to confirm all tests pass.

If tests pass, this feature is ready for production use."

---

## Rules for This Command

- **One task per execution** — never implement multiple tasks in a single response without user confirmation
- **The test must pass before committing** — never commit a failing task
- **Only stage files from the current task** — `git add specific-file.py`, not `git add .`
- **Never modify files outside the task's listed file(s)** — if a bug in another file is discovered, note it but don't fix it in this task
- **Never add features not in the task description** — implement exactly what's specified
- **If a task is unclear**, ask one specific clarifying question before starting — don't guess
- **If a task would require touching files owned by another task**, split the work and flag it
