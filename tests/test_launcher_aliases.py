#!/usr/bin/env python3
"""Tests for launcher aliases (cc, cca, ccbot) — S230 Matthew directive.

Validates that ~/.zshrc contains the correct alias definitions with
proper model split: CCA=Opus, Kalshi=Sonnet, generic=no model override.
"""

import os
import re
import unittest


def _read_zshrc():
    path = os.path.expanduser("~/.zshrc")
    with open(path) as f:
        return f.read()


class TestLauncherAliases(unittest.TestCase):
    """Verify launcher aliases in ~/.zshrc."""

    def setUp(self):
        self.zshrc = _read_zshrc()

    def test_cc_alias_exists(self):
        self.assertIn('alias cc=', self.zshrc)

    def test_cc_has_no_model_flag(self):
        # cc is generic — should NOT force a model
        match = re.search(r'alias cc="([^"]+)"', self.zshrc)
        self.assertIsNotNone(match, "cc alias not found")
        self.assertNotIn("--model", match.group(1))

    def test_cc_has_skip_permissions(self):
        match = re.search(r'alias cc="([^"]+)"', self.zshrc)
        self.assertIsNotNone(match)
        self.assertIn("--dangerously-skip-permissions", match.group(1))

    def test_cca_alias_exists(self):
        self.assertIn('alias cca=', self.zshrc)

    def test_cca_uses_sonnet(self):
        match = re.search(r'alias cca="([^"]+)"', self.zshrc)
        self.assertIsNotNone(match, "cca alias not found")
        self.assertIn("--model sonnet", match.group(1))

    def test_cca_targets_correct_dir(self):
        match = re.search(r'alias cca="([^"]+)"', self.zshrc)
        self.assertIsNotNone(match)
        self.assertIn("ClaudeCodeAdvancements", match.group(1))

    def test_ccbot_alias_exists(self):
        self.assertIn('alias ccbot=', self.zshrc)

    def test_ccbot_uses_sonnet(self):
        match = re.search(r'alias ccbot="([^"]+)"', self.zshrc)
        self.assertIsNotNone(match, "ccbot alias not found")
        self.assertIn("--model sonnet", match.group(1))

    def test_ccbot_targets_correct_dir(self):
        match = re.search(r'alias ccbot="([^"]+)"', self.zshrc)
        self.assertIsNotNone(match)
        self.assertIn("polymarket-bot", match.group(1))

    def test_no_duplicate_alias_definitions(self):
        # Each alias should appear exactly once as a definition
        cc_count = len(re.findall(r'^alias cc="', self.zshrc, re.MULTILINE))
        cca_count = len(re.findall(r'^alias cca="', self.zshrc, re.MULTILINE))
        ccbot_count = len(re.findall(r'^alias ccbot="', self.zshrc, re.MULTILINE))
        self.assertEqual(cc_count, 1, f"cc defined {cc_count} times")
        self.assertEqual(cca_count, 1, f"cca defined {cca_count} times")
        self.assertEqual(ccbot_count, 1, f"ccbot defined {ccbot_count} times")


if __name__ == "__main__":
    unittest.main()
