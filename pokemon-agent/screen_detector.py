"""Screen transition detection for Pokemon Crystal.

Mewtoo pattern: detect blank/transition screens and skip LLM calls.
During screen transitions (map changes, battle intros, fade effects),
the game disables joypad input (JOY_DISABLED flag). We detect this
and auto-wait instead of burning an API call.

Usage:
    from screen_detector import ScreenDetector, ScreenState

    sd = ScreenDetector()
    state = sd.classify(joy_disabled=1, battle_mode=0, window_stack=0)
    action = sd.recommended_action(state)  # "wait" or None
    sd.update(state)  # track consecutive transitions

Stdlib only. No external dependencies.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class ScreenState(Enum):
    """Screen classification for LLM skip decisions."""
    ACTIVE = "active"                    # Interactive — LLM should decide
    TRANSITION = "transition"            # Non-interactive — skip LLM, wait
    BATTLE_TRANSITION = "battle_transition"  # Battle intro/outro — skip LLM, wait


# After this many consecutive transitions, try pressing START to unstick
LONG_TRANSITION_THRESHOLD = 30


class ScreenDetector:
    """Detects screen transitions to skip unnecessary LLM calls.

    When JOY_DISABLED is set and we're not in an interactive state,
    the screen is in transition (fade, map load, cutscene animation).
    No point asking the LLM what to do — just wait for it to finish.
    """

    def __init__(self):
        self.consecutive_transitions: int = 0
        self._total_transitions: int = 0
        self._total_active: int = 0

    def classify(
        self,
        joy_disabled: int,
        battle_mode: int,
        window_stack: int,
    ) -> ScreenState:
        """Classify the current screen state.

        Args:
            joy_disabled: Value of JOY_DISABLED RAM flag (0xCFA0).
            battle_mode: Value of BATTLE_MODE RAM flag (0xD22D).
            window_stack: Value of WINDOW_STACK_SIZE RAM flag (0xCF85).

        Returns:
            ScreenState indicating whether the screen is interactive.
        """
        if joy_disabled == 0:
            return ScreenState.ACTIVE

        # Joy is disabled — screen is in transition
        if battle_mode > 0:
            return ScreenState.BATTLE_TRANSITION

        return ScreenState.TRANSITION

    def recommended_action(self, state: ScreenState) -> Optional[str]:
        """Get the recommended action for a screen state.

        Returns:
            "wait" for transitions, "start" if stuck in long transition,
            None if the LLM should decide.
        """
        if state == ScreenState.ACTIVE:
            return None

        # If we've been in transition for too long, try START to unstick
        if self.consecutive_transitions >= LONG_TRANSITION_THRESHOLD:
            return "start"

        return "wait"

    def update(self, state: ScreenState) -> None:
        """Update tracking counters after classifying a screen."""
        if state in (ScreenState.TRANSITION, ScreenState.BATTLE_TRANSITION):
            self.consecutive_transitions += 1
            self._total_transitions += 1
        else:
            self.consecutive_transitions = 0
            self._total_active += 1

    def stats(self) -> dict:
        """Return tracking stats."""
        return {
            "total_transitions": self._total_transitions,
            "total_active": self._total_active,
            "llm_calls_saved": self._total_transitions,
            "consecutive_transitions": self.consecutive_transitions,
        }
