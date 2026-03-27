"""Hivemind Phase 1 validation — verify detect_chat_id env var behavior.

Tests that detect_chat_id correctly reads CCA_CHAT_ID for internal CCA identities.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDetectChatId(unittest.TestCase):
    """Verify detect_chat_id returns correct values based on CCA_CHAT_ID env var."""

    def _detect(self, env_overrides=None):
        """Import fresh each call so env changes take effect."""
        import importlib
        import cca_comm
        importlib.reload(cca_comm)
        return cca_comm.detect_chat_id()

    def test_cli1_env_var(self):
        """CCA_CHAT_ID=cli1 must return 'cli1'."""
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}, clear=False):
            import cca_comm
            result = cca_comm.detect_chat_id()
        self.assertEqual(result, "cli1")

    def test_cli2_env_var(self):
        """CCA_CHAT_ID=cli2 must return 'cli2'."""
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli2"}, clear=False):
            import cca_comm
            result = cca_comm.detect_chat_id()
        self.assertEqual(result, "cli2")

    def test_desktop_env_var(self):
        """CCA_CHAT_ID=desktop must return 'desktop'."""
        with patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"}, clear=False):
            import cca_comm
            result = cca_comm.detect_chat_id()
        self.assertEqual(result, "desktop")

    def test_codex_env_var(self):
        """CCA_CHAT_ID=codex must return 'codex'."""
        with patch.dict(os.environ, {"CCA_CHAT_ID": "codex"}, clear=False):
            import cca_comm
            result = cca_comm.detect_chat_id()
        self.assertEqual(result, "codex")


if __name__ == "__main__":
    unittest.main()
