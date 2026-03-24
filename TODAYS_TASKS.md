# CCA Tasks for 2026-03-24 (Matthew's Full Directive)
# Created: S151. Read by ALL subsequent CCA chats today.
# This file persists across sessions so nothing gets forgotten.

---

## Priority Allocation (Matthew directive)
- **50%+ time on Kalshi bot work** (higher priority)
- Remaining time on CCA improvements
- Frequent comms with Kalshi main chat (starting now)

---

## KALSHI BOT WORK (HIGH PRIORITY — 50%+)

### K1. REQ-027: Monte Carlo + Synthetic Origination + Edge Stability [URGENT]
- Build three scripts: monte_carlo_simulator.py, synthetic_bet_generator.py, edge_stability.py
- Matthew explicitly ordered this. #1 build priority.
- Filed 2026-03-24 07:06 UTC in POLYBOT_TO_CCA.md

### K2. REQ-025: Second Edge Discovery [URGENT]
- Find >3% EV/bet, >5 bets/day edge
- Current sniper ~8 USD/day. Target: 15-25 USD/day total
- Research + validate structural basis

### K3. Respond to Kalshi Topics A-D (from POLYBOT_TO_CCA.md)
- TOPIC A: Bet type expansion beyond 15-min crypto contracts
- TOPIC B: Knowledge expansion (FLB non-sports, sequential testing, Kelly in binary markets)
- TOPIC C: Convergence detector integration into Kalshi strategy health
- TOPIC D: synthesis.trade cross-platform signal follow-up

### K4. Ongoing Cross-Chat Coordination
- Check POLYBOT_TO_CCA.md every cycle
- Write CCA_TO_POLYBOT.md deliveries promptly
- Implement any Kalshi chat deliveries same-session

---

## CCA IMPROVEMENTS

### C1. Autoloop Correctly Firing [HIGH]
- Autoloop was disabled last night — re-enable for today
- Verify autoloop_stop_hook.py fires correctly
- Test the full loop: wrap -> stop hook -> new session spawn
- Ensure /cca-wrap runs at the right time (not too early, not too late)

### C2. Report Visual Enhancement Research [MEDIUM]
- Read CCA_STATUS_REPORT_2026-03-24.pdf — assess current state
- Research how reports could become much more advanced:
  - Style and appearance improvements
  - Formatting and layout upgrades
  - Content depth and readability
  - Charts/graphs/figures (more types, better data viz)
  - Key data points to add to each section
  - Trend/delta data (report_differ integration)
- This is exploration/research — not necessarily building all of it today

### C3. MT Knockouts [MEDIUM]
- Continue knocking out MTs from MASTER_TASKS.md
- Priority picker: `python3 priority_picker.py full --session 151`
- Focus on MTs that advance the Two Pillars (Get Smarter, Get More Bodies)

### C4. Discover Advancements to Other MTs [LOW]
- While working, identify connections/advancements that apply to other MTs
- Log discoveries in session state

### C5. Address "Honest Assessment" Report Issues [LOW]
- Read the honest assessment section of CCA reports
- Identify and fix gaps/issues flagged there

### C6. MT-32 Report Improvements (from S150 carryover)
- TOC page numbers
- Cover title fix
- MT phase tracking contradictions
- Trend/delta section (report_differ.py integration)
- MT section condensing

---

## SESSION RULES
- Autoloop SHOULD fire at end of this session (re-enabled for today)
- Keep Kalshi comms frequent — Kalshi main chat is active NOW
- Each subsequent CCA chat reads THIS FILE to know what to work on
- Mark items [DONE] as they complete, but NEVER remove them
