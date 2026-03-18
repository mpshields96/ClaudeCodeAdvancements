# CCA Skillbook — Distilled Strategies That Survive Sessions
# Inspired by YoYo's self-evolving Skillbook pattern.
# NOT a journal. NOT raw reflections. These are ACTIONABLE STRATEGIES
# that get injected into context to make every session smarter.
#
# Format: Each strategy has a confidence score (0-100), source sessions,
# and a one-line directive that can be copy-pasted into a system prompt.
#
# Strategies get PROMOTED (confidence up) when validated by new evidence.
# Strategies get DEMOTED (confidence down) when contradicted.
# Strategies at confidence < 20 get ARCHIVED (moved to bottom).
#
# Updated: 2026-03-17 (Session 33)

---

## Hard Metric: APF (Actionable Per Find)

**The ruthless number: what % of findings lead to code, architecture decisions, or strategy changes?**

- BUILD + ADAPT findings = actionable
- REFERENCE + SKIP = noise (useful context but no code ships)
- **APF = (BUILD + ADAPT) / total findings * 100**

### Current APF: 32.1%
- BUILD: 19, ADAPT: 49, REFERENCE: 98, REFERENCE-PERSONAL: 13, SKIP: 32, HIGH-VALUE: 1 = 212 total
- Actionable: 68 / 212 = **32.1%**
- Target: **40% APF** (raise signal, cut noise)
- Kalshi equivalent: APF is to CCA what win rate is to the trading bot

### APF Levers (how to improve):
1. Raise min_score_threshold (currently 30 — sessions 23+ show <100 posts are mostly noise)
2. Add needle_ratio_cap to classifier (r/investing, r/LocalLLaMA saturated at 100%)
3. Prioritize deep-reads on BUILD/ADAPT candidates, skip REFERENCE-heavy subs
4. Weight frontier-specific subs (r/ClaudeCode) over general subs (r/investing)

### APF History:
| Session | Total Finds | Actionable | APF % | Note |
|---------|------------|------------|-------|------|
| 14-16   | ~45        | ~10        | 22%   | First nuclear scans, learning curve |
| 17-28   | ~120       | ~38        | 32%   | Calibrated scanning, better triage |
| 29-33   | ~47        | ~20        | 43%   | Focused deep-reads, frontier-targeted |

---

## Active Strategies (Confidence >= 50)

### S1: Deep-read BUILD/ADAPT candidates only — Confidence: 90
**Directive:** "When scanning, triage by title first. Only deep-read posts scoring >200pts OR containing frontier keywords. Skip low-engagement posts entirely."
- Source: Sessions 14, 23, 29-33
- Evidence: Posts >500pts have 3x higher BUILD/ADAPT rate. Title-based triage saves ~60% tokens on noisy subs.
- Last validated: Session 33

### S2: Parallel review agents for batch URLs — Confidence: 85
**Directive:** "Launch up to 5 review agents simultaneously for batch URL processing. Each agent costs ~45K tokens but runs in parallel, turning 30min serial work into 5min parallel."
- Source: Sessions 32-33
- Evidence: 5 parallel agents completed 5 reviews in ~90 seconds wall time. Token cost identical to serial but elapsed time 5x faster.
- Last validated: Session 33

### S3: Classifier needs per-sub keyword tuning — Confidence: 80
**Directive:** "If a subreddit scan returns >80% NEEDLE, the profile keywords are too generic. Add needle_ratio_cap to profiles.py and tighten keywords for that specific sub."
- Source: Sessions 32-33
- Evidence: r/investing (48/50 NEEDLE) and r/LocalLLaMA (50/50 NEEDLE) both saturated. Every post matches because the keywords are too broad for those subs.
- Last validated: Session 33

### S4: Memory promotion logic > storage/retrieval — Confidence: 80
**Directive:** "When building Frontier 1 memory system, prioritize the PROMOTION step (what gets kept vs demoted) over storage engine or retrieval algorithm. Community consensus: this is the hardest unsolved piece."
- Source: Sessions 33 (Obsidian+Claude review, cerebellum review)
- Evidence: 220pt Obsidian+Claude post, cerebellum's 3-layer filtering, YoYo's time-weighted decay. All approaches differ on storage but agree: curation is the bottleneck.
- Last validated: Session 33

### S5: Memories as strategies, not raw facts — Confidence: 75
**Directive:** "Store memories as distilled actionable strategies ('always check for path traversal in shell commands') not raw event logs ('Session 14: found path traversal bug'). Strategies survive context compression; raw facts don't."
- Source: Session 33 (agent accuracy "Skillbook" review, YoYo time-weighted synthesis)
- Evidence: YoYo abstracts old learnings into themes. Agent accuracy post's "Skillbook" injects strategies not recall. Both independently converged on this pattern.
- Last validated: Session 33

### S6: r/ClaudeCode is the only high-signal CCA sub — Confidence: 85
**Directive:** "Prioritize r/ClaudeCode for CCA frontier scanning. General subs (r/investing, r/LocalLLaMA, r/Anthropic) have near-zero BUILD/ADAPT rate for CCA. Scan them for Kalshi/personal intel only."
- Source: Sessions 23, 29-33
- Evidence: r/Anthropic scan: 0 BUILD/ADAPT. r/investing: 0 CCA-relevant. r/ClaudeCode: 19 BUILD + 49 ADAPT across all sessions.
- Last validated: Session 33

### S7: Agent Guard is highest-demand CCA frontier — Confidence: 90
**Directive:** "Agent Guard (Frontier 4) has the strongest community validation. Four independent catastrophic failure stories (F: drive wipe, S3 deletion, credential exposure, multi-agent conflicts) all point to the same gap. Prioritize AG development."
- Source: Sessions 29-33 (vibecoding deep-reads, permission model posts, autonomous agent posts)
- Evidence: ALL four vibecoding safety posts validated AG. safeexec and tirith are existing tools in this space but neither uses Claude Code hooks.
- Last validated: Session 33

### S8: Pre-assembled context beats ad-hoc prompting — Confidence: 75
**Directive:** "Orchestration not prompting. Pre-assemble all relevant context before starting a task, don't gather it during execution. This applies to spec-system (requirements before code), nuclear scans (profile keywords before fetch), and memory injection (hook delivers context, agent doesn't search for it)."
- Source: Sessions 12, 33 (100K lines solo dev review, spec-system design)
- Evidence: 100K lines dev: "The agents that actually work are the ones where context is pre-assembled before the task starts." Validates CCA's hook-based delivery over search-based retrieval.
- Last validated: Session 33

---

## Emerging Strategies (Confidence 30-49)

### S9: Time-weighted memory decay complements TTL — Confidence: 40
**Directive:** "Consider dual decay: TTL-by-confidence for deletion, time-weighted abstraction for compression. Recent memories stay full-detail, old memories get compressed into theme summaries."
- Source: Session 33 (YoYo review)
- Evidence: YoYo's approach (recent=full, old=themes). Only one implementation seen. Needs validation against CCA's TTL approach.

### S10: Dedicated role-agents beat general agents for visual output — Confidence: 35
**Directive:** "For non-code outputs (diagrams, docs, marketing), use a dedicated agent with a role-specific system prompt rather than asking a general agent. Quality gap is significant."
- Source: Session 33 (100K lines review — diagram agents)
- Evidence: Single post. OP's UX + marketing agents produced polished infographics. N=1, needs more evidence.

---

## Archived Strategies (Confidence < 20)

(None yet — Skillbook initialized Session 33)

---

## Growth Tracking (YoYo-Inspired)

### CCA Evolution Metrics
| Metric | Session 14 | Session 23 | Session 33 | Trend |
|--------|-----------|-----------|-----------|-------|
| Total findings | 0 | ~90 | 212 | Growing |
| APF % | 22% | 32% | 32.1% | Plateau — need lever |
| Test suites | 8 | 20 | 30 | Growing |
| Total tests | 283 | ~700 | 1259 | Growing |
| Active strategies | 0 | 0 | 10 | NEW |
| Modules | 5 | 7 | 9+ | Growing |

### Next Evolution Targets
1. **APF to 40%** — Raise min_score_threshold to 50, add needle_ratio_cap
2. **Strategy count to 20** — Distill more patterns from journal.jsonl backlog
3. **Auto-inject top strategies** — Hook that reads SKILLBOOK.md and injects S1-S8 into session context
4. **Strategy validation loop** — Each session checks if new evidence confirms or contradicts active strategies
