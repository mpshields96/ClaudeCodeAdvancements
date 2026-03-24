#!/usr/bin/env python3
"""Tests for autoloop_trigger.py — CCA-internal autoloop trigger (MT-22, S138)."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import autoloop_trigger


class TestReadResume(unittest.TestCase):
    """Test resume file reading."""

    def test_reads_resume_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Run /cca-init. Last session was S138.")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path):
                content = autoloop_trigger.read_resume()
                self.assertEqual(content, "Run /cca-init. Last session was S138.")
        finally:
            os.unlink(path)

    def test_returns_empty_for_missing_file(self):
        with patch.object(autoloop_trigger, "RESUME_FILE", "/nonexistent/file.md"):
            content = autoloop_trigger.read_resume()
            self.assertEqual(content, "")

    def test_strips_whitespace(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("  content with spaces  \n\n")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path):
                content = autoloop_trigger.read_resume()
                self.assertEqual(content, "content with spaces")
        finally:
            os.unlink(path)


class TestBuildPrompt(unittest.TestCase):
    """Test prompt construction."""

    def test_prefixes_with_cca_init(self):
        prompt = autoloop_trigger.build_prompt("Resume text here")
        self.assertTrue(prompt.startswith("/cca-init"))

    def test_includes_resume_content(self):
        prompt = autoloop_trigger.build_prompt("Last session S138")
        self.assertIn("Last session S138", prompt)

    def test_has_cca_auto_in_prefix(self):
        prompt = autoloop_trigger.build_prompt("test")
        self.assertIn("/cca-auto", prompt)


class TestCheckReadiness(unittest.TestCase):
    """Test readiness checks."""

    def test_passes_with_resume_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Resume content")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path):
                checks = autoloop_trigger.check_readiness()
                self.assertEqual(checks["resume_file"], "PASS")
        finally:
            os.unlink(path)

    def test_fails_without_resume_file(self):
        with patch.object(autoloop_trigger, "RESUME_FILE", "/nonexistent/file.md"):
            checks = autoloop_trigger.check_readiness()
            self.assertEqual(checks["resume_file"], "FAIL")


class TestTriggerNextSession(unittest.TestCase):
    """Test the main trigger function."""

    @patch("autoloop_trigger.DesktopAutomator")
    def test_full_success_flow(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = True
        mock_da.ensure_code_tab.return_value = True
        mock_da.new_conversation.return_value = True
        mock_da.send_prompt.return_value = True

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Resume content for next session")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", "/dev/null"):
                result = autoloop_trigger.trigger_next_session(dry_run=True)
                self.assertTrue(result)
                mock_da.activate_claude.assert_called_once()
                mock_da.ensure_code_tab.assert_called_once()
                mock_da.new_conversation.assert_called_once()
                mock_da.send_prompt.assert_called_once()
        finally:
            os.unlink(path)

    @patch("autoloop_trigger.DesktopAutomator")
    def test_fails_without_resume(self, MockDA):
        with patch.object(autoloop_trigger, "RESUME_FILE", "/nonexistent.md"), \
             patch.object(autoloop_trigger, "AUDIT_LOG", "/dev/null"):
            result = autoloop_trigger.trigger_next_session(dry_run=True)
            self.assertFalse(result)

    @patch("autoloop_trigger.DesktopAutomator")
    def test_fails_if_activate_fails(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Resume content")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", "/dev/null"):
                result = autoloop_trigger.trigger_next_session(dry_run=True)
                self.assertFalse(result)
                mock_da.ensure_code_tab.assert_not_called()
        finally:
            os.unlink(path)

    @patch("autoloop_trigger.DesktopAutomator")
    def test_fails_if_code_tab_fails(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = True
        mock_da.ensure_code_tab.return_value = False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Resume content")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", "/dev/null"):
                result = autoloop_trigger.trigger_next_session(dry_run=True)
                self.assertFalse(result)
                mock_da.new_conversation.assert_not_called()
        finally:
            os.unlink(path)

    @patch("autoloop_trigger.DesktopAutomator")
    def test_fails_if_new_conversation_fails(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = True
        mock_da.ensure_code_tab.return_value = True
        mock_da.new_conversation.return_value = False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Resume content")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", "/dev/null"):
                result = autoloop_trigger.trigger_next_session(dry_run=True)
                self.assertFalse(result)
                mock_da.send_prompt.assert_not_called()
        finally:
            os.unlink(path)

    @patch("autoloop_trigger.DesktopAutomator")
    def test_fails_if_send_fails(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = True
        mock_da.ensure_code_tab.return_value = True
        mock_da.new_conversation.return_value = True
        mock_da.send_prompt.return_value = False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Resume content")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", "/dev/null"):
                result = autoloop_trigger.trigger_next_session(dry_run=True)
                self.assertFalse(result)
        finally:
            os.unlink(path)

    @patch("autoloop_trigger.DesktopAutomator")
    def test_prompt_includes_resume_content(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = True
        mock_da.ensure_code_tab.return_value = True
        mock_da.new_conversation.return_value = True
        mock_da.send_prompt.return_value = True

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Specific resume text XYZ123")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", "/dev/null"):
                autoloop_trigger.trigger_next_session(dry_run=True)
                sent_prompt = mock_da.send_prompt.call_args[0][0]
                self.assertIn("Specific resume text XYZ123", sent_prompt)
                self.assertIn("/cca-init", sent_prompt)
        finally:
            os.unlink(path)

    @patch("autoloop_trigger.DesktopAutomator")
    def test_step_order_code_tab_then_new_conv_then_send(self, MockDA):
        """Verify strict ordering: Code tab -> New session -> Send."""
        mock_da = MockDA.return_value
        call_order = []
        mock_da.activate_claude.side_effect = lambda: (call_order.append("activate"), True)[1]
        mock_da.ensure_code_tab.side_effect = lambda: (call_order.append("code_tab"), True)[1]
        mock_da.new_conversation.side_effect = lambda: (call_order.append("new_conv"), True)[1]
        mock_da.send_prompt.side_effect = lambda p: (call_order.append("send"), True)[1]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Resume")
            path = f.name
        try:
            with patch.object(autoloop_trigger, "RESUME_FILE", path), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", "/dev/null"):
                autoloop_trigger.trigger_next_session(dry_run=True)
                self.assertEqual(call_order, ["activate", "code_tab", "new_conv", "send"])
        finally:
            os.unlink(path)


class TestAuditLogging(unittest.TestCase):
    """Test audit log entries."""

    @patch("autoloop_trigger.DesktopAutomator")
    def test_logs_trigger_start(self, MockDA):
        mock_da = MockDA.return_value
        mock_da.activate_claude.return_value = True
        mock_da.ensure_code_tab.return_value = True
        mock_da.new_conversation.return_value = True
        mock_da.send_prompt.return_value = True

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as rf, \
             tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as lf:
            rf.write("Resume content")
            rf.flush()
            log_path = lf.name

            with patch.object(autoloop_trigger, "RESUME_FILE", rf.name), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", log_path):
                autoloop_trigger.trigger_next_session(dry_run=True)

            with open(log_path) as f:
                entries = [json.loads(line) for line in f if line.strip()]
            events = [e["event"] for e in entries]
            self.assertIn("trigger_start", events)
            self.assertIn("trigger_success", events)

            os.unlink(rf.name)
            os.unlink(log_path)

    @patch("autoloop_trigger.DesktopAutomator")
    def test_logs_failure_reason(self, MockDA):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as lf:
            log_path = lf.name

            with patch.object(autoloop_trigger, "RESUME_FILE", "/nonexistent.md"), \
                 patch.object(autoloop_trigger, "AUDIT_LOG", log_path):
                autoloop_trigger.trigger_next_session(dry_run=True)

            with open(log_path) as f:
                entries = [json.loads(line) for line in f if line.strip()]
            events = [e["event"] for e in entries]
            self.assertIn("trigger_failed", events)
            failed = [e for e in entries if e["event"] == "trigger_failed"][0]
            self.assertEqual(failed["reason"], "no_resume")

            os.unlink(log_path)


if __name__ == "__main__":
    unittest.main()
