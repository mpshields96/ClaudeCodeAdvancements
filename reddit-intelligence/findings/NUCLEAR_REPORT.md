# Nuclear Deep-Dive Report: r/ClaudeCode Top Year (FINAL)
Generated: 2026-03-15
Posts scanned: 138 total | Sessions used: 2

## Summary Stats
| Metric | Count |
|--------|-------|
| Posts fetched | 138 |
| Deduped (vs FINDINGS_LOG) | 110 reviewed |
| BUILD | 5 |
| ADAPT | 23 |
| REFERENCE | 20 |
| SKIP | 6 |
| FAST-SKIP | 57 |
| HAY (auto-skipped) | 28 |
| Polybot-relevant | 1 |
| Maestro-relevant | 3 |
| Usage-Dashboard | 9 |

## BUILD Candidates (ranked by score x feasibility)

### 1. claude-devtools (879 pts) — Frontier 3+5
- **What to build**: Desktop app tailing ~/.claude/ session logs for real-time observability
- **Key features**: Inline diffs, token breakdown by category (File/Tool/Thinking), sub-agent execution tree, .env regex alert triggers
- **Steal**: Session log visualization pattern, custom regex alerts for sensitive file access
- **URL**: https://www.reddit.com/r/ClaudeCode/comments/1r3to9f/
- **Repo**: github.com/matt1398/claude-devtools

### 2. OpenTelemetry Metrics (807 pts) — Frontier 5
- **What to build**: OTel-based usage dashboard leveraging CC's native metrics
- **Key features**: Grafana dashboard, per-session cost, 741x productivity ratio metric
- **Steal**: OTel collector setup, Grafana dashboard JSON template
- **URL**: https://www.reddit.com/r/ClaudeCode/comments/1pjon1r/

### 3. Self-Improvement Loop /wrap-up Skill (269pts) — Frontier 1+2
- **What to build**: 4-phase session wrap (Ship/Remember/Review/Publish). The "Review & Apply" phase is the key — Claude catches its own patterns and auto-writes rules.
- **Steal**: Self-learning review step directly upgradeable into our /cca-wrap
- **POLYBOT-RELEVANT**: Maps to self-learning journal strategy feedback loop
- **URL**: https://www.reddit.com/r/ClaudeCode/comments/1r89084/

### 4. Claude Island — Dynamic Island (309pts) — Frontier 5
- **What to build**: macOS notch-area overlay with real-time session status and permission approve/deny
- **Steal**: Ready to install. Swift/SwiftUI, Apache 2.0, hooks integration
- **URL**: https://www.reddit.com/r/ClaudeCode/comments/1pibst6/
- **Repo**: github.com/farouqaldori/claude-island

### 5. ClaudeCode Usage in Menu Bar (282pts) — Frontier 5
- **What to build**: macOS menu bar usage tracker
- **Key gap**: No OAuth `user:usage:read` scope exists yet
- **URL**: https://www.reddit.com/r/ClaudeCode/comments/1rl6djl/
- **Repo**: github.com/Blimp-Labs/claude-usage-bar

## ADAPT Patterns (grouped by frontier)

### Frontier 1: Persistent Memory
- **AST-linked memory with staleness**: Observations linked to dependency graph nodes; auto-stale when code changes (vexp, 270pts)
- **Passive behavior observation**: Watch agent actions -> auto-generate memory without relying on agent self-report
- **evolve-yourself skill**: JSON frequency DB, auto-creates skills after 3x/day pattern, auto-removes after 6mo unused (486pts)

### Frontier 2: Spec-Driven Development
- **/arewedone structural completeness check** after every change (348pts, ZacheryGlass/.claude)
- **Documentation handbook**: 52 per-feature .md files with data model + API + business rules + edge cases (304pts)
- **DOCUMENT -> IMPLEMENT -> TEST -> VERIFY -> MERGE** lifecycle
- **Frontmatter with cross-deps** for fuzzy-match RAG lookup
- **CLAUDE.md as most-edited file**: 43 changes/312 commits validates constraints doc > prompting (344pts)
- **Nested CLAUDE.md per subdirectory**: 3-layer context (project/feature/task)
- **Anthropic's own harness**: initializer+coder agent split, progress log, git checkpoint (393pts)
- **Valence adversarial review**: /arm -> /design -> /ar (3-model critique) -> /plan -> /build -> QA (552pts)
- **cc-sessions**: Auto-plans/gits/tasks, 6 hooks + 5 agents, cross-model orchestration (329pts)
- **GSD improvements**: Wave-based parallel execution, goal-backward verification, files-as-memory (261pts)

### Frontier 3: Context Health
- **40% context ceiling** community-validated across 8+ posts
- **Subagents for context isolation** — main context stays 30-40%
- **/clear + re-read .md** pattern at ceiling
- **beads + repomix** for context injection at session start
- **Code-Mode**: One TypeScript sandbox replaces many MCP tools (60%+ savings, 263pts)
- **MCP socket pooling**: Agent Deck 85-90% MCP memory reduction (311pts)
- **MCP token bloat**: 70k+ per prompt even unused; mcp-proxy filters 90% (670pts)
- **Enable LSP**: 50ms vs 30-60s navigation, hidden flag (855pts)
- **Context drift by hour 8** in /loop — need checkpoint behavior
- **Startup tax**: CLAUDE.md bloat = higher per-prompt cost (280pts)

### Frontier 4: Agent Guard
- **Post-deployment security audit** with different model (cross-model scrutiny) (458pts)
- **Log-based prompt injection** via library output — major unsolved vector (358pts)
- **Dedicated user account sandboxing**: `useradd claude` — Unix permissions solve 90% (358pts)
- **Session forking**: Agent Deck preserves context (311pts)
- **Worktree-per-task**: Subtask pattern for safe parallel (268pts)
- **Multi-model orchestration**: Claude plans -> Codex implements -> Claude reviews (256pts)
- **ClawdBot prompt injection**: Fundamentally unsolvable, CVE list, agents modify own config (711pts)
- **Worktree merge conflicts**: Claude discards other session's changes (653pts)

### Frontier 5: Usage Dashboard
- **Claude Island**: macOS notch overlay (309pts)
- **claude-usage-bar**: Menu bar widget (282pts)
- **OAuth gap**: No `user:usage:read` scope — must use full `user:inference` token
- **Effort level tuning**: Medium often > max (reduces overthinking) (250pts)
- **Per-project settings.json**: Different effort per codebase
- **Local model routing**: litellm proxy for cheap tasks (377pts)
- **CodexBar**: 10+ providers, free, open source
- **OTel metrics**: CC already emits, Grafana dashboard available (807pts)

## Polybot-Relevant Findings
1. **Self-improvement Loop /wrap-up** — directly maps to self-learning journal. Review & Apply phase where Claude catches patterns is exactly the strategy feedback loop Polybot needs.

## Maestro-Relevant Findings
1. **VoiceTree/Gas Town** (451pts) — graph orchestration with subagent spawning
2. **Agent Deck** (311pts) — MCP socket pooling, session forking, global search
3. **agtx** (256pts) — kanban + worktrees, multi-model orchestration demand

## Recurring Pain Points
| Pain Point | Mentions | Frontier |
|-----------|----------|---------|
| Context rot / degradation | 12+ | F3 |
| Usage limits / cost opacity | 9+ | F5 |
| Permission prompt fatigue | 5+ | F4 |
| Session memory loss | 5+ | F1 |
| CLAUDE.md maintenance burden | 4+ | F2 |
| MCP token bloat | 4+ | F3+F5 |
| Prompt injection via logs/tools | 3+ | F4 |
| Model effort/quality regression | 3+ | F5 |
| Merge conflicts from parallel agents | 3+ | F4 |

## Official Anthropic Features Noted
| Feature | Status |
|---------|--------|
| Auto Mode | Launched March 12, 2026 |
| /loop (recurring tasks) | Launched, 3-day cap |
| Code Review ($15-25/review) | Team/Enterprise |
| Remote Control | Max users |
| /effort (VS Code) | Available |
| LSP plugin system | Hidden flag |
| OTel metrics | Available |

## Recommendations for Next Session

1. **IMPLEMENT: Self-learning review in /cca-wrap** — Port the Review & Apply phase. Low-cost skill edit, directly enables self-improvement.

2. **IMPLEMENT: USAGE-1 token counter** — Integrate with CC's native OTel metrics. Community demand is overwhelming (9+ posts). Claude Island is installable today.

3. **ADOPT: /arewedone structural completeness check** — Add as a skill that runs after major changes to verify no stubs.

4. **INVESTIGATE: Code-Mode token savings** — One-sandbox-replaces-many-tools pattern for context reduction.

5. **INSTALL: Claude Island** — Ready today. macOS native, open source, hooks-integrated.

---

Nuclear scan COMPLETE. All 138 posts processed. Run `/cca-auto` to implement top BUILD candidates.
