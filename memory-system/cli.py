"""
MEM-5: CLI Memory Viewer

Manage persistent Claude Code memories from the terminal.

Usage:
  python3 memory-system/cli.py list                     # Current project memories
  python3 memory-system/cli.py list --global            # Global memories
  python3 memory-system/cli.py list --all               # All projects
  python3 memory-system/cli.py list --confidence HIGH   # Filter by confidence
  python3 memory-system/cli.py search "hook pattern"    # Keyword/tag search
  python3 memory-system/cli.py delete mem_20260219_abc  # Delete by ID
  python3 memory-system/cli.py purge                    # Remove expired entries
  python3 memory-system/cli.py stats                    # Summary counts

Options:
  --project SLUG    Override project slug (default: derived from cwd)
  --dir PATH        Override memory directory (default: ~/.claude-memory)
  --no-color        Disable ANSI color output
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MEMORY_DIR = Path.home() / ".claude-memory"
SCHEMA_VERSION = "1.0"

TTL_DAYS = {
    "HIGH": 365,
    "MEDIUM": 180,
    "LOW": 90,
}

# ANSI colors
_COLORS = {
    "HIGH": "\033[32m",     # green
    "MEDIUM": "\033[33m",   # yellow
    "LOW": "\033[90m",      # grey
    "decision": "\033[36m", # cyan
    "pattern": "\033[34m",  # blue
    "error": "\033[31m",    # red
    "preference": "\033[35m",  # magenta
    "glossary": "\033[33m", # yellow
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
}
_NO_COLOR = {"HIGH": "", "MEDIUM": "", "LOW": "", "decision": "", "pattern": "",
             "error": "", "preference": "", "glossary": "", "reset": "", "bold": "", "dim": ""}


# ---------------------------------------------------------------------------
# Storage helpers (mirror of capture_hook.py — no import dependency)
# ---------------------------------------------------------------------------

def _project_slug(cwd: str) -> str:
    name = Path(cwd).name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return slug or "unknown-project"


def _memory_file(memory_dir: Path, slug: str) -> Path:
    return memory_dir / f"{slug}.json"


def _load_store(memory_file: Path) -> dict:
    if memory_file.exists():
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "project": memory_file.stem,
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "memories": [],
    }


def _save_store(store: dict, memory_file: Path) -> None:
    store["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = memory_file.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
        tmp.replace(memory_file)
    except OSError as e:
        print(f"Error saving store: {e}", file=sys.stderr)


def _all_stores(memory_dir: Path) -> list[tuple[str, dict]]:
    """Return [(slug, store), ...] for every .json file in memory_dir."""
    if not memory_dir.exists():
        return []
    result = []
    for path in sorted(memory_dir.glob("*.json")):
        try:
            store = json.loads(path.read_text(encoding="utf-8"))
            result.append((path.stem, store))
        except (json.JSONDecodeError, OSError):
            pass
    return result


def _is_expired(memory: dict) -> bool:
    conf = memory.get("confidence", "MEDIUM")
    ttl = TTL_DAYS.get(conf, 180)
    try:
        last_used = datetime.fromisoformat(memory["last_used"])
        expiry = last_used + timedelta(days=ttl)
        return datetime.now(timezone.utc) > expiry
    except (KeyError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _color(key: str, c: dict) -> str:
    return c.get(key, "")


def _format_memory(mem: dict, c: dict, index: int | None = None) -> str:
    conf = mem.get("confidence", "?")
    mtype = mem.get("type", "?")
    content = mem.get("content", "")
    tags = mem.get("tags", [])
    mem_id = mem.get("id", "?")
    created = mem.get("created_at", "")[:10]

    prefix = f"{index:3d}. " if index is not None else "  "
    conf_str = f"{_color(conf, c)}{conf}{_color('reset', c)}"
    type_str = f"{_color(mtype, c)}{mtype}{_color('reset', c)}"
    tag_str = f"  {_color('dim', c)}tags: {', '.join(tags)}{_color('reset', c)}" if tags else ""

    lines = [
        f"{prefix}{_color('bold', c)}{content[:100]}{_color('reset', c)}{'...' if len(content) > 100 else ''}",
        f"     {conf_str} | {type_str} | {_color('dim', c)}{mem_id}{_color('reset', c)} | {created}{tag_str}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(args, memory_dir: Path, c: dict) -> int:
    if args.all:
        stores = _all_stores(memory_dir)
        if not stores:
            print(f"No memory files in {memory_dir}")
            return 0
        for slug, store in stores:
            _print_store(slug, store, args, c)
        return 0

    slug = "_global" if args.glob else (args.project or _project_slug(os.getcwd()))
    mfile = _memory_file(memory_dir, slug)
    store = _load_store(mfile)
    _print_store(slug, store, args, c)
    return 0


def _print_store(slug: str, store: dict, args, c: dict) -> None:
    memories = store.get("memories", [])

    # Filter
    if hasattr(args, "confidence") and args.confidence:
        memories = [m for m in memories if m.get("confidence") == args.confidence.upper()]
    if hasattr(args, "type") and args.type:
        memories = [m for m in memories if m.get("type") == args.type.lower()]

    count = len(memories)
    total = len(store.get("memories", []))
    header = f"{_color('bold', c)}{slug}{_color('reset', c)} — {count} memories"
    if count != total:
        header += f" (of {total} total)"
    print(f"\n{header}")
    print("-" * 50)

    if not memories:
        print(f"  {_color('dim', c)}(no memories){_color('reset', c)}")
        return

    for i, mem in enumerate(memories, 1):
        print(_format_memory(mem, c, i))
        print()


def cmd_search(args, memory_dir: Path, c: dict) -> int:
    query = args.query.lower()
    slug = args.project or _project_slug(os.getcwd())
    stores_to_search = []

    if args.all:
        stores_to_search = _all_stores(memory_dir)
    else:
        for s in [slug, "_global"]:
            mfile = _memory_file(memory_dir, s)
            stores_to_search.append((s, _load_store(mfile)))

    results = []
    for store_slug, store in stores_to_search:
        for mem in store.get("memories", []):
            content_match = query in mem.get("content", "").lower()
            tag_match = any(query in t.lower() for t in mem.get("tags", []))
            type_match = query in mem.get("type", "").lower()
            if content_match or tag_match or type_match:
                results.append((store_slug, mem))

    if not results:
        print(f"No memories match '{args.query}'")
        return 0

    print(f"\n{_color('bold', c)}{len(results)} result(s) for '{args.query}'{_color('reset', c)}")
    print("-" * 50)
    for i, (store_slug, mem) in enumerate(results[:20], 1):
        print(f"  {_color('dim', c)}[{store_slug}]{_color('reset', c)}")
        print(_format_memory(mem, c, i))
        print()

    if len(results) > 20:
        print(f"  ... and {len(results) - 20} more. Use --all for full results.")
    return 0


def cmd_delete(args, memory_dir: Path, c: dict) -> int:
    mem_id = args.id
    slug = args.project or _project_slug(os.getcwd())

    # Search current project and global
    deleted = False
    for s in [slug, "_global"]:
        mfile = _memory_file(memory_dir, s)
        store = _load_store(mfile)
        before = len(store["memories"])
        store["memories"] = [m for m in store["memories"] if m.get("id") != mem_id]
        if len(store["memories"]) < before:
            _save_store(store, mfile)
            print(f"Deleted memory {mem_id} from {s}")
            deleted = True
            break

    if not deleted:
        print(f"Memory ID '{mem_id}' not found in {slug} or _global")
        return 1
    return 0


def cmd_purge(args, memory_dir: Path, c: dict) -> int:
    stores = _all_stores(memory_dir) if args.all else []
    if not args.all:
        slug = args.project or _project_slug(os.getcwd())
        for s in [slug, "_global"]:
            mfile = _memory_file(memory_dir, s)
            stores.append((s, _load_store(mfile)))

    total_removed = 0
    for store_slug, store in stores:
        expired = [m for m in store["memories"] if _is_expired(m)]
        if not expired:
            continue
        mfile = _memory_file(memory_dir, store_slug)
        store["memories"] = [m for m in store["memories"] if not _is_expired(m)]
        _save_store(store, mfile)
        total_removed += len(expired)
        for mem in expired:
            print(f"  Purged: {mem.get('id')} ({mem.get('confidence')}) — {mem.get('content', '')[:60]}")

    if total_removed == 0:
        print("No expired memories found.")
    else:
        print(f"\nPurged {total_removed} expired memories.")
    return 0


def cmd_stats(args, memory_dir: Path, c: dict) -> int:
    stores = _all_stores(memory_dir)
    if not stores:
        print(f"No memory files in {memory_dir}")
        return 0

    print(f"\n{_color('bold', c)}Memory Statistics{_color('reset', c)}")
    print(f"Directory: {memory_dir}")
    print("-" * 50)

    grand_total = 0
    for slug, store in stores:
        memories = store.get("memories", [])
        high = sum(1 for m in memories if m.get("confidence") == "HIGH")
        med = sum(1 for m in memories if m.get("confidence") == "MEDIUM")
        low = sum(1 for m in memories if m.get("confidence") == "LOW")
        expired = sum(1 for m in memories if _is_expired(m))
        grand_total += len(memories)
        exp_note = f"  {_color('dim', c)}({expired} expired){_color('reset', c)}" if expired else ""
        print(f"  {_color('bold', c)}{slug:30s}{_color('reset', c)} "
              f"{len(memories):3d} total  "
              f"{_color('HIGH', c)}HIGH:{high}{_color('reset', c)}  "
              f"{_color('MEDIUM', c)}MED:{med}{_color('reset', c)}  "
              f"{_color('LOW', c)}LOW:{low}{_color('reset', c)}"
              f"{exp_note}")

    print("-" * 50)
    print(f"  {'TOTAL':30s} {grand_total:3d}")
    return 0


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 memory-system/cli.py",
        description="Manage persistent Claude Code memories",
    )
    parser.add_argument("--dir", metavar="PATH", help="Memory directory (default: ~/.claude-memory)")
    parser.add_argument("--no-color", action="store_true", help="Disable color output")

    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List memories")
    p_list.add_argument("--project", metavar="SLUG", help="Override project slug")
    p_list.add_argument("--global", dest="glob", action="store_true", help="List global memories")
    p_list.add_argument("--all", action="store_true", help="List all projects")
    p_list.add_argument("--confidence", metavar="LEVEL", help="Filter: HIGH / MEDIUM / LOW")
    p_list.add_argument("--type", metavar="TYPE", help="Filter: decision / pattern / error / preference / glossary")

    # search
    p_search = sub.add_parser("search", help="Search memories by keyword or tag")
    p_search.add_argument("--project", metavar="SLUG", help="Override project slug")
    p_search.add_argument("query", help="Search query (keyword or tag)")
    p_search.add_argument("--all", action="store_true", help="Search all projects")

    # delete
    p_delete = sub.add_parser("delete", help="Delete a memory by ID")
    p_delete.add_argument("--project", metavar="SLUG", help="Override project slug")
    p_delete.add_argument("id", help="Memory ID (e.g., mem_20260219_143022_abc)")

    # purge
    p_purge = sub.add_parser("purge", help="Remove expired memories")
    p_purge.add_argument("--project", metavar="SLUG", help="Override project slug")
    p_purge.add_argument("--all", action="store_true", help="Purge across all projects")

    # stats
    sub.add_parser("stats", help="Show memory counts and statistics")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    memory_dir = Path(args.dir) if args.dir else DEFAULT_MEMORY_DIR
    c = _NO_COLOR if args.no_color or not sys.stdout.isatty() else _COLORS

    dispatch = {
        "list": cmd_list,
        "search": cmd_search,
        "delete": cmd_delete,
        "purge": cmd_purge,
        "stats": cmd_stats,
    }
    fn = dispatch.get(args.command)
    if fn is None:
        print(f"Unknown command: {args.command}")
        return 1

    return fn(args, memory_dir, c)


if __name__ == "__main__":
    sys.exit(main())
