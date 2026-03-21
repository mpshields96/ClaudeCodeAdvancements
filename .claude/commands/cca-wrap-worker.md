# /cca-wrap-worker — CLI Worker Session Wrap-Up

Lightweight wrap for CLI workers. You do NOT own shared docs.
Fully autonomous — no confirmation needed.

---

## Step 1 — Run all tests

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
for f in $(find . -name "test_*.py" -type f | sort); do
  python3 "$f" 2>&1 | tail -1
done
```

All must pass before committing.

---

## Step 2 — Self-assessment (output only)

```
WORKER WRAP — [today's date]

TASK: [what was assigned]
RESULT: [what was built]
TESTS: [how many new tests, total passing]
GRADE: [A/B/C/D]
```

Do NOT write this to SESSION_STATE or CHANGELOG — desktop owns those.

---

## Step 3 — Stage and commit YOUR code only

```bash
git add [files you created/modified]
git commit -m "Worker: [summary of what was built]"
```

Only commit files within your claimed scope. Never commit shared docs.

---

## Step 4 — Report to desktop

```bash
python3 cca_comm.py done "WRAP: [grade] — [summary]. Tests: [N new], [N total]. Files: [list]"
python3 cca_comm.py release "[your claimed scope]"
```

---

## Step 5 — Self-learning journal

Log a session event with your key observation (what worked, what didn't):

```bash
python3 self-learning/journal.py log session_outcome --session [N] --domain general \
    --metrics '{"tasks_completed": N, "tests_added": N, "grade": "[A/B/C/D]"}' \
    --learnings '["one key observation from this worker session"]'
```

Also send your best advancement tip to desktop:

```bash
python3 cca_comm.py say desktop "Advancement tip: [your best insight from this session]"
```

---

## Step 6 — Output resume context (do NOT write files)

Output (but do NOT write SESSION_RESUME.md — desktop owns that):

```
WORKER SESSION COMPLETE
Task: [what was done]
Files changed: [list]
Tests added: [N]
Reported to desktop via cca_comm.py
```

---

## Step 7 — Late inbox check (catch messages sent while wrapping)

Before closing, do a final inbox check. Desktop may have queued a new task while you were wrapping.

```bash
python3 cca_comm.py inbox
```

- If a **new task** is assigned: Do NOT close. Go back to Step 2 of /cca-auto-worker and execute it.
- If a **SHUTDOWN** message is present: Proceed to Step 8.
- If **inbox is empty**: Proceed to Step 8.

This step prevents task loss when desktop sends work after seeing the worker wrap start.

---

## Step 8 — Close terminal tab

After all wrap steps are complete and inbox is empty, close this Terminal tab to prevent stale sessions:

```bash
[[ "$TERM_PROGRAM" == "Apple_Terminal" ]] && \
  osascript -e 'tell application "Terminal" to close front window'
```

This prevents duplicate chat windows from accumulating between sessions.
The guard skips silently when running in Claude Code's built-in shell (where `TERM_PROGRAM` is not `Apple_Terminal` and no Terminal.app window exists to close).
Only exception: if Matthew explicitly said to keep this CLI chat open.

---

## Rules

- Do NOT update SESSION_STATE, PROJECT_INDEX, CHANGELOG, LEARNINGS, SESSION_RESUME
- Only commit files within your claimed scope
- Report completion to desktop coordinator via cca_comm.py
- If tests fail, fix them before committing
- ALWAYS close your terminal tab on wrap (Step 8) unless explicitly told otherwise
- ALWAYS log to self-learning journal (Step 5) — this feeds cross-session improvement
