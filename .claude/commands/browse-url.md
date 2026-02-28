# /browse-url — Open and Read Any URL in Chrome

Navigate to the URL in the user's message, scroll through the full page, and
return a structured summary with full content. Uses Playwright MCP browser tools.

Works for Reddit posts + comments, GitHub repos/issues/PRs, Streamlit, and general URLs.

---

## Steps (follow exactly)

### 1. Parse the URL

The URL is the text after `/browse-url`. Strip whitespace.

**Reddit:** Replace `www.reddit.com` with `old.reddit.com` before navigating.
Old Reddit uses plain HTML; new Reddit uses React shadow DOM that blocks extraction.

### 2. Navigate and scroll to load all content

Use `mcp__plugin_playwright_playwright__browser_run_code` with this pattern:

```javascript
async (page) => {
  await page.goto('[URL]');
  // Scroll to load all content
  for (let i = 0; i < 5; i++) {
    await page.evaluate(() => window.scrollBy(0, 2000));
    await page.waitForTimeout(500);
  }
  return 'loaded';
}
```

### 3. Extract content with browser_run_code

**Reddit post with comments (most common use case):**

```javascript
async (page) => {
  return await page.evaluate(() => {
    const title = document.querySelector('.title a')?.textContent?.trim() || document.title;
    const body = document.querySelector('.usertext-body .md')?.innerText?.trim() || '';
    const commentNodes = document.querySelectorAll('.comment');
    const comments = Array.from(commentNodes).map(node => {
      const author = node.querySelector('.author')?.textContent?.trim() || '[deleted]';
      const score = node.querySelector('.score')?.textContent?.trim() || '';
      const text = node.querySelector('.usertext-body .md')?.innerText?.trim() || '';
      const depth = (node.className.match(/depth-(\d+)/) || ['','0'])[1];
      const indent = '  '.repeat(parseInt(depth));
      return text ? `${indent}[${author}] ${score}\n${indent}${text.replace(/\n/g, '\n' + indent)}` : null;
    }).filter(Boolean);
    return { title, body, commentCount: commentNodes.length, comments };
  });
}
```

Returns: title, post body, comment count, and all comments with author/score/nesting.

**Reddit listing page (r/subreddit hot posts):**

```javascript
async (page) => {
  return await page.evaluate(() => {
    const posts = document.querySelectorAll('.thing .title a.title');
    return Array.from(posts).map(a => a.textContent.trim());
  });
}
```

**GitHub repo:**

```javascript
async (page) => {
  return await page.evaluate(() => {
    const desc = document.querySelector('.f4.my-3')?.textContent?.trim() || '';
    const readme = document.querySelector('[data-target="readme-toc.content"]')?.innerText ||
                   document.querySelector('#readme article')?.innerText || '';
    return `DESCRIPTION: ${desc}\n\nREADME:\n${readme.slice(0, 4000)}`;
  });
}
```

**GitHub issue or PR:**

```javascript
async (page) => {
  return await page.evaluate(() => {
    const title = document.querySelector('.js-issue-title, h1.gh-header-title')?.textContent?.trim() || '';
    const comments = Array.from(document.querySelectorAll('.comment-body')).map(c => c.innerText.trim());
    return { title, comments };
  });
}
```

**Any other URL:**

```javascript
async (page) => {
  return await page.evaluate(() => ({
    title: document.title,
    text: document.body.innerText.slice(0, 5000)
  }));
}
```

### 4. Return structured response

```
URL: [url]
Title: [title]
Comment count: [N] (for Reddit)

Post body:
[full post text]

Comments ([N] total):
[author] [score]
[comment text]

  [author] [score]  ← indented = reply
  [reply text]
```

Present all comments — do not truncate unless the user asks for a summary only.

### 5. Close browser when done

```
mcp__plugin_playwright_playwright__browser_close
```

---

## Troubleshooting

**CAPTCHA or security block:**
Report to user: "This site blocked the browser. Try pasting the content manually."

**Empty extraction on new Reddit (www.reddit.com):**
Ensure you switched to `old.reddit.com` — new Reddit uses shadow DOM.

**GitHub returns nothing:**
Try `document.body.innerText.slice(0, 5000)` as a fallback.

---

## Global install (use /browse-url in any Claude Code session)

```bash
mkdir -p ~/.claude/commands && \
cp /Users/matthewshields/Projects/ClaudeCodeAdvancements/.claude/commands/browse-url.md \
   ~/.claude/commands/browse-url.md
```
