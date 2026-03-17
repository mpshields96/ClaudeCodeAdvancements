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

## Step 6 — Review & Apply (Self-Learning)

This is the self-improvement loop. Claude catches its own patterns and auto-writes rules.

### 6a — Log session outcome to journal

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 self-learning/journal.py log session_outcome \
    --session [SESSION_NUMBER] --domain general \
    --outcome [success/partial/failure] \
    --notes "[one-sentence summary of what was accomplished]" \
    --learnings '[LIST_OF_LEARNINGS_FROM_STEP_5]'
```

Use the grade from Step 2: A/B = success, C = partial, D = failure.

### 6a.5 — Log pain/win signals from self-assessment

From the WINS and LOSSES in Step 2, log individual pain and win events. These feed the
self-learning pattern detector and build a dataset of what works vs what wastes time.

For each WIN bullet from Step 2:
```bash
python3 self-learning/journal.py log win \
    --session [SESSION_NUMBER] --domain [relevant_domain] \
    --notes "[the win, one sentence]"
```

For each LOSS bullet from Step 2:
```bash
python3 self-learning/journal.py log pain \
    --session [SESSION_NUMBER] --domain [relevant_domain] \
    --notes "[the loss/friction, one sentence]"
```

Domain mapping: use the most relevant domain from the valid list:
`nuclear_scan`, `memory_system`, `spec_system`, `context_monitor`, `agent_guard`,
`usage_dashboard`, `reddit_intelligence`, `self_learning`, `general`

If the session had no clear losses: log at least one win. If the session was a D grade:
log at least one pain. This ensures every session contributes data.

### 6b — Run reflection to detect patterns

```bash
python3 self-learning/reflect.py --brief
```

If patterns are detected, output them. If any pattern has a suggestion, note it for the user.

### 6c — Auto-escalate learnings to rules

Scan LEARNINGS.md for any entry with **Severity: 3** and **Count: 3+** that does NOT already
have a corresponding rule file in `.claude/rules/`. For each qualifying entry:

1. Create a rule file at `.claude/rules/[topic].md` with the pattern and fix
2. Append to the LEARNINGS.md entry: `- **Promoted:** [date] -> .claude/rules/[topic].md`

Scan for any entry with **Severity: 2** and **Count: 2+** that is NOT already referenced in
the project CLAUDE.md. For each qualifying entry:

1. Add a bullet to the "Known Gotchas" section of CLAUDE.md
2. Append to the LEARNINGS.md entry: `- **Promoted:** [date] -> CLAUDE.md Known Gotchas`

If no entries qualify: skip silently. Do not fabricate promotions.

### 6d — Apply strategy changes from detected patterns

If reflect.py detected patterns with suggestions (e.g., threshold adjustments), apply them:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/reflect.py --apply
```

Review the output. For each applied change:
- If the change suggests a new project rule (e.g., "always do X before Y"), add it to the
  appropriate `.claude/rules/` file inside this project
- If the change is a strategy parameter tweak, it's already written to `strategy.json` by `--apply`

Log any rule file changes:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/journal.py log strategy_update \
    --session [SESSION_NUMBER] --domain self_learning \
    --outcome success \
    --notes "[what was changed and why]"
```

If no patterns had suggestions: skip silently.

### 6e — Check for recurring session-level anti-patterns

Review the last 3 session entries in CHANGELOG.md. If you see the same type of issue
appearing in 2+ consecutive sessions (e.g., "forgot to commit", "tests broke from same cause",
"spent time on overhead"), output:

```
RECURRING ANTI-PATTERN DETECTED: [pattern]
Suggestion: [specific fix — new rule, workflow change, or automation]
```

If no recurring patterns: skip silently.

### 6f — Structural health check

If the `/arewedone` command is available, run it as a structural health check:

```
/arewedone
```

Record the result as pass, warn, or fail. If not available, skip and record "skipped".

### 6g — Print Session Learning Summary

After all sub-steps above, output this summary block:

```
SESSION LEARNING:
- Patterns detected: [N from 6b]
- Rules updated: [list of .claude/rules/ files changed, or "none"]
- Strategy changes: [list of strategy.json changes from 6d, or "none"]
- Learnings escalated: [list of severity promotions from 6c, or "none"]
- Structural health: [pass/warn/fail/skipped from 6f]
```

This block is mandatory — always print it, even if all values are "none"/"0".

---

## Step 7 — Update PROJECT_INDEX.md

If any new files were created this session, add them to PROJECT_INDEX.md.
If no new files: skip this step.

---

## Step 8 — Stage and display diff

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && git status && git diff --stat
```

Show the user what will be committed. Do NOT commit automatically —
let the user decide when to commit (they may want to review first).

---

## Step 9 — Resume prompt

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
