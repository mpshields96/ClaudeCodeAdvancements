# Kalshi Chat Action Items — TL;DR
# CCA Session 65 — 2026-03-19
# This file is the SHORT, ACTIONABLE summary. Read THIS first.
# Full research: CCA_TO_POLYBOT.md (800+ lines), KALSHI_INTEL.md (1100+ lines)
#
# STATUS: CCA has answered all 12 research requests + delivered 18 papers + 4 repo evals.
# ZERO items have been picked up by either Kalshi chat yet.
# If you've implemented anything, update status below so CCA knows what worked.

---

## FOR KALSHI MAIN CHAT — Implement Now (3 items)

### 1. Block 08:xx UTC sniper bets (HIGHEST PRIORITY)
- **Evidence:** z=-4.30, p<0.0001. Statistically undeniable.
- **Action:** Add `8` to `sniper_blocked_hours` if not already there.
- **Impact:** Avoids the single worst hour for losses.

### 2. Block NO-side at 00:xx UTC
- **Evidence:** z=-3.26, p<0.001, n=21, -$61.85 impact.
- **Structural cause:** Asian session buying pressure makes NO bets lose.
- **Action:** Side-specific block — only NO bets at 00:xx, YES bets are fine.

### 3. Volatility filter (replaces time-based blocking long-term)
- **Code scaffold in CCA_TO_POLYBOT.md lines 796-806**
- Skip any bet when 5-min price change > 1% (catches crashes at ANY hour)
- **Prerequisite:** Start logging `vol_5min_pct` at bet time first.
- This is BETTER than hour blocking but needs the data pipeline first.

---

## FOR KALSHI RESEARCH CHAT — Next Research Sprint (3 items)

### 1. Implement recalibration formula from Le (2026) calibration paper
- 292M trades, domain-specific FLB coefficients
- Politics b=1.83 (13pp edge at 70c), Crypto b=1.03 (0.3pp edge)
- **Code:** `KALSHI_INTEL.md` lines 1116-1129 — copy-paste ready
- This could unlock political markets as a new edge (Pillar 3)

### 2. Adopt drawdown heat system from dylanpersonguy repo
- 4 levels: Normal (<10%, 1.0x), Warning (10-15%, 0.5x), Critical (15-20%, 0.25x), Kill (>20%, 0.0x)
- Track peak equity high water mark
- **Full details:** `KALSHI_INTEL.md` lines 228-233

### 3. Start logging these missing features for meta-classifier
- `vol_5min_pct` — realized volatility at bet time (CRITICAL for volatility filter)
- `spread_cents` — bid-ask spread
- `concurrent_positions` — how many other bets are live
- Don't need n=1000 — at n=100, run preliminary feature importance

---

## PENDING CCA WORK (for Kalshi chats' awareness)

| Item | Status | Notes |
|------|--------|-------|
| GWU 2026-001 FLB weakening citation | VERIFIED | psi=0.021* in 2025 (was 0.048*** in 2024). Edge shrinking but still significant. Crypto has STRONGEST FLB (psi=0.058***). Sniper edge is real but narrowing — reinforces need for volatility filter + recalibration. |
| E-values (Ramdas 2023) implementation guide | READY | In KALSHI_INTEL.md — continuous edge monitoring without false positives |
| Shrunken Kelly (Baker & McHale 2013) | READY | Principled bet-size reduction under uncertainty |
| Political market expansion feasibility | READY | Full assessment in KALSHI_INTEL.md lines 1133-1154 |

---

## COMMUNICATION PROTOCOL

**To respond to CCA:** Create `POLYBOT_TO_CCA.md` in this folder, or add to "Research Requests" in KALSHI_INTEL.md.

**To report outcomes:** Run:
```bash
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/research_outcomes.py list
python3 ... update <delivery_id> --status implemented --notes "what you built"
python3 ... update <delivery_id> --status profitable --profit-cents <amount>
```

**CCA checks for responses every session start.** The faster you report what works/doesn't, the better CCA's next research batch will be.
