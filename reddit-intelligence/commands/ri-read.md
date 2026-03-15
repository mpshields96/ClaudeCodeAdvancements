# /reddit-intel:ri-read — Read Any Reddit URL

Read a specific Reddit post (with all comments) or browse a subreddit's hot posts.
Uses the Reddit JSON API via Python — no Chrome dependency, no safety blocks.

**Works for:** post URLs, subreddit names, old.reddit.com and www.reddit.com links.

---

## Usage

```
/reddit-intel:ri-read r/ClaudeAI
/reddit-intel:ri-read r/ClaudeCode top 10
/reddit-intel:ri-read https://www.reddit.com/r/ClaudeAI/comments/abc123/title/
/reddit-intel:ri-read https://old.reddit.com/r/vibecoding/comments/xyz456/
```

---

## STEP 1 — Run the Python reader

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "[INPUT]"
```

Where `[INPUT]` is the URL or subreddit name exactly as given by the user.

**For subreddit with sort and limit:**
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "r/ClaudeAI" top 10
```

Supported sorts: `hot` (default), `new`, `top`, `rising`
Default limit: 25 posts for subreddit listings.

---

## STEP 2 — Present the output

For a **subreddit listing**, present:
- The header line (subreddit name, sort, count)
- All posts with title, author, score, comment count, permalink
- Offer to read any individual post by its number or URL

For a **post with comments**, present:
- Full metadata block (URL, title, author, score, upvote %, comment count, flair)
- Full post body (or link URL for link posts)
- All comments with author, score, and nesting preserved
- Do NOT truncate comments unless the user asks for a summary

---

## Error handling

**HTTP error (403/404/410):** Subreddit may be private, banned, or quarantined. Report to user.
**Network error:** Report connection issue. User may need to check connectivity.
**Parse error:** Reddit API returned unexpected format. Report raw error.

---

## Target subreddits (pre-verified working)

```
r/ClaudeCode       r/ClaudeAI         r/Claude
r/algobetting      r/algotrading      r/vibecoding
r/AI_agents        r/Kalshi           r/polymarket_bets
r/PredictionMarkets
```

All 10 confirmed working as of 2026-03-10 (live-tested with Python JSON API).

---

## Security contract

- Read-only. No authentication, no login, no write operations.
- No data transmitted off-machine beyond the Reddit API request.
- No cookies, no OAuth. Purely public data via User-Agent header.
- See SECURITY.md for full constraints.
