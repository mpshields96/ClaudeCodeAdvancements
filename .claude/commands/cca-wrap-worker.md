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

## Step 5 — Output resume context

Output (but do NOT write SESSION_RESUME.md — desktop owns that):

```
WORKER SESSION COMPLETE
Task: [what was done]
Files changed: [list]
Tests added: [N]
Reported to desktop via cca_comm.py
```

---

## Step 6 — Close terminal tab

After all wrap steps are complete, close this Terminal tab to prevent stale sessions:

```bash
osascript -e 'tell application "Terminal" to close (first window whose frontmost is true)'
```

This prevents duplicate chat windows from accumulating between sessions.
Only exception: if Matthew explicitly said to keep this CLI chat open.

---

## Rules

- Do NOT update SESSION_STATE, PROJECT_INDEX, CHANGELOG, LEARNINGS, SESSION_RESUME
- Only commit files within your claimed scope
- Report completion to desktop coordinator via cca_comm.py
- If tests fail, fix them before committing
- ALWAYS close your terminal tab on wrap (Step 6) unless explicitly told otherwise
