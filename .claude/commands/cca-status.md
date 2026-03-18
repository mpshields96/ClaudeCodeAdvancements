# /cca-status — Nuclear-Level CCA Project Overview

Generate a comprehensive status report covering ALL modules, tests, hooks, and tasks.
Execute every step autonomously. No user input needed.

---

## Step 1 — Run all tests (parallel, capture counts)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
total=0; failed=0
for f in $(find . -name "test_*.py" -type f | sort); do
  result=$(python3 "$f" 2>&1)
  n=$(echo "$result" | grep "Ran " | awk '{print $2}')
  status=$(echo "$result" | tail -1)
  total=$((total + n))
  if echo "$status" | grep -q "FAILED"; then
    failed=$((failed + 1))
    echo "FAIL: $f"
  fi
done
echo "TOTAL: $total tests, $failed failures"
```

---

## Step 2 — Git health

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
git status --short
git log --oneline -10
echo "---"
git diff --stat HEAD~5..HEAD
```

---

## Step 3 — Read current state files

Read these in parallel:
- `PROJECT_INDEX.md` — module map and test counts
- `SESSION_STATE.md` — current phase and next actions (first 30 lines)
- `MASTER_TASKS.md` — MT-0 through MT-16 status (grep for Status lines)
- `ROADMAP.md` — first 50 lines for priorities

---

## Step 4 — Check live hooks

```bash
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/.claude/settings.local.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
hooks = data.get('hooks', {})
for event, entries in hooks.items():
    for entry in entries:
        matcher = entry.get('matcher', '*')
        for h in entry.get('hooks', []):
            cmd = h.get('command', '')
            # Extract just the filename
            name = cmd.split('/')[-1] if '/' in cmd else cmd
            print(f'  {event:20s} [{matcher or \"*\":10s}] {name}')
"
```

---

## Step 5 — Module completeness

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/usage-dashboard/arewedone.py 2>&1
```

---

## Step 6 — Self-learning health

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/validate_strategies.py --brief 2>&1
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/paper_scanner.py stats 2>&1
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/improver.py stats 2>&1
```

---

## Step 7 — Reddit intelligence status

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/autonomous_scanner.py status 2>&1
```

---

## Step 8 — Output the nuclear report

Format the output as a single, dense report:

```
============================================
CCA NUCLEAR STATUS REPORT — [date]
============================================

TESTS: [total]/[total] [OK/FAILING] ([N] suites)
GIT: [clean/dirty] | [N] commits last 5 sessions
HOOKS: [N] live hooks across [N] events

FRONTIERS:
  1. memory-system    [STATUS] [test count] tests
  2. spec-system      [STATUS] [test count] tests
  3. context-monitor  [STATUS] [test count] tests
  4. agent-guard      [STATUS] [test count] tests
  5. usage-dashboard  [STATUS] [test count] tests

SUPPORT MODULES:
  reddit-intelligence [test count] tests | [scan status]
  self-learning       [test count] tests | APF: [N]% | [N] strategies
  research            [test count] tests

MASTER TASKS:
  [For each MT-0 through MT-16: one-line status]

SELF-LEARNING:
  Strategies: [N] validated, [N] contradicted
  Papers: [N] logged | [N] IMPLEMENT, [N] REFERENCE, [N] SKIP
  Improvements: [stats]

NEXT PRIORITIES:
  1. [from SESSION_STATE]
  2. [from SESSION_STATE]
  3. [from SESSION_STATE]

SESSION HISTORY (last 5):
  [session] [date] [one-line summary]
============================================
```

---

## Rules

- Execute ALL steps autonomously — no user input needed
- If any test fails, report it prominently
- Keep the report under 80 lines
- This is a READ-ONLY command — do not modify any files
