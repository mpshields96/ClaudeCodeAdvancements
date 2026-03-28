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
