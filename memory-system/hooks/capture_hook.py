#!/usr/bin/env python3
"""
MEM-2: Memory Capture Hook
Fires on PostToolUse and Stop events.
Reads JSON from stdin, writes JSON to stdout.

PostToolUse: detects significant Write/Edit events and auto-tags them as
             candidate memories (pattern type). Does NOT auto-write — flags
             for session-end review only.

Stop:        extracts memories from last_assistant_message.
             Writes confirmed memories to ~/.claude-memory/[project].json.

Usage (hooks config):
  PostToolUse: python3 /path/to/capture_hook.py
  Stop:        python3 /path/to/capture_hook.py

Both events use the same script. Hook event is identified from stdin JSON.
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

MEMORY_DIR = Path.home() / ".claude-memory"
SCHEMA_VERSION = "1.0"
MAX_CONTENT_CHARS = 500

# Credentials filter: if memory content matches any of these, REJECT the write.
_CREDENTIAL_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9\-]{20,}", re.IGNORECASE),         # Anthropic keys (sk-ant-api03-...)
    re.compile(r"Bearer\s+[A-Za-z0-9\-_.]{20,}", re.IGNORECASE), # Bearer tokens
    re.compile(r"(api[_-]?key|secret|password|token|credential)"
               r"\s*[=:]\s*\S{8,}", re.IGNORECASE),              # key=value patterns
    re.compile(r"SUPABASE_(KEY|URL)\s*=", re.IGNORECASE),
    re.compile(r"(AKIA|ASIA)[A-Z0-9]{16}", re.IGNORECASE),       # AWS access keys
]

# Tools whose PostToolUse output warrants a candidate memory flag.
_SIGNIFICANT_TOOLS = {"Write", "Edit", "Bash"}

# Keywords in last_assistant_message that suggest a memory-worthy decision.
_DECISION_KEYWORDS = [
    "decided to", "we decided", "going to use", "will use", "chose to",
    "the reason is", "because", "instead of", "rather than", "the fix is",
    "the issue was", "fixed by", "non-negotiable", "always", "never",
    "pattern is", "rule:", "note:", "important:",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def _project_slug(cwd: str) -> str:
    """Convert a file path to a project slug. Last path component, lowercase."""
    name = Path(cwd).name.lower()
    # Replace spaces and special chars with hyphens, keep alphanumeric + hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return slug or "unknown-project"


def _memory_file(project_slug: str) -> Path:
    """Return the path to the memory store for this project."""
    MEMORY_DIR.mkdir(exist_ok=True)
    return MEMORY_DIR / f"{project_slug}.json"


def _load_store(memory_file: Path) -> dict:
    """Load the memory store, creating it if absent."""
    if memory_file.exists():
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass  # Corrupted file — start fresh rather than crash

    return {
        "project": memory_file.stem,
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "last_updated": _now(),
        "memories": [],
    }


def _save_store(store: dict, memory_file: Path) -> None:
    """Persist the memory store to disk."""
    store["last_updated"] = _now()
    tmp = memory_file.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    tmp.replace(memory_file)  # Atomic rename — avoids partial writes


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # uuid4 gives 122 bits of randomness — collision probability is negligible
    suffix = uuid.uuid4().hex[:8]
    return f"mem_{ts}_{suffix}"


def _contains_credentials(content: str) -> bool:
    """Return True if content matches any credential pattern."""
    for pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(content):
            return True
    return False


def _truncate(text: str, max_chars: int = MAX_CONTENT_CHARS) -> str:
    """Truncate to max_chars, appending ellipsis if needed."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _build_memory(
    content: str,
    mem_type: str,
    project: str,
    tags: list[str],
    confidence: str,
    source: str,
) -> dict | None:
    """
    Validate and construct a memory entry dict.
    Returns None if the content fails validation.
    """
    content = content.strip()
    if not content:
        return None
    if _contains_credentials(content):
        return None
    content = _truncate(content)

    valid_types = {"decision", "pattern", "error", "preference", "glossary"}
    if mem_type not in valid_types:
        mem_type = "decision"  # Sensible fallback

    valid_confidence = {"HIGH", "MEDIUM", "LOW"}
    if confidence not in valid_confidence:
        confidence = "MEDIUM"

    return {
        "id": _make_id(),
        "type": mem_type,
        "content": content,
        "project": project,
        "tags": tags[:5],  # Max 5 tags
        "created_at": _now(),
        "last_used": _now(),
        "confidence": confidence,
        "source": source,
    }


# ── PostToolUse Handler ───────────────────────────────────────────────────────

def handle_post_tool_use(hook_input: dict) -> dict:
    """
    Detect significant tool events and inject a soft reminder into context.
    We don't auto-write memories here — the Stop hook does that with better context.
    This hook only adds an additionalContext nudge when a pattern-worthy event occurs.
    """
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    cwd = hook_input.get("cwd", "")

    if tool_name not in _SIGNIFICANT_TOOLS:
        # Not interesting — pass through silently
        return {}

    # For Write/Edit: note which file was touched (for session-end memory extraction)
    if tool_name in {"Write", "Edit"}:
        file_path = tool_input.get("file_path", "")
        if file_path:
            # Inject a subtle context note so the Stop hook has file history to work with
            return {
                "additionalContext": (
                    f"[memory-system] File modified this session: {file_path}"
                )
            }

    return {}


# ── Stop Hook Handler ─────────────────────────────────────────────────────────

def handle_stop(hook_input: dict) -> dict:
    """
    Extract memories from the session's last_assistant_message and transcript.
    Writes confirmed memories to the project's memory store.
    """
    cwd = hook_input.get("cwd", "")
    last_msg = hook_input.get("last_assistant_message", "")
    transcript_path = hook_input.get("transcript_path", "")
    project = _project_slug(cwd)

    extracted = _extract_memories_from_message(last_msg, project)
    transcript_memories = _extract_from_transcript(transcript_path, project)

    all_memories = extracted + transcript_memories

    if not all_memories:
        return {}

    memory_file = _memory_file(project)
    store = _load_store(memory_file)

    # Deduplicate against existing memories by content similarity
    existing_contents = {m["content"].lower() for m in store["memories"]}
    new_memories = []
    for mem in all_memories:
        if mem["content"].lower() not in existing_contents:
            store["memories"].append(mem)
            new_memories.append(mem)
            existing_contents.add(mem["content"].lower())

    if new_memories:
        _save_store(store, memory_file)
        count = len(new_memories)
        return {
            "additionalContext": (
                f"[memory-system] Saved {count} new "
                f"{'memory' if count == 1 else 'memories'} to {memory_file}. "
                f"Run 'python3 memory-system/cli.py' to review."
            )
        }

    return {}


def _extract_memories_from_message(message: str, project: str) -> list[dict]:
    """
    Parse last_assistant_message for decision-worthy sentences.
    Uses keyword heuristics — conservative, low false-positive rate.
    """
    if not message or len(message) < 20:
        return []

    memories = []
    # Split on sentence boundaries (rough heuristic)
    sentences = re.split(r"(?<=[.!?])\s+", message)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 30 or len(sentence) > MAX_CONTENT_CHARS:
            continue

        # Check if the sentence contains decision-signaling language
        lower = sentence.lower()
        if not any(kw in lower for kw in _DECISION_KEYWORDS):
            continue

        # Don't capture questions
        if sentence.endswith("?"):
            continue

        # Don't capture credential-containing content
        if _contains_credentials(sentence):
            continue

        # Infer type from content
        mem_type = "decision"
        if any(kw in lower for kw in ["error", "bug", "issue", "fix", "fixed"]):
            mem_type = "error"
        elif any(kw in lower for kw in ["always", "never", "prefer", "style", "format"]):
            mem_type = "preference"
        elif any(kw in lower for kw in ["pattern", "convention", "structure", "layout"]):
            mem_type = "pattern"

        mem = _build_memory(
            content=sentence,
            mem_type=mem_type,
            project=project,
            tags=_infer_tags(sentence),
            confidence="MEDIUM",  # Inferred, not explicit
            source="session-end",
        )
        if mem:
            memories.append(mem)

    return memories[:5]  # Cap at 5 per session to prevent noise


def _extract_from_transcript(transcript_path: str, project: str) -> list[dict]:
    """
    Parse the session transcript JSONL for explicit memory instructions.
    Looks for user messages containing 'remember that', 'always', 'never'.
    These get HIGH confidence.
    """
    if not transcript_path:
        return []

    path = Path(transcript_path)
    if not path.exists():
        return []

    memories = []
    explicit_patterns = [
        re.compile(r"remember (that |this |):?\s*(.{20,200})", re.IGNORECASE),
        re.compile(r"always (use|do|prefer|run|start|check)\s+(.{10,150})", re.IGNORECASE),
        re.compile(r"never (use|do|touch|modify)\s+(.{10,150})", re.IGNORECASE),
        re.compile(r"rule:\s*(.{10,200})", re.IGNORECASE),
        re.compile(r"non-negotiable:\s*(.{10,200})", re.IGNORECASE),
    ]

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Only look at user messages
                if entry.get("role") != "user":
                    continue

                content_blocks = entry.get("content", [])
                if isinstance(content_blocks, str):
                    text = content_blocks
                elif isinstance(content_blocks, list):
                    text = " ".join(
                        b.get("text", "") for b in content_blocks
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                else:
                    continue

                for pattern in explicit_patterns:
                    match = pattern.search(text)
                    if match:
                        # Last capture group contains the actual content
                        captured = match.group(match.lastindex).strip()
                        if _contains_credentials(captured):
                            continue
                        mem = _build_memory(
                            content=_truncate(captured),
                            mem_type="preference",
                            project=project,
                            tags=_infer_tags(captured),
                            confidence="HIGH",  # Explicitly instructed
                            source="explicit",
                        )
                        if mem:
                            memories.append(mem)

    except OSError:
        pass

    return memories[:10]  # Cap at 10 explicit memories per session


def _infer_tags(content: str) -> list[str]:
    """
    Infer 1-3 tags from content by keyword matching against known module names
    and common architectural concepts.
    """
    lower = content.lower()
    tags = []

    # Module-level tags
    module_map = {
        "memory": "memory-system",
        "spec": "spec-system",
        "context": "context-monitor",
        "agent": "agent-guard",
        "usage": "usage-dashboard",
        "hook": "hooks",
        "sqlite": "storage",
        "json": "storage",
        "schema": "schema",
        "transcript": "transcript",
        "mcp": "mcp",
        "slash command": "commands",
        "test": "testing",
        "architecture": "architecture",
        "import": "architecture",
        "dependency": "dependencies",
        "credential": "security",
        "api key": "security",
        "error": "error-handling",
    }

    for keyword, tag in module_map.items():
        if keyword in lower and tag not in tags:
            tags.append(tag)
        if len(tags) >= 3:
            break

    if not tags:
        tags = ["general"]

    return tags


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    event = hook_input.get("hook_event_name", "")

    if event == "PostToolUse":
        result = handle_post_tool_use(hook_input)
    elif event == "Stop":
        result = handle_stop(hook_input)
    else:
        result = {}

    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
