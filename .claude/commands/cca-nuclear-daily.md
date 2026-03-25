# /cca-nuclear-daily — Daily Hot+Rising Intelligence Scan

Lightweight daily scan of hot and rising posts across key subreddits.
Designed for daily use — faster and cheaper than full /cca-nuclear.
Feeds the self-learning system with fresh signals every day.

No questions needed. Just type `/cca-nuclear-daily` and walk away.

## How It Works

1. Fetches **hot** posts (trending now) + **rising** posts (gaining traction) from key subs
2. Deduplicates against FINDINGS_LOG.md (skips already-reviewed posts)
3. Classifies each post (NEEDLE/MAYBE/HAY)
4. Reviews top NEEDLEs with full /cca-review treatment
5. Logs findings and feeds self-learning journal

## Phase 0 — Discovery (find new subreddits we're not tracking)

Run the subreddit discoverer to check for new relevant subs across all domains:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/subreddit_discoverer.py --top 5 --json
```

Review the top candidates. If any score >= 70 and have > 5K subscribers:
1. Note them in the daily briefing output
2. Optionally add to profiles.py for future scans (requires code change — log as TODO)

This step uses Reddit's public API — no auth or tokens needed. Skip if rate-limited.

## Phase 1 — Fetch & Classify

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/autonomous_scanner.py daily --json
```

Parse the JSON output. It contains one ScanResult per subreddit with:
- `report`: summary stats (posts_fetched, needles, maybes, hay)
- `needles`: posts to deep-read
- `maybes`: optional secondary reads
- `hay`: skip

### Custom subreddits

Default scans: r/ClaudeCode, r/ClaudeAI, r/vibecoding

To scan different subs:
```bash
python3 .../autonomous_scanner.py daily --subs "ClaudeCode,algotrading,Polymarket" --json
```

To adjust limits:
```bash
python3 .../autonomous_scanner.py daily --hot-limit 40 --rising-limit 15 --json
```

## Phase 2 — Review NEEDLEs

For each NEEDLE post (up to 15 total across all subs):

1. Read using reddit_reader.py:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "<permalink>"
```

2. Deliver full /cca-review verdict:
   - Frontier mapping (which of the 5 frontiers does this touch?)
   - Rat poison check
   - BUILD / ADAPT / REFERENCE / REFERENCE-PERSONAL / SKIP

3. Log to FINDINGS_LOG.md (append)

4. Follow links to GitHub repos or tools mentioned in comments

**Use parallel review agents** (S2 strategy): Launch up to 5 review agents simultaneously.

## Phase 3 — Self-Learning

After all reviews:

1. Log a `nuclear_batch` event to the self-learning journal:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/journal.py log nuclear_batch \
    --session $SESSION_NUM --domain nuclear_scan \
    --metrics '{"posts_reviewed": N, "build": B, "adapt": A, "reference": R, "skip": S}' \
    --learnings '["key insight 1", "key insight 2"]'
```

2. Run reflection to check for pattern changes:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/reflect.py --brief
```

3. If APF has improved, note it. If APF dropped, note why.

## Phase 4 — Summary

Output a concise daily briefing:

```
DAILY SCAN — [date]

Subs scanned: [list]
Posts fetched: [total] | New: [deduped] | NEEDLEs: [N]
Reviews completed: [N]
Verdicts: BUILD [B] | ADAPT [A] | REFERENCE [R] | SKIP [S]
APF impact: [up/down/stable]

Top finds:
1. [title] — [verdict] — [one-line summary]
2. ...

Self-learning: [any pattern changes or strategy updates]
```

## Rules

- Maximum 15 NEEDLE reviews per daily scan (token budget)
- Always dedup against FINDINGS_LOG before reviewing
- Use parallel agents for batch reviews (S2)
- Log everything to self-learning journal
- This is a DAILY command — run it once per day for consistent intelligence intake
- For deep-dive sessions (100+ posts), use /cca-nuclear instead
