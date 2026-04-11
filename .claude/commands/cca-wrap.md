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

`--tips` captures learning candidates for the trackers. It does NOT require ending the user-facing response with suggestion-only advice. If a tip was implemented or codified during the session, report it in the wrap summary as `Advancement follow-through: ...`.

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

## Step 7.5 — Cross-chat comms (Kalshi bot + Codex, ALWAYS RUN)

Run every wrap — no skipping. This keeps CCA_STATUS.md current so the Kalshi chat
knows what CCA built this session without waiting for Matthew to relay it.

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements

# Summarize what CCA did this session for the Kalshi chat
SESSION_FOCUS="[one-line summary of what was built/researched this session]"
python3 cross_chat_board.py update "$SESSION_FOCUS"

# If Kalshi-relevant work was done (trading research, infra, guard changes):
# append a delivery to CCA_TO_POLYBOT.md and set the delivery flag
python3 cross_chat_board.py board  # show full state before wrapping
```

**Delivery flag**: if you wrote to CCA_TO_POLYBOT.md this session, also run:
```bash
python3 cross_chat_board.py flag-delivery
```
This creates `~/.claude/cross-chat/.new_cca_delivery` so the Kalshi chat detects
the new delivery on its next cycle (not just every 3rd cycle).

If no Kalshi-relevant work: still run `python3 cross_chat_board.py update "no Kalshi work this session"`.
Never skip this step — CCA_STATUS.md staleness is exactly why comms break down.

**Codex comms (ALWAYS RUN if leagues6-companion work was done):**

Append a wrap summary to the canonical CCA-local `CLAUDE_TO_CODEX.md` bridge so
Codex knows what was built and can pick up the next task without manual relay
from Matthew.

```bash
cat >> /Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md << CODEX_EOF

## [$(date -u '+%Y-%m-%d %H:%M') UTC] — WRAP — S[SESSION_NUMBER] complete
**Status:** FYI
**Summary:** [one-line session summary]
**Wins:** [list key deliverables]
**Gate:** [N]/[N] tests pass, GATE: PASSED/FAILED
**Next for Codex:** [specific next task or "check TODAYS_TASKS.md"]
CODEX_EOF
```

If Codex QA was requested this session, flag it explicitly so Codex prioritises it.

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
