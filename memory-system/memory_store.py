#!/usr/bin/env python3
"""
SQLite + FTS5 memory storage backend.
Replaces JSON file storage with relevance-ranked full-text search.
Python stdlib only — sqlite3 ships with FTS5 on macOS Python 3.10+.

Usage:
    store = MemoryStore()              # uses default ~/.claude-memory/memories.db
    store = MemoryStore("/tmp/test.db")  # custom path (for tests)

One file = one job: this module handles CRUD + search + TTL cleanup.
It does NOT handle MCP protocol, hook events, or credential filtering.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from decay import compute_effective_confidence


# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_DB_DIR = Path.home() / ".claude-memory"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "memories.db"

VALID_CONFIDENCE = ("HIGH", "MEDIUM", "LOW")

# TTL defaults by confidence level (days)
TTL_BY_CONFIDENCE = {
    "HIGH": 365,
    "MEDIUM": 180,
    "LOW": 90,
}

SCHEMA_VERSION = "2.0"


# ── ID generation ────────────────────────────────────────────────────────────

def _make_id() -> str:
    """Generate a unique memory ID with 8-char hex suffix (collision-safe)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"mem_{ts}_{suffix}"


def _now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── MemoryStore ──────────────────────────────────────────────────────────────

class MemoryStore:
    """SQLite + FTS5 backend for persistent cross-session memory."""

    def __init__(self, db_path: Optional[str] = None):
        """Open or create the memory database.

        Args:
            db_path: Path to the SQLite database file.
                     If None, uses ~/.claude-memory/memories.db.
                     Pass ":memory:" for in-memory (tests only).
        """
        if db_path is None:
            self._path = DEFAULT_DB_PATH
            DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
        elif db_path == ":memory:":
            self._path = ":memory:"
        else:
            self._path = Path(db_path)
            self._path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self._path),
            isolation_level=None,  # autocommit off — we manage transactions
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        """Create tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id          TEXT PRIMARY KEY,
                content     TEXT NOT NULL,
                tags        TEXT NOT NULL DEFAULT '[]',
                confidence  TEXT NOT NULL DEFAULT 'MEDIUM',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                ttl_days    INTEGER NOT NULL DEFAULT 180,
                source      TEXT NOT NULL DEFAULT 'explicit',
                context     TEXT NOT NULL DEFAULT '',
                project     TEXT NOT NULL DEFAULT '',
                user_id     TEXT NOT NULL DEFAULT 'default',
                agent_id    TEXT NOT NULL DEFAULT '',
                run_id      TEXT NOT NULL DEFAULT ''
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                tags,
                context,
                content_rowid='rowid',
                tokenize='unicode61'
            );

            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        # Migrations: add columns if missing
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "last_accessed_at" not in cols:
            self._conn.execute("ALTER TABLE memories ADD COLUMN last_accessed_at TEXT NOT NULL DEFAULT ''")
        if "user_id" not in cols:
            self._conn.execute("ALTER TABLE memories ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default'")
        if "agent_id" not in cols:
            self._conn.execute("ALTER TABLE memories ADD COLUMN agent_id TEXT NOT NULL DEFAULT ''")
        if "run_id" not in cols:
            self._conn.execute("ALTER TABLE memories ADD COLUMN run_id TEXT NOT NULL DEFAULT ''")

        # Store schema version
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,)
        )
        self._conn.commit()

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_memory(
        self,
        content: str,
        tags: Optional[list[str]] = None,
        confidence: str = "MEDIUM",
        source: str = "explicit",
        context: str = "",
        project: str = "",
        memory_id: Optional[str] = None,
        ttl_days: Optional[int] = None,
        user_id: str = "default",
        agent_id: str = "",
        run_id: str = "",
    ) -> dict:
        """Create a new memory entry. Returns the created memory as a dict.

        Args:
            content: The memory text (required, non-empty).
            tags: List of tags for categorization.
            confidence: HIGH, MEDIUM, or LOW.
            source: How the memory was captured (explicit/inferred/session-end).
            context: Additional context about where/when this was learned.
            project: Project slug this memory belongs to.
            memory_id: Custom ID. If None, auto-generated with 8-char hex suffix.
            ttl_days: Custom TTL. If None, derived from confidence level.

        Returns:
            Dict with all memory fields.

        Raises:
            ValueError: If content is empty or confidence is invalid.
        """
        if not content or not content.strip():
            raise ValueError("Memory content cannot be empty")

        if confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Confidence must be one of {VALID_CONFIDENCE}, got '{confidence}'")

        mid = memory_id or _make_id()
        now = _now_iso()
        tags_list = tags or []
        tags_json = json.dumps(tags_list)
        ttl = ttl_days if ttl_days is not None else TTL_BY_CONFIDENCE.get(confidence, 180)

        self._conn.execute("BEGIN")
        try:
            self._conn.execute(
                """INSERT INTO memories (id, content, tags, confidence, created_at,
                   updated_at, ttl_days, source, context, project,
                   user_id, agent_id, run_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mid, content.strip(), tags_json, confidence, now, now, ttl, source,
                 context, project, user_id, agent_id, run_id),
            )
            # Get the rowid for the FTS index
            rowid = self._conn.execute(
                "SELECT rowid FROM memories WHERE id = ?", (mid,)
            ).fetchone()[0]
            self._conn.execute(
                "INSERT INTO memories_fts (rowid, content, tags, context) VALUES (?, ?, ?, ?)",
                (rowid, content.strip(), " ".join(tags_list), context),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

        return self._row_to_dict_by_id(mid)

    def get_by_id(self, memory_id: str) -> Optional[dict]:
        """Fetch a single memory by ID. Returns None if not found."""
        row = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
        confidence: Optional[str] = None,
        context: Optional[str] = None,
        ttl_days: Optional[int] = None,
    ) -> Optional[dict]:
        """Update an existing memory. Returns updated dict, or None if not found.

        Only provided fields are updated; others remain unchanged.
        """
        existing = self._conn.execute(
            "SELECT rowid, * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if existing is None:
            return None

        rowid = existing[0]  # rowid is first column
        now = _now_iso()
        updates = {"updated_at": now}
        fts_updates = {}

        if content is not None:
            if not content.strip():
                raise ValueError("Memory content cannot be empty")
            updates["content"] = content.strip()
            fts_updates["content"] = content.strip()

        if tags is not None:
            updates["tags"] = json.dumps(tags)
            fts_updates["tags"] = " ".join(tags)

        if confidence is not None:
            if confidence not in VALID_CONFIDENCE:
                raise ValueError(f"Confidence must be one of {VALID_CONFIDENCE}")
            updates["confidence"] = confidence

        if context is not None:
            updates["context"] = context
            fts_updates["context"] = context

        if ttl_days is not None:
            updates["ttl_days"] = ttl_days

        self._conn.execute("BEGIN")
        try:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [memory_id]
            self._conn.execute(
                f"UPDATE memories SET {set_clause} WHERE id = ?", values
            )

            if fts_updates:
                # Delete old FTS entry and re-insert with updated values
                self._conn.execute(
                    "DELETE FROM memories_fts WHERE rowid = ?", (rowid,)
                )
                # Get current values for fields not being updated
                current = self._conn.execute(
                    "SELECT content, tags, context FROM memories WHERE id = ?",
                    (memory_id,)
                ).fetchone()
                fts_content = fts_updates.get("content", current[0])
                fts_tags = fts_updates.get("tags", " ".join(json.loads(current[1])))
                fts_context = fts_updates.get("context", current[2])
                self._conn.execute(
                    "INSERT INTO memories_fts (rowid, content, tags, context) VALUES (?, ?, ?, ?)",
                    (rowid, fts_content, fts_tags, fts_context),
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

        return self._row_to_dict_by_id(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID. Returns True if deleted, False if not found."""
        row = self._conn.execute(
            "SELECT rowid FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return False

        rowid = row[0]
        self._conn.execute("BEGIN")
        try:
            self._conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (rowid,))
            self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return True

    def list_all(
        self,
        project: Optional[str] = None,
        limit: int = 100,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> list[dict]:
        """List all memories, optionally filtered by project and/or scope.

        Three-tier scoping: user_id > agent_id > run_id (each optional).
        Returns up to `limit` results, ordered by updated_at descending.
        """
        conditions = []
        params: list = []
        if project is not None:
            conditions.append("project = ?")
            params.append(project)
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if run_id is not None:
            conditions.append("run_id = ?")
            params.append(run_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM memories {where} ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ── Search ───────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 10,
        project: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> list[dict]:
        """Full-text search with BM25 relevance ranking.

        Args:
            query: Search terms. Supports FTS5 syntax (AND, OR, NOT, phrases).
                   Empty query returns empty list.
            limit: Maximum results to return (default 10).
            project: If provided, filter results to this project only.
            user_id: If provided, filter to this user's memories only.
            agent_id: If provided, filter to this agent's memories only.
            run_id: If provided, filter to this run's memories only.

        Returns:
            List of memory dicts, ordered by relevance (best match first).
        """
        if not query or not query.strip():
            return []

        # Escape special FTS5 characters for safe querying, unless the user
        # is intentionally using FTS5 syntax (AND/OR/NOT/quotes).
        safe_query = self._prepare_query(query.strip())
        if not safe_query:
            return []

        # Build optional scope filter for the JOIN
        scope_conditions = []
        scope_params: list = []
        if project is not None:
            scope_conditions.append("m.project = ?")
            scope_params.append(project)
        if user_id is not None:
            scope_conditions.append("m.user_id = ?")
            scope_params.append(user_id)
        if agent_id is not None:
            scope_conditions.append("m.agent_id = ?")
            scope_params.append(agent_id)
        if run_id is not None:
            scope_conditions.append("m.run_id = ?")
            scope_params.append(run_id)

        scope_clause = (" AND " + " AND ".join(scope_conditions)) if scope_conditions else ""

        try:
            rows = self._conn.execute(
                f"""SELECT m.*, bm25(memories_fts) AS rank
                   FROM memories_fts f
                   JOIN memories m ON f.rowid = m.rowid
                   WHERE memories_fts MATCH ?{scope_clause}
                   ORDER BY rank
                   LIMIT ?""",
                [safe_query] + scope_params + [limit],
            ).fetchall()
        except sqlite3.OperationalError:
            # Bad FTS5 query syntax — fall back to empty results
            return []

        now = datetime.now(timezone.utc)
        results = []
        ids_to_touch = []
        for r in rows:
            d = self._row_to_dict(r)
            # Compute days since last access (or creation if never accessed)
            ref_field = d.get("last_accessed_at") or d.get("updated_at") or d.get("created_at")
            try:
                ref_dt = datetime.fromisoformat(ref_field.replace("Z", "+00:00"))
                days_since = max(0.0, (now - ref_dt).total_seconds() / 86400)
            except (ValueError, TypeError, AttributeError):
                days_since = 0.0
            d["effective_confidence"] = compute_effective_confidence(
                100.0,  # base score normalized to 100
                days_since,
                d.get("confidence", "MEDIUM"),
            )
            results.append(d)
            ids_to_touch.append(d["id"])

        # Touch last_accessed_at for all returned memories
        now_iso = _now_iso()
        if ids_to_touch:
            placeholders = ",".join("?" for _ in ids_to_touch)
            self._conn.execute(
                f"UPDATE memories SET last_accessed_at = ? WHERE id IN ({placeholders})",
                [now_iso] + ids_to_touch,
            )
            self._conn.commit()

        # Sort by effective_confidence descending (highest relevance + freshness first)
        results.sort(key=lambda d: d["effective_confidence"], reverse=True)
        return results

    def _prepare_query(self, query: str) -> str:
        """Prepare a search query for FTS5.

        Simple queries (no operators) get quoted as terms.
        Queries with FTS5 operators (AND/OR/NOT/quotes) pass through.
        """
        # If user is using FTS5 operators, pass through as-is
        fts5_operators = (' AND ', ' OR ', ' NOT ', '"')
        if any(op in query for op in fts5_operators):
            return query

        # For simple queries, split into terms and join with implicit AND
        # Each term is wrapped in quotes to handle special chars safely
        terms = query.split()
        if not terms:
            return ""
        if len(terms) == 1:
            # Single term: quote it for safety
            escaped = terms[0].replace('"', '""')
            return f'"{escaped}"'
        # Multiple terms: each quoted, implicit AND
        parts = []
        for t in terms:
            escaped = t.replace('"', '""')
            parts.append(f'"{escaped}"')
        return " AND ".join(parts)

    # ── TTL Cleanup ──────────────────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        """Delete memories past their TTL based on updated_at + ttl_days.

        Returns the number of memories deleted.
        """
        now = datetime.now(timezone.utc)
        # Get all memories and check TTL
        rows = self._conn.execute(
            "SELECT id, rowid, updated_at, ttl_days FROM memories"
        ).fetchall()

        to_delete = []
        for row in rows:
            try:
                updated = datetime.fromisoformat(row[2].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            expiry = updated + timedelta(days=row[3])
            if now >= expiry:
                to_delete.append((row[0], row[1]))  # (id, rowid)

        if not to_delete:
            return 0

        self._conn.execute("BEGIN")
        try:
            for mid, rowid in to_delete:
                self._conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (rowid,))
                self._conn.execute("DELETE FROM memories WHERE id = ?", (mid,))
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

        return len(to_delete)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _row_to_dict(self, row) -> dict:
        """Convert a sqlite3.Row to a plain dict with parsed tags."""
        d = dict(row)
        # Parse tags from JSON string
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError, KeyError):
            d["tags"] = []
        # Remove internal rank column if present (from search queries)
        d.pop("rank", None)
        d.pop("rowid", None)
        return d

    def _row_to_dict_by_id(self, memory_id: str) -> dict:
        """Fetch and convert a memory by ID."""
        row = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def count(self) -> int:
        """Return total number of memories in the store."""
        return self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
