#!/usr/bin/env python3
"""Tests for self-learning/meta_tracker.py — MT-49 Phase 1: Meta-Learning Tracker."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "self-learning"))


def _make_principle(pid, text, domain, usage=0, success=0, created_session=100,
                    last_used=0, pruned=False):
    """Helper to create a principle dict for test JSONL."""
    return {
        "id": pid,
        "text": text,
        "source_domain": domain,
        "applicable_domains": [domain],
        "success_count": success,
        "usage_count": usage,
        "created_session": created_session,
        "last_used_session": last_used,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
        "pruned": pruned,
        "source_context": "test",
    }


class TestMetaTrackerHealth(unittest.TestCase):
    """Test the health scoring logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.snapshots_path = os.path.join(self.tmpdir, "meta_snapshots.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_principles(self, principles):
        with open(self.principles_path, "w") as f:
            for p in principles:
                f.write(json.dumps(p) + "\n")

    def test_empty_registry(self):
        """Empty registry should still produce a valid health report."""
        from meta_tracker import MetaTracker
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        health = mt.health(current_session=200)
        self.assertIn("total", health)
        self.assertEqual(health["total"], 0)
        self.assertIn("health_score", health)
        self.assertGreaterEqual(health["health_score"], 0.0)
        self.assertLessEqual(health["health_score"], 1.0)

    def test_all_zombies(self):
        """Registry full of unused principles should have low health."""
        principles = [
            _make_principle(f"prin_{i:08x}", f"Zombie {i}", "general",
                            usage=0, success=0, created_session=100)
            for i in range(50)
        ]
        self._write_principles(principles)
        from meta_tracker import MetaTracker
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        health = mt.health(current_session=200)
        self.assertEqual(health["zombies"], 50)
        self.assertLess(health["health_score"], 0.3)

    def test_healthy_registry(self):
        """Registry with high usage and good scores should have high health."""
        principles = [
            _make_principle(f"prin_{i:08x}", f"Active {i}", "cca_operations",
                            usage=10, success=8, created_session=100, last_used=195)
            for i in range(20)
        ]
        self._write_principles(principles)
        from meta_tracker import MetaTracker
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        health = mt.health(current_session=200)
        self.assertEqual(health["zombies"], 0)
        self.assertGreater(health["health_score"], 0.7)

    def test_mixed_registry(self):
        """Mix of active and zombie principles."""
        principles = [
            _make_principle("prin_active01", "Active principle", "cca_operations",
                            usage=15, success=12, created_session=100, last_used=198),
            _make_principle("prin_zombie01", "Zombie principle", "general",
                            usage=0, success=0, created_session=100),
            _make_principle("prin_zombie02", "Another zombie", "general",
                            usage=0, success=0, created_session=100),
        ]
        self._write_principles(principles)
        from meta_tracker import MetaTracker
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        health = mt.health(current_session=200)
        self.assertEqual(health["total"], 3)
        self.assertEqual(health["zombies"], 2)
        self.assertEqual(health["active"], 1)


class TestMetaTrackerZombieDetection(unittest.TestCase):
    """Test zombie principle identification."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.snapshots_path = os.path.join(self.tmpdir, "meta_snapshots.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_principles(self, principles):
        with open(self.principles_path, "w") as f:
            for p in principles:
                f.write(json.dumps(p) + "\n")

    def test_zombie_threshold(self):
        """Principles unused for 30+ sessions after creation are zombies."""
        from meta_tracker import MetaTracker
        principles = [
            # Created at session 100, never used, now session 200 = 100 sessions stale
            _make_principle("prin_old", "Old unused", "general",
                            usage=0, created_session=100),
            # Created at session 195, never used, now session 200 = 5 sessions = too new
            _make_principle("prin_new", "New unused", "general",
                            usage=0, created_session=195),
        ]
        self._write_principles(principles)
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        zombies = mt.list_zombies(current_session=200)
        zombie_ids = [z["id"] for z in zombies]
        self.assertIn("prin_old", zombie_ids)
        self.assertNotIn("prin_new", zombie_ids)

    def test_used_principle_not_zombie(self):
        """A principle with usage > 0 is never a zombie regardless of age."""
        from meta_tracker import MetaTracker
        principles = [
            _make_principle("prin_used", "Used once", "general",
                            usage=1, success=1, created_session=100, last_used=150),
        ]
        self._write_principles(principles)
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        zombies = mt.list_zombies(current_session=200)
        self.assertEqual(len(zombies), 0)


class TestMetaTrackerSnapshot(unittest.TestCase):
    """Test snapshot recording for trend tracking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.snapshots_path = os.path.join(self.tmpdir, "meta_snapshots.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_principles(self, principles):
        with open(self.principles_path, "w") as f:
            for p in principles:
                f.write(json.dumps(p) + "\n")

    def test_snapshot_creation(self):
        """Snapshot should be written to snapshots file."""
        from meta_tracker import MetaTracker
        principles = [
            _make_principle("prin_a", "Test A", "cca_operations",
                            usage=5, success=4, created_session=100, last_used=198),
        ]
        self._write_principles(principles)
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        mt.snapshot(session=200)
        self.assertTrue(os.path.exists(self.snapshots_path))
        with open(self.snapshots_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(len(lines), 1)
        snap = lines[0]
        self.assertEqual(snap["session"], 200)
        self.assertIn("total", snap)
        self.assertIn("health_score", snap)

    def test_trend_requires_multiple_snapshots(self):
        """Trend analysis needs at least 2 snapshots."""
        from meta_tracker import MetaTracker
        principles = [
            _make_principle("prin_a", "Test A", "cca_operations",
                            usage=5, success=4, created_session=100, last_used=198),
        ]
        self._write_principles(principles)
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        trend = mt.trend(last_n=5)
        self.assertEqual(trend["status"], "insufficient_data")

    def test_trend_with_data(self):
        """Trend should detect improving/declining/stable."""
        from meta_tracker import MetaTracker
        # Write some fake snapshots
        snapshots = [
            {"session": 195, "total": 100, "active": 10, "zombies": 80,
             "health_score": 0.3, "timestamp": "2026-03-25"},
            {"session": 200, "total": 100, "active": 20, "zombies": 60,
             "health_score": 0.5, "timestamp": "2026-03-27"},
        ]
        with open(self.snapshots_path, "w") as f:
            for s in snapshots:
                f.write(json.dumps(s) + "\n")
        self._write_principles([])  # Empty is fine for trend
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        trend = mt.trend(last_n=5)
        self.assertIn(trend["status"], ["improving", "declining", "stable"])
        self.assertEqual(trend["status"], "improving")


class TestMetaTrackerCLI(unittest.TestCase):
    """Test CLI subcommands."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.snapshots_path = os.path.join(self.tmpdir, "meta_snapshots.jsonl")
        # Write some test data
        with open(self.principles_path, "w") as f:
            f.write(json.dumps(_make_principle(
                "prin_test01", "Test principle", "cca_operations",
                usage=5, success=4, created_session=100, last_used=198
            )) + "\n")
            f.write(json.dumps(_make_principle(
                "prin_zombie1", "Zombie principle", "general",
                usage=0, success=0, created_session=50
            )) + "\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_health_command(self):
        """health subcommand should produce output."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "self-learning/meta_tracker.py",
             "--principles-path", self.principles_path,
             "--snapshots-path", self.snapshots_path,
             "--session", "200", "health"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("total", result.stdout.lower())

    def test_zombies_command(self):
        """zombies subcommand should list zombie principles."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "self-learning/meta_tracker.py",
             "--principles-path", self.principles_path,
             "--snapshots-path", self.snapshots_path,
             "--session", "200", "zombies"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("zombie", result.stdout.lower())

    def test_snapshot_command(self):
        """snapshot subcommand should create a snapshot file."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "self-learning/meta_tracker.py",
             "--principles-path", self.principles_path,
             "--snapshots-path", self.snapshots_path,
             "--session", "200", "snapshot"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertTrue(os.path.exists(self.snapshots_path))


class TestMetaTrackerPruning(unittest.TestCase):
    """Test zombie principle pruning."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.snapshots_path = os.path.join(self.tmpdir, "meta_snapshots.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_principles(self, principles):
        with open(self.principles_path, "w") as f:
            for p in principles:
                f.write(json.dumps(p) + "\n")

    def test_dry_run_doesnt_modify(self):
        """Dry run should not modify the principles file."""
        from meta_tracker import MetaTracker
        principles = [
            _make_principle("prin_old", "Old zombie", "general",
                            usage=0, created_session=100),
        ]
        self._write_principles(principles)
        original_size = os.path.getsize(self.principles_path)
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        targets = mt.prune_zombies(current_session=200, min_stale_sessions=50, dry_run=True)
        self.assertEqual(len(targets), 1)
        self.assertEqual(os.path.getsize(self.principles_path), original_size)

    def test_actual_prune_marks_pruned(self):
        """Actual prune should append pruned=True entries."""
        from meta_tracker import MetaTracker
        principles = [
            _make_principle("prin_old", "Old zombie", "general",
                            usage=0, created_session=100),
            _make_principle("prin_active", "Active one", "cca_operations",
                            usage=5, success=4, created_session=100, last_used=190),
        ]
        self._write_principles(principles)
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        pruned = mt.prune_zombies(current_session=200, min_stale_sessions=50, dry_run=False)
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["id"], "prin_old")

        # Verify the pruned principle is no longer loaded (pruned=True filtered out)
        remaining = mt._principles()
        self.assertNotIn("prin_old", remaining)
        self.assertIn("prin_active", remaining)

    def test_respects_min_stale_sessions(self):
        """Only prune principles older than min_stale_sessions."""
        from meta_tracker import MetaTracker
        principles = [
            _make_principle("prin_40s", "40 sessions stale", "general",
                            usage=0, created_session=160),
            _make_principle("prin_80s", "80 sessions stale", "general",
                            usage=0, created_session=120),
        ]
        self._write_principles(principles)
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        targets = mt.prune_zombies(current_session=200, min_stale_sessions=50, dry_run=True)
        target_ids = [t["id"] for t in targets]
        self.assertIn("prin_80s", target_ids)
        self.assertNotIn("prin_40s", target_ids)


class TestMetaTrackerBriefing(unittest.TestCase):
    """Test the init-briefing output format."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.snapshots_path = os.path.join(self.tmpdir, "meta_snapshots.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_principles(self, principles):
        with open(self.principles_path, "w") as f:
            for p in principles:
                f.write(json.dumps(p) + "\n")

    def test_briefing_format(self):
        """init-briefing should produce a compact, readable line."""
        from meta_tracker import MetaTracker
        principles = [
            _make_principle("prin_a", "Active", "cca_operations",
                            usage=10, success=8, created_session=100, last_used=198),
            _make_principle("prin_z", "Zombie", "general",
                            usage=0, success=0, created_session=50),
        ]
        self._write_principles(principles)
        mt = MetaTracker(self.principles_path, self.snapshots_path)
        briefing = mt.init_briefing(current_session=200)
        self.assertIsInstance(briefing, str)
        self.assertGreater(len(briefing), 10)
        # Should mention zombie count
        self.assertIn("1", briefing)  # 1 zombie


if __name__ == "__main__":
    unittest.main()
