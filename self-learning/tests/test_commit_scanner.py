"""Tests for commit_scanner.py — Scan Kalshi bot git commits for REQ delivery implementations."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from commit_scanner import (
    parse_commit_line,
    extract_req_ids,
    scan_commits,
    match_commits_to_outcomes,
    CommitInfo,
)


class TestParseCommitLine(unittest.TestCase):
    """Parse git log --oneline output into structured info."""

    def test_basic_commit(self):
        line = "4c84724 docs: S139 monitoring wrap — CLV deployed, REQ-027 confirmed"
        ci = parse_commit_line(line)
        self.assertEqual(ci.hash, "4c84724")
        self.assertEqual(ci.message, "docs: S139 monitoring wrap — CLV deployed, REQ-027 confirmed")

    def test_feat_commit(self):
        line = "06c310b feat: CLV tracking — capture close_price_cents at settlement (REQ-036)"
        ci = parse_commit_line(line)
        self.assertEqual(ci.hash, "06c310b")
        self.assertIn("REQ-036", ci.message)

    def test_empty_line(self):
        self.assertIsNone(parse_commit_line(""))
        self.assertIsNone(parse_commit_line("   "))

    def test_short_hash(self):
        line = "abc1234 fix: something"
        ci = parse_commit_line(line)
        self.assertEqual(ci.hash, "abc1234")


class TestExtractReqIds(unittest.TestCase):
    """Extract REQ-NNN from commit messages."""

    def test_single_req(self):
        self.assertEqual(extract_req_ids("feat: CLV tracking (REQ-036)"), ["REQ-036"])

    def test_multiple_reqs(self):
        result = extract_req_ids("REQ-034 + REQ-035 integration")
        self.assertIn("REQ-034", result)
        self.assertIn("REQ-035", result)

    def test_no_req(self):
        self.assertEqual(extract_req_ids("fix: random bug"), [])

    def test_req_in_context(self):
        self.assertEqual(extract_req_ids("copy CCA Monte Carlo simulator (REQ-040)"), ["REQ-040"])

    def test_normalizes_short_form(self):
        """REQ-4 -> REQ-004."""
        result = extract_req_ids("fix for REQ-4 issue")
        self.assertEqual(result, ["REQ-004"])

    def test_deduplicates(self):
        result = extract_req_ids("REQ-036 and also REQ-036 again")
        self.assertEqual(result, ["REQ-036"])


class TestScanCommits(unittest.TestCase):
    """Scan raw git log output for REQ-referenced commits."""

    def test_finds_req_commits(self):
        log_output = (
            "4c84724 docs: S139 wrap — REQ-027 confirmed\n"
            "06c310b feat: CLV tracking (REQ-036)\n"
            "d7d1aca feat: Monte Carlo simulator (REQ-040)\n"
            "e073d0e docs: correct maker_sniper fill count\n"
        )
        results = scan_commits(log_output)
        self.assertEqual(len(results), 3)  # Only commits with REQ-xxx

    def test_empty_log(self):
        self.assertEqual(scan_commits(""), [])

    def test_returns_commit_info_with_reqs(self):
        log_output = "06c310b feat: CLV (REQ-036)\n"
        results = scan_commits(log_output)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hash, "06c310b")
        self.assertEqual(results[0].req_ids, ["REQ-036"])

    def test_categorizes_feat_as_implementation(self):
        log_output = "06c310b feat: CLV tracking (REQ-036)\n"
        results = scan_commits(log_output)
        self.assertEqual(results[0].category, "implementation")

    def test_categorizes_docs_as_documentation(self):
        log_output = "4c84724 docs: S139 wrap — REQ-027 confirmed\n"
        results = scan_commits(log_output)
        self.assertEqual(results[0].category, "documentation")

    def test_categorizes_fix_as_implementation(self):
        log_output = "abc1234 fix: guard for REQ-033\n"
        results = scan_commits(log_output)
        self.assertEqual(results[0].category, "implementation")

    def test_categorizes_test_as_testing(self):
        log_output = "abc1234 test: add tests for REQ-027\n"
        results = scan_commits(log_output)
        self.assertEqual(results[0].category, "testing")


class TestMatchCommitsToOutcomes(unittest.TestCase):
    """Match scanned commits to research_outcomes entries."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.outcomes_path = os.path.join(self.tmpdir, "research_outcomes.jsonl")

    def _write_outcomes(self, entries):
        with open(self.outcomes_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_matches_by_req_id(self):
        self._write_outcomes([
            {"delivery_id": "d-abc", "req_id": "REQ-036", "title": "CLV Tracking",
             "status": "delivered", "category": "framework"},
        ])
        commits = [CommitInfo("06c310b", "feat: CLV tracking (REQ-036)", ["REQ-036"], "implementation")]
        matches = match_commits_to_outcomes(commits, self.outcomes_path)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["delivery_id"], "d-abc")
        self.assertEqual(matches[0]["commit_hash"], "06c310b")
        self.assertEqual(matches[0]["new_status"], "implemented")

    def test_docs_commit_sets_acknowledged(self):
        self._write_outcomes([
            {"delivery_id": "d-abc", "req_id": "REQ-027", "title": "Monte Carlo",
             "status": "delivered", "category": "tool"},
        ])
        commits = [CommitInfo("4c84724", "docs: wrap — REQ-027 confirmed", ["REQ-027"], "documentation")]
        matches = match_commits_to_outcomes(commits, self.outcomes_path)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["new_status"], "acknowledged")

    def test_no_match_for_unknown_req(self):
        self._write_outcomes([
            {"delivery_id": "d-abc", "req_id": "REQ-036", "title": "CLV",
             "status": "delivered", "category": "framework"},
        ])
        commits = [CommitInfo("abc1234", "feat: something (REQ-099)", ["REQ-099"], "implementation")]
        matches = match_commits_to_outcomes(commits, self.outcomes_path)
        self.assertEqual(len(matches), 0)

    def test_multiple_commits_same_req(self):
        """Multiple commits referencing same REQ — use the implementation one."""
        self._write_outcomes([
            {"delivery_id": "d-abc", "req_id": "REQ-036", "title": "CLV",
             "status": "delivered", "category": "framework"},
        ])
        commits = [
            CommitInfo("aaa", "docs: mention REQ-036", ["REQ-036"], "documentation"),
            CommitInfo("bbb", "feat: build CLV (REQ-036)", ["REQ-036"], "implementation"),
        ]
        matches = match_commits_to_outcomes(commits, self.outcomes_path)
        # Should pick implementation over documentation
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["commit_hash"], "bbb")
        self.assertEqual(matches[0]["new_status"], "implemented")

    def test_empty_outcomes(self):
        self._write_outcomes([])
        commits = [CommitInfo("abc", "feat: (REQ-036)", ["REQ-036"], "implementation")]
        matches = match_commits_to_outcomes(commits, self.outcomes_path)
        self.assertEqual(len(matches), 0)

    def test_preserves_already_implemented(self):
        """Don't downgrade implemented to acknowledged."""
        self._write_outcomes([
            {"delivery_id": "d-abc", "req_id": "REQ-036", "title": "CLV",
             "status": "implemented", "category": "framework"},
        ])
        commits = [CommitInfo("aaa", "docs: mention REQ-036", ["REQ-036"], "documentation")]
        matches = match_commits_to_outcomes(commits, self.outcomes_path)
        # Already implemented — docs commit shouldn't downgrade
        self.assertEqual(len(matches), 0)


if __name__ == "__main__":
    unittest.main()
