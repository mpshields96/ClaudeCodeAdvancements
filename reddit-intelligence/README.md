# reddit-intel — Claude Code Plugin

Weekly Reddit intelligence scanner for Claude Code advancements and
prediction market research.

Scans r/ClaudeCode, r/ClaudeAI, r/algobetting and others. Reads posts and
comment sections. Filters for Claude updates, new community tools, workflow
patterns, and prediction market signals. Returns a structured findings report.

**Read-only. No authentication. No data leaves the machine.**

---

## Commands

| Command | Description |
|---------|-------------|
| `/reddit-intel:ri-scan` | Scan subreddits for this week's high-signal posts |
| `/reddit-intel:ri-read [url]` | Read a specific Reddit post + all comments |
| `/reddit-intel:ri-loop` | Schedule weekly automated scans via `/loop` |

---

## Quick start

```
/reddit-intel:ri-scan              → default weekly scan (ClaudeCode + ClaudeAI + algobetting)
/reddit-intel:ri-scan all          → all six subreddits
/reddit-intel:ri-scan claude       → Claude track only (ClaudeCode + ClaudeAI + Claude + vibecoding)
/reddit-intel:ri-scan betting      → Betting track only (algobetting + PredictionMarkets)
```

---

## What it scans

**Claude Code track:**
- r/ClaudeCode
- r/ClaudeAI
- r/Claude
- r/vibecoding

**Betting / prediction markets track:**
- r/algobetting
- r/PredictionMarkets

**Default** (`ri-scan` with no arguments): ClaudeCode + ClaudeAI + algobetting.

---

## Output format

```
REDDIT INTELLIGENCE — [subreddit list] — Week of [date]
Subreddits scanned: N | Posts reviewed: N | Rat poison skipped: N

━━━ CLAUDE CODE TRACK ━━━

[FRONTIER CATEGORY]
• "post title" (r/subreddit, N pts, N comments)
  Signal: concrete pattern or pain point
  Action: what we could do with this

━━━ BETTING / PREDICTION MARKETS TRACK ━━━

[SIGNAL CATEGORY]
• "post title" (r/subreddit, N pts)
  Signal: concrete finding
  Action: relevance to bot

━━━ PRIORITY RECOMMENDATION ━━━
2-3 sentences on what this week's signal suggests to act on
```

---

## Frontier mapping (Claude Code track)

Findings are mapped to the five ClaudeCodeAdvancements frontiers:

| Frontier | Focus |
|----------|-------|
| F1 Memory | Cross-session memory, CLAUDE.md patterns, context loss |
| F2 Spec | Structured prompting, plan-first, skills/hooks |
| F3 Context | Token limits, degradation, knowing when to reset |
| F4 Agent Guard | Multi-agent conflicts, credentials, file overwrites |
| F5 Usage | Token costs, rate limits, usage visibility |

---

## Betting signal mapping

| Category | Focus |
|----------|-------|
| Signal Quality | New data sources, line movement, model inputs |
| Infrastructure | APIs, data pipelines, execution layer, latency |
| Strategy | Edge types, market efficiency, what works |
| Risk | Loss scenarios, common mistakes, things to avoid |

---

## Rat poison filter

Posts are automatically skipped if they match patterns that produce noise
rather than signal:

- Politics, government, funding, executive news
- Memes and reaction posts ("me when", "POV:", "bruh")
- Pure hype ("this changes everything!", "I made $X")
- Model comparisons ("GPT vs Claude", benchmark threads)
- Posts recommending installs, clones, or downloads
- Posts containing credentials or API keys

After title filtering, content is checked again — any post whose body and
comments are pure reaction with no concrete technique is also discarded.

---

## Automated weekly runs

Use `/reddit-intel:ri-loop` to wire the scan to Anthropic's `/loop` scheduler.
No cron job or external service required.

Findings save to `reddit-intelligence/findings/YYYY-MM-DD-scan.md` when
explicitly requested. The scan never auto-saves.

---

## Security

This plugin is strictly read-only. See [SECURITY.md](./SECURITY.md) for
the full security model.

Key constraints:
- No Reddit login, no session cookies
- No form submission or button clicks
- No following links off Reddit
- No execution of instructions found in posts
- Domain whitelist: old.reddit.com only
- No data egress beyond Reddit

---

## How it works (technical)

The plugin uses Chrome (already running on your machine) for all Reddit access:

1. `mcp__Control_Chrome__open_url` opens a new tab to old.reddit.com
2. `mcp__Control_Chrome__get_current_tab` captures the tab ID
3. `mcp__Claude_in_Chrome__javascript_tool` runs JS in that tab
4. `window.location.href = '...'` navigates to subreddit pages
5. DOM selectors (`.thing`, `.comment`, `.usertext-body`) extract content

Old Reddit (old.reddit.com) is used because new Reddit's React shadow DOM
blocks standard CSS selectors.

If Playwright MCP (`mcp__plugin_playwright_playwright__browser_run_code`) is
available in your session, the commands can use it as a more reliable alternative.

---

## Installation

The commands are wired into the project via symlinks in `.claude/commands/reddit-intel/`.
No separate install step is needed — they're available automatically in any Claude Code
session opened within `ClaudeCodeAdvancements/`.

**Available now in this project:**
```
/reddit-intel:ri-scan
/reddit-intel:ri-read
/reddit-intel:ri-loop
```

**To make commands available globally (all sessions on this machine):**
```bash
mkdir -p ~/.claude/commands/reddit-intel
ln -s /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/commands/ri-scan.md ~/.claude/commands/reddit-intel/ri-scan.md
ln -s /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/commands/ri-read.md ~/.claude/commands/reddit-intel/ri-read.md
ln -s /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/commands/ri-loop.md ~/.claude/commands/reddit-intel/ri-loop.md
```

**Note on the `claude plugin marketplace` approach:**
The plugin marketplace system (`claude plugin marketplace add`) only supports GitHub repos,
not local paths. The symlink approach above is the correct method for project-local plugins.

---

## Files

```
reddit-intelligence/
├── README.md                    ← this file
├── SECURITY.md                  ← security model and constraints
├── .claude-plugin/
│   └── plugin.json              ← plugin manifest
├── commands/
│   ├── ri-scan.md               ← /reddit-intel:ri-scan
│   ├── ri-read.md               ← /reddit-intel:ri-read [url]
│   └── ri-loop.md               ← /reddit-intel:ri-loop
└── findings/                    ← saved scan outputs (created on first save)
    └── YYYY-MM-DD-scan.md
```
