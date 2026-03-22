# MT-29: Cowork + Pro Bridge Research — S114

## Research Question
Is Claude Cowork objectively better than our current hivemind pattern for CCA workflows?
Can it bridge Claude Pro ↔ Claude Code for unified strategy+implementation?

## Findings

### What Cowork Is
- Agentic mode in Claude Desktop app (launched Jan 2026 research preview)
- Brings Claude Code-style autonomous task execution to non-developer knowledge workers
- Access to local files, terminal commands, MCP servers (with caveats)
- "Give Claude a task, step away, come back to completed work"
- Enterprise focus: MCP connectors for Google Drive, Gmail, DocuSign, etc.

### What Cowork Is NOT
- NOT a Claude Code replacement for developer workflows
- NOT a bridge between Pro web chat and Code CLI sessions
- NOT a shared-context system across sessions (memory not retained in standalone mode)
- NOT reliable for local MCP servers (GitHub #23424 — only HTTP-based remote MCPs work)

### Comparison: Cowork vs Our Hivemind

| Feature | Our Hivemind (MT-21) | Cowork |
|---------|---------------------|--------|
| Dev workflow support | Full (git, tests, hooks) | Limited (general-purpose) |
| Multi-session coordination | cca_comm.py queue + scope claims | None — single session only |
| Crash recovery | crash_recovery.py | None documented |
| Peak hours awareness | peak_hours.py | None |
| Session pacing | session_pacer.py | None |
| Local MCP servers | Fully working | Buggy (issue #23424) |
| Cross-session memory | Our memory-system (Frontier 1) | Not retained in standalone |
| File safety | path_validator + bash_guard | Basic containerized sandbox |

### Pro ↔ Code Bridge Assessment
- No official bridge exists (confirmed by research)
- Claude Projects feature (shared file uploads) is the closest mechanism
- MCP-based bridge (expose project files to Pro via MCP server) is theoretically possible but:
  - Pro/Desktop has MCP bugs in Cowork mode
  - Would require running an MCP server locally while Code sessions run
  - Complexity not worth the benefit — easier to just share files via git

## Verdict: SKIP for now

MT-29 is low priority. Our hivemind infrastructure is objectively superior for CCA's dev-centric
workflows. Cowork adds no value over what we've built.

**When to revisit:**
- If Anthropic ships a native Pro ↔ Code shared context feature
- If Cowork local MCP bugs are fixed (monitor GitHub #23424)
- If Anthropic launches a multi-agent orchestration API

## Sources
- https://claude.com/blog/cowork-research-preview
- https://support.claude.com/en/articles/13345190-get-started-with-cowork
- https://github.com/anthropics/claude-code/issues/23424
- https://composio.dev/content/how-to-better-your-claude-cowork-experience-with-mcps
