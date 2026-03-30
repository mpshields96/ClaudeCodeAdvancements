# Wrap Reference — Full Step Documentation

This is the detailed reference for `/cca-wrap`. The wrap command itself (`cca-wrap.md`)
contains only the slim execution instructions. This file has the "why" behind each step.

---

## Step 1.5 — Senior Dev Review

Only run in interactive sessions or when Matthew explicitly requests a review.
Skip during autoloop sessions. Reviews changed `.py` files (non-test) from the last 4 hours
using `agent-guard/senior_review.py`.

## Step 1.7 — APF Checkpoint

APF = Actionable Post Frequency = (BUILD + ADAPT) / total findings * 100.
Target: 40%. Baseline: 22.7% (S102). Reads FINDINGS_LOG, no API calls.
Compare to last session's APF — note changes in Step 2 wins/losses.

## Step 1.8 — APF Session Snapshot

Appends one line to `~/.cca-apf-snapshots.jsonl` (append-only). The status command
shows delta vs previous session — include in Step 2 wins/losses.

## Step 2 — Self-Assessment Grading

Grade scale:
- A = shipped working code with tests, no regressions
- B = made progress, minor issues
- C = spent most of the time on overhead or debugging
- D = net negative — broke things or wasted the session

## Steps 3-5 — Doc Updater Details

`doc_updater.py` handles:
- SESSION_STATE.md: new state at top, old demoted to Previous
- CHANGELOG.md: append-only new session entry
- LEARNINGS.md: append new patterns (skipped if none)
- PROJECT_INDEX.md: add new file entries via `--new-files` (skipped if none)

Optional flags:
- `--learnings-json '[{"title": "...", "severity": 1, "anti_pattern": "...", "fix": "..."}]'`
- `--new-files "file1.py" "file2.py"`

Severity escalation: if a learning recurred, manually bump Count in LEARNINGS.md after batch.

## Step 6 — Self-Learning Details

### FULL MODE Steps (6a-6a.7)

These are all handled by `batch_wrap_learning.py` in slim mode. Only use individual
commands if batch_wrap_learning.py fails or you need to debug a specific step.

- **6a**: `journal.py log session_outcome` — grade mapping: A/B=success, C=partial, D=failure
- **6a.1**: `session_outcome_tracker.py auto-record` — parses SESSION_STATE for planned/completed
- **6a.5**: `journal.py log win/pain` — one entry per win/loss bullet from Step 2
  - Valid domains: nuclear_scan, memory_system, spec_system, context_monitor, agent_guard,
    usage_dashboard, reddit_intelligence, self_learning, general
- **6a.6**: `wrap_tracker.py log` — persistent record of session quality trends
- **6a.7**: `tip_tracker.py add` — persists advancement tips from conversation

### Analysis Steps (6b-6h)

These are all handled by `batch_wrap_analysis.py`. Details:

- **6b**: `reflect.py --brief` — pattern detection from journal entries
- **6c**: Auto-escalate: scan LEARNINGS.md for Severity 3 + Count 3+ → create rule files;
  Severity 2 + Count 2+ → add to CLAUDE.md Known Gotchas
- **6d**: `reflect.py --apply` — apply strategy parameter tweaks to strategy.json
- **6e**: Recurring anti-patterns: compare last 3 CHANGELOG sessions for repeated issues
- **6f**: Skillbook evolution: bump/drop strategy confidence based on session evidence
  (validated +5, contradicted -10, archived below 20)
- **6g.5**: `improver.py evolve` — sentinel adaptation (mutations, cross-pollination, gaps)
- **6h**: `validate_strategies.py --brief` — strategy health check vs journal evidence

## Step 7.5 — Cross-Chat Details

**What to include in CCA_TO_POLYBOT.md updates:**
- Self-learning improvements that affect Kalshi bot
- Research findings relevant to trading
- Tools or infrastructure the bot benefits from
- Questions about bot performance or strategy needs
- Status of pending POLYBOT_TO_CCA.md requests

**Format:**
```
## [YYYY-MM-DD HH:MM UTC] — UPDATE [N] — Session S[N] Summary
[What CCA built/improved this session that's relevant]
Status: DELIVERED
```

## Step 9 — Resume Prompt Details

The resume prompt must be extremely detailed (S122 format is gold standard):
file paths, LOC, test counts, gotchas, exact next steps.

`resume_generator.py --force` writes SESSION_RESUME.md from current SESSION_STATE.md.
The autoloop watches this file's mtime to detect session completion.

## Step 10 — Autoloop Details

autoloop_trigger.py workflow:
1. Reads SESSION_RESUME.md
2. Verifies Code tab is active in Claude.app
3. Cmd+N for new session
4. Pastes resume prompt
5. Cmd+Return to send

If trigger fails: print error, do NOT retry. Wrap is still complete.
Skip if `--no-autoloop` or `CCA_NO_AUTOLOOP=1` is set.
