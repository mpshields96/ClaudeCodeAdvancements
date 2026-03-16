# reddit-intelligence — Module Rules

## What This Module Does
Provides tools for systematically scanning, reading, and analyzing Reddit posts relevant to the ClaudeCodeAdvancements project's five frontiers.

## Components
- `reddit_reader.py` — Canonical URL reader for all Reddit URLs (fetches post + all comments)
- `nuclear_fetcher.py` — Batch fetcher + classifier for deep-dive scanning (NEEDLE/MAYBE/HAY)
- `commands/` — Slash commands for ri-scan, ri-read, ri-loop

## Rules
- reddit_reader.py is the canonical URL reader — use it for ALL Reddit URLs
- FINDINGS_LOG.md is append-only — never truncate or reorder entries
- Verdicts: BUILD / ADAPT / REFERENCE / REFERENCE-PERSONAL / SKIP
- REFERENCE-PERSONAL is valid for tools useful to Matthew personally
- Read ALL comments — best insights are often buried 3-4 levels deep
- Follow links in comments to GitHub repos and implementations
- Nuclear fetcher classifies with zero LLM tokens (title keyword matching)
