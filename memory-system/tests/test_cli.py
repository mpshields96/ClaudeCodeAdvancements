"""
Tests for MEM-5: CLI memory viewer.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(
    mem_id: str = "mem_20260219_000000_aaa",
    mtype: str = "decision",
    content: str = "Test memory content",
    confidence: str = "HIGH",
    tags: list[str] | None = None,
    days_old: int = 10,
) -> dict:
    from datetime import datetime, timezone, timedelta
    dt = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    return {
        "id": mem_id,
        "type": mtype,
        "content": content,
        "project": "testproject",
        "tags": tags or ["test"],
        "created_at": dt,
        "last_used": dt,
        "confidence": confidence,
        "source": "explicit",
    }


def _write_store(memory_dir: Path, slug: str, memories: list[dict]) -> Path:
    from datetime import datetime, timezone
    memory_dir.mkdir(parents=True, exist_ok=True)
    mfile = memory_dir / f"{slug}.json"
    store = {
        "project": slug,
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "memories": memories,
    }
    mfile.write_text(json.dumps(store, indent=2))
    return mfile


# ---------------------------------------------------------------------------
# Unit tests: pure functions
# ---------------------------------------------------------------------------

class TestProjectSlug(unittest.TestCase):

    def test_lowercases_name(self):
        self.assertEqual(cli._project_slug("/Users/foo/Projects/MyApp"), "myapp")

    def test_replaces_spaces_with_hyphens(self):
        self.assertEqual(cli._project_slug("/Users/foo/My Project"), "my-project")

    def test_handles_special_chars(self):
        self.assertEqual(cli._project_slug("/Users/foo/app_v2!"), "app-v2")

    def test_uses_last_component(self):
        self.assertEqual(cli._project_slug("/a/b/c/d/e"), "e")


class TestIsExpired(unittest.TestCase):

    def test_not_expired_for_recent_memory(self):
        mem = _make_memory(confidence="HIGH", days_old=10)
        self.assertFalse(cli._is_expired(mem))

    def test_expired_for_old_high_confidence(self):
        mem = _make_memory(confidence="HIGH", days_old=400)
        self.assertTrue(cli._is_expired(mem))

    def test_expired_for_old_medium_confidence(self):
        mem = _make_memory(confidence="MEDIUM", days_old=200)
        self.assertTrue(cli._is_expired(mem))

    def test_not_expired_for_medium_within_180(self):
        mem = _make_memory(confidence="MEDIUM", days_old=90)
        self.assertFalse(cli._is_expired(mem))

    def test_expired_for_old_low_confidence(self):
        mem = _make_memory(confidence="LOW", days_old=100)
        self.assertTrue(cli._is_expired(mem))

    def test_handles_missing_last_used(self):
        mem = {"id": "x", "confidence": "HIGH", "content": "test"}
        # Should not raise, should return False (assume not expired if no date)
        self.assertFalse(cli._is_expired(mem))


class TestLoadStore(unittest.TestCase):

    def test_loads_existing_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            slug = "testproject"
            mems = [_make_memory()]
            _write_store(mdir, slug, mems)
            store = cli._load_store(mdir / f"{slug}.json")
            self.assertEqual(len(store["memories"]), 1)

    def test_returns_empty_store_for_missing_file(self):
        store = cli._load_store(Path("/tmp/no_such_memory_cli_test.json"))
        self.assertEqual(store["memories"], [])


class TestAllStores(unittest.TestCase):

    def test_returns_all_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "proj-a", [_make_memory("mem1")])
            _write_store(mdir, "proj-b", [_make_memory("mem2")])
            _write_store(mdir, "_global", [])
            stores = cli._all_stores(mdir)
            slugs = [s for s, _ in stores]
            self.assertIn("proj-a", slugs)
            self.assertIn("proj-b", slugs)
            self.assertIn("_global", slugs)

    def test_returns_empty_for_nonexistent_dir(self):
        stores = cli._all_stores(Path("/tmp/no_such_memory_dir_cli"))
        self.assertEqual(stores, [])


# ---------------------------------------------------------------------------
# Command tests (via main() with captured output)
# ---------------------------------------------------------------------------

def _run(args_list: list[str], memory_dir: Path) -> tuple[int, str]:
    """Run CLI with given args, return (exit_code, stdout_output)."""
    out = StringIO()
    with patch("sys.stdout", out):
        with patch("sys.argv", ["cli.py"] + ["--no-color", "--dir", str(memory_dir)] + args_list):
            try:
                result = cli.main()
            except SystemExit as e:
                result = e.code or 0
    return result, out.getvalue()


class TestListCommand(unittest.TestCase):

    def test_lists_memories_for_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "myapp", [_make_memory(content="Use stdlib first")])
            code, out = _run(["list", "--project", "myapp"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("Use stdlib first", out)

    def test_empty_store_shows_no_memories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "emptyproject", [])
            code, out = _run(["list", "--project", "emptyproject"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("no memories", out)

    def test_list_all_shows_all_projects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "proj-a", [_make_memory("m1", content="Alpha memory")])
            _write_store(mdir, "proj-b", [_make_memory("m2", content="Beta memory")])
            code, out = _run(["list", "--all"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("Alpha memory", out)
            self.assertIn("Beta memory", out)

    def test_filter_by_confidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "proj", [
                _make_memory("m1", confidence="HIGH", content="High confidence memory"),
                _make_memory("m2", confidence="LOW", content="Low confidence memory"),
            ])
            code, out = _run(["list", "--project", "proj", "--confidence", "HIGH"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("High confidence memory", out)
            self.assertNotIn("Low confidence memory", out)

    def test_list_global(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "_global", [_make_memory(content="Global preference")])
            code, out = _run(["list", "--global"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("Global preference", out)


class TestSearchCommand(unittest.TestCase):

    def test_finds_by_keyword(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "proj", [
                _make_memory("m1", content="Use SQLite for storage"),
                _make_memory("m2", content="Use Python stdlib"),
            ])
            code, out = _run(["search", "SQLite", "--project", "proj"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("SQLite", out)
            self.assertNotIn("Use Python stdlib", out)

    def test_finds_by_tag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "proj", [
                _make_memory("m1", tags=["database", "storage"], content="DB memory"),
                _make_memory("m2", tags=["python"], content="Python memory"),
            ])
            code, out = _run(["search", "database", "--project", "proj"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("DB memory", out)
            self.assertNotIn("Python memory", out)

    def test_no_results_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "proj", [_make_memory("m1", content="Unrelated content")])
            code, out = _run(["search", "zzz_no_match", "--project", "proj"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("No memories match", out)


class TestDeleteCommand(unittest.TestCase):

    def test_deletes_existing_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            mem = _make_memory("mem_target_001", content="To be deleted")
            _write_store(mdir, "proj", [mem])
            code, out = _run(["delete", "mem_target_001", "--project", "proj"], mdir)
            self.assertEqual(code, 0)
            # Verify it's gone
            store = cli._load_store(mdir / "proj.json")
            ids = [m["id"] for m in store["memories"]]
            self.assertNotIn("mem_target_001", ids)

    def test_returns_error_for_missing_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "proj", [])
            code, out = _run(["delete", "mem_nonexistent", "--project", "proj"], mdir)
            self.assertEqual(code, 1)


class TestPurgeCommand(unittest.TestCase):

    def test_purges_expired_memories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            fresh = _make_memory("m_fresh", confidence="HIGH", days_old=10)
            stale = _make_memory("m_stale", confidence="LOW", days_old=200)
            _write_store(mdir, "proj", [fresh, stale])
            code, out = _run(["purge", "--project", "proj"], mdir)
            self.assertEqual(code, 0)
            store = cli._load_store(mdir / "proj.json")
            ids = [m["id"] for m in store["memories"]]
            self.assertIn("m_fresh", ids)
            self.assertNotIn("m_stale", ids)

    def test_no_expired_shows_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            fresh = _make_memory("m_fresh", confidence="HIGH", days_old=1)
            _write_store(mdir, "proj", [fresh])
            code, out = _run(["purge", "--project", "proj"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("No expired", out)


class TestStatsCommand(unittest.TestCase):

    def test_shows_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            _write_store(mdir, "proj", [
                _make_memory("m1", confidence="HIGH"),
                _make_memory("m2", confidence="MEDIUM"),
                _make_memory("m3", confidence="LOW"),
            ])
            code, out = _run(["stats"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("Statistics", out)

    def test_empty_dir_shows_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            code, out = _run(["stats"], mdir)
            self.assertEqual(code, 0)
            self.assertIn("No memory files", out)


if __name__ == "__main__":
    unittest.main()
