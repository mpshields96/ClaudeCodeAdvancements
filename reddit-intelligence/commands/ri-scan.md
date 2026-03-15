# /reddit-intel:ri-scan — Reddit Intelligence Scanner

Scan one or more subreddits for high-signal posts this week. Read posts and
comment sections. Filter for Claude updates, new tools, useful workflow patterns,
and prediction market signals. Return a structured findings report.

**Security contract:** read-only, no login, no form submission, no data leaves
the machine. See SECURITY.md for full constraints.

## Usage

```
/reddit-intel:ri-scan                    → default: ClaudeCode + ClaudeAI + algobetting
/reddit-intel:ri-scan claude             → Claude Code subreddits only
/reddit-intel:ri-scan betting            → algobetting + PredictionMarkets only
/reddit-intel:ri-scan r/vibecoding       → specific subreddit
/reddit-intel:ri-scan all               → all configured subreddits
```

---

## STEP 0 — Determine target subreddits

Parse the argument:
- No argument or `default` → `ClaudeCode`, `ClaudeAI`, `algobetting`
- `claude` → `ClaudeCode`, `ClaudeAI`, `Claude`, `vibecoding`
- `betting` → `algobetting`, `PredictionMarkets`
- `all` → `ClaudeCode`, `ClaudeAI`, `Claude`, `vibecoding`, `algobetting`, `PredictionMarkets`
- `r/SomeName` → that specific subreddit
- Custom list → comma-separated subreddit names

**Time range:** always use `t=week` (past 7 days). This keeps results fresh and
non-overlapping with previous runs.

---

## STEP 1 — Open a Chrome tab and get its ID

First call:
```
mcp__Control_Chrome__open_url  url="https://old.reddit.com"  new_tab=true
```

Then get the tab ID:
```
mcp__Control_Chrome__get_current_tab
```

Save the `id` field. All subsequent JS execution uses this tab ID.

---

## STEP 2 — Fetch each subreddit listing

For each target subreddit, navigate and extract the top/week posts.

**Navigate:**
```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
window.location.href = 'https://old.reddit.com/r/SUBREDDIT/top/?t=week'
```

Wait ~1 second for page load, then extract:

```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
Array.from(document.querySelectorAll('.thing'))
  .filter(p => p.querySelector('.title a.title'))
  .map(p => ({
    title: p.querySelector('.title a.title')?.textContent?.trim() || '',
    score: parseInt(p.querySelector('.score')?.getAttribute('title') || '0'),
    url: (p.querySelector('a.comments')?.href || '').replace('www.reddit.com', 'old.reddit.com'),
    comments: parseInt(p.querySelector('a.comments')?.textContent || '0')
  }))
  .filter(p => p.title && p.url)
```

Collect the listing. Mark each post with its source subreddit.

---

## STEP 3 — Apply rat poison filter to the listing

**Skip immediately** (do not navigate to) any post whose title matches:

| Pattern | Reason |
|---------|--------|
| Trump, DOD, Pentagon, government | Politics — no workflow signal |
| "DeepSeek distillation", "Moonshot", competitor drama | Company news — not actionable |
| "POV:", "me when", "this is what X looks like", "bruh" | Meme — no signal |
| "I made $X", "went viral", "blew up" | Hype — no pattern |
| "install this", "clone and run", "download now" | Potential malware vector |
| API keys, credentials, tokens | Security — skip |
| Pure model comparison ("GPT vs Claude", "Opus vs Sonnet") | Benchmark noise |
| Anthropic company news (funding, politics, executives) | Company PR |

**Select posts where:** score ≥ 20 OR comments ≥ 25 (after rat poison removal).

**Aim for:** 5–8 posts per subreddit maximum. Quality over quantity.

---

## STEP 4 — Deep-dive each selected post

For each selected post URL, navigate and extract:

```javascript
// Navigate first:
window.location.href = 'POST_URL_HERE'
```

Then extract (wait ~500ms after navigation):

```javascript
const title = document.querySelector('.title a')?.textContent?.trim() || document.title;
const body = document.querySelector('.usertext-body .md')?.innerText?.trim() || '[link post — no body]';
const commentNodes = document.querySelectorAll('.comment');
const comments = Array.from(commentNodes).slice(0, 25).map(n => {
  const author = n.querySelector('.author')?.textContent?.trim() || '[del]';
  const score = n.querySelector('.score')?.textContent?.trim() || '';
  const text = n.querySelector('.usertext-body .md')?.innerText?.trim() || '';
  const depth = parseInt((n.className.match(/depth-(\d+)/) || ['','0'])[1]);
  return text ? '  '.repeat(depth) + '[' + author + '] ' + score + ': ' + text.slice(0, 400) : null;
}).filter(Boolean);
({ title, body: body.slice(0, 1000), commentCount: commentNodes.length, comments })
```

---

## STEP 5 — Apply content-level rat poison filter

After reading each post, **discard entirely** if:
- Body and top comments are pure hype with no concrete technique
- Post is about Claude model capabilities, not Claude Code workflows
- Post is about Anthropic company matters, not developer tooling
- Comments are mostly jokes or reactions with no technical content

**Keep** if there is a concrete workflow pattern, pain point, code snippet, tool,
or technique a developer would actually use.

---

## STEP 6 — Map findings to topic categories

### For Claude Code subreddits, map to:

```
Frontier 1 — Memory:        cross-session memory, CLAUDE.md patterns, context loss
Frontier 2 — Spec:          structured prompting, plan-first, skills/hooks
Frontier 3 — Context:       token limits, degradation, knowing when to reset
Frontier 4 — Agent Guard:   multi-agent conflicts, credentials, file overwrites, permissions
Frontier 5 — Usage:         token costs, rate limits, usage visibility, menu bar tools
New Feature:                anything Anthropic just shipped (Auto Mode, /loop, context window)
Community Tool:             third-party tools, plugins, GitHub repos worth evaluating
```

### For betting/prediction market subreddits, map to:

```
Signal Quality:     new data sources, line movement signals, model inputs
Infrastructure:     APIs, data pipelines, execution layer, latency
Strategy:           edge types, market efficiency findings, what works/doesn't
Risk:               loss scenarios, common mistakes, things to avoid
```

---

## STEP 7 — Deliver structured report

Format:

```
REDDIT INTELLIGENCE — [subreddit list] — Week of [date]
Subreddits scanned: [N] | Posts reviewed: [N] | Rat poison skipped: [N]

━━━ CLAUDE CODE TRACK ━━━

[TOPIC CATEGORY]
• "[post title]" (r/subreddit, [score] pts, [N] comments)
  Signal: [1-2 sentences — concrete pattern or pain point]
  Action: [what we could do with this, if anything]

[repeat per category, skip categories with no signal]

━━━ BETTING / PREDICTION MARKETS TRACK ━━━

[SIGNAL CATEGORY]
• "[post title]" (r/subreddit, [score] pts)
  Signal: [concrete finding]
  Action: [relevance to bot]

━━━ PRIORITY RECOMMENDATION ━━━
[2-3 sentences: what this week's community signal suggests to act on]
```

Omit any track or category that had no useful signal this run.

---

## STEP 8 — Optional: save findings to log

If the user wants a persistent record, append the report to:
`/Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/findings/`

Name the file: `YYYY-MM-DD-scan.md`

Only write this file if the user explicitly asks to save it. Never auto-save.

---

## Resilience patterns

These defensive checks run before extraction. Use them whenever a step returns
empty results or behaves unexpectedly.

### Check 1 — Verify the page loaded and is the right URL

Before running any extraction JS, confirm the page is on the expected URL:

```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
({ href: window.location.href, ready: document.readyState })
```

Expected: `href` contains `old.reddit.com/r/SUBREDDIT` and `ready` is `"complete"`.

If `ready` is `"loading"` or `"interactive"`, wait and re-run this check.
If `href` is wrong (e.g. still on previous page), the `window.location.href`
assignment hasn't resolved yet — re-check in 1-2 seconds.

### Check 2 — Detect Chrome popups/dialogs/overlays

Chrome update prompts, system dialogs, and fullscreen overlays will prevent JS
from running correctly in the tab. Check for them first:

```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
({
  title: document.title,
  overlays: document.querySelectorAll('[role="dialog"], .modal, #update-banner').length,
  bodyVisible: document.body && document.body.innerText.length > 100
})
```

- If `overlays > 0`: a dialog is open. Note which one and ask the user to dismiss it.
- If `bodyVisible` is false: page content hasn't rendered. Wait and retry.
- If `title` is "about:blank" or empty: the tab opened but Reddit didn't load.
  Re-navigate with `window.location.href`.

### Check 3 — Safe extraction with fallback

Wrap listing extraction in a guard so empty results don't silently mislead:

```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
const things = document.querySelectorAll('.thing');
if (things.length === 0) {
  // Return diagnostic info instead of empty array
  ({ error: 'no .thing elements found', href: window.location.href, title: document.title })
} else {
  Array.from(things)
    .filter(p => p.querySelector('.title a.title'))
    .map(p => ({
      title: p.querySelector('.title a.title')?.textContent?.trim() || '',
      score: parseInt(p.querySelector('.score')?.getAttribute('title') || '0'),
      url: (p.querySelector('a.comments')?.href || '').replace('www.reddit.com', 'old.reddit.com'),
      comments: parseInt(p.querySelector('a.comments')?.textContent || '0')
    }))
    .filter(p => p.title && p.url)
}
```

If the result is `{ error: 'no .thing elements found' }`:
1. Check the `href` — if it's on www.reddit.com, re-navigate to old.reddit.com
2. Check `title` — if it contains "CAPTCHA" or "rate limited", see below
3. Otherwise wait 2 seconds and retry extraction once

### Check 4 — Per-post load failure (skip, don't abort)

When deep-diving individual posts, some may time out or redirect. Use this pattern
to fail gracefully and continue with the remaining posts:

```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
const postTitle = document.querySelector('.title a')?.textContent?.trim();
if (!postTitle || window.location.href.includes('reddit.com/login')) {
  ({ skip: true, reason: 'post not loaded or redirected to login', href: window.location.href })
} else {
  // ... full extraction as normal
}
```

If `skip: true` is returned, note the post as `[skipped — load failure]` in the
report and move on to the next post. Never abort the full scan for one failed post.

---

## Troubleshooting

**Tab ID not found:**
Call `mcp__Control_Chrome__list_tabs` to see open tabs and pick the Reddit one.

**Chrome update banner / dialog blocking the tab:**
Run Check 2 above. If an overlay is detected, inform the user:
"Chrome has a dialog open that needs to be dismissed before I can continue.
Please close it and I'll retry." Never attempt to click the dialog yourself.

**Page shows old content after navigation:**
The `window.location.href` assignment is async. Run Check 1 above to confirm
the page has finished loading, then re-run extraction.

**Extraction returns empty after correct URL confirmed:**
Run Check 3's guarded extraction. If still empty after one retry, skip that
subreddit and note it in the report: `[r/SUBREDDIT — listing failed to load]`.

**Reddit showing CAPTCHA or login wall:**
Reddit occasionally shows this to automated browsers. Navigate away:
```javascript
window.location.href = 'https://old.reddit.com'
```
Wait 30 seconds, then re-navigate to the subreddit. Never attempt to solve
CAPTCHAs or log in.

**Empty listing (0 posts):**
Check `window.location.href` to confirm you're on old.reddit.com, not www.reddit.com.
New Reddit uses React shadow DOM that blocks `.thing` selectors.

**Playwright MCP available instead of Chrome:**
If `mcp__plugin_playwright_playwright__browser_run_code` is available, use it —
it's more reliable than the Chrome approach. See `ri-read.md` for Playwright patterns.
