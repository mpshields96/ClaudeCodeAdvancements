# self-learning — Module Rules

## What This Module Does
Provides a structured self-learning system that logs session outcomes, detects patterns, and recommends strategy adjustments. Adapted from the YoYo self-evolving agent pattern.

## Components
- `journal.py` — Structured append-only event log (JSONL format)
- `reflect.py` — Pattern detection + strategy recommendations
- `strategy.json` — Tunable parameters (thresholds, filters, confidence)
- `journal.jsonl` — Persistent event log (append-only, never truncate)

## Rules
- Journal is append-only — never truncate or rewrite entries
- Strategy changes require minimum sample size (N=20) before applying
- All strategy changes must be logged with reason (no silent drift)
- NEVER expose API keys, account balances, trade data, or financial info
- Profit is the only objective for trading strategies — never accept break-even
- Pattern detection runs on session wrap, not during active work
