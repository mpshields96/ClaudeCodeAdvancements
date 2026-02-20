# memory-system — Research Evidence Base

## Primary Evidence

### GitHub Issue #14227 — "Persistent Memory Between Claude Code Sessions"
- One of the highest-voted feature requests in Claude Code history
- Core user statement: "The value of an AI assistant compounds over time, and every session that starts from zero wastes that compounding."
- Status: Open as of February 2026

### Reddit Community Consensus (r/ClaudeCode, r/ClaudeAI)
- Persistent cross-session memory is the #1 most-demanded missing feature across the Claude Code community
- Source: aitooldiscovery.com analysis of 500+ Reddit comments (Feb 2026)

### Community Workarounds (Signal of Demand)
Tools that ONLY exist because the official solution doesn't:
- `claude-mem` — persistent memory via external storage
- `memory-mcp` — session memory via MCP protocol
- `claude-cognitive` — working memory with multi-instance state sharing
- `Beads` — git-backed memory system, dependency-aware

All are unofficial, brittle, and require manual setup. Their existence proves demand.

### Compaction Bug — Widely Documented
- After context compaction fires, the assistant ignores `.claude/project-context.md` rules it was following 100% before compaction
- Binary failure: followed 100% → violated 100%
- Source: paddo.dev "Claude Code 2.1 Pain Points Addressed" + multiple r/ClaudeCode threads

### The "Overconfident Junior with Amnesia" Problem
- Most-quoted Reddit characterization of Claude Code's session-start failure mode
- Two dimensions: overconfident on tasks it doesn't understand + retains nothing between sessions
- Source: aitooldiscovery.com synthesis of r/ClaudeCode sentiment

## Prior Art (What Exists, Why We're Different)

| Tool | What It Does | What's Missing |
|------|-------------|----------------|
| claude-mem | Stores raw conversation history | Too much noise, no structure |
| memory-mcp | MCP-based session memory | No capture automation |
| CLAUDE.md (manual) | User manually writes rules | No automated capture, no persistence across compaction |
| AWS AgentCore Memory | Enterprise memory for AWS agents | Cloud-based, not local, not Claude Code native |
| Mem0 | Production memory for AI agents | General purpose, not Claude Code hook-integrated |

**Our differentiator**: Hook-native capture (automatic, not manual) + local-first (private by default) + schema-driven (structured, not raw logs) + compaction-resistant (survives context reset).

## Technical Feasibility

### Claude Code Hooks Available
- `PostToolUse`: fires after every tool execution — can inspect what was done
- `Stop`: fires when main agent finishes — can prompt for session summary
- Both can run Python scripts via the hooks configuration
- Both receive structured input about what just happened

### MCP Server Feasibility
- Claude Code supports local MCP servers (localhost:PORT)
- A simple Python HTTP server exposing a `search_memory` tool is sufficient
- No cloud infrastructure required

### Storage Feasibility
- JSON files: Python stdlib, human-readable, trivially searchable
- SQLite: Python stdlib, structured queries, handles larger datasets
- Start with JSON, migrate to SQLite if performance issues arise at scale

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Credential accidentally captured | Medium | Regex filter for API key patterns before any write |
| Memory store grows unbounded | Medium | Built-in purge command, 90-day TTL by default |
| Wrong memories retrieved | Medium | Confidence scores, user-reviewable CLI |
| Hook fires on every tool (expensive) | Low | Filter to significant events only (Write, major decisions) |
| User loses trust if memory is wrong | Low | All memories shown before use, easy correction mechanism |
