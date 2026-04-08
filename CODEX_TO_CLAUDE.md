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

## [2026-04-08 17:34 UTC] — LEAGUES6 STATUS UPDATE — User wants guided Discord Developer Portal setup after current CCA task
**Status:** ACTION NEEDED
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/DISCORD_READER_SETUP.md`, desktop CCA chat workflow only
**Summary:**
Matthew said that after the current OSRS Leagues Phase 3 task finishes in the desktop CCA app, he plans to ask CCA to carefully guide him through the Discord Developer Portal flow for creating the separate read-only bot application. Keep this in setup-only mode for now: create/manage the bot application, explain the separate bot-vs-personal-account distinction, generate the invite link, and avoid any implementation overlap with active UI work unless that task is explicitly complete.

The current Codex guidance already written in `DISCORD_READER_SETUP.md` should be used as the safety baseline: no selfbot, no personal-account automation, no token in source, read-only permissions only.

**Verification:**
- Coordination note only

**Relay Guidance:**
- After the current UI task, CCA can safely switch into step-by-step portal guidance mode.
- CCA should not ask Matthew to paste the raw bot token into chat; only confirm it is stored locally.

## [2026-04-08 17:21 UTC] — LEAGUES6 STATUS UPDATE — Non-overlap support docs landed
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/CLAUDE_TO_CODEX.md`, `/Users/matthewshields/Projects/leagues6-companion/PHASE3_UI_STATE_CONTRACT.md`, `/Users/matthewshields/Projects/leagues6-companion/DISCORD_READER_SETUP.md`, `/Users/matthewshields/Projects/leagues6-companion/SESSION_RESUME.md`
**Summary:**
The adjacent support pass is complete and did not touch `src/app.py` or other active UI implementation files. I created the missing `CLAUDE_TO_CODEX.md` append-only handoff lane, added `PHASE3_UI_STATE_CONTRACT.md` to keep Streamlit session state compatible with the future full pact tree, and added `DISCORD_READER_SETUP.md` so the Discord reader has a safe token/setup/spec document before any code is written. `SESSION_RESUME.md` now points the next Phase 3 session at the UI state contract.

This slice is safe for CCA to consume immediately while continuing UI ownership.

**Verification:**
- Docs/state updates only; no runtime code touched

**Relay Guidance:**
- CCA should read `PHASE3_UI_STATE_CONTRACT.md` before locking pact/session-state design.
- Discord work is still setup-only; no bot code exists yet and no package was added.

## [2026-04-08 17:20 UTC] — LEAGUES6 STATUS UPDATE — Non-overlap support work for active CCA UI session
**Status:** FYI
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/CLAUDE_TO_CODEX.md`, project-root design/setup docs only; explicitly avoiding `src/app.py` and active UI implementation files
**Summary:**
Matthew started a new CCA session aimed at Phase 3 `src/app.py`. To avoid overlap, this Codex session is taking adjacent support scope only: create the missing CCA→Codex coordination file template, write a pact-tree-ready UI state contract CCA can follow while building Streamlit, and write the Discord bot setup/spec so that future `discord_reader.py` work has safety and setup guardrails.

No UI code or active `src/` implementation files are being touched in this slice.

**Verification:**
- Coordination note only; support work in progress

**Relay Guidance:**
- CCA can continue owning `src/app.py` without collision from this Codex session.
- If CCA wants to consume the contract/setup docs mid-session, it can do so safely.

## [2026-04-08 17:15 UTC] — LEAGUES6 STATUS UPDATE — Engine hardening landed and verified
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/src/engine.py`, `/Users/matthewshields/Projects/leagues6-companion/src/models.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_engine.py`, `/Users/matthewshields/Projects/leagues6-companion/SESSION_RESUME.md`, `/Users/matthewshields/Projects/leagues6-companion/TODAYS_TASKS.md`
**Summary:**
The validation-first hardening pass is complete. Codex turned four Phase 2 review findings into enforced tests, reproduced the failures, and patched the engine/model layer so the fixes are now proven rather than speculative. `score_build()` now preserves the selected relic path and pact ID, rejects duplicate region IDs, surfaces always-unlocked region context (`Varlamore`, `Karamja`), and includes Karamja's pending echo intel in `pending_fields`. `RelicSynergiser` also now uses region context for region-substitute scoring, so relic values are no longer fully region-agnostic.

The deeper pact-tree architecture issue is still open: this pass did not replace the current scalar pact model with a full 40-node tree representation. That remains the main correctness/design blocker before Phase 3 UI should be allowed to hard-bake pact state.

**Verification:**
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/test_engine.py -q` → `26 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/ -q` → `67 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 validate.py` → `GATE: PASSED`

**Relay Guidance:**
- CCA can treat the old concrete Phase 2 correctness bugs as closed.
- Before building Streamlit pact UI, keep the remaining warning active: do not bind UI state to a scalar `pact_id` if the product goal is still the full Demonic Pacts tree.

## [2026-04-08 17:11 UTC] — LEAGUES6 STATUS UPDATE — Active Codex ownership on engine hardening
**Status:** ACTION NEEDED
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/src/engine.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_engine.py`, possible supporting model/data files if required by failing tests
**Summary:**
Matthew explicitly authorized this Codex session to move from review-only into contributor mode on the OSRS Leagues 6 Companion project, with the requirement that CCA stays aware to avoid overlapping edits. I am taking ownership of validation-first engine hardening: add missing correctness tests around the known Phase 2 gaps, reproduce failures, and patch the implementation only where the tests prove it is wrong.

Initial target issues are the same five already flagged in review: `BuildScore` fidelity, duplicate-region rejection, region-aware relic synergy, full-build always-unlocked context visibility, and avoiding Phase 3 lock-in to a scalar pact shape.

**Verification:**
- Coordination note only; implementation work in progress

**Relay Guidance:**
- Treat the leagues6 engine/test layer as actively owned by Codex right now.
- If a CCA/Claude session touches the same files, coordinate first or stay read-only until this hardening pass is complete.

## [2026-04-08 17:10 UTC] — LEAGUES6 REVIEW — Phase 2 tests green, but 5 post-gate issues remain
**Status:** ACTION NEEDED
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/src/engine.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_engine.py`, `/Users/matthewshields/Projects/leagues6-companion/data/combat_pacts.json`, `/Users/matthewshields/Projects/leagues6-companion/CODEX_REVIEW_S277.md`
**Summary:**
Codex reviewed the shipped Phase 2 engine. The gate suite passes (`24/24`), but the tests are missing several important consumer-facing correctness checks. The biggest concrete bug is that `score_build()` returns a `BuildScore` with `relic_path=[]` and `pact_id=""`, so any Phase 3 UI summary will misreport the actual user-selected build. The deeper architectural issue is that the engine still models pacts as a single scalar choice backed by a 3-entry JSON file, which does not match Matthew's new directive to support the full 40-node pact tree.

Additional findings:
- `RelicSynergiser.score_path()` accepts `regions` but ignores them, so relic+region synergy and Reloaded marginal choice are still effectively region-agnostic.
- `score_build()` validates region count but not uniqueness, so duplicate region IDs score successfully.
- Always-unlocked regions are omitted from `BuildScore`, which means Karamja's pending echo-boss context never surfaces in `pending_fields` for real builds.

Detailed write-up plus a Phase 3 Streamlit structure sketch is in `CODEX_REVIEW_S277.md`.

**Verification:**
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/test_engine.py -q`
- Ad hoc probes confirmed:
  - `BuildScore.relic_path == []`
  - `BuildScore.pact_id == ""`
  - `RelicSynergiser.score_path({7: "reloaded"}, ["kandarin"], prefs) == score_path({7: "reloaded"}, ["desert"], prefs)`
  - duplicate region IDs currently score instead of raising

**Relay Guidance:**
- Read `/Users/matthewshields/Projects/leagues6-companion/CODEX_REVIEW_S277.md` before locking Phase 3 UI structure.
- Fix `BuildScore` fidelity first; otherwise the UI will display incorrect selections.
- Do not build pact UI around a single `pact_id` string. Use a richer tree/path state shape now.

---

## [2026-04-08 17:01 UTC] — LEAGUES6 DIRECTIVE — OSRS username provided for tracker wiring
**Status:** FYI
**Scope:** future `src/tracker.py` / hiscores integration in `/Users/matthewshields/Projects/leagues6-companion/`
**Summary:**
Matthew provided the OSRS account name for the live tracker and hiscores integration: `QwertyLoolz9`. Use it as the initial/default profile value for local development or example wiring, but do not hardcode it in a way that blocks later editing in the UI.

**Verification:**
- User directive received directly in Codex chat on 2026-04-08

**Relay Guidance:**
- CCA can prewire the tracker flow against `QwertyLoolz9` now.
- Keep the username editable in Streamlit session state or config, not embedded as a fixed constant.

---

## [2026-04-08 17:00 UTC] — LEAGUES6 DIRECTIVE — Full pact tree required for MVP planning
**Status:** ACTION NEEDED
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/CODEX_REVIEW_S276.md`, active `src/engine.py` Phase 2 design
**Summary:**
Matthew answered the open pact-model question: the tool should plan the full 40-node Demonic Pacts tree, not just a top-level melee/ranged/magic selector, if feasible and useful. That means the current simplified pact abstraction is no longer the target architecture for the universal interactive planner. Phase 2 does not necessarily need every node's perfect balance logic today, but the engine contract should be shaped so pact path depth can be represented now rather than bolted on later.

**Verification:**
- User directive received directly in Codex chat on 2026-04-08

**Relay Guidance:**
- CCA should not hard-bake pact handling to a single `pact_id` scalar if that creates migration pain.
- Prefer a structure like `combat_style + unlocked_nodes + reset_count_remaining` or equivalent typed model, even if node-level scoring starts simple in the first pass.
- Keep the current region/relic scoring work moving, but design the pact layer for full-tree expansion immediately.

---

## [2026-04-08 16:51 UTC] — LEAGUES6 REVIEW — Phase 1 gate hardened, Phase 2 contract proposed
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/src/models.py`, `/Users/matthewshields/Projects/leagues6-companion/data/relics.json`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_models.py`, `/Users/matthewshields/Projects/leagues6-companion/validate.py`, `/Users/matthewshields/Projects/leagues6-companion/CODEX_REVIEW_S276.md`
**Summary:**
Codex reviewed the OSRS Leagues tool Phase 1 layer and found one concrete gate failure plus two schema issues that mattered for Phase 2. `validate.py` was reporting Phase 1 `PASSED` even while `tests/test_models.py` was failing, placeholder relic stubs were ambiguous enough to leak into future engine logic, and important JSON notes for Reloaded/community intelligence were being silently dropped by Pydantic. I hardened the model/data/test/validation layer and wrote a concrete engine contract plus algorithm notes in `CODEX_REVIEW_S276.md` so the active Phase 2 chat can build against a reviewed interface instead of designing blind.

**Verification:**
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 validate.py`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/test_models.py -q`
- Result: Phase 1 gate passes and model tests are green

**Relay Guidance:**
- Read `/Users/matthewshields/Projects/leagues6-companion/CODEX_REVIEW_S276.md` before finalizing `src/engine.py`.
- Do not let `engine.py` consider placeholder relics selectable.
- Treat Reloaded as an exhaustive marginal search over tiers 1-6 excluding already-picked relic IDs; do not recurse and do not zero unknown value.

---

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

---

## [2026-04-07 03:35 UTC] — HANDOFF PROMPT — Tomorrow Continue Overhaul From Visibility Cache Gate
**Status:** ACTION NEEDED
**Scope:** `polymarket-bot/scripts/kalshi_visibility_report.py`, `polymarket-bot/scripts/polybot_wrap_helper.py`, `polymarket-bot/tests/test_kalshi_visibility_report.py`, `polymarket-bot/tests/test_polybot_wrap_helper.py`, `polymarket-bot/.claude/commands/polybot-init.md`, `polymarket-bot/.claude/commands/polybot-wrap.md`
**Summary:**
Codex continued the Kalshi overhaul and changed the visibility gate so startup is now cache-only by default instead of silently doing a full live exchange crawl. The gate now rejects stale or obviously corrupt cached reports and fails closed as `UNKNOWN`; the wrap helper applies the same check so handoff/resume state stops trusting junk visibility snapshots. This closes the immediate “startup-safe gate” bug, but the live rebuild path itself is still unproven and remains the next blocker.

**Verification:**
- `source /Users/matthewshields/Projects/polymarket-bot/venv/bin/activate && python3 -m pytest /Users/matthewshields/Projects/polymarket-bot/tests/test_kalshi_visibility_report.py /Users/matthewshields/Projects/polymarket-bot/tests/test_polybot_wrap_helper.py -q`
- `python3 -m py_compile /Users/matthewshields/Projects/polymarket-bot/scripts/kalshi_visibility_report.py /Users/matthewshields/Projects/polymarket-bot/scripts/polybot_wrap_helper.py`
- Result: targeted tests passed; compile passed
- Not run: live rebuild, because current shell/env lacked `KALSHI_API_KEY_ID`

**Relay Guidance:**
- Relay to Kalshi: startup gate is now fail-closed and cache-safe; do not treat that as overhaul complete
- Relay to Kalshi: next action is a deliberate live rebuild to validate the refreshed report path, not restart pressure or new strategy work

**Tomorrow Prompt:**
```text
Continue the Kalshi overhaul from the visibility gate work Codex landed on 2026-04-06/07.

Current truth:
- `scripts/kalshi_visibility_report.py` is now cache-only by default and startup-safe.
- Stale or obviously corrupt cached reports now fail closed as `same_day_gate = UNKNOWN`.
- `scripts/polybot_wrap_helper.py` now applies the same validation.
- The next blocker is not “wire the gate”; it is “prove the intentional live rebuild path is sane and fast enough.”

First actions:
1. Read `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CODEX_TO_CLAUDE.md` latest handoff entry and `/Users/matthewshields/Projects/polymarket-bot/CODEX_OBSERVATIONS.md`.
2. In `/Users/matthewshields/Projects/polymarket-bot`, verify focused tests still pass:
   `source venv/bin/activate && python3 -m pytest tests/test_kalshi_visibility_report.py tests/test_polybot_wrap_helper.py -q`
3. Run the intentional live rebuild only if credentials are available:
   `./venv/bin/python3 scripts/kalshi_visibility_report.py --refresh-live --edge-mode cached --strict-same-day-sports`
4. Inspect the rebuilt JSON/markdown and decide:
   - if sane: the startup visibility blocker is materially reduced
   - if still too heavy or malformed: keep working on the live fetch path itself

Rules for this continuation:
- Do not revert user/Claude runtime changes in `sports_game.py` or `sports_math.py`.
- Do not pivot to restart, expansion, or strategy work until the live rebuild path is validated.
- Treat any fresh-but-bogus report as an overhaul blocker, not a PASS.
```
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

## [2026-04-07 03:10 UTC] — HARDENING — Kalshi overhaul prompt path cleaned up + advancement execution rule codified
**Status:** ACTION NEEDED
**Scope:** `polymarket-bot/scripts/polybot_wrap_helper.py`, `polymarket-bot/tests/test_polybot_wrap_helper.py`, `polymarket-bot/SESSION_HANDOFF.md`, `polymarket-bot/SESSION_RESUME.md`, `polymarket-bot/CODEX_OBSERVATIONS.md`, `CODEX_OPERATING_MANUAL.md`, `polymarket-bot/AGENTS.md`
**Summary:**
Codex reviewed the completed Kalshi overhaul work and found the stale-state problem was still active in the operator prompt path even after the visibility gate landed. The wrap helper could not replace the legacy `SESSION_RESUME.md` format, the generated prompt still carried old restart-first priorities, and it even rendered the entire guard-count dict into the startup text. Those are now fixed. I also codified Matthew's new instruction that Codex should execute or formalize actionable advancement tips during the workstream instead of leaving them as suggestion-only footers.

**Verification:**
- `source venv/bin/activate && python3 -m pytest tests/test_polybot_wrap_helper.py tests/test_kalshi_visibility_report.py -q`
- Result: `11 passed`

**Relay Guidance:**
- CCA should treat the Kalshi prompt path as partially hardened but still blocked until `scripts/kalshi_visibility_report.py --edge-mode cached --strict-same-day-sports` produces a real cached report instead of `UNKNOWN @ missing`.
- Do not route playoff/in-play/dynamic-series expansion as "current progress" until the visibility/coverage/startup blockers are actually closed.

---

## [2026-04-07 03:22 UTC] — LIVE PROBE — visibility gate runtime path still blocked
**Status:** ACTION NEEDED
**Scope:** `polymarket-bot/scripts/kalshi_visibility_report.py`, `polymarket-bot/SESSION_HANDOFF.md`, `polymarket-bot/SESSION_RESUME.md`, `polymarket-bot/CODEX_OBSERVATIONS.md`, `CODEX_OPERATING_MANUAL.md`
**Summary:**
Codex live-tested the visibility gate instead of trusting the green test suite and found the real blocker is worse than "cache missing." The runtime path started crawling huge pagination in `/events` and `/markets` and still had not produced a cached report within normal startup time. The gate wiring exists, but the operator-facing scan is not startup-safe yet. I codified the rule this exposed as well: operational helpers need a live probe, not just unit coverage.

**Verification:**
- Live probe: `source venv/bin/activate && python3 scripts/kalshi_visibility_report.py --edge-mode cached --strict-same-day-sports`
- Result: runtime crawl hit 10,000+ events before safety stop and 100,000+ open-market pages during the probe window; no usable cache was produced in normal operator time

**Relay Guidance:**
- CCA should now describe the Kalshi visibility blocker as a runtime scan-path problem, not merely a missing JSON file.
- Any follow-on work should prioritize a startup-safe visibility scan strategy or bounded pagination path before more restart/expansion guidance.

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

## [2026-04-03 18:32 UTC] — MT-53 SUPPORT — Crystal intro navigator wired into runtime
**Status:** COMPLETE
**Scope:** `pokemon-agent/crystal_intro_navigation.py`, `pokemon-agent/agent.py`, `pokemon-agent/main.py`, `pokemon-agent/prompts.py`, `pokemon-agent/test_crystal_intro_navigation.py`, `pokemon-agent/test_agent.py`
**Summary:**
Codex pushed MT-53 forward on the real wiring gap instead of more theory. Crystal now gets a minimal static intro navigator at runtime covering the four verified New Bark intro maps: Player's House 2F, Player's House 1F, New Bark Town, and Elm's Lab.

What changed:
- added `crystal_intro_navigation.py` with a tiny preloaded `Navigator` plus verified warp links for the intro loop
- wired `main.py` so Crystal runs receive that navigator by default
- tightened `CrystalAgent._available_tools()` so `navigate_to` only appears when the current map is actually supported by the loaded navigator
- updated the prompt text so it no longer claims `navigate_to` is always available

Verification:
- `python3 -m unittest pokemon-agent.test_crystal_intro_navigation pokemon-agent.test_agent pokemon-agent.test_main`
- `python3 -m unittest discover -s pokemon-agent -p 'test_*.py'`

Net result:
- `navigate_to` is no longer dead for Crystal runtime
- it is still intentionally limited to the intro bootstrap maps, not the whole game

**Relay Guidance:**
- CCA should treat this as a real MT-53 increment: runtime wiring improved, not just docs
- the next obvious Pokemon task is `collision_reader_crystal.py` or equivalent live walkability data so Crystal navigation can extend past the intro bootstrap maps

---
