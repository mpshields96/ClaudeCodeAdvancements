# /cca-nuclear — Autonomous Deep-Dive Session

This is a SELF-CONTAINED autonomous command. When invoked in a fresh Claude Code session,
it knows everything — context, plan, open work, Maestro status, self-learning architecture.

No other commands need to be run first. No questions need to be asked.
Just type `/cca-nuclear` and walk away.

## Subreddit Targeting

**Three modes:**

1. **Default:** `r/ClaudeCode` (when no argument given)
2. **Custom subreddit:** `/cca-nuclear r/LocalLLaMA` or `/cca-nuclear r/MachineLearning`
3. **Autonomous mode:** `/cca-nuclear autonomous` — auto-picks the highest-priority subreddit using the autonomous scanner

### Autonomous Mode (`/cca-nuclear autonomous`)

When `$ARGUMENTS` is "autonomous" or "auto":

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/autonomous_scanner.py scan --json
```

This will:
1. Auto-pick the highest-priority subreddit (staleness + yield + never-scanned bonus)
2. Fetch and classify posts
3. Return JSON with report + NEEDLE/MAYBE/HAY post lists

Parse the JSON output to get `TARGET_SUB` and the post queue. Skip Phase 1 (fetch already done).
Go directly to Phase 2 (progress tracker) and Phase 3 (review) using the returned post lists.

To scan a specific domain (e.g., trading subs for Kalshi research):
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/autonomous_scanner.py scan --domain trading --json
```

After reviewing all posts, the autonomous scanner will record the scan in the registry
so next time it picks a different (staler) subreddit. This creates a rotation:
each autonomous session scans whichever sub is most overdue.

### Manual Mode (default or custom sub)

When `$ARGUMENTS` is provided and non-empty (and not "autonomous"/"auto"), use it as the target subreddit.
All progress files, queue files, and reports are namespaced by subreddit slug:
- Queue: `nuclear_queue_<slug>.json` (e.g., `nuclear_queue_localllama.json`)
- Progress: `nuclear_progress_<slug>.json`
- Report: `NUCLEAR_REPORT_<slug>.md`

For the default r/ClaudeCode, files keep their original names (no suffix) for backwards
compatibility: `nuclear_queue.json`, `nuclear_progress.json`, `NUCLEAR_REPORT.md`.

**Determine the target subreddit at the start of every run:**
```
If "$ARGUMENTS" is "autonomous" or "auto":
    → Use autonomous scanner (see above)
Elif "$ARGUMENTS" is non-empty:
    TARGET_SUB = "$ARGUMENTS"    (e.g., "r/LocalLLaMA")
    FILE_SUFFIX = "_" + slug     (e.g., "_localllama")
Else:
    TARGET_SUB = "r/ClaudeCode"
    FILE_SUFFIX = ""             (backwards compatible)
```

To compute the slug programmatically:
```bash
python3 -c "
import re, sys
sub = re.sub(r'^/?r/', '', '$ARGUMENTS'.strip()) if '$ARGUMENTS'.strip() else ''
slug = re.sub(r'[^a-z0-9]', '', sub.lower())
suffix = f'_{slug}' if slug and slug != 'claudecode' else ''
print(suffix)
"
```

Then use `FILE_SUFFIX` throughout all Phase 1-4 file paths below.

---

## Token Budget Design

This command is SPECIFICALLY DESIGNED to not nuke your token usage:

1. **Phase 1 (fetch + triage)** = pure Python, ZERO Claude tokens. The nuclear_fetcher.py
   script hits Reddit's JSON API directly and classifies 150 posts without any LLM calls.

2. **Phase 3 (review)** uses condensed 1-3 line verdicts instead of full /cca-review format.
   A full review burns ~2000 tokens per post. Condensed format burns ~200 tokens per post.
   That's 10x savings across 100+ posts.

3. **40% context ceiling** — the command stops automatically at 40% context usage, saves
   progress, and resumes next session. You never hit the degradation zone.

4. **HAY auto-skip** — ~30% of posts are classified as HAY (memes, humor, rants) and are
   never read at all. Another ~20% get FAST-SKIP at the title level.

5. **Dedup** — posts already in FINDINGS_LOG.md are excluded before any tokens are spent.

**Estimated token cost per session:** ~50-60k tokens to process one batch of 40-50 posts
(of which ~25 get deep-read, ~15 get fast-skipped). That's well within a single session's
budget and leaves room for the report generation at the end.

**Estimated sessions to complete:** 2-3 sessions to review all ~110 NEEDLE + MAYBE posts.

---

## PHASE 0 — Full Context Load (do this FIRST, silently)

Read these files to understand the full project state:

```bash
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/FINDINGS_LOG.md
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE.md
```

Key context you need:
- **CCA** = ClaudeCodeAdvancements — research + build next advancements for Claude Code
- **5 Frontiers**: Memory, Spec-Driven Dev, Context Health, Agent Guard, Usage Dashboard
- **483+ tests** across 14+ suites — run `python3 <test_file>` to verify
- **NEVER access files outside** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/`
- **NEVER expose** API keys, account balances, trade data, or financial info

### Active Projects & Open Work

**1. Nuclear Reddit Deep-Dive (THIS COMMAND — primary task)**
- Systematically review top 100-150 posts from r/ClaudeCode (Top > Year)
- Extract every actionable pattern, tool, and insight for the 5 frontiers
- Classifier auto-triages: NEEDLE (read fully), MAYBE (scan title), HAY (skip)
- Progress tracked in `nuclear_progress.json` — resumes across sessions

**2. Maestro Desktop App (blocked — retry each session)**
- Maestro v0.2.4 = Rust + React + Tauri native macOS app for multi-session management
- Last session: crashed on macOS 15.6 beta SDK (`_NSUserActivityTypeBrowsingWeb` symbol missing)
- Each nuclear session should check if Maestro has released a fix:
  ```bash
  curl -s "https://api.github.com/repos/nichochar/maestro/releases/latest" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Latest: {d.get(\"tag_name\",\"unknown\")} ({d.get(\"published_at\",\"?\")[:10]})')" 2>/dev/null || echo "Could not check Maestro releases"
  ```
  If version > v0.2.4, notify: "Maestro has a new release — worth retrying the install."
  Otherwise, skip silently.

**3. Self-Learning Polybot Architecture (designed, not yet built in Polybot)**
- Journal + strategy feedback loop for Kalshi bot — YoYo pattern adapted for trading
- PROFIT IS THE ONLY OBJECTIVE — never accept break-even or losing strategies
- Architecture is in SESSION_STATE.md "MASTER PLAN Part 2"
- If nuclear scan finds self-learning/autonomous agent posts, flag them as POLYBOT-RELEVANT

**4. Uncommitted Work (sessions 10-13)**
- There may be uncommitted changes. Note but don't commit during nuclear scan.

**5. Path-Scoped Rules (.claude/rules/)**
- 5 glob-scoped rule files exist for each frontier module
- Flag posts about CLAUDE.md organization as RULES-RELEVANT

### Quick Test Verification
```bash
python3 memory-system/tests/test_memory.py 2>&1 | tail -1
python3 spec-system/tests/test_spec.py 2>&1 | tail -1
python3 context-monitor/tests/test_meter.py 2>&1 | tail -1
python3 reddit-intelligence/tests/test_nuclear_fetcher.py 2>&1 | tail -1
```

---

## PHASE 1 — Fetch and Triage (zero Claude tokens)

Use `TARGET_SUB` (determined above) in place of the hardcoded subreddit:

```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/nuclear_fetcher.py \
    TARGET_SUB 150 year \
    --min-score 30 \
    --dedup /Users/matthewshields/Projects/ClaudeCodeAdvancements/FINDINGS_LOG.md \
    --classify \
    --output /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/findings/nuclear_queue{FILE_SUFFIX}.json
```

Then print summary:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/nuclear_fetcher.py \
    TARGET_SUB 150 year \
    --min-score 30 \
    --dedup /Users/matthewshields/Projects/ClaudeCodeAdvancements/FINDINGS_LOG.md \
    --classify \
    --summary 2>&1 | head -80
```

Report:
```
NUCLEAR SCAN: TARGET_SUB
Posts fetched: [N] | After dedup: [M] | NEEDLE: [X] | MAYBE: [Y] | HAY: [Z]
Maestro: [new release / still v0.2.4]
Tests: [pass count]
Resuming from: [post N / fresh start]
```

---

## PHASE 2 — Load or Create Progress Tracker

```bash
cat /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/findings/nuclear_progress{FILE_SUFFIX}.json 2>/dev/null || echo '{"reviewed": [], "session": 0, "stats": {"build": 0, "adapt": 0, "reference": 0, "skip": 0}}'
```

If resuming: skip already-reviewed post IDs. Report how many are left.

---

## PHASE 3 — Process Posts (batches of 10-15)

Process NEEDLE posts first (highest score to lowest), then MAYBE. Never HAY.

### For each post:

**3a. Fast-Scan Title Check**
If the title clearly indicates meme/humor/rant/complaint/comparison/pricing/first-time:
```
FAST-SKIP: [title] — [reason]
```

**3b. Deep Read (posts that pass title check)**
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "POST_URL"
```
Read EVERY comment — best insights are buried 3-4 levels deep.

**3c. Condensed Verdict**

SKIP: `SKIP: [title] ([score] pts) — [5-word reason]`

REF: `REF: [title] ([score] pts) — [frontier] — [1-sentence summary]`

ADAPT/BUILD:
```
[ADAPT/BUILD]: [title] ([score] pts) — [frontier]
STEAL: [specific pattern, tool, or approach to take]
```

**3d. Special Flags**
- Self-learning/autonomous agent posts → `POLYBOT-RELEVANT`
- Multi-session/tmux/workspace posts → `MAESTRO-RELEVANT`
- CLAUDE.md organization posts → `RULES-RELEVANT`
- Token usage/cost posts → `USAGE-DASHBOARD`

**3e. After Each Batch**

1. Append results to FINDINGS_LOG.md:
   `[YYYY-MM-DD] [VERDICT] [Frontier] Description — URL`

2. Update `nuclear_progress{FILE_SUFFIX}.json` with reviewed IDs and stats

3. Print: `NUCLEAR: [N]/[total] | BUILD:[B] ADAPT:[A] REF:[R] SKIP:[S] | Polybot:[P]`

4. If context > 40%: STOP. Save progress. Generate interim report.

5. Otherwise: continue automatically. Do NOT ask user between batches.

---

## PHASE 4 — Generate Report

Write to `reddit-intelligence/findings/NUCLEAR_REPORT{FILE_SUFFIX}.md`:

```markdown
# Nuclear Deep-Dive Report: TARGET_SUB Top Year
Generated: [date]
Posts scanned: [N] of [total] | Sessions used: [N]

## Summary Stats
| Metric | Count |
|--------|-------|
| Posts fetched | [N] |
| Deduped | [N] |
| BUILD | [N] |
| ADAPT | [N] |
| REFERENCE | [N] |
| SKIP | [N] |
| Polybot-relevant | [N] |

## BUILD Candidates (ranked by score x feasibility)
### 1. [Title] ([score] pts)
- Frontier: [1-5]
- What to build: [description]
- URL: [link]

## ADAPT Patterns (grouped by frontier)
### Frontier 1-5: [grouped findings]

## Polybot-Relevant Findings
[Posts useful for self-learning journal / strategy loop]

## Maestro-Relevant Findings
[Posts about multi-session management]

## Recurring Pain Points
| Pain Point | Mentions | Frontier |
|-----------|----------|---------|

## Recommendations for Next Session
1. [Top BUILD to implement]
2. [Key ADAPT to incorporate]
3. [Maestro: retry / wait]
```

---

## Rules (NON-NEGOTIABLE)

- **Fully autonomous** — do NOT ask between batches. Just keep going.
- NEEDLEs first, then MAYBEs. Never HAY.
- Condensed verdicts (1-3 lines), not full /cca-review
- Stop at 40% context — save progress, generate interim report
- **REVIEW ONLY** — no code changes except FINDINGS_LOG and progress files
- Log every result to FINDINGS_LOG.md (permanent record)
- Update progress after every batch (crash recovery)
- Note GitHub repo URLs but don't WebFetch during scan
- Always dedup against FINDINGS_LOG before starting
- **NEVER expose** API keys, balances, or financial info
- End EVERY response with `Advancement tip: ...`

---

## Resume Protocol

When `nuclear_progress{FILE_SUFFIX}.json` exists:
1. Load progress + queue (skip re-fetch if queue is <24h old)
2. Report: "Resuming. [M]/[N] reviewed. [B] BUILD, [A] ADAPT found."
3. Check Maestro for new release
4. Skip to next unreviewed post, continue PHASE 3

When entire queue is processed:
1. Generate final NUCLEAR_REPORT.md
2. Print top 5 recommendations
3. Say: "Nuclear scan complete. Run /cca-auto to implement top BUILD candidates."
