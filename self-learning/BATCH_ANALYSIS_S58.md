# Batch Trace Analysis — Session 58 (2026-03-19)

## Summary

| Metric | Value |
|--------|-------|
| Sessions analyzed | 50 |
| Parse errors | 0 |
| Score: avg / median / min / max | 72.6 / 75 / 15 / 100 |
| Distribution | 22 excellent, 19 good, 7 poor, 2 critical |
| Read waste avg / max | 35% / 83% |
| Retry hotspot #1 | PROJECT_INDEX.md (32/50 sessions, 64%) |
| Retry hotspot #2 | SESSION_STATE.md (17/50 sessions, 34%) |

## Score Distribution

- Excellent (80+): 22 sessions (44%)
- Good (60-79): 19 sessions (38%)
- Poor (40-59): 7 sessions (14%)
- Critical (<40): 2 sessions (4%)

## Critical Finding: PROJECT_INDEX.md Edit Retry Pattern

**32 out of 50 sessions** (64%) have Edit retry loops on PROJECT_INDEX.md.

- 17 minor (3-4 retries), 11 major (5-7), 4 critical (8+)
- Average retry count: 4.9 per instance
- Estimated wasted tool calls: ~157 across all sessions

**Root cause**: Edit tool requires exact string matching. PROJECT_INDEX.md contains
structured tables with alignment-sensitive whitespace. When the old_string doesn't
match exactly (tabs, trailing spaces, line breaks), the Edit fails and Claude retries
with slightly different strings.

**The CLAUDE.md gotcha** ("Always Read PROJECT_INDEX.md before editing") helps but
doesn't eliminate the problem — retries still happen in 64% of sessions.

SESSION_STATE.md has the same pattern at 34% frequency.

## Read Waste Analysis

Average 35% of non-orientation reads are never referenced in the next 20 entries.

Worst offenders:
- 83% waste in session 39abaa34 (1 commit, likely exploration-heavy)
- 75% waste in session 05d59e2a (0 commits, setup/research session)

Read waste above 50% correlates with low commit counts (exploration sessions).

## Trend (by date)

March 15-16: avg score ~73 (early sessions, learning curve)
March 17: avg score ~82 (productive building phase)
March 18: avg score ~78 (high commit output, moderate waste)
March 19: avg score ~74 (S57-58 sessions, stable)

No significant degradation trend. Quality is stable.

## Actionable Recommendations

1. **Fix PROJECT_INDEX.md edits** — Use Write (full rewrite) instead of Edit for
   structured table files, or build a helper that reads the file immediately before
   each Edit call. This alone would improve ~32 sessions' scores.

2. **Reduce read waste in exploration sessions** — When scanning/researching, batch
   reads and reference them promptly. 35% avg waste = ~1 in 3 reads is thrown away.

3. **Investigate 2 critical sessions** (514ccc66 score=15, e3f28b53 score=25) —
   Both had severe retry storms on structured doc files.

## How This Was Generated

```bash
python3 self-learning/batch_report.py --json
```

Raw data from TraceAnalyzer running against 50 JSONL transcripts in
`~/.claude/projects/-Users-matthewshields-Projects-ClaudeCodeAdvancements/`
