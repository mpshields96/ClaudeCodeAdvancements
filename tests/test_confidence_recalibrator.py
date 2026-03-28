"""
test_confidence_recalibrator.py — Tests for confidence_recalibrator.py apply functionality.

MT-49 Phase 4: Bayesian decay/boost applied to principle scores.
Tests the apply subcommand that writes recalibrated scores back to principles.jsonl.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "self-learning"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_principle(pid, text, score, last_used_session, usage_count=3, success_count=2,
                    pruned=False, domain="general"):
    return {
        "id": pid,
        "text": text,
        "source_domain": domain,
        "applicable_domains": [domain, "general"],
        "score": score,
        "success_count": success_count,
        "usage_count": usage_count,
        "created_session": 100,
        "last_used_session": last_used_session,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "pruned": pruned,
        "source_context": "test",
    }


def _write_principles(path, principles):
    with open(path, "w") as f:
        for p in principles:
            f.write(json.dumps(p) + "\n")


def _load_latest_principles(path):
    """Load principles dict, latest version wins."""
    principles = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                p = json.loads(line)
                principles[p["id"]] = p
    return principles


class TestStalenessFactorEdgeCases(unittest.TestCase):
    """Edge cases for staleness_factor function."""

    def test_zero_gap_returns_one(self):
        from confidence_recalibrator import staleness_factor
        self.assertAlmostEqual(staleness_factor(100, 100), 1.0)

    def test_large_gap_floored(self):
        from confidence_recalibrator import staleness_factor, STALENESS_FLOOR
        # Very large gap should be floored
        result = staleness_factor(0, 1000)
        self.assertEqual(result, STALENESS_FLOOR)

    def test_moderate_gap_decays(self):
        from confidence_recalibrator import staleness_factor
        # 50-session gap: exp(-0.01 * 50) = exp(-0.5) ~= 0.607
        result = staleness_factor(100, 150)
        self.assertGreater(result, 0.5)
        self.assertLess(result, 0.7)

    def test_future_session_clipped_to_one(self):
        from confidence_recalibrator import staleness_factor
        # last_used > current should not give > 1.0
        result = staleness_factor(200, 100)
        self.assertLessEqual(result, 1.0)


class TestApplyRecalibration(unittest.TestCase):
    """Tests for apply_recalibration() writing scores back to principles.jsonl."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.checkpoint_path = os.path.join(self.tmpdir, "recal_checkpoint.json")

    def _write_test_principles(self):
        principles = [
            _make_principle("prin_aaa", "Always test before shipping", 0.8,
                            last_used_session=100),
            _make_principle("prin_bbb", "Commit after each task completes", 0.7,
                            last_used_session=150),
            _make_principle("prin_ccc", "Read files before editing", 0.9,
                            last_used_session=180),
            _make_principle("prin_ddd", "Pruned principle", 0.5,
                            last_used_session=100, pruned=True),
        ]
        _write_principles(self.principles_path, principles)

    def test_apply_writes_decayed_scores(self):
        """Stale principles get lower scores written back."""
        from confidence_recalibrator import apply_recalibration
        self._write_test_principles()

        result = apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path
        )

        self.assertGreater(result["applied"], 0)
        loaded = _load_latest_principles(self.principles_path)
        # prin_aaa was last used at 100, gap=128 — should decay
        self.assertLess(loaded["prin_aaa"]["score"], 0.8)

    def test_apply_skips_pruned_principles(self):
        """Pruned principles are not modified."""
        from confidence_recalibrator import apply_recalibration
        self._write_test_principles()

        apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path
        )

        loaded = _load_latest_principles(self.principles_path)
        # Pruned principle score unchanged at 0.5
        self.assertEqual(loaded["prin_ddd"]["score"], 0.5)
        self.assertTrue(loaded["prin_ddd"]["pruned"])

    def test_apply_writes_checkpoint(self):
        """Checkpoint file written after apply."""
        from confidence_recalibrator import apply_recalibration
        self._write_test_principles()

        apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path
        )

        self.assertTrue(os.path.exists(self.checkpoint_path))
        with open(self.checkpoint_path) as f:
            cp = json.load(f)
        self.assertEqual(cp["last_recalibrated_session"], 228)

    def test_apply_respects_min_gap_checkpoint(self):
        """Second apply within min_gap sessions is skipped."""
        from confidence_recalibrator import apply_recalibration
        self._write_test_principles()

        # Write checkpoint saying we recalibrated at session 225 (3 sessions ago)
        with open(self.checkpoint_path, "w") as f:
            json.dump({"last_recalibrated_session": 225}, f)

        result = apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path,
            min_gap=10
        )

        self.assertEqual(result["applied"], 0)
        self.assertIn("recently", result.get("reason", "").lower())

    def test_apply_runs_after_min_gap_passes(self):
        """Apply runs when min_gap sessions have passed since last recalibration."""
        from confidence_recalibrator import apply_recalibration
        self._write_test_principles()

        # Checkpoint at session 210 — gap is 18 > min_gap=10
        with open(self.checkpoint_path, "w") as f:
            json.dump({"last_recalibrated_session": 210}, f)

        result = apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path,
            min_gap=10
        )

        self.assertGreater(result["applied"], 0)

    def test_apply_only_changes_significantly_decayed(self):
        """Only principles with >10% score change get updated."""
        from confidence_recalibrator import apply_recalibration, DECAY_THRESHOLD
        # Principle very recently used (1 session ago) — minimal decay
        principles = [
            _make_principle("prin_fresh", "Fresh principle", 0.8, last_used_session=227),
            _make_principle("prin_stale", "Stale principle", 0.8, last_used_session=100),
        ]
        _write_principles(self.principles_path, principles)

        result = apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path
        )

        loaded = _load_latest_principles(self.principles_path)
        # Fresh principle should NOT be decayed (gap=1)
        self.assertAlmostEqual(loaded["prin_fresh"]["score"], 0.8, places=1)
        # Stale principle should be decayed (gap=128)
        self.assertLess(loaded["prin_stale"]["score"], 0.8 - DECAY_THRESHOLD)

    def test_apply_returns_summary_dict(self):
        """apply_recalibration returns dict with applied/skipped keys."""
        from confidence_recalibrator import apply_recalibration
        self._write_test_principles()

        result = apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path
        )

        self.assertIn("applied", result)
        self.assertIn("skipped", result)
        self.assertIsInstance(result["applied"], int)
        self.assertIsInstance(result["skipped"], int)

    def test_apply_preserves_other_fields(self):
        """Apply only updates score and updated_at, preserves all other fields."""
        from confidence_recalibrator import apply_recalibration
        self._write_test_principles()

        apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path
        )

        loaded = _load_latest_principles(self.principles_path)
        p = loaded["prin_aaa"]
        self.assertEqual(p["text"], "Always test before shipping")
        self.assertEqual(p["source_domain"], "general")
        self.assertEqual(p["success_count"], 2)
        self.assertEqual(p["usage_count"], 3)
        self.assertEqual(p["last_used_session"], 100)
        self.assertFalse(p["pruned"])


class TestCLIApplySubcommand(unittest.TestCase):
    """Test CLI interface for apply subcommand."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.checkpoint_path = os.path.join(self.tmpdir, "recal_checkpoint.json")
        principles = [
            _make_principle("prin_test1", "Test principle 1", 0.8, last_used_session=100),
            _make_principle("prin_test2", "Test principle 2", 0.6, last_used_session=150),
        ]
        _write_principles(self.principles_path, principles)

    def test_apply_subcommand_exists(self):
        """CLI has apply subcommand."""
        import subprocess
        result = subprocess.run(
            ["python3",
             os.path.join(os.path.dirname(__file__), "..", "self-learning",
                          "confidence_recalibrator.py"),
             "--help"],
            capture_output=True, text=True
        )
        self.assertIn("apply", result.stdout)

    def test_dry_run_does_not_write(self):
        """--dry-run flag does not modify principles.jsonl."""
        from confidence_recalibrator import apply_recalibration
        # Get original content
        with open(self.principles_path) as f:
            original = f.read()

        apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path,
            dry_run=True
        )

        with open(self.principles_path) as f:
            after = f.read()
        self.assertEqual(original, after)

    def test_dry_run_still_returns_summary(self):
        """--dry-run returns what would be applied."""
        from confidence_recalibrator import apply_recalibration

        result = apply_recalibration(
            self.principles_path, current_session=228,
            checkpoint_path=self.checkpoint_path,
            dry_run=True
        )

        self.assertIn("applied", result)
        self.assertGreater(result["applied"], 0)


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
