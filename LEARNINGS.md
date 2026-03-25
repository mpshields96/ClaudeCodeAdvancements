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

### Ambiguous user negation = user wants to change course — Severity: 1 — Count: 1
- **Anti-pattern:** Interpreting "no /cca-wrap now" as "don't run /cca-wrap" when user meant "no [to continuing], run /cca-wrap now". Same with "No stop" meaning "No, stop [working]" not "No, don't stop".
- **Fix:** When user says "no [action]" in response to your continuing work, default to: they want to stop current activity and do the action. Parse "no X now" as "no, X now".
- **First seen:** 2026-03-24 (Session 156)
- **Last seen:** 2026-03-24
- **Files:** instruction following in all sessions

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

### CCA dual mission: 50% Kalshi profitability + 50% self-improvement as dev tool — Severity: 3 — Count: 1
- **Anti-pattern:** Treating CCA as 100% Kalshi-serving. Or treating CCA as 100% dev tooling with no financial connection. Both extremes are wrong.
- **Fix:** CCA has a 50/50 mission:
  - **50% Kalshi support:** Research papers, formulas, intelligence scanning that makes the Kalshi bot smarter and more profitable. ROI here = financial profit. Every delivery should include implementable code + expected edge size + validation protocol.
  - **50% CCA self-improvement:** The five frontiers (memory, spec, context, agent-guard, usage), YoYo self-learning framework, becoming a smarter version of itself as a development tool. Self-learning here means the CCA tool gets better at its own job — better scanning, better analysis, better infrastructure. Personal projects (iOS, academic writing) also served here.
- **Kalshi bot chats are 100% financial** — there is no 50/50 split for them. They optimize purely for profit.
- **CCA uses YoYo** as a strong framework for self-improvement while incorporating personal touch and projects.
- **Matthew directive (S52):** "Self-learning for CCA = 50% financial upgrades for Kalshi, 50% becoming smarter as a dev tool using YoYo framework."
- **First seen:** 2026-03-18 (Session 45 — Prime Directive established)
- **Last seen:** 2026-03-18 (Session 52 — Matthew clarified the 50/50 split)
- **Files:** KALSHI_PRIME_DIRECTIVE.md, self-learning/CLAUDE.md, KALSHI_INTEL.md

---

### Test DBs with synthetic trades need non-overlapping timestamps — Severity: 1 — Count: 1
- **Anti-pattern:** Creating "good" trades from date A and "bad" trades from date A+9 days, expecting ORDER BY created_at to keep them separate. With `timedelta(days=i)` the sets overlap and interleave.
- **Fix:** Push the second dataset's base_time past the first dataset's end. E.g., 60 trades from March 1 = ends ~May 1, so bad trades should start May 10+.
- **First seen:** 2026-03-19 (Session 60 — trade_reflector schema fix)
- **Last seen:** 2026-03-19
- **Files:** self-learning/tests/test_trade_reflector.py, any test with multiple synthetic trade batches

---

### Autonomous scan NEEDLE URLs must be persisted to a file — Severity: 1 — Count: 1
- **Anti-pattern:** MT-9 scan identified 8 NEEDLEs in S51 but URLs only existed in session context. Next session couldn't find them.
- **Fix:** autonomous_scanner.py (or the scan wrapper) should write NEEDLE URLs to a persistent file (e.g., `reddit-intelligence/pending_needles.jsonl`) immediately after classification. Fresh scan is a fine fallback but wastes the classification work.
- **First seen:** 2026-03-19 (Session 59)
- **Last seen:** 2026-03-19
- **Files:** reddit-intelligence/autonomous_scanner.py

---

### Regex pattern extraction needs overlap/span tracking — Severity: 1 — Count: 1
- **Anti-pattern:** Multiple regex patterns extracting from same text without dedup. "Remember that we always use X" matches both `remember that` and `always use` patterns, producing two overlapping extractions.
- **Fix:** Track matched character spans and skip any pattern whose match range overlaps with an already-captured span. Additionally check Jaccard similarity between extracted candidates (>=0.6 threshold).
- **First seen:** 2026-03-19
- **Last seen:** 2026-03-19
- **Files:** memory-system/hooks/capture_hook.py

---


### Cross-chat bridge location must be known — Severity: 1 — Count: 1
- **Anti-pattern:** Claiming scope boundary prevents cross-chat communication when bridge files exist at ~/.claude/cross-chat/ specifically for this purpose. Caused user frustration.
- **Fix:** Always check ~/.claude/cross-chat/ FIRST when cross-chat interaction is requested. CCA has READ permission on these files and WRITE permission to CCA_TO_POLYBOT.md in CCA's own directory.
- **First seen:** 2026-03-20
- **Last seen:** 2026-03-20
- **Files:** ~/.claude/cross-chat/POLYBOT_TO_CCA.md, CCA_TO_POLYBOT.md

---

### Kalshi support first, not last — Severity: 1 — Count: 1
- **Anti-pattern:** Spending entire session on CCA infrastructure then running out of context before doing Kalshi cross-chat work. The 1/3 Kalshi allocation gets squeezed when it's scheduled last.
- **Fix:** Start each session by checking Kalshi cross-chat requests FIRST (5-10 min), then proceed to CCA master tasks. Front-loading ensures the allocation is honored even if the session runs long.
- **First seen:** 2026-03-19
- **Last seen:** 2026-03-19
- **Files:** SESSION_STATE.md, KALSHI_ACTION_ITEMS.md

---

### Regex-based safety hooks are not trustworthy for unattended operation — Severity: 1 — Count: 1
- **Anti-pattern:** Assuming Python hooks parsing Bash commands with regex provide production-grade safety for overnight autonomous sessions. Regex can be bypassed by creative command construction.
- **Fix:** Regex hooks are useful for daytime supervised sessions (catch obvious mistakes). For true unattended safety, need OS-level sandboxing (Docker/VM with read-only mounts, network firewall rules). Don't let hook coverage create false confidence.
- **First seen:** 2026-03-19
- **Last seen:** 2026-03-19
- **Files:** agent-guard/bash_guard.py, memory: project_autonomous_loop.md

---

### paper_scanner.py evaluate() always 404s — Severity: 1 — Count: 1
- **Anti-pattern:** Calling `python3 self-learning/paper_scanner.py evaluate <semanticscholar_url>` to get paper details
- **Fix:** Use WebFetch on the arXiv URL directly (e.g., `https://arxiv.org/abs/XXXX.XXXXX`). The evaluate command hits a Semantic Scholar endpoint that returns 404 for all tested papers.
- **First seen:** 2026-03-19 (Session 70)
- **Files:** self-learning/paper_scanner.py, any academic research session

---

### paper_scanner.py search() low-signal for SE topics — Severity: 1 — Count: 1
- **Anti-pattern:** Relying solely on `paper_scanner.py search` for software engineering research topics (code review, technical debt, SWE agents). Returns tangential results.
- **Fix:** Use paper_scanner.py for its designed domains (prediction/agents/statistics/interaction). For SE topics, supplement with direct WebSearch targeting arXiv + specific conference proceedings (ICSE, FSE, ISSTA, NeurIPS, TOSEM). Fetch high-citation papers directly via WebFetch.
- **First seen:** 2026-03-19 (Session 70)
- **Files:** self-learning/paper_scanner.py

---

### Hivemind wrap: only coordinator should edit shared docs — Severity: 2 — Count: 1
- **Anti-pattern:** Multiple hivemind chats independently editing SESSION_STATE.md, CHANGELOG.md, PROJECT_INDEX.md — causes merge conflicts, duplicate entries, and inconsistent state
- **Fix:** Desktop coordinator owns ALL shared doc updates. CLI chats: run tests, commit code, send wrap summary via `cca_internal_queue.py send --from terminal --to desktop --subject "WRAP: ..."`. Desktop aggregates into one coherent wrap.
- **First seen:** 2026-03-20 (Session 72 — first hivemind wrap)
- **Last seen:** 2026-03-20
- **Files:** SESSION_STATE.md, CHANGELOG.md, LEARNINGS.md, PROJECT_INDEX.md, cca_internal_queue.py

---

### Regex pattern ordering matters in classifiers — Severity: 1 — Count: 1
- **Anti-pattern:** review_classifier.py had "fix" in bugfix pattern matching before style/logging patterns, causing "fix style" to classify as bugfix instead of style
- **Fix:** Order regex patterns from most specific to least specific. Remove overly broad terms like bare "fix" from patterns; use strong signals only (crash, null, exception, error).
- **First seen:** 2026-03-20 (Session 72 — review_classifier 5 test failures)
- **Last seen:** 2026-03-20
- **Files:** agent-guard/review_classifier.py

---

### Hivemind: check git status before building — Severity: 1 — Count: 1
- **Anti-pattern:** In a 3-chat hivemind sprint, starting to build a module without first checking if another chat already built and committed it.
- **Fix:** Run `git status` and `ls <module>/*.py` at the start of each task. If the file exists and tests pass, mark it done and move to next task.
- **First seen:** 2026-03-20 (S72 — fp_filter.py and tech_debt_tracker.py were already committed by Desktop chat before cli2 checked)
- **Last seen:** 2026-03-20
- **Files:** All agent-guard/ builds during hivemind sprints

### Regex keyword ordering matters for classifiers — Severity: 1 — Count: 1
- **Anti-pattern:** In a keyword-based classifier with ordered rules, placing generic keywords (fix, error) in a high-priority category causes false matches against lower-priority categories.
- **Fix:** Use strong/unambiguous indicators only in high-priority categories. Generic words like "fix" and "error" appear in style and testing contexts. Test every category against real examples before finalizing.
- **First seen:** 2026-03-20 (S72 — review_classifier.py had 5 failures because "fix" matched bugfix before style/logging)
- **Last seen:** 2026-03-20
- **Files:** agent-guard/review_classifier.py, any future keyword-based classifiers

### Check git log before building in loop-adjacent sessions — Severity: 1 — Count: 1
- **Anti-pattern:** Starting a context-resumed session without checking `git log -10` — the cca-loop may have committed files you're about to build, causing duplicate work and confusion.
- **Fix:** Run `git log --oneline -10` immediately after context recovery to see what was built during the gap. Then check `git ls-files --others` for untracked test files the loop pre-wrote.
- **First seen:** 2026-03-20 (S73 — satd_detector.py and senior_dev_hook.py were already committed by the loop; took time to discover)
- **Last seen:** 2026-03-20
- **Files:** All sessions resumed after context compression

### pytest not installed — use stdlib unittest — Severity: 2 — Count: 1
- **Anti-pattern:** Writing tests with `import pytest` and `@pytest.fixture` — pytest is not installed in this environment
- **Fix:** Always use `import unittest` and `unittest.TestCase`. Use `tempfile.mkdtemp()` + `setUp`/`tearDown` instead of `tmp_path` fixtures.
- **First seen:** 2026-03-20
- **Last seen:** 2026-03-20
- **Files:** tests/test_loop_health.py (converted), any future test file

### Built-but-not-wired modules — Severity: 1 — Count: 1
- **Anti-pattern:** Building a monitoring/tracking module (loop_health.record_session) but never calling it from the lifecycle it's supposed to track (cca-loop). Result: health dashboard shows "No data" despite the module being complete and tested.
- **Fix:** When building a tracking/monitoring module, the LAST step before commit must be verifying the call site exists. Check: "Where does this get called in production?" If nowhere — it's not done.
- **First seen:** 2026-03-20
- **Last seen:** 2026-03-20
- **Files:** loop_health.py (record_session), ~/.local/bin/cca-loop

### Shared skills need role-awareness for hivemind — Severity: 1 — Count: 1
- **Anti-pattern:** /cca-wrap, /cca-init, /cca-auto all assume single-chat mode. In hivemind, workers running these update shared docs (SESSION_STATE, PROJECT_INDEX) causing file conflicts.
- **Fix:** Add hivemind mode check to every shared skill. Workers (CCA_CHAT_ID=cli1/cli2) skip shared doc updates and send summaries via cca_comm.py instead.
- **First seen:** 2026-03-20
- **Last seen:** 2026-03-20
- **Files:** ~/.claude/commands/cca-wrap.md, cca-init.md, cca-auto.md

### Import regex must allow leading whitespace — Severity: 1 — Count: 1
- **Anti-pattern:** `^import X` or `^from X import` misses imports inside try/except blocks (indented)
- **Fix:** Use `^\s*import` and `^\s*from` with MULTILINE flag to catch imports at any indentation level
- **First seen:** 2026-03-20 (Session 78 — coherence_checker missed code_quality_scorer's import of satd_detector)
- **Last seen:** 2026-03-20
- **Files:** agent-guard/coherence_checker.py ImportDependencyCheck

### fp_filter must run BEFORE counting, not after — Severity: 1 — Count: 1
- **Anti-pattern:** Running SATD detection, counting results, then filtering. Metrics show pre-filter counts (inflated for test/vendored files).
- **Fix:** Filter SATD findings BEFORE computing satd_total and satd_high metrics. Vendored files should show satd_total=0, not satd_total=3.
- **First seen:** 2026-03-20 (Session 79 — initial fp_filter integration had wrong order)
- **Last seen:** 2026-03-20
- **Files:** agent-guard/senior_review.py

### Mock post data must include all classify_post required fields — Severity: 1 — Count: 1
- **Anti-pattern:** Creating mock Reddit posts for autonomous_scanner tests with only basic fields (id, title, score, etc.) — missing `is_self` and `selftext` that `classify_post()` requires.
- **Fix:** Always include `is_self` and `selftext` in mock post dicts when tests will pass through `classify_posts()` -> `classify_post()`.
- **First seen:** 2026-03-20 (Session 84)
- **Last seen:** 2026-03-20
- **Files:** reddit-intelligence/tests/test_autonomous_scanner.py

### Message ID hashes must include ALL distinguishing fields — Severity: 2 — Count: 1
- **Anti-pattern:** `_make_id(sender, subject)` hashing only sender + subject + timestamp. Broadcast messages to 3 targets in the same second produce identical IDs, causing `acknowledge(msg_id)` to only ack the first match.
- **Fix:** Include ALL distinguishing fields in the hash: `_make_id(sender, target, subject)` with `sha256(sender:target:subject:timestamp)`. Apply to all queue files consistently.
- **First seen:** 2026-03-20 (Session 89 — found via deep testing)
- **Last seen:** 2026-03-20
- **Files:** cca_internal_queue.py, cca_hivemind.py, cross_chat_queue.py

---

### Worker front-loading: one task per message, not combined — Severity: 2 — Count: 1
- **Anti-pattern:** Combining tasks in a single launch message ("TASK 1 (PRIMARY): do X. TASK 2 (SECONDARY): do Y"). Worker picks the easiest and wraps.
- **Fix:** Send primary task via `launch_worker.sh "primary task only"`. Queue secondary tasks separately via `python3 cca_comm.py task cli1 "secondary task"` AFTER the worker starts. Worker loops on inbox after each task and finds secondary tasks.
- **First seen:** 2026-03-21 (Session 96)
- **Last seen:** 2026-03-21
- **Files:** launch_worker.sh, cca_comm.py, /cca-auto-desktop

---

### AppleScript keystroke tab creation is fragile — Severity: 2 — Count: 1
- **Anti-pattern:** Using `keystroke "t" using command down` + `do script ... in front window` in AppleScript to open Terminal tabs. Fails with -1719 "Invalid index" when Terminal has no windows.
- **Fix:** Use `open -a Terminal <tempscript.sh>` which always works. Creates a new window instead of a tab, but is 100% reliable regardless of Terminal state.
- **First seen:** 2026-03-21 (Session 108)
- **Last seen:** 2026-03-21
- **Files:** launch_kalshi.sh, launch_worker.sh

---

### Refactoring from inline to registry requires dual-path mocking — Severity: 1 — Count: 1
- **Anti-pattern:** Extracting inline code from module A into module B breaks tests that mock `A.function` — the real code now runs via `B.function` which isn't mocked.
- **Fix:** Update test mock helpers to patch both the old path (`A.function`) and the new path (`B.function`). This maintains backwards compatibility during the transition.
- **First seen:** 2026-03-21 (Session 108)
- **Last seen:** 2026-03-21
- **Files:** self-learning/tests/test_reflect.py, test_reflect_extended.py

---

### Desktop autoloop must NOT run from within an active Claude Code session — Severity: 2 — Count: 1
- **Anti-pattern:** Running `./start_desktop_autoloop.sh` from within a Claude Code CLI session. The script uses AppleScript to control Claude.app — running it inside the very app it's trying to control creates recursive conflicts.
- **Fix:** The autoloop script must be run from a **separate Terminal.app window** (external orchestrator pattern). The script controls Claude.app from outside; the Claude Code sessions are what it creates and monitors. Never run the orchestrator from inside the thing being orchestrated.
- **Correct supervised trial pattern:** (1) Open a separate Terminal window, (2) `cd /Users/matthewshields/Projects/ClaudeCodeAdvancements`, (3) `./start_desktop_autoloop.sh --max-iterations 2`. OR: manually use the Claude desktop app "+ New session" button and paste the resume prompt.
- **Standing note:** Terminal Accessibility permission is GRANTED (Matthew confirmed S135). Do not re-ask.
- **First seen:** 2026-03-23 (Session 135)
- **Last seen:** 2026-03-23
- **Files:** desktop_autoloop.py, start_desktop_autoloop.sh

---

### Claude Desktop App UI Layout — Critical Reference for Autoloop — Severity: 2 — Count: 1
- **The app is `Claude` (com.anthropic.claudefordesktop)** — one app hosts Chat, Cowork, AND Code.
- **Three tabs in top-center island** (left to right):
  1. **Chat** — Claude Pro conversational AI. NOT us. Never go here.
  2. **Cowork** — Collaborative mode. NOT us. Never go here.
  3. **Code** — Claude Code (CLI-powered coding agent). **ALWAYS be here. ALWAYS click back here if not.**
- **"+ New session" button** — Top-left corner of the sidebar. Opens a new Code session window.
- **New session defaults:** Opus 4.6 model, Bypass permissions ON, project folder linked to ClaudeCodeAdvancements (linked to GitHub).
- **Left sidebar:** Session history list (named sessions, today/yesterday groupings).
- **Bottom bar:** `+ Bypass permissions` | model selector (`Opus 4.6 (1M context)`) | project folder path.
- **Git status bar:** Shows branch, diff stats, "Create PR" button.
- **For the autoloop:** The script must navigate to Code tab, click "+ New session", paste resume prompt. AppleScript must target the correct tab. If landed on Chat or Cowork tab, click Code tab first.
- **Recovery pattern:** If ever not in Code tab, click the "Code" tab (far right of the 3-tab island at top center). This is the ONLY tab CCA sessions should ever be in.
- **First seen:** 2026-03-23 (Session 135) — Matthew screenshot walkthrough
- **Last seen:** 2026-03-23
- **Files:** desktop_automator.py, desktop_autoloop.py, DESKTOP_AUTOLOOP_SETUP.md


### Electron accessibility tree lacks tab groups — Severity: 2 — Count: 2
- **Anti-pattern:** Using `first tab group of first window` in AppleScript to detect Claude.app tabs. Returns "Invalid index" error because Electron doesn't expose tab bar as standard macOS tab group.
- **Fix:** Need alternative approach. Options: (1) keyboard shortcut if one exists, (2) menu bar navigation, (3) enumerate all UI elements and find by description/name, (4) coordinate-based click as last resort. `ensure_code_tab()` currently proceeds optimistically when detection fails — but this means it doesn't actually switch tabs.
- **First seen:** 2026-03-23 (Session 137)
- **Last seen:** 2026-03-23 (Session 138) — trigger landed on Chat tab instead of Code
- **Files:** desktop_automator.py (get_active_tab, ensure_code_tab, click_code_tab)

### CCA autoloop is session-internal not external — Severity: 2 — Count: 1
- **Anti-pattern:** Running autoloop from Terminal.app via `start_desktop_autoloop.sh`. Terminal.app subprocess context means AppleScript targets wrong app (Terminal is frontmost, not Claude).
- **Fix:** Autoloop trigger runs FROM WITHIN a CCA session as the final step of /cca-wrap (Step 10). The CCA session calls `python3 autoloop_trigger.py` which uses AppleScript to activate Claude.app, click "+ New session", and paste the resume prompt. Each session spawns the next.
- **First seen:** 2026-03-23 (Session 138) — Matthew directive after Terminal.app approach failed
- **Last seen:** 2026-03-23
- **Files:** autoloop_trigger.py, .claude/commands/cca-wrap.md (Step 10)

### Python default parameter capture binds at definition time — Severity: 1 — Count: 1
- **Anti-pattern:** `def f(state_file: str = COOLDOWN_STATE_FILE)` captures the module-level value when the function is defined. If tests later patch `COOLDOWN_STATE_FILE`, the function still uses the original value.
- **Fix:** Use `def f(state_file: str = None): if state_file is None: state_file = COOLDOWN_STATE_FILE`. This reads the module-level variable at call time, respecting patches.
- **First seen:** 2026-03-24 (Session 144) — cooldown tests failed because patched state file wasn't used
- **Last seen:** 2026-03-24
- **Files:** context-monitor/session_notifier.py (_check_cooldown, _record_send)

### Effort scorer threshold tests are fragile to file growth — Severity: 1 — Count: 2
- **Anti-pattern:** `self.assertLess(result.complexity, 40)` — hardcoded threshold breaks when the target file legitimately grows with new features.
- **Fix:** Use wider thresholds or relative checks (e.g., "complexity should be < 2x the number of functions"). Broke twice this session (40 -> 60 -> 85) as session_notifier.py grew.
- **First seen:** 2026-03-24 (Session 144)
- **Last seen:** 2026-03-24
- **Files:** agent-guard/tests/test_effort_scorer.py (test_session_notifier_improved)

### /cca-wrap Step 10 (autoloop trigger) consistently skipped — Severity: 3 — Count: 3+
- **Anti-pattern:** Claude completes Steps 1-9 of /cca-wrap, outputs the resume prompt, then STOPS — never executing Step 10 (`python3 autoloop_trigger.py`). This breaks the self-sustaining loop.
- **Root cause:** The /cca-wrap skill file has 10 steps but Step 10 is after the resume prompt (Step 9), which feels like a natural stopping point. Context pressure at wrap time makes Claude eager to finish.
- **Fix:** Step 10 MUST run after Step 9. The autoloop trigger is the FINAL action. The session is NOT complete until the trigger fires. If context is critical, still run `python3 autoloop_trigger.py` — it's a single command.
- **First seen:** S137 (2026-03-23)
- **Last seen:** S148 (2026-03-24)
- **Files:** `.claude/commands/cca-wrap.md` (Step 10), `autoloop_trigger.py`
- **Promoted:** 2026-03-24 -> ~/.claude/rules/ and CLAUDE.md Known Gotchas

### Priority picker aging_rate=0 blindspot — Severity: 2 — Count: 1
- Anti-pattern: Completed MTs with aging_rate=0 become invisible to dust detection
- Fix: growth_score() adds dust_bonus = min(sessions_since_touch * 0.1, 5.0)
- Also: ARCHIVED status for MTs Matthew explicitly kills — removes noise from dust report
- First seen: 2026-03-25 (S160)
- Last seen: 2026-03-25
- Files: priority_picker.py

### Keyword matching must exclude URLs — Severity: 2 — Count: 1
- Anti-pattern: mt_originator coverage check matched "github" in URLs against MT-11's "github" keyword
- Fix: search_text = f"{f.title} {f.frontier}" — exclude URL from keyword matching
- First seen: 2026-03-25 (S160)
- Last seen: 2026-03-25
- Files: mt_originator.py

### Claude Control exists for MT-1 — Severity: 1 — Count: 1
- Claude Control (github.com/sverrirsig/claude-control) is a real, actively maintained macOS app
- v0.10.0 released 2026-03-24, Electron+Next.js, auto-discovers Claude Code sessions
- Card dashboard with real-time status, git state, permission approval
- DMG install, works with Terminal.app and iTerm2
- First seen: 2026-03-25 (S160)

### Matthew MT archival decisions (S160) — Severity: 1 — Count: 1
- Archived 8 MTs: MT-5, MT-8, MT-16, MT-19, MT-23, MT-25, MT-31, MT-34
- Kept MT-1 (Maestro — wants visual grid)
- Created MT-42 (Kalshi Smart Money Copytrading — follow others' edges via order flow)
- "I'm okay on all others" = archive everything except what's explicitly wanted

### CCA must NEVER touch model selection — Severity: 2 — Count: 2
- **Anti-pattern:** CCA autoloop or session commands changing the model type in Claude.app UI
- **Fix:** CCA does NOT touch model selection. Matthew sets it manually. Period.
- **Context:** Model changed from "Opus 4.6 (1M context)" back to "Opus 4.6" — Matthew flagged S161
- **First seen:** 2026-03-23 (S134 directive)
- **Last seen:** 2026-03-25 (S161 — Matthew reaffirmed)
- **Files:** autoloop_trigger.py, desktop_automator.py, /cca-init, /cca-auto, /cca-wrap

### Run /cca-wrap proactively — Severity: 1 — Count: 1
- **Anti-pattern:** Working continuously without wrapping until Matthew reminds you
- **Fix:** Run /cca-wrap at natural stopping points (after completing a major task chain)
- **First seen:** 2026-03-25 (S161)

### Anthropic features that burn tokens — standing policy — Severity: 2 — Count: 1
- **Anti-pattern:** Opting into Anthropic features that charge tokens for things CCA hooks do for free
- **Fix:** Never enable Auto Mode (Sonnet classifier per tool call). Our hook-based guards are zero-cost and deterministic.
- **Context:** Auto Mode uses Sonnet 4.6 classifier on every tool call, charges tokens. CCA hooks: <50ms, zero tokens.
- **First seen:** 2026-03-25 (S161)
- **Files:** Any settings.json or permission mode configuration

### Kalshi API has no trader attribution — Severity: 1 — Count: 1
- Orderbook: aggregate bids only (price + quantity). No trader IDs, no individual orders.
- Trades: public tape with ticker/price/quantity/timestamp. No buyer/seller identity.
- Portfolio endpoints: YOUR data only (authenticated).
- MT-42 copytrading NOT feasible on Kalshi. Reframe as order flow signal detection.
- First seen: 2026-03-25 (S161)

### Git log in generated docs causes false positive assertions — Severity: 1 — Count: 1
- **Anti-pattern:** Asserting `assertNotIn("X", content)` on full generated output that includes git log
- **Fix:** Scope assertions to the relevant section (e.g., split on "## RECENT COMMITS" first)
- **First seen:** 2026-03-25 (S175)
- **Files:** tests/test_handoff_generator.py

### /model command only works in Terminal.app CLI, not desktop Electron app — Severity: 2 — Count: 1
- **Anti-pattern:** Typing `/model claude-opus-4-6[1m]` in the desktop Claude.app Code tab
- **Fix:** Model selection in desktop Electron app must be done through the UI, not CLI commands. CCA does NOT touch model selection — Matthew sets manually (S161 reaffirmed). In Terminal.app CLI sessions, `/model` works normally.
- **First seen:** 2026-03-25 (S175)
- **Files:** autoloop_trigger.py, desktop_automator.py, CLAUDE.md

### TODAYS_TASKS.md overrides priority_picker for daily task selection — Severity: 2 — Count: 1
- **Anti-pattern:** Using priority_picker or MASTER_TASKS to select next task when TODAYS_TASKS.md has uncompleted items
- **Fix:** Always read TODAYS_TASKS.md FIRST. Work ALL TODO items there before falling through to priority_picker. Matthew updates this file daily — follow it, don't second-guess it. Wired into cca-init, cca-auto, cca-auto-desktop, cca-wrap, slim_init, resume_generator, CLAUDE.md.
- **First seen:** 2026-03-25 (S178)
- **Files:** TODAYS_TASKS.md, CLAUDE.md, cca-init.md, cca-auto.md, slim_init.py

### Background agents lost on context compaction — recovery costs tokens — Severity: 1 — Count: 1
- **Anti-pattern:** Spawning 3+ background agents that take >5 min each while also doing foreground work that grows context toward compaction
- **Fix:** Either (a) do foreground-only work and wait for agents, or (b) spawn agents and do minimal foreground work to avoid triggering compaction. If compaction kills agents, re-run them — budget for the re-run cost.
- **First seen:** 2026-03-25 (S178)
- **Files:** N/A (general workflow pattern)
