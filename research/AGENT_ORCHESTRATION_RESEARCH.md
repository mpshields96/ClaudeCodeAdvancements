# Agent Orchestration Research — S190 (Matthew Directive)

**Date:** 2026-03-26
**Source:** S190 directive — research agent use, multi-agent systems, orchestration patterns
**Scope:** Reddit, GitHub repos, academic papers

---

## 1. Top Multi-Agent Frameworks (GitHub, ranked by stars)

| Framework | Stars | Key Pattern | Language | Notes |
|-----------|-------|-------------|----------|-------|
| Dify | 134K+ | Visual workflow builder | Python | More orchestration than agent |
| LangChain/LangGraph | 116K | Graph-based state machine | Python | Fastest execution in benchmarks |
| CrewAI | 46.8K | Role-playing autonomous agents | Python | Longest deliberation delays |
| DeerFlow | 37K+ | ByteDance SuperAgent harness | Python | Hit #1 GitHub trending Feb 2026 |
| Mastra | 22.3K+ | TypeScript-native orchestration | TypeScript | Launched Jan 2026, rapid growth |
| AgentScope | 19.6K+ | Alibaba production multi-agent | Python | Production-grade, research-backed |
| Swarms | ~8K | Enterprise multi-agent swarms | Python | Ambitious scope, less proven |
| AWS Agent Squad | ~3K | Flexible agent management | Python/TS | AWS official, conversation handling |

**CCA relevance:** Our hivemind (MT-21) is most similar to CrewAI's role-based pattern (coordinator + workers). LangGraph's state machine model could inform our session_orchestrator.py.

---

## 2. Claude-Specific Multi-Agent Patterns

### Claude Agent Teams (Official — Experimental)
- One "team lead" session coordinates via shared task list
- Teammates run in separate context windows, communicate directly
- Built-in to Claude Code — uses TeammateTool (AG-10 worktree_guard already handles this)

### Third-Party Orchestrators for Claude
| Tool | Pattern | Stars | Notes |
|------|---------|-------|-------|
| Shipyard | Production multi-agent Claude Code | N/A | Blog/commercial |
| Gas Town | Task decomposition + parallel workers | N/A | Community tool |
| Multiclaude | Primary agent spawns subagents | N/A | Community tool |
| Ruflo | Swarm orchestration platform | ~1K | RAG + distributed swarms |
| Agentrooms | Multi-agent dev workspace | N/A | Claude Code specific |

### Execution Modes (from community patterns)
1. **Autopilot** — autonomous end-to-end (our /cca-auto)
2. **Ultrapilot** — 3-5 parallel workers (our hivemind vision Phase 5)
3. **Swarm mode** — explicit dependencies + messaging (our cca_comm.py)
4. **Pipeline** — sequential chaining (our desktop autoloop)
5. **Ecomode** — token efficiency optimization (our peak/off-peak budgeting)

**CCA relevance:** We already implement patterns 1, 3, and 4. Pattern 2 (Ultrapilot) is our Phase 5 hivemind target. Pattern 5 maps to our MT-38 token budget system.

---

## 3. Academic Research — Failure Modes

### Paper: "Why Do Multi-Agent LLM Systems Fail?" (Cemri et al., 2025)
- **arXiv:** 2503.13657
- **Dataset:** MAST-Data — 1,600+ annotated traces across 7 MAS frameworks
- **Taxonomy:** MAST — 14 unique failure modes in 3 categories

**Category 1: System Design Issues**
- Agents assigned tasks outside their capabilities
- Inadequate tool/resource allocation
- Poor prompt engineering for agent roles

**Category 2: Inter-Agent Misalignment**
- Conversation resets (FM-2.1): 2.20% of failures
- Wrong assumptions without clarification (FM-2.2): 6.80% of failures
- Role swapping — agents inadvertently exchange roles
- Infinite message loops — stuck in unproductive exchanges
- Communication overhead offsetting coordination gains

**Category 3: Task Verification**
- Insufficient verification of completed work
- Agents proceeding without validating intermediate results

**CCA relevance — DIRECT APPLICABILITY:**
- FM-2.1 (conversation resets): Our autoloop handles this via SESSION_RESUME.md
- FM-2.2 (wrong assumptions): Our cca_comm.py explicit messaging prevents this
- Role swapping: Our hivemind rules (.claude/rules/hivemind-worker.md) explicitly prevent this
- Infinite loops: Our session_pacer.py + context monitor prevent runaway loops
- Verification: Our test-before-commit + wrap self-grading addresses this

### Paper: "Multi-Agent Collaboration Mechanisms: A Survey of LLMs" (2025)
- **arXiv:** 2501.06322
- Comprehensive survey of collaboration mechanisms
- Key finding: scaling agents yields diminishing or negative returns without proper coordination

### Paper: "On the Uncertainty of Large Language Model-Based Multi-Agent Systems" (2026)
- **arXiv:** 2602.04234
- Analyzes uncertainty propagation in multi-agent LLM systems
- Key finding: uncertainty compounds across agent interactions

### Paper: "MAESTRO: Multi-Agent Evaluation Suite" (2026)
- **arXiv:** 2601.00481
- Evaluation framework for multi-agent systems
- Benchmarks coordination quality, not just task completion

---

## 4. Actionable Insights for CCA

### Already Doing Well (validated by literature)
1. Role-based agent assignment (hivemind coordinator/worker) — matches CrewAI best practice
2. Explicit communication channel (cca_comm.py) — prevents FM-2.2 wrong assumptions
3. Session state persistence (SESSION_STATE.md) — prevents FM-2.1 conversation resets
4. Token budget awareness (MT-38) — matches Ecomode pattern
5. Scope isolation (worktree_guard) — matches Agent Teams best practice

### Gaps to Address
1. **No formal task dependency graph** — our cca_comm.py is flat messaging, not DAG-based.
   LangGraph's state machine approach could improve multi-task ordering.
2. **No intermediate verification** — workers commit and report done, but no automated
   verification before coordinator accepts. The MAST taxonomy shows this is the #3 failure category.
3. **No scaling analysis** — we haven't measured diminishing returns at 3+ agents.
   Literature suggests 2-3 agents is optimal; beyond that, overhead dominates.
4. **No uncertainty tracking** — we don't track confidence across agent handoffs.
   2602.04234 shows uncertainty compounds. Our principle_registry could track this.

### Next Steps (propose as MT phases)
1. **MT-21 Phase 6: Intermediate verification** — worker output auto-tested by coordinator before merge
2. **MT-21 Phase 7: Task dependency DAG** — upgrade cca_comm.py to support ordered task graphs
3. **MT-44 enhancement: Scaling benchmark** — measure overhead at 2, 3, 4 agents empirically
4. **Research: Read MAST paper fully** — 1,600 traces of failure modes, directly applicable to CCA

---

## 5. Sources

- [awesome-llm-agents](https://github.com/kaushikb11/awesome-llm-agents) — Curated list of LLM agent frameworks
- [LLM Orchestration 2026](https://aimultiple.com/llm-orchestration) — Top 22 frameworks comparison
- [CrewAI](https://github.com/crewAIInc/crewAI) — Role-playing agent orchestration (46.8K stars)
- [AgentScope](https://www.decisioncrafters.com/agentscope-build-production-ready-multi-agent-systems/) — Alibaba production multi-agent
- [Claude Agent Teams Docs](https://code.claude.com/docs/en/agent-teams) — Official Claude multi-agent
- [Shipyard Multi-Agent Guide](https://shipyard.build/blog/claude-code-multi-agent/) — Claude Code multi-agent patterns
- [MAST: Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) — 14 failure modes taxonomy
- [Multi-Agent Collaboration Mechanisms Survey](https://arxiv.org/abs/2501.06322) — Comprehensive collaboration survey
- [Uncertainty in Multi-Agent LLM Systems](https://arxiv.org/abs/2602.04234) — Uncertainty propagation analysis
- [MAESTRO Evaluation Suite](https://arxiv.org/abs/2601.00481) — Multi-agent evaluation benchmark
