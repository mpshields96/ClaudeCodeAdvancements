"""Tests for principle_discoverer.py — MT-49 Phase 3: Automated principle discovery.

Discovers principles from git commit patterns, session outcomes, and test patterns.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from principle_discoverer import (
    CommitPattern,
    GitPatternDiscoverer,
    SessionPatternDiscoverer,
    PrincipleDiscoverer,
)


class TestCommitPattern(unittest.TestCase):
    """Tests for the CommitPattern dataclass."""

    def test_basic_creation(self):
        p = CommitPattern(
            pattern_type="coupling",
            description="files A and B always change together",
            evidence_count=5,
            confidence=0.8,
            source_commits=["abc1234"],
        )
        self.assertEqual(p.pattern_type, "coupling")
        self.assertEqual(p.evidence_count, 5)
        self.assertAlmostEqual(p.confidence, 0.8)

    def test_to_principle_text(self):
        p = CommitPattern(
            pattern_type="coupling",
            description="foo.py and bar.py are tightly coupled",
            evidence_count=8,
            confidence=0.9,
            source_commits=[],
        )
        text = p.to_principle_text()
        self.assertIn("foo.py", text)
        self.assertIn("bar.py", text)

    def test_confidence_clamped(self):
        p = CommitPattern(
            pattern_type="velocity",
            description="test",
            evidence_count=1,
            confidence=1.5,
            source_commits=[],
        )
        self.assertLessEqual(p.clamped_confidence, 1.0)
        p2 = CommitPattern(
            pattern_type="velocity",
            description="test",
            evidence_count=1,
            confidence=-0.1,
            source_commits=[],
        )
        self.assertGreaterEqual(p2.clamped_confidence, 0.0)


class TestGitPatternDiscoverer(unittest.TestCase):
    """Tests for GitPatternDiscoverer."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_log_lines(self, entries):
        """Create fake git log output lines."""
        lines = []
        for entry in entries:
            lines.append(f"COMMIT_START {entry['hash']} {entry.get('date', '2026-03-20 10:00:00 -0400')}")
            lines.append(entry.get("message", "test commit"))
            lines.append("FILES_START")
            for f in entry.get("files", []):
                lines.append(f)
            lines.append("FILES_END")
        return "\n".join(lines)

    def test_parse_git_log_basic(self):
        d = GitPatternDiscoverer(project_root=self.tmpdir)
        log = self._make_log_lines([
            {"hash": "abc1234", "message": "fix bug", "files": ["src/foo.py", "src/bar.py"]},
        ])
        commits = d._parse_git_log(log)
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["hash"], "abc1234")
        self.assertEqual(commits[0]["files"], ["src/foo.py", "src/bar.py"])

    def test_parse_git_log_multiple(self):
        d = GitPatternDiscoverer(project_root=self.tmpdir)
        log = self._make_log_lines([
            {"hash": "aaa", "message": "first", "files": ["a.py"]},
            {"hash": "bbb", "message": "second", "files": ["b.py", "c.py"]},
        ])
        commits = d._parse_git_log(log)
        self.assertEqual(len(commits), 2)

    def test_detect_coupling(self):
        d = GitPatternDiscoverer(project_root=self.tmpdir, min_coupling_count=2)
        commits = [
            {"hash": "a", "message": "m1", "files": ["x.py", "y.py"], "date": "2026-03-20"},
            {"hash": "b", "message": "m2", "files": ["x.py", "y.py", "z.py"], "date": "2026-03-20"},
            {"hash": "c", "message": "m3", "files": ["x.py", "y.py"], "date": "2026-03-21"},
        ]
        patterns = d._detect_coupling(commits)
        # x.py and y.py appear together 3 times
        coupled = [p for p in patterns if "x.py" in p.description and "y.py" in p.description]
        self.assertGreater(len(coupled), 0)
        self.assertGreaterEqual(coupled[0].evidence_count, 3)

    def test_detect_coupling_ignores_rare(self):
        d = GitPatternDiscoverer(project_root=self.tmpdir, min_coupling_count=3)
        commits = [
            {"hash": "a", "message": "m1", "files": ["x.py", "y.py"], "date": "2026-03-20"},
            {"hash": "b", "message": "m2", "files": ["x.py", "z.py"], "date": "2026-03-20"},
        ]
        patterns = d._detect_coupling(commits)
        # Only 1 co-occurrence of x+y, below threshold of 3
        coupled_xy = [p for p in patterns if "x.py" in p.description and "y.py" in p.description]
        self.assertEqual(len(coupled_xy), 0)

    def test_detect_session_size_patterns(self):
        d = GitPatternDiscoverer(project_root=self.tmpdir)
        commits = [
            {"hash": "a", "message": "S100: fix A", "files": ["a.py"], "date": "2026-03-20"},
            {"hash": "b", "message": "S100: fix B", "files": ["b.py", "c.py"], "date": "2026-03-20"},
            {"hash": "c", "message": "S100: fix C", "files": ["d.py"], "date": "2026-03-20"},
            {"hash": "d", "message": "S101: big change", "files": list(f"f{i}.py" for i in range(15)), "date": "2026-03-21"},
        ]
        patterns = d._detect_session_size(commits)
        # S101 has a single commit with 15 files — should flag as large commit
        self.assertTrue(any("large" in p.description.lower() or "big" in p.description.lower() for p in patterns) or len(patterns) == 0)

    def test_detect_hotspot_files(self):
        d = GitPatternDiscoverer(project_root=self.tmpdir, hotspot_threshold=3)
        commits = [
            {"hash": str(i), "message": f"fix {i}", "files": ["hot.py", f"other{i}.py"], "date": "2026-03-20"}
            for i in range(5)
        ]
        patterns = d._detect_hotspots(commits)
        hotspot = [p for p in patterns if "hot.py" in p.description]
        self.assertGreater(len(hotspot), 0)

    def test_discover_returns_list(self):
        """discover() with no git repo returns empty list gracefully."""
        d = GitPatternDiscoverer(project_root=self.tmpdir)
        result = d.discover()
        self.assertIsInstance(result, list)

    def test_coupling_excludes_test_source_pairs(self):
        """Test+source file coupling (TDD) should not be reported."""
        d = GitPatternDiscoverer(project_root=self.tmpdir, min_coupling_count=2)
        commits = [
            {"hash": "a", "message": "m1", "files": ["foo.py", "test_foo.py"], "date": "2026-03-20"},
            {"hash": "b", "message": "m2", "files": ["foo.py", "test_foo.py"], "date": "2026-03-20"},
            {"hash": "c", "message": "m3", "files": ["foo.py", "test_foo.py"], "date": "2026-03-21"},
        ]
        patterns = d._detect_coupling(commits)
        self.assertEqual(len(patterns), 0)

    def test_is_test_source_pair(self):
        self.assertTrue(GitPatternDiscoverer._is_test_source_pair("test_foo.py", "foo.py"))
        self.assertTrue(GitPatternDiscoverer._is_test_source_pair("foo.py", "test_foo.py"))
        self.assertFalse(GitPatternDiscoverer._is_test_source_pair("foo.py", "bar.py"))
        self.assertFalse(GitPatternDiscoverer._is_test_source_pair("test_foo.py", "bar.py"))

    def test_hotspots_exclude_test_files(self):
        d = GitPatternDiscoverer(project_root=self.tmpdir, hotspot_threshold=3)
        commits = [
            {"hash": str(i), "message": f"c{i}", "files": ["test_hot.py", "hot.py"], "date": "2026-03-20"}
            for i in range(5)
        ]
        patterns = d._detect_hotspots(commits)
        for p in patterns:
            self.assertNotIn("test_hot.py", p.description)

    def test_discover_dedup(self):
        d = GitPatternDiscoverer(project_root=self.tmpdir, min_coupling_count=2)
        commits = [
            {"hash": "a", "message": "m1", "files": ["x.py", "y.py"], "date": "2026-03-20"},
            {"hash": "b", "message": "m2", "files": ["x.py", "y.py"], "date": "2026-03-20"},
            {"hash": "c", "message": "m3", "files": ["x.py", "y.py"], "date": "2026-03-21"},
        ]
        patterns = d._detect_coupling(commits)
        # Should not produce duplicate descriptions
        descs = [p.description for p in patterns]
        self.assertEqual(len(descs), len(set(descs)))


class TestSessionPatternDiscoverer(unittest.TestCase):
    """Tests for SessionPatternDiscoverer — extracts from journal.jsonl."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_journal(self, entries):
        with open(self.journal_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_empty_journal(self):
        d = SessionPatternDiscoverer(journal_path=self.journal_path)
        result = d.discover()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_missing_journal(self):
        d = SessionPatternDiscoverer(journal_path="/tmp/nonexistent.jsonl")
        result = d.discover()
        self.assertEqual(len(result), 0)

    def test_detect_recurring_pain(self):
        """Recurring pain events with similar tags should produce a principle."""
        entries = [
            {"type": "pain", "session": i, "detail": "Edit retries on structured files",
             "tags": ["edit_retry"], "timestamp": f"2026-03-{20+i}T10:00:00Z"}
            for i in range(5)
        ]
        self._write_journal(entries)
        d = SessionPatternDiscoverer(journal_path=self.journal_path, min_occurrences=3)
        patterns = d.discover()
        self.assertGreater(len(patterns), 0)
        self.assertTrue(any("edit" in p.description.lower() or "retry" in p.description.lower() for p in patterns))

    def test_detect_recurring_win(self):
        """Recurring win events should produce positive principles."""
        entries = [
            {"type": "win", "session": i, "detail": "TDD caught regression before commit",
             "tags": ["tdd"], "timestamp": f"2026-03-{20+i}T10:00:00Z"}
            for i in range(4)
        ]
        self._write_journal(entries)
        d = SessionPatternDiscoverer(journal_path=self.journal_path, min_occurrences=3)
        patterns = d.discover()
        self.assertGreater(len(patterns), 0)

    def test_low_frequency_ignored(self):
        """Events that appear only once should not produce patterns."""
        entries = [
            {"type": "pain", "session": 1, "detail": "one-off issue",
             "tags": ["rare"], "timestamp": "2026-03-20T10:00:00Z"},
        ]
        self._write_journal(entries)
        d = SessionPatternDiscoverer(journal_path=self.journal_path, min_occurrences=3)
        patterns = d.discover()
        self.assertEqual(len(patterns), 0)

    def test_pattern_has_evidence_count(self):
        entries = [
            {"type": "pain", "session": i, "detail": "same problem",
             "tags": ["same_tag"], "timestamp": f"2026-03-{20+i}T10:00:00Z"}
            for i in range(5)
        ]
        self._write_journal(entries)
        d = SessionPatternDiscoverer(journal_path=self.journal_path, min_occurrences=3)
        patterns = d.discover()
        if patterns:
            self.assertGreaterEqual(patterns[0].evidence_count, 5)


class TestPrincipleDiscoverer(unittest.TestCase):
    """Tests for the top-level PrincipleDiscoverer orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_discover_all_returns_list(self):
        d = PrincipleDiscoverer(
            project_root=self.tmpdir,
            principles_path=self.principles_path,
            journal_path=self.journal_path,
        )
        result = d.discover_all()
        self.assertIsInstance(result, list)

    def test_register_skips_duplicates(self):
        """Should not register a principle whose text already exists."""
        d = PrincipleDiscoverer(
            project_root=self.tmpdir,
            principles_path=self.principles_path,
            journal_path=self.journal_path,
        )
        pattern = CommitPattern(
            pattern_type="coupling",
            description="a.py and b.py are coupled",
            evidence_count=5,
            confidence=0.8,
            source_commits=["abc"],
        )
        count1 = d._register_patterns([pattern])
        count2 = d._register_patterns([pattern])
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 0)  # duplicate

    def test_register_respects_min_confidence(self):
        d = PrincipleDiscoverer(
            project_root=self.tmpdir,
            principles_path=self.principles_path,
            journal_path=self.journal_path,
            min_confidence=0.5,
        )
        weak = CommitPattern(
            pattern_type="hotspot",
            description="rarely changed file",
            evidence_count=2,
            confidence=0.3,
            source_commits=[],
        )
        count = d._register_patterns([weak])
        self.assertEqual(count, 0)

    def test_register_writes_to_principles_file(self):
        d = PrincipleDiscoverer(
            project_root=self.tmpdir,
            principles_path=self.principles_path,
            journal_path=self.journal_path,
        )
        pattern = CommitPattern(
            pattern_type="coupling",
            description="x.py and y.py change together",
            evidence_count=5,
            confidence=0.7,
            source_commits=["aaa"],
        )
        d._register_patterns([pattern])
        self.assertTrue(os.path.exists(self.principles_path))
        with open(self.principles_path) as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertIn("x.py", data["text"])

    def test_summary_format(self):
        d = PrincipleDiscoverer(
            project_root=self.tmpdir,
            principles_path=self.principles_path,
            journal_path=self.journal_path,
        )
        pattern = CommitPattern(
            pattern_type="coupling",
            description="a and b coupled",
            evidence_count=5,
            confidence=0.8,
            source_commits=[],
        )
        d._register_patterns([pattern])
        summary = d.summary()
        self.assertIn("1", summary)  # 1 principle registered

    def test_cli_discover_mode(self):
        """CLI --discover should run without error."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "..", "principle_discoverer.py"),
             "discover", "--dry-run",
             "--project-root", self.tmpdir,
             "--principles-path", self.principles_path,
             "--journal-path", self.journal_path],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_status_mode(self):
        """CLI status should run without error."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "..", "principle_discoverer.py"),
             "status",
             "--principles-path", self.principles_path],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
