# /browse-url — Open and Read Any URL in Chrome

Navigate to the URL in the user's message and return the full content.

Works for Reddit posts, subreddit listings, GitHub repos/issues/PRs, articles,
and general URLs.

---

## STEP 1 — Detect URL type

Check if the URL contains `reddit.com` or starts with `r/`.

- **Reddit URL or subreddit** → use Python reader (Step 2A)
- **Any other URL** → use WebFetch (Step 2B)

---

## Step 2A — Reddit (Python JSON API)

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "[URL_OR_SUBREDDIT]"
```

This works for:
- Full post URLs: `https://www.reddit.com/r/ClaudeAI/comments/abc123/...`
- Old reddit URLs: `https://old.reddit.com/r/ClaudeAI/comments/abc123/...`
- Subreddit listings: `r/ClaudeAI` or `r/ClaudeAI top 10`

Returns: full post body + all comments with author/score/nesting, or post listing.

**Why not Chrome for Reddit:**
Chrome safety restrictions block JavaScript execution on reddit.com tabs.
The Python JSON API approach has no such restriction and is more reliable.

---

## Step 2B — Non-Reddit URLs (WebFetch)

Use the WebFetch tool directly:

```
WebFetch url="[URL]" prompt="Return the full text content of this page."
```

WebFetch returns the page content as markdown. Present the content to the user.

**For GitHub repos**, ask for:
- Repository description, README, and main file structure

**For GitHub issues/PRs**, ask for:
- Issue/PR title, body, and all comments

**For articles/docs**, ask for:
- Full article text

---

## Step 3 — Return structured response

**Reddit post:**
```
URL: [url]
Title: [title]
Author: u/[author]
Score: [score] ([upvote%] upvoted)
Comments: [N] total

Post body:
[full post text]

--- COMMENTS ([N] loaded) ---
[author] [score]
[comment text]

  [author] [score]  ← indented = reply
  [reply text]
```

**Reddit listing:**
```
r/[subreddit] — HOT — [N] posts

1. [title] [flair]
   u/[author] | [score] pts | [N] comments
   [permalink]
```

**Other URL:**
Present whatever WebFetch returns, formatted for readability.

---

## Error handling

**Reddit 403/private subreddit:** Report to user — subreddit may be private or banned.
**Reddit network error:** Report. No retry loop.
**WebFetch blocked:** Report the block. Suggest the user paste the content manually.

---

## Global install (use /browse-url in any Claude Code session)

```bash
mkdir -p ~/.claude/commands && \
cp /Users/matthewshields/Projects/ClaudeCodeAdvancements/.claude/commands/browse-url.md \
   ~/.claude/commands/browse-url.md
```
