#!/usr/bin/env python3
"""
test_phase2_validator.py — Tests for phase2_validator.py

Tests cover:
1. count_queue_messages — raw JSONL message counting
2. validate_queue_integrity — structural integrity of the queue
3. validate_pre_launch_pipeline — pre-launch check + crash recovery end-to-end
4. validate_crash_recovery_integration — crash_recovery + chat_detector together
5. run_phase2_validation — full integrated validation report
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import phase2_validator as pv
import cca_internal_queue as ciq


# ── Helpers ──────────────────────────────────────────────────────────────────

def _write_queue(path: str, messages: list) -> None:
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


def _make_scope_claim(sender="cli1", subject="some-scope", minutes_ago=5) -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return {
        "id": f"cca_test_{sender}_{subject[:8]}",
        "sender": sender,
        "target": "desktop",
        "subject": subject,
        "body": "claimed",
        "priority": "medium",
        "category": "scope_claim",
        "status": "unread",
        "created_at": ts,
        "read_at": None,
    }


def _make_process(pid=12345, chat_id="cli1", cca=True) -> dict:
    return {"pid": pid, "command": "claude", "chat_id": chat_id, "cca_project": cca}


# ── count_queue_messages ─────────────────────────────────────────────────────

class TestCountQueueMessages(unittest.TestCase):

    def test_empty_file_returns_zero(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            result = pv.count_queue_messages(path)
            self.assertEqual(result["total"], 0)
            self.assertEqual(result["valid"], 0)
            self.assertEqual(result["corrupt"], 0)
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_zero(self):
        result = pv.count_queue_messages("/tmp/does_not_exist_xyz.jsonl")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["valid"], 0)
        self.assertEqual(result["corrupt"], 0)

    def test_counts_valid_json_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
            for i in range(5):
                f.write(json.dumps({"id": i, "data": "x"}) + "\n")
        try:
            result = pv.count_queue_messages(path)
            self.assertEqual(result["valid"], 5)
            self.assertEqual(result["corrupt"], 0)
            self.assertEqual(result["total"], 5)
        finally:
            os.unlink(path)

    def test_counts_corrupt_lines_separately(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
            f.write(json.dumps({"id": 1}) + "\n")
            f.write("this is not json\n")
            f.write(json.dumps({"id": 2}) + "\n")
            f.write("{broken\n")
        try:
            result = pv.count_queue_messages(path)
            self.assertEqual(result["valid"], 2)
            self.assertEqual(result["corrupt"], 2)
            self.assertEqual(result["total"], 4)
        finally:
            os.unlink(path)

    def test_ignores_blank_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
            f.write(json.dumps({"id": 1}) + "\n")
            f.write("\n")
            f.write("   \n")
            f.write(json.dumps({"id": 2}) + "\n")
        try:
            result = pv.count_queue_messages(path)
            self.assertEqual(result["valid"], 2)
            self.assertEqual(result["corrupt"], 0)
        finally:
            os.unlink(path)


# ── validate_queue_integrity ─────────────────────────────────────────────────

class TestValidateQueueIntegrity(unittest.TestCase):

    def test_empty_queue_is_healthy(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            result = pv.validate_queue_integrity(path)
            self.assertEqual(result["status"], "healthy")
            self.assertEqual(result["total_messages"], 0)
            self.assertEqual(result["active_scopes"], 0)
        finally:
            os.unlink(path)

    def test_detects_active_scope_claims(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            _write_queue(path, [_make_scope_claim("cli1", "my-feature")])
            result = pv.validate_queue_integrity(path)
            self.assertGreaterEqual(result["active_scopes"], 1)
        finally:
            os.unlink(path)

    def test_detects_corrupt_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
            f.write(json.dumps({"id": "x1", "sender": "cli1"}) + "\n")
            f.write("CORRUPT LINE\n")
        try:
            result = pv.validate_queue_integrity(path)
            self.assertGreater(result["corrupt_lines"], 0)
            self.assertEqual(result["status"], "warning")
        finally:
            os.unlink(path)

    def test_counts_total_messages_correctly(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            msgs = [_make_scope_claim("cli1", f"scope-{i}") for i in range(7)]
            _write_queue(path, msgs)
            result = pv.validate_queue_integrity(path)
            self.assertEqual(result["total_messages"], 7)
        finally:
            os.unlink(path)


# ── validate_pre_launch_pipeline ─────────────────────────────────────────────

class TestValidatePreLaunchPipeline(unittest.TestCase):

    def test_safe_launch_when_no_existing_process(self):
        with patch("phase2_validator._get_processes", return_value=[]):
            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
                path = f.name
            try:
                result = pv.validate_pre_launch_pipeline("cli1", path)
                self.assertTrue(result["pre_launch_safe"])
                self.assertEqual(result["status"], "ready")
            finally:
                os.unlink(path)

    def test_blocked_when_existing_process(self):
        existing = [_make_process(pid=99, chat_id="cli1", cca=True)]
        with patch("phase2_validator._get_processes", return_value=existing):
            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
                path = f.name
            try:
                result = pv.validate_pre_launch_pipeline("cli1", path)
                self.assertFalse(result["pre_launch_safe"])
                self.assertEqual(result["status"], "blocked")
            finally:
                os.unlink(path)

    def test_detects_orphaned_scope_with_no_process(self):
        """Scope claimed but no process running → crash detected in pipeline."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            _write_queue(path, [_make_scope_claim("cli1", "orphaned-scope")])
            with patch("phase2_validator._get_processes", return_value=[]):
                result = pv.validate_pre_launch_pipeline("cli2", path)
                # cli1 scope exists but no cli1 process — should flag crash
                self.assertGreaterEqual(result["crashed_workers_detected"], 1)
        finally:
            os.unlink(path)

    def test_no_crash_when_process_matches_scope(self):
        """Scope claimed AND process running → no crash."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            _write_queue(path, [_make_scope_claim("cli1", "active-scope")])
            running = [_make_process(pid=42, chat_id="cli1", cca=True)]
            with patch("phase2_validator._get_processes", return_value=running):
                result = pv.validate_pre_launch_pipeline("cli2", path)
                self.assertEqual(result["crashed_workers_detected"], 0)
        finally:
            os.unlink(path)


# ── validate_crash_recovery_integration ─────────────────────────────────────

class TestValidateCrashRecoveryIntegration(unittest.TestCase):

    def test_clean_state_returns_clean_status(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch("phase2_validator._get_processes", return_value=[]):
                result = pv.validate_crash_recovery_integration(path)
                self.assertEqual(result["status"], "clean")
                self.assertEqual(result["orphaned_scopes"], 0)
        finally:
            os.unlink(path)

    def test_detects_orphaned_scope(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            _write_queue(path, [_make_scope_claim("cli1", "lost-scope")])
            # No processes running
            with patch("phase2_validator._get_processes", return_value=[]):
                result = pv.validate_crash_recovery_integration(path)
                self.assertEqual(result["status"], "recovered")
                self.assertGreater(result["orphaned_scopes"], 0)
        finally:
            os.unlink(path)

    def test_no_false_positive_for_active_worker(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            _write_queue(path, [_make_scope_claim("cli2", "real-scope")])
            running = [_make_process(pid=77, chat_id="cli2", cca=True)]
            with patch("phase2_validator._get_processes", return_value=running):
                result = pv.validate_crash_recovery_integration(path)
                self.assertEqual(result["orphaned_scopes"], 0)
        finally:
            os.unlink(path)


# ── run_phase2_validation ────────────────────────────────────────────────────

class TestRunPhase2Validation(unittest.TestCase):

    def test_returns_required_keys(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch("phase2_validator._get_processes", return_value=[]):
                result = pv.run_phase2_validation("cli1", path)
            required = {
                "status", "chat_id", "queue_counts",
                "pre_launch", "crash_recovery",
                "summary", "timestamp",
            }
            self.assertTrue(required.issubset(result.keys()),
                            f"Missing keys: {required - result.keys()}")
        finally:
            os.unlink(path)

    def test_clean_system_returns_ready_status(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch("phase2_validator._get_processes", return_value=[]):
                result = pv.run_phase2_validation("cli1", path)
            self.assertEqual(result["status"], "ready")
        finally:
            os.unlink(path)

    def test_blocked_pre_launch_sets_status(self):
        existing = [_make_process(pid=55, chat_id="cli1", cca=True)]
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch("phase2_validator._get_processes", return_value=existing):
                result = pv.run_phase2_validation("cli1", path)
            self.assertIn(result["status"], ("blocked", "warning"))
        finally:
            os.unlink(path)

    def test_summary_is_non_empty_string(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch("phase2_validator._get_processes", return_value=[]):
                result = pv.run_phase2_validation("cli1", path)
            self.assertIsInstance(result["summary"], str)
            self.assertGreater(len(result["summary"]), 0)
        finally:
            os.unlink(path)

    def test_queue_counts_reflects_actual_messages(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            msgs = [_make_scope_claim("cli2", f"scope-{i}") for i in range(3)]
            _write_queue(path, msgs)
            with patch("phase2_validator._get_processes",
                       return_value=[_make_process(pid=9, chat_id="cli2", cca=True)]):
                result = pv.run_phase2_validation("cli1", path)
            self.assertEqual(result["queue_counts"]["valid"], 3)
        finally:
            os.unlink(path)

    def test_timestamp_is_present_and_parseable(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch("phase2_validator._get_processes", return_value=[]):
                result = pv.run_phase2_validation("cli1", path)
            ts = result["timestamp"]
            parsed = datetime.fromisoformat(ts)
            self.assertIsNotNone(parsed)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
