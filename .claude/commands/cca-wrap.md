# /cca-wrap — ClaudeCodeAdvancements Session Wrap-Up

Run the full session wrap ritual. Fully autonomous — no confirmation needed at any step.

---

## Step 1 — Run all tests

Run every test suite. ALL must pass before any docs get updated.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
for f in $(find . -name "test_*.py" -type f | sort); do
  echo "=== $f ==="
  python3 "$f" 2>&1 | tail -1
done
```

If any test fails: fix it before proceeding. Do not skip failing tests to update docs.

Count total tests passing (sum all "Ran N tests" numbers).

---

## Step 2 — Self-assessment (be brutally honest)

Review what was actually accomplished this session. Output:

```
SESSION WRAP — [session number] — [today's date]

WINS:
- [What moved the needle — concrete deliverables, new tests, features shipped]

LOSSES:
- [What wasted time, caused bugs, went in circles, or was abandoned]

GRADE: [A/B/C/D]
- A = shipped working code with tests, no regressions
- B = made progress, minor issues
- C = spent most of the time on overhead or debugging
- D = net negative — broke things or wasted the session

ONE THING next session must do differently:
[specific, actionable]
```

---

## Step 3 — Update SESSION_STATE.md

Update `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md` with:
- Session number incremented
- Date
- What was completed (bullets with file names)
- New test count
- What's next (specific task, not vague)
- Any architectural decisions made

---

## Step 4 — Append to CHANGELOG.md

Append (NEVER overwrite) to `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CHANGELOG.md`.

If the file doesn't exist, create it with a header first.

Format:

```
## Session [N] — [YYYY-MM-DD]

**What changed:**
- [bullet per change, with file names]

**Why:**
- [motivation — what problem was solved or what feature was requested]

**Tests:** [N]/[N] passing

**Lessons:**
- [anything learned that future sessions should know]

---
```

This file is append-only. NEVER truncate or rewrite previous entries.

---

## Step 5 — Capture learnings

Review the session for any mistakes, gotchas, or patterns worth remembering.
Append to `/Users/matthewshields/Projects/ClaudeCodeAdvancements/LEARNINGS.md`.

If the file doesn't exist, create it with this header:
```
# CCA Learnings — Severity-Tracked Patterns
# Severity: 1 = noted, 2 = hard rule, 3 = global (promoted to ~/.claude/rules/)
# Append-only. Never truncate.
```

Format per entry:
```
### [SHORT TITLE] — Severity: [1/2/3] — Count: [N]
- **Anti-pattern:** [what went wrong]
- **Fix:** [the correct approach]
- **First seen:** [date]
- **Last seen:** [date]
- **Files:** [where it applies]
```

Rules for severity escalation:
- First occurrence: Severity 1 (noted here)
- Second occurrence: Severity 2 (add as hard rule to CLAUDE.md)
- Third occurrence: Severity 3 (tell user to promote to ~/.claude/rules/ for all projects)

If a pattern from a previous session recurred this session, bump its Count and Last seen
date. If Count reaches the next severity threshold, escalate it.

If nothing was learned this session: skip this step. Don't fabricate lessons.

---

## Step 6 — Update PROJECT_INDEX.md

If any new files were created this session, add them to PROJECT_INDEX.md.
If no new files: skip this step.

---

## Step 7 — Stage and display diff

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && git status && git diff --stat
```

Show the user what will be committed. Do NOT commit automatically —
let the user decide when to commit (they may want to review first).

---

## Step 8 — Resume prompt

Output a copy-paste prompt for the next session:

```
RESUME PROMPT (copy-paste into next CCA session):
---
Run /cca-init. Last session was [N] on [date].
[One sentence: what was just completed.]
[One sentence: what's next — specific task from SESSION_STATE.]
Tests: [N]/[N] passing. Git: [clean/uncommitted changes].
---
```

---

## Rules

- Fully autonomous — execute every step without asking
- Tests MUST pass before updating any docs
- CHANGELOG.md is append-only — NEVER truncate
- Self-assessment must be honest — do not inflate grades
- Resume prompt is the most important output — never skip it
- Do not push to remote — only stage changes
