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
# Updated: 2026-03-18 (Session 43)

---

## Hard Metric: APF (Actionable Per Find)

**The ruthless number: what % of findings lead to code, architecture decisions, or strategy changes?**

- BUILD + ADAPT findings = actionable
- REFERENCE + SKIP = noise (useful context but no code ships)
- **APF = (BUILD + ADAPT) / total findings * 100**

### Current APF: 31.4%
- BUILD: 19, ADAPT: 51, REFERENCE: 101, REFERENCE-PERSONAL: 14, SKIP: 36, HIGH-VALUE: 1 = 222 total
- Actionable: 70 / 222 = **31.4%**
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

### S3: Classifier needs per-sub keyword tuning — Confidence: 95 (IMPLEMENTED)
**Directive:** "If a subreddit scan returns >80% NEEDLE, the profile keywords are too generic. Use needle_ratio_cap in profiles.py to cap NEEDLE ratio and tighten keywords."
- Source: Sessions 32-33, implemented Session 35
- Evidence: r/investing (48/50 NEEDLE) and r/LocalLLaMA (50/50 NEEDLE) both saturated. Fixed: needle_ratio_cap field added (0.35 for investing, 0.4 for LocalLLaMA), quick_scan_triage demotes lowest-score NEEDLEs when ratio exceeds cap.
- Last validated: Session 35 (6 tests passing)

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

### S10: CLAUDE.md as router, not monolith — Confidence: 45
**Directive:** "Keep CLAUDE.md as a lightweight index/router that points to focused skill/rule files. Load only what's needed for the current task. A monolithic CLAUDE.md burns early context where the model is smartest. The 80/20 rule: a good CLAUDE.md is the 80%, everything else is the 20%."
- Source: Session 43 (harness setups thread, u/diystateofmind + u/bensyverson)
- Evidence: u/diystateofmind: "I treat agents.md like an index/router instead of the rules file to reduce context — on Pro Max and never hit limits." u/bensyverson: "good CLAUDE.md is the 80/20 — last thing you want is harness sucking up early context where the model is smartest." u/Certain_Housing8987: regex-triggered rules have zero cognitive overhead vs skills (giant switch statement).
- Last validated: Session 43

### S11: Retrospective at 80% implementation — Confidence: 40
**Directive:** "At ~80% through a complex implementation, pause and ask: 'knowing what we know now, what would we do differently if we refactored from scratch?' This surfaces architectural mistakes before they're cemented. Can be looped until an evaluator passes. Applies across all projects."
- Source: Session 43 (harness setups thread, u/reliant-labs "Get-It-Right" loop)
- Evidence: u/reliant-labs: "the best results I have is typically when 80% through and I ask what we'd do differently." Matches YoYo retrospective pattern. github.com/reliant-labs/get-it-right implements this as an automated loop.
- Last validated: Session 43

### S12: Dedicated role-agents beat general agents for visual output — Confidence: 35
**Directive:** "For non-code outputs (diagrams, docs, marketing), use a dedicated agent with a role-specific system prompt rather than asking a general agent. Quality gap is significant."
- Source: Session 33 (100K lines review — diagram agents)
- Evidence: Single post. OP's UX + marketing agents produced polished infographics. N=1, needs more evidence.

---

## Archived Strategies (Confidence < 20)

(None yet — Skillbook initialized Session 33)

---

## Growth Tracking (YoYo-Inspired)

### CCA Evolution Metrics
| Metric | Session 14 | Session 23 | Session 33 | Session 35 | Trend |
|--------|-----------|-----------|-----------|-----------|-------|
| Total findings | 0 | ~90 | 212 | 222 | +10 S43 |
| APF % | 22% | 32% | 32.1% | 31.4% | r/ClaudeAI SKIP dilution |
| Test suites | 8 | 20 | 30 | 38 | +6 since S35 |
| Total tests | 283 | ~700 | 1259 | 1552 | +188 since S35 |
| Active strategies | 0 | 0 | 10 | 12 | +S10, S11 this session |
| Modules | 5 | 7 | 9+ | 10+ | Stable |

### Next Evolution Targets
1. **APF to 40%** — needle_ratio_cap DEPLOYED (S35). Next: raise min_score_threshold to 50
2. **Strategy count to 20** — Distill more patterns from journal.jsonl backlog
3. ~~**Auto-inject top strategies**~~ DONE (Session 35) — skillbook_inject.py hook built
4. **Strategy validation loop** — Each session checks if new evidence confirms or contradicts active strategies
5. **Wire skillbook_inject into settings.json** — Hook built but not yet wired into Claude Code hooks config
