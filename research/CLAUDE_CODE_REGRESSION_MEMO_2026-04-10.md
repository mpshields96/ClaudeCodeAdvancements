# Claude Code Regression Memo — 2026-04-10

Purpose: turn the current Claude Code quality blowup into an operator memo CCA can
act on instead of a vague frustration spiral.

Scope:
- Matthew's S294 urgent handoff of 12 Reddit URLs
- Spot-check review of representative posts on 2026-04-10
- CCA-local observations from recent handoff/state-discipline failures

This is a triage memo, not the final exhaustive CCA review. CCA should still run the
full `/cca-review` or `cca-reviewer` batch on the full 12-link set.

---

## Bottom-Line Assessment

The community signal is not "one angry thread." It is a clustered regression report
with recurring failure modes:

1. less visible reasoning / shallower effort
2. more shortcut-taking and superficial answers
3. more prompt misses, hallucinated behavior, and unfinished work
4. worse latency / API stability / token burn efficiency
5. users adapting with manual flags and workflow workarounds just to recover prior quality

Even if some claims are overstated or speculative, the operational conclusion is the
same: **CCA should treat Claude Code as a more volatile and less trustworthy agent than it
was 1-2 months ago.**

That does NOT mean CCA is useless.
It means the harness must get stricter.

---

## Evidence Patterns From Today's Posts

### Pattern 1 — Users are reporting shallower thinking, not just stricter limits

Representative posts:
- `PSA: Getting 'Old Opus' back`
- `dug into the browser console on claude.ai and found the flags that control how much opus 4.6 actually thinks`
- `Claude Code's "max effort" thinking has been silently broken since v2.0.64`
- `Anthropic made Claude 67% dumber...`

Observed theme:
- users believe "thinking depth" is being reduced dynamically
- users are trying config/env workarounds to recover prior behavior
- "adaptive" or auto-thinking settings are widely suspected to be hurting hard tasks

CCA implication:
- high-effort tasks should no longer assume the model is actually using the requested effort
- if a task is complex, CCA must explicitly verify the work product, not infer competence from the model setting

### Pattern 2 — More shortcut behavior and lower-quality first drafts

Representative posts:
- `Claude Code has become so superficial and stupid...`
- `2 months ago Opus 4.6 built my tool in 15 min... today it took almost 2 hours and has multiple bugs`
- `Canceled my 20x subscription. The drop in quality answers is beyond limits.`

Observed theme:
- users describe more back-and-forth to reach the same result
- first passes are more incomplete
- the model misses details that older sessions handled cleanly

CCA implication:
- older workflows that depended on "one strong pass" are now higher risk
- CCA should bias toward narrower task slices, explicit acceptance criteria, and immediate post-change verification

### Pattern 3 — Behavioral weirdness and hallucinated failure modes

Representative posts:
- `Claude ignored my prompt entirely, hallucinated prompt injection...`
- `Claude just died?`
- `Things are getting really bad`

Observed theme:
- fresh-session derailments
- API / session instability
- token burn wasted on failed or malformed turns

CCA implication:
- long brittle sessions are now more expensive
- CCA should favor short bounded loops with earlier wrap/compact boundaries and stronger fail-safe behavior

### Pattern 4 — Trust erosion is now a product problem, not just a tuning problem

Representative posts:
- `The current state of Claude Code Opus 4.6. Today I have unsubscribed from my MAX plan.`
- `What would you do if somebody confirmed...`
- `Anthropic made Claude 67% dumber...`

Observed theme:
- users are questioning transparency, not just quality
- people are making subscription downgrade/cancel decisions
- users are comparing Claude against alternatives on reliability, not just benchmark quality

CCA implication:
- CCA should treat provider volatility as an architectural risk
- workflows must be portable enough that Matthew is not trapped by one provider's regression cycle

---

## What CCA Should Change Immediately

### 1. Raise verification density

New default for meaningful work:
- require tests or direct verification after every nontrivial change
- require file-read verification before file edits on critical paths
- require "what changed / what was verified / what remains unverified" in every wrap

Reason:
- if the model is shortcutting more often, the harness has to catch silent slop faster

### 2. Shrink task grain

New default:
- one function, one file, one narrow objective at a time when possible
- avoid "implement the whole feature" unless the feature is already decomposed
- break work into "data", "logic", "wiring", "docs" passes

Reason:
- degraded agents fail harder on broad tasks than on narrow ones

### 3. Shorten session trust horizon

New default:
- compact or restart earlier
- do not let one session accumulate too many loosely related tasks
- treat stale context as hostile, not harmless

Reason:
- multiple user reports point to context/effort instability and drift across long sessions

### 4. Make reviewer mode mandatory on important work

New default:
- Codex reviews architecture, tests, and state hygiene
- CCA does not self-certify complex work without a second-pass check when feasible
- on risky tasks, separate implementer and reviewer roles

Reason:
- CCA remains useful, but the current environment no longer justifies single-agent trust

### 5. Prefer explicit operator controls over hidden automation

New default:
- expose env flags and model settings in session notes
- log whether adaptive/1M/effort controls were active
- prefer deterministic helper scripts and pure functions over vague agent improvisation

Reason:
- today's posts suggest users are recovering quality by overriding hidden defaults

---

## CCA Frontier Mapping

### Frontier 1 — Memory / state systems

Helps with:
- recovering intent after compaction/restarts
- preserving acceptance criteria and constraints explicitly
- preventing the agent from "forgetting the plot"

Needed adaptation:
- memory should store tighter task contracts and known regression patterns
- bad-state detection matters more than passive recall

### Frontier 4 — Agent guard / quality controls

Most directly relevant frontier right now.

Needed adaptation:
- stronger anti-shortcut checks
- explicit detection of "claimed done without verification"
- stronger review gates for broad edits, empty assurances, or no-test completions

### Get More Bodies pillar

Still valuable, but only if the extra bodies are role-separated:
- one worker
- one reviewer
- one coordinator

More agents without stronger verification just multiplies garbage faster.

---

## Recommended Operating Posture For Matthew

Short-term posture:
- keep using CCA/Claude only with a stricter harness
- keep Codex in active reviewer/backup-implementer mode
- do not assume yesterday's Claude quality is today's Claude quality

Subscription posture:
- if Matthew is on the fence before the April 14 renewal, the rational move is **do not pay for trust that currently has to be rebuilt every session**
- that means downgrade or cancel is reasonable unless the next few days show stable recovery under real usage
- if staying subscribed, treat it as paying for a volatile tool that needs guardrails, not a dependable primary agent

This is not a benchmark verdict.
It is an operator-risk verdict.

---

## Concrete Next Actions For CCA

1. Review all 12 URLs from `S294_HANDOFF_URGENT.md`
2. Write a final CCA verdict with:
   - strongest evidence
   - weakest/speculative claims
   - actual mitigations Matthew can use now
3. Convert this memo into:
   - one durable rule update for CCA workflow
   - one durable rule update for wrap/init verification
   - one decision note for Matthew before April 14
4. Log any good workflow recoveries as BUILD/ADAPT findings, not just complaints

---

## Sources Reviewed

Full task queue for CCA:
- `S294_HANDOFF_URGENT.md`

Representative posts spot-checked on 2026-04-10:
- https://www.reddit.com/r/ClaudeCode/comments/1shq9lu/psa_getting_old_opus_back/
- https://www.reddit.com/r/ClaudeAI/comments/1shs1iq/dug_into_the_browser_console_on_claudeai_and/
- https://www.reddit.com/r/ClaudeCode/comments/1shjfxb/claude_codes_max_effort_thinking_has_been/
- https://www.reddit.com/r/ClaudeCode/comments/1sho7oe/canceled_my_20x_subscription_the_drop_in_quality/
- https://www.reddit.com/r/ClaudeCode/comments/1shaxkt/anthropic_made_claude_67_dumber_and_didnt_tell/
- https://www.reddit.com/r/ClaudeCode/comments/1shibf4/the_current_state_of_claude_code_opus_46_today_i/
- https://www.reddit.com/r/ClaudeCode/comments/1shscad/claude_ignored_my_prompt_entirely_hallucinated/
- https://www.reddit.com/r/ClaudeCode/comments/1shya2h/things_are_getting_really_bad/
- https://www.reddit.com/r/ClaudeCode/comments/1shzkr7/claude_code_has_become_so_superficial_and_stupid/
- https://www.reddit.com/r/ClaudeCode/comments/1shpsa9/what_would_you_do_if_somebody_confirmed_with/
- https://www.reddit.com/r/ClaudeCode/comments/1sh4bkf/2_months_ago_opus_46_built_my_tool_in_15_min/
- https://www.reddit.com/r/ClaudeCode/comments/1sh0mw7/claude_just_died/
