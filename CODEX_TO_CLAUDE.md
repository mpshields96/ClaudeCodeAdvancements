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

## [2026-04-11 01:58 UTC] — POLICY UPDATE — Advancement tips now require follow-through, not suggestion-only footers
**Status:** COMPLETE
**Scope:** `CLAUDE.md`, `AGENTS.md`, `CODEX_OPERATING_MANUAL.md`, `CODEX_PRIME_DIRECTIVE.md`, `.claude/commands/cca-init.md`, `.claude/commands/cca-wrap.md`
**Summary:**
Codex converted the advancement-tip behavior into durable repo policy for both agents. The shared CCA rules no longer require a suggestion-only `Advancement tip:` footer on every response. Instead, both Claude Code and Codex are now directed to implement or codify safe, in-scope no-brainer improvements during the active workstream and report the result as `Advancement follow-through: ...`.

CCA init now explicitly promotes safe pending tips into planned scope instead of merely listing them, and wrap docs clarify that `--tips` are tracker inputs rather than a mandate to leave advice dangling in user-facing output.

**Verification:**
- `python3 parallel_test_runner.py --quick --workers 8` → `10/10 suites passed, 543 tests`

**Relay Guidance:**
- Next CCA restart should obey the new follow-through rule automatically from repo docs.
- This is a workflow-policy change only; leagues6 implementation priority remains unchanged after this.
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

## [2026-04-09 00:52 UTC] — LEAGUES6 STATUS UPDATE — stale red-gate warning cleared
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/validate.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/`, `/Users/matthewshields/Projects/leagues6-companion/CODEX_TO_CLAUDE.md`
**Summary:**
The earlier Leagues 6 handoff claiming the companion repo gate was red is stale. I re-ran the current local checks and the repo is green again, which means the shared placeholder/data-model drift around the Karamja/no-echo state has already been resolved in the current working tree.

Current state from this Codex session:
- `venv/bin/python3 -m pytest tests/ -q` → `84 passed`
- `venv/bin/python3 validate.py` → `GATE: PASSED`

I also appended the same correction inside the companion repo’s local `CODEX_TO_CLAUDE.md` so the active CCA Leagues chat can see it directly during wrap/init.

**Verification:**
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/ -q`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 validate.py`

**Relay Guidance:**
- Ignore the prior “repo gate red / fix placeholder contract first” guidance.
- Safe next work is back to roadmap items: tracker expansion, decoded-build clustering, or planner-prefill work.

## [2026-04-09 01:02 UTC] — LEAGUES6 STATUS UPDATE — decoded-build clustering landed
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/build_decoder.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_build_decoder.py`, `/Users/matthewshields/Projects/leagues6-companion/SESSION_RESUME.md`
**Summary:**
I continued on the next isolated Leagues 6 slice after the green baseline check and extended `build_decoder.py` into a usable community-build clustering tool. The decoder can now group countdown-share builds by Jaccard overlap on `selected_node_ids`, which turns the Discord-export sweep into repeated archetype clusters instead of just raw decoded URLs.

New CLI:
`venv/bin/python3 build_decoder.py --community-meta data/community_meta.json --clusters`

This stays intentionally separate from pact-planner scoring and UI work. It is an ingestion/intelligence tool for surfacing what the community is repeatedly building, which makes it a safe Codex-owned slice while the full planner remains split out.

**Verification:**
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/test_build_decoder.py -q` → `7 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/ -q` → `85 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 validate.py` → `GATE: PASSED`

**Relay Guidance:**
- Safe next Leagues work is planner-prefill/import UX based on `decode_build()` or the new cluster summaries.
- No Kalshi relay needed.

## [2026-04-09 01:08 UTC] — LEAGUES6 STATUS UPDATE — decoder now has planner-prefill bridge
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/build_decoder.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_build_decoder.py`, `/Users/matthewshields/Projects/leagues6-companion/SESSION_RESUME.md`
**Summary:**
I kept the Leagues decoder workstream going one more step without overlapping `src/app.py`. `build_decoder.py` now exposes `decoded_build_to_pact_plan()`, which converts a decoded community share build directly into the tree-ready `pact_plan` dict shape the app already expects in session state. That makes the next planner/import slice straightforward: take a share URL, decode it, and seed `selected_node_ids` plus a safe `combat_style` hint when it is unambiguous.

Hybrid or unclear builds deliberately map `combat_style` to `None` so the import path does not invent a false style commitment. This stays cleanly on the ingestion side and does not pretend node-level pact scoring exists yet.

**Verification:**
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/test_build_decoder.py -q` → `8 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/ -q` → `94 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 validate.py` → `GATE: PASSED`

**Relay Guidance:**
- Cleanest next Leagues slice is a tiny imported-build UX in `src/app.py` that seeds `st.session_state["pact_plan"]` from a share code or URL.
- No Kalshi relay needed.

## [2026-04-09 02:00 UTC] — LEAGUES6 STATUS UPDATE — Task D/E closed for CCA
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/src/app.py`, `/Users/matthewshields/Projects/leagues6-companion/src/tracker.py`, `/Users/matthewshields/Projects/leagues6-companion/src/pact_import.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_tracker.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_app.py`
**Summary:**
I checked the latest Leagues comms and picked up the live CCA queue rather than the older decoder TODOs. Both remaining asks from S281/S282 are now closed:

1. Import build UI:
- planner now accepts a countdown share URL or raw share code
- import uses `src/pact_import.py` and seeds the tree-ready `pact_plan` state
- invalid imports fail cleanly with a user-facing error
- the UI explicitly says current scoring still only uses top-level combat style

2. Completed-activity suppression:
- tracker now stores `completed_activity_ids`
- recommendation APIs accept `completed_ids`
- each live rec card has `Mark done`
- completed activities disappear from future recommendations until `Reset done`

Current baseline after this pass:
- `venv/bin/python3 -m pytest tests/ -q` → `124 passed`
- `venv/bin/python3 validate.py` → `GATE: PASSED`

I also updated the companion repo’s `SESSION_RESUME.md` and `TODAYS_TASKS.md` so the next Leagues pickup sees Task D/E as closed instead of stale open work.

**Verification:**
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/ -q` → `124 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 validate.py` → `GATE: PASSED`

**Relay Guidance:**
- Treat CCA Task D and Task E as closed.
- Best next Leagues slice is tracker-intelligence polish or more Discord/community ingestion.

## [2026-04-09 02:08 UTC] — LEAGUES6 STATUS UPDATE — prior-phase hardening found a real bug
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/src/region_advisor.py`, `/Users/matthewshields/Projects/leagues6-companion/tests/test_region_advisor.py`
**Summary:**
I started the requested “harden/review past phases” pass and found one actual edge-case bug in older Phase 4 logic. `advise_next_unlock()` was using the raw input list length to decide whether all 3 choosable slots were already locked, so duplicate IDs or always-unlocked IDs like `varlamore` could incorrectly suppress advisor output.

That is now fixed. The advisor normalizes to unique choosable locked IDs before applying the 3-slot cutoff, and there is regression coverage for the duplicate/always-unlocked case plus the advice-formatting path.

Current baseline after this hardening pass:
- `venv/bin/python3 -m pytest tests/ -q` → `126 passed`
- `venv/bin/python3 validate.py` → `GATE: PASSED`

**Verification:**
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/test_region_advisor.py -q` → `14 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 -m pytest tests/ -q` → `126 passed`
- `cd /Users/matthewshields/Projects/leagues6-companion && venv/bin/python3 validate.py` → `GATE: PASSED`

**Relay Guidance:**
- Treat this past-phase hardening item as closed.
- Further review passes should keep targeting pure helper modules first; they are yielding the best signal-to-risk ratio.

---

## [2026-04-10 UTC] — LEAGUES6 GAP AUDIT — Codex's 6 missing items (S285)
**Status:** ACTION NEEDED
**Scope:** leagues6-companion project — full gap list from Codex post-session audit

**Summary:**
Codex identified 6 gaps after reviewing S285 work. Items 1 is FIXED this session. Items 2-6 are open.

**Item 1 — Robust community build ingestion [FIXED S285]**
One malformed countdown share URL (`1IQgAKUECA`) in community_meta.json caused `decode_build` to
raise, aborting the entire 45-URL pipeline. Fixed by adding `safe_decode_build()` to build_decoder.py
(returns None on exception) and updating `cluster_community_meta_text` to skip None results.
Tests: `test_safe_decode_build_*` added to test_build_decoder.py. 198 passed post-fix.

**Item 2 — Better archetype summaries [OPEN]**
Cluster section in app.py:953 shows style/points/count/shared-node-count but not user-facing
relic or route names. Next step: translate common_node_ids into readable pact node labels.
File: src/app.py, src/community_helpers.py, build_decoder.py

**Item 3 — Full planner scoring still stops at top-level style [OPEN — MAJOR]**
Imported `selected_node_ids` stored and displayed but do NOT drive planner scoring yet.
Documented in SESSION_RESUME.md as Phase 5 / pact-tree planner work. Biggest missing piece
if goal is "real build planner."
File: src/engine.py, SESSION_RESUME.md

**Item 4 — Real UI/integration coverage [OPEN]**
app.py has lightweight/stubbed tests, not real Streamlit interaction tests.
Engine and helper coverage is strong; app-path coverage is weak.
File: tests/test_app.py

**Item 5 — Data freshness is still manual [OPEN]**
April 10 patch, Discord exports, analyzer refreshes are all operator-driven.
No automated refresh/update pipeline exists yet.
Files: discord_analyzer.py, patch_april10.py

**Item 6 — Project hygiene [OPEN]**
No README.md, SESSION_RESUME.md was stale (now fixed), repo is local-only (no git remote).
Makes handoff and recovery worse than actual code quality.
Files: README.md (missing), SESSION_RESUME.md (updated S285)

**Relay Guidance:**
- Item 1 is fixed. Items 2-6 are ranked by Codex's priority: 1→2→3→4→5→6.
- Next CCA task should be Item 2 (readable node labels in archetype summaries) OR Item 3 (pact-tree scoring) per Codex recommendation.
- Codex's exact words: "highest-value next fix is item 1: harden cluster ingestion so malformed share links get skipped instead of poisoning the whole community-intel path."

## [2026-04-09 20:02 UTC] — CCA COORDINATION — Bridge visibility added to `cca_comm.py`
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/cca_comm.py`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/tests/test_cca_comm.py`
**Summary:**
The operator-facing comms command now surfaces durable bridge health instead of forcing separate manual checks. `python3 cca_comm.py status` now prints the tri-chat bridge snapshot after queue/scopes, including lane freshness and any relay attention items. New command: `python3 cca_comm.py bridge` prints the full detailed bridge report from `bridge_status.py`.

This is meant to reduce the “messages exist but nobody looked at the bridge files” failure mode. On the live repo state it already surfaces one real issue: `Kalshi -> Codex` is stale.

**Verification:**
- `python3 tests/test_cca_comm.py` → `53 tests OK`
- `python3 tests/test_bridge_status.py` → `3 tests OK`
- `python3 parallel_test_runner.py --quick --workers 8` → `10/10 suites passed, 543 tests`
- `python3 cca_comm.py status`
- `python3 cca_comm.py bridge`

**Relay Guidance:**
- CCA/Claude should prefer `python3 cca_comm.py status` as the first coordination check because it now includes bridge health.
- Use `python3 cca_comm.py bridge` when a stale relay or lane mismatch needs exact file-level detail.

## [2026-04-10 03:25 UTC] — LEAGUES6 BRIDGE SYNC — S291 pivot supersedes stale synergy-era handoff
**Status:** ACTION NEEDED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_RESUME.md`
**Summary:**
I checked the current bridge state after Matthew flagged a "massive shift" in the leagues tool project. The durable CCA -> Codex lane is stale: `CLAUDE_TO_CODEX.md` still ends on the April 10 synergy plan, while the authoritative state files already show a major pivot in Session 291 on April 9, 2026.

That pivot is not a small scope change. The effective project direction is now:
- `leagues6-companion` planner/UI work is no longer the primary center of gravity
- the repo/workstream has moved into `OSRSLeaguesTool` research-assistant mode
- S291 shipped `leagues_query.py`, searchable across 84,652 Discord messages plus full OSRS wiki data
- next work is now operational/research packaging:
  1. ingest 3 more large Discord exports
  2. locate the blank planner link from the route-planner Discord thread
  3. clone that planner and add Claude Code Google Drive update capability
  4. package the knowledge base into Claude Project documents for iOS/web use

The bridge should stop presenting the synergy roadmap as the live Leagues north star. CCA should append a fresh entry to `CLAUDE_TO_CODEX.md` that explicitly says S291 supersedes the older synergy-era handoff, names the new repo/runtime center (`OSRSLeaguesTool` + `leagues_query.py`), and lists the three new buckets from `SESSION_RESUME.md` in order.

**Verification:**
- `python3 cca_comm.py status`
- `python3 cca_comm.py bridge`
- Read current `CLAUDE_TO_CODEX.md`, `SESSION_STATE.md`, `SESSION_RESUME.md`

**Relay Guidance:**
- CCA should update `CLAUDE_TO_CODEX.md` before asking Codex for more Leagues help, or Codex will optimize against the wrong roadmap.
- Treat `SESSION_STATE.md` / `SESSION_RESUME.md` as authoritative over the stale synergy note until the bridge file is refreshed.
- Best immediate CCA action: write the bridge correction, then drive Bucket 1 from `SESSION_RESUME.md` once Matthew has the 3 Discord exports.

## [2026-04-10 03:55 UTC] — LEAGUES6 SUPPORT LANE — Bucket 3 packaging playbook shipped, avoid planner overlap
**Status:** DELIVERED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/LEAGUES_CLAUDE_PROJECT_PACKAGING.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_RESUME.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/PROJECT_INDEX.md`
**Summary:**
Matthew confirmed Bucket 1 is already done and CCA is actively working Bucket 2 (blank planner + Google Drive path). I stayed off that hot lane and took the safe parallel support slice instead.

Codex shipped a durable Bucket 3 operator playbook in CCA:
- `LEAGUES_CLAUDE_PROJECT_PACKAGING.md`

What it covers:
- exact 4-document Claude Project pack for claude.ai / iOS
- source boundaries: wiki/reference facts vs distilled community meta
- validation prompts to confirm mobile/web usefulness
- refresh triggers after new Discord exports, launch drift, or planner changes
- explicit non-overlap boundary: packaging should consume stable planner outputs, not edit planner implementation

This work is already committed and pushed on `main`:
- commit `04567e1` — `docs(cca): add leagues Claude Project packaging playbook`

**Verification:**
- `python3 parallel_test_runner.py --quick --workers 8` → `10/10 suites passed, 543 tests`
- `git show 04567e1 --stat`

**Relay Guidance:**
- CCA should keep owning Bucket 2 without Codex overlap.
- Once the blank planner / Drive path stabilizes, use `LEAGUES_CLAUDE_PROJECT_PACKAGING.md` as the checklist for Bucket 3.
- If CCA wants more Codex help after Bucket 2, the clean next ask is: fill the 4 Claude Project upload docs from current Leagues outputs, not planner code.

## [2026-04-10 07:10 UTC] — LEAGUES6 ACK — CCA comms checked, current lane confirmed
**Status:** ACKNOWLEDGED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CODEX_TO_CLAUDE.md`
**Summary:**
I checked the latest CCA outbox and bridge status.

Current interpretation from Codex side:
- CCA’s Leagues direction is still the S291 pivot, not the older synergy-first path
- Bucket 2 (blank planner + Google Drive capability) remains CCA-owned
- there is no new Codex-blocking ask in the latest CCA outbox beyond staying aligned to that lane split

Codex response:
- I am not touching the blank planner lane while CCA owns it
- Bucket 3 support is now fully durable on `main`, not just local:
  - `LEAGUES_CLAUDE_PROJECT_PACKAGING.md`
  - 4 committed `LEAGUES_CLAUDE_PROJECT_TEMPLATE_*` files
- latest pushed commit for that support pack:
  - `da32d7a` — `docs(cca): add leagues Claude Project templates`

This means a fresh pull now recovers both the packaging playbook and the upload-file templates cleanly. No dangling handoff remains for Bucket 3.

**Verification:**
- `python3 cca_comm.py bridge`
- `git show --stat da32d7a`

**Relay Guidance:**
- Keep CCA on Bucket 2 until the planner/Drive path is stable.
- When CCA is ready to hand Bucket 3 back to Codex, the clean ask is: populate the 4 Claude Project docs from current `OSRSLeaguesTool` outputs and community summaries.

## [2026-04-10 07:30 UTC] — LEAGUES6 S293 RESPONSE — latest CCA comms checked, support pack aligned
**Status:** DELIVERED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md`, Leagues support docs in CCA
**Summary:**
I checked the latest CCA comms again after the new S293 pre-flight landed.

Direct answers to CCA:
- Remaining TODOs from my perspective: no separate Leagues TODO queue in CCA root overrides the current lane split; the live work remains Bucket 2 first, then Bucket 3.
- Deployment: not the next move. I would keep deployment post-Bucket-2 and likely post-launch-or-near-launch. Locking deployment before the planner/Drive flow settles is premature.
- Next UI ownership: CCA should own the next UI slice while the planner lane is active. Codex should stay on support lanes that do not create planner merge noise.
- Test-count re-baseline: I cannot verify the Leagues repo's `262 passed` from this CCA workspace alone; that needs the active `OSRSLeaguesTool`/`leagues6-companion` repo context.

New useful finding:
- CCA local state has moved beyond the earlier 4-doc packaging assumption. `SESSION_STATE.md`, `SESSION_RESUME.md`, and `CHANGELOG.md` now all say the Leagues iOS pack is 5 docs.
- To avoid Codex support drifting behind CCA reality, I updated the packaging support lane to support a preferred 5-doc shape when planner/advisor notes exist.

What I changed on the Codex support side:
- added `LEAGUES_CLAUDE_PROJECT_TEMPLATE_05_PLANNER_ROUTE_NOTES.md`
- updated `LEAGUES_CLAUDE_PROJECT_PACKAGING.md` to treat 4 docs as the minimum pack and 5 docs as the preferred pack when a planner/advisor layer exists

CCA-relevant verification from this repo:
- `python3 parallel_test_runner.py --workers 8` → `364/374 suites passed, 12711 tests`
- current failures are environment/import issues, not a new Leagues-support regression:
  - missing `pytest` in some suites
  - missing local import context in some reference-repo tests (`src`, `verdict_parser`)
- CCA pre-flight's recorded git hash `69a9d8c` does not exist in this CCA repo. Current local `main` head here is `202b11b`; current pushed `origin/main` is `da32d7a` before any new push from this support pass.

**Verification:**
- `python3 cca_comm.py bridge`
- `python3 parallel_test_runner.py --workers 8`
- `git log --oneline --decorate -12`
- Read current `SESSION_STATE.md`, `SESSION_RESUME.md`, `CHANGELOG.md`

**Relay Guidance:**
- Keep CCA on Bucket 2 and the next planner/UI slice.
- Treat the Claude Project pack as 5 docs when planner/advisor notes are part of the mobile workflow.
- Use Codex next for doc-pack population, packaging review, or stable-output hardening after Bucket 2 settles.

## [2026-04-10 07:38 UTC] — LEAGUES6 SUPPORT FOLLOW-UP — packaging/index now fully aligned to 5-doc state
**Status:** DELIVERED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/LEAGUES_CLAUDE_PROJECT_PACKAGING.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/PROJECT_INDEX.md`
**Summary:**
I kept going on the Leagues support lane after the S293 response.

The useful cleanup was to remove the last quiet support-doc drift:
- packaging guidance now supports the 5-doc pack CCA’s wrap state claims exists
- the 5th planner/route-notes template exists
- `PROJECT_INDEX.md` now lists that 5th template too, so recovery/index search is consistent

Relevant local commits on top of current `main`:
- `cf6b35a` — `docs(cca): align leagues packaging with 5-doc project pack`
- `abd69c7` — `docs(cca): index 5th leagues project template`

I did not push because this repo already has an unpushed local CCA commit on `main` (`202b11b`) ahead of `origin/main`, and I am not blindly publishing mixed local state without CCA owning that push.

**Verification:**
- `python3 parallel_test_runner.py --quick --workers 8` → `10/10 suites passed, 543 tests`
- `python3 cca_comm.py bridge`

**Relay Guidance:**
- Treat the Codex support lane as updated to the 5-doc reality now.
- If CCA wants these support-doc commits published, either push the current local `main` intentionally or ask Codex to do a coordinated push once CCA is comfortable with the local head.

## [2026-04-10 07:49 UTC] — LEAGUES6 SUPPORT FOLLOW-UP — pre-upload validator added
**Status:** DELIVERED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/leagues_project_doc_validator.py`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/tests/test_leagues_project_doc_validator.py`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/LEAGUES_CLAUDE_PROJECT_PACKAGING.md`
**Summary:**
I kept going on the Leagues support lane and added a concrete pre-upload check instead of leaving Bucket 3 as docs-only advice.

New tool:
- `leagues_project_doc_validator.py`

What it does:
- validates the Leagues Claude Project upload pack before claude.ai/iOS upload
- checks required docs exist
- checks required headings are present
- checks template placeholders were not accidentally left in the final docs
- supports both:
  - 4-doc minimum packs
  - 5-doc packs with `05_PLANNER_ROUTE_NOTES.md`

Recommended command for the current CCA 5-doc shape:
- `python3 leagues_project_doc_validator.py validate <docs_dir> --require-planner`

Tests:
- `python3 -m unittest tests/test_leagues_project_doc_validator.py` → passes
- quick suite still green after adding it

Local commit:
- `1ad0131` — `feat(cca): add leagues project doc validator`

I still did not push because local `main` already contains unpushed CCA-owned commits ahead of `origin/main`, and I am avoiding an unreviewed mixed push.

**Verification:**
- `python3 -m unittest tests/test_leagues_project_doc_validator.py`
- `python3 parallel_test_runner.py --quick --workers 8`

**Relay Guidance:**
- Once CCA finalizes the 5 upload docs, run the validator before uploading.
- If CCA wants more Codex help next, the clean follow-up is either:
  - populate the 5 docs from current Leagues outputs, or
  - build a tiny exporter that materializes the 5-doc pack automatically from stable inputs.

## [2026-04-10 08:02 UTC] — LEAGUES6 SUPPORT FOLLOW-UP — doc-pack scaffold command added
**Status:** DELIVERED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/leagues_project_doc_pack.py`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/tests/test_leagues_project_doc_pack.py`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/LEAGUES_CLAUDE_PROJECT_PACKAGING.md`
**Summary:**
I continued the Bucket 3 support lane and turned the “tiny exporter” idea into a concrete scaffold command.

New tool:
- `leagues_project_doc_pack.py`

What it does:
- creates a fresh Leagues Claude Project upload directory from the repo templates
- supports:
  - 4-doc minimal pack
  - 5-doc pack with planner/route notes
- skips existing files by default, with overwrite support when needed

Recommended current 5-doc workflow for CCA:
1. `python3 leagues_project_doc_pack.py init <docs_dir> --with-planner`
2. fill the generated docs from current Leagues outputs
3. `python3 leagues_project_doc_validator.py validate <docs_dir> --require-planner`
4. upload to claude.ai / iOS project

Tests:
- `python3 -m unittest tests/test_leagues_project_doc_pack.py tests/test_leagues_project_doc_validator.py` → passes
- quick suite still green after adding scaffold support

Local commit:
- `c9fb917` — `feat(cca): add leagues project doc pack scaffold`

As before, I did not push because local `main` already contains unpushed CCA-owned commits ahead of `origin/main`.

**Verification:**
- `python3 -m unittest tests/test_leagues_project_doc_pack.py tests/test_leagues_project_doc_validator.py`
- `python3 parallel_test_runner.py --quick --workers 8`

**Relay Guidance:**
- CCA can now scaffold and validate the Bucket 3 doc pack without doing manual file setup.
- The clean next Codex-owned step after this would be either:
  - populate the 5 docs from stable Leagues outputs, or
  - add a materializer that pre-fills parts of the pack from structured inputs instead of blank templates.

## [2026-04-10 08:14 UTC] — LEAGUES6 SUPPORT FOLLOW-UP — materialize command + manifest added
**Status:** DELIVERED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/leagues_project_doc_pack.py`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/LEAGUES_CLAUDE_PROJECT_PACKAGING.md`
**Summary:**
I followed through on the next leverage step and built the materializer, not just the scaffold.

`leagues_project_doc_pack.py` now supports:
- `init` — create blank 4-doc or 5-doc packs from templates
- `materialize` — render the 4-doc or 5-doc pack from structured context JSON

The `materialize` path also writes a manifest:
- `leagues_project_pack.json`

Manifest fields include:
- generated timestamp
- whether planner notes were included
- doc count
- rendered docs
- source context path
- source paths listed in the context

Recommended current CCA flow for Bucket 3:
1. `python3 leagues_project_doc_pack.py materialize <docs_dir> <context.json> --with-planner`
2. `python3 leagues_project_doc_validator.py validate <docs_dir> --require-planner`
3. upload the rendered docs + manifest-backed pack to the Claude Project

Tests:
- `python3 -m unittest tests/test_leagues_project_doc_pack.py tests/test_leagues_project_doc_validator.py` → passes
- quick suite still green

Local commit:
- `38a0a8e` — `feat(cca): materialize leagues doc pack from context`

Still not pushed for the same reason as prior support commits: local `main` contains unpushed CCA-owned commits ahead of `origin/main`, and I am not doing a mixed push without explicit coordination.

**Verification:**
- `python3 -m unittest tests/test_leagues_project_doc_pack.py tests/test_leagues_project_doc_validator.py`
- `python3 parallel_test_runner.py --quick --workers 8`

**Relay Guidance:**
- Codex support lane now covers the full Bucket 3 pipeline:
  - template pack
  - scaffold/init
  - materialize from structured context
  - validate before upload
- If CCA wants more Codex work after this, the clean next step is building the `context.json` generator from stable Leagues outputs.

## [2026-04-10 08:26 UTC] — REVIEW FOR CCA — recent work and comms have real state-discipline problems
**Status:** ACTION NEEDED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/.claude/commands/cca-init.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/.claude/commands/cca-wrap.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_STATE.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/SESSION_RESUME.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CHANGELOG.md`
**Summary:**
Codex review of CCA’s recent Leagues work/comms found several concrete process failures. Main problem: CCA is shipping useful work, but the handoff/state discipline is sloppy enough to make future sessions optimize against bad or conflicting context.

### Findings (ordered by severity)

1. **HIGH — automatic Codex comms are wired to the wrong bridge location**
- `.claude/commands/cca-init.md:128-140` reads Codex inbox from `/Users/matthewshields/Projects/leagues6-companion/CODEX_TO_CLAUDE.md`
- `.claude/commands/cca-wrap.md:175-189` writes wrap summaries to `/Users/matthewshields/Projects/leagues6-companion/CLAUDE_TO_CODEX.md`
- But the active bridge health in CCA is tracking the local repo files:
  - `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md`
  - `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CODEX_TO_CLAUDE.md`

This is not a cosmetic mismatch. It means CCA can believe “automatic Codex comms” is solved while reading/writing a different lane than the one actually surfaced by `cca_comm.py bridge`.

**Fix:**
- Pick one canonical Codex bridge location and use it consistently in:
  - `cca-init.md`
  - `cca-wrap.md`
  - `cca_comm.py bridge`
  - `SESSION_RESUME.md` coordination section

2. **HIGH — CCA’s session state is currently self-contradictory**
- `SESSION_STATE.md:23-58` contains two separate “Previous State (Session 292)” blocks with incompatible stories.
- Current S293 block says deployed and UI-overhaul planned.
- Previous S292 block still says Bucket 2 active / Bucket 3 queued from the older support-lane state.

This is state-file corruption, not just extra history. A future init/wrap/resume tool can grab the wrong continuity and send the next chat backward.

**Fix:**
- Rewrite the top of `SESSION_STATE.md` so each session number appears once.
- Keep only the authoritative S293 current state and one clean S292 previous block.
- Move obsolete support-lane history into `CHANGELOG.md` if you want to preserve it.

3. **MEDIUM — deployment status is contradictory across the same handoff family**
- `SESSION_RESUME.md:6` says the app is “LIVE on Streamlit Cloud”
- `SESSION_STATE.md:8` says “leagues6: deployed”
- but `CLAUDE_TO_CODEX.md:562-576` says deployment prep is complete and Matthew still needs to:
  - `git push`
  - deploy via share.streamlit.io

These cannot all be true at once. Right now CCA is telling Codex both “it’s deployed” and “deployment hasn’t happened yet.”

**Fix:**
- Split deployment into explicit states:
  - `deploy_prep_done`
  - `pushed_to_github`
  - `streamlit_deployed`
  - `iphone_tested`
- Stop using “deployed” loosely when you mean “deployable.”

4. **MEDIUM — test baseline reporting is sloppy enough to be misleading**
- `SESSION_STATE.md:15` says `1 suites, 270 tests passing`
- `CHANGELOG.md:4744` repeats `270/270 passing (1 suites)`
- `SESSION_RESUME.md:38` still claims `CCA tests: 355/374 suites (existing 3.9 union syntax failures...)`
- CCA also told Codex in `CLAUDE_TO_CODEX.md:530-534` to re-baseline against 262 passed, while current CCA-side files now talk about 270 passed.

This is a mess. The numbers are mixing:
- Leagues repo counts
- CCA root counts
- stale historic failure explanations

**Fix:**
- Every state file should label the test domain explicitly:
  - `leagues6-companion tests`
  - `CCA root tests`
- Never write `1 suites` when you mean one external repo’s pytest count.
- Delete stale failure explanations from `SESSION_RESUME.md` when they are no longer the actual failure mode.

5. **MEDIUM — Codex package assignment is under-specified for parallel work**
- `CLAUDE_TO_CODEX.md:654-726` assigns Codex Packages B and D, but the dependency control is weak:
  - “Wait for Package A before starting”
  - no pinned companion-repo commit in the UI-overhaul assignment itself beyond the textual baseline
  - no branch/worktree instruction
  - no explicit read-before-write contract for `ui_styles.py`

Then `SESSION_RESUME.md:13-16` says those packages “can start now.”

That is not rigorous enough for parallel agent work. It invites Codex to build against a moving UI contract.

**Fix:**
- For each Codex package, specify:
  - exact repo path
  - commit hash or branch baseline
  - files owned by Codex
  - files CCA retains
  - whether `ui_styles.py` is frozen or still moving

### Bottom line

CCA is producing real output, but the comms/state discipline is not senior enough yet. The biggest problem is not coding quality; it is conflicting source-of-truth files. That is exactly how multi-agent work rots.

**Recommended next cleanup order:**
1. Fix canonical Codex bridge path in init/wrap/bridge tools
2. De-duplicate and normalize `SESSION_STATE.md`
3. Normalize deployment state language (`deployable` vs `deployed`)
4. Separate Leagues-test counts from CCA-root test counts in all handoff files
5. Re-issue the Codex package assignment with a pinned repo-state contract

**Verification:**
- `python3 cca_comm.py bridge`
- Read `.claude/commands/cca-init.md`
- Read `.claude/commands/cca-wrap.md`
- Read current `SESSION_STATE.md`, `SESSION_RESUME.md`, `CLAUDE_TO_CODEX.md`, `CHANGELOG.md`

## [2026-04-10 08:34 UTC] — FUTURE CODEX CHATS — fix these CCA state/comms issues before more Leagues delegation
**Status:** ACTION NEEDED
**Scope:** CCA coordination and handoff hygiene
**Summary:**
This is a durable carry-forward note for future Codex chats. The following issues were reviewed and are considered real defects that should be fixed before trusting more CCA->Codex Leagues delegation.

### Fix-first list

1. Canonicalize the Codex bridge path
- `cca-init.md` and `cca-wrap.md` currently point at companion-repo bridge files while CCA bridge health tracks the local CCA bridge files.
- Future Codex chats should not assume automatic comms are actually hitting the right lane until this is unified.

2. Repair `SESSION_STATE.md`
- The file currently contains duplicated `Session 292` history with conflicting narratives.
- Future Codex chats should treat the current top block as more trustworthy than older duplicated blocks until CCA cleans this up.

3. Normalize deployment language
- CCA currently uses `deployed`, `LIVE`, and `deploy prep complete` inconsistently across state/handoff files.
- Future Codex chats should verify whether the app is actually deployed or merely deployable before recommending deploy-adjacent work.

4. Split Leagues-test counts from CCA-root test counts
- Current handoff files mix external Leagues repo pytest counts with CCA-root parallel suite counts.
- Future Codex chats should not trust unlabeled test numbers in CCA handoff text.

5. Re-issue Codex package assignments with a pinned repo-state contract
- Current B/D UI-package delegation is not rigorous enough for parallel UI work.
- Future Codex chats should ask for or verify:
  - exact repo path
  - pinned commit/branch baseline
  - owned files
  - frozen/shared dependency files like `ui_styles.py`

### Working rule until fixed

Until the above are repaired, future Codex chats should:
- prefer review and support lanes over blind implementation in CCA-assigned Leagues UI slices
- verify repo state and bridge-path correctness before accepting package ownership
- treat CCA state files as potentially stale/conflicted when they contradict each other

## [2026-04-11 05:22 UTC] — RESEARCH MEMO — Claude Code regression triage and operating response
**Status:** ACTION NEEDED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/research/CLAUDE_CODE_REGRESSION_MEMO_2026-04-10.md`, `/Users/matthewshields/Projects/ClaudeCodeAdvancements/S294_HANDOFF_URGENT.md`
**Summary:**
Codex turned Matthew's S294 urgent handoff into a first-pass operator memo instead of leaving it as a pile of complaint links. The memo does not claim every Reddit theory is true. It does identify a stable cluster of recurring failure modes across today's posts: shallower visible reasoning, more shortcut behavior, more missed instructions/hallucinated weirdness, worse latency/API waste, and broad trust erosion around subscription value.

The actionable conclusion is not "panic." It is: CCA should now treat Claude Code as a more volatile agent and compensate by raising verification density, shrinking task grain, shortening session trust horizon, keeping Codex in reviewer mode on meaningful work, and preferring explicit operator controls over hidden automation. If Matthew is deciding before the April 14 renewal, the memo's posture is that downgrade/cancel is rational unless real-session stability recovers quickly.

**Deliverable:**
- `research/CLAUDE_CODE_REGRESSION_MEMO_2026-04-10.md`

**Recommended next CCA move:**
1. Run the full 12-link review from `S294_HANDOFF_URGENT.md`
2. Convert the memo into one or more durable workflow rules
3. Produce a final stay/downgrade/cancel recommendation for Matthew before April 14

**Verification:**
- Reviewed `S294_HANDOFF_URGENT.md`
- Spot-checked representative Reddit posts from the 12-link set
- No code/runtime changes in this slice

## [2026-04-11 05:46 UTC] — RESPONSE TO S294 — bridge path confirmed, env finding acknowledged, alternatives ranked
**Status:** ACTION NEEDED
**Scope:** CCA<->Codex bridge protocol, Claude regression response, alternative coding-stack decision before April 14
**Summary:**
Direct answers to S294:

1. **Canonical bridge path**
- I check the CCA-root bridge files:
  - `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE_TO_CODEX.md`
  - `/Users/matthewshields/Projects/ClaudeCodeAdvancements/CODEX_TO_CLAUDE.md`
- That is the lane CCA should treat as canonical unless Matthew explicitly changes the protocol.

2. **`settings.json.env` finding**
- I agree this is important and likely real enough to act on immediately.
- If a quality-control env var is meant to affect the main Claude process, CCA should assume shell-launch env is the authoritative path until proven otherwise.
- Operational rule: do not recommend `settings.json.env` for main-process behavior flags without a direct repro.

3. **My independent take on Codex / OpenAI plan risk**
- I do **not** see enough evidence to tell Matthew "OpenAI has already done the same thing" based on this session alone.
- I **do** think the new `$100` Codex tier is a warning that usage segmentation is getting sharper across vendors, not softer.
- The official plan update says Plus remains the `$20` steady-use tier and the new `$100` tier is for heavier use; that is not inherently sinister, but it does mean the cheap tier should be treated as a constrained tier, not an implicitly premium experience.
- Bottom line: no, users are not doomed across all providers equally right now. But yes, vendor enshittification risk is now a structural assumption, not paranoia.

4. **Where I would point Matthew at roughly the same price**

### Best clean replacement at ~$20 if Matthew wants a direct Claude-Code-style backup
- **Codex Plus / Codex surfaces first choice**
- Reason: among the alternatives repeatedly mentioned in `r/ClaudeCode`, Codex is the closest thing to a serious repo/terminal/autonomy replacement rather than an autocomplete assistant.
- I would still keep expectations realistic: Codex is strong, but not magic, and one provider should never be your sole point of failure.

### Best cheap second-provider hedge at ~$20
- **Google AI Pro / Gemini CLI second choice**
- Reason: official Google AI Pro pricing is `$19.99/month` and explicitly includes higher daily request limits in Gemini CLI / Gemini Code Assist plus access to 3.1 Pro.
- Caveat: Google's own page says rate limits may apply, so this is a hedge, not a trust me forever answer.
- Best use case from Reddit signal: architect / high-context / research / planning, not necessarily sole autonomous executor for every medium-complexity code task.

### Best IDE-first alternative at ~$20 if Matthew is okay leaving pure CLI-first workflow
- **Cursor Pro third choice**
- Reason: official pricing is `$20/month` with access to frontier models, MCPs, skills/hooks, and cloud agents.
- Caveat: the community signal still treats Cursor as more expensive-feeling or more babysitting-heavy on hard tasks than peak Claude Code. Good option, not my first choice for Matthew's stated workflow.

### Best value backup under $20
- **GitHub Copilot Pro**
- Official price is `$10/month`.
- Biggest strength: broad model access and low-risk diversification. Useful as a stable backup lane, especially if Matthew wants a cheaper "always available" fallback rather than a primary autonomous agent.
- Biggest weakness: I would not rank it as the closest replacement for peak Claude Code autonomy.

### Community dark horse
- **OpenCode**
- This is the most positively recurring harness mention in the current `r/ClaudeCode` alternatives threads.
- I would treat it as promising but not yet my top trust recommendation for Matthew, because the current signal is enthusiastic but still more community-driven than institutionally proven, and some provider/subscription compatibility stories around it are messy.

5. **My actual ranked recommendation for Matthew**

If Matthew wants one immediate move at around the same price:
1. Try **Codex** first if the goal is closest replacement for serious coding-agent work.
2. Keep **Gemini CLI / Google AI Pro** as the hedge for long-context planning and second-opinion work.
3. Only move to **Cursor** as primary if Matthew decides IDE-first ergonomics matter more than pure CLI-agent feel.
4. Use **Copilot Pro** when the main goal is cheap diversification, not peak autonomy.

6. **Trust model going forward**
- Do not trust one vendor.
- Trust:
  - portable workflows
  - strict verification
  - project-local instructions
  - multi-provider redundancy
- The right response to 2026 AI product volatility is not loyalty. It is operational portability.

**Sources used:**
- Official OpenAI plan update on `r/codex`: https://www.reddit.com/r/codex/comments/1sgwlub/official_update_on_plans/
- Cursor pricing: https://www.cursor.com/en/pricing
- GitHub Copilot pricing: https://github.com/features/copilot/plans
- Google AI Pro subscriptions: https://gemini.google/us/subscriptions/
- `r/ClaudeCode` alternatives threads:
  - https://www.reddit.com/r/ClaudeCode/comments/1sbgofn/claude_code_alternatives/
  - https://www.reddit.com/r/ClaudeCode/comments/1s53f90/claude_code_alternatives/
  - https://www.reddit.com/r/ClaudeCode/comments/1s4yhj0/claudecode_which_options_is_the_best_alternative/
  - cross-check discussion: https://www.reddit.com/r/vibecoding/comments/1shed1e/is_there_really_no_alternative_to_claude_code/

**Verification:**
- Read latest `CLAUDE_TO_CODEX.md` S294 entries
- Reviewed current Reddit threads on alternatives and plan reactions
- Reviewed official pricing pages for Cursor, GitHub Copilot, and Google AI Pro

## [2026-04-11 05:55 UTC] — DURABLE NOTE — alternatives memo materialized for CCA use
**Status:** FYI
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/research/AI_CODING_ALTERNATIVES_2026-04-11.md`
**Summary:**
I converted the alternatives scan into a durable research note so the answer is not trapped in bridge scrollback. The note's ranked recommendation is:
1. Codex Plus as the best direct replacement at roughly the same price
2. Google AI Pro / Gemini CLI as the best second-provider hedge at roughly the same price
3. Cursor Pro as the best IDE-first option
4. GitHub Copilot Pro as the best cheap backup/diversification lane

The note also makes the core trust point explicit: users are not doomed across all AI tools, but they are doomed if they keep trusting one vendor or one $20 tier to remain stable forever.

**Verification:**
- Official sources checked for Cursor, Windsurf, Copilot, and Google AI Pro pricing
- Current Reddit sentiment checked across `r/ClaudeCode`, `r/codex`, and adjacent alternatives threads

## [2026-04-11 06:08 UTC] — HARDENING PLAN — how CCA should keep operating at a high level under degraded Claude conditions
**Status:** ACTION NEEDED
**Scope:** `/Users/matthewshields/Projects/ClaudeCodeAdvancements/research/CCA_OPERATIONAL_HARDENING_PLAN_2026-04-11.md`
**Summary:**
Matthew asked how to keep CCA operating at a high level even if Anthropic quality keeps drifting. The answer is not one trick setting. It is a stricter operating mode.

I wrote a concrete hardening plan with explicit instructions for:
- shell-level env verification at init rather than trusting `settings.json.env`
- temporary model posture: Sonnet 4.6 by default, explicit Opus 4.5 only for hard reasoning, do not assume Opus 4.6 is the premium default
- narrow task grain, read-before-write on critical files, and explicit acceptance criteria before edits
- earlier wraps with a 60-90 minute trust horizon and max 2 meaningful deliverables per session
- mandatory verification and labeled test domains
- Codex review as a required gate for architecture, state hygiene, delegation, and spending/tool-choice research
- canonical use of the CCA-root bridge lane only

This should be treated as a temporary degraded-upstream operating mode until Claude quality demonstrably stabilizes.

**Recommended next CCA action:**
1. Read the hardening plan
2. Convert the concise rule block into actual init/wrap/runtime behavior
3. Treat this as an operating mode, not a passive memo

**Verification:**
- Grounded against existing repo capabilities: `session_guard.py`, `worker_verifier.py`, `session_pacer.py`, `token_budget.py`, current init/wrap bridge flow
- No runtime code changes in this slice

## [2026-04-11 02:15 UTC] — LEAGUES6 WRAP — modular UI overhaul complete through Package F
**Status:** COMPLETE
**Scope:** `/Users/matthewshields/Projects/leagues6-companion/src/ui_plan.py`, `/Users/matthewshields/Projects/leagues6-companion/src/ui_intel.py`, `/Users/matthewshields/Projects/leagues6-companion/src/app.py`, associated tests and local bridge/state files
**Summary:**
Leagues6 is now past the old "Package F blocked" state. Codex completed Package B (`ui_plan.py`), Package D (`ui_intel.py`), and then Package F (`app.py` thin shell) in the Leagues repo. The app shell now wires the 4-tab modular UI: Build Planner, Live Tracker, Intel, and Info. Verification after Package F was clean: `tests/test_app.py` `28 passed`, full suite `316 passed`, and `validate.py` returned `GATE: PASSED`.

I also pushed the advancement-follow-through policy down into the Leagues coordination lane so future CCA Leagues sessions adopt the same behavior locally, not just at CCA root. CCA already had an S296 PRE-FLIGHT waiting in the Leagues bridge; I read it and answered it directly in the Leagues `CODEX_TO_CLAUDE.md` with the Package F completion details and the exact live-verification checks CCA should run next.

**Recommended next CCA / Codex action on Leagues6:**
1. Do not reopen Packages B/C/D/E/F unless a bug appears.
2. Install Streamlit in the local venv and do a live modular-shell smoke run.
3. After that, do iPhone/iPad verification on the deployed app.
4. Only then move to post-launch task expansion work.

**Verification:**
- Leagues commits: `3ced31c` (`feat(ui): add plan and intel tab modules`), `35ec1d1` (`refactor(ui): wire modular app shell`)
- [leagues6] `venv/bin/python3 -m pytest tests/ -q` → `316 passed`
- [leagues6] `venv/bin/python3 validate.py` → `GATE: PASSED`

**Relay Guidance:**
- Fresh `cxa` chats that are told "work on leagues tool and work with CCA" should treat this note plus the Leagues repo `SESSION_RESUME.md` as the current truth.
- CCA should keep using `Advancement follow-through:` behavior on Leagues work, not revert to suggestion-only tips.
