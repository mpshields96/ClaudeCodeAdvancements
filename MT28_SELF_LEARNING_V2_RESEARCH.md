# MT-28: Self-Learning v2 (Multi-Domain) — Research Summary
# Phase 1 Research — 2026-03-21 (S104)

---

## Problem Statement

CCA's self-learning system (journal.py, reflect.py, improver.py, strategy.json) is production-quality but domain-locked. It learns from CCA's own operations but can't transfer insights to Kalshi trading, and Kalshi outcomes don't feed back into research prioritization. The system also lacks predictive capability — it detects patterns after-the-fact but doesn't anticipate failures.

---

## Current Architecture (Audit Summary)

**What exists (1552 tests, 38 suites):**
- journal.py: 17 event types, append-only JSONL, 800+ events across 50+ sessions
- reflect.py: 11 pattern detectors (5 general + 6 trading-specific)
- improver.py: Proposal lifecycle with SentinelMutator (adaptive mutations)
- strategy.json: 4 sections (nuclear_scan, trading, learning, session) with bounded params
- trace_analyzer.py: Session quality metrics (retries, waste, efficiency)
- SKILLBOOK.md: Distilled actionable strategies

**10 gaps identified for cross-domain:**
1. Domain knowledge embedded in enums — adding domains requires changing 3 files
2. Pattern detectors monolithic in reflect.py — no plugin/registry pattern
3. Risk classification hardcoded per domain
4. Sentinel mutations domain-aware but static
5. No cross-domain reasoning — patterns don't inform other domains
6. Strategy tuning threshold-based only — no model learning
7. Confidence scoring manual — no Bayesian updating
8. **Research outcomes are delivery-only — no feedback loop** (CRITICAL)
9. No domain schema registry
10. **No cross-project intelligence** (CRITICAL)

---

## Academic Research Findings

### Tier 1: Directly Relevant Architectures

| System | Paper/Repo | Key Pattern | Relevance to CCA |
|--------|-----------|-------------|-------------------|
| **EvolveR** | arXiv 2510.16079 | Distill trajectories into strategic principles with success scoring | Best fit for cross-domain transfer |
| **Godel Agent** | arXiv 2410.04444, github.com/Arvid-pku/Godel_Agent | Recursive self-modification via monkey-patching, $15/30 iterations | Cheapest self-improvement loop |
| **SAFLA** | github.com/ruvnet/SAFLA | 4-memory architecture (vector, episodic, semantic, working) with MCP integration | Only impl targeting Claude Code |
| **Darwin Godel Machine** | arXiv 2505.22954, github.com/jennyzzt/dgm | Evolutionary self-improving agent, 20%→50% on SWE-bench | Proof of autonomous improvement |
| **EvoAgentX** | github.com/EvoAgentX/EvoAgentX | Self-evolving ecosystem with dual memory + human-in-loop | Full framework reference |

### Tier 2: Relevant Patterns

| Paper | Key Insight |
|-------|-------------|
| Cross-Domain RL Transfer Survey (arXiv 2404.17687) | Domain-agnostic: confidence calibration, explore/exploit, failure classification. Domain-specific: feature representations, reward signals, time horizons. |
| DARWIN (arXiv 2602.05848) | Genetic mutation of agent code with 0.3 mutation probability per chunk, JSON memory tracking |
| SAGE (arXiv 2512.17102) | Skill library + RL for cross-environment adaptation |
| Self-Improving Coding Agent (arXiv 2504.15228) | Non-gradient LLM reflection + code self-editing, 17-53% improvement |
| MAR Multi-Agent Reflexion (arXiv 2512.20845) | Multi-persona critique replacing single-agent self-reflection |

### Reference Lists
- Awesome Self-Evolving Agents: github.com/EvoAgentX/Awesome-Self-Evolving-Agents
- Autonomous Agents Papers (daily updated): github.com/tmgthb/Autonomous-Agents

---

## Proposed Architecture: Three-Pattern Synthesis

The optimal MT-28 architecture combines three proven patterns:

### Pattern 1: EvolveR-Style Principle Distillation

After each session (coding OR trading), distill the trajectory into abstract strategic principles:

```
Session trajectory → Principle extraction → Success/usage tracking → Retrieval for next session
```

**Principle schema:**
```json
{
  "id": "prin_20260321_abc123",
  "text": "When initial evidence is ambiguous, seek corroborating sources before committing",
  "source_domain": "cca_operations",
  "applicable_domains": ["cca_operations", "trading_research"],
  "success_count": 12,
  "usage_count": 18,
  "score": 0.65,
  "created_session": 104,
  "last_used_session": 108
}
```

**Scoring formula (Laplace-smoothed):**
```
s(p) = (success_count + 1) / (usage_count + 2)
```

Principles scoring below 0.3 get pruned. Above 0.7 get reinforced.

**What transfers across domains (domain-agnostic):**
- "Multi-source corroboration reduces false positives"
- "When data is sparse, ensemble weak signals rather than trusting one strong signal"
- "Approach X fails when sample size < threshold"
- Confidence calibration heuristics
- Explore vs exploit tradeoffs

**What stays domain-specific:**
- Feature representations (code ASTs vs price time-series)
- Reward signals (test pass/fail vs continuous P&L)
- Time horizons (seconds vs hours)
- Risk profiles (compute cost vs money cost)

### Pattern 2: Enhanced Sentinel Adaptive Mutation

Current SentinelMutator already does targeted mutations. Enhance with:

1. **Failure analysis before mutation**: Classify WHY a strategy failed (bad data, wrong domain, timing, insufficient sample)
2. **Counter-strategy generation**: LLM-analyzed targeted modification based on failure mode (not random)
3. **Cross-domain pollination**: When a principle succeeds in domain A, test adapted version in domain B
4. **Automatic domain mapping**: Translate domain-specific concepts (e.g., "retry" in coding = "re-enter" in trading)

### Pattern 3: Research Outcomes Feedback Loop (THE CRITICAL WIRE)

This is the single most important missing piece:

```
CCA recommends paper X → Kalshi implements strategy from paper X
→ Strategy produces +$Y or -$Z → Outcome feeds back to CCA
→ Principle that led to recommending paper X gets score update
→ Future research prioritization reflects what actually worked
```

**Implementation:**
```json
// research_outcomes.jsonl entry (enhanced)
{
  "delivery_id": "del_20260321_abc123",
  "research_item": "Bayesian calibration paper",
  "delivered_to": "kalshi_main",
  "delivered_session": 104,
  "kalshi_action": "implemented_calibration_v2",
  "outcome": {
    "pnl_cents": 450,
    "bets_influenced": 12,
    "win_rate_delta": "+0.08",
    "recorded_session": 115
  },
  "principles_updated": ["prin_bayesian_calibration_001"]
}
```

**The closed loop:**
1. CCA delivers research intelligence to Kalshi via cross_chat_queue.jsonl
2. Kalshi bot logs which research items influenced which bets
3. Bet outcomes (P&L) flow back to CCA via return channel
4. CCA updates principle scores based on downstream profitability
5. Future research prioritization uses updated scores to pick papers/topics

---

## Implementation Plan (Phased)

### Phase 1: Principle Registry (Foundation)
- Add `principles.jsonl` to self-learning module
- Implement principle extraction from session trajectories
- Implement Laplace-smoothed scoring formula
- Wire into reflect.py as new pattern source
- Tests: principle CRUD, scoring, pruning, dedup
- **Estimate: 1-2 sessions**

### Phase 2: Pattern Plugin Registry (Extensibility)
- Refactor reflect.py's 11 detectors from monolithic function to registry pattern
- Each detector becomes a registered plugin with domain tag
- New domains can add detectors without modifying reflect.py core
- Tests: plugin registration, domain filtering, backwards compatibility
- **Estimate: 1-2 sessions**

### Phase 3: Cross-Domain Principle Transfer
- Add `applicable_domains` field to principles
- Implement domain-mapping heuristics (coding↔trading concept translation)
- Retrieve top-3 principles by relevance when acting in any domain
- Track cross-domain success/failure separately
- Tests: cross-domain retrieval, domain-specific scoring, transfer validation
- **Estimate: 2-3 sessions**

### Phase 4: Research Outcomes Feedback Loop
- Enhance research_outcomes.jsonl schema with Kalshi outcome tracking
- Build return channel: Kalshi bot reports which research items influenced bets
- Wire P&L outcomes back to principle score updates
- Auto-prune research directions with consistently negative ROI
- Tests: feedback loop integrity, score propagation, pruning safety
- **Estimate: 2-3 sessions** (requires coordination with Kalshi bot)

### Phase 5: Predictive Capability
- Move from pattern detection (reactive) to pattern prediction (proactive)
- Use principle scores + trajectory similarity to predict session outcomes
- Pre-session recommendations: "Based on similar past sessions, avoid X, try Y"
- Tests: prediction accuracy tracking, recommendation quality
- **Estimate: 2-3 sessions**

### Phase 6: Sentinel v2 (Cross-Domain Mutations)
- Enhanced failure classification (why, not just what)
- Cross-domain counter-strategy generation
- Automatic domain concept mapping
- Mutation success tracking across domains
- Tests: mutation quality, cross-domain transfer success rate
- **Estimate: 2-3 sessions**

**Total: 10-16 sessions across all 6 phases**

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Over-engineering abstractions | Phase 1 is minimal (one JSONL file + scoring). Only add complexity when proven needed. |
| Cross-domain noise | Domain-specific scoring prevents coding noise from corrupting trading decisions |
| Feedback loop latency | Trading outcomes take days/weeks. Use batch updates, not real-time. |
| Principle explosion | Dedup by semantic similarity. Cap at 100 active principles per domain. |
| Breaking existing tests | Plugin registry (Phase 2) must maintain backwards compatibility. All 1552 tests must pass. |

---

## Relationship to Other MTs

| MT | Relationship |
|---|---|
| **MT-0** | Phase 4 of MT-28 depends on MT-0 Phase 2 being deployed (Kalshi bot must log which research influenced bets) |
| **MT-26** | Financial Intelligence Engine produces the research items that MT-28's feedback loop evaluates |
| **MT-7** | Trace analyzer provides session quality data that feeds principle extraction |
| **MT-10** | YoYo self-learning (COMPLETED) is the foundation MT-28 extends |

**Dependency chain: MT-0 Phase 2 → MT-28 Phase 4 → MT-26 integration**

---

## Sources

- EvolveR: arXiv 2510.16079
- Godel Agent: arXiv 2410.04444, github.com/Arvid-pku/Godel_Agent
- SAFLA: github.com/ruvnet/SAFLA
- Darwin Godel Machine: arXiv 2505.22954, github.com/jennyzzt/dgm
- EvoAgentX: github.com/EvoAgentX/EvoAgentX
- Cross-Domain RL Transfer Survey: arXiv 2404.17687
- DARWIN: arXiv 2602.05848
- Self-Improving Coding Agent: arXiv 2504.15228
- Comprehensive Survey on Self-Evolving Agents: arXiv 2508.07407
- Awesome Self-Evolving Agents: github.com/EvoAgentX/Awesome-Self-Evolving-Agents
