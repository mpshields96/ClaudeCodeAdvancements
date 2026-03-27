# S190 Agent/Multi-Agent Research — Session 199

**Directive:** Matthew S190 — "we need more research on reddit/github/academic papers regarding agent use/multi-agent use/orchestrations"

**Date:** 2026-03-26

---

## 1. Claude Code Agent Teams (Official — Anthropic)

**Source:** [Anthropic Docs](https://code.claude.com/docs/en/agent-teams)

**Status:** Experimental, disabled by default. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and Claude Code v2.1.32+.

**Architecture:**
- Team lead (main session) + teammates (separate Claude Code instances)
- Shared task list with pending/in-progress/completed states + dependency tracking
- Mailbox system for direct peer-to-peer messaging (unlike subagents which only report back)
- File locking prevents race conditions on task claiming
- Storage: `~/.claude/teams/{name}/config.json`, `~/.claude/tasks/{name}/`

**Display modes:** in-process (Shift+Down to cycle) or split panes (tmux/iTerm2)

**Key capabilities:**
- Lead can require plan approval before teammates implement
- TeammateIdle, TaskCreated, TaskCompleted hooks for quality gates
- Teammates load same CLAUDE.md/MCP/skills but NOT lead's conversation history
- Broadcast messages to all teammates (use sparingly — cost scales linearly)

**Best practices (from docs):**
- 3-5 teammates for most workflows
- 5-6 tasks per teammate
- Start with research/review tasks before parallel implementation
- Avoid same-file edits across teammates
- Pre-approve common operations to reduce permission prompt friction

**Limitations:**
- No session resumption with in-process teammates
- No nested teams (teammates can't spawn teams)
- One team per session, lead is fixed
- Split panes not supported in VS Code terminal, Windows Terminal, Ghostty

**CCA relevance:** HIGH. This is the official multi-agent feature. CCA's hivemind (MT-21) should align with/extend Agent Teams rather than compete. AG-10 worktree_guard already provides isolation. Key gap: CCA's cca_comm.py predates Agent Teams — evaluate whether to migrate.

---

## 2. Community Orchestration Frameworks

### 2a. Gas Town (Steve Yegge)
- Mayor agent decomposes tasks, spawns worker Polecats
- Witness agent monitors quality
- Kubernetes-like structure
- Best for solo developers

### 2b. Multiclaude (Dan Lorenc)
- Supervisor assigns to subagents
- "Singleplayer" (auto-merge) and "multiplayer" (peer review) modes
- Brownian ratchet: always push forward if tests pass
- Best for team workflows with human review

### 2c. Ruflo (ruvnet/ruflo on GitHub)
- 313+ MCP tools, self-learning neural capabilities
- Enterprise-grade distributed swarm intelligence
- Native Claude Code/Codex integration
- RAG integration built in

### 2d. Overstory (jayminwest/overstory)
- Pluggable runtime adapters for Claude Code, Pi, and more
- Explicit warnings about multi-agent risks: compounding errors, cost amplification, debug complexity

### 2e. Claude Swarm (affaan-m/claude-swarm)
- Built with Claude Agent SDK for hackathon (Feb 2026)
- Opus 4.6 analyzes codebases, creates dependency graphs
- Parallel agent execution with Opus quality gate on combined output
- Rich terminal UI

### 2f. Metaswarm (dsifry/metaswarm)
- Self-improving framework, 18 agents, 13 skills, 15 commands
- Recursive orchestration: Coordinators spawn Issue Orchestrators for complex epics
- TDD enforcement, quality gates, spec-driven development

### 2g. Ccswarm (nwiizo/ccswarm)
- Git worktree isolation per agent
- Specialized AI agents for collaborative development

**CCA relevance:** MEDIUM. These are all "swarm" approaches. Key insight: the market converges on leader+workers+shared-task-list as the dominant pattern. CCA already has this with desktop+workers+cca_comm.py. The gap is: CCA lacks the quality gate / watchdog agent pattern.

---

## 3. Microsoft Azure Agent Design Patterns

**Source:** [Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)

Five canonical patterns:

| Pattern | Description | When to Use |
|---------|-------------|-------------|
| **Sequential** | Pipeline — each agent builds on previous output | Clear linear dependencies, progressive refinement |
| **Concurrent** | Fan-out/fan-in — agents work same task in parallel | Multiple perspectives needed, time-sensitive |
| **Group Chat** | Shared conversation thread, chat manager coordinates | Brainstorming, structured validation, quality gates |
| **Handoff** | Agents transfer control based on context | Domain transitions, escalation workflows |
| **Magentic** | Dynamic role assignment based on task evolution | Complex evolving tasks, adaptive specialization |

**Key design insight:** "Justify multi-agent complexity by demonstrating that a single agent can't reliably handle the task due to prompt complexity, tool overload, or security requirements."

**CCA relevance:** HIGH. CCA uses Sequential (slim_init pipeline), Concurrent (parallel test runners, dual-chat), and Handoff (cross-chat coordination). Missing: Group Chat (for design reviews/brainstorming) and Magentic (for adaptive role assignment). The Handoff pattern maps directly to CCA's cross-chat protocol.

---

## 4. Academic Papers

### 4a. LLM-Coordination (NAACL 2025)
- **Paper:** [arXiv:2310.03903](https://arxiv.org/abs/2310.03903)
- Introduces LLM-Coordination Benchmark for pure coordination games
- Cognitive Architecture for Coordination (CAC): plug-and-play LLM modules
- Tests environment comprehension, theory of mind, joint planning
- **Takeaway:** Coordination ability varies dramatically by model. Claude-class models perform best.

### 4b. Multi-Agent Collaboration Mechanisms: A Survey (2025)
- **Paper:** [arXiv:2501.06322](https://arxiv.org/abs/2501.06322)
- Taxonomy: actors, types (cooperation/competition/coopetition), structures (P2P/centralized/distributed), strategies, protocols
- **Takeaway:** Centralized (leader+workers) dominates for practical systems. P2P is theoretically elegant but harder to debug.

### 4c. Multi-Agent LLM Orchestration for Incident Response (2025)
- **Paper:** [arXiv:2511.15755](https://arxiv.org/abs/2511.15755)
- 100% actionable recommendation rate vs 1.7% for single-agent
- 80x improvement in action specificity, 140x in solution correctness
- **Takeaway:** Multi-agent is dramatically better for complex decision support. Not marginal improvement — order-of-magnitude.

### 4d. LLM-Based Multi-Agent Systems for Software Engineering (ACM TOSEM 2025)
- **Paper:** [DOI:10.1145/3712003](https://dl.acm.org/doi/10.1145/3712003)
- Comprehensive literature review of multi-agent for SE
- **Takeaway:** The field is maturing rapidly. Standard patterns emerging.

### 4e. TRiSM for Agentic AI (2025)
- **Paper:** [arXiv:2506.04133](https://arxiv.org/abs/2506.04133)
- Trust, Risk, Security Management framework for agentic multi-agent systems
- Four pillars: explainability, ModelOps, security, privacy/governance
- **Takeaway:** Security boundaries between agents are critical. CCA's cardinal safety rules + AG-10 worktree guard align with this.

---

## 5. Practical Insights (Cross-Source Synthesis)

### What works:
1. **Leader + workers + shared task list** is the dominant pattern (Agent Teams, Gas Town, Multiclaude, CCA hivemind all converge here)
2. **Git worktree isolation** is standard for parallel agents (CCA AG-10 already does this)
3. **Quality gates / watchdog agents** catch errors that individual agents miss
4. **3-5 agents is the sweet spot** — beyond that, coordination overhead > parallel gain
5. **5-6 tasks per agent** keeps agents productive without context switching

### What fails:
1. **Token costs scale linearly** — 5 agents = 5x tokens, no way around it
2. **Same-file edits** across agents = merge conflicts and overwrites
3. **Prompt quality is critical** — bad initial instructions compound across agents
4. **No session resumption** — if an agent dies, context is lost
5. **Multi-agent suits ~5% of use cases** — most work is better as single-agent

### CCA gaps identified:
1. **No watchdog/quality gate agent** — add a reviewer agent that validates before commit
2. **cca_comm.py vs Agent Teams** — evaluate migration path
3. **No Group Chat pattern** — useful for design reviews (spec-panel could use this)
4. **No adaptive role assignment** — agents have fixed roles, can't reassign based on task evolution
5. **No formal task dependency tracking** — Agent Teams has this, CCA doesn't

---

## 6. Recommendations for CCA

### Short-term (this milestone):
- **Enable and test Agent Teams** with CCA's existing dual-chat setup
- Add Agent Teams enable flag to CCA settings if not present
- Test with a simple parallel task (e.g., research + build)

### Medium-term (next 2-3 milestones):
- **Add watchdog agent pattern** — a lightweight reviewer that runs after each commit
- **Evaluate cca_comm.py → Agent Teams migration** — Agent Teams has task deps, file locking, hooks
- **Implement Group Chat for /sc:spec-panel and /sc:design-review** — natural fit

### Long-term:
- **Magentic/adaptive roles** — agents detect what's needed and self-assign
- **Cross-project agent coordination** — CCA agents helping Kalshi agents and vice versa
- **Self-improving agent configurations** — which team compositions work best for which tasks

---

## Sources

- [Anthropic Agent Teams Docs](https://code.claude.com/docs/en/agent-teams)
- [Shipyard: Multi-agent for Claude Code](https://shipyard.build/blog/claude-code-multi-agent/)
- [Azure Agent Design Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [LLM-Coordination (NAACL 2025)](https://arxiv.org/abs/2310.03903)
- [Multi-Agent Collaboration Survey](https://arxiv.org/abs/2501.06322)
- [Multi-Agent Incident Response](https://arxiv.org/abs/2511.15755)
- [Multi-Agent SE (ACM TOSEM)](https://dl.acm.org/doi/10.1145/3712003)
- [TRiSM for Agentic AI](https://arxiv.org/abs/2506.04133)
- [Ruflo](https://github.com/ruvnet/ruflo)
- [Claude Swarm](https://github.com/affaan-m/claude-swarm)
- [Metaswarm](https://github.com/dsifry/metaswarm)
- [Overstory](https://github.com/jayminwest/overstory)
