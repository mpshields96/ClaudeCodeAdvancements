"""Integration tests for the full agent loop.

Phase 4 Step 4: Verify state changes propagate correctly through the
complete observe -> think -> act -> verify pipeline. Tests run with
MockLLM (no API calls) but exercise the full code path.

These tests validate:
1. Multi-step execution with state changes between steps
2. Stuck detection + enhanced stuck context integration
3. Summarization triggers and state preservation
4. Battle entry/exit transitions across steps
5. Menu state transitions during gameplay
6. Tool execution + verification + strategy tracking working together
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
from game_state import MenuState
from memory_reader import (
    MemoryReader, BATTLE_MODE, ENEMY_MON_SPECIES, ENEMY_MON_LEVEL,
    ENEMY_MON_HP_HI, ENEMY_MON_HP_LO, ENEMY_MON_HP_MAX_HI, ENEMY_MON_HP_MAX_LO,
    PARTY_COUNT, PARTY_DATA_START, PLAYER_X, PLAYER_Y,
    WINDOW_STACK_SIZE, TEXT_BOX_FLAGS, MART_POINTER, JOY_DISABLED,
)
from agent import CrystalAgent, MockLLMClient, LLMResponse, ToolUse, StepResult


def _setup_crystal_emu():
    """Create a mock emulator with realistic Crystal starting state."""
    emu = EmulatorControl.mock()
    # Party: 1 Cyndaquil Lv5
    emu.write_byte(PARTY_COUNT, 1)
    emu.write_byte(PARTY_DATA_START + 0, 155)   # species = Cyndaquil
    emu.write_byte(PARTY_DATA_START + 31, 5)    # level 5
    emu.write_byte(PARTY_DATA_START + 34, 0)    # HP high
    emu.write_byte(PARTY_DATA_START + 35, 20)   # HP = 20
    emu.write_byte(PARTY_DATA_START + 36, 0)    # max HP high
    emu.write_byte(PARTY_DATA_START + 37, 20)   # max HP = 20
    emu.write_byte(PARTY_DATA_START + 2, 33)    # move1 = Tackle
    # Position: New Bark Town
    emu.write_byte(0xDCB5, 3)   # map group
    emu.write_byte(0xDCB6, 1)   # map number
    emu.write_byte(PLAYER_X, 5)
    emu.write_byte(PLAYER_Y, 4)
    return emu


def _make_agent(emu=None, responses=None, max_history=60, stuck_threshold=5):
    """Create agent with mock emulator and LLM.

    Action cache disabled (max_size=0) so integration tests that expect
    LLM calls every step aren't broken by caching.
    """
    if emu is None:
        emu = _setup_crystal_emu()
    reader = MemoryReader(emu)
    llm = MockLLMClient(responses=responses)
    agent = CrystalAgent(
        emulator=emu, reader=reader, llm=llm,
        max_history=max_history, stuck_threshold=stuck_threshold,
    )
    from action_cache import ActionCache
    agent.action_cache = ActionCache(max_size=0)
    return agent, llm, emu


class TestMultiStepExecution(unittest.TestCase):
    """Test that multi-step runs maintain coherent state."""

    def test_10_steps_no_crash(self):
        """Agent runs 10 steps without errors."""
        agent, _, _ = _make_agent()
        results = agent.run(num_steps=10)
        self.assertEqual(len(results), 10)
        self.assertEqual(agent.step_count, 10)

    def test_position_change_resets_stuck(self):
        """Moving to a new position resets stuck counter."""
        agent, _, emu = _make_agent(stuck_threshold=3)
        # 2 steps at same position
        agent.step()
        agent.step()
        # Move player
        emu.write_byte(PLAYER_X, 8)
        result = agent.step()
        self.assertFalse(result.was_stuck)

    def test_message_history_grows(self):
        """Messages accumulate across steps."""
        agent, _, _ = _make_agent()
        agent.step()
        count1 = len(agent.messages)
        agent.step()
        count2 = len(agent.messages)
        agent.step()
        count3 = len(agent.messages)
        self.assertGreater(count2, count1)
        self.assertGreater(count3, count2)

    def test_token_tracking_accumulates(self):
        """Token counts accumulate across steps."""
        agent, _, _ = _make_agent()
        agent.run(num_steps=5)
        self.assertEqual(agent.token_usage["steps"], 5)


class TestBattleTransitions(unittest.TestCase):
    """Test battle entry/exit across agent steps."""

    def test_enter_battle_mid_run(self):
        """Agent detects battle entry between steps."""
        agent, _, emu = _make_agent()

        # Step 1: overworld
        r1 = agent.step()
        self.assertFalse(r1.state.is_in_battle())

        # Set battle state in RAM
        emu.write_byte(BATTLE_MODE, 1)
        emu.write_byte(ENEMY_MON_SPECIES, 19)   # Rattata
        emu.write_byte(ENEMY_MON_LEVEL, 3)
        emu.write_byte(ENEMY_MON_HP_HI, 0)
        emu.write_byte(ENEMY_MON_HP_LO, 12)
        emu.write_byte(ENEMY_MON_HP_MAX_HI, 0)
        emu.write_byte(ENEMY_MON_HP_MAX_LO, 12)

        # Step 2: in battle
        r2 = agent.step()
        self.assertTrue(r2.state.is_in_battle())
        self.assertEqual(r2.state.battle.enemy.species, "Rattata")

    def test_exit_battle_mid_run(self):
        """Agent detects battle exit between steps."""
        agent, _, emu = _make_agent()

        # Start in battle
        emu.write_byte(BATTLE_MODE, 1)
        emu.write_byte(ENEMY_MON_SPECIES, 19)
        emu.write_byte(ENEMY_MON_LEVEL, 3)
        emu.write_byte(ENEMY_MON_HP_HI, 0)
        emu.write_byte(ENEMY_MON_HP_LO, 12)
        emu.write_byte(ENEMY_MON_HP_MAX_HI, 0)
        emu.write_byte(ENEMY_MON_HP_MAX_LO, 12)

        r1 = agent.step()
        self.assertTrue(r1.state.is_in_battle())

        # Exit battle
        emu.write_byte(BATTLE_MODE, 0)
        r2 = agent.step()
        self.assertFalse(r2.state.is_in_battle())


class TestMenuStateTransitions(unittest.TestCase):
    """Test menu state detection across agent steps."""

    def test_window_flags_are_overworld_in_crystal(self):
        """Window/text flags unreliable in Crystal — always overworld (S208)."""
        agent, _, emu = _make_agent()

        r1 = agent.step()
        self.assertEqual(r1.state.menu_state, MenuState.OVERWORLD)

        emu.write_byte(WINDOW_STACK_SIZE, 10)
        emu.write_byte(TEXT_BOX_FLAGS, 190)
        r2 = agent.step()
        self.assertEqual(r2.state.menu_state, MenuState.OVERWORLD)

    def test_battle_reliably_detected(self):
        """Battle mode overrides unreliable flags."""
        agent, _, emu = _make_agent()

        emu.write_byte(BATTLE_MODE, 1)
        r1 = agent.step()
        self.assertEqual(r1.state.menu_state, MenuState.BATTLE)

        emu.write_byte(BATTLE_MODE, 0)
        r2 = agent.step()
        self.assertEqual(r2.state.menu_state, MenuState.OVERWORLD)

    def test_shop_state(self):
        """Agent detects shop mode."""
        agent, _, emu = _make_agent()
        emu.write_byte(MART_POINTER, 3)
        r = agent.step()
        self.assertEqual(r.state.menu_state, MenuState.SHOP)


class TestStuckDetectionIntegration(unittest.TestCase):
    """Test stuck detection + self-anchoring counter in full loop."""

    def test_stuck_fires_after_threshold(self):
        """Agent reports stuck after N same-position steps."""
        agent, _, _ = _make_agent(stuck_threshold=3)
        results = agent.run(num_steps=5)
        # Steps 1-2: not stuck. Steps 3+: stuck.
        self.assertFalse(results[0].was_stuck)
        self.assertFalse(results[1].was_stuck)
        self.assertTrue(results[2].was_stuck)
        self.assertTrue(results[4].was_stuck)

    def test_stuck_context_in_messages(self):
        """When stuck, agent's message history contains stuck warning."""
        agent, llm, _ = _make_agent(stuck_threshold=3)
        agent.run(num_steps=4)
        # Agent's message history should contain stuck warning in user messages
        user_msgs = [m for m in agent.messages if m["role"] == "user"]
        all_text = ""
        for msg in user_msgs:
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    all_text += block["text"]
        self.assertIn("STUCK", all_text)

    def test_strategies_tracked_when_stuck(self):
        """Failed button strategies are tracked after stuck threshold."""
        responses = []
        for i in range(8):
            responses.append(LLMResponse(
                text=f"try {i}",
                tool_uses=[ToolUse(id=f"t{i}", name="press_buttons",
                                   input={"buttons": ["right", "a"]})],
            ))
        agent, _, _ = _make_agent(responses=responses, stuck_threshold=3)
        agent.run(num_steps=8)
        # Should have accumulated strategies from steps 3+ (when stuck)
        self.assertGreater(len(agent._failed_strategies), 0)


class TestSummarizationIntegration(unittest.TestCase):
    """Test that summarization works within the full loop."""

    def test_summarization_preserves_continuity(self):
        """After summarization, agent continues running without crash."""
        agent, llm, _ = _make_agent(max_history=4)
        # 5 steps should trigger summarization and continue
        results = agent.run(num_steps=5)
        self.assertEqual(len(results), 5)
        # At least one step should have triggered summarization
        summarized = any(r.was_summarized for r in results)
        self.assertTrue(summarized)

    def test_summarization_reduces_message_count(self):
        """Messages are reduced after summarization."""
        agent, _, _ = _make_agent(max_history=4)
        agent.run(num_steps=2)  # Triggers summarization
        # After summarization, message count should be manageable
        self.assertLess(len(agent.messages), 15)


class TestCallbackIntegration(unittest.TestCase):
    """Test step callbacks work across full runs."""

    def test_callback_receives_all_steps(self):
        """Callback fires for every step in a multi-step run."""
        captured = []
        agent, _, _ = _make_agent()
        agent.on_step(lambda r: captured.append(r.step_number))
        agent.run(num_steps=5)
        self.assertEqual(captured, [1, 2, 3, 4, 5])

    def test_callback_sees_battle_transitions(self):
        """Callback can track battle state changes."""
        states = []
        agent, _, emu = _make_agent()
        agent.on_step(lambda r: states.append(r.state.is_in_battle()))

        agent.step()  # overworld
        emu.write_byte(BATTLE_MODE, 1)
        emu.write_byte(ENEMY_MON_SPECIES, 41)
        emu.write_byte(ENEMY_MON_LEVEL, 2)
        emu.write_byte(ENEMY_MON_HP_LO, 10)
        emu.write_byte(ENEMY_MON_HP_MAX_LO, 10)
        agent.step()  # battle
        emu.write_byte(BATTLE_MODE, 0)
        agent.step()  # overworld again

        self.assertEqual(states, [False, True, False])


if __name__ == "__main__":
    unittest.main()
