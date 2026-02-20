#!/usr/bin/env python3
"""
MEM-3: Memory Retrieval MCP Server
Speaks JSON-RPC 2.0 over stdio — the MCP protocol Claude Code expects.
Two tools: search_memory, load_memories.
Python stdlib only. No external dependencies.

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

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone


# ── Storage helpers (mirrors capture_hook.py) ────────────────────────────────

def _memory_dir() -> Path:
    return Path.home() / ".claude-memory"


def _project_slug(cwd: str) -> str:
    return Path(cwd).name.lower().replace(" ", "-").replace("_", "-")


def _load_store(project_slug: str) -> dict:
    store_path = _memory_dir() / f"{project_slug}.json"
    if not store_path.exists():
        return {"project": project_slug, "schema_version": "1.0", "memories": []}
    try:
        return json.loads(store_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"project": project_slug, "schema_version": "1.0", "memories": []}


def _touch_last_used(store: dict, matched_ids: list[str], project_slug: str) -> None:
    """Update last_used on surfaced memories and persist."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    changed = False
    for mem in store.get("memories", []):
        if mem.get("id") in matched_ids:
            mem["last_used"] = now
            changed = True
    if changed:
        store_path = _memory_dir() / f"{project_slug}.json"
        tmp = store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(store, indent=2))
        tmp.replace(store_path)


# ── Tool implementations ──────────────────────────────────────────────────────

def tool_load_memories(args: dict) -> dict:
    """
    Load memories for a project.
    Returns HIGH confidence memories always; MEDIUM if include_medium=True.
    Sorted by confidence (HIGH first) then last_used descending.
    """
    cwd = args.get("cwd", os.getcwd())
    include_medium = args.get("include_medium", False)
    project_slug = _project_slug(cwd)

    store = _load_store(project_slug)
    memories = store.get("memories", [])

    # Filter by confidence
    if include_medium:
        kept = [m for m in memories if m.get("confidence") in ("HIGH", "MEDIUM")]
    else:
        kept = [m for m in memories if m.get("confidence") == "HIGH"]

    # Sort: HIGH before MEDIUM, then last_used descending within each tier
    from functools import cmp_to_key
    def cmp(a, b):
        a_rank = 0 if a.get("confidence") == "HIGH" else 1
        b_rank = 0 if b.get("confidence") == "HIGH" else 1
        if a_rank != b_rank:
            return a_rank - b_rank
        a_used = a.get("last_used", "")
        b_used = b.get("last_used", "")
        if a_used > b_used:
            return -1
        if a_used < b_used:
            return 1
        return 0
    kept = sorted(kept, key=cmp_to_key(cmp))

    # Update last_used
    _touch_last_used(store, [m["id"] for m in kept], project_slug)

    return {
        "project": project_slug,
        "count": len(kept),
        "memories": kept
    }


def tool_search_memory(args: dict) -> dict:
    """
    Search memories by keyword across content and tags.
    Returns up to 10 results sorted by last_used descending.
    """
    query = args.get("query", "").lower().strip()
    cwd = args.get("cwd", os.getcwd())
    project_slug = _project_slug(cwd)

    if not query:
        return {"project": project_slug, "count": 0, "memories": [], "query": query}

    store = _load_store(project_slug)
    memories = store.get("memories", [])

    results = []
    for mem in memories:
        content_match = query in mem.get("content", "").lower()
        tag_match = any(query in tag.lower() for tag in mem.get("tags", []))
        type_match = query in mem.get("type", "").lower()
        if content_match or tag_match or type_match:
            results.append(mem)

    # Sort by last_used descending
    results.sort(key=lambda m: m.get("last_used", ""), reverse=True)
    results = results[:10]

    # Update last_used
    _touch_last_used(store, [m["id"] for m in results], project_slug)

    return {
        "project": project_slug,
        "query": query,
        "count": len(results),
        "memories": results
    }


# ── MCP protocol (JSON-RPC 2.0 over stdio) ───────────────────────────────────

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
            "Search project memories by keyword. Matches against content, tags, and type. "
            "Returns up to 10 results sorted by recency. "
            "Use this to find specific decisions, errors, or patterns."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword (case-insensitive, substring match)."
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


def handle_request(req: dict) -> dict | None:
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
            "serverInfo": {"name": "claude-memory", "version": "1.0.0"}
        })

    if method == "notifications/initialized":
        return None  # notification — no response

    if method == "tools/list":
        return ok({"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name == "load_memories":
            result = tool_load_memories(tool_args)
        elif tool_name == "search_memory":
            result = tool_search_memory(tool_args)
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
