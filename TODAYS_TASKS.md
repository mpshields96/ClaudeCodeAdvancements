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

### K1. REQ-027: Monte Carlo + Synthetic Origination + Edge Stability [DONE S151]
- Built and committed: edge_stability.py (40t), synthetic_bet_generator.py (28t), monte_carlo_simulator.py (27t)
- Delivered to polybot repo. CCA_TO_POLYBOT.md updated.

### K2. REQ-025: Second Edge Discovery [URGENT]
- Find >3% EV/bet, >5 bets/day edge
- Current sniper ~8 USD/day. Target: 15-25 USD/day total
- Research + validate structural basis

### K3. Respond to Kalshi Topics A-D [DONE S151]
- All 4 topics responded via CCA_TO_POLYBOT.md
- REQ-030 convergence spec delivered, REQ-031 synthetic validation completed

### K4. Ongoing Cross-Chat Coordination
- Check POLYBOT_TO_CCA.md every cycle
- Write CCA_TO_POLYBOT.md deliveries promptly
- Implement any Kalshi chat deliveries same-session

---

## CCA IMPROVEMENTS

### C1. Autoloop Correctly Firing [DONE S151]
- Flag file created, breadcrumb cleared, trigger verified ready
- Stop hook wired in settings.local.json

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

### C2 Notes: Report Visual Findings (from S154 agent — persisted S155)
Agent did a 20-page visual audit of CCA_STATUS_REPORT_2026-03-24.pdf. Key issues found:
- MT Phase Progress chart: X-axis labels overlap and are unreadable
- Chart axes show decimal values for integer data (LOC counts, file counts)
- Pages 5 and 10 have significant wasted whitespace
- design-guide.md color palette does not match actual Typst template colors
- Suggested fixes: rotate/abbreviate X labels, force integer axis ticks, compress whitespace, sync color definitions
These are actionable Typst template fixes — no research needed, just implementation.
