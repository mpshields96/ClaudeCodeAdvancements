#!/usr/bin/env python3
"""
MEM-2: Memory Capture Hook (v2.0 — FTS5 backend)
Fires on PostToolUse and Stop events.
Reads JSON from stdin, writes JSON to stdout.

PostToolUse: detects significant Write/Edit events and injects context notes.
             Does NOT auto-write — flags for session-end review only.

Stop:        extracts memories from last_assistant_message and transcript.
             Writes confirmed memories to FTS5 MemoryStore (~/.claude-memory/memories.db).

Usage (hooks config):
  PostToolUse: python3 /path/to/capture_hook.py
  Stop:        python3 /path/to/capture_hook.py

Both events use the same script. Hook event is identified from stdin JSON.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Import MemoryStore from parent directory ─────────────────────────────────
# capture_hook.py lives in memory-system/hooks/, MemoryStore in memory-system/
_MODULE_DIR = Path(__file__).resolve().parent.parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

from memory_store import MemoryStore

# ── Constants ────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "2.0"
MAX_CONTENT_CHARS = 500

# ── OMEGA-inspired: Per-type TTL rules (in days) ────────────────────────────
TYPE_TTL_DAYS = {
    "decision": 365,
    "pattern": 180,
    "error": 365,
    "preference": 730,
    "glossary": 730,
}

# Similarity threshold for content dedup (0.0-1.0)
DEDUP_SIMILARITY_THRESHOLD = 0.85

# Credentials filter: if memory content matches any of these, REJECT the write.
_CREDENTIAL_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9\-]{20,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_.]{20,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key|secret|password|token|credential)"
               r"\s*[=:]\s*\S{8,}", re.IGNORECASE),
    re.compile(r"SUPABASE_(KEY|URL)\s*=", re.IGNORECASE),
    re.compile(r"(AKIA|ASIA)[A-Z0-9]{16}", re.IGNORECASE),
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

# Valid memory types (encoded as "type:<name>" tag in MemoryStore)
VALID_TYPES = {"decision", "pattern", "error", "preference", "glossary"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _project_slug(cwd: str) -> str:
    """Convert a file path to a project slug. Last path component, lowercase."""
    name = Path(cwd).name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return slug or "unknown-project"


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
    return text[: max_chars - 1] + "\u2026"


# ── OMEGA-inspired: Dedup + Contradiction Detection ─────────────────────────

def _content_hash(content: str) -> str:
    """Generate a hash of normalized content for exact-match dedup."""
    import hashlib
    normalized = content.strip().lower()
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _word_set(text: str) -> set:
    """Extract a set of meaningful words from text (for similarity)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    stopwords = {"the", "a", "an", "is", "was", "are", "were", "be", "been",
                 "to", "of", "in", "for", "on", "with", "at", "by", "from",
                 "and", "or", "not", "that", "this", "it", "its", "we", "i"}
    return {w for w in words if w not in stopwords and len(w) > 2}


def _content_similarity(a: str, b: str) -> float:
    """Jaccard similarity between word sets of two texts (0.0 to 1.0)."""
    set_a = _word_set(a)
    set_b = _word_set(b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def find_duplicates(new_content: str, existing_memories: list[dict]) -> list[dict]:
    """Find existing memories that are duplicates (hash or Jaccard >= 0.85)."""
    new_hash = _content_hash(new_content)
    duplicates = []
    for mem in existing_memories:
        if _content_hash(mem.get("content", "")) == new_hash:
            duplicates.append(mem)
            continue
        sim = _content_similarity(new_content, mem.get("content", ""))
        if sim >= DEDUP_SIMILARITY_THRESHOLD:
            duplicates.append(mem)
    return duplicates


def _days_since(iso_str: str) -> float:
    """Return days elapsed since an ISO 8601 timestamp. Returns 0 on parse error."""
    if not iso_str:
        return 0.0
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
    except (ValueError, TypeError):
        return 0.0


def _get_agent_id() -> str:
    """Return the agent ID from $CCA_CHAT_ID env var (e.g. 'desktop', 'cli1')."""
    return os.environ.get("CCA_CHAT_ID", "")


def decide_action(
    new_content: str, existing_memories: list[dict]
) -> tuple[str, str | None]:
    """Decide what to do with new_content against existing memories.

    Returns (action, memory_id):
    - ("ADD", None)       — no similar memory; create new
    - ("UPDATE", id)      — similar exists, new content is richer; update in place
    - ("SKIP", id)        — near-identical exists and is fresh; nothing to do
    - ("DELETE_ADD", id)  — near-identical exists but is stale (>90 days); replace

    Rules (applied to the most-similar existing memory):
      sim < 0.55            → ADD   (no meaningful overlap)
      0.55 <= sim < 0.85:
          new is >20% longer  → UPDATE (new enriches existing)
          old is stale        → UPDATE (refresh stale with new info)
          else                → ADD   (genuinely different perspectives)
      sim >= 0.85 (near-identical):
          old is stale        → DELETE_ADD (replace stale near-duplicate)
          new is >15% longer  → UPDATE     (new is richer version)
          else                → SKIP       (existing is fine)
    """
    if not existing_memories:
        return ("ADD", None)

    # Find most-similar existing memory
    best_sim = 0.0
    best_mem: dict | None = None
    for mem in existing_memories:
        sim = _content_similarity(new_content, mem.get("content", ""))
        if sim > best_sim:
            best_sim = sim
            best_mem = mem

    if best_sim < 0.55 or best_mem is None:
        return ("ADD", None)

    mid = best_mem["id"]
    old_content = best_mem.get("content", "")
    ref_date = (
        best_mem.get("last_accessed_at")
        or best_mem.get("updated_at")
        or best_mem.get("created_at", "")
    )
    days_old = _days_since(ref_date)

    if best_sim >= DEDUP_SIMILARITY_THRESHOLD:  # >= 0.85 near-identical
        if days_old > 90:
            return ("DELETE_ADD", mid)
        if old_content and len(new_content) > len(old_content) * 1.15:
            return ("UPDATE", mid)
        return ("SKIP", mid)

    # 0.55 <= sim < 0.85 — overlapping but different
    if old_content and len(new_content) > len(old_content) * 1.2:
        return ("UPDATE", mid)
    if days_old > 90:
        return ("UPDATE", mid)
    return ("ADD", None)


def _extract_mem_type(tags: list) -> str:
    """Extract memory type from tags list. Returns type string or 'decision'."""
    for tag in tags:
        if isinstance(tag, str) and tag.startswith("type:"):
            return tag[5:]
    return "decision"


def find_contradictions(
    new_content: str,
    new_type: str,
    new_tags: list[str],
    existing_memories: list[dict],
) -> list[dict]:
    """Find existing memories that contradict the new one (same type, overlapping tags, 55-85% similarity)."""
    contradictions = []
    new_tag_set = {t for t in new_tags if not t.startswith("type:")}

    for mem in existing_memories:
        mem_type = _extract_mem_type(mem.get("tags", []))
        if mem_type != new_type:
            continue
        mem_tags = {t for t in mem.get("tags", []) if not t.startswith("type:")}
        if not (new_tag_set & mem_tags):
            continue
        sim = _content_similarity(new_content, mem.get("content", ""))
        if 0.55 <= sim < DEDUP_SIMILARITY_THRESHOLD:
            contradictions.append(mem)

    return contradictions


def get_ttl_days(mem_type: str, confidence: str) -> int:
    """Get TTL in days based on memory type and confidence."""
    base_ttl = TYPE_TTL_DAYS.get(mem_type, 180)
    if confidence == "HIGH":
        return min(base_ttl * 2, 730)
    elif confidence == "LOW":
        return max(base_ttl // 2, 30)
    return base_ttl


def _build_tags(mem_type: str, inferred_tags: list[str]) -> list[str]:
    """Build tags list with type prefix. Max 5 tags total."""
    tags = [f"type:{mem_type}"]
    for t in inferred_tags:
        if t not in tags and len(tags) < 5:
            tags.append(t)
    return tags


def _validate_memory_params(
    content: str,
    mem_type: str,
    confidence: str,
) -> tuple[str, str, str] | None:
    """Validate and normalize memory parameters. Returns (content, type, confidence) or None."""
    content = content.strip()
    if not content:
        return None
    if _contains_credentials(content):
        return None
    content = _truncate(content)

    if mem_type not in VALID_TYPES:
        mem_type = "decision"
    if confidence not in ("HIGH", "MEDIUM", "LOW"):
        confidence = "MEDIUM"

    return content, mem_type, confidence


# ── PostToolUse Handler ───────────────────────────────────────────────────────

def handle_post_tool_use(hook_input: dict) -> dict:
    """Detect significant tool events and inject a context note."""
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name not in _SIGNIFICANT_TOOLS:
        return {}

    if tool_name in {"Write", "Edit"}:
        file_path = tool_input.get("file_path", "")
        if file_path:
            return {
                "additionalContext": (
                    f"[memory-system] File modified this session: {file_path}"
                )
            }

    return {}


# ── UserPromptSubmit Handler ──────────────────────────────────────────────────

def handle_user_prompt_submit(hook_input: dict, store: MemoryStore | None = None) -> dict:
    """
    Real-time memory capture from user prompts.
    Detects 'remember that', 'always use', 'never do', 'rule:', 'non-negotiable:'
    and writes to FTS5 MemoryStore immediately — available within the same session.

    Args:
        hook_input: Hook event payload with 'prompt' and 'cwd' fields.
        store: Optional MemoryStore instance (for testing). If None, opens default.
    """
    prompt = hook_input.get("prompt", "")
    cwd = hook_input.get("cwd", "")
    project = _project_slug(cwd)

    if not prompt or len(prompt) < 15:
        return {}

    # Extract explicit memory candidates from the prompt
    candidates = _extract_from_prompt(prompt, project)
    if not candidates:
        return {}

    # Open store (default or injected for tests)
    own_store = store is None
    if own_store:
        try:
            store = MemoryStore()
        except Exception:
            return {}  # Fail silently

    agent_id = _get_agent_id()

    try:
        existing = store.list_all(project=project, limit=500)
        new_count = 0
        updated_count = 0

        for candidate in candidates:
            content = candidate["content"]
            mem_type = candidate["type"]
            tags = candidate["tags"]

            action, target_id = decide_action(content, existing)

            if action == "SKIP":
                continue
            elif action == "UPDATE" and target_id:
                store.update(target_id, content=content)
                # Refresh in local list
                existing = [
                    {**m, "content": content} if m["id"] == target_id else m
                    for m in existing
                ]
                updated_count += 1
            elif action in ("ADD", "DELETE_ADD"):
                if action == "DELETE_ADD" and target_id:
                    store.delete(target_id)
                    existing = [m for m in existing if m["id"] != target_id]
                ttl = get_ttl_days(mem_type, candidate["confidence"])
                created = store.create_memory(
                    content=content,
                    tags=tags,
                    confidence=candidate["confidence"],
                    source=candidate["source"],
                    context=f"type:{mem_type}",
                    project=project,
                    ttl_days=ttl,
                    user_id=project,
                    agent_id=agent_id,
                )
                existing.append(created)
                new_count += 1

        total = new_count + updated_count
        if total > 0:
            parts = []
            if new_count:
                parts.append(f"saved {new_count} new")
            if updated_count:
                parts.append(f"updated {updated_count}")
            return {
                "additionalContext": (
                    f"[memory-system] {', '.join(parts)} "
                    f"{'memory' if total == 1 else 'memories'} from user prompt."
                )
            }

    except Exception:
        pass  # Fail silently — hooks must never crash the CLI
    finally:
        if own_store and store is not None:
            store.close()

    return {}


def _extract_from_prompt(prompt: str, project: str) -> list[dict]:
    """
    Parse a user prompt for explicit memory instructions.
    Same patterns as transcript parsing but operates on raw prompt text.
    Returns list of candidate dicts. Capped at 3 per prompt (speed).
    """
    explicit_patterns = [
        re.compile(r"remember (that |this |):?\s*(.{15,200})", re.IGNORECASE),
        re.compile(r"always (use|do|prefer|run|start|check)\s+(.{10,150})", re.IGNORECASE),
        re.compile(r"never (use|do|touch|modify)\s+(.{10,150})", re.IGNORECASE),
        re.compile(r"rule:\s*(.{10,200})", re.IGNORECASE),
        re.compile(r"non-negotiable:\s*(.{10,200})", re.IGNORECASE),
    ]

    memories = []
    used_spans = []  # Track character ranges already captured

    for pattern in explicit_patterns:
        for match in pattern.finditer(prompt):
            # Skip if this match overlaps with an already-captured span
            start, end = match.start(), match.end()
            if any(s <= start < e or s < end <= e for s, e in used_spans):
                continue

            captured = match.group(match.lastindex).strip()
            # Trim at sentence boundary if present
            dot_pos = captured.find(".")
            if dot_pos > 15:
                captured = captured[:dot_pos]

            if _contains_credentials(captured):
                continue

            validated = _validate_memory_params(captured, "preference", "HIGH")
            if not validated:
                continue
            content, mem_type, confidence = validated

            # Skip if too similar to something already captured
            if any(_content_similarity(content, m["content"]) >= 0.6
                   for m in memories):
                continue

            used_spans.append((start, end))
            tags = _build_tags(mem_type, _infer_tags(content))
            memories.append({
                "content": content,
                "type": mem_type,
                "tags": tags,
                "confidence": confidence,
                "source": "realtime",
                "project": project,
            })

            if len(memories) >= 3:
                return memories

    return memories


# ── Stop Hook Handler ─────────────────────────────────────────────────────────

def handle_stop(hook_input: dict, store: MemoryStore | None = None) -> dict:
    """
    Extract memories from last_assistant_message and transcript.
    Writes confirmed memories to FTS5 MemoryStore.

    Args:
        hook_input: Hook event payload from Claude Code.
        store: Optional MemoryStore instance (for testing). If None, opens default.
    """
    cwd = hook_input.get("cwd", "")
    last_msg = hook_input.get("last_assistant_message", "")
    transcript_path = hook_input.get("transcript_path", "")
    project = _project_slug(cwd)

    # Extract candidate memories from message + transcript
    candidates = _extract_memories_from_message(last_msg, project)
    candidates += _extract_from_transcript(transcript_path, project)

    if not candidates:
        return {}

    # Open store (default or injected for tests)
    own_store = store is None
    if own_store:
        try:
            store = MemoryStore()
        except Exception:
            return {}  # Fail silently — hook must not crash

    agent_id = _get_agent_id()

    try:
        # Load existing project memories for dedup/contradiction checks
        existing = store.list_all(project=project, limit=500)

        new_count = 0
        updated_count = 0
        superseded_ids: set[str] = set()

        for candidate in candidates:
            content = candidate["content"]
            mem_type = candidate["type"]
            tags = candidate["tags"]

            action, target_id = decide_action(content, existing)

            if action == "SKIP":
                continue
            elif action == "UPDATE" and target_id:
                store.update(target_id, content=content)
                existing = [
                    {**m, "content": content} if m["id"] == target_id else m
                    for m in existing
                ]
                updated_count += 1
                continue
            elif action == "DELETE_ADD" and target_id:
                superseded_ids.add(target_id)
                existing = [m for m in existing if m["id"] != target_id]

            # action is ADD or DELETE_ADD (old removed above) — also check contradictions
            contradictions = find_contradictions(content, mem_type, tags, existing)
            for old_mem in contradictions:
                superseded_ids.add(old_mem["id"])

            # Write new memory
            ttl = get_ttl_days(mem_type, candidate["confidence"])
            created = store.create_memory(
                content=content,
                tags=tags,
                confidence=candidate["confidence"],
                source=candidate["source"],
                context=f"type:{mem_type}",
                project=project,
                ttl_days=ttl,
                user_id=project,
                agent_id=agent_id,
            )
            existing.append(created)
            new_count += 1

        # Remove superseded / contradicted memories
        for old_id in superseded_ids:
            store.delete(old_id)

        total = new_count + updated_count
        if total > 0:
            parts = []
            if new_count:
                parts.append(f"{new_count} new")
            if updated_count:
                parts.append(f"{updated_count} updated")
            return {
                "additionalContext": (
                    f"[memory-system] {', '.join(parts)} "
                    f"{'memory' if total == 1 else 'memories'} written. "
                    f"Run 'python3 memory-system/cli.py' to review."
                )
            }

    except Exception:
        pass  # Fail silently — hooks must never crash the CLI
    finally:
        if own_store and store is not None:
            store.close()

    return {}


def _extract_memories_from_message(message: str, project: str) -> list[dict]:
    """
    Parse last_assistant_message for decision-worthy sentences.
    Uses keyword heuristics — conservative, low false-positive rate.
    Returns list of candidate dicts (not yet written to store).
    """
    if not message or len(message) < 20:
        return []

    memories = []
    sentences = re.split(r"(?<=[.!?])\s+", message)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 30 or len(sentence) > MAX_CONTENT_CHARS:
            continue

        lower = sentence.lower()
        if not any(kw in lower for kw in _DECISION_KEYWORDS):
            continue

        if sentence.endswith("?"):
            continue

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

        validated = _validate_memory_params(sentence, mem_type, "MEDIUM")
        if not validated:
            continue
        content, mem_type, confidence = validated
        tags = _build_tags(mem_type, _infer_tags(content))

        memories.append({
            "content": content,
            "type": mem_type,
            "tags": tags,
            "confidence": confidence,
            "source": "session-end",
            "project": project,
        })

    return memories[:5]  # Cap at 5 per session


def _extract_from_transcript(transcript_path: str, project: str) -> list[dict]:
    """
    Parse session transcript JSONL for explicit memory instructions.
    Looks for 'remember that', 'always', 'never'. These get HIGH confidence.
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
                        captured = match.group(match.lastindex).strip()
                        if _contains_credentials(captured):
                            continue
                        validated = _validate_memory_params(
                            _truncate(captured), "preference", "HIGH"
                        )
                        if not validated:
                            continue
                        content, mem_type, confidence = validated
                        tags = _build_tags(mem_type, _infer_tags(content))
                        memories.append({
                            "content": content,
                            "type": mem_type,
                            "tags": tags,
                            "confidence": confidence,
                            "source": "explicit",
                            "project": project,
                        })

    except OSError:
        pass

    return memories[:10]


def _infer_tags(content: str) -> list[str]:
    """Infer 1-3 tags from content by keyword matching."""
    lower = content.lower()
    tags = []

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
    elif event == "UserPromptSubmit":
        result = handle_user_prompt_submit(hook_input)
    elif event == "Stop":
        result = handle_stop(hook_input)
    else:
        result = {}

    if result:
        print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
