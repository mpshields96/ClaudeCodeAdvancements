"""Tests for context-monitor/hooks/post_compact.py — PostCompact hook."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestParsePayload(unittest.TestCase):
    """Tests for parsing the PostCompact hook payload."""

    def test_parse_valid_payload(self):
        from post_compact import parse_payload
        raw = json.dumps({
            "session_id": "abc123",
            "transcript_path": "/tmp/session.jsonl",
            "cwd": "/home/user/project",
            "hook_event_name": "PostCompact",
            "trigger": "auto",
            "compact_summary": "User was building a feature X..."
        })
        result = parse_payload(raw)
        self.assertEqual(result["session_id"], "abc123")
        self.assertEqual(result["trigger"], "auto")
        self.assertEqual(result["compact_summary"], "User was building a feature X...")

    def test_parse_empty_input(self):
        from post_compact import parse_payload
        result = parse_payload("")
        self.assertEqual(result["session_id"], "")
        self.assertEqual(result["trigger"], "unknown")
        self.assertEqual(result["compact_summary"], "")

    def test_parse_invalid_json(self):
        from post_compact import parse_payload
        result = parse_payload("not json {{{")
        self.assertEqual(result["session_id"], "")
        self.assertEqual(result["trigger"], "unknown")

    def test_parse_minimal_payload(self):
        from post_compact import parse_payload
        raw = json.dumps({"trigger": "manual"})
        result = parse_payload(raw)
        self.assertEqual(result["trigger"], "manual")
        self.assertEqual(result["session_id"], "")

    def test_parse_preserves_all_fields(self):
        from post_compact import parse_payload
        raw = json.dumps({
            "session_id": "sess-001",
            "transcript_path": "/path/to/transcript.jsonl",
            "cwd": "/cwd",
            "trigger": "auto",
            "compact_summary": "Summary here",
        })
        result = parse_payload(raw)
        self.assertEqual(result["transcript_path"], "/path/to/transcript.jsonl")
        self.assertEqual(result["cwd"], "/cwd")


class TestUpdateStateFile(unittest.TestCase):
    """Tests for updating the context health state file after compaction."""

    def test_update_existing_state(self):
        from post_compact import update_state_after_compact
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"zone": "red", "pct": 72.5, "tokens": 145000, "turns": 50}, f)
            f.flush()
            state_path = Path(f.name)

        try:
            update_state_after_compact(state_path, "auto", "sess-001")
            with open(state_path) as f:
                state = json.load(f)
            self.assertEqual(state["zone"], "green")
            self.assertEqual(state["pct"], 0)
            self.assertEqual(state["tokens"], 0)
            self.assertEqual(state["turns"], 0)
            self.assertTrue(state["last_compaction_auto"])
            self.assertIn("last_compaction_time", state)
            self.assertEqual(state["compaction_count"], 1)
        finally:
            os.unlink(state_path)

    def test_update_missing_state_file(self):
        from post_compact import update_state_after_compact
        state_path = Path(tempfile.mktemp(suffix=".json"))
        try:
            update_state_after_compact(state_path, "manual", "sess-002")
            self.assertTrue(state_path.exists())
            with open(state_path) as f:
                state = json.load(f)
            self.assertEqual(state["zone"], "green")
            self.assertFalse(state["last_compaction_auto"])
            self.assertEqual(state["compaction_count"], 1)
        finally:
            if state_path.exists():
                os.unlink(state_path)

    def test_increment_compaction_count(self):
        from post_compact import update_state_after_compact
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"zone": "red", "pct": 80, "compaction_count": 3}, f)
            f.flush()
            state_path = Path(f.name)

        try:
            update_state_after_compact(state_path, "auto", "sess-003")
            with open(state_path) as f:
                state = json.load(f)
            self.assertEqual(state["compaction_count"], 4)
        finally:
            os.unlink(state_path)

    def test_preserves_window_size(self):
        from post_compact import update_state_after_compact
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"zone": "critical", "pct": 90, "window": 1000000}, f)
            f.flush()
            state_path = Path(f.name)

        try:
            update_state_after_compact(state_path, "auto", "sess-004")
            with open(state_path) as f:
                state = json.load(f)
            self.assertEqual(state["window"], 1000000)
        finally:
            os.unlink(state_path)


class TestBuildRecoveryDigest(unittest.TestCase):
    """Tests for building the recovery file after compaction."""

    def test_builds_markdown(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest(
            trigger="auto",
            compact_summary="Building PostCompact hook for context-monitor",
            session_id="abc12345",
        )
        self.assertIn("COMPACT RECOVERY", result)
        self.assertIn("auto", result)
        self.assertIn("Building PostCompact hook", result)
        self.assertIn("abc12345", result)

    def test_manual_trigger_label(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest(
            trigger="manual",
            compact_summary="User ran /compact",
            session_id="xyz",
        )
        self.assertIn("manual", result)

    def test_empty_summary(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest(
            trigger="auto",
            compact_summary="",
            session_id="sess",
        )
        self.assertIn("COMPACT RECOVERY", result)
        self.assertIn("No summary available", result)

    def test_recovery_instructions_present(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest(
            trigger="auto",
            compact_summary="Working on feature X",
            session_id="sess",
        )
        self.assertIn("SESSION_STATE.md", result)
        self.assertIn("CLAUDE.md", result)

    def test_truncates_long_summary(self):
        from post_compact import build_recovery_digest
        long_summary = "x" * 2000
        result = build_recovery_digest(
            trigger="auto",
            compact_summary=long_summary,
            session_id="sess",
        )
        # Should truncate to something reasonable
        self.assertLess(len(result), 3000)


class TestWriteRecoveryFile(unittest.TestCase):
    """Tests for atomic write of recovery file."""

    def test_writes_file(self):
        from post_compact import write_recovery_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recovery.md"
            write_recovery_file(path, "# Recovery content")
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(), "# Recovery content")

    def test_overwrites_existing(self):
        from post_compact import write_recovery_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recovery.md"
            path.write_text("old content")
            write_recovery_file(path, "new content")
            self.assertEqual(path.read_text(), "new content")

    def test_creates_parent_dirs(self):
        from post_compact import write_recovery_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "recovery.md"
            write_recovery_file(path, "content")
            self.assertTrue(path.exists())


class TestLogCompactionEvent(unittest.TestCase):
    """Tests for logging compaction to self-learning journal."""

    def test_builds_event_dict(self):
        from post_compact import build_compaction_event
        event = build_compaction_event(
            trigger="auto",
            session_id="sess-001",
            compact_summary="Working on X",
            pre_compaction_state={"zone": "red", "pct": 82, "turns": 47},
        )
        self.assertEqual(event["event_type"], "compaction")
        self.assertEqual(event["domain"], "context_monitor")
        self.assertEqual(event["trigger"], "auto")
        self.assertEqual(event["session_id"], "sess-001")
        self.assertEqual(event["pre_zone"], "red")
        self.assertEqual(event["pre_pct"], 82)
        self.assertIn("timestamp", event)

    def test_event_with_unknown_state(self):
        from post_compact import build_compaction_event
        event = build_compaction_event(
            trigger="manual",
            session_id="sess-002",
            compact_summary="",
            pre_compaction_state={},
        )
        self.assertEqual(event["pre_zone"], "unknown")
        self.assertEqual(event["pre_pct"], 0)

    def test_append_to_journal(self):
        from post_compact import append_journal_event
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type":"test","old":"entry"}\n')
            f.flush()
            journal_path = Path(f.name)

        try:
            event = {"event_type": "compaction", "domain": "context_monitor", "trigger": "auto", "timestamp": "2026-03-19T00:00:00Z"}
            append_journal_event(journal_path, event)
            lines = journal_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 2)
            last = json.loads(lines[-1])
            self.assertEqual(last["event_type"], "compaction")
        finally:
            os.unlink(journal_path)

    def test_append_creates_file(self):
        from post_compact import append_journal_event
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / "journal.jsonl"
            event = {"event_type": "compaction", "domain": "context_monitor", "trigger": "manual"}
            append_journal_event(journal_path, event)
            self.assertTrue(journal_path.exists())
            line = json.loads(journal_path.read_text().strip())
            self.assertEqual(line["event_type"], "compaction")


class TestDisableEnvVar(unittest.TestCase):
    """Tests for disabling the hook via environment variable."""

    def test_disabled_returns_true(self):
        from post_compact import is_disabled
        with patch.dict(os.environ, {"CLAUDE_POSTCOMPACT_DISABLED": "1"}):
            self.assertTrue(is_disabled())

    def test_enabled_by_default(self):
        from post_compact import is_disabled
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_disabled())

    def test_not_disabled_when_zero(self):
        from post_compact import is_disabled
        with patch.dict(os.environ, {"CLAUDE_POSTCOMPACT_DISABLED": "0"}):
            self.assertFalse(is_disabled())


class TestConfigPaths(unittest.TestCase):
    """Tests for resolving config paths from environment."""

    def test_default_state_file(self):
        from post_compact import resolve_paths
        with patch.dict(os.environ, {}, clear=True):
            paths = resolve_paths()
            self.assertTrue(str(paths["state_file"]).endswith(".claude-context-health.json"))

    def test_custom_state_file(self):
        from post_compact import resolve_paths
        with patch.dict(os.environ, {"CLAUDE_CONTEXT_STATE_FILE": "/tmp/custom.json"}):
            paths = resolve_paths()
            self.assertEqual(str(paths["state_file"]), "/tmp/custom.json")

    def test_default_recovery_path(self):
        from post_compact import resolve_paths
        with patch.dict(os.environ, {}, clear=True):
            paths = resolve_paths()
            self.assertTrue(str(paths["recovery_file"]).endswith(".claude-compact-recovery.md"))

    def test_custom_recovery_path(self):
        from post_compact import resolve_paths
        with patch.dict(os.environ, {"CLAUDE_COMPACT_RECOVERY_PATH": "/tmp/recovery.md"}):
            paths = resolve_paths()
            self.assertEqual(str(paths["recovery_file"]), "/tmp/recovery.md")


# ---------------------------------------------------------------------------
# Snapshot integration tests (CTX-8 PreCompact ↔ PostCompact)
# ---------------------------------------------------------------------------

class TestReadSnapshot(unittest.TestCase):
    """Tests for reading and consuming PreCompact snapshots."""

    def test_reads_valid_snapshot(self):
        from post_compact import read_snapshot
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "version": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "s1",
                "git_status": ["M file.py"],
                "todays_tasks_todos": ["Task A [TODO]"],
                "context_health": {"zone": "red", "pct": 72},
            }, f)
            path = Path(f.name)
        result = read_snapshot(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["session_id"], "s1")
        self.assertEqual(result["git_status"], ["M file.py"])
        # File should be deleted after reading
        self.assertFalse(path.exists())

    def test_returns_none_for_missing_file(self):
        from post_compact import read_snapshot
        result = read_snapshot(Path("/nonexistent/snapshot.json"))
        self.assertIsNone(result)

    def test_returns_none_for_corrupt_json(self):
        from post_compact import read_snapshot
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{corrupt json")
            path = Path(f.name)
        result = read_snapshot(path)
        self.assertIsNone(result)
        # Corrupt file should be cleaned up
        self.assertFalse(path.exists())

    def test_returns_none_for_stale_snapshot(self):
        from post_compact import read_snapshot
        # Create snapshot with timestamp 2 hours ago
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "version": 1,
                "timestamp": old_time,
                "session_id": "old",
            }, f)
            path = Path(f.name)
        result = read_snapshot(path)
        self.assertIsNone(result)
        self.assertFalse(path.exists())

    def test_returns_none_for_wrong_version(self):
        from post_compact import read_snapshot
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "version": 99,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, f)
            path = Path(f.name)
        result = read_snapshot(path)
        self.assertIsNone(result)

    def test_handles_missing_timestamp_gracefully(self):
        from post_compact import read_snapshot
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"version": 1}, f)
            path = Path(f.name)
        result = read_snapshot(path)
        # No timestamp means no staleness check — should still work
        self.assertIsNotNone(result)
        self.assertFalse(path.exists())


class TestBuildRecoveryDigestFromSnapshot(unittest.TestCase):
    """Tests for the snapshot-enhanced recovery digest."""

    def _make_snapshot(self, **overrides):
        base = {
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": "test-session",
            "cwd": "/test/project",
            "chat_role": "desktop",
            "context_health": {"zone": "red", "pct": 72, "tokens": 144000, "turns": 45, "window": 200000},
            "git_status": ["M  hooks/pre_compact.py", "?? tests/test_pre_compact.py"],
            "git_diff_stat": "2 files changed, 200 insertions(+), 5 deletions(-)",
            "todays_tasks_todos": ["10A. Design Protocol [TODO]", "10B. Build Protection [TODO]"],
            "session_header": "Session 243 | Chat 10 | 2026-03-31",
            "anchor_content": "Zone: red (72% of 200k tokens)",
        }
        base.update(overrides)
        return base

    def test_includes_git_status(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot()
        digest = build_recovery_digest_from_snapshot("auto", "summary", "s1", snapshot)
        self.assertIn("pre_compact.py", digest)
        self.assertIn("test_pre_compact.py", digest)
        self.assertIn("Files Modified", digest)

    def test_includes_tasks(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot()
        digest = build_recovery_digest_from_snapshot("auto", "summary", "s1", snapshot)
        self.assertIn("10A. Design Protocol", digest)
        self.assertIn("10B. Build Protection", digest)
        self.assertIn("Current Tasks", digest)

    def test_includes_context_health(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot()
        digest = build_recovery_digest_from_snapshot("auto", "summary", "s1", snapshot)
        self.assertIn("red zone", digest)
        self.assertIn("72%", digest)

    def test_includes_session_header(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot()
        digest = build_recovery_digest_from_snapshot("auto", "summary", "s1", snapshot)
        self.assertIn("Session 243", digest)

    def test_includes_chat_role(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot()
        digest = build_recovery_digest_from_snapshot("auto", "summary", "s1", snapshot)
        self.assertIn("desktop", digest)

    def test_includes_recovery_steps(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot()
        digest = build_recovery_digest_from_snapshot("auto", "summary", "s1", snapshot)
        self.assertIn("Re-read `CLAUDE.md`", digest)
        self.assertIn("git diff", digest)

    def test_handles_empty_snapshot_fields(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot(
            git_status=[], todays_tasks_todos=[], context_health={},
            session_header="", chat_role="", cwd=""
        )
        digest = build_recovery_digest_from_snapshot("manual", "", "s1", snapshot)
        # Should still produce valid digest without crashing
        self.assertIn("Recovery Steps", digest)
        self.assertNotIn("Files Modified", digest)  # No files = no section

    def test_truncates_long_summary(self):
        from post_compact import build_recovery_digest_from_snapshot, MAX_SUMMARY_LEN
        snapshot = self._make_snapshot()
        long_summary = "x" * (MAX_SUMMARY_LEN + 500)
        digest = build_recovery_digest_from_snapshot("auto", long_summary, "s1", snapshot)
        self.assertIn("...", digest)

    def test_snapshot_enhanced_marker(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot()
        digest = build_recovery_digest_from_snapshot("auto", "test", "s1", snapshot)
        self.assertIn("snapshot-enhanced", digest)

    def test_manual_trigger_label(self):
        from post_compact import build_recovery_digest_from_snapshot
        snapshot = self._make_snapshot()
        digest = build_recovery_digest_from_snapshot("manual", "test", "s1", snapshot)
        self.assertIn("manual (/compact)", digest)


class TestResolvePathsWithSnapshot(unittest.TestCase):
    """Tests for snapshot path resolution."""

    def test_default_snapshot_path(self):
        from post_compact import resolve_paths
        with patch.dict(os.environ, {}, clear=True):
            paths = resolve_paths()
            self.assertTrue(str(paths["snapshot_file"]).endswith(".claude-compaction-snapshot.json"))

    def test_custom_snapshot_path(self):
        from post_compact import resolve_paths
        with patch.dict(os.environ, {"CLAUDE_COMPACTION_SNAPSHOT_PATH": "/tmp/snap.json"}):
            paths = resolve_paths()
            self.assertEqual(str(paths["snapshot_file"]), "/tmp/snap.json")


if __name__ == "__main__":
    unittest.main()
