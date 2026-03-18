# /cca-nuclear-github — GitHub Repository Intelligence Scan

Autonomous scan of GitHub repos relevant to CCA frontiers.
Evaluates repos by stars, activity, license, relevance, and safety.
No questions needed. Just type `/cca-nuclear-github` and walk away.

## Phase 1 — Search & Evaluate

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/github_scanner.py scan --all --json
```

This runs 10 built-in search queries against the GitHub API:
- claude code mcp server
- claude hooks agent
- context window management llm
- persistent memory ai agent
- multi-agent coordination
- prediction market bot api
- trading bot python backtesting
- developer tools cli ai
- spec driven development
- token usage tracking llm

Each repo is scored 0-100 (stars + activity + license + relevance + age).
Repos scoring >= 50 get EVALUATE verdict. Below 50 = SKIP.
Scam/dangerous repos are BLOCKED.

All results are deduped against `github_evaluations.jsonl` — already-evaluated repos are skipped.

### Custom query mode

```bash
python3 .../github_scanner.py scan "your search terms" --json
```

### Single repo evaluation

```bash
python3 .../github_scanner.py fetch owner/repo
```

## Phase 2 — Deep Review EVALUATE Repos

For each repo with verdict EVALUATE (up to 10):

1. Read the repo's README via WebFetch:
   `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md`

2. Check for CLAUDE.md (if it exists, this is a Claude Code tool):
   `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/CLAUDE.md`

3. Deliver full /cca-review verdict:
   - Frontier mapping (which of the 5 frontiers + trading/personal)
   - Rat poison check
   - BUILD / ADAPT / REFERENCE / REFERENCE-PERSONAL / SKIP

4. Log to FINDINGS_LOG.md (append)

**Use parallel review agents** (S2 strategy): Launch up to 5 review agents simultaneously.

## Phase 3 — Self-Learning

After all reviews:

1. Log a `nuclear_batch` event:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/journal.py log nuclear_batch \
    --session $SESSION_NUM --domain nuclear_scan \
    --metrics '{"repos_evaluated": N, "evaluate": E, "skip": S, "blocked": B}' \
    --learnings '["key insight 1", "key insight 2"]'
```

2. Run reflection:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/reflect.py --brief
```

## Phase 4 — Summary

```
GITHUB SCAN — [date]

Queries run: [N]
Repos found: [total] | New: [deduped] | EVALUATE: [N]
Deep reviews: [N]
Verdicts: BUILD [B] | ADAPT [A] | REFERENCE [R] | SKIP [S]

Top repos:
1. [owner/repo] ([stars] stars) — [verdict] — [one-line summary]
2. ...
```

## Rules

- Maximum 10 deep reviews per scan (token budget)
- Always dedup against github_evaluations.jsonl before reviewing
- Never git clone repos into CCA directory (safety)
- Never install dependencies from scanned repos (safety)
- Read source code via raw.githubusercontent.com only
- Use parallel agents for batch reviews (S2)
- Log everything to self-learning journal
