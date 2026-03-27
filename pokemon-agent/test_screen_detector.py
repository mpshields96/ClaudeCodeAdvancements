"""Tests for screen transition detection.

Mewtoo pattern: detect blank/transition screens and skip LLM calls.
During screen transitions (map changes, battle intros, fade effects),
the game disables joypad input. We detect this and auto-wait.
"""
import unittest
from screen_detector import ScreenDetector, ScreenState


class TestScreenDetector(unittest.TestCase):
    """Core screen detection tests."""

    def setUp(self):
        self.sd = ScreenDetector()

    # ── Basic detection ──

    def test_normal_screen(self):
        """Joy enabled + no battle = ACTIVE screen."""
        state = self.sd.classify(joy_disabled=0, battle_mode=0, window_stack=0)
        self.assertEqual(state, ScreenState.ACTIVE)

    def test_transition_screen(self):
        """Joy disabled + no battle = TRANSITION."""
        state = self.sd.classify(joy_disabled=1, battle_mode=0, window_stack=0)
        self.assertEqual(state, ScreenState.TRANSITION)

    def test_battle_intro(self):
        """Joy disabled + battle mode = BATTLE_TRANSITION."""
        state = self.sd.classify(joy_disabled=1, battle_mode=1, window_stack=0)
        self.assertEqual(state, ScreenState.BATTLE_TRANSITION)

    def test_active_battle(self):
        """Joy enabled + battle mode = ACTIVE (battle is interactive)."""
        state = self.sd.classify(joy_disabled=0, battle_mode=1, window_stack=0)
        self.assertEqual(state, ScreenState.ACTIVE)

    def test_dialog_active(self):
        """Joy enabled + window open = ACTIVE (dialog needs LLM)."""
        state = self.sd.classify(joy_disabled=0, battle_mode=0, window_stack=1)
        self.assertEqual(state, ScreenState.ACTIVE)

    def test_transition_with_window(self):
        """Joy disabled + window = still TRANSITION (cutscene text)."""
        state = self.sd.classify(joy_disabled=1, battle_mode=0, window_stack=1)
        self.assertEqual(state, ScreenState.TRANSITION)

    # ── Recommended action ──

    def test_transition_recommends_wait(self):
        """Transition screens recommend waiting (not pressing buttons)."""
        action = self.sd.recommended_action(ScreenState.TRANSITION)
        self.assertEqual(action, "wait")

    def test_battle_transition_recommends_wait(self):
        """Battle transitions recommend waiting."""
        action = self.sd.recommended_action(ScreenState.BATTLE_TRANSITION)
        self.assertEqual(action, "wait")

    def test_active_recommends_none(self):
        """Active screens have no recommendation (LLM decides)."""
        action = self.sd.recommended_action(ScreenState.ACTIVE)
        self.assertIsNone(action)

    # ── Consecutive transition tracking ──

    def test_consecutive_transitions_counted(self):
        """Track how many consecutive transitions we've seen."""
        self.assertEqual(self.sd.consecutive_transitions, 0)
        self.sd.update(ScreenState.TRANSITION)
        self.assertEqual(self.sd.consecutive_transitions, 1)
        self.sd.update(ScreenState.TRANSITION)
        self.assertEqual(self.sd.consecutive_transitions, 2)

    def test_active_resets_consecutive(self):
        """An active screen resets the consecutive counter."""
        self.sd.update(ScreenState.TRANSITION)
        self.sd.update(ScreenState.TRANSITION)
        self.sd.update(ScreenState.ACTIVE)
        self.assertEqual(self.sd.consecutive_transitions, 0)

    def test_long_transition_recommends_start(self):
        """After 30+ consecutive transitions, recommend START to unstick."""
        for _ in range(30):
            self.sd.update(ScreenState.TRANSITION)
        action = self.sd.recommended_action(ScreenState.TRANSITION)
        self.assertEqual(action, "start")

    # ── Stats ──

    def test_stats(self):
        """Stats tracks total transitions and skipped LLM calls."""
        self.sd.update(ScreenState.TRANSITION)
        self.sd.update(ScreenState.TRANSITION)
        self.sd.update(ScreenState.ACTIVE)
        stats = self.sd.stats()
        self.assertEqual(stats["total_transitions"], 2)
        self.assertEqual(stats["total_active"], 1)
        self.assertEqual(stats["llm_calls_saved"], 2)


if __name__ == "__main__":
    unittest.main()
