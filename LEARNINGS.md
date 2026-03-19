# CCA Learnings — Severity-Tracked Patterns
# Severity: 1 = noted, 2 = hard rule, 3 = global (promoted to ~/.claude/rules/)
# Append-only. Never truncate.

---

### Anthropic key regex must include hyphens — Severity: 3 — Count: 3
- **Anti-pattern:** `sk-[A-Za-z0-9]{20,}` (misses keys with hyphens)
- **Fix:** `sk-[A-Za-z0-9\-]{20,}` (keys contain `sk-ant-api03-...`)
- **First seen:** 2026-02-19
- **Last seen:** 2026-03-15
- **Files:** any credential scanning or validation
- **Promoted:** 2026-03-17 -> `.claude/rules/agent-guard.md` + `~/.claude/rules/learnings.md` (global)

---

### PreToolUse deny format vs Stop hook block format differ — Severity: 2 — Count: 2
- **Anti-pattern:** Using same format for both hook types. Top-level `{"decision": "block"}` on PreToolUse silently fails.
- **Fix:**
  - PreToolUse deny: `{"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "..."}}`
  - Stop hook block: `{"decision": "block", "reason": "..."}`
- **First seen:** 2026-02-20 (Session 2)
- **Last seen:** 2026-03-08 (Session 8)
- **Files:** any hook that needs to block or deny

---

### Claude Code transcript usage field location — Severity: 2 — Count: 1
- **Anti-pattern:** Reading `entry.get("usage", {})` on all entries — returns 0 for real transcripts
- **Fix:** For `type == "assistant"` entries, usage is at `entry["message"]["usage"]`. Sum: `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
- **First seen:** 2026-03-08 (Session 8 CTX-1 bug fix)
- **Last seen:** 2026-03-08
- **Files:** `context-monitor/hooks/meter.py`, any transcript parser

---

### argparse subparsers don't inherit parent options — Severity: 1 — Count: 1
- **Anti-pattern:** Adding `--project` to the parent parser expecting subcommands to inherit it
- **Fix:** Add `--project` explicitly to each subparser that needs it
- **First seen:** 2026-03-08 (Session 8, memory-system/cli.py)
- **Last seen:** 2026-03-08
- **Files:** any CLI using argparse subparsers

---

### Project-scoped commands invisible outside project folder — Severity: 1 — Count: 1
- **Anti-pattern:** Creating commands in `.claude/commands/` within a project, expecting them to work from other folders
- **Fix:** Copy any command that should be global to `~/.claude/commands/`. Project-scoped commands only load when Claude Code is launched from that project directory.
- **First seen:** 2026-03-15 (Session 10)
- **Last seen:** 2026-03-15
- **Files:** any `.claude/commands/*.md`

---

### Reddit JSON API top requires explicit time range — Severity: 1 — Count: 1
- **Anti-pattern:** Calling `/r/subreddit/top.json` without `t=month` or `t=year` — returns only ~24hr top
- **Fix:** Append `&t=month` or `&t=year` to the URL for longer time ranges
- **First seen:** 2026-03-15 (Session 10 — /cca-scout results were too narrow)
- **Last seen:** 2026-03-15
- **Files:** `reddit-intelligence/reddit_reader.py`

---

### Tools outside sandbox require batch install in separate session — Severity: 1 — Count: 1
- **Anti-pattern:** Discovering tools (CShip, RTK, pipx packages) during CCA reviews and context-switching per install
- **Fix:** Collect all install commands during the session, batch them into one non-CCA terminal session at the end
- **First seen:** 2026-03-15 (Session 10)
- **Last seen:** 2026-03-15
- **Files:** CCA scope boundary rule in CLAUDE.md

---

### File-writing hooks trigger system-reminder context burn — Severity: 2 — Count: 1
- **Anti-pattern:** PostToolUse or Stop hooks that write/modify files during a Claude Code session. Each file modification triggers a `<system-reminder>` notification showing the diff, which consumes context tokens silently.
- **Evidence:** Reddit user reported 160k tokens consumed in 3 rounds from a Prettier formatting hook writing files. The system-reminders showing file diffs were the cause, not the hook execution itself.
- **Fix:** Hooks should avoid writing files during active sessions where possible. If file writes are necessary (e.g., compact_anchor.py), keep files small and writes infrequent. Never use hooks to auto-format or auto-modify source files mid-conversation.
- **CCA impact:** `compact_anchor.py` (CTX-5) writes `.claude-compact-anchor.md` every 10 turns — review whether this triggers system-reminders and adjust frequency if so.
- **First seen:** 2026-03-15 (Session 11 — from Beast post review, r/ClaudeCode/comments/1oivs81)
- **Last seen:** 2026-03-15
- **Files:** any hook that calls Write/Edit, `context-monitor/hooks/compact_anchor.py`
- **Source:** https://www.reddit.com/r/ClaudeAI/comments/1oivjvm/comment/nm2cxm7/

---

### Commit discipline — work must be committed before session close — Severity: 2 — Count: 2
- **Anti-pattern:** Completing and testing multiple features across sessions without committing — leaves 80+ untracked files as recovery liability
- **Fix:** Commit each task when tests pass. Never close a session with untracked deliverables.
- **First seen:** 2026-03-15 (Session 9 — sessions 7+8 work never committed)
- **Last seen:** 2026-03-15 (Session 16 — sessions 10-15 backlog finally committed)
- **Files:** session workflow (applies to all sessions)
- **Promoted:** 2026-03-15 -> CLAUDE.md Known Gotchas

---

### Test fixture files trigger false positives in code scanners — Severity: 1 — Count: 1
- **Anti-pattern:** Scanning test files for TODO/FIXME/NotImplementedError — test fixtures intentionally contain these strings as test data
- **Fix:** Exclude files in `/tests/` directories and `test_*.py` files from stub/TODO scanning
- **First seen:** 2026-03-15 (Session 16 — arewedone.py reported 10 false positives from test fixtures)
- **Last seen:** 2026-03-15
- **Files:** `usage-dashboard/arewedone.py`, any code quality scanner

---

### Claude Island auto-installs hooks on first launch — Severity: 2 — Count: 1
- **Anti-pattern:** Launching Claude Island while other Claude Code sessions are actively running
- **Fix:** Only launch Claude Island when all other Claude Code sessions are idle. The app auto-installs hooks into `~/.claude/hooks/` which affects ALL sessions globally.
- **First seen:** 2026-03-15 (Session 16 — discovered during install research)
- **Last seen:** 2026-03-15
- **Files:** Claude Island v1.2 (`/Applications/Claude Island.app`)

---

### tmux kill-server corrupts socket — Severity: 1 — Count: 1
- **Anti-pattern:** Running `tmux kill-server` to clean up sessions — can corrupt the socket at `/private/tmp/tmux-501/default`, causing all subsequent tmux commands to fail with "server exited unexpectedly"
- **Fix:** Use `tmux kill-session -t <name>` to kill specific sessions. If socket is already corrupted: `rm -f /private/tmp/tmux-501/default`
- **First seen:** 2026-03-16 (Session 18 — dev-start kalshi debugging)
- **Last seen:** 2026-03-16
- **Files:** `~/.local/bin/dev-start`, any tmux automation

---

### AppleScript keystroke simulation unreliable for CLI apps — Severity: 1 — Count: 1
- **Anti-pattern:** Using `osascript` with `keystroke` to type commands into Terminal windows running interactive CLI apps (Claude Code). Requires Accessibility permissions, types into whichever window is focused (not targeted), and `do script` creates new shell processes instead of typing into running apps.
- **Fix:** Use tmux `send-keys` with exact pane targeting for reliable scripted input to running CLI apps.
- **First seen:** 2026-03-16 (Session 18 — dev-start kalshi iterations)
- **Last seen:** 2026-03-16
- **Files:** `~/.local/bin/dev-start`, any Terminal automation

---

### Self-learning loops plateau at mechanical optimization — Severity: 1 — Count: 1
- **Anti-pattern:** Expecting self-learning to improve architectural judgment or strategic decisions through log analysis alone
- **Fix:** Design self-learning for bounded parameter tuning (thresholds, filters, batch sizes) and use it to free the human for judgment calls. Don't chase unbounded self-improvement.
- **First seen:** 2026-03-16 (Session 19 — CCA vs YoYo analysis, u/inbetweenthebleeps observation)
- **Last seen:** 2026-03-16
- **Files:** `self-learning/reflect.py`, `self-learning/strategy.json`, any future Kalshi self-learning integration

---

### Claude Squad worktrees break shared filesystem apps — Severity: 1 — Count: 1
- **Anti-pattern:** Using Claude Squad for projects that need a shared filesystem (database, venv, config files). Claude Squad creates git worktrees per session, so each chat gets an isolated copy — breaking any app relying on shared state.
- **Fix:** Use tmux split panes or Terminal tabs instead for apps needing shared filesystem. Claude Squad is good for independent coding tasks, not for shared-state bots.
- **First seen:** 2026-03-16 (Session 18 — Kalshi bot hook errors in Claude Squad)
- **Last seen:** 2026-03-16
- **Files:** any bot/daemon needing shared database or venv

---

### Edit tool context cleared by system-reminder injection — Severity: 1 — Count: 1
- **Anti-pattern:** Reading a file, then having the Edit tool refuse because system-reminder tags (CLAUDE.md injection) cleared the file from Read context between the read and edit
- **Fix:** Read the file immediately before editing, or use Bash sed as fallback for files in directories that trigger CLAUDE.md system-reminders
- **First seen:** 2026-03-16
- **Last seen:** 2026-03-16
- **Files:** spec-system/commands/*.md (triggers spec-system/CLAUDE.md injection)

### Percentage-based context thresholds break at 1M windows — Severity: 2 — Count: 1
- **Anti-pattern:** Using fixed percentage thresholds (50/70/85%) for all window sizes. At 1M, yellow fires at 500k tokens — well past quality degradation.
- **Fix:** Adaptive thresholds: `min(pct_threshold, quality_ceiling / window * 100)`. Quality ceilings: yellow=250k, red=400k, critical=600k. For 200k: unchanged. For 1M: yellow=25%, red=40%, critical=60%.
- **Evidence:** 1855pts Reddit post + 174 comments. Community consensus: quality degrades at 250-500k regardless of window size.
- **First seen:** 2026-03-16 (Session 24)
- **Last seen:** 2026-03-16
- **Files:** `context-monitor/hooks/meter.py`, `context-monitor/statusline.py`

---

### Documented pass-only functions are not stubs — Severity: 1 — Count: 1
- **Anti-pattern:** Code scanner flagging `def method(self): """Suppress X."""; pass` as a stub
- **Fix:** Only flag pass-only functions WITHOUT a docstring. If a docstring is present, the pass is intentional (e.g. overriding log_message to suppress HTTP server output).
- **First seen:** 2026-03-16 (Session 24 — arewedone.py false positive on otel_receiver.py)
- **Last seen:** 2026-03-16
- **Files:** `usage-dashboard/arewedone.py`

---

### General subreddits are noise for CCA nuclear scans — Severity: 2 — Count: 2
- **Anti-pattern:** Running full nuclear scans on r/Anthropic, r/algotrading, or other general subs expecting CCA frontier signal
- **Fix:** Only nuclear scan r/ClaudeCode (and r/ClaudeAI if time allows). For niche subs, use keyword-filtered /cca-scout instead.
- **Evidence:** r/Anthropic: 0 BUILD, 0 ADAPT from 75 posts (~85% politics). r/algotrading: 0 BUILD, 0 ADAPT from 98 posts (domain-specific). r/ClaudeCode: 5 BUILD, 23 ADAPT from 138 posts. r/ClaudeAI: 2 BUILD, 1 ADAPT from 100 posts.
- **First seen:** 2026-03-16 (Session 22, r/ClaudeAI predicted ~60% noise)
- **Last seen:** 2026-03-16 (Session 23, r/Anthropic ~85% noise, r/algotrading ~93% noise)
- **Files:** .claude/commands/cca-nuclear.md, SESSION_STATE.md

---

### Documentation debt compounds silently — Severity: 1 — Count: 1
- **Anti-pattern:** ROADMAP.md went 24 sessions without an update — still showed all frontiers as "Research phase" when they were all COMPLETE with 800 tests
- **Fix:** Update docs in the same session as the work they describe. If a frontier is completed, update ROADMAP.md that session, not 24 sessions later.
- **First seen:** 2026-03-16 (Session 25 — ROADMAP.md finally updated)
- **Last seen:** 2026-03-16
- **Files:** ROADMAP.md, any long-lived project documentation

---

### Building without testing/validation is wasted work — Severity: 3 — Count: 1
- **Anti-pattern:** Treating "build" as the goal. Shipping code without the full lifecycle: research -> plan -> build -> test -> validate -> debug -> backtest -> iterate. Building is just one step of eight.
- **Fix:** Every master task and every feature MUST have an explicit lifecycle section with all steps. No task is "done" at the build step. Validation against real data, backtesting against historical data, and debugging found issues are all required before claiming completion. A feature that builds and passes unit tests but has never been validated against real-world data is NOT complete.
- **Applies everywhere:** CCA development, Kalshi bot strategies, self-learning improvements, nuclear scan tooling.
- **First seen:** 2026-03-16 (Session 24 — Matthew's explicit directive)
- **Last seen:** 2026-03-16
- **Files:** MASTER_TASKS.md, all module CLAUDE.md files, all future task definitions

### Orientation files should be exempt from RetryDetector (same as WasteDetector) — Severity: 1 — Count: 1
- **Anti-pattern:** RetryDetector flags SESSION_STATE.md with 5-8 consecutive Edits — these are intentional doc-update patterns at session wrap, not retry loops
- **Fix:** Exempt ORIENTATION_FILES (SESSION_STATE.md, CLAUDE.md, CHANGELOG.md, ROADMAP.md) from RetryDetector, or add a "doc-update" exemption similar to WasteDetector's orientation exemption
- **First seen:** 2026-03-17 (Session 26 — trace_analyzer real-data validation)
- **Last seen:** 2026-03-17
- **Files:** `self-learning/trace_analyzer.py` RetryDetector class

### Validate Reddit post URLs before spawning deep-read agents — Severity: 1 — Count: 1
- **Anti-pattern:** Spawning haiku agents (~45k tokens each) to deep-read Reddit posts without verifying the URL is accessible first
- **Fix:** Add a quick HEAD request or JSON fetch validation before spawning agents. Nuclear_fetcher post IDs can differ from actual current URLs (especially r/ClaudeAI month-view vs search)
- **First seen:** 2026-03-17 (Session 27)
- **Last seen:** 2026-03-17
- **Files:** reddit-intelligence/nuclear_fetcher.py, any agent-based deep-read workflow

### Phishing regex needs whitelist-first approach — Severity: 1 — Count: 1
- **Anti-pattern:** Running phishing domain patterns (e.g., `r"anthropic"`) against ALL URLs including legitimate ones like anthropic.com
- **Fix:** Check URL against `legit_domains` whitelist set BEFORE applying phishing pattern matching. Prevents false positives on official domains.
- **First seen:** 2026-03-17 (Session 27 — content_scanner backtest caught 2/138 false positives)
- **Last seen:** 2026-03-17
- **Files:** `agent-guard/content_scanner.py` scan_url()

---

### Background agent results lost to context compaction — Severity: 1 — Count: 1
- **Anti-pattern:** Spawning 3-4 background deep-read agents and continuing work, then losing their results when context compacts before they complete
- **Fix:** Check background agent results within 5 minutes of spawn. If session is long, process agents in batches of 2 rather than 4.
- **First seen:** 2026-03-17 (Session 28 — 3 deep-read agents lost to compaction)
- **Last seen:** 2026-03-17
- **Files:** any workflow using background Agent tool spawns

---

### Semantic Scholar paper IDs are NOT arXiv IDs — Severity: 1 — Count: 1
- **Anti-pattern:** Using Semantic Scholar paper hash as arXiv ID (e.g., fetching arxiv.org/abs/dc491963de5b...)
- **Fix:** Search for the paper title on arXiv first (`WebSearch "paper title" arxiv`), then use the returned arXiv ID
- **First seen:** 2026-03-18
- **Last seen:** 2026-03-18
- **Files:** paper_scanner.py workflow, any paper deep-read task

---

### Typst resolves sys.inputs paths relative to template file — Severity: 1 — Count: 1
- **Anti-pattern:** Passing `/tmp/data.json` via `--input data=/tmp/data.json` — Typst resolves as `<template_dir>/tmp/data.json`
- **Fix:** Use `--root /` flag with absolute paths: `typst compile --root / --input data=/abs/path template.typ`
- **First seen:** 2026-03-18
- **Last seen:** 2026-03-18
- **Files:** design-skills/report_generator.py, any Typst integration

---

### Self-resolution scan catches wasted effort on solved problems — Severity: 2 — Count: 1
- **Anti-pattern:** Keeping MTs as "blocked" without checking if the ecosystem has solved them
- **Fix:** Every 5 sessions, WebSearch each blocked/aging MT to check if Anthropic or community shipped a solution. MT-1 (visual grid), MT-5 (Pro bridge), and MT-8 (remote control) were all mostly solved externally.
- **First seen:** 2026-03-18
- **Last seen:** 2026-03-18
- **Files:** MASTER_TASKS.md scoring rules

---

### Run self-resolution scan at session START not END — Severity: 1 — Count: 1
- **Anti-pattern:** Running self-resolution scan during wrap, after priorities were already set and work done
- **Fix:** Add self-resolution scan to /cca-init for blocked MTs every 5 sessions — changes priority queue before work begins
- **First seen:** 2026-03-18
- **Last seen:** 2026-03-18
- **Files:** .claude/commands/cca-init.md

---

### PROJECT_INDEX.md is chronic Edit retry hotspot — Severity: 2 — Count: 25
- **Anti-pattern:** Attempting Edit on structured table files without reading current state first
- **Fix:** Always Read structured files (markdown tables, indexes) before Edit. Cost: ~500 tokens read. Saves: ~2000 tokens in retry loops (3-11 retries per failure)
- **Data:** 25/37 sessions (68%) have PROJECT_INDEX.md retries. SESSION_STATE.md at 16/37 (43%).
- **First seen:** 2026-03-17 (MT-10 batch analysis)
- **Last seen:** 2026-03-18 (Session 43 batch report)
- **Files:** PROJECT_INDEX.md, SESSION_STATE.md, any structured markdown table
- **Promoted:** 2026-03-18 -> CLAUDE.md Known Gotchas

---

### Cross-chat bridge files need explicit delivery protocol — Severity: 1 — Count: 1
- **Anti-pattern:** Writing a file to polymarket-bot/ and hoping the other chat reads it
- **Fix:** Use a shared inbox pattern (CROSS_CHAT_INBOX.md) with explicit request/delivery status. CCA writes CCA_TO_POLYBOT.md, Kalshi chat writes POLYBOT_TO_CCA.md. Check inbox at session start.
- **First seen:** 2026-03-18 (Session 45 — cross-chat system design)
- **Last seen:** 2026-03-18
- **Files:** CROSS_CHAT_INBOX.md, CCA_TO_POLYBOT.md, bridge-sync.sh

---

### Citation integrity — never cite unverified academic sources — Severity: 3 — Count: 1
- **Anti-pattern:** Writing "Per Author (Year), X is true..." without fetching or verifying the paper
- **Fix:** Verify via WebFetch (arXiv/DOI/SSRN URL) or WebSearch returning real title+authors+year. If unverified: write "[UNVERIFIED]" or drop entirely. Never present as fact.
- **First seen:** 2026-03-18 (Session 45 — CCA_TO_POLYBOT.md first draft had unverified citations)
- **Last seen:** 2026-03-18
- **Files:** any research output, planning files, cross-chat deliverables
- **Promoted:** 2026-03-18 -> `~/.claude/rules/learnings.md` (global)

---

### Inline doc updates eliminate wrap overhead — Severity: 1 — Count: 1
- **Anti-pattern:** Deferring all doc updates (SESSION_STATE, CHANGELOG, PROJECT_INDEX) to wrap step, creating a large batch update at end of session when context may be tight
- **Fix:** Update docs inline after each task commit. Wrap step then only needs to verify + minor additions. Session 48 had all docs current before wrap started — wrap was a 2-minute verification instead of a 15-minute rewrite.
- **First seen:** 2026-03-18 (Session 48)
- **Last seen:** 2026-03-18
- **Files:** SESSION_STATE.md, CHANGELOG.md, PROJECT_INDEX.md

---

### r/ClaudeAI classifier too loose — 76% NEEDLE rate — Severity: 1 — Count: 1
- **Anti-pattern:** nuclear_fetcher.classify_post returns NEEDLE for praise posts, memes, and off-topic discussions on r/ClaudeAI
- **Fix:** Needs r/ClaudeAI-specific keyword tuning in profiles.py, similar to S3 needle_ratio_cap for r/investing
- **First seen:** 2026-03-18 (Session 43, MT-9 Phase 4)
- **Last seen:** 2026-03-18
- **Files:** reddit-intelligence/profiles.py, reddit-intelligence/nuclear_fetcher.py

---

