# self-learning — Module Rules

## What This Module Does
Provides a structured self-learning system that logs session outcomes, detects patterns,
distills actionable strategies, and tracks improvement over time. Adapted from the YoYo
self-evolving agent pattern — the goal is to get smarter every session, not just log events.

## Components
- `journal.py` — Structured append-only event log (JSONL format)
- `journal.jsonl` — Persistent event log (append-only, never truncate)
- `reflect.py` — Pattern detection + strategy recommendations
- `strategy.json` — Tunable parameters (thresholds, filters, confidence)
- `SKILLBOOK.md` — **Distilled actionable strategies** (the playbook, not the journal)
- `improver.py` — Self-improvement loop engine
- `trace_analyzer.py` — Session trace analysis

## The Hard Metric: APF (Actionable Per Find)

**APF = (BUILD + ADAPT findings) / total findings * 100**

This is CCA's equivalent of Kalshi's net profit. Every session should either maintain
or improve APF. If APF drops, we're scanning noise. If APF rises, we're getting smarter
about what to read and what to skip.

Current: **32.1%** | Target: **40%**

## Skillbook vs Journal

| | Journal (journal.jsonl) | Skillbook (SKILLBOOK.md) |
|---|---|---|
| Format | Raw events, timestamped | Distilled strategies with confidence scores |
| Purpose | Audit trail, pattern detection input | Context injection, session smarts |
| Mutability | Append-only | Strategies promoted/demoted/archived |
| Survives compaction? | No (too verbose) | Yes (terse directives) |
| Read when? | By reflect.py at wrap time | By Claude at session start |

## Rules
- Journal is append-only — never truncate or rewrite entries
- Skillbook strategies require evidence from 2+ sessions before confidence >= 50
- Strategy changes require minimum sample size (N=20) before applying
- All strategy changes must be logged with reason (no silent drift)
- NEVER expose API keys, account balances, trade data, or financial info
- Profit is the only objective for trading strategies — never accept break-even
- Pattern detection runs on session wrap, not during active work
- **APF must be reported at every session wrap** — it's the scoreboard
- Strategies at confidence < 20 get archived, not deleted (we learn from failures too)
