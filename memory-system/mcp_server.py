#!/usr/bin/env python3
"""
MEM-3: Memory Retrieval MCP Server (v2.0 — FTS5 backend)
Speaks JSON-RPC 2.0 over stdio — the MCP protocol Claude Code expects.
Two tools: search_memory, load_memories.
Python stdlib only. No external dependencies.

Backend: SQLite + FTS5 via memory_store.py (BM25-ranked full-text search).

Registration (add to ~/.claude/claude_desktop_config.json or project MCP config):
{
  "mcpServers": {
    "claude-memory": {
      "command": "python3",
      "args": ["/Users/matthewshields/Projects/ClaudeCodeAdvancements/memory-system/mcp_server.py"]
    }
  }
}
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# Import MemoryStore from sibling module
sys.path.insert(0, str(Path(__file__).parent))
from memory_store import MemoryStore


# ── Storage helpers ──────────────────────────────────────────────────────────

# Singleton store — initialized lazily on first tool call, or injected for tests.
_global_store: MemoryStore | None = None


def _get_store() -> MemoryStore:
    """Get or create the global MemoryStore singleton."""
    global _global_store
    if _global_store is None:
        _global_store = MemoryStore()  # default: ~/.claude-memory/memories.db
    return _global_store


def _project_slug(cwd: str) -> str:
    return Path(cwd).name.lower().replace(" ", "-").replace("_", "-")


# ── Tool implementations ────────────────────────────────────────────────────

def tool_load_memories(args: dict, store: MemoryStore | None = None) -> dict:
    """
    Load memories for a project.
    Returns HIGH confidence memories always; MEDIUM if include_medium=True.
    Sorted by confidence (HIGH first) then updated_at descending.
    """
    cwd = args.get("cwd", os.getcwd())
    include_medium = args.get("include_medium", False)
    project_slug = _project_slug(cwd)
    s = store or _get_store()

    # Get all memories for this project
    all_mems = s.list_all(project=project_slug, limit=500)

    # Filter by confidence
    if include_medium:
        kept = [m for m in all_mems if m.get("confidence") in ("HIGH", "MEDIUM")]
    else:
        kept = [m for m in all_mems if m.get("confidence") == "HIGH"]

    # Sort: HIGH before MEDIUM, then updated_at descending within each tier
    def sort_key(m):
        conf_rank = 0 if m.get("confidence") == "HIGH" else 1
        updated = m.get("updated_at", "")
        return (conf_rank, updated)

    # Sort by conf_rank ascending, then updated descending
    kept.sort(key=lambda m: (
        0 if m.get("confidence") == "HIGH" else 1,
        # Negate updated_at for descending — use reverse string trick
    ))
    # Two-pass sort: stable sort on updated_at desc, then conf_rank asc
    kept.sort(key=lambda m: m.get("updated_at", ""), reverse=True)
    kept.sort(key=lambda m: 0 if m.get("confidence") == "HIGH" else 1)

    return {
        "project": project_slug,
        "count": len(kept),
        "memories": kept
    }


def tool_search_memory(args: dict, store: MemoryStore | None = None) -> dict:
    """
    Search memories by keyword using FTS5 full-text search.
    Returns up to 10 results ranked by BM25 relevance.
    """
    query = args.get("query", "").strip()
    cwd = args.get("cwd", os.getcwd())
    project_slug = _project_slug(cwd)
    s = store or _get_store()

    if not query:
        return {"project": project_slug, "count": 0, "memories": [], "query": query}

    results = s.search(query=query, limit=10, project=project_slug)

    return {
        "project": project_slug,
        "query": query,
        "count": len(results),
        "memories": results
    }


# ── MCP protocol (JSON-RPC 2.0 over stdio) ─────────────────────────────────

TOOLS = [
    {
        "name": "load_memories",
        "description": (
            "Load persistent memories for the current project. "
            "Call this at session start to restore context from previous sessions. "
            "Returns HIGH confidence memories by default. Set include_medium=true for broader context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cwd": {
                    "type": "string",
                    "description": "Current working directory (project root). Defaults to process cwd."
                },
                "include_medium": {
                    "type": "boolean",
                    "description": "Include MEDIUM confidence memories. Defaults to false (HIGH only)."
                }
            }
        }
    },
    {
        "name": "search_memory",
        "description": (
            "Search project memories using full-text search with BM25 relevance ranking. "
            "Returns up to 10 results. Supports FTS5 syntax (AND, OR, NOT, quoted phrases). "
            "Use this to find specific decisions, errors, or patterns."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. Supports FTS5 operators: AND, OR, NOT, \"quoted phrases\"."
                },
                "cwd": {
                    "type": "string",
                    "description": "Current working directory (project root). Defaults to process cwd."
                }
            },
            "required": ["query"]
        }
    }
]


def handle_request(req: dict, store: MemoryStore | None = None) -> dict | None:
    """Route a JSON-RPC request to the correct handler. Returns None for notifications."""
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {})

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    # MCP lifecycle
    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "claude-memory", "version": "2.0.0"}
        })

    if method == "notifications/initialized":
        return None  # notification — no response

    if method == "tools/list":
        return ok({"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name == "load_memories":
            result = tool_load_memories(tool_args, store=store)
        elif tool_name == "search_memory":
            result = tool_search_memory(tool_args, store=store)
        else:
            return err(-32601, f"Unknown tool: {tool_name}")

        return ok({
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": False
        })

    # Ping
    if method == "ping":
        return ok({})

    return err(-32601, f"Method not found: {method}")


def main():
    """Read newline-delimited JSON-RPC from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            continue

        response = handle_request(req)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
