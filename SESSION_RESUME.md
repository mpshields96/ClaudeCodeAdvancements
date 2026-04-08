# Session Resume — S274 → S275

**Last session:** S274 — 2026-04-07
**Next session number:** S275
**Status:** Tests 12708/12708 passing (364/374 suites; 10 pre-existing module-not-found failures). Git: clean after wrap commit.

---

## STANDING DIRECTIVE (Matthew — PERMANENT for next several sessions)

**ALL CCA chats focus SOLELY on Kalshi bot overhaul. No MT work, no CCA internals.**
Every session reads TODAYS_TASKS.md TONIGHT PRIORITY OVERRIDE and works those tasks.
Codex is offline (thermal shutdown). CCA delivers guidance; Kalshi chat implements.

---

## What S274 completed

1. **mlb_live_ratings.py** built in `polymarket-bot/src/strategies/` (commit `181f7d8`)
   - Fetches 2026 MLB standings from MLB Stats API (free, same API as mlb_pitcher_feed)
   - Computes regressed pythagorean win% → adj_em with 30-game Bayesian prior
   - All 30 teams mapped via `_API_TO_CANONICAL`; 6h cache
   - 14 tests all pass in `tests/test_mlb_live_ratings.py`

2. **meta_learning_dashboard.py ROIResolver fix** (commit `ebce9d4`)
   - `ResearchROITracker.__init__()` now calls `ROIResolver.get_resolved_deliveries()` for canonical path only
   - Implementation rate corrected: 0% → 29.5% (28/95 resolved)
   - Canonical-path guard prevents test isolation contamination

3. **CCA_TO_POLYBOT.md** — S274 full delivery written:
   - **REQ-093 verdict**: MLB losses structural (bug fixed, pitcher wired, efficiency stale) → paper-only, 50 bets gate
   - **efficiency_feed Option A** exact code: `from mlb_live_ratings import refresh_efficiency_feed_mlb as _mlb_refresh; _mlb_refresh(_TEAM_EFFICIENCY)` at module load
   - **UCL 2nd legs**: Bayern (2-1 up, Apr 15 away Bayer) and Arsenal (1-0 up, Apr 16 away PSG leg analysis needed) = strong FLB setups. PSG/LFC and BAR/ATM results from Apr 8 still needed
   - **Economics sniper CPI brief**: 48h gate open, `cpi_release_monitor.py` at 08:28 ET Apr 10
   - **NBA playoffs**: PDO flags and adj_em comparisons for first-round matchups

---

## TODAYS_TASKS.md status (TONIGHT PRIORITY OVERRIDE)

| Task | Status |
|------|--------|
| CHAT T1 — REQ-093 MLB verdict | DONE S274 |
| CHAT T2 — sports_analytics runtime wiring plan | **TODO** |
| CHAT T3 — Reddit MLB nuclear scan | **TODO** |
| CHAT T4 — 2026 MLB data refresh plan | DONE S274 |
| CHAT T5 — NBA PDO (low priority) | deferred |

---

## S275 priorities (in order)

1. **CHAT T2**: Read `src/strategies/sports_analytics.py` → deliver exact operator-facing wiring guide (which function, what inputs, where to print, min tests) to `CCA_TO_POLYBOT.md`
2. **CHAT T3**: Reddit MLB nuclear scan (r/sportsbook, r/sportsbetting) → pitcher-first vs team-efficiency framing, 2026 xFIP/rest/bullpen models, BUILD/SKIP verdicts
3. **Check Codex wire-in**: Did Codex implement efficiency_feed Option A? Check git log in polymarket-bot
4. **UCL 2nd legs**: April 8 results now available — check PSG/LFC and BAR/ATM scorelines, update FLB analysis

---

## Key file paths

- `polymarket-bot/src/strategies/mlb_live_ratings.py` — new file, commit `181f7d8`
- `polymarket-bot/tests/test_mlb_live_ratings.py` — 14 tests
- `polymarket-bot/src/strategies/sports_analytics.py` — READ THIS for CHAT T2
- `polymarket-bot/src/strategies/efficiency_feed.py` — lines 148-179: MLB section, Option A wire-in target
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md` — all deliveries written, delivery flag set
- `self-learning/meta_learning_dashboard.py` — ROIResolver canonical-path guard at `__init__`

---

## Known gotchas

- When running polymarket-bot tests: use `PYTHONPATH=. pytest tests/` from `/Users/matthewshields/Projects/polymarket-bot/`
- System Python at `/opt/homebrew/opt/python@3.14` lacks pytest — use `/Library/Frameworks/Python.framework/Versions/3.13/bin/pytest`
- MLB efficiency_feed scale: ±8 (ERA-based 2024) vs ±2.3 (pythagorean early 2026) — Bayesian regression toward .500 makes early-season values near-neutral, not a bug
- Codex is OFFLINE (thermal shutdown) — CCA proposes, Kalshi chat self-implements or waits for Codex spot-check
- Kalshi bot was STOPPED at S274 wrap (SIGKILL after SIGTERM/SIGINT failed to terminate async loop)

---

Run `/cca-init` then proceed directly to CHAT T2 (sports_analytics wiring plan).
