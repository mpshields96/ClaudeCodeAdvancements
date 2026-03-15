# /reddit-research — Deep Reddit Research for Claude Code Advancements

Browse r/ClaudeCode (and optionally r/ClaudeAI, r/vibecoding), sorted by top posts
from the past month. Read full posts and comments. Return structured findings mapped
to the five ClaudeCodeAdvancements frontiers.

**Primary approach:** Chrome JS execution
**Fallback:** Playwright MCP (when `mcp__plugin_playwright_playwright__browser_run_code` is available)

## Usage
```
/reddit-research              → r/ClaudeCode only
/reddit-research r/ClaudeAI   → specific subreddit
/reddit-research all          → all three subreddits (ClaudeCode + ClaudeAI + vibecoding)
```

---

## Steps (follow exactly — this is a multi-page research process)

### Step 0 — Open a Chrome tab and get its ID

```
mcp__Control_Chrome__open_url  url="https://old.reddit.com"  new_tab=true
mcp__Control_Chrome__get_current_tab
```

Save the `id` field. All JS execution uses this tab ID.

**Note:** `mcp__Claude_in_Chrome__navigate` is blocked for Reddit. Use
`window.location.href` assignments via `javascript_tool` instead.

---

### Step 1 — Get the top posts listing

For each target subreddit, navigate and extract post metadata.

**Navigate (separate tool call from extraction):**
```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
window.location.href = 'https://old.reddit.com/r/ClaudeCode/top/?t=month'
```

Wait for page load, then scroll and extract:

```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
for (let i = 0; i < 3; i++) {
  window.scrollBy(0, 2000);
  await new Promise(r => setTimeout(r, 300));
}
Array.from(document.querySelectorAll('.thing'))
  .filter(p => p.querySelector('.title a.title'))
  .map(p => ({
    title: p.querySelector('.title a.title')?.textContent?.trim() || '',
    score: parseInt(p.querySelector('.score')?.getAttribute('title') || '0'),
    comments_url: (p.querySelector('a.comments')?.href || '').replace('www.reddit.com', 'old.reddit.com'),
    num_comments: parseInt(p.querySelector('a.comments')?.textContent || '0')
  }))
  .filter(p => p.title && p.comments_url)
```

Replace `r/ClaudeCode` with the target subreddit as needed.

---

### Step 2 — Select high-signal posts to deep-dive

From the listing, select posts where **score >= 15 OR num_comments >= 20**.

**Skip immediately (rat poison)** — do not navigate to posts whose titles contain:
- "install", "clone", "download", "run this", "execute"
- "jailbreak", "bypass", "prompt injection", "hack"
- "I made $", "went viral", "blew up"
- Pure complaints with no constructive angle ("Claude sucks", "Claude broke")
- Off-topic (politics, personal drama, unrelated tools)
- Pure model comparisons ("GPT vs Claude", "Opus vs Sonnet")
- Anthropic company news (funding, executives, policy)

Aim to deep-dive **5-10 posts maximum** — quality over quantity.

---

### Step 3 — Deep-dive each selected post

**Navigate:**
```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
window.location.href = '[comments_url]'
```

**Scroll, then extract:**
```javascript
// via mcp__Claude_in_Chrome__javascript_tool  action=javascript_exec  tabId=[ID]
for (let i = 0; i < 5; i++) {
  window.scrollBy(0, 2000);
  await new Promise(r => setTimeout(r, 350));
}
const title = document.querySelector('.title a')?.textContent?.trim() || document.title;
const score = document.querySelector('.score')?.getAttribute('title') || '';
const body = document.querySelector('.usertext-body .md')?.innerText?.trim() || '[link post — no body]';
const commentNodes = document.querySelectorAll('.comment');
const comments = Array.from(commentNodes).slice(0, 25).map(node => {
  const author = node.querySelector('.author')?.textContent?.trim() || '[deleted]';
  const cscore = node.querySelector('.score')?.textContent?.trim() || '';
  const text = node.querySelector('.usertext-body .md')?.innerText?.trim() || '';
  const depth = (node.className.match(/depth-(\d+)/) || ['','0'])[1];
  const indent = '  '.repeat(parseInt(depth));
  return text ? `${indent}[${author}] ${cscore}: ${text.slice(0, 400)}` : null;
}).filter(Boolean);
({ title, score, body: body.slice(0, 1000), comments })
```

---

### Step 4 — Apply the rat poison filter to content

After reading each post, discard it entirely if the **body or top comments** primarily:
- Recommend installing/cloning/running specific third-party tools
- Contain API keys, tokens, or credentials
- Are hype without a concrete pattern ("this changes everything!")
- Are about Claude models generally, not Claude Code workflows
- Are about Anthropic company matters, not developer tooling

Keep it if there is a **concrete workflow pattern, pain point, or technique** that
a developer would actually use.

---

### Step 5 — Map each surviving finding to a frontier

```
Frontier 1 — Memory System:    cross-session memory, /compact, context loss, remembering decisions
Frontier 2 — Spec System:      structured prompting, requirements docs, CLAUDE.md patterns
Frontier 3 — Context Monitor:  token limits, context degradation, knowing when to reset
Frontier 4 — Agent Guard:      hooks, permissions, multi-agent conflicts, file overwrites
Frontier 5 — Usage Dashboard:  token costs, rate limits, usage visibility
Other:                         genuinely new pattern not covered by any frontier
```

---

### Step 6 — Return structured findings

```
REDDIT RESEARCH — r/ClaudeCode — Top/Month — [today's date]
Posts scanned: [N] | Posts deep-dived: [N] | Rat poison skipped: [N]

---

FRONTIER 1 — Memory System
• "post title" (N pts, N comments)
  Pattern: what developers are doing or struggling with — 1-2 sentences
  Opportunity: how this maps to what we're building

FRONTIER 3 — Context Monitor
• "post title" (N pts)
  Pattern: ...
  Opportunity: ...

[repeat for each frontier that has findings]

OTHER — Novel patterns not in current frontiers
• [finding]: [description]

---

PRIORITY RECOMMENDATION:
1-2 sentences on what the community signal suggests we should build next,
purely based on what was found — no speculation
```

If a frontier has no findings this run, omit it entirely.

---

## Fallback: Playwright MCP

If `mcp__plugin_playwright_playwright__browser_run_code` is available, replace
all the Chrome JS steps with this pattern (more reliable for scrolling):

```javascript
async (page) => {
  await page.goto('https://old.reddit.com/r/ClaudeCode/top/?t=month');
  await page.waitForTimeout(1000);
  for (let i = 0; i < 3; i++) {
    await page.evaluate(() => window.scrollBy(0, 2000));
    await page.waitForTimeout(300);
  }
  return await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.thing')).map(p => ({
      title: p.querySelector('.title a.title')?.textContent?.trim() || '',
      score: parseInt(p.querySelector('.score')?.getAttribute('title') || '0'),
      comments_url: p.querySelector('a.comments')?.href?.replace('www.reddit.com', 'old.reddit.com') || '',
      num_comments: parseInt(p.querySelector('a.comments')?.textContent || '0')
    })).filter(p => p.title && p.comments_url);
  });
}
```

---

## Notes

- old.reddit.com is required — new Reddit blocks JavaScript evaluation
- A full "all" run (3 subreddits, 10 posts each) takes several minutes — expected
- If a post redirects to a video or external link with no text, skip it and note it
- Findings can be saved manually to `reddit-intelligence/findings/` if you want a dated record
- For weekly scans (t=week) with betting track, use `/reddit-intel:ri-scan` instead
