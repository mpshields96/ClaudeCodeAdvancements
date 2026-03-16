"""
Tests for USAGE-1: Token/Cost Counter CLI

Covers:
  - Cost calculation for each model (sonnet, opus, haiku)
  - Token extraction from transcript JSONL
  - Session listing and filtering by date
  - Edge cases: empty transcript, missing usage, malformed JSON
  - Model detection from transcript entries
  - Output formatting
  - Aggregation
  - CLI parser
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent to path so we can import usage_counter
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usage_counter as uc


class TestCostForTokens(unittest.TestCase):
    """Test the pure cost calculation function."""

    def test_sonnet_basic(self):
        result = uc.cost_for_tokens(1_000_000, 1_000_000, 0, 0, "sonnet")
        self.assertAlmostEqual(result["input_cost"], 3.00)
        self.assertAlmostEqual(result["output_cost"], 15.00)
        self.assertAlmostEqual(result["total"], 18.00)
        self.assertEqual(result["model"], "sonnet")

    def test_opus_basic(self):
        result = uc.cost_for_tokens(1_000_000, 1_000_000, 0, 0, "opus")
        self.assertAlmostEqual(result["input_cost"], 15.00)
        self.assertAlmostEqual(result["output_cost"], 75.00)
        self.assertAlmostEqual(result["total"], 90.00)

    def test_haiku_basic(self):
        result = uc.cost_for_tokens(1_000_000, 1_000_000, 0, 0, "haiku")
        self.assertAlmostEqual(result["input_cost"], 0.25)
        self.assertAlmostEqual(result["output_cost"], 1.25)
        self.assertAlmostEqual(result["total"], 1.50)

    def test_sonnet_with_cache(self):
        result = uc.cost_for_tokens(100_000, 50_000, 200_000, 30_000, "sonnet")
        self.assertAlmostEqual(result["input_cost"], 0.30)
        self.assertAlmostEqual(result["output_cost"], 0.75)
        self.assertAlmostEqual(result["cache_read_cost"], 0.06)
        self.assertAlmostEqual(result["cache_create_cost"], 0.1125)
        expected_total = 0.30 + 0.75 + 0.06 + 0.1125
        self.assertAlmostEqual(result["total"], expected_total, places=4)

    def test_zero_tokens(self):
        result = uc.cost_for_tokens(0, 0, 0, 0, "sonnet")
        self.assertEqual(result["total"], 0.0)
        self.assertEqual(result["input_cost"], 0.0)

    def test_unknown_model_defaults_to_sonnet(self):
        result = uc.cost_for_tokens(1_000_000, 0, 0, 0, "gpt-4")
        self.assertAlmostEqual(result["input_cost"], 3.00)
        self.assertEqual(result["model"], "gpt-4")

    def test_cost_dict_has_all_keys(self):
        result = uc.cost_for_tokens(100, 200, 300, 400, "sonnet")
        expected_keys = {"input_cost", "output_cost", "cache_read_cost", "cache_create_cost", "total", "model"}
        self.assertEqual(set(result.keys()), expected_keys)


class TestDetectModel(unittest.TestCase):
    """Test model detection from transcript entries."""

    def test_top_level_sonnet(self):
        entry = {"model": "claude-sonnet-4-20250514"}
        self.assertEqual(uc.detect_model(entry), "sonnet")

    def test_top_level_opus(self):
        entry = {"model": "claude-opus-4-20250514"}
        self.assertEqual(uc.detect_model(entry), "opus")

    def test_top_level_haiku(self):
        entry = {"model": "claude-haiku-3.5-20250514"}
        self.assertEqual(uc.detect_model(entry), "haiku")

    def test_nested_in_message(self):
        entry = {"message": {"model": "claude-sonnet-4-20250514"}}
        self.assertEqual(uc.detect_model(entry), "sonnet")

    def test_no_model_field(self):
        entry = {"type": "assistant", "message": {"content": "hello"}}
        self.assertIsNone(uc.detect_model(entry))

    def test_unknown_model_string(self):
        entry = {"model": "claude-mystery-99"}
        self.assertIsNone(uc.detect_model(entry))

    def test_empty_entry(self):
        self.assertIsNone(uc.detect_model({}))


class TestExtractSessionUsage(unittest.TestCase):
    """Test parsing transcript JSONL files."""

    def _write_jsonl(self, entries: list[dict]) -> Path:
        """Write entries to a temporary JSONL file and return its path."""
        self._tmpdir = tempfile.mkdtemp()
        path = Path(self._tmpdir) / "test_session.jsonl"
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return path

    def test_basic_extraction(self):
        entries = [
            {"type": "human", "message": {"content": "hello"}},
            {
                "type": "assistant",
                "message": {
                    "model": "claude-sonnet-4-20250514",
                    "usage": {
                        "input_tokens": 1000,
                        "output_tokens": 500,
                        "cache_read_input_tokens": 2000,
                        "cache_creation_input_tokens": 300,
                    },
                    "content": "Hi there!",
                },
            },
        ]
        path = self._write_jsonl(entries)
        result = uc.extract_session_usage(path)

        self.assertEqual(result["input_tokens"], 1000)
        self.assertEqual(result["output_tokens"], 500)
        self.assertEqual(result["cache_read_tokens"], 2000)
        self.assertEqual(result["cache_create_tokens"], 300)
        self.assertEqual(result["total_tokens"], 3800)
        self.assertEqual(result["turn_count"], 2)
        self.assertEqual(result["assistant_turns"], 1)
        self.assertEqual(result["model"], "sonnet")

    def test_multiple_assistant_turns(self):
        entries = [
            {"type": "human", "message": {"content": "q1"}},
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 1000,
                        "output_tokens": 500,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                },
            },
            {"type": "human", "message": {"content": "q2"}},
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 2000,
                        "output_tokens": 800,
                        "cache_read_input_tokens": 500,
                        "cache_creation_input_tokens": 0,
                    },
                },
            },
        ]
        path = self._write_jsonl(entries)
        result = uc.extract_session_usage(path)

        self.assertEqual(result["input_tokens"], 3000)
        self.assertEqual(result["output_tokens"], 1300)
        self.assertEqual(result["cache_read_tokens"], 500)
        self.assertEqual(result["assistant_turns"], 2)
        self.assertEqual(result["turn_count"], 4)

    def test_empty_transcript(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "empty.jsonl"
        path.write_text("")
        result = uc.extract_session_usage(path)

        self.assertEqual(result["total_tokens"], 0)
        self.assertEqual(result["turn_count"], 0)
        self.assertEqual(result["assistant_turns"], 0)
        self.assertEqual(result["model"], "sonnet")

    def test_nonexistent_file(self):
        path = Path("/tmp/nonexistent_session_xyz.jsonl")
        result = uc.extract_session_usage(path)
        self.assertEqual(result["total_tokens"], 0)
        self.assertEqual(result["turn_count"], 0)

    def test_malformed_json_lines_skipped(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "malformed.jsonl"
        with open(path, "w") as f:
            f.write('{"type": "human", "message": {"content": "hello"}}\n')
            f.write("this is not json\n")
            f.write('{"type": "assistant", "message": {"usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}}\n')
        result = uc.extract_session_usage(path)

        self.assertEqual(result["turn_count"], 2)  # malformed line skipped
        self.assertEqual(result["input_tokens"], 100)

    def test_missing_usage_in_assistant(self):
        entries = [
            {"type": "assistant", "message": {"content": "no usage data here"}},
        ]
        path = self._write_jsonl(entries)
        result = uc.extract_session_usage(path)

        self.assertEqual(result["turn_count"], 1)
        self.assertEqual(result["assistant_turns"], 0)
        self.assertEqual(result["total_tokens"], 0)

    def test_top_level_usage_fallback(self):
        """Test that top-level usage (non-assistant type) is also picked up."""
        entries = [
            {
                "type": "assistant",
                "usage": {
                    "input_tokens": 500,
                    "output_tokens": 200,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        ]
        path = self._write_jsonl(entries)
        result = uc.extract_session_usage(path)
        # The entry is type=assistant but usage is at top level (no message.usage)
        # Should fall back to top-level usage
        self.assertEqual(result["input_tokens"], 500)
        self.assertEqual(result["output_tokens"], 200)

    def test_session_id_from_filename(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "abc123def.jsonl"
        path.write_text("")
        result = uc.extract_session_usage(path)
        self.assertEqual(result["session_id"], "abc123def")

    def test_timestamps_extracted(self):
        entries = [
            {"type": "human", "timestamp": "2026-03-15T10:00:00Z"},
            {"type": "assistant", "timestamp": "2026-03-15T10:01:00Z",
             "message": {"usage": {"input_tokens": 100, "output_tokens": 50,
                                    "cache_read_input_tokens": 0,
                                    "cache_creation_input_tokens": 0}}},
        ]
        path = self._write_jsonl(entries)
        result = uc.extract_session_usage(path)
        self.assertEqual(result["first_timestamp"], "2026-03-15T10:00:00Z")
        self.assertEqual(result["last_timestamp"], "2026-03-15T10:01:00Z")


class TestDeriveProjectHash(unittest.TestCase):

    def test_standard_path(self):
        h = uc.derive_project_hash("/Users/matthewshields/Projects/Foo")
        self.assertEqual(h, "-Users-matthewshields-Projects-Foo")

    def test_trailing_slash_stripped(self):
        h = uc.derive_project_hash("/Users/matthewshields/Projects/Foo/")
        self.assertEqual(h, "-Users-matthewshields-Projects-Foo")


class TestListSessions(unittest.TestCase):
    """Test session discovery with temp directories mimicking Claude's layout."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        # Create a fake project and transcript structure
        self.project_dir = os.path.join(self._tmpdir, "project")
        os.makedirs(self.project_dir)
        project_hash = self.project_dir.replace("/", "-")
        self.transcript_dir = Path(self._tmpdir) / ".claude" / "projects" / project_hash
        self.transcript_dir.mkdir(parents=True)

        # Monkey-patch Path.home to return our tmpdir
        self._original_home = Path.home
        tmpdir = self._tmpdir
        Path.home = staticmethod(lambda: Path(tmpdir))

    def tearDown(self):
        Path.home = self._original_home

    def _write_session(self, session_id: str, entries: list[dict], mtime_offset_hours: int = 0):
        path = self.transcript_dir / f"{session_id}.jsonl"
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        # Set mtime to now minus offset
        now = datetime.now().timestamp()
        mtime = now - (mtime_offset_hours * 3600)
        os.utime(path, (mtime, mtime))
        return path

    def test_list_empty_project(self):
        sessions = uc.list_sessions(self.project_dir)
        self.assertEqual(sessions, [])

    def test_list_single_session(self):
        self._write_session("sess1", [
            {"type": "assistant", "message": {
                "model": "claude-sonnet-4",
                "usage": {"input_tokens": 100, "output_tokens": 50,
                          "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0}}},
        ])
        sessions = uc.list_sessions(self.project_dir)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "sess1")
        self.assertEqual(sessions[0]["input_tokens"], 100)
        self.assertIn("costs", sessions[0])
        self.assertIn("file_mtime", sessions[0])

    def test_list_sorted_by_mtime_descending(self):
        self._write_session("old", [
            {"type": "assistant", "message": {
                "usage": {"input_tokens": 10, "output_tokens": 5,
                          "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0}}},
        ], mtime_offset_hours=48)
        self._write_session("new", [
            {"type": "assistant", "message": {
                "usage": {"input_tokens": 20, "output_tokens": 10,
                          "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0}}},
        ], mtime_offset_hours=0)
        sessions = uc.list_sessions(self.project_dir)
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]["session_id"], "new")
        self.assertEqual(sessions[1]["session_id"], "old")

    def test_list_with_limit(self):
        for i in range(5):
            self._write_session(f"sess{i}", [
                {"type": "assistant", "message": {
                    "usage": {"input_tokens": 10, "output_tokens": 5,
                              "cache_read_input_tokens": 0,
                              "cache_creation_input_tokens": 0}}},
            ], mtime_offset_hours=i)
        sessions = uc.list_sessions(self.project_dir, limit=3)
        self.assertEqual(len(sessions), 3)

    def test_list_with_since_filter(self):
        # One session 2 hours ago, one 48 hours ago
        self._write_session("recent", [
            {"type": "assistant", "message": {
                "usage": {"input_tokens": 10, "output_tokens": 5,
                          "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0}}},
        ], mtime_offset_hours=2)
        self._write_session("old", [
            {"type": "assistant", "message": {
                "usage": {"input_tokens": 10, "output_tokens": 5,
                          "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0}}},
        ], mtime_offset_hours=48)

        since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
        sessions = uc.list_sessions(self.project_dir, since=since)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "recent")


class TestAggregateSessions(unittest.TestCase):

    def test_aggregate_empty(self):
        agg = uc.aggregate_sessions([])
        self.assertEqual(agg["session_count"], 0)
        self.assertEqual(agg["total_tokens"], 0)
        self.assertEqual(agg["total_cost"], 0.0)

    def test_aggregate_single(self):
        session = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_tokens": 200,
            "cache_create_tokens": 100,
            "total_tokens": 1800,
            "model": "sonnet",
            "costs": uc.cost_for_tokens(1000, 500, 200, 100, "sonnet"),
        }
        agg = uc.aggregate_sessions([session])
        self.assertEqual(agg["session_count"], 1)
        self.assertEqual(agg["total_tokens"], 1800)
        self.assertGreater(agg["total_cost"], 0)
        self.assertIn("sonnet", agg["by_model"])

    def test_aggregate_multi_model(self):
        s1 = {
            "input_tokens": 1000, "output_tokens": 500,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "total_tokens": 1500, "model": "sonnet",
            "costs": uc.cost_for_tokens(1000, 500, 0, 0, "sonnet"),
        }
        s2 = {
            "input_tokens": 2000, "output_tokens": 1000,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "total_tokens": 3000, "model": "opus",
            "costs": uc.cost_for_tokens(2000, 1000, 0, 0, "opus"),
        }
        agg = uc.aggregate_sessions([s1, s2])
        self.assertEqual(agg["session_count"], 2)
        self.assertEqual(agg["total_tokens"], 4500)
        self.assertIn("sonnet", agg["by_model"])
        self.assertIn("opus", agg["by_model"])
        self.assertEqual(agg["by_model"]["sonnet"]["session_count"], 1)
        self.assertEqual(agg["by_model"]["opus"]["session_count"], 1)


class TestFormatting(unittest.TestCase):

    def test_format_tokens(self):
        self.assertEqual(uc.format_tokens(0), "0")
        self.assertEqual(uc.format_tokens(1000), "1,000")
        self.assertEqual(uc.format_tokens(1_234_567), "1,234,567")

    def test_format_cost(self):
        self.assertEqual(uc.format_cost(0.0), "$0.00")
        self.assertEqual(uc.format_cost(1.5), "$1.50")
        self.assertEqual(uc.format_cost(0.003), "$0.00")
        self.assertEqual(uc.format_cost(15.999), "$16.00")

    def test_format_session_detail(self):
        usage = {
            "session_id": "abc123",
            "model": "sonnet",
            "input_tokens": 45230,
            "output_tokens": 12100,
            "cache_read_tokens": 89000,
            "cache_create_tokens": 15000,
            "total_tokens": 161330,
            "turn_count": 20,
            "assistant_turns": 10,
        }
        costs = uc.cost_for_tokens(45230, 12100, 89000, 15000, "sonnet")
        mtime = datetime(2026, 3, 15, 14, 30, tzinfo=timezone.utc)
        output = uc.format_session_detail(usage, costs, mtime)

        self.assertIn("Session: abc123", output)
        self.assertIn("Model: sonnet", output)
        self.assertIn("2026-03-15 14:30", output)
        self.assertIn("45,230", output)
        self.assertIn("12,100", output)
        self.assertIn("89,000", output)
        self.assertIn("15,000", output)
        self.assertIn("Est. cost:", output)

    def test_format_sessions_table_header(self):
        sessions = [
            {
                "session_id": "test1",
                "model": "sonnet",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "total_tokens": 150,
                "file_mtime": datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
                "costs": uc.cost_for_tokens(100, 50, 0, 0, "sonnet"),
            }
        ]
        output = uc.format_sessions_table(sessions, title="Test Table")
        self.assertIn("Test Table", output)
        self.assertIn("Session", output)
        self.assertIn("TOTAL", output)

    def test_format_aggregate(self):
        agg = {
            "session_count": 3,
            "input_tokens": 10000,
            "output_tokens": 5000,
            "cache_read_tokens": 2000,
            "cache_create_tokens": 1000,
            "total_tokens": 18000,
            "total_cost": 0.42,
            "by_model": {
                "sonnet": {"session_count": 2, "total_tokens": 12000, "total_cost": 0.30},
                "opus": {"session_count": 1, "total_tokens": 6000, "total_cost": 0.12},
            },
        }
        output = uc.format_aggregate(agg, title="Test Aggregate")
        self.assertIn("Test Aggregate", output)
        self.assertIn("3", output)
        self.assertIn("18,000", output)
        self.assertIn("$0.42", output)
        self.assertIn("sonnet", output)
        self.assertIn("opus", output)


class TestCLIParser(unittest.TestCase):

    def test_sessions_command(self):
        parser = uc.build_parser()
        args = parser.parse_args(["sessions", "--limit", "5"])
        self.assertEqual(args.command, "sessions")
        self.assertEqual(args.limit, 5)

    def test_session_command(self):
        parser = uc.build_parser()
        args = parser.parse_args(["session", "abc123"])
        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_id, "abc123")

    def test_today_command(self):
        parser = uc.build_parser()
        args = parser.parse_args(["today"])
        self.assertEqual(args.command, "today")

    def test_week_command(self):
        parser = uc.build_parser()
        args = parser.parse_args(["week"])
        self.assertEqual(args.command, "week")

    def test_project_command_with_path(self):
        parser = uc.build_parser()
        args = parser.parse_args(["project", "/some/path"])
        self.assertEqual(args.command, "project")
        self.assertEqual(args.path, "/some/path")

    def test_project_command_default_path(self):
        parser = uc.build_parser()
        args = parser.parse_args(["project"])
        self.assertEqual(args.command, "project")
        # Default is cwd
        self.assertEqual(args.path, os.getcwd())


if __name__ == "__main__":
    unittest.main()
