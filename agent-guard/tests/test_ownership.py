"""
Tests for AG-2: ownership manifest.
"""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ownership


# ---------------------------------------------------------------------------
# extract_session_label
# ---------------------------------------------------------------------------

class TestExtractSessionLabel(unittest.TestCase):

    def test_extracts_ag_prefix(self):
        self.assertEqual(ownership.extract_session_label("AG-1: iPhone mobile approver"), "AG-1")

    def test_extracts_ctx_prefix(self):
        self.assertEqual(ownership.extract_session_label("CTX-3: alert hook"), "CTX-3")

    def test_extracts_mem_prefix(self):
        self.assertEqual(ownership.extract_session_label("MEM-5: CLI viewer"), "MEM-5")

    def test_extracts_spec_prefix(self):
        self.assertEqual(ownership.extract_session_label("SPEC-6: slash commands"), "SPEC-6")

    def test_extracts_session_n(self):
        label = ownership.extract_session_label("Session 6: browse-url skill")
        self.assertEqual(label, "Session 6")

    def test_falls_back_to_first_word(self):
        label = ownership.extract_session_label("fix: typo in README")
        self.assertIn("fix", label)

    def test_handles_empty_subject(self):
        label = ownership.extract_session_label("")
        self.assertIsInstance(label, str)


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------

class TestParseDate(unittest.TestCase):

    def test_parses_standard_iso(self):
        dt = ownership.parse_date("2026-03-08T22:41:55+00:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 3)

    def test_parses_git_format(self):
        dt = ownership.parse_date("2026-03-08 22:41:55 +0000")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)

    def test_returns_none_for_garbage(self):
        dt = ownership.parse_date("not a date")
        self.assertIsNone(dt)

    def test_returns_none_for_empty(self):
        dt = ownership.parse_date("")
        self.assertIsNone(dt)


# ---------------------------------------------------------------------------
# find_conflict_risks
# ---------------------------------------------------------------------------

class TestFindConflictRisks(unittest.TestCase):

    def _commit(self, subject="AG-1: test"):
        return {"hash": "abc", "author": "Claude", "date_iso": "2026-03-08T12:00:00+00:00", "subject": subject}

    def test_no_conflicts_when_each_file_in_one_commit(self):
        ownership_map = {
            "file_a.py": [self._commit()],
            "file_b.py": [self._commit()],
        }
        risks = ownership.find_conflict_risks(ownership_map)
        self.assertEqual(risks, [])

    def test_flags_file_in_multiple_commits(self):
        ownership_map = {
            "shared.py": [self._commit("AG-1: first"), self._commit("CTX-3: second")],
            "unique.py": [self._commit()],
        }
        risks = ownership.find_conflict_risks(ownership_map)
        self.assertIn("shared.py", risks)
        self.assertNotIn("unique.py", risks)

    def test_empty_ownership_returns_no_risks(self):
        risks = ownership.find_conflict_risks({})
        self.assertEqual(risks, [])


# ---------------------------------------------------------------------------
# build_ownership_map (with mocked git calls)
# ---------------------------------------------------------------------------

class TestBuildOwnershipMap(unittest.TestCase):

    def _commit(self, h, date_iso, subject):
        return {"hash": h, "author": "Claude", "date_iso": date_iso, "subject": subject}

    def test_maps_files_to_commits(self):
        commits = [
            self._commit("aaa", "2026-03-08T22:00:00+00:00", "AG-1: hook"),
        ]
        with patch.object(ownership, "get_files_for_commit", return_value=["src/foo.py"]):
            result = ownership.build_ownership_map(commits, "/fake/cwd")
        self.assertIn("src/foo.py", result)
        self.assertEqual(len(result["src/foo.py"]), 1)

    def test_same_file_in_two_commits_appears_twice(self):
        commits = [
            self._commit("aaa", "2026-03-08T22:00:00+00:00", "AG-1: first"),
            self._commit("bbb", "2026-03-07T22:00:00+00:00", "CTX-3: second"),
        ]
        with patch.object(ownership, "get_files_for_commit", return_value=["shared.py"]):
            result = ownership.build_ownership_map(commits, "/fake/cwd")
        self.assertEqual(len(result["shared.py"]), 2)

    def test_filters_commits_before_since_dt(self):
        since = datetime(2026, 3, 8, 0, 0, 0, tzinfo=timezone.utc)
        commits = [
            self._commit("aaa", "2026-03-09T00:00:00+00:00", "recent"),   # after
            self._commit("bbb", "2026-03-07T00:00:00+00:00", "old"),       # before
        ]
        calls = []
        def fake_files(h, cwd):
            calls.append(h)
            return ["file.py"]
        with patch.object(ownership, "get_files_for_commit", side_effect=fake_files):
            ownership.build_ownership_map(commits, "/fake/cwd", since_dt=since)
        # Only the "recent" commit should have been processed
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], "aaa")


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

class TestBuildReport(unittest.TestCase):

    def _commit(self, subject="AG-1: test"):
        return {"hash": "abc", "author": "Claude", "date_iso": "2026-03-08T22:00:00+00:00", "subject": subject}

    def test_contains_header(self):
        report = ownership.build_report({}, [], [], "/tmp/myproject")
        self.assertIn("Ownership Manifest", report)
        self.assertIn("myproject", report)

    def test_shows_uncommitted_files(self):
        report = ownership.build_report({}, ["src/hot.py"], [], "/tmp/proj")
        self.assertIn("src/hot.py", report)
        self.assertIn("Uncommitted", report)

    def test_shows_conflict_risks(self):
        ownership_map = {"shared.py": [self._commit("AG-1"), self._commit("CTX-3")]}
        risks = ["shared.py"]
        report = ownership.build_report(ownership_map, [], risks, "/tmp/proj")
        self.assertIn("Conflict Risk", report)
        self.assertIn("shared.py", report)

    def test_conflicts_only_omits_full_table(self):
        ownership_map = {"file.py": [self._commit()]}
        report = ownership.build_report(ownership_map, [], [], "/tmp/proj", conflicts_only=True)
        # Should not contain the "Recent File Activity" section
        self.assertNotIn("Recent File Activity", report)

    def test_full_report_shows_file_table(self):
        ownership_map = {"src/tool.py": [self._commit("MEM-5: viewer")]}
        report = ownership.build_report(ownership_map, [], [], "/tmp/proj", conflicts_only=False)
        self.assertIn("Recent File Activity", report)
        self.assertIn("src/tool.py", report)

    def test_no_activity_shows_message(self):
        report = ownership.build_report({}, [], [], "/tmp/proj")
        self.assertIn("No file activity", report)


# ---------------------------------------------------------------------------
# format_date_short
# ---------------------------------------------------------------------------

class TestFormatDateShort(unittest.TestCase):

    def test_formats_standard_date(self):
        s = ownership.format_date_short("2026-03-08T22:41:55+00:00")
        self.assertIn("2026-03-08", s)
        self.assertIn("22:41", s)

    def test_handles_bad_date(self):
        s = ownership.format_date_short("bad-date")
        self.assertIsInstance(s, str)


# ---------------------------------------------------------------------------
# is_git_repo
# ---------------------------------------------------------------------------

class TestIsGitRepo(unittest.TestCase):

    def test_current_dir_is_git_repo(self):
        # ClaudeCodeAdvancements is a git repo
        import os
        result = ownership.is_git_repo(os.getcwd())
        self.assertTrue(result)

    def test_tmp_dir_is_not_git_repo(self):
        result = ownership.is_git_repo("/tmp")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
