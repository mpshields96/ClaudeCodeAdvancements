# /cca-wrap — ClaudeCodeAdvancements Session Wrap-Up

Fully autonomous — no confirmation needed. See WRAP_REFERENCE.md for detailed explanations.

## CRITICAL PATH (never skip — S200 fix)

If context is low, run ONLY these steps (skip all OPTIONAL):

1. **Step 1** — Run tests
2. **Steps 3-5** — Batch doc update
3. **Step 6 SLIM** — batch_wrap_learning.py
4. **Step 9** — Resume prompt + SESSION_RESUME.md
5. **Step 10** — Autoloop trigger (FINAL)

OPTIONAL: 0.5, 1.5, 1.7, 1.8, 2, 2.5, 6b-6h, 7, 7.5, 8, 8.5, 8.9, 9.5
**NEVER silently skip steps.** State what you skipped and why.

---

## Step 0.5 — Start wrap timer (OPTIONAL)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 session_timer.py mark wrap:tests test
```

---

## Step 1 — Run all tests

ALL must pass before any docs get updated.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 parallel_test_runner.py --workers 8
```

---

## Step 1.5 — Senior dev review (OPTIONAL, skip in autoloop)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
CHANGED=$(git diff --name-only HEAD~$(git log --oneline --since="4 hours ago" | wc -l | tr -d ' ') 2>/dev/null | grep '\.py$' | grep -v test_ | grep -v __pycache__ | head -5)
[ -n "$CHANGED" ] && for f in $CHANGED; do echo "=== Senior Review: $f ===" && python3 agent-guard/senior_review.py "$f" 2>/dev/null || echo "  (skipped)"; done
```

---

## Step 1.7 — APF checkpoint (OPTIONAL)

```bash
python3 self-learning/hit_rate_tracker.py report 2>/dev/null || echo "hit_rate_tracker not available"
```

---

## Step 1.8 — APF session snapshot (OPTIONAL)

```bash
python3 self-learning/apf_session_tracker.py snapshot S[SESSION_NUMBER] 2>/dev/null || true
python3 self-learning/apf_session_tracker.py status 2>/dev/null || true
```

---

## Step 2 — Self-assessment (OPTIONAL but recommended)

Output this block with honest grading (A/B/C/D):

```
SESSION WRAP — [session number] — [date]
WINS: [concrete deliverables]
LOSSES: [what wasted time]
GRADE: [A/B/C/D]
ONE THING next session must do differently: [actionable]
```

---

## Step 2.5 — Mark doc update timer (OPTIONAL)

```bash
python3 session_timer.py mark wrap:docs doc
```

---

## Steps 3-5 — Batch doc update

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 doc_updater.py \
    --session [SESSION_NUMBER] --grade [GRADE] \
    --summary "[one-sentence summary]" \
    --wins "[WIN_1]" "[WIN_2]" \
    --losses "[LOSS_1]" "[LOSS_2]" \
    --next "[NEXT_1]" "[NEXT_2]" \
    --tests [TOTAL_TEST_COUNT] --suites [TOTAL_SUITES] \
    --date [YYYY-MM-DD]
```

Add `--learnings-json` or `--new-files` only if applicable.

**ALSO update TODAYS_TASKS.md manually** — mark items `[DONE SN]`, never remove items.

---

## Step 6 — Self-Learning

```bash
python3 session_timer.py mark wrap:self_learning wrap
```

### 6a — Batch write (journal + assessment + tips)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 batch_wrap_learning.py \
    --session [SESSION_NUMBER] --grade [GRADE] \
    --wins "[WIN_1]" "[WIN_2]" \
    --losses "[LOSS_1]" "[LOSS_2]" \
    --summary "[one-sentence summary]" \
    --domain general \
    --tests-added [TESTS_ADDED] --tests-total [TOTAL_TESTS] \
    --tips "[TIP_1]" "[TIP_2]"
```

### 6b-6h — Batch analysis (reflect, escalate, apply, anti-patterns, skillbook, sentinel, validate)

Run if context is under 50%. Otherwise defer to next init.

```bash
python3 batch_wrap_analysis.py --session [SESSION_NUMBER] --grade [GRADE] \
    --wins "[WIN_1]" "[WIN_2]" --losses "[LOSS_1]" "[LOSS_2]"
```

Output includes SESSION LEARNING summary. If PROMOTE TO RULE candidates found, create rule files manually.

---

## Step 7 — Update PROJECT_INDEX.md

Handled by doc_updater.py (Steps 3-5). Only edit manually if batch missed something.

---

## Step 7.5 — Cross-chat comms (Kalshi bot, CONDITIONAL)

Skip check — if none of these are true, skip the entire step:
- Session touched files in polymarket-bot/ or kalshi-related code
- Session produced trading research, self-learning improvements, or guard changes
- There are pending POLYBOT_TO_CCA.md requests to answer
- Session built infrastructure the Kalshi bot benefits from

If skipping: log "Cross-chat: no Kalshi-relevant work this session." and move on.

Otherwise:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
grep "^## \[" ~/.claude/cross-chat/CCA_TO_POLYBOT.md 2>/dev/null | tail -1 || echo "No deliveries"
grep -c "Status: PENDING" ~/.claude/cross-chat/POLYBOT_TO_CCA.md 2>/dev/null || echo "0"
```

Append update to `~/.claude/cross-chat/CCA_TO_POLYBOT.md` if relevant work was done.

---

## Step 8 — Stage and display diff (OPTIONAL)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && git status && git diff --stat
```

---

## Step 8.5 — Session-end notification (OPTIONAL)

```bash
python3 context-monitor/session_notifier.py wrap --auto --session S[SESSION_NUMBER] --grade [GRADE]
```

---

## Step 8.9 — Deregister from orchestrator (OPTIONAL)

```bash
CCA_ROLE="${CCA_CHAT_ID:-desktop}"
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/session_orchestrator.py deregister "$CCA_ROLE"
```

---

## Step 9 — Resume prompt + SESSION_RESUME.md

Output a detailed resume prompt, then write to disk:

```
RESUME PROMPT (copy-paste into next CCA session):
---
Run /cca-init. Last session was [N] on [date].
[What was completed.] [What's next from TODAYS_TASKS.md.]
Tests: [N]/[N] passing. Git: [clean/uncommitted].
---
```

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/resume_generator.py --force
```

---

## Step 9.5 — Finalize session timer (OPTIONAL)

```bash
python3 session_timer.py finish
python3 session_timer.py history
```

---

## Step 10 — Autoloop trigger (FINAL)

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
python3 autoloop_trigger.py
```

Skip if `CCA_NO_AUTOLOOP=1`. If trigger fails, print error but do NOT retry.

---

## Rules

- Tests MUST pass before updating docs
- CHANGELOG.md is append-only
- Self-assessment must be honest
- Resume prompt is the most important output
- Do not push to remote
- Step 10 runs LAST

After Step 10: output `Session [N] wrap complete. Autoloop triggered.` then **STOP RESPONDING.**
No further text. No sign-offs. No "done." The wrap is finished.
