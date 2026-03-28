# 3-Chat System Game Plan
# Created: S106 (2026-03-22)
# Status: PRE-FLIGHT — must complete before going live

---

## Goal
Run 3 simultaneous Claude Code chats:
1. **CCA Desktop** — coordinator, priorities, docs
2. **CCA Worker (cli1)** — code tasks, tests, commits
3. **Kalshi Research** — trading bot research + self-learning

## What Must Be True Before Go-Live

### Phase 1: Fix Auth (BLOCKING — do this first) — DONE (S107)

- [x] **Root cause found**: `ANTHROPIC_API_KEY` env var set in shell profile. New Terminal tabs inherit it, making CLI chats use API credits instead of Max subscription (OAuth).
- [x] **Fix applied**: Both `launch_worker.sh` and `launch_kalshi.sh` now run `unset ANTHROPIC_API_KEY` before launching `claude`. Committed: 277d6e8.
- [ ] **Verify**: Launch a test CLI chat, confirm it says "Max" not "API" in the model info. (Needs Matthew to test — can't verify from inside a running chat.)
- [ ] **Verify**: `launch_worker.sh` opens a terminal chat that uses Max subscription.
- [ ] **Verify**: `launch_kalshi.sh` opens a terminal chat that uses Max subscription.

### Phase 2: Test Bridge Communication (OFFLINE) — DONE (S107)

- [x] **CCA_TO_POLYBOT.md**: Well-structured (47.7K in CCA, 9.2K stale copy in polybot). Contains full analytics framework + citations. **GAP: polybot copy is stale** — missing S57+ updates (ROI tracking, etc). Needs manual sync before Kalshi chat launch.
- [x] **POLYBOT_TO_CCA.md**: Return channel now exists in `~/.claude/cross-chat/`. CCA can read it at session start.
- [x] **Simulate read**: polymarket-bot CLAUDE.md (line 574) explicitly mandates reading CCA_TO_POLYBOT.md at session start. Protocol is defined. Kalshi chat writes to POLYBOT_TO_CCA.md for return.
- [x] **Protocol defined**: See `BRIDGE_PROTOCOL.md` (created S107, updated S217). Covers the 3-way hub model: CCA <-> Codex and CCA <-> Kalshi, with CCA as relay/router.

### Phase 2.5: Codex Lane — DONE (S217)

- [x] `CLAUDE_TO_CODEX.md` established as CCA -> Codex durable bridge
- [x] `CODEX_TO_CLAUDE.md` established as Codex -> CCA durable bridge
- [x] `SESSION_RESUME.md` now surfaces recent Codex/Kalshi bridge headings so fresh CCA chats start aware of both lanes
- [x] `BRIDGE_PROTOCOL.md` updated from 2-lane docs to an active 3-way hub model

**Remaining gap**: CCA_TO_POLYBOT.md in polybot project needs manual update (copy from CCA). Matthew should run: `cp CCA_TO_POLYBOT.md ../polymarket-bot/CCA_TO_POLYBOT.md`

### Phase 3: Safety Checklist for Kalshi Chat — DONE (S107)

- [x] **Small bets only**: CONFIRMED. Bot is at Stage 1 ($5/bet max). Kelly sizing is invisible at Stage 1 — $5 cap always binds. Kill switch at 8 consecutive losses. Stage promotion gated on Kelly calibration, not just bankroll.
- [x] **Know how to turn off**: Documented below in Emergency Procedures (already existed in gameplan). Quick: `Ctrl+C` in terminal tab. Nuclear: `pkill -f "python main.py"` for bot process, `killall claude` for all chats.
- [x] **Rate limits**: 3 Opus chats on Max x5 during off-peak (2x promo through March 28) should be fine. During peak (8AM-2PM ET weekdays): pause worker or switch to Sonnet. Matthew directive S107: watch tokens during peak.
- [x] **Emergency kill**: Full procedure documented. Bot kill: switch to Kalshi tab, `Ctrl+C`. If unresponsive: `Ctrl+\` (SIGQUIT). Nuclear: `ps aux | grep python` + `kill <PID>`. All chats: `killall claude`.
- [x] **Matthew departure protocol**: If Matthew says "leaving" or "shutting down" — turn bot off IMMEDIATELY before anything else. Non-negotiable (S107 explicit).

### Phase 4: Dry Run (one session)

- [ ] Launch all 3 chats with auth confirmed.
- [ ] CCA Desktop writes a simple test message to CCA_TO_POLYBOT.md.
- [ ] Kalshi Research chat reads it, acknowledges in POLYBOT_TO_CCA.md.
- [ ] CCA Desktop reads the acknowledgment.
- [ ] Worker does a small code task independently.
- [ ] All 3 wrap cleanly. No crashes, no orphaned processes.

### Phase 5: Go Live

- [ ] Run real 3-chat session with actual work items.
- [ ] Desktop coordinates, worker builds, Kalshi researches.
- [ ] **Turn bot off before wrap.** Non-negotiable.

---

## Session-by-Session Plan

| Session | Desktop Focus | Worker Focus | Kalshi |
|---------|--------------|-------------|--------|
| S107 | Fix CLI auth, test bridge offline, write safety docs | Code tasks (MT-28 Phase 2 or bug fixes) | NOT LAUNCHED |
| S108 | Dry run: launch all 3, test round-trip communication | Small code task | Test read/write bridge, small bet experiment |
| S109+ | Full 3-chat production | Real MT tasks | Research + self-learning integration |

---

## Emergency Procedures

### Stop the Kalshi bot immediately:
1. Switch to Kalshi terminal tab
2. Type: `Ctrl+C` (interrupts current command)
3. If unresponsive: `Ctrl+\` (SIGQUIT)
4. Nuclear: Find PID with `ps aux | grep claude` and `kill <PID>`

### Stop all chats:
1. Close Terminal.app windows (Cmd+W on each tab)
2. Or: `killall claude` (kills all Claude processes — use as last resort)

---

## Key Files

| File | Purpose |
|------|---------|
| `launch_worker.sh` | Starts worker chat in new Terminal tab |
| `launch_kalshi.sh` | Starts Kalshi chat in new Terminal tab |
| `LAUNCH_3CHAT.md` | Copy-paste manual steps |
| `CCA_TO_POLYBOT.md` | CCA -> Kalshi bridge (CCA writes) |
| `POLYBOT_TO_CCA.md` | Kalshi -> CCA bridge (Kalshi writes) |
| `CLAUDE_TO_CODEX.md` | CCA -> Codex bridge (CCA writes) |
| `CODEX_TO_CLAUDE.md` | Codex -> CCA bridge (Codex writes) |
| `BRIDGE_PROTOCOL.md` | 3-way hub protocol + routing docs |
| `cca_comm.py` | Internal CCA queue (desktop <-> worker) |
