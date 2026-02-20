# agent-guard — Research Evidence Base

## Primary Evidence

### Parallel Agent Workflows Are Moving to Standard Practice
- Incident.io runs 4–5 parallel Claude agents routinely (confirmed public blog post)
- Git worktrees for parallel agents is Anthropic's officially documented pattern
- Claude Agent Teams feature (Opus 4.6) ships native multi-agent — increasing adoption rapidly
- Source: Anthropic 2026 Agentic Coding Trends Report, incident.io blog, Upsun devcenter

### The Conflict Problem Is Documented but Unsolved
- "When running parallel tmux/worktree agent setups, there is no native mechanism to prevent agents from overwriting each other's work"
- "Users currently hard-code file ownership rules in CLAUDE.md as a workaround"
- Source: aitooldiscovery.com Reddit analysis, awesome-claude-code repository

### Community Tools That Partially Address This
| Tool | What It Does | What's Missing |
|------|-------------|----------------|
| Claude Squad | Multi-agent workspace manager | No conflict detection |
| Uzi | CLI for parallel worktrees | No file-level ownership |
| CCPM | GitHub Issues as agent DB | No hook-level conflict block |
| Claude Flow | Swarm intelligence framework | Coordination but no file guard |

None of these tools implement PreToolUse conflict detection. Agent-guard fills this specific gap.

### The 80/20 Adoption Split
- ~20% of power users run full parallel swarm setups currently
- ~80% use single-session workflows
- Prediction: parallel workflows move toward standard practice as Agent Teams matures
- Source: aitooldiscovery.com synthesis, redmonk.com

### The CLAUDE.md Hard-Code Workaround Pattern
A specific workaround for conflict prevention appears repeatedly in r/ClaudeCode:
```
# In CLAUDE.md:
# Agent A owns: src/auth/**, tests/auth/**
# Agent B owns: src/api/**, tests/api/**
# Never modify the other agent's files
```
This proves demand; it also proves the current solution is completely manual and unenforceable.

## Technical Feasibility

### PreToolUse Hook Can Intercept Write/Edit
- The PreToolUse hook fires before `Write` and `Edit` tool calls
- The hook receives `tool_name` and `tool_input` (which includes the file path)
- The hook can return `{"action": "deny", "message": "..."}` to block execution
- This is the exact mechanism needed for conflict detection

### Environment Variable for Agent Identity
- Setting `CLAUDE_AGENT_NAME` before launching Claude Code is a trivially simple pattern
- Documented in Claude Code docs as supported
- The lock file name becomes `.agent-[CLAUDE_AGENT_NAME].lock`

### fnmatch for Glob Pattern Matching
- Python stdlib `fnmatch` handles `.gitignore`-style patterns
- `fnmatch.fnmatch("src/auth/login.py", "src/auth/**")` — works correctly
- Zero dependency

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Agents don't set CLAUDE_AGENT_NAME | High (initially) | WARN-only when name not set (never block) |
| Manifest becomes stale after refactoring | Medium | `/agent:assign` regenerates manifest, versioned in git |
| Lock files not released on crash | Low | Stop hook releases all locks for current agent |
| False positives block legitimate work | Low | WARN mode by default, BLOCK only explicit opt-in |
| Glob pattern is too broad (locks entire src/) | Medium | Pattern validation warns on overly broad captures |
