# /browse-url — Open and Read Any URL in Chrome

When invoked, navigate to the URL in the user's message, read the page content,
and return a structured summary. Uses Playwright MCP browser tools.

Works for Reddit posts, GitHub, Streamlit, and general URLs.

---

## Steps (follow exactly)

### 1. Parse the URL from the user's message

The URL is the text provided after `/browse-url`. Strip any surrounding whitespace.

**Reddit special case:** Replace `www.reddit.com` with `old.reddit.com` before navigating.
Old Reddit uses plain HTML and is far easier to read than the React new site.

### 2. Navigate to the URL

```
mcp__plugin_playwright_playwright__browser_navigate  url=[URL]
```

Wait 1 second for page load:
```
mcp__plugin_playwright_playwright__browser_wait_for  time=1
```

### 3. Extract content — use JavaScript evaluation, NOT snapshot

The accessibility snapshot is often too large. Use targeted JavaScript extraction instead:

**Reddit listing page (r/subreddit):**
```javascript
() => {
  const posts = document.querySelectorAll('.thing .title a.title');
  return Array.from(posts).slice(0, 15).map(a => a.textContent.trim()).join('\n');
}
```

**Reddit post/comments page:**
```javascript
() => {
  const title = document.querySelector('.title a')?.textContent || '';
  const body = document.querySelector('.usertext-body .md')?.innerText || '';
  const comments = Array.from(document.querySelectorAll('.comment .usertext-body .md'))
    .slice(0, 8).map(c => c.innerText.trim()).join('\n---\n');
  return `TITLE: ${title}\n\nPOST BODY:\n${body}\n\nTOP COMMENTS:\n${comments}`;
}
```

**GitHub repo:**
```javascript
() => {
  const readme = document.querySelector('[data-target="readme-toc.content"]')?.innerText ||
                 document.querySelector('#readme')?.innerText || '';
  const desc = document.querySelector('.f4.my-3')?.textContent?.trim() || '';
  return `DESCRIPTION: ${desc}\n\nREADME:\n${readme.slice(0, 3000)}`;
}
```

**GitHub issue or PR:**
```javascript
() => {
  const title = document.querySelector('.js-issue-title')?.textContent?.trim() || '';
  const body = document.querySelector('.comment-body')?.innerText || '';
  return `TITLE: ${title}\n\nBODY:\n${body}`;
}
```

**Streamlit app:**
- Use `mcp__plugin_playwright_playwright__browser_take_screenshot` — visual output is most useful
- Also try: `() => document.body.innerText.slice(0, 3000)`

**Any other URL:**
```javascript
() => {
  const title = document.title;
  const text = document.body.innerText.slice(0, 4000);
  return `TITLE: ${title}\n\n${text}`;
}
```

Use `mcp__plugin_playwright_playwright__browser_evaluate` with the function above.

### 4. Return a structured response

```
URL: [the URL]
Title: [page title]

Content:
[extracted text or summary]
```

For Reddit posts: include title, post body, and top 5-8 comments.
For GitHub: include description and key README sections.
For Streamlit: include screenshot description and any text metrics.

### 5. Close the browser when done

```
mcp__plugin_playwright_playwright__browser_close
```

---

## Troubleshooting

**"Network security" block or CAPTCHA:**
- Report to user: "This site blocked Playwright. Paste the text manually."

**JavaScript evaluation returns empty string:**
- Try `() => document.body.innerText.slice(0, 4000)` as a fallback
- Or take a screenshot for visual inspection

**Reddit new site (www.reddit.com) returns sparse content:**
- Make sure you used `old.reddit.com` — the new site uses shadow DOM that blocks evaluation

---

## Making this available globally

This skill lives in the ClaudeCodeAdvancements project. To use `/browse-url` in any
Claude Code session on this Mac, copy it:

```bash
cp /Users/matthewshields/Projects/ClaudeCodeAdvancements/.claude/commands/browse-url.md \
   ~/.claude/commands/browse-url.md
```
