# Codex -> Claude Code Outbox
# Codex writes durable notes here for CCA / Claude Code to pick up.
# CCA reads this file at session start and during wrap/handoff review.
# Format: append-only. Never overwrite or delete entries.
# ──────────────────────────────────────────────────────────────────
#
# Use this header for each note:
#
# ## [DATE TIME UTC] — [TYPE] — [SHORT TITLE]
# **Status:** FYI | ACTION NEEDED | BLOCKED | COMPLETE
# **Scope:** files/modules/branch touched or reviewed
# **Summary:**
# [2-4 sentences on what changed, what matters, or what CCA should relay]
#
# **Verification:**
# - [tests run, checks passed, or "not run"]
#
# **Relay Guidance:**
# - CCA relay to Kalshi if relevant
# - CCA log in session wrap if durable
#
# ---

## [2026-03-28 02:44 UTC] — STATUS UPDATE — 3-Way Hub Bridge Activated
**Status:** COMPLETE
**Scope:** `resume_generator.py`, `BRIDGE_PROTOCOL.md`, `KALSHI_3CHAT_GAMEPLAN.md`, `SESSION_RESUME.md`
**Summary:**
Codex created the durable Codex -> CCA outbox and updated the repo protocol to an active 3-way hub model with CCA as router between Codex and Kalshi. `SESSION_RESUME.md` now surfaces recent Codex/Kalshi bridge headings, so fresh CCA chats start with direct bridge awareness instead of relying on Matthew to restate it.

**Verification:**
- `python3 -m pytest tests/test_resume_generator.py tests/test_codex_init.py tests/test_slim_init.py`
- Result: 148 passed

**Relay Guidance:**
- Relay to Kalshi only if it needs to know the hub model is now official
- Keep future durable Codex outcomes append-only in this file

---


## [2026-03-28 03:13 UTC] — STATUS UPDATE — Starting Kalshi Relay Review
**Status:** ACTION NEEDED
**Scope:** sports-game signal generation review, Kalshi relay item REQ-61
**Summary:**
Codex is starting work on the Kalshi-relayed sports-game calibration and signal-generation review that CCA flagged for Codex follow-up. Treat this as an active Codex workstream so CCA does not assume the item is still unowned.

**Verification:**
- Not run yet

**Relay Guidance:**
- CCA should consider REQ-61 actively picked up by Codex
- If Kalshi asks for status before completion, relay that Codex is reviewing the signal path now

---

## [2026-03-28 03:25 UTC] — STATUS UPDATE — Sports-Game Hardening Landed
**Status:** COMPLETE
**Scope:** `polymarket-bot/main.py`, `polymarket-bot/src/strategies/sports_game.py`, `polymarket-bot/tests/test_sports_game.py`, `polymarket-bot/tests/test_live_announce.py`
**Summary:**
Codex reviewed the REQ-61 relay path and found no direct proof that the live sports-game loop flipped YES/NO sides globally. Codex hardened the strategy anyway by validating the YES-side team against Kalshi `yes_sub_title` / `no_sub_title` metadata when available, and made `_announce_live_bet` backward-compatible with legacy keyword-style callers so a live trade cannot crash the loop on announcement mismatch.

**Verification:**
- `python3 -m pytest tests/test_sports_game.py tests/test_live_announce.py`
- Result: 38 passed

**Relay Guidance:**
- Relay to Kalshi that side-mapping hardening is in and the live announcement crash path is guarded
- Current open question remains the Boston false signal's source consensus, which Codex is still tracing in the odds aggregation layer

---

## [2026-03-28 03:27 UTC] — STATUS UPDATE — Dual-Notify Rule Codified
**Status:** COMPLETE
**Scope:** `CODEX_OPERATING_MANUAL.md`, `BRIDGE_PROTOCOL.md`, `polymarket-bot/CODEX_QUICKSTART.md`, `polymarket-bot/AGENTS.md`
**Summary:**
Codex codified the standing rule that any Codex change to the Kalshi bot must be reported to both CCA and Kalshi. The rule now lives in both the CCA-side Codex operating docs and the Kalshi-bot Codex-facing docs so fresh Codex chats in either repo inherit the behavior by default.

**Verification:**
- Docs update only

**Relay Guidance:**
- CCA and Kalshi should treat dual notification on Kalshi-bot changes as a standing operating rule
- If a future Codex chat updates polymarket-bot without notifying both lanes, that is a process violation

---

## [2026-03-28 04:01 UTC] — BUGFIX — `cca_comm.py task` Stale Inbox Cleanup
**Status:** COMPLETE
**Scope:** `cca_comm.py`, `tests/test_cca_comm.py`
**Summary:**
Codex fixed a coordination bug in `cca_comm.py` where `cmd_task()` called `ciq.acknowledge()` with the wrong argument list while clearing stale unread messages. That crash could prevent replacement tasks from being assigned when an inbox contained old handoff items. The fix now acknowledges stale messages with the correct queue path and adds regression coverage for the stale-cleanup path.

**Verification:**
- `python3 -m pytest tests/test_cca_comm.py` -> `41 passed`

**Relay Guidance:**
- CCA can trust `cca_comm.py task` to clear stale inbox items without crashing before assigning a new task
- Kalshi lanes were notified because this affects cross-chat task routing reliability

---

## [2026-03-28 19:05 UTC] — BUGFIX — CLI Autoloop Test Env Leak Isolated
**Status:** COMPLETE
**Scope:** `tests/test_autoloop_trigger.py`, `tests/test_autoloop_stop_hook.py`
**Summary:**
Codex reviewed the active CLI migration blocker in the live CCA repo and confirmed the issue was in test isolation, not the trigger/stop-hook runtime logic. `tests/test_autoloop_trigger.py` had started an env-leak fix, but the class-level patch on `is_cli_mode()` injected an extra mock argument into every desktop-path test method and broke the suite. Codex replaced that with `CCA_AUTOLOOP_CLI` cleanup in `setUp`/`tearDown`, matching the stop-hook test pattern and keeping desktop-path assertions stable even when CLI-mode env state leaks in from autoloop shells.

**Verification:**
- `python3 -m pytest tests/test_autoloop_trigger.py tests/test_autoloop_stop_hook.py -q`
- `python3 -m pytest tests/test_cca_autoloop.py tests/test_desktop_autoloop.py tests/test_autoloop_trigger.py tests/test_autoloop_stop_hook.py -q`
- Result: `60 passed` and `266 passed`

**Relay Guidance:**
- CCA can treat the current CLI autoloop test blocker as resolved in the live repo
- Next CLI migration work should move back to Codex/Kalshi phases unless a fresh runtime bug appears

---

## [2026-03-28 19:20 UTC] — HARDENING — Codex Helper Commands Re-Anchor To Canonical CCA Repo
**Status:** COMPLETE
**Scope:** `codex_init.py`, `codex_auto.py`, `codex_autoloop.py`, `codex_wrap.py`, `codex-skills/cca-desktop-workflow/SKILL.md`, `CODEX_DESKTOP_WORKFLOW.md`, `CODEX_OPERATING_MANUAL.md`, `tests/test_codex_*.py`
**Summary:**
Codex traced the recurring wrong-repo problem to two layers: the Codex desktop app had been pointed at `/Users/matthewshields/Documents/New project`, and the CCA Codex helper commands still trusted whatever root they were invoked with. The app-level workspace root was corrected separately, and the live repo now has command/skill guardrails so Codex helper flows re-anchor to `/Users/matthewshields/Projects/ClaudeCodeAdvancements` when launched from a wrapper folder or non-canonical clone. That means `CCA init/auto/autoloop/wrap` prompts should keep targeting the shared CCA repo even if chat cwd drifts.

**Verification:**
- `python3 -m pytest tests/test_codex_init.py tests/test_codex_auto.py tests/test_codex_autoloop.py tests/test_codex_wrap.py tests/test_resume_generator.py tests/test_slim_init.py -q`
- Result: `171 passed`
- Live smoke: `python3 codex_init.py --root '/Users/matthewshields/Documents/New project'` warns, then emits an init prompt for `/Users/matthewshields/Projects/ClaudeCodeAdvancements`

**Relay Guidance:**
- CCA can treat the wrong-repo Codex chat issue as fixed at both the app-workspace and repo-helper layers
- If a future Codex chat still opens in a wrapper folder, the current chat cwd may still look odd, but helper-generated work prompts should snap back to canonical CCA automatically

---

## [2026-03-28 20:35 UTC] — STATUS UPDATE — Autoloop Truth Table For Next Chat
**Status:** ACTION NEEDED
**Scope:** `autoloop_trigger.py`, `autoloop_stop_hook.py`, `start_autoloop.sh`, `cca_autoloop.py`, `.claude/commands/cca-wrap.md`
**Summary:**
Codex verified that the live CCA autoloop runtime files are currently clean in the working tree, so there is no evidence that CCA broke desktop Electron autoloop during this conversation. The actual gap is architectural: a standalone terminal `cca` chat does not self-chain today. Current behavior is: Claude desktop app can self-chain via `autoloop_trigger.py`; CLI autoloop works when launched under `bash start_autoloop.sh` or `cca_autoloop.py`; a one-off terminal `cca` session cannot autonomously launch the next session by itself. This mismatch cost time and should be stated plainly in future chats.

**Verification:**
- `git status --short autoloop_trigger.py autoloop_stop_hook.py start_autoloop.sh cca_autoloop.py .claude/commands/cca-wrap.md` -> clean
- `git log --oneline -n 12 -- autoloop_trigger.py autoloop_stop_hook.py start_autoloop.sh cca_autoloop.py .claude/commands/cca-wrap.md`
- Process check during investigation showed a real active outer loop: `bash start_autoloop.sh` with a child CCA `claude` process

**Relay Guidance:**
- Tell Matthew: desktop Electron autoloop should still behave as intended; the missing feature is standalone terminal self-chaining
- For future implementation work, frame the task explicitly as: "add self-chaining for one-off terminal CCA chats without breaking existing desktop autoloop or outer-loop CLI autoloop"

---

## [2026-04-03 15:45 UTC] — COORDINATION HARDENING — Tri-Chat Bridge Supervisor + Kalshi Research Delivery
**Status:** COMPLETE
**Scope:** `bridge_status.py`, `codex_init.py`, `codex_auto.py`, `BRIDGE_PROTOCOL.md`, `CODEX_OPERATING_MANUAL.md`, `tests/test_bridge_status.py`, `tests/test_codex_init.py`, `tests/test_codex_auto.py`, `research/KALSHI_REQ63_NON_SNIPER_MARKET_SCAN_2026-04-03.md`
**Summary:**
Codex tightened the 3-chat bridge around one canonical comms-health command: `python3 bridge_status.py`. It reads the live CCA/Codex/Kalshi lanes, shows freshness, latest headings, and likely pending relay gaps instead of forcing each chat to freehand the bridge state. Codex init/auto prompts now explicitly tell Codex to run it at coordination rounds. I also wrote a fresh Kalshi research note ranking realistic non-sniper market candidates and skip-listing the noisy ones.

**Verification:**
- `python3 -m unittest tests.test_bridge_status tests.test_codex_init tests.test_codex_auto`

**Relay Guidance:**
- CCA should adopt `python3 bridge_status.py` as the first bridge check before task switches and wrap decisions
- The fresh Kalshi delivery is in the CCA outbox and the detailed research note lives at `research/KALSHI_REQ63_NON_SNIPER_MARKET_SCAN_2026-04-03.md`

---

## [2026-04-03 16:05 UTC] — RESEARCH DELIVERY — REQ-66 Timing / CPI / UCL Verdict
**Status:** COMPLETE
**Scope:** `research/KALSHI_REQ66_TIMING_CPI_UCL_2026-04-03.md`, `~/.claude/cross-chat/CCA_TO_POLYBOT.md`, `/Users/matthewshields/Projects/polymarket-bot/CODEX_OBSERVATIONS.md`
**Summary:**
Codex answered the active Kalshi REQ-66 with a tighter operational verdict. Sports game markets should be treated as same-day liquidity opportunities rather than reliable 8-14h-early boards; UCL season-winner futures are not a valid replacement for game markets; April 10 CPI is eligible for micro-live only; combos remain a skip.

**Verification / basis:**
- Official BLS schedule confirms March 2026 CPI releases on April 10, 2026 at 8:30 AM ET
- Official Kalshi docs confirm 24/7 trading hours and combo/RFQ complexity
- Official Kalshi market-maker docs show `KXUCLGAME` exists as a product line

**Relay Guidance:**
- CCA can treat REQ-66 as answered in the live Kalshi outbox
- If the Kalshi chat asks for implementation next, the cleanest immediate decision is micro-live CPI gating or same-day sports timing refinement, not UCL futures or combos

---

## [2026-04-03 16:20 UTC] — COMMS HARDENING — kalshi-check Now Surfaces REQ-66 State
**Status:** COMPLETE
**Scope:** `cross_chat_board.py`, `tests/test_cross_chat_board.py`, `~/.claude/cross-chat/CCA_TO_POLYBOT.md`, `/Users/matthewshields/Projects/polymarket-bot/CODEX_OBSERVATIONS.md`
**Summary:**
Codex upgraded the existing `python3 cross_chat_board.py kalshi-check` path so the Kalshi loop can see more than a bare delivery flag. It now reports the latest delivery heading, latest request heading, whether REQ-66 has already been answered, and a direct action hint. A fresh REQ-067 note was appended to the outbox and the delivery flag was re-fired.

**Verification:**
- `python3 -m unittest tests.test_cross_chat_board`
- `python3 cross_chat_board.py kalshi-check`

**Relay Guidance:**
- CCA can treat REQ-067 as answered
- Kalshi can use `kalshi-check` as the cheap JSON gate before deciding whether to read the full outbox

---

## [2026-04-03 16:32 UTC] — COMMS HARDENING — kalshi-check Now Exposes Explicit REQ Arrays
**Status:** COMPLETE
**Scope:** `cross_chat_board.py`, `tests/test_cross_chat_board.py`, `KALSHI_TASK_CATALOG.md`, `~/.claude/cross-chat/CCA_TO_POLYBOT.md`, `/Users/matthewshields/Projects/polymarket-bot/CODEX_OBSERVATIONS.md`
**Summary:**
Codex pushed `kalshi-check` one step further so the consumer can branch on structured REQ IDs instead of string-matching headings. The JSON now includes `should_read_outbox`, `latest_delivery_req_ids`, and `latest_request_req_ids`. I also updated the Kalshi task catalog to make the bridge gate an explicit pre-check.

**Verification:**
- `python3 -m unittest tests.test_cross_chat_board`
- `python3 cross_chat_board.py kalshi-check`

**Relay Guidance:**
- CCA can treat the helper as machine-ready enough for Kalshi-loop integration
- The next logical step lives in polybot: consume `should_read_outbox` and REQ arrays directly in monitoring flow

---

## [2026-04-03 17:14 UTC] — KALSHI SUPPORT — CPI readiness audit helper added
**Status:** COMPLETE
**Scope:** `kalshi_cpi_readiness.py`, `tests/test_kalshi_cpi_readiness.py`, `KALSHI_TASK_CATALOG.md`, `research/KALSHI_CPI_READINESS_2026-04-03.md`, `~/.claude/cross-chat/CCA_TO_POLYBOT.md`, `/Users/matthewshields/Projects/polymarket-bot/CODEX_OBSERVATIONS.md`
**Summary:**
Codex added a CCA-side audit command to stop the Kalshi chat from freehanding CPI readiness. `python3 kalshi_cpi_readiness.py` inspects the existing polybot economics strategy, main-loop wiring, config mode, CPI monitor, and test coverage, then returns a structured `blocked` or `watch` verdict plus next actions. On the live workspace it currently returns `WATCH`.

**Verification:**
- `python3 -m unittest tests.test_kalshi_cpi_readiness tests.test_bridge_status tests.test_cross_chat_board`
- `python3 kalshi_cpi_readiness.py`

**Relay Guidance:**
- CCA can now answer CPI readiness questions with one command instead of re-reading the polybot repo manually
- Kalshi should use the audit before April 8 and again on April 10 morning, then follow the note in `research/KALSHI_CPI_READINESS_2026-04-03.md`

---

## [2026-04-03 17:34 UTC] — KALSHI SUPPORT — tonight board ranked for April 3
**Status:** COMPLETE
**Scope:** `research/KALSHI_TONIGHT_MARKETS_2026-04-03.md`, `~/.claude/cross-chat/CCA_TO_POLYBOT.md`, `/Users/matthewshields/Projects/polymarket-bot/CODEX_OBSERVATIONS.md`
**Summary:**
Codex did a live-date research pass for Friday, April 3, 2026 and converted it into a ranked board for the Kalshi chat. The main conclusion is not to invent exotic new bets tonight: use the liquid same-day sports board first, then stage tomorrow's weather and Top App work.

Ranked board:
- NBA same-day game markets first
- NHL second
- MLB late board third
- weather setup for tomorrow fourth
- Top App for tomorrow morning fifth

Key targets relayed:
- NBA: Pacers/Hornets, Bulls/Knicks, Hawks/Nets, Celtics/Bucks
- NHL: Blues/Ducks
- MLB late board: Brewers/Royals, Mariners/Angels, Astros/Athletics, Braves/Diamondbacks, Mets/Giants

**Relay Guidance:**
- CCA can use this to steer Kalshi away from random market-hopping tonight
- Kalshi still needs live order-book checks before any exact side recommendation

---

## [2026-04-03 18:07 UTC] — KALSHI SUPPORT — April 4 sports board reduced to price ceilings
**Status:** COMPLETE
**Scope:** `research/KALSHI_TOMORROW_SPORTS_2026-04-04.md`, `~/.claude/cross-chat/CCA_TO_POLYBOT.md`, `/Users/matthewshields/Projects/polymarket-bot/CODEX_OBSERVATIONS.md`
**Summary:**
Codex translated tomorrow's sports help into three ranked NBA leans with explicit Kalshi price ceilings, plus a secondary MLB scan list. This is deliberately stricter than "pick winners" because the user needs actable bet discipline, not just team preference.

Leans sent to Kalshi:
- Rockets over Bucks if YES <= 60-62c
- Hawks over Magic if YES <= 57-59c
- Pacers over Bulls if YES <= 55-57c

**Relay Guidance:**
- CCA can now answer "what about tomorrow?" with a compact, price-disciplined board
- next upgrade is to turn live quoted Kalshi prices into exact bet/pass calls

---

## [2026-04-03 18:18 UTC] — KALSHI SUPPORT — April 4 price-gate helper added
**Status:** COMPLETE
**Scope:** `kalshi_price_gate.py`, `tests/test_kalshi_price_gate.py`, `KALSHI_TASK_CATALOG.md`, `~/.claude/cross-chat/CCA_TO_POLYBOT.md`, `/Users/matthewshields/Projects/polymarket-bot/CODEX_OBSERVATIONS.md`
**Summary:**
Codex added a tiny CLI to enforce tomorrow's sports ceilings on real Kalshi quotes. This turns the April 4 note into an immediate operational gate instead of a prose-only suggestion.

Usage:
- `python3 kalshi_price_gate.py list`
- `python3 kalshi_price_gate.py eval --market rockets-bucks --yes 61`

Current encoded gates:
- rockets-bucks <= 62c
- hawks-magic <= 59c
- pacers-bulls <= 57c

**Verification:**
- `python3 -m unittest tests.test_kalshi_price_gate tests.test_cross_chat_board tests.test_bridge_status`
- `python3 kalshi_price_gate.py list`
- `python3 kalshi_price_gate.py eval --market rockets-bucks --yes 61`

**Relay Guidance:**
- CCA and Kalshi can now handle tomorrow's quoted prices in one command
- if Kalshi sends live quotes, Codex can still do a deeper pass, but the helper is enough for first-line discipline

---
