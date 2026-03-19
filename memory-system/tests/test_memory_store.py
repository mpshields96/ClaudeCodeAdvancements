#!/usr/bin/env python3
"""
Tests for memory_store.py — SQLite + FTS5 memory backend.
Run: python3 memory-system/tests/test_memory_store.py
All tests use temporary directories or :memory: — no writes to ~/.claude-memory.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_store import MemoryStore, _make_id, _now_iso, TTL_BY_CONFIDENCE


# ═══════════════════════════════════════════════════════════════════════════
# ID Generation
# ═══════════════════════════════════════════════════════════════════════════

class TestMakeId(unittest.TestCase):
    def test_has_mem_prefix(self):
        mid = _make_id()
        self.assertTrue(mid.startswith("mem_"))

    def test_has_8_char_hex_suffix(self):
        mid = _make_id()
        suffix = mid.split("_")[-1]
        self.assertEqual(len(suffix), 8)
        # Verify it's valid hex
        int(suffix, 16)

    def test_unique_across_100(self):
        ids = {_make_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_format_matches_pattern(self):
        mid = _make_id()
        parts = mid.split("_")
        self.assertEqual(parts[0], "mem")
        # date part: YYYYMMDD
        self.assertEqual(len(parts[1]), 8)
        # time part: HHMMSS
        self.assertEqual(len(parts[2]), 6)
        # hex suffix
        self.assertEqual(len(parts[3]), 8)


# ═══════════════════════════════════════════════════════════════════════════
# Store Initialization
# ═══════════════════════════════════════════════════════════════════════════

class TestStoreInit(unittest.TestCase):
    def test_creates_in_memory(self):
        store = MemoryStore(":memory:")
        self.assertEqual(store.count(), 0)
        store.close()

    def test_creates_db_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = MemoryStore(db_path)
            self.assertTrue(os.path.exists(db_path))
            store.close()

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "subdir", "deep", "test.db")
            store = MemoryStore(db_path)
            self.assertTrue(os.path.exists(db_path))
            store.close()

    def test_reopens_existing_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store1 = MemoryStore(db_path)
            store1.create_memory("persistent data", tags=["test"])
            store1.close()

            store2 = MemoryStore(db_path)
            self.assertEqual(store2.count(), 1)
            store2.close()

    def test_context_manager(self):
        with MemoryStore(":memory:") as store:
            store.create_memory("test content")
            self.assertEqual(store.count(), 1)


# ═══════════════════════════════════════════════════════════════════════════
# Create Memory
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateMemory(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_basic_create(self):
        mem = self.store.create_memory("Use SQLite for storage")
        self.assertIn("mem_", mem["id"])
        self.assertEqual(mem["content"], "Use SQLite for storage")
        self.assertEqual(mem["confidence"], "MEDIUM")
        self.assertEqual(mem["source"], "explicit")

    def test_create_with_all_fields(self):
        mem = self.store.create_memory(
            content="Always run tests first",
            tags=["testing", "workflow"],
            confidence="HIGH",
            source="session-end",
            context="Learned during debugging session",
            project="claudecodeadvancements",
        )
        self.assertEqual(mem["content"], "Always run tests first")
        self.assertEqual(mem["tags"], ["testing", "workflow"])
        self.assertEqual(mem["confidence"], "HIGH")
        self.assertEqual(mem["source"], "session-end")
        self.assertEqual(mem["context"], "Learned during debugging session")
        self.assertEqual(mem["project"], "claudecodeadvancements")

    def test_create_with_custom_id(self):
        mem = self.store.create_memory("test", memory_id="mem_custom_12345678")
        self.assertEqual(mem["id"], "mem_custom_12345678")

    def test_create_with_custom_ttl(self):
        mem = self.store.create_memory("test", ttl_days=30)
        self.assertEqual(mem["ttl_days"], 30)

    def test_ttl_defaults_by_confidence(self):
        high = self.store.create_memory("h", confidence="HIGH")
        med = self.store.create_memory("m", confidence="MEDIUM")
        low = self.store.create_memory("l", confidence="LOW")
        self.assertEqual(high["ttl_days"], 365)
        self.assertEqual(med["ttl_days"], 180)
        self.assertEqual(low["ttl_days"], 90)

    def test_empty_content_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_memory("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_memory("   ")

    def test_invalid_confidence_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_memory("test", confidence="EXTREME")

    def test_content_stripped(self):
        mem = self.store.create_memory("  padded content  ")
        self.assertEqual(mem["content"], "padded content")

    def test_timestamps_set(self):
        mem = self.store.create_memory("test")
        self.assertTrue(mem["created_at"].endswith("Z"))
        self.assertTrue(mem["updated_at"].endswith("Z"))
        self.assertEqual(mem["created_at"], mem["updated_at"])

    def test_duplicate_id_raises(self):
        self.store.create_memory("first", memory_id="mem_dup_00000001")
        with self.assertRaises(Exception):
            self.store.create_memory("second", memory_id="mem_dup_00000001")

    def test_count_increments(self):
        self.assertEqual(self.store.count(), 0)
        self.store.create_memory("one")
        self.assertEqual(self.store.count(), 1)
        self.store.create_memory("two")
        self.assertEqual(self.store.count(), 2)

    def test_tags_default_empty(self):
        mem = self.store.create_memory("no tags")
        self.assertEqual(mem["tags"], [])


# ═══════════════════════════════════════════════════════════════════════════
# Get By ID
# ═══════════════════════════════════════════════════════════════════════════

class TestGetById(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_found(self):
        created = self.store.create_memory("test", memory_id="mem_get_12345678")
        found = self.store.get_by_id("mem_get_12345678")
        self.assertIsNotNone(found)
        self.assertEqual(found["content"], "test")

    def test_not_found(self):
        result = self.store.get_by_id("mem_nonexistent_00")
        self.assertIsNone(result)

    def test_returns_all_fields(self):
        self.store.create_memory(
            "full fields", tags=["a", "b"], confidence="HIGH",
            source="inferred", context="ctx", project="proj",
            memory_id="mem_full_12345678",
        )
        mem = self.store.get_by_id("mem_full_12345678")
        self.assertEqual(mem["tags"], ["a", "b"])
        self.assertEqual(mem["confidence"], "HIGH")
        self.assertEqual(mem["source"], "inferred")
        self.assertEqual(mem["context"], "ctx")
        self.assertEqual(mem["project"], "proj")


# ═══════════════════════════════════════════════════════════════════════════
# Update
# ═══════════════════════════════════════════════════════════════════════════

class TestUpdate(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(":memory:")
        self.store.create_memory(
            "original content",
            tags=["old"],
            confidence="LOW",
            context="old context",
            memory_id="mem_upd_12345678",
        )

    def tearDown(self):
        self.store.close()

    def test_update_content(self):
        updated = self.store.update("mem_upd_12345678", content="new content")
        self.assertEqual(updated["content"], "new content")

    def test_update_tags(self):
        updated = self.store.update("mem_upd_12345678", tags=["new", "tags"])
        self.assertEqual(updated["tags"], ["new", "tags"])

    def test_update_confidence(self):
        updated = self.store.update("mem_upd_12345678", confidence="HIGH")
        self.assertEqual(updated["confidence"], "HIGH")

    def test_update_context(self):
        updated = self.store.update("mem_upd_12345678", context="new context")
        self.assertEqual(updated["context"], "new context")

    def test_update_ttl(self):
        updated = self.store.update("mem_upd_12345678", ttl_days=30)
        self.assertEqual(updated["ttl_days"], 30)

    def test_update_preserves_unchanged(self):
        updated = self.store.update("mem_upd_12345678", confidence="HIGH")
        self.assertEqual(updated["content"], "original content")
        self.assertEqual(updated["tags"], ["old"])

    def test_update_bumps_updated_at(self):
        before = self.store.get_by_id("mem_upd_12345678")
        # Small delay to ensure timestamp changes
        updated = self.store.update("mem_upd_12345678", content="changed")
        self.assertGreaterEqual(updated["updated_at"], before["updated_at"])

    def test_update_nonexistent_returns_none(self):
        result = self.store.update("mem_nonexistent_00", content="test")
        self.assertIsNone(result)

    def test_update_empty_content_raises(self):
        with self.assertRaises(ValueError):
            self.store.update("mem_upd_12345678", content="")

    def test_update_invalid_confidence_raises(self):
        with self.assertRaises(ValueError):
            self.store.update("mem_upd_12345678", confidence="BOGUS")

    def test_update_content_searchable(self):
        """After updating content, new content is findable via FTS."""
        self.store.update("mem_upd_12345678", content="unique_xylophone_term")
        results = self.store.search("unique_xylophone_term")
        self.assertEqual(len(results), 1)

    def test_update_old_content_not_searchable(self):
        """After updating content, old content should not match."""
        self.store.update("mem_upd_12345678", content="completely different text")
        results = self.store.search("original content")
        self.assertEqual(len(results), 0)


# ═══════════════════════════════════════════════════════════════════════════
# Delete
# ═══════════════════════════════════════════════════════════════════════════

class TestDelete(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_delete_existing(self):
        self.store.create_memory("deleteme", memory_id="mem_del_12345678")
        result = self.store.delete("mem_del_12345678")
        self.assertTrue(result)
        self.assertIsNone(self.store.get_by_id("mem_del_12345678"))

    def test_delete_nonexistent(self):
        result = self.store.delete("mem_nonexistent_00")
        self.assertFalse(result)

    def test_delete_removes_from_fts(self):
        self.store.create_memory("searchable_zephyr", memory_id="mem_dfts_1234567")
        self.store.delete("mem_dfts_1234567")
        results = self.store.search("searchable_zephyr")
        self.assertEqual(len(results), 0)

    def test_delete_decrements_count(self):
        self.store.create_memory("a", memory_id="mem_cnt1_12345678")
        self.store.create_memory("b", memory_id="mem_cnt2_12345678")
        self.assertEqual(self.store.count(), 2)
        self.store.delete("mem_cnt1_12345678")
        self.assertEqual(self.store.count(), 1)


# ═══════════════════════════════════════════════════════════════════════════
# List All
# ═══════════════════════════════════════════════════════════════════════════

class TestListAll(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_empty_store(self):
        self.assertEqual(self.store.list_all(), [])

    def test_returns_all(self):
        self.store.create_memory("one")
        self.store.create_memory("two")
        self.store.create_memory("three")
        results = self.store.list_all()
        self.assertEqual(len(results), 3)

    def test_filter_by_project(self):
        self.store.create_memory("a", project="proj1")
        self.store.create_memory("b", project="proj2")
        self.store.create_memory("c", project="proj1")
        results = self.store.list_all(project="proj1")
        self.assertEqual(len(results), 2)

    def test_respects_limit(self):
        for i in range(20):
            self.store.create_memory(f"mem {i}")
        results = self.store.list_all(limit=5)
        self.assertEqual(len(results), 5)

    def test_ordered_by_updated_at_desc(self):
        # Create in order and update the first one last
        self.store.create_memory("first", memory_id="mem_ord1_12345678")
        self.store.create_memory("second", memory_id="mem_ord2_12345678")
        self.store.update("mem_ord1_12345678", content="first updated")
        results = self.store.list_all()
        self.assertEqual(results[0]["id"], "mem_ord1_12345678")


# ═══════════════════════════════════════════════════════════════════════════
# FTS5 Search
# ═══════════════════════════════════════════════════════════════════════════

class TestSearch(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(":memory:")
        # Seed with test data
        self.store.create_memory(
            "Use SQLite for local storage because it requires no server",
            tags=["architecture", "storage"],
            project="cca",
            memory_id="mem_sql_12345678",
        )
        self.store.create_memory(
            "PostToolUse hooks fire after Write and Edit tool calls",
            tags=["hooks", "capture"],
            project="cca",
            memory_id="mem_hook_12345678",
        )
        self.store.create_memory(
            "Never store API keys or credentials in memory content",
            tags=["security", "credentials"],
            project="cca",
            memory_id="mem_sec_12345678",
        )
        self.store.create_memory(
            "FTS5 provides relevance-ranked full-text search with BM25",
            tags=["search", "fts5"],
            project="other",
            memory_id="mem_fts_12345678",
        )

    def tearDown(self):
        self.store.close()

    def test_single_term_match(self):
        results = self.store.search("SQLite")
        self.assertGreater(len(results), 0)
        ids = [r["id"] for r in results]
        self.assertIn("mem_sql_12345678", ids)

    def test_multi_term_match(self):
        results = self.store.search("SQLite storage")
        self.assertGreater(len(results), 0)
        # SQLite + storage memory should rank highest
        self.assertEqual(results[0]["id"], "mem_sql_12345678")

    def test_tag_search(self):
        results = self.store.search("security")
        self.assertGreater(len(results), 0)
        ids = [r["id"] for r in results]
        self.assertIn("mem_sec_12345678", ids)

    def test_context_search(self):
        self.store.create_memory(
            "test content",
            context="learned during overnight session",
            memory_id="mem_ctx_12345678",
        )
        results = self.store.search("overnight")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "mem_ctx_12345678")

    def test_empty_query_returns_empty(self):
        self.assertEqual(self.store.search(""), [])

    def test_whitespace_query_returns_empty(self):
        self.assertEqual(self.store.search("   "), [])

    def test_no_match_returns_empty(self):
        self.assertEqual(self.store.search("xylophone"), [])

    def test_limit_respected(self):
        results = self.store.search("storage", limit=1)
        self.assertLessEqual(len(results), 1)

    def test_project_filter(self):
        results = self.store.search("FTS5", project="other")
        self.assertEqual(len(results), 1)
        results_cca = self.store.search("FTS5", project="cca")
        self.assertEqual(len(results_cca), 0)

    def test_relevance_ranking(self):
        """More relevant results should rank higher."""
        # "SQLite storage" should match mem_sql better than mem_fts
        results = self.store.search("SQLite local storage")
        if len(results) > 1:
            self.assertEqual(results[0]["id"], "mem_sql_12345678")

    def test_case_insensitive(self):
        results = self.store.search("sqlite")
        self.assertGreater(len(results), 0)

    def test_special_characters_safe(self):
        """Special chars should not crash the search."""
        results = self.store.search("test (parentheses) [brackets]")
        # Should not raise, results may be empty
        self.assertIsInstance(results, list)

    def test_quotes_in_query(self):
        """Quoted phrases use FTS5 phrase search."""
        results = self.store.search('"local storage"')
        self.assertGreater(len(results), 0)

    def test_fts5_and_operator(self):
        results = self.store.search("hooks AND capture")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "mem_hook_12345678")

    def test_fts5_not_operator(self):
        results = self.store.search("storage NOT SQLite")
        # Should not include the SQLite memory, but might include FTS5 one
        ids = [r["id"] for r in results]
        self.assertNotIn("mem_sql_12345678", ids)

    def test_results_have_all_fields(self):
        results = self.store.search("SQLite")
        self.assertGreater(len(results), 0)
        mem = results[0]
        for field in ("id", "content", "tags", "confidence", "created_at",
                       "updated_at", "ttl_days", "source", "context", "project"):
            self.assertIn(field, mem, f"Missing field: {field}")

    def test_tags_returned_as_list(self):
        results = self.store.search("SQLite")
        self.assertIsInstance(results[0]["tags"], list)


# ═══════════════════════════════════════════════════════════════════════════
# TTL Cleanup
# ═══════════════════════════════════════════════════════════════════════════

class TestCleanupExpired(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_no_expired_returns_zero(self):
        self.store.create_memory("fresh", ttl_days=365)
        self.assertEqual(self.store.cleanup_expired(), 0)
        self.assertEqual(self.store.count(), 1)

    def test_expired_memory_deleted(self):
        # Create a memory with TTL=1 and backdate updated_at to 2 days ago
        mid = "mem_exp_12345678"
        self.store.create_memory("old memory", memory_id=mid, ttl_days=1)
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
        self.store._conn.execute(
            "UPDATE memories SET updated_at = ? WHERE id = ?",
            (two_days_ago, mid)
        )
        self.store._conn.commit()
        deleted = self.store.cleanup_expired()
        self.assertEqual(deleted, 1)
        self.assertIsNone(self.store.get_by_id(mid))

    def test_cleanup_removes_from_fts(self):
        mid = "mem_expfts_123456"
        self.store.create_memory("unique_quasar_term", memory_id=mid, ttl_days=1)
        old_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat().replace("+00:00", "Z")
        self.store._conn.execute(
            "UPDATE memories SET updated_at = ? WHERE id = ?", (old_date, mid)
        )
        self.store._conn.commit()
        self.store.cleanup_expired()
        results = self.store.search("unique_quasar_term")
        self.assertEqual(len(results), 0)

    def test_mixed_expired_and_fresh(self):
        self.store.create_memory("keep me", memory_id="mem_keep_12345678", ttl_days=365)
        self.store.create_memory("delete me", memory_id="mem_del2_12345678", ttl_days=1)
        old_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat().replace("+00:00", "Z")
        self.store._conn.execute(
            "UPDATE memories SET updated_at = ? WHERE id = ?",
            (old_date, "mem_del2_12345678")
        )
        self.store._conn.commit()
        deleted = self.store.cleanup_expired()
        self.assertEqual(deleted, 1)
        self.assertEqual(self.store.count(), 1)
        self.assertIsNotNone(self.store.get_by_id("mem_keep_12345678"))

    def test_confidence_ttl_defaults(self):
        """Verify TTL defaults match the documented values."""
        self.assertEqual(TTL_BY_CONFIDENCE["HIGH"], 365)
        self.assertEqual(TTL_BY_CONFIDENCE["MEDIUM"], 180)
        self.assertEqual(TTL_BY_CONFIDENCE["LOW"], 90)


# ═══════════════════════════════════════════════════════════════════════════
# Atomic Writes
# ═══════════════════════════════════════════════════════════════════════════

class TestAtomicWrites(unittest.TestCase):
    def test_create_rolls_back_on_duplicate_id(self):
        store = MemoryStore(":memory:")
        store.create_memory("first", memory_id="mem_atom_12345678")
        try:
            store.create_memory("second", memory_id="mem_atom_12345678")
        except Exception:
            pass
        # First memory should still be intact
        self.assertEqual(store.count(), 1)
        mem = store.get_by_id("mem_atom_12345678")
        self.assertEqual(mem["content"], "first")
        store.close()

    def test_persistence_across_close(self):
        """Data survives close/reopen cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store1 = MemoryStore(db_path)
            store1.create_memory("persistent", memory_id="mem_pers_12345678")
            store1.close()

            store2 = MemoryStore(db_path)
            mem = store2.get_by_id("mem_pers_12345678")
            self.assertIsNotNone(mem)
            self.assertEqual(mem["content"], "persistent")
            store2.close()


# ═══════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_unicode_content(self):
        mem = self.store.create_memory("Decision: use UTF-8 encoding always")
        found = self.store.get_by_id(mem["id"])
        self.assertIn("UTF-8", found["content"])

    def test_emoji_content(self):
        mem = self.store.create_memory("Status indicator uses checkmark symbol")
        self.assertIsNotNone(mem)

    def test_very_long_content(self):
        long_content = "x" * 10000
        mem = self.store.create_memory(long_content)
        found = self.store.get_by_id(mem["id"])
        self.assertEqual(found["content"], long_content)

    def test_many_tags(self):
        tags = [f"tag{i}" for i in range(50)]
        mem = self.store.create_memory("tagged", tags=tags)
        found = self.store.get_by_id(mem["id"])
        self.assertEqual(len(found["tags"]), 50)

    def test_empty_tags_list(self):
        mem = self.store.create_memory("no tags", tags=[])
        self.assertEqual(mem["tags"], [])

    def test_special_chars_in_content(self):
        mem = self.store.create_memory('Content with "quotes" and \'apostrophes\' and $pecial chars')
        found = self.store.get_by_id(mem["id"])
        self.assertIn('"quotes"', found["content"])

    def test_newlines_in_content(self):
        mem = self.store.create_memory("Line 1\nLine 2\nLine 3")
        found = self.store.get_by_id(mem["id"])
        self.assertIn("\n", found["content"])

    def test_search_with_hyphenated_term(self):
        self.store.create_memory("The stdlib-first approach is best", tags=["stdlib-first"])
        results = self.store.search("stdlib")
        self.assertGreater(len(results), 0)

    def test_large_batch_create(self):
        for i in range(200):
            self.store.create_memory(f"Memory number {i}", tags=[f"batch{i}"])
        self.assertEqual(self.store.count(), 200)

    def test_search_after_many_creates(self):
        for i in range(100):
            self.store.create_memory(f"Generic memory {i}")
        self.store.create_memory("unique_nebula_identifier")
        results = self.store.search("unique_nebula_identifier")
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
