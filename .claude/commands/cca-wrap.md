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

## Step 1.5 — Senior dev review on changed files

Run a quick senior review on files changed this session. This catches issues before commit.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
# Get list of changed .py files (not tests, not __pycache__)
CHANGED=$(git diff --name-only HEAD~$(git log --oneline --since="4 hours ago" | wc -l | tr -d ' ') 2>/dev/null | grep '\.py$' | grep -v test_ | grep -v __pycache__ | head -5)
if [ -n "$CHANGED" ]; then
  for f in $CHANGED; do
    echo "=== Senior Review: $f ==="
    python3 agent-guard/senior_review.py "$f" 2>/dev/null || echo "  (review skipped)"
  done
fi
```

If any file gets a REJECT verdict: note it in the self-assessment losses.
If all files pass or get CONDITIONAL: proceed normally.
If no .py files changed: skip this step.

---

## Step 1.7 — APF checkpoint (hit_rate_tracker)

Run the APF (Actionable Post Frequency) checkpoint to track scan quality trends:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 self-learning/hit_rate_tracker.py report 2>/dev/null || echo "hit_rate_tracker not available"
```

Record the APF% and any frontier-level breakdown. Compare to last session's APF.
If APF dropped: note the decline in losses (Step 2). If APF improved: note in wins.
Target: 40% APF. Current baseline: 22.7% (S102).

This step is fast (reads FINDINGS_LOG, no API calls) and feeds the session learning summary.

---

## Step 1.8 — APF session snapshot (trend tracking)

Record an APF snapshot for this session to enable session-over-session trend tracking:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 self-learning/apf_session_tracker.py snapshot S<SESSION_NUMBER> 2>/dev/null || echo "apf_session_tracker not available"
python3 self-learning/apf_session_tracker.py status 2>/dev/null || true
```

Replace `<SESSION_NUMBER>` with the actual session number (e.g., S115).
This appends one line to `~/.cca-apf-snapshots.jsonl` (append-only, never overwrites).
The status line shows delta vs previous session — include in Step 2 wins/losses.

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

### 6a.1 — Record session outcome (trend tracking)

Record the session's planned-vs-completed outcome for cross-session trend analysis:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 session_outcome_tracker.py auto-record SESSION_STATE.md --tests-added [TESTS_ADDED_THIS_SESSION] --tests-total [TOTAL_TEST_COUNT]
```

Replace `[TESTS_ADDED_THIS_SESSION]` with the number of new tests written this session.
Replace `[TOTAL_TEST_COUNT]` with the total from Step 1.
This parses SESSION_STATE.md to extract planned/completed tasks, counts commits from git log,
auto-grades, and appends to `session_outcomes.jsonl` (append-only JSONL).

After recording, show the trend:
```bash
python3 session_outcome_tracker.py trend --last 5
```

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

### 6a.6 — Persist wrap assessment

Log the self-assessment from Step 2 to the wrap tracker for cross-session trend analysis:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 wrap_tracker.py log [SESSION_NUMBER] [GRADE] \
    --wins [WIN_BULLET_1] [WIN_BULLET_2] ... \
    --losses [LOSS_BULLET_1] ... \
    --tests [TOTAL_TEST_COUNT]
```

This creates a persistent record of session quality trends. Use the grade and
win/loss bullets from Step 2 verbatim. The test count should be the total from Step 1.

### 6a.7 — Extract and persist advancement tips

Scan the conversation for any "Advancement tip:" lines output during this session.
For each tip found, log it:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 tip_tracker.py add "[TIP_TEXT]" --source cca-desktop --session S[SESSION_NUMBER]
```

If no tips were generated this session (unlikely — every response should end with one),
skip silently. This ensures all tips persist across sessions rather than being lost.

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

### 6f — Skillbook evolution (YoYo-inspired)

Review the session's findings, learnings, and outcomes against SKILLBOOK.md strategies.
Read `/Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/SKILLBOOK.md`.

For each active strategy (S1-S10+):
- If this session **validated** the strategy (new evidence confirms it): bump confidence by 5 (max 100)
- If this session **contradicted** the strategy (evidence against it): drop confidence by 10
- If a strategy hits confidence < 20: move to Archived section

If this session revealed a NEW pattern not captured by any existing strategy:
- Add it as an Emerging Strategy (confidence 30-35)
- Must have source sessions and evidence

Update APF if new findings were logged:
- Recount: APF = (BUILD + ADAPT) / total findings * 100
- Update the APF History table with this session's row

This step makes the Skillbook a living document that evolves every session — like YoYo's
self-restructuring code, but applied to research intelligence strategies.

### 6g — Structural health check

If the `/arewedone` command is available, run it as a structural health check:

```
/arewedone
```

Record the result as pass, warn, or fail. If not available, skip and record "skipped".

### 6g.5 — Sentinel adaptation cycle

Run the adaptive mutation engine to evolve the self-learning system:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 self-learning/improver.py evolve
```

This generates counter-strategies from failures, cross-pollinates successes, and scans
for weak spots. Record mutations/gaps count in the session learning summary.

### 6h — Validate Skillbook strategies

Run the strategy validation check against journal evidence:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 self-learning/validate_strategies.py --brief
```

Record the output. If any strategy shows WEAK or UNVALIDATED status, note it in the
session learning summary. This ensures every session ends with a strategy health check.

### 6i — Print Session Learning Summary

After all sub-steps above, output this summary block:

```
SESSION LEARNING:
- Patterns detected: [N from 6b]
- Rules updated: [list of .claude/rules/ files changed, or "none"]
- Strategy changes: [list of strategy.json changes from 6d, or "none"]
- Learnings escalated: [list of severity promotions from 6c, or "none"]
- Skillbook updates: [strategies promoted/demoted/added, or "none"]
- APF: [current %] ([up/down/stable] from last session)
- Structural health: [pass/warn/fail/skipped from 6g]
- Strategy health: [output from 6h — or "skipped"]
- Sentinel: [mutations/cross-pollinations/gaps from 6g.5 — or "skipped"]
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

## Step 8.5 — Send session-end notification (MT-22)

Send a push notification so Matthew knows the session has finished:

```bash
python3 context-monitor/session_notifier.py wrap --auto --session S[SESSION_NUMBER] --grade [GRADE]
```

Reads task count and elapsed time from session pacer state. Requires `MOBILE_APPROVER_TOPIC`.
Fails silently if not configured — never blocks wrap.

---

## Step 8.9 — Deregister from session orchestrator

```bash
CCA_ROLE="${CCA_CHAT_ID:-desktop}"
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/session_orchestrator.py deregister "$CCA_ROLE"
```

---

## Step 9 — Resume prompt + write SESSION_RESUME.md

Output a copy-paste prompt for the next session AND write it to disk (for desktop autoloop):

```
RESUME PROMPT (copy-paste into next CCA session):
---
Run /cca-init. Last session was [N] on [date].
[One sentence: what was just completed.]
[One sentence: what's next — specific task from SESSION_STATE.]
Tests: [N]/[N] passing. Git: [clean/uncommitted changes].
---
```

**CRITICAL for desktop autoloop (MT-22):** Also write the resume prompt to disk so the
autoloop can detect session completion via mtime change:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/resume_generator.py --force
```

This writes `SESSION_RESUME.md` from the current SESSION_STATE.md. The desktop autoloop
watches this file for mtime changes to know when to start the next iteration. If you
skip this step, the autoloop will hang indefinitely waiting for a signal that never comes.

---

## Step 10 — Trigger next session (Desktop Autoloop — MT-22)

This is the FINAL step. After SESSION_RESUME.md is written to disk, trigger the next
CCA session automatically. This makes CCA self-sustaining — each session spawns the next.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 autoloop_trigger.py
```

What this does (see CLAUDE.md "Desktop Autoloop Workflow" for full spec):
1. Reads SESSION_RESUME.md
2. Verifies Code tab is active in Claude.app
3. Clicks "+ New session" (Cmd+N) to open a fresh chat
4. Pastes the resume prompt into the NEW chat
5. Sends it (Cmd+Return)

**If the trigger fails:** Print the error but do NOT retry or debug. The wrap is still
complete. Matthew can manually start the next session.

**If `--no-autoloop` was passed or `CCA_NO_AUTOLOOP=1` is set:** Skip this step entirely.
This allows manual sessions without auto-chaining.

---

## Rules

- Fully autonomous — execute every step without asking
- Tests MUST pass before updating any docs
- CHANGELOG.md is append-only — NEVER truncate
- Self-assessment must be honest — do not inflate grades
- Resume prompt is the most important output — never skip it
- Do not push to remote — only stage changes
- Step 10 (autoloop trigger) runs LAST — after all docs are committed

## CRITICAL: End-of-Wrap Behavior

After Step 10 fires the autoloop trigger, your wrap is COMPLETE. Follow these rules exactly:

1. Output one final line: `Session [N] wrap complete. Autoloop triggered.`
   (or `Session [N] wrap complete. Autoloop skipped.` if trigger was skipped/failed)
2. **STOP RESPONDING.** Do not output any further text.
3. Do NOT say "done", "exit", "safe to close", "acknowledged", or any other sign-off.
4. Do NOT respond to your own completion — there is no Step 11.
5. If the user says nothing, say nothing. Wait silently for the next user message.

The exit loop anti-pattern (repeatedly saying "Done." / "Exit." / "Safe to close.") wastes tokens and confuses the user. The wrap is finished when the autoloop trigger fires. Full stop.
