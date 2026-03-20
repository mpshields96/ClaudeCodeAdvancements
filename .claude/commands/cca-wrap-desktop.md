# /cca-wrap-desktop — Desktop Coordinator Session Wrap-Up

Run the full session wrap ritual. You are the desktop coordinator — you own all shared docs.
Fully autonomous — no confirmation needed at any step.

---

## Step 1 — Run all tests

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
for f in $(find . -name "test_*.py" -type f | sort); do
  echo "=== $f ==="
  python3 "$f" 2>&1 | tail -1
done
```

All must pass before updating docs. Count total tests.

---

## Step 2 — Check worker inbox

```bash
python3 cca_comm.py inbox
```

Incorporate any worker completion summaries into the session record.

---

## Step 3 — Self-assessment (be brutally honest)

```
SESSION WRAP — [session number] — [today's date]

WINS:
- [Concrete deliverables, new tests, features shipped]
- [Include worker contributions if any]

LOSSES:
- [Time wasted, bugs, circles, abandoned work]

GRADE: [A/B/C/D]
- A = shipped working code with tests, no regressions
- B = made progress, minor issues
- C = spent most time on overhead or debugging
- D = net negative — broke things or wasted the session

ONE THING next session must do differently:
[specific, actionable]
```

---

## Step 4 — Update SESSION_STATE.md

Update with:
- Session number incremented
- Date
- What was completed (bullets with file names)
- Worker contributions (if any)
- New test count
- What's next (specific task)

---

## Step 5 — Append to CHANGELOG.md

Append (NEVER overwrite):

```
## Session [N] — [YYYY-MM-DD]

**What changed:**
- [bullet per change, with file names]

**Why:**
- [motivation]

**Tests:** [N]/[N] passing

**Lessons:**
- [anything learned]

---
```

---

## Step 6 — Capture learnings

Append to LEARNINGS.md if applicable. Follow severity escalation rules (1->2->3).

---

## Step 7 — Self-learning journal

```bash
python3 self-learning/journal.py log session_outcome \
    --session [SESSION_NUMBER] --domain general \
    --outcome [success/partial/failure] \
    --notes "[summary]" \
    --learnings '[]'
```

Run reflection:
```bash
python3 self-learning/reflect.py --brief
```

---

## Step 8 — Update PROJECT_INDEX.md

If new files were created, add them. If not, skip.

---

## Step 9 — Stage and display diff

```bash
git status && git diff --stat
```

Show what will be committed. Do NOT commit automatically.

---

## Step 10 — Resume prompt

Output AND write to `SESSION_RESUME.md`:

```
RESUME PROMPT (copy-paste into next CCA session):
---
Run /cca-init. Last session was [N] on [date].
[What was completed.] [What's next.]
Tests: [N]/[N] passing. Git: [clean/uncommitted].
---
```

---

## Rules

- Fully autonomous — execute every step
- Tests MUST pass before updating docs
- CHANGELOG.md is append-only
- Self-assessment must be honest
- Resume prompt is the most important output — never skip it
