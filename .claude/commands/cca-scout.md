# /cca-scout — Find High-Signal Posts Across Claude Subreddits

Scan multiple subreddits for objectively beneficial posts from the past month.
Uses the Python reddit_reader.py (JSON API — no Chrome needed). Fully autonomous.

---

## Step 1 — Pull top posts from each subreddit

Run these commands to get the top posts from the past month:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "r/ClaudeCode" top 50
```

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "r/ClaudeAI" top 50
```

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "r/vibecoding" top 25
```

Note: Reddit's "top" defaults to ~month range for active subreddits. This gives
broad coverage without needing time filtering.

---

## Step 2 — Filter for high-signal posts

From the combined listings, select posts that match ALL of these criteria:

**Include if:**
- Score >= 50 (community validated)
- Title mentions: tool, built, workflow, tip, trick, hook, skill, command,
  MCP, memory, context, token, cost, agent, automation, statusline, CLI,
  template, framework, best practice, open source, github
- OR: Comments >= 30 (high engagement even if score is moderate)

**Exclude (rat poison):**
- Memes, humor, screenshots of funny Claude responses
- "Claude is amazing" / "Claude sucks" opinion posts
- Model comparison debates (GPT vs Claude)
- Anthropic company news, funding, politics
- "I made $X with AI" hype
- Duplicate topics already in FINDINGS_LOG.md

---

## Step 3 — Check against existing reviews

Read the current findings log:

```bash
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/FINDINGS_LOG.md
```

Remove any posts whose URLs already appear in the log. We don't re-review.

---

## Step 4 — Present the shortlist

Output a numbered list of posts worth reviewing:

```
CCA SCOUT — [date] — [N] new high-signal posts found

Already reviewed: [N] posts skipped (in FINDINGS_LOG.md)

NEW FINDS:

1. "[title]" (r/subreddit, [score] pts, [N] comments)
   URL: [full URL]
   Why: [1 sentence — what makes this worth reviewing]

2. ...

Which ones do you want me to /cca-review? (numbers, "all", or "skip")
```

---

## Step 5 — Review on request

If the user says "all" — run /cca-review on each one sequentially.
If the user gives numbers — review only those.
If the user says "skip" — done.

Each review follows the full /cca-review workflow (read post + comments,
chase GitHub links, frontier mapping, verdict, log to FINDINGS_LOG.md).

---

## Rules

- Fully autonomous through Step 4 — only pause for user selection
- Never re-review a URL already in FINDINGS_LOG.md
- Quality over quantity — 5-10 posts is ideal, not 50
- Reddit JSON API only — no Chrome, no Playwright
- If reddit_reader.py fails (rate limited), wait 30 seconds and retry once
