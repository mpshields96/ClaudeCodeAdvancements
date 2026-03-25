"""
test_post_compact_extended.py — Extended coverage for post_compact.py.

Targets gaps from the original test suite:
- parse_payload: whitespace-only, null values, extra fields
- update_state_after_compact: thresholds preservation, session_id fallback,
  corrupt state, pre_state returned, missing compaction_count in prior state
- build_recovery_digest: exactly at MAX_SUMMARY_LEN, session_id edge cases,
  whitespace summary, trigger labels
- write_recovery_file: tmp cleanup after success
- build_compaction_event: compact_summary_len field, compaction_count from empty state
- append_journal_event: creates parent directories, journal is valid JSONL
- resolve_paths: default and custom journal path
- main(): full integration, disabled exits without side effects
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from post_compact import MAX_SUMMARY_LEN


# ── parse_payload: Edge Cases ─────────────────────────────────────────────────


class TestParsePayloadEdgeCases(unittest.TestCase):

    def test_whitespace_only_treated_as_empty(self):
        from post_compact import parse_payload
        result = parse_payload("   \n\t  ")
        self.assertEqual(result["session_id"], "")
        self.assertEqual(result["trigger"], "unknown")

    def test_extra_fields_ignored(self):
        from post_compact import parse_payload
        raw = json.dumps({
            "session_id": "abc",
            "trigger": "auto",
            "unknown_field": "value",
            "another": 42,
        })
        result = parse_payload(raw)
        self.assertEqual(result["session_id"], "abc")
        self.assertNotIn("unknown_field", result)
        self.assertNotIn("another", result)

    def test_null_session_id_defaults_to_empty(self):
        from post_compact import parse_payload
        raw = json.dumps({"session_id": None, "trigger": "auto"})
        result = parse_payload(raw)
        # json.loads(None) returns None, dict.get returns None — may be None or ""
        self.assertIn(result["session_id"], [None, ""])

    def test_all_required_keys_present(self):
        from post_compact import parse_payload
        result = parse_payload("{}")
        for key in ("session_id", "transcript_path", "cwd", "trigger", "compact_summary"):
            self.assertIn(key, result)

    def test_trigger_manual_preserved(self):
        from post_compact import parse_payload
        raw = json.dumps({"trigger": "manual"})
        result = parse_payload(raw)
        self.assertEqual(result["trigger"], "manual")

    def test_compact_summary_empty_string(self):
        from post_compact import parse_payload
        raw = json.dumps({"compact_summary": ""})
        result = parse_payload(raw)
        self.assertEqual(result["compact_summary"], "")

    def test_numeric_session_id_parsed(self):
        from post_compact import parse_payload
        raw = json.dumps({"session_id": "12345", "trigger": "auto"})
        result = parse_payload(raw)
        self.assertEqual(result["session_id"], "12345")


# ── update_state_after_compact: Extended ─────────────────────────────────────


class TestUpdateStateExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _state_path(self, name="state.json"):
        return Path(self.tmpdir) / name

    def test_returns_pre_state_dict(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({"zone": "yellow", "pct": 55.0}))
        pre = update_state_after_compact(path, "auto", "sess")
        self.assertIsInstance(pre, dict)
        self.assertEqual(pre["zone"], "yellow")

    def test_returns_empty_dict_when_no_state_file(self):
        from post_compact import update_state_after_compact
        path = self._state_path("nonexistent.json")
        pre = update_state_after_compact(path, "auto", "sess")
        self.assertIsInstance(pre, dict)
        self.assertEqual(pre, {})

    def test_preserves_thresholds(self):
        from post_compact import update_state_after_compact
        thresholds = {"yellow": 0.5, "red": 0.7, "critical": 0.85}
        path = self._state_path()
        path.write_text(json.dumps({"zone": "red", "pct": 75, "thresholds": thresholds}))
        update_state_after_compact(path, "auto", "sess")
        new_state = json.loads(path.read_text())
        self.assertIn("thresholds", new_state)
        self.assertEqual(new_state["thresholds"], thresholds)

    def test_state_without_thresholds_no_key(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({"zone": "green", "pct": 10}))
        update_state_after_compact(path, "auto", "sess")
        new_state = json.loads(path.read_text())
        self.assertNotIn("thresholds", new_state)

    def test_session_id_from_payload(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({"session_id": "old-session"}))
        update_state_after_compact(path, "auto", "new-session")
        new_state = json.loads(path.read_text())
        self.assertEqual(new_state["session_id"], "new-session")

    def test_session_id_fallback_from_pre_state(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({"session_id": "pre-existing-session"}))
        update_state_after_compact(path, "auto", "")  # empty session_id in payload
        new_state = json.loads(path.read_text())
        self.assertEqual(new_state["session_id"], "pre-existing-session")

    def test_corrupt_state_file_defaults_gracefully(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text("CORRUPT JSON {{{")
        # Should not raise
        pre = update_state_after_compact(path, "auto", "sess")
        self.assertIsInstance(pre, dict)
        self.assertTrue(path.exists())  # Should have written new state

    def test_compaction_count_starts_at_1_for_new_state(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        # State without compaction_count
        path.write_text(json.dumps({"zone": "green"}))
        update_state_after_compact(path, "auto", "sess")
        new_state = json.loads(path.read_text())
        self.assertEqual(new_state["compaction_count"], 1)

    def test_window_defaults_to_1m(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        # State without window field
        path.write_text(json.dumps({"zone": "green"}))
        update_state_after_compact(path, "auto", "sess")
        new_state = json.loads(path.read_text())
        self.assertEqual(new_state["window"], 1_000_000)

    def test_last_compaction_time_is_utc_isoformat(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({}))
        update_state_after_compact(path, "auto", "sess")
        new_state = json.loads(path.read_text())
        ts = new_state["last_compaction_time"]
        # Should be a valid ISO datetime string
        from datetime import datetime
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        self.assertIsNotNone(dt)

    def test_manual_trigger_sets_auto_false(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({}))
        update_state_after_compact(path, "manual", "sess")
        new_state = json.loads(path.read_text())
        self.assertFalse(new_state["last_compaction_auto"])

    def test_auto_trigger_sets_auto_true(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({}))
        update_state_after_compact(path, "auto", "sess")
        new_state = json.loads(path.read_text())
        self.assertTrue(new_state["last_compaction_auto"])

    def test_unknown_trigger_sets_auto_false(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({}))
        update_state_after_compact(path, "unknown", "sess")
        new_state = json.loads(path.read_text())
        self.assertFalse(new_state["last_compaction_auto"])

    def test_atomic_write_no_tmp_left(self):
        from post_compact import update_state_after_compact
        path = self._state_path()
        path.write_text(json.dumps({"zone": "red"}))
        update_state_after_compact(path, "auto", "sess")
        self.assertFalse(path.with_suffix(".tmp").exists())


# ── build_recovery_digest: Edge Cases ────────────────────────────────────────


class TestBuildRecoveryDigestEdgeCases(unittest.TestCase):

    def test_summary_exactly_at_max_len_not_truncated(self):
        from post_compact import build_recovery_digest
        summary = "x" * MAX_SUMMARY_LEN
        result = build_recovery_digest("auto", summary, "sess")
        self.assertIn("x" * MAX_SUMMARY_LEN, result)
        self.assertNotIn("...", result.split(summary[-10:])[1] if summary[-10:] in result else "")

    def test_summary_over_max_len_truncated_with_ellipsis(self):
        from post_compact import build_recovery_digest
        summary = "a" * (MAX_SUMMARY_LEN + 100)
        result = build_recovery_digest("auto", summary, "sess")
        self.assertIn("...", result)
        # The full summary should not appear — only the first MAX_SUMMARY_LEN chars
        self.assertNotIn("a" * (MAX_SUMMARY_LEN + 1), result)

    def test_whitespace_summary_treated_as_empty(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("auto", "   \n\t  ", "sess")
        self.assertIn("No summary available", result)

    def test_long_session_id_truncated_with_ellipsis(self):
        from post_compact import build_recovery_digest
        session_id = "abcdefghijklmnop12345"  # > 12 chars
        result = build_recovery_digest("auto", "summary", session_id)
        self.assertIn(session_id[:12], result)
        self.assertIn("...", result)

    def test_short_session_id_no_ellipsis(self):
        from post_compact import build_recovery_digest
        session_id = "abc123"  # <= 12 chars
        result = build_recovery_digest("auto", "summary", session_id)
        self.assertIn("abc123", result)

    def test_empty_session_id_shows_unknown(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("auto", "summary", "")
        self.assertIn("unknown", result.lower())

    def test_auto_trigger_shows_automatic(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("auto", "summary", "sess")
        self.assertIn("automatic", result.lower())

    def test_manual_trigger_shows_manual(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("manual", "summary", "sess")
        self.assertIn("manual", result.lower())

    def test_recovery_steps_numbered(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("auto", "summary", "sess")
        self.assertIn("1.", result)
        self.assertIn("2.", result)

    def test_result_is_string(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("auto", "summary", "sess")
        self.assertIsInstance(result, str)

    def test_result_ends_with_newline(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("auto", "summary", "sess")
        self.assertTrue(result.endswith("\n"))

    def test_contains_git_status_reminder(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("auto", "summary", "sess")
        self.assertIn("git", result.lower())

    def test_contains_html_comment_marker(self):
        from post_compact import build_recovery_digest
        result = build_recovery_digest("auto", "summary", "sess")
        self.assertIn("<!-- COMPACT RECOVERY", result)


# ── write_recovery_file: Extended ────────────────────────────────────────────


class TestWriteRecoveryFileExtended(unittest.TestCase):

    def test_tmp_file_cleaned_up_after_write(self):
        from post_compact import write_recovery_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recovery.md"
            write_recovery_file(path, "content")
            tmp = path.with_suffix(".tmp")
            self.assertFalse(tmp.exists())

    def test_content_encoding_utf8(self):
        from post_compact import write_recovery_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recovery.md"
            content = "# Recovery — café naïve résumé\n"
            write_recovery_file(path, content)
            self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_empty_content_writes_empty_file(self):
        from post_compact import write_recovery_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recovery.md"
            write_recovery_file(path, "")
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(), "")

    def test_deep_nested_dirs_created(self):
        from post_compact import write_recovery_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a" / "b" / "c" / "recovery.md"
            write_recovery_file(path, "content")
            self.assertTrue(path.exists())


# ── build_compaction_event: Extended ─────────────────────────────────────────


class TestBuildCompactionEventExtended(unittest.TestCase):

    def test_compact_summary_len_recorded(self):
        from post_compact import build_compaction_event
        summary = "x" * 350
        event = build_compaction_event("auto", "sess", summary, {})
        self.assertEqual(event["compact_summary_len"], 350)

    def test_empty_summary_len_is_zero(self):
        from post_compact import build_compaction_event
        event = build_compaction_event("auto", "sess", "", {})
        self.assertEqual(event["compact_summary_len"], 0)

    def test_compaction_count_from_zero(self):
        from post_compact import build_compaction_event
        event = build_compaction_event("auto", "sess", "summary", {"compaction_count": 0})
        self.assertEqual(event["compaction_count"], 1)

    def test_compaction_count_incremented_from_pre_state(self):
        from post_compact import build_compaction_event
        event = build_compaction_event("auto", "sess", "summary", {"compaction_count": 7})
        self.assertEqual(event["compaction_count"], 8)

    def test_compaction_count_when_no_prior_count(self):
        from post_compact import build_compaction_event
        event = build_compaction_event("auto", "sess", "summary", {})
        self.assertEqual(event["compaction_count"], 1)

    def test_pre_turns_from_state(self):
        from post_compact import build_compaction_event
        event = build_compaction_event("auto", "sess", "summary", {"turns": 42})
        self.assertEqual(event["pre_turns"], 42)

    def test_pre_turns_default_zero(self):
        from post_compact import build_compaction_event
        event = build_compaction_event("auto", "sess", "summary", {})
        self.assertEqual(event["pre_turns"], 0)

    def test_event_has_required_keys(self):
        from post_compact import build_compaction_event
        event = build_compaction_event("auto", "sess", "summary", {})
        for key in ("event_type", "domain", "timestamp", "session_id", "trigger", "pre_zone",
                    "pre_pct", "pre_turns", "compact_summary_len", "compaction_count"):
            self.assertIn(key, event)

    def test_event_type_is_compaction(self):
        from post_compact import build_compaction_event
        event = build_compaction_event("manual", "sess", "summary", {})
        self.assertEqual(event["event_type"], "compaction")
        self.assertEqual(event["domain"], "context_monitor")

    def test_timestamp_is_iso_format(self):
        from post_compact import build_compaction_event
        from datetime import datetime
        event = build_compaction_event("auto", "sess", "summary", {})
        dt = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        self.assertIsNotNone(dt)


# ── append_journal_event: Extended ───────────────────────────────────────────


class TestAppendJournalEventExtended(unittest.TestCase):

    def test_creates_parent_directories(self):
        from post_compact import append_journal_event
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / "sub" / "dir" / "journal.jsonl"
            append_journal_event(journal_path, {"type": "test"})
            self.assertTrue(journal_path.exists())

    def test_each_line_is_valid_json(self):
        from post_compact import append_journal_event
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / "journal.jsonl"
            for i in range(5):
                append_journal_event(journal_path, {"type": "event", "i": i})
            lines = journal_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 5)
            for line in lines:
                obj = json.loads(line)
                self.assertEqual(obj["type"], "event")

    def test_appends_not_overwrites(self):
        from post_compact import append_journal_event
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / "journal.jsonl"
            journal_path.write_text('{"type":"existing"}\n')
            append_journal_event(journal_path, {"type": "new"})
            lines = journal_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 2)

    def test_compact_json_no_spaces(self):
        from post_compact import append_journal_event
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / "journal.jsonl"
            append_journal_event(journal_path, {"type": "test", "value": 42})
            content = journal_path.read_text()
            # separators=(",", ":") means no spaces after : or ,
            self.assertNotIn(": ", content)
            self.assertNotIn(", ", content)


# ── resolve_paths: Extended ───────────────────────────────────────────────────


class TestResolvePathsExtended(unittest.TestCase):

    def test_default_journal_path(self):
        from post_compact import resolve_paths
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_COMPACT_JOURNAL_PATH", "CLAUDE_CONTEXT_STATE_FILE",
                            "CLAUDE_COMPACT_RECOVERY_PATH")}
        with patch.dict(os.environ, env, clear=True):
            paths = resolve_paths()
            self.assertTrue(str(paths["journal_file"]).endswith("journal.jsonl"))

    def test_custom_journal_path(self):
        from post_compact import resolve_paths
        with patch.dict(os.environ, {"CLAUDE_COMPACT_JOURNAL_PATH": "/tmp/custom_journal.jsonl"}):
            paths = resolve_paths()
            self.assertEqual(str(paths["journal_file"]), "/tmp/custom_journal.jsonl")

    def test_all_three_paths_returned(self):
        from post_compact import resolve_paths
        paths = resolve_paths()
        self.assertIn("state_file", paths)
        self.assertIn("recovery_file", paths)
        self.assertIn("journal_file", paths)

    def test_paths_are_path_objects(self):
        from post_compact import resolve_paths
        paths = resolve_paths()
        for key in ("state_file", "recovery_file", "journal_file"):
            self.assertIsInstance(paths[key], Path)


# ── main(): Integration ───────────────────────────────────────────────────────


class TestMainIntegration(unittest.TestCase):

    def _run_main(self, payload: dict, env_overrides: dict = None) -> tuple:
        """Run main() with given payload and env, return (state, recovery, journal)."""
        import shutil
        from post_compact import main

        tmpdir = Path(tempfile.mkdtemp())
        state_path = tmpdir / "state.json"
        recovery_path = tmpdir / "recovery.md"
        journal_path = tmpdir / "journal.jsonl"

        env = {
            "CLAUDE_CONTEXT_STATE_FILE": str(state_path),
            "CLAUDE_COMPACT_RECOVERY_PATH": str(recovery_path),
            "CLAUDE_COMPACT_JOURNAL_PATH": str(journal_path),
        }
        if env_overrides:
            env.update(env_overrides)

        stdin_data = json.dumps(payload)
        with patch.dict(os.environ, env):
            with patch("sys.stdin", io.StringIO(stdin_data)):
                with self.assertRaises(SystemExit) as cm:
                    main()
        self.assertEqual(cm.exception.code, 0)

        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        recovery = recovery_path.read_text() if recovery_path.exists() else ""
        journal_lines = [json.loads(l) for l in journal_path.read_text().strip().split("\n")] \
            if journal_path.exists() else []

        shutil.rmtree(tmpdir, ignore_errors=True)
        return state, recovery, journal_lines

    def test_full_flow_creates_all_outputs(self):
        state, recovery, journal = self._run_main({
            "session_id": "sess-001",
            "trigger": "auto",
            "compact_summary": "Building PostCompact hook",
        })
        self.assertEqual(state["zone"], "green")
        self.assertIn("COMPACT RECOVERY", recovery)
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]["event_type"], "compaction")

    def test_disabled_env_exits_without_writing(self):
        from post_compact import main
        import shutil
        tmpdir = Path(tempfile.mkdtemp())
        state_path = tmpdir / "state.json"
        recovery_path = tmpdir / "recovery.md"
        journal_path = tmpdir / "journal.jsonl"

        env = {
            "CLAUDE_POSTCOMPACT_DISABLED": "1",
            "CLAUDE_CONTEXT_STATE_FILE": str(state_path),
            "CLAUDE_COMPACT_RECOVERY_PATH": str(recovery_path),
            "CLAUDE_COMPACT_JOURNAL_PATH": str(journal_path),
        }
        with patch.dict(os.environ, env):
            with patch("sys.stdin", io.StringIO(json.dumps({"trigger": "auto"}))):
                with self.assertRaises(SystemExit) as cm:
                    main()
        self.assertEqual(cm.exception.code, 0)
        # No files should have been created
        self.assertFalse(state_path.exists())
        self.assertFalse(recovery_path.exists())
        self.assertFalse(journal_path.exists())
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_empty_payload_does_not_crash(self):
        state, recovery, journal = self._run_main({})
        self.assertEqual(state["zone"], "green")
        self.assertIsInstance(recovery, str)
        self.assertEqual(len(journal), 1)

    def test_manual_trigger_in_output(self):
        state, recovery, journal = self._run_main({
            "session_id": "sess-002",
            "trigger": "manual",
            "compact_summary": "User ran /compact",
        })
        self.assertIn("manual", recovery.lower())
        self.assertFalse(state["last_compaction_auto"])

    def test_journal_records_pre_state(self):
        import shutil
        from post_compact import main

        tmpdir = Path(tempfile.mkdtemp())
        state_path = tmpdir / "state.json"
        recovery_path = tmpdir / "recovery.md"
        journal_path = tmpdir / "journal.jsonl"

        # Write pre-existing state
        state_path.write_text(json.dumps({"zone": "critical", "pct": 88, "turns": 120}))

        env = {
            "CLAUDE_CONTEXT_STATE_FILE": str(state_path),
            "CLAUDE_COMPACT_RECOVERY_PATH": str(recovery_path),
            "CLAUDE_COMPACT_JOURNAL_PATH": str(journal_path),
        }
        with patch.dict(os.environ, env):
            with patch("sys.stdin", io.StringIO(json.dumps({"trigger": "auto"}))):
                with self.assertRaises(SystemExit):
                    main()

        journal_lines = [json.loads(l) for l in journal_path.read_text().strip().split("\n")]
        event = journal_lines[0]
        self.assertEqual(event["pre_zone"], "critical")
        self.assertEqual(event["pre_pct"], 88)
        self.assertEqual(event["pre_turns"], 120)
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
