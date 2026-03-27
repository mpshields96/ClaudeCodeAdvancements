"""Tests for config.py — Crystal agent configuration."""
import unittest


class TestConfig(unittest.TestCase):
    """Validate configuration defaults and types."""

    def test_model_name(self):
        from config import MODEL_NAME
        self.assertEqual(MODEL_NAME, "claude-opus-4-6")

    def test_max_tokens_positive(self):
        from config import MAX_TOKENS
        self.assertGreater(MAX_TOKENS, 0)
        self.assertIsInstance(MAX_TOKENS, int)

    def test_temperature_range(self):
        from config import TEMPERATURE
        self.assertGreaterEqual(TEMPERATURE, 0.0)
        self.assertLessEqual(TEMPERATURE, 1.0)

    def test_max_history_positive(self):
        from config import MAX_HISTORY
        self.assertGreater(MAX_HISTORY, 0)

    def test_screenshot_upscale_positive(self):
        from config import SCREENSHOT_UPSCALE
        self.assertGreater(SCREENSHOT_UPSCALE, 0)

    def test_stuck_threshold_positive(self):
        from config import STUCK_THRESHOLD
        self.assertGreater(STUCK_THRESHOLD, 0)

    def test_save_interval_positive(self):
        from config import SAVE_INTERVAL
        self.assertGreater(SAVE_INTERVAL, 0)

    def test_offline_mode_default_false(self):
        from config import OFFLINE_MODE
        self.assertFalse(OFFLINE_MODE)

    def test_default_rom_path(self):
        from config import DEFAULT_ROM
        self.assertTrue(DEFAULT_ROM.endswith(".gbc"))

    def test_all_dirs_are_strings(self):
        from config import STATE_DIR, SCREENSHOT_DIR, LOG_DIR
        for d in (STATE_DIR, SCREENSHOT_DIR, LOG_DIR):
            self.assertIsInstance(d, str)
            self.assertTrue(len(d) > 0)


if __name__ == "__main__":
    unittest.main()
