# Claw-Code Architecture Notes

Reference patterns from `references/claw-code/` (instructkr's Python rewrite of Claude Code).
These inform CCA's agent dispatch and budget management design. Do NOT build from these directly.

## Key Patterns

### 1. Token-Based Prompt Routing (`runtime.py`, 193 lines)

`route_prompt()` uses fuzzy keyword overlap scoring to route user input to either a command
or a tool. Separation of routing (which agent?) from execution (run agent). CCA relevance:
`/cca-nuclear` could auto-select which agent handles which URL type using this pattern.

### 2. Budget-Aware Session Management (`query_engine.py`, 194 lines)

`QueryEnginePort` has `max_turns`, `max_budget_tokens`, and `compact_after_turns` with
transcript persistence. `max_budget_tokens=2000` is a hard cap on cumulative token usage.
Directly informs our tool-call budget awareness rule (CLAUDE.md). A programmatic version
would be a hook that counts tool calls and warns at threshold.

### 3. Uniform Execution Registry (`execution_registry.py`, 52 lines)

`ExecutionRegistry` wraps `MirroredCommand` and `MirroredTool` with a uniform `.execute()`
interface. Clean registry pattern. CCA agents could follow: `AgentRegistry` with uniform
`.spawn()` for all agent types.

### 4. Permission Deny Model (`permissions.py`, 21 lines)

`ToolPermissionContext` uses `deny_names` (frozenset) + `deny_prefixes` (tuple) with a
`.blocks(tool_name)` method. Matches our `disallowedTools` frontmatter approach — confirms
CCA's agent permission model is aligned with CC internals.

### 5. Filtered Tool Pools (`tool_pool.py`, 38 lines)

`ToolPool` assembled with `simple_mode`/`include_mcp`/`permission_context` filters.
Pattern for building per-task agent tool pools (research agents get WebFetch, build agents
get Edit/Write, review agents get Read-only).

## Chat 16+ Implications

- **Agent dispatch router**: Implement keyword-overlap scoring for `/cca-nuclear` URL routing
- **Tool-call budget hook**: Programmatic `max_budget_tokens` via PreToolUse hook (counts calls, warns at threshold)
- **Agent registry**: Uniform `.spawn()` interface across all CCA agent types
