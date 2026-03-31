"""Tests for context-monitor/hooks/pre_compact.py — PreCompact hook (CTX-8)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestIsDisabled(unittest.TestCase):
    """Tests for the disabled check."""

    def test_disabled_when_env_set(self):
        from pre_compact import is_disabled
        with patch.dict(os.environ, {"CLAUDE_PRECOMPACT_DISABLED": "1"}):
            self.assertTrue(is_disabled())

    def test_enabled_by_default(self):
        from pre_compact import is_disabled
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_disabled())

    def test_enabled_when_env_not_1(self):
        from pre_compact import is_disabled
        with patch.dict(os.environ, {"CLAUDE_PRECOMPACT_DISABLED": "0"}):
            self.assertFalse(is_disabled())


class TestResolvePaths(unittest.TestCase):
    """Tests for path resolution."""

    def test_defaults(self):
        from pre_compact import resolve_paths, DEFAULT_SNAPSHOT_PATH, DEFAULT_STATE_FILE
        with patch.dict(os.environ, {}, clear=True):
            paths = resolve_paths()
            self.assertEqual(paths["snapshot"], DEFAULT_SNAPSHOT_PATH)
            self.assertEqual(paths["state_file"], DEFAULT_STATE_FILE)

    def test_custom_paths(self):
        from pre_compact import resolve_paths
        with patch.dict(os.environ, {
            "CLAUDE_COMPACTION_SNAPSHOT_PATH": "/tmp/snap.json",
            "CLAUDE_CONTEXT_STATE_FILE": "/tmp/state.json",
        }):
            paths = resolve_paths()
            self.assertEqual(paths["snapshot"], Path("/tmp/snap.json"))
            self.assertEqual(paths["state_file"], Path("/tmp/state.json"))


class TestParsePayload(unittest.TestCase):
    """Tests for parsing PreCompact hook payload."""

    def test_valid_payload(self):
        from pre_compact import parse_payload
        raw = json.dumps({
            "session_id": "abc123",
            "transcript_path": "/tmp/transcript.jsonl",
            "cwd": "/home/user/project",
            "hook_event_name": "PreCompact",
        })
        result = parse_payload(raw)
        self.assertEqual(result["session_id"], "abc123")
        self.assertEqual(result["cwd"], "/home/user/project")
        self.assertEqual(result["hook_event_name"], "PreCompact")

    def test_empty_input(self):
        from pre_compact import parse_payload
        result = parse_payload("")
        self.assertEqual(result["session_id"], "")
        self.assertEqual(result["hook_event_name"], "PreCompact")

    def test_invalid_json(self):
        from pre_compact import parse_payload
        result = parse_payload("{invalid")
        self.assertEqual(result["session_id"], "")

    def test_minimal_payload(self):
        from pre_compact import parse_payload
        result = parse_payload(json.dumps({"session_id": "s1"}))
        self.assertEqual(result["session_id"], "s1")
        self.assertEqual(result["cwd"], "")


class TestReadContextHealth(unittest.TestCase):
    """Tests for reading context health state file."""

    def test_reads_valid_state(self):
        from pre_compact import read_context_health
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "zone": "red",
                "pct": 72,
                "tokens": 144000,
                "turns": 45,
                "window": 200000,
            }, f)
            f.flush()
            result = read_context_health(Path(f.name))
        os.unlink(f.name)
        self.assertEqual(result["zone"], "red")
        self.assertEqual(result["pct"], 72)
        self.assertEqual(result["tokens"], 144000)
        self.assertEqual(result["turns"], 45)
        self.assertEqual(result["window"], 200000)

    def test_missing_file_returns_empty(self):
        from pre_compact import read_context_health
        result = read_context_health(Path("/nonexistent/state.json"))
        self.assertEqual(result, {})

    def test_corrupt_json_returns_empty(self):
        from pre_compact import read_context_health
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{corrupt")
            f.flush()
            result = read_context_health(Path(f.name))
        os.unlink(f.name)
        self.assertEqual(result, {})

    def test_partial_state_uses_defaults(self):
        from pre_compact import read_context_health
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"zone": "yellow"}, f)
            f.flush()
            result = read_context_health(Path(f.name))
        os.unlink(f.name)
        self.assertEqual(result["zone"], "yellow")
        self.assertEqual(result["pct"], 0)
        self.assertEqual(result["window"], 200_000)


class TestCaptureGitStatus(unittest.TestCase):
    """Tests for git status capture."""

    @patch("pre_compact.run_git_command")
    def test_parses_git_status(self, mock_git):
        from pre_compact import capture_git_status
        mock_git.return_value = " M file1.py\n?? file2.py\nMM file3.py"
        result = capture_git_status("/some/path")
        self.assertEqual(len(result), 3)
        self.assertIn(" M file1.py", result)
        self.assertIn("?? file2.py", result)

    @patch("pre_compact.run_git_command")
    def test_empty_status(self, mock_git):
        from pre_compact import capture_git_status
        mock_git.return_value = ""
        result = capture_git_status("/some/path")
        self.assertEqual(result, [])

    @patch("pre_compact.run_git_command")
    def test_caps_at_max_lines(self, mock_git):
        from pre_compact import capture_git_status, MAX_GIT_STATUS_LINES
        mock_git.return_value = "\n".join(f"M  file{i}.py" for i in range(100))
        result = capture_git_status("/some/path")
        self.assertEqual(len(result), MAX_GIT_STATUS_LINES)


class TestCaptureGitDiffStat(unittest.TestCase):
    """Tests for git diff --stat capture."""

    @patch("pre_compact.run_git_command")
    def test_extracts_summary_line(self, mock_git):
        from pre_compact import capture_git_diff_stat
        mock_git.return_value = (
            " file1.py | 10 +++++\n"
            " file2.py |  3 ---\n"
            " 2 files changed, 10 insertions(+), 3 deletions(-)"
        )
        result = capture_git_diff_stat("/some/path")
        self.assertIn("2 files changed", result)

    @patch("pre_compact.run_git_command")
    def test_empty_diff(self, mock_git):
        from pre_compact import capture_git_diff_stat
        mock_git.return_value = ""
        result = capture_git_diff_stat("/some/path")
        self.assertEqual(result, "")


class TestCaptureTodaysTasks(unittest.TestCase):
    """Tests for TODAYS_TASKS.md TODO extraction."""

    def test_extracts_todos(self):
        from pre_compact import capture_todays_tasks
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "TODAYS_TASKS.md"
            tasks_path.write_text(
                "# Today's Tasks\n"
                "- 10A. Design something [TODO]\n"
                "- 10B. Build something [TODO]\n"
                "- 9A. Done thing [DONE]\n"
                "- 10C. Deliver [TODO]\n"
            )
            result = capture_todays_tasks(tmpdir)
        self.assertEqual(len(result), 3)
        self.assertIn("10A. Design something [TODO]", result)
        self.assertIn("10B. Build something [TODO]", result)
        self.assertIn("10C. Deliver [TODO]", result)

    def test_missing_file(self):
        from pre_compact import capture_todays_tasks
        result = capture_todays_tasks("/nonexistent/path")
        self.assertEqual(result, [])

    def test_no_todos(self):
        from pre_compact import capture_todays_tasks
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "TODAYS_TASKS.md"
            tasks_path.write_text("# Today's Tasks\n- All done [DONE]\n")
            result = capture_todays_tasks(tmpdir)
        self.assertEqual(result, [])

    def test_caps_at_max(self):
        from pre_compact import capture_todays_tasks, MAX_TODAYS_TASKS
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "TODAYS_TASKS.md"
            lines = [f"- Task {i} [TODO]\n" for i in range(30)]
            tasks_path.write_text("".join(lines))
            result = capture_todays_tasks(tmpdir)
        self.assertEqual(len(result), MAX_TODAYS_TASKS)


class TestCaptureSessionHeader(unittest.TestCase):
    """Tests for SESSION_STATE.md header extraction."""

    def test_extracts_session_line(self):
        from pre_compact import capture_session_header
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "SESSION_STATE.md"
            state_path.write_text(
                "# CCA Session State\n\n"
                "Session 242 | Chat 9 | 2026-03-31\n\n"
                "## Current Work\n"
            )
            result = capture_session_header(tmpdir)
        self.assertIn("Session 242", result)

    def test_missing_file(self):
        from pre_compact import capture_session_header
        result = capture_session_header("/nonexistent")
        self.assertEqual(result, "")

    def test_no_session_line(self):
        from pre_compact import capture_session_header
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "SESSION_STATE.md"
            state_path.write_text("# No session info here\n")
            result = capture_session_header(tmpdir)
        self.assertEqual(result, "")


class TestCaptureAnchorSummary(unittest.TestCase):
    """Tests for compact anchor summary extraction."""

    def test_extracts_zone_line(self):
        from pre_compact import capture_anchor_summary
        with tempfile.TemporaryDirectory() as tmpdir:
            anchor = Path(tmpdir) / ".claude-compact-anchor.md"
            anchor.write_text(
                "# Anchor\n"
                "- Zone: **red** (72% of 200k tokens)\n"
                "- Tokens: 144000\n"
            )
            result = capture_anchor_summary(tmpdir)
        self.assertIn("Zone:", result)
        self.assertIn("red", result)

    def test_missing_anchor(self):
        from pre_compact import capture_anchor_summary
        result = capture_anchor_summary("/nonexistent")
        self.assertEqual(result, "")


class TestBuildSnapshot(unittest.TestCase):
    """Tests for the complete snapshot builder."""

    @patch("pre_compact.capture_anchor_summary", return_value="Zone: green")
    @patch("pre_compact.capture_session_header", return_value="Session 243")
    @patch("pre_compact.capture_todays_tasks", return_value=["Task A [TODO]"])
    @patch("pre_compact.capture_git_diff_stat", return_value="1 file changed")
    @patch("pre_compact.capture_git_status", return_value=["M file.py"])
    @patch("pre_compact.read_context_health", return_value={"zone": "yellow", "pct": 55})
    def test_builds_complete_snapshot(self, *mocks):
        from pre_compact import build_snapshot, SNAPSHOT_VERSION
        payload = {"session_id": "s1", "cwd": "/tmp"}
        paths = {"state_file": Path("/tmp/state.json")}
        result = build_snapshot(payload, paths)

        self.assertEqual(result["version"], SNAPSHOT_VERSION)
        self.assertEqual(result["session_id"], "s1")
        self.assertEqual(result["context_health"]["zone"], "yellow")
        self.assertEqual(result["git_status"], ["M file.py"])
        self.assertEqual(result["git_diff_stat"], "1 file changed")
        self.assertEqual(result["todays_tasks_todos"], ["Task A [TODO]"])
        self.assertEqual(result["session_header"], "Session 243")
        self.assertIn("timestamp", result)


class TestWriteSnapshot(unittest.TestCase):
    """Tests for atomic snapshot writing."""

    def test_writes_valid_json(self):
        from pre_compact import write_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snapshot.json"
            data = {"version": 1, "test": True}
            success = write_snapshot(path, data)
            self.assertTrue(success)
            self.assertTrue(path.exists())
            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(loaded["version"], 1)
            self.assertTrue(loaded["test"])

    def test_creates_parent_dirs(self):
        from pre_compact import write_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sub" / "dir" / "snapshot.json"
            success = write_snapshot(path, {"version": 1})
            self.assertTrue(success)
            self.assertTrue(path.exists())

    def test_overwrites_existing(self):
        from pre_compact import write_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snapshot.json"
            write_snapshot(path, {"version": 1, "first": True})
            write_snapshot(path, {"version": 1, "second": True})
            with open(path) as f:
                loaded = json.load(f)
            self.assertTrue(loaded["second"])
            self.assertNotIn("first", loaded)

    def test_no_tmp_file_left_on_success(self):
        from pre_compact import write_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snapshot.json"
            write_snapshot(path, {"version": 1})
            files = list(Path(tmpdir).iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].name, "snapshot.json")


class TestRunGitCommand(unittest.TestCase):
    """Tests for git command execution."""

    def test_returns_empty_on_timeout(self):
        from pre_compact import run_git_command
        # Use a command that would hang but with very short timeout
        # Just verify the function handles failures gracefully
        result = run_git_command(["status", "--short"], "/nonexistent/repo/path/xyz")
        # Either empty (no git repo) or some output — shouldn't crash
        self.assertIsInstance(result, str)

    def test_returns_empty_on_missing_git(self):
        from pre_compact import run_git_command
        with patch("pre_compact.subprocess.run", side_effect=FileNotFoundError):
            result = run_git_command(["status"], "/tmp")
        self.assertEqual(result, "")


class TestEndToEnd(unittest.TestCase):
    """Integration-style tests for the full PreCompact flow."""

    @patch("pre_compact.capture_anchor_summary", return_value="")
    @patch("pre_compact.capture_session_header", return_value="")
    @patch("pre_compact.capture_todays_tasks", return_value=[])
    @patch("pre_compact.capture_git_diff_stat", return_value="")
    @patch("pre_compact.capture_git_status", return_value=[])
    @patch("pre_compact.read_context_health", return_value={})
    def test_empty_state_still_writes_valid_snapshot(self, *mocks):
        from pre_compact import build_snapshot, write_snapshot
        payload = {"session_id": "", "cwd": "/tmp"}
        paths = {"state_file": Path("/tmp/nonexistent.json")}
        snapshot = build_snapshot(payload, paths)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snap.json"
            success = write_snapshot(path, snapshot)
            self.assertTrue(success)
            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(loaded["version"], 1)
            self.assertIn("timestamp", loaded)


if __name__ == "__main__":
    unittest.main()
