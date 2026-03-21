#!/usr/bin/env python3
"""
End-to-end integration tests for autonomous_scanner.py — MT-9 Phase 3.

Tests the full autonomous scanning pipeline from CLI entry to structured output,
using mocked Reddit fetches (no real network calls). Validates:
  - CLI scan command produces valid JSON output
  - ScanReport has correct field structure
  - NEEDLE/MAYBE/HAY classification is applied
  - Safety gate is enforced (blocks at session limit)
  - Dedup against FINDINGS_LOG works correctly
  - No external fetches beyond reddit.com are required

Run: python3 tests/test_autonomous_scanner_e2e.py
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Add project root and reddit-intelligence to path
_PROJECT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT))
sys.path.insert(0, str(_PROJECT / "reddit-intelligence"))

from autonomous_scanner import (
    AutonomousScanner,
    ScanPrioritizer,
    SafetyGate,
    ScanReport,
    ScanResult,
    cli_main,
)


def _mock_posts(n=10, subreddit="ClaudeCode", needle_count=2):
    """Generate mock Reddit posts with realistic structure."""
    posts = []
    for i in range(n):
        triage_hint = "memory" if i < needle_count else "humor"
        posts.append({
            "id": f"post{i:04d}",
            "title": f"{'Claude Code memory persistence' if i < needle_count else 'Funny Claude meme'} #{i}",
            "author": f"user{i}",
            "score": 500 - i * 10,
            "upvote_ratio": 0.95,
            "num_comments": 50,
            "created_utc": 1773000000.0 + i * 3600,
            "flair": "Discussion" if i < needle_count else "Humor",
            "is_self": True,
            "url": f"https://www.reddit.com/r/{subreddit}/comments/post{i:04d}/",
            "permalink": f"https://www.reddit.com/r/{subreddit}/comments/post{i:04d}/",
            "selftext_length": 800 if i < needle_count else 0,
            "subreddit": subreddit,
        })
    return posts


class TestScanReportStructure(unittest.TestCase):
    """Verify ScanReport has correct fields and serialization."""

    def test_scan_report_fields(self):
        """ScanReport must have all required fields for downstream consumers."""
        report = ScanReport(
            subreddit="ClaudeCode",
            slug="claudecode",
            domain="claude",
            posts_fetched=15,
            posts_safe=12,
            posts_blocked=3,
            needles=4,
            maybes=1,
            hay=7,
            blocked_reasons=["scam_url"],
        )
        self.assertEqual(report.subreddit, "ClaudeCode")
        self.assertEqual(report.slug, "claudecode")
        self.assertEqual(report.domain, "claude")
        self.assertEqual(report.posts_fetched, 15)
        self.assertEqual(report.posts_safe, 12)
        self.assertEqual(report.posts_blocked, 3)
        self.assertEqual(report.needles, 4)
        self.assertEqual(report.maybes, 1)
        self.assertEqual(report.hay, 7)
        self.assertIsInstance(report.timestamp, str)
        # Timestamp must be ISO format
        datetime.fromisoformat(report.timestamp)

    def test_scan_report_to_dict_is_json_serializable(self):
        """ScanReport.to_dict() must produce JSON-serializable output."""
        report = ScanReport(
            subreddit="ClaudeCode", slug="claudecode", domain="claude",
            posts_fetched=10, posts_safe=8, posts_blocked=2,
            needles=3, maybes=1, hay=4,
        )
        d = report.to_dict()
        # Must not raise
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        self.assertEqual(loaded["subreddit"], "ClaudeCode")
        self.assertEqual(loaded["needles"], 3)

    def test_scan_report_summary_contains_key_counts(self):
        """ScanReport.summary() must include all critical counts."""
        report = ScanReport(
            subreddit="ClaudeCode", slug="claudecode", domain="claude",
            posts_fetched=15, posts_safe=12, posts_blocked=3,
            needles=4, maybes=0, hay=8,
        )
        summary = report.summary()
        self.assertIn("15", summary)   # posts_fetched
        self.assertIn("12", summary)   # posts_safe
        self.assertIn("3", summary)    # posts_blocked
        self.assertIn("4", summary)    # needles
        self.assertIn("NEEDLE", summary)


class TestScannerPipelineE2E(unittest.TestCase):
    """End-to-end tests: full scan pipeline with mocked Reddit fetch."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.state_path = os.path.join(self.tmpdir, "autonomous_state.json")
        self.kill_switch_path = os.path.join(self.tmpdir, "pause")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        # Write empty FINDINGS_LOG
        with open(self.findings_path, "w") as f:
            f.write("# FINDINGS LOG\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_scanner(self):
        return AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )

    def test_execute_scan_returns_scan_result(self):
        """execute_scan must return a ScanResult with report + classified posts."""
        mock_posts = _mock_posts(n=10, needle_count=3)
        scanner = self._make_scanner()

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
                fetch_limit=10,
                timeframe="month",
            )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, ScanResult)
        self.assertIsInstance(result.report, ScanReport)

    def test_scan_result_counts_match_report(self):
        """Needle/maybe/hay list lengths must match report counts."""
        mock_posts = _mock_posts(n=10, needle_count=3)
        scanner = self._make_scanner()

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
                fetch_limit=10,
                timeframe="month",
            )

        report = result.report
        self.assertEqual(report.needles, len(result.needles))
        self.assertEqual(report.maybes, len(result.maybes))
        self.assertEqual(report.hay, len(result.hay))

    def test_scan_result_posts_fetched_equals_mock_count(self):
        """posts_fetched must equal the number of posts returned by fetch."""
        n = 12
        mock_posts = _mock_posts(n=n)
        scanner = self._make_scanner()

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
                fetch_limit=n,
                timeframe="month",
            )

        self.assertEqual(result.report.posts_fetched, n)

    def test_dedup_removes_known_findings_log_posts(self):
        """Posts already in FINDINGS_LOG must be deduplicated."""
        # Write a known post ID into FINDINGS_LOG
        known_id = "post0000"
        with open(self.findings_path, "w") as f:
            f.write(f"# FINDINGS LOG\n[2026-03-20] [BUILD] https://www.reddit.com/r/ClaudeCode/comments/{known_id}/\n")

        mock_posts = _mock_posts(n=5, needle_count=2)
        scanner = self._make_scanner()

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
                fetch_limit=5,
                timeframe="month",
            )

        # Total post list should be one less (known_id deduped)
        total = len(result.needles) + len(result.maybes) + len(result.hay)
        # posts_fetched=5, known deduped=1, so total<=4
        self.assertLessEqual(total, 4)
        # Verify none of the classified posts have the known ID
        all_classified = result.needles + result.maybes + result.hay
        ids = [p["id"] for p in all_classified]
        self.assertNotIn(known_id, ids)

    def test_safety_gate_blocks_at_session_limit(self):
        """execute_scan must return None when session scan limit is exceeded."""
        scanner = self._make_scanner()
        # Exhaust the session scan limit
        scanner.safety_gate.scans_this_session = scanner.safety_gate.max_scans_per_session
        scanner.safety_gate.save_state()

        mock_posts = _mock_posts(n=5)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
            )

        self.assertIsNone(result)

    def test_kill_switch_blocks_scan(self):
        """execute_scan must return None when kill switch file exists."""
        # Create kill switch
        with open(self.kill_switch_path, "w") as f:
            f.write("pause")

        scanner = self._make_scanner()
        mock_posts = _mock_posts(n=5)

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
            )

        self.assertIsNone(result)

    def test_scan_records_in_safety_gate(self):
        """After scan, scan count must increment and slug must appear in subs_scanned."""
        mock_posts = _mock_posts(n=5)
        scanner = self._make_scanner()
        initial_count = scanner.safety_gate.scans_this_session

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
                fetch_limit=5,
                timeframe="month",
            )

        # Reload state from disk
        gate = SafetyGate(
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
        )
        self.assertEqual(gate.scans_this_session, initial_count + 1)
        self.assertIn("claudecode", gate.subs_scanned)

    def test_all_classified_posts_have_triage_field(self):
        """Every post in needles/maybes/hay must have a 'triage' field."""
        mock_posts = _mock_posts(n=8, needle_count=3)
        scanner = self._make_scanner()

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
                fetch_limit=8,
                timeframe="month",
            )

        all_posts = result.needles + result.maybes + result.hay
        for post in all_posts:
            self.assertIn("triage", post)
            self.assertIn(post["triage"], ("NEEDLE", "MAYBE", "HAY"))

    def test_needle_posts_are_in_needles_list(self):
        """Posts triaged as NEEDLE must appear in result.needles."""
        mock_posts = _mock_posts(n=5, needle_count=2)
        scanner = self._make_scanner()

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                subreddit="ClaudeCode",
                slug="claudecode",
                domain="claude",
                fetch_limit=5,
                timeframe="month",
            )

        for post in result.needles:
            self.assertEqual(post["triage"], "NEEDLE")
        for post in result.hay:
            self.assertEqual(post["triage"], "HAY")


class TestCLIScanCommandE2E(unittest.TestCase):
    """Test the CLI scan command end-to-end with captured output."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.state_path = os.path.join(self.tmpdir, "autonomous_state.json")
        self.kill_switch_path = os.path.join(self.tmpdir, "pause")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        with open(self.findings_path, "w") as f:
            f.write("# FINDINGS LOG\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _cli_args(self, extra=None):
        base = [
            "scan",
            "--target", "ClaudeCode",
            "--registry", self.registry_path,
            "--state", self.state_path,
            "--kill-switch", self.kill_switch_path,
            "--findings", self.findings_path,
            "--limit", "8",
            "--timeframe", "month",
        ]
        if extra:
            base.extend(extra)
        return base

    def test_cli_scan_json_output_is_valid(self):
        """CLI scan --json must emit valid JSON with report/needles/maybes/hay keys."""
        mock_posts = _mock_posts(n=8, needle_count=2)

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            cli_main(self._cli_args(extra=["--json"]))
            output = mock_out.getvalue()

        data = json.loads(output)
        self.assertIn("report", data)
        self.assertIn("needles", data)
        self.assertIn("maybes", data)
        self.assertIn("hay", data)

    def test_cli_scan_json_report_has_required_fields(self):
        """CLI JSON report must contain all required ScanReport fields."""
        mock_posts = _mock_posts(n=6, needle_count=1)

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            cli_main(self._cli_args(extra=["--json"]))
            output = mock_out.getvalue()

        data = json.loads(output)
        report = data["report"]
        for field in ("subreddit", "slug", "domain", "posts_fetched",
                      "posts_safe", "posts_blocked", "needles", "maybes",
                      "hay", "timestamp"):
            self.assertIn(field, report, f"Missing field: {field}")

    def test_cli_scan_human_summary_contains_subreddit(self):
        """CLI scan without --json must print human-readable summary."""
        mock_posts = _mock_posts(n=6)

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            cli_main(self._cli_args())
            output = mock_out.getvalue()

        self.assertIn("ClaudeCode", output)
        self.assertIn("NEEDLE", output)

    def test_cli_scan_json_counts_are_consistent(self):
        """JSON counts: needles+maybes+hay list lengths must match report counts."""
        mock_posts = _mock_posts(n=10, needle_count=3)

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            cli_main(self._cli_args(extra=["--json"]))
            output = mock_out.getvalue()

        data = json.loads(output)
        report = data["report"]
        self.assertEqual(report["needles"], len(data["needles"]))
        self.assertEqual(report["maybes"], len(data["maybes"]))
        self.assertEqual(report["hay"], len(data["hay"]))

    def test_cli_scan_blocked_by_kill_switch(self):
        """CLI scan must print blocked message when kill switch is active."""
        with open(self.kill_switch_path, "w") as f:
            f.write("pause")

        mock_posts = _mock_posts(n=5)

        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            cli_main(self._cli_args())
            output = mock_out.getvalue()

        self.assertIn("blocked", output.lower())


class TestSafetyVerification(unittest.TestCase):
    """Verify safety constraints are enforced in the full pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "state.json")
        self.kill_switch_path = os.path.join(self.tmpdir, "pause")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_posts_exceed_max_posts_per_scan(self):
        """Scanner must cap safe posts at max_posts_per_scan (50)."""
        gate = SafetyGate(
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
        )
        # Create 100 safe posts
        safe_posts = [{"id": f"p{i}", "url": "https://reddit.com", "title": "t"} for i in range(100)]
        blocked_posts = []

        from autonomous_scanner import AutonomousScanner
        scanner = AutonomousScanner(
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
        )
        safe, blocked = scanner.filter_posts(safe_posts)
        self.assertLessEqual(len(safe), gate.max_posts_per_scan)

    def test_safety_gate_can_scan_returns_allowed_initially(self):
        """Fresh safety gate must allow scanning."""
        gate = SafetyGate(
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            min_delay_seconds=0,  # Disable rate limit for test
        )
        allowed, reason = gate.can_scan()
        self.assertTrue(allowed)
        self.assertIn("allowed", reason.lower())

    def test_safety_gate_blocks_with_kill_switch(self):
        """Safety gate must block when kill switch file exists."""
        with open(self.kill_switch_path, "w") as f:
            f.write("pause")

        gate = SafetyGate(
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
        )
        allowed, reason = gate.can_scan()
        self.assertFalse(allowed)
        self.assertIn("kill switch", reason.lower())

    def test_safety_gate_blocks_at_session_limit(self):
        """Safety gate must block when scans_this_session >= max."""
        gate = SafetyGate(
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            min_delay_seconds=0,
        )
        gate.scans_this_session = gate.max_scans_per_session

        allowed, reason = gate.can_scan()
        self.assertFalse(allowed)
        self.assertIn("limit", reason.lower())

    def test_record_scan_increments_counter(self):
        """record_scan must increment count and persist slug."""
        gate = SafetyGate(
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
        )
        gate.record_scan("claudecode")
        self.assertEqual(gate.scans_this_session, 1)
        self.assertIn("claudecode", gate.subs_scanned)

        # Verify persistence: reload and check
        gate2 = SafetyGate(
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
        )
        self.assertEqual(gate2.scans_this_session, 1)
        self.assertIn("claudecode", gate2.subs_scanned)


class TestScannerApprovedDomains(unittest.TestCase):
    """Verify scanner only operates on approved domains."""

    def test_rank_all_only_returns_approved_domains(self):
        """rank_all must only include approved domains."""
        from autonomous_scanner import ScanPrioritizer, APPROVED_DOMAINS

        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = os.path.join(tmpdir, "registry.json")
            p = ScanPrioritizer(registry_path=registry_path)
            ranked = p.rank_all()

        for entry in ranked:
            self.assertIn(entry["domain"], APPROVED_DOMAINS | {"unknown"},
                         f"Unapproved domain found: {entry['domain']}")

    def test_approved_domains_are_safe_set(self):
        """APPROVED_DOMAINS must only contain expected safe values."""
        from autonomous_scanner import APPROVED_DOMAINS
        expected = {"claude", "trading", "dev", "research"}
        self.assertEqual(APPROVED_DOMAINS, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
