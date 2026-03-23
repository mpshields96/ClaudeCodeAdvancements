"""Tests for MT-0 deployment verifier — validates self-learning integration in Kalshi bot.

The verifier checks whether the polymarket-bot has properly integrated CCA's
self-learning system by looking for expected files, journal entries, and
configuration.

This is CCA-side tooling that Kalshi chat runs after deployment to verify
everything is wired correctly.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestDeploymentVerifier(unittest.TestCase):
    """Test DeploymentVerifier initialization and checks."""

    def setUp(self):
        from deployment_verifier import DeploymentVerifier
        self.tmpdir = tempfile.mkdtemp()
        self.verifier = DeploymentVerifier(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init(self):
        from deployment_verifier import DeploymentVerifier
        v = DeploymentVerifier("/tmp/test")
        self.assertEqual(v.bot_root, "/tmp/test")

    def test_check_trading_journal_file_missing(self):
        """Reports FAIL when trading_journal.py doesn't exist."""
        result = self.verifier.check_trading_journal()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("not found", result["message"])

    def test_check_trading_journal_file_exists(self):
        """Reports PASS when trading_journal.py exists with log_event."""
        sl_dir = os.path.join(self.tmpdir, "src", "self_learning")
        os.makedirs(sl_dir, exist_ok=True)
        with open(os.path.join(sl_dir, "trading_journal.py"), "w") as f:
            f.write("def log_event(event_type, metrics):\n    pass\n")
        result = self.verifier.check_trading_journal()
        self.assertEqual(result["status"], "PASS")

    def test_check_trading_journal_missing_log_event(self):
        """Reports WARN when file exists but log_event not found."""
        sl_dir = os.path.join(self.tmpdir, "src", "self_learning")
        os.makedirs(sl_dir, exist_ok=True)
        with open(os.path.join(sl_dir, "trading_journal.py"), "w") as f:
            f.write("# empty\n")
        result = self.verifier.check_trading_journal()
        self.assertEqual(result["status"], "WARN")
        self.assertIn("log_event", result["message"])

    def test_check_research_tracker_missing(self):
        result = self.verifier.check_research_tracker()
        self.assertEqual(result["status"], "FAIL")

    def test_check_research_tracker_exists(self):
        sl_dir = os.path.join(self.tmpdir, "src", "self_learning")
        os.makedirs(sl_dir, exist_ok=True)
        with open(os.path.join(sl_dir, "research_tracker.py"), "w") as f:
            f.write("def log_research_outcome(item_id, action):\n    pass\n")
        result = self.verifier.check_research_tracker()
        self.assertEqual(result["status"], "PASS")

    def test_check_journal_data_no_file(self):
        """Reports FAIL when no journal JSONL exists."""
        result = self.verifier.check_journal_data()
        self.assertEqual(result["status"], "FAIL")

    def test_check_journal_data_empty(self):
        """Reports WARN when journal exists but is empty."""
        data_dir = os.path.join(self.tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "trading_journal.jsonl"), "w") as f:
            pass  # empty
        result = self.verifier.check_journal_data()
        self.assertEqual(result["status"], "WARN")
        self.assertIn("empty", result["message"])

    def test_check_journal_data_valid(self):
        """Reports PASS when journal has valid entries."""
        data_dir = os.path.join(self.tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        entries = [
            {"event_type": "bet_outcome", "domain": "trading", "metrics": {"result": "win"}},
            {"event_type": "bet_placed", "domain": "trading", "metrics": {"strategy": "sniper"}},
        ]
        with open(os.path.join(data_dir, "trading_journal.jsonl"), "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = self.verifier.check_journal_data()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["entry_count"], 2)

    def test_check_live_wiring_not_wired(self):
        """Reports FAIL when live.py doesn't reference trading_journal."""
        exec_dir = os.path.join(self.tmpdir, "src", "execution")
        os.makedirs(exec_dir, exist_ok=True)
        with open(os.path.join(exec_dir, "live.py"), "w") as f:
            f.write("# no self-learning wiring\ndef execute_bet():\n    pass\n")
        result = self.verifier.check_live_wiring()
        self.assertEqual(result["status"], "FAIL")

    def test_check_live_wiring_wired(self):
        """Reports PASS when live.py imports/references trading_journal."""
        exec_dir = os.path.join(self.tmpdir, "src", "execution")
        os.makedirs(exec_dir, exist_ok=True)
        with open(os.path.join(exec_dir, "live.py"), "w") as f:
            f.write("from self_learning.trading_journal import log_event\ndef execute_bet():\n    log_event('bet_placed', {})\n")
        result = self.verifier.check_live_wiring()
        self.assertEqual(result["status"], "PASS")

    def test_check_live_wiring_no_file(self):
        """Reports SKIP when live.py doesn't exist."""
        result = self.verifier.check_live_wiring()
        self.assertEqual(result["status"], "SKIP")

    def test_run_all_returns_summary(self):
        """run_all returns structured summary with all checks."""
        summary = self.verifier.run_all()
        self.assertIn("checks", summary)
        self.assertIsInstance(summary["checks"], list)
        self.assertGreater(len(summary["checks"]), 0)
        self.assertIn("overall", summary)
        self.assertIn(summary["overall"], ["PASS", "PARTIAL", "FAIL"])

    def test_run_all_overall_fail_when_nothing_deployed(self):
        """Empty bot root should produce FAIL overall."""
        summary = self.verifier.run_all()
        self.assertEqual(summary["overall"], "FAIL")

    def test_run_all_overall_pass_when_fully_deployed(self):
        """Fully deployed bot should produce PASS overall."""
        # Create all expected files
        sl_dir = os.path.join(self.tmpdir, "src", "self_learning")
        os.makedirs(sl_dir, exist_ok=True)
        with open(os.path.join(sl_dir, "trading_journal.py"), "w") as f:
            f.write("def log_event(event_type, metrics):\n    pass\n")
        with open(os.path.join(sl_dir, "research_tracker.py"), "w") as f:
            f.write("def log_research_outcome(item_id, action):\n    pass\n")

        exec_dir = os.path.join(self.tmpdir, "src", "execution")
        os.makedirs(exec_dir, exist_ok=True)
        with open(os.path.join(exec_dir, "live.py"), "w") as f:
            f.write("from self_learning.trading_journal import log_event\n")

        data_dir = os.path.join(self.tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "trading_journal.jsonl"), "w") as f:
            f.write(json.dumps({"event_type": "bet_outcome", "domain": "trading", "metrics": {}}) + "\n")

        summary = self.verifier.run_all()
        self.assertEqual(summary["overall"], "PASS")

    def test_run_all_partial_when_some_deployed(self):
        """Partial deployment should produce PARTIAL overall."""
        sl_dir = os.path.join(self.tmpdir, "src", "self_learning")
        os.makedirs(sl_dir, exist_ok=True)
        with open(os.path.join(sl_dir, "trading_journal.py"), "w") as f:
            f.write("def log_event(event_type, metrics):\n    pass\n")
        summary = self.verifier.run_all()
        self.assertEqual(summary["overall"], "PARTIAL")

    def test_format_report(self):
        """format_report produces human-readable text."""
        summary = self.verifier.run_all()
        report = self.verifier.format_report(summary)
        self.assertIn("MT-0", report)
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 50)


class TestVerifierSchemaValidation(unittest.TestCase):
    """Test journal entry schema validation."""

    def setUp(self):
        from deployment_verifier import DeploymentVerifier
        self.tmpdir = tempfile.mkdtemp()
        self.verifier = DeploymentVerifier(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_valid_entry(self):
        entry = {
            "timestamp": "2026-03-23T10:00:00Z",
            "event_type": "bet_outcome",
            "domain": "trading",
            "metrics": {"result": "win", "pnl_cents": 35},
        }
        self.assertTrue(self.verifier.validate_entry(entry))

    def test_missing_event_type(self):
        entry = {"domain": "trading", "metrics": {}}
        self.assertFalse(self.verifier.validate_entry(entry))

    def test_missing_domain(self):
        entry = {"event_type": "bet_outcome", "metrics": {}}
        self.assertFalse(self.verifier.validate_entry(entry))

    def test_missing_metrics(self):
        entry = {"event_type": "bet_outcome", "domain": "trading"}
        self.assertFalse(self.verifier.validate_entry(entry))

    def test_invalid_event_type(self):
        entry = {"event_type": "invalid_type", "domain": "trading", "metrics": {}}
        self.assertFalse(self.verifier.validate_entry(entry))

    def test_all_valid_event_types(self):
        from deployment_verifier import VALID_EVENT_TYPES
        for evt in VALID_EVENT_TYPES:
            entry = {"event_type": evt, "domain": "trading", "metrics": {}}
            self.assertTrue(self.verifier.validate_entry(entry), f"Failed for {evt}")

    def test_check_journal_data_reports_invalid_entries(self):
        """Journal with invalid entries should report count of invalid ones."""
        data_dir = os.path.join(self.tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        entries = [
            {"event_type": "bet_outcome", "domain": "trading", "metrics": {"result": "win"}},
            {"event_type": "bogus", "domain": "trading", "metrics": {}},  # invalid
            {"event_type": "bet_placed", "domain": "trading", "metrics": {}},
        ]
        with open(os.path.join(data_dir, "trading_journal.jsonl"), "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = self.verifier.check_journal_data()
        self.assertEqual(result["status"], "WARN")
        self.assertEqual(result["invalid_count"], 1)


if __name__ == "__main__":
    unittest.main()
