# /cca-nuclear-wrap — Nuclear Scan Session Wrap-Up + Self-Learning

Wrap up a nuclear scan session. Fully autonomous — no confirmation needed.
Generates final report, logs to self-learning journal, runs reflection, updates all docs.

This command replaces the generic /cca-wrap for nuclear scan sessions.
It knows about nuclear_progress.json, FINDINGS_LOG.md, and the self-learning system.

---

## STEP 1 — Run Tests (gate everything behind this)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
for f in $(find . -name "test_*.py" -type f | sort); do
  echo "=== $f ==="
  python3 "$f" 2>&1 | tail -1
done
```

ALL must pass. If any fail: fix before proceeding. Count total tests passing.

---

## STEP 2 — Load Current State

Read these files silently:

```bash
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/findings/nuclear_progress.json
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/findings/nuclear_queue.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Queue: {len(d)} posts')"
```

Read FINDINGS_LOG.md — count entries added this session (compare to progress stats).

---

## STEP 3 — Generate/Update NUCLEAR_REPORT.md

Read the existing report:
```bash
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/findings/NUCLEAR_REPORT.md
```

Update `reddit-intelligence/findings/NUCLEAR_REPORT.md` with:
- Accurate stats from nuclear_progress.json
- All BUILD candidates ranked by score x feasibility
- ADAPT patterns grouped by frontier (1-5)
- Special flags: Polybot-relevant, Maestro-relevant, Usage-Dashboard
- Recurring pain points table (aggregate from all reviewed posts)
- Official Anthropic features noted
- Recommendations for next session (be specific and actionable)

If the queue is fully processed, mark the report as FINAL.
If posts remain, mark as INTERIM with "N/M reviewed, K remaining."

---

## STEP 4 — Self-Learning Journal Entries

Log structured events to the self-learning journal for everything that happened this session.

### 4a. Nuclear batch entry (one per session, aggregated)

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/journal.py log nuclear_batch \
    --session [SESSION_NUMBER] \
    --domain nuclear_scan \
    --outcome success \
    --metrics '{"posts_reviewed": [N], "build": [B], "adapt": [A], "reference": [R], "skip": [S], "fast_skip": [FS], "batches": [BATCH_COUNT], "queue_total": [TOTAL], "queue_remaining": [REMAINING]}' \
    --learnings '[LIST_OF_KEY_LEARNINGS_FROM_THIS_SESSION]' \
    --notes "[Free text summary of the session]"
```

Learnings should be SPECIFIC and actionable, e.g.:
- "CC natively emits OTel metrics — USAGE-1 should integrate with this not reinvent"
- "MCP tools consume 70k+ tokens even when unused — #1 context killer"
- "evolve-yourself frequency-based skill auto-create at 3x/day threshold"

Do NOT log vague learnings like "reviewed some posts" or "found interesting things."

### 4b. Individual BUILD entries

For each BUILD candidate found this session:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/journal.py log review_verdict \
    --domain [FRONTIER_DOMAIN] \
    --metrics '{"score": [PTS], "verdict": "build", "title": "[TITLE]"}' \
    --notes "[URL]"
```

### 4c. Strategy observations

If any patterns suggest strategy adjustments (e.g., "posts under 100pts rarely yield BUILD"),
log them:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/journal.py log pattern_detected \
    --domain self_learning \
    --learnings '["[PATTERN_DESCRIPTION]"]' \
    --notes "[Evidence]"
```

---

## STEP 5 — Run Reflection

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/reflect.py --brief
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/reflect.py
```

If reflection detects actionable patterns AND `learning.auto_adjust_enabled` is true in strategy.json:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/reflect.py --apply
```

Otherwise, report the suggestions but don't apply automatically.

---

## STEP 6 — Session Self-Assessment

Review what was accomplished. Be brutally honest.

```
NUCLEAR WRAP — Session [N] — [date]

SCAN PROGRESS: [reviewed]/[total] ([pct]%) | [remaining] posts left
VERDICT BREAKDOWN: BUILD:[B] ADAPT:[A] REF:[R] SKIP:[S] FAST-SKIP:[FS]
SIGNAL RATE: [BUILD+ADAPT / reviewed as %]

WINS:
- [What moved the needle — specific BUILD/ADAPT findings, tools discovered]

LOSSES:
- [Token waste, false positives, missed opportunities]

TOP FINDINGS THIS SESSION:
1. [Most impactful BUILD or ADAPT with one-line summary]
2. [Second most impactful]
3. [Third most impactful]

SELF-LEARNING:
- Learnings captured: [N]
- Patterns detected: [N]
- Strategy adjustments: [applied/suggested/none]

GRADE: [A/B/C/D]
- A = high signal rate, multiple BUILDs, efficient token use
- B = good progress, some useful findings
- C = mostly SKIPs, low signal
- D = wasted tokens, bugs, or no progress

ONE THING next nuclear session must do differently:
[specific, actionable]
```

### Log session outcome to journal

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/journal.py log session_outcome \
    --session [SESSION_NUMBER] \
    --domain nuclear_scan \
    --outcome [success/partial/failure] \
    --metrics '{"grade": "[A/B/C/D]", "signal_rate": [RATE], "learnings_captured": [N]}' \
    --notes "[ONE_THING from above]"
```

---

## STEP 7 — Update SESSION_STATE.md

Update `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md`:
- Increment session number
- Date
- What was completed (nuclear scan batch details)
- Nuclear progress status (N/M reviewed)
- Self-learning system status
- What's next (specific: continue scan, or implement top BUILD)

---

## STEP 8 — Append to CHANGELOG.md

Append (NEVER overwrite) to CHANGELOG.md:

```
## Session [N] — [YYYY-MM-DD]

**What changed:**
- Nuclear scan: [N] posts reviewed ([B] BUILD, [A] ADAPT, [R] REF, [S] SKIP)
- Self-learning system created (journal.py, reflect.py, strategy.json, [N] tests)
- [Any other changes]

**Why:**
- Systematic community intelligence gathering for CCA frontiers
- Self-learning infrastructure for cross-session pattern detection

**Tests:** [N]/[N] passing

**Lessons:**
- [From self-assessment ONE THING above]

---
```

---

## STEP 9 — Capture Learnings

Review the session for LEARNINGS.md-worthy patterns (severity-tracked).

Nuclear-scan-specific patterns to watch for:
- Score thresholds that predict BUILD vs SKIP
- Subreddits that yield higher signal
- Post types that waste tokens
- Keywords that predict useful content
- Self-learning infrastructure patterns

Follow the severity escalation protocol from /cca-wrap.

### Auto-escalate learnings to rules

Scan LEARNINGS.md for any entry with **Severity: 3** and **Count: 3+** that does NOT already
have a corresponding rule file in `.claude/rules/`. For each qualifying entry:

1. Create a rule file at `.claude/rules/[topic].md` with the pattern and fix
2. Append to the LEARNINGS.md entry: `- **Promoted:** [date] -> .claude/rules/[topic].md`

Scan for any entry with **Severity: 2** and **Count: 2+** that is NOT already referenced in
the project CLAUDE.md. For each qualifying entry:

1. Add a bullet to the "Known Gotchas" section of CLAUDE.md
2. Append to the LEARNINGS.md entry: `- **Promoted:** [date] -> CLAUDE.md Known Gotchas`

If no entries qualify: skip silently. Do not fabricate promotions.

### Check for recurring session-level anti-patterns

Review the last 3 session entries in CHANGELOG.md. If you see the same type of issue
appearing in 2+ consecutive sessions (e.g., "forgot to commit", "low signal rate",
"token waste on same post type"), output:

```
RECURRING ANTI-PATTERN DETECTED: [pattern]
Suggestion: [specific fix — new rule, workflow change, or automation]
```

If no recurring patterns: skip silently.

---

## STEP 10 — Update PROJECT_INDEX.md

If new files were created (self-learning/*, new commands), add them to PROJECT_INDEX.md.
Update test counts.

---

## STEP 11 — Stage and Display

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && git status && git diff --stat
```

Do NOT commit automatically. Let the user review.

---

## STEP 12 — Resume Prompt

```
RESUME PROMPT (copy-paste into next CCA session):
---
Run /cca-init. Last session was [N] on [date].
Nuclear scan: [reviewed]/[total] reviewed. [remaining] posts left.
[top BUILD candidate summary].
Self-learning: [N] journal entries, strategy v[V].
Run /cca-nuclear to continue scan or /cca-auto to implement top BUILD.
Tests: [N]/[N] passing. Git: [clean/uncommitted changes].
---
```

---

## STEP 13 — Nuclear Completion Check

If the entire queue is processed (0 remaining):

```
NUCLEAR SCAN COMPLETE.

Total: [N] posts reviewed across [S] sessions
BUILD candidates: [list with scores]
Top ADAPT patterns: [list]
Signal rate: [%]

Self-learning journal: [N] entries, [L] learnings captured
Strategy version: v[V]

Next: Run /cca-auto to implement the top BUILD candidate.
Or: Run /cca-nuclear on a different subreddit for fresh signal.
```

---

## Rules (NON-NEGOTIABLE)

- Fully autonomous — execute every step without asking
- Tests MUST pass before updating any docs
- CHANGELOG.md is append-only
- FINDINGS_LOG.md is append-only
- Self-assessment must be honest — do not inflate grades
- Journal entries must have SPECIFIC learnings, not vague summaries
- Resume prompt is critical — never skip it
- Do not push to remote
- End EVERY response with `Advancement tip: ...`
- **NEVER expose** API keys, account balances, trade data, or financial info

## CRITICAL: End-of-Wrap Behavior

After outputting the final report/resume prompt, your wrap is COMPLETE.

1. Output one final line: `Nuclear wrap complete. Waiting for instructions.`
2. **STOP RESPONDING.** Do not output any further text.
3. Do NOT say "done", "exit", "safe to close", "acknowledged", or any other sign-off.
4. Do NOT respond to your own completion — there is no further step.
5. If the user says nothing, say nothing. Wait silently for the next user message.
