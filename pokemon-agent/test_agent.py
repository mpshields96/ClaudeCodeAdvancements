"""Tests for agent.py — Crystal agent core loop."""
import unittest
import os
import sys
import tempfile

from emulator_control import EmulatorControl
from game_state import (
    Badges, BattleState, GameState, MapPosition, Move, Party, Pokemon,
)
from memory_reader import MemoryReader
from agent_memory import AgentMemory, MapMarkers, Objectives
from agent import (
    CrystalAgent, MockLLMClient, LLMResponse, ToolUse, StepResult,
)


def _make_pokemon(species="Cyndaquil", level=10, hp=30, hp_max=30):
    return Pokemon(
        species=species, nickname=species, level=level,
        hp=hp, hp_max=hp_max,
        attack=30, defense=25, speed=35, sp_attack=40, sp_defense=30,
        moves=[Move(name="Tackle", move_type="Normal", power=40,
                     accuracy=100, pp=35, pp_max=35)],
    )


def _setup_mock_emu():
    """Create a mock emulator with basic Crystal RAM state."""
    emu = EmulatorControl.mock()
    # Set up party: 1 Cyndaquil
    emu.write_byte(0xDCD7, 1)  # party count
    emu.write_byte(0xDCDF + 0, 155)  # species = Cyndaquil
    emu.write_byte(0xDCDF + 31, 10)  # level
    emu.write_byte(0xDCDF + 34, 0)   # HP high
    emu.write_byte(0xDCDF + 35, 30)  # HP low
    emu.write_byte(0xDCDF + 36, 0)   # max HP high
    emu.write_byte(0xDCDF + 37, 30)  # max HP low
    emu.write_byte(0xDCDF + 2, 33)   # move1 = Tackle
    # Position: map group 3, map 1, x=5, y=4
    emu.write_byte(0xDCB5, 3)
    emu.write_byte(0xDCB6, 1)
    emu.write_byte(0xDCB8, 5)
    emu.write_byte(0xDCB7, 4)
    return emu


def _make_agent(llm_responses=None, max_history=60, stuck_threshold=10, cache_size=0):
    """Create a CrystalAgent with mock emulator and LLM.

    cache_size=0 disables action caching by default in tests so existing
    tests that expect LLM calls on every step aren't broken by the cache.
    Tests that specifically test caching should pass cache_size > 0.
    """
    emu = _setup_mock_emu()
    reader = MemoryReader(emu)
    llm = MockLLMClient(responses=llm_responses)
    agent = CrystalAgent(
        emulator=emu,
        reader=reader,
        llm=llm,
        max_history=max_history,
        stuck_threshold=stuck_threshold,
    )
    from action_cache import ActionCache
    agent.action_cache = ActionCache(max_size=cache_size)
    return agent, llm


class TestAgentConstruction(unittest.TestCase):
    """Test agent initialization."""

    def test_create_agent(self):
        agent, _ = _make_agent()
        self.assertEqual(agent.step_count, 0)
        self.assertEqual(len(agent.messages), 0)

    def test_no_llm_offline_fallback(self):
        """Without LLM, agent falls back to offline mode (press A)."""
        emu = _setup_mock_emu()
        reader = MemoryReader(emu)
        agent = CrystalAgent(emulator=emu, reader=reader, llm=None)
        result = agent.step()
        self.assertEqual(result.llm_text, "[offline: press a]")
        self.assertEqual(result.input_tokens, 0)
        self.assertEqual(result.output_tokens, 0)

    def test_token_usage_initial(self):
        agent, _ = _make_agent()
        usage = agent.token_usage
        self.assertEqual(usage["input_tokens"], 0)
        self.assertEqual(usage["output_tokens"], 0)
        self.assertEqual(usage["steps"], 0)


class TestAgentStep(unittest.TestCase):
    """Test single step execution."""

    def test_step_returns_result(self):
        agent, _ = _make_agent()
        result = agent.step()
        self.assertIsInstance(result, StepResult)
        self.assertEqual(result.step_number, 1)

    def test_step_increments_count(self):
        agent, _ = _make_agent()
        agent.step()
        self.assertEqual(agent.step_count, 1)
        agent.step()
        self.assertEqual(agent.step_count, 2)

    def test_step_reads_game_state(self):
        agent, _ = _make_agent()
        result = agent.step()
        # Should have read the mock RAM
        self.assertIsNotNone(result.state)
        self.assertEqual(result.state.party.size(), 1)

    def test_step_calls_llm(self):
        agent, llm = _make_agent()
        agent.step()
        self.assertEqual(llm.call_count, 1)

    def test_step_passes_system_prompt(self):
        agent, llm = _make_agent()
        agent.step()
        self.assertIn("Pokemon Crystal", llm.last_system)

    def test_step_adds_messages(self):
        agent, _ = _make_agent()
        agent.step()
        # Should have: user msg + assistant msg + tool result msg
        self.assertGreaterEqual(len(agent.messages), 2)

    def test_step_executes_tool_call(self):
        responses = [LLMResponse(
            text="Pressing A.",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": ["a"]})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].name, "press_buttons")

    def test_step_result_has_tool_results(self):
        responses = [LLMResponse(
            text="Moving right.",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": ["right", "right"]})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        self.assertEqual(len(result.tool_results), 1)
        self.assertEqual(result.tool_results[0]["count"], 2)

    def test_step_with_no_tool_calls(self):
        responses = [LLMResponse(text="Just thinking...", tool_uses=[])]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        self.assertEqual(len(result.tool_calls), 0)
        self.assertEqual(len(result.tool_results), 0)

    def test_step_does_not_offer_navigation_without_navigator(self):
        agent, llm = _make_agent()
        agent.step()
        offered_tools = {tool["name"] for tool in llm.last_tools}
        self.assertNotIn("navigate_to", offered_tools)


class TestToolExecution(unittest.TestCase):
    """Test tool call routing and execution."""

    def test_press_buttons_executes(self):
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": ["a", "b", "start"]})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        self.assertEqual(result.tool_results[0]["count"], 3)

    def test_wait_executes(self):
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="wait",
                               input={"frames": 60})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        self.assertEqual(result.tool_results[0]["waited_frames"], 60)

    def test_invalid_tool_returns_error(self):
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": []})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        self.assertIn("error", result.tool_results[0])

    def test_navigate_without_navigator_returns_error(self):
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="navigate_to",
                               input={"x": 5, "y": 3})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        # No navigator set
        result = agent.step()
        self.assertIn("error", result.tool_results[0])

    def test_multiple_tool_calls(self):
        responses = [LLMResponse(
            text="test",
            tool_uses=[
                ToolUse(id="t1", name="press_buttons", input={"buttons": ["a"]}),
                ToolUse(id="t2", name="wait", input={"frames": 30}),
            ],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        self.assertEqual(len(result.tool_results), 2)


class TestStuckDetection(unittest.TestCase):
    """Test stuck detection based on position tracking."""

    def test_not_stuck_initially(self):
        agent, _ = _make_agent(stuck_threshold=3)
        result = agent.step()
        self.assertFalse(result.was_stuck)

    def test_stuck_after_threshold(self):
        agent, _ = _make_agent(stuck_threshold=3)
        # Same position for 3+ steps
        for _ in range(2):
            agent.step()
        result = agent.step()
        self.assertTrue(result.was_stuck)

    def test_not_stuck_if_position_changes(self):
        agent, _ = _make_agent(stuck_threshold=5)
        agent.step()
        # Change position in RAM
        agent.emulator.write_byte(0xDCB8, 6)  # X = 6
        agent.step()
        agent.emulator.write_byte(0xDCB8, 7)  # X = 7
        result = agent.step()
        self.assertFalse(result.was_stuck)


class TestSummarization(unittest.TestCase):
    """Test conversation summarization."""

    def test_no_summarization_below_threshold(self):
        agent, llm = _make_agent(max_history=100)
        result = agent.step()
        self.assertFalse(result.was_summarized)

    def test_summarization_at_threshold(self):
        # Low threshold to trigger quickly
        agent, llm = _make_agent(max_history=4)
        # Each step adds ~3 messages (user + assistant + tool_result)
        # So 2 steps = ~6 messages, triggers summarization
        agent.step()
        result = agent.step()
        self.assertTrue(result.was_summarized)

    def test_summarization_reduces_messages(self):
        agent, llm = _make_agent(max_history=4)
        agent.step()
        agent.step()  # triggers summarization
        # After summarization, messages should be reset to 2 (summary + ack)
        # But then the step adds more. Should be much less than 8+.
        self.assertLess(len(agent.messages), 8)

    def test_summarization_calls_llm_extra(self):
        agent, llm = _make_agent(max_history=4)
        agent.step()
        agent.step()  # triggers summarization
        # 2 step calls + 1 summarization call = 3
        self.assertEqual(llm.call_count, 3)


class TestPostActionVerification(unittest.TestCase):
    """Test post-action RAM verification (Phase 4 Step 1)."""

    def test_direction_press_no_move_warns(self):
        """If we press 3+ direction buttons and don't move, verification warns."""
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": ["right", "right", "right"]})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        # Position stays the same (mock emulator doesn't actually move)
        result = agent.step()
        tool_result = result.tool_results[0]
        self.assertIn("verification", tool_result)
        self.assertEqual(tool_result["verification"]["warning"],
                         "pressed_directions_but_didnt_move")

    def test_single_direction_no_warn(self):
        """Single direction press doesn't trigger warning (normal wall bumps)."""
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": ["right"]})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        tool_result = result.tool_results[0]
        # Should NOT have a direction-didn't-move warning for single press
        if "verification" in tool_result:
            self.assertNotEqual(
                tool_result["verification"].get("warning"),
                "pressed_directions_but_didnt_move",
            )

    def test_non_direction_press_no_move_check(self):
        """Pressing A/B doesn't check for position change."""
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": ["a", "a", "a"]})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        tool_result = result.tool_results[0]
        # No direction-related warning
        if "verification" in tool_result:
            self.assertNotEqual(
                tool_result["verification"].get("warning"),
                "pressed_directions_but_didnt_move",
            )

    def test_battle_start_detected(self):
        """Verify battle start is detected via verification."""
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": ["a"]})],
        )]
        agent, _ = _make_agent(llm_responses=responses)

        # Simulate battle starting: set battle mode AFTER tool execution
        # We need to hook into the emulator to change state during execution
        original_press = agent.emulator.press
        call_count = [0]
        def press_with_battle(button, **kwargs):
            original_press(button, **kwargs)
            call_count[0] += 1
            if call_count[0] == 1:
                # After first button press, "enter battle"
                agent.emulator.write_byte(0xD22D, 1)  # BATTLE_MODE = wild
                agent.emulator.write_byte(0xD206, 19)  # Enemy = Rattata
                agent.emulator.write_byte(0xD213, 3)   # Enemy level 3
                agent.emulator.write_byte(0xD214, 0)
                agent.emulator.write_byte(0xD215, 15)  # Enemy HP 15
                agent.emulator.write_byte(0xD216, 0)
                agent.emulator.write_byte(0xD217, 15)  # Enemy max HP 15
        agent.emulator.press = press_with_battle

        result = agent.step()
        tool_result = result.tool_results[0]
        self.assertIn("verification", tool_result)
        self.assertEqual(tool_result["verification"]["event"], "battle_started")
        self.assertEqual(tool_result["verification"]["type"], "wild")

    def test_wait_no_verification(self):
        """Wait tool should not produce verification output."""
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="wait",
                               input={"frames": 30})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        tool_result = result.tool_results[0]
        self.assertNotIn("verification", tool_result)

    def test_error_result_skips_verification(self):
        """Tool errors should not trigger verification."""
        responses = [LLMResponse(
            text="test",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": []})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        result = agent.step()
        tool_result = result.tool_results[0]
        self.assertIn("error", tool_result)
        self.assertNotIn("verification", tool_result)


class TestRun(unittest.TestCase):
    """Test multi-step execution."""

    def test_run_returns_results(self):
        agent, _ = _make_agent()
        results = agent.run(num_steps=3)
        self.assertEqual(len(results), 3)

    def test_run_increments_steps(self):
        agent, _ = _make_agent()
        agent.run(num_steps=5)
        self.assertEqual(agent.step_count, 5)

    def test_run_tracks_tokens(self):
        agent, _ = _make_agent()
        agent.run(num_steps=3)
        usage = agent.token_usage
        self.assertEqual(usage["steps"], 3)


class TestCallback(unittest.TestCase):
    """Test step callback."""

    def test_on_step_fires(self):
        results_captured = []
        agent, _ = _make_agent()
        agent.on_step(lambda r: results_captured.append(r))
        agent.step()
        self.assertEqual(len(results_captured), 1)
        self.assertIsInstance(results_captured[0], StepResult)

    def test_on_step_fires_each_step(self):
        count = [0]
        agent, _ = _make_agent()
        agent.on_step(lambda r: count.__setitem__(0, count[0] + 1))
        agent.run(num_steps=3)
        self.assertEqual(count[0], 3)


class TestMessageHistory(unittest.TestCase):
    """Test message history management."""

    def test_messages_grow_with_steps(self):
        agent, _ = _make_agent(max_history=100)
        agent.step()
        count1 = len(agent.messages)
        agent.step()
        count2 = len(agent.messages)
        self.assertGreater(count2, count1)

    def test_assistant_message_format(self):
        responses = [LLMResponse(
            text="Thinking about next move.",
            tool_uses=[ToolUse(id="t1", name="press_buttons",
                               input={"buttons": ["a"]})],
        )]
        agent, _ = _make_agent(llm_responses=responses)
        agent.step()
        # Find assistant message
        assistant_msgs = [m for m in agent.messages if m["role"] == "assistant"]
        self.assertGreater(len(assistant_msgs), 0)
        content = assistant_msgs[0]["content"]
        # Should have text + tool_use blocks
        types = {block["type"] for block in content}
        self.assertIn("text", types)
        self.assertIn("tool_use", types)


class TestActionCacheIntegration(unittest.TestCase):
    """Test action cache integration with the agent loop."""

    def test_cache_skips_llm_on_repeat_state(self):
        """Second step at same state uses cache, skips LLM."""
        agent, llm = _make_agent(cache_size=256)
        agent.step()  # LLM call -> caches action
        self.assertEqual(llm.call_count, 1)
        agent.step()  # Same state -> cache hit
        self.assertEqual(llm.call_count, 1)  # No new LLM call

    def test_cache_disabled_when_stuck(self):
        """When stuck, cache is bypassed for fresh LLM reasoning."""
        agent, llm = _make_agent(cache_size=256, stuck_threshold=2)
        agent.step()  # LLM call 1
        agent.step()  # Cache hit (not stuck yet since threshold=2)
        agent.step()  # Now stuck (3 steps same position) -> LLM call
        self.assertGreater(llm.call_count, 1)

    def test_cache_reports_zero_tokens(self):
        """Cached steps report 0 input/output tokens."""
        agent, _ = _make_agent(cache_size=256)
        agent.step()  # LLM call
        result = agent.step()  # Cache hit
        self.assertEqual(result.input_tokens, 0)
        self.assertEqual(result.output_tokens, 0)

    def test_cache_stats_accessible(self):
        """Cache stats are accessible from agent."""
        agent, _ = _make_agent(cache_size=256)
        agent.step()
        agent.step()
        stats = agent.action_cache.stats()
        self.assertIn("hit_rate", stats)
        self.assertGreater(stats["total_hits"], 0)

    def test_different_positions_no_cache_hit(self):
        """Different positions produce different cache keys -> no hit."""
        agent, llm = _make_agent(cache_size=256)
        agent.step()  # Position (5,4)
        self.assertEqual(llm.call_count, 1)
        # Move to new position
        agent.emulator.write_byte(0xDCB8, 8)  # x=8
        agent.step()  # Different position -> cache miss -> LLM call
        self.assertEqual(llm.call_count, 2)


class TestAutoAdvance(unittest.TestCase):
    """Test dialog auto-advance and escape (mewtoo patterns).

    S208 fix: dialog detection now uses text_reader.is_text_active() which checks
    the text buffer at 0xD073 (wStringBuffer1). More reliable than WINDOW_STACK/
    JOY_DISABLED flags which have non-zero values during normal Crystal overworld.
    _set_dialog writes non-terminator bytes to 0xD073 to simulate active dialog.
    """

    def _set_dialog(self, emu):
        """Set RAM to DIALOG state via text buffer approach (S208 fix).

        Writes WINDOW_STACK_SIZE > 0 so is_text_active() proceeds past the
        early-exit, then writes actual text bytes to wStringBuffer1 (0xD073)
        so the content check succeeds. 0x80 = 'A' in Crystal char encoding.
        """
        emu.write_byte(0xCF85, 1)   # WINDOW_STACK_SIZE > 0
        emu.write_byte(0xD073, 0x80)  # Text buffer: 'A' (non-zero, non-terminator)
        emu.write_byte(0xD074, 0x81)  # Text buffer: 'B'

    def _set_pokemon_center(self, emu):
        """Set RAM to POKEMON_CENTER state — uses battle mode=0 + text active."""
        # Pokemon Center healing uses text buffer too; simulate same way
        emu.write_byte(0xCF85, 1)
        emu.write_byte(0xD073, 0x80)
        emu.write_byte(0xD074, 0x81)

    def _clear_menu_state(self, emu):
        """Reset to overworld — clear all menu/dialog indicators."""
        emu.write_byte(0xCF85, 0)
        emu.write_byte(0xCF86, 0)
        emu.write_byte(0xCFA0, 0)
        emu.write_byte(0xD100, 0)
        emu.write_byte(0xD22D, 0)
        # Clear text buffer so is_text_active() returns False
        emu.write_byte(0xD073, 0x00)
        emu.write_byte(0xD074, 0x00)

    def test_dialog_auto_presses_a(self):
        """In DIALOG state, agent auto-presses A without calling LLM."""
        agent, llm = _make_agent()
        self._set_dialog(agent.emulator)
        result = agent.step()
        self.assertEqual(llm.call_count, 0)
        self.assertIn("auto", result.llm_text)
        self.assertEqual(result.input_tokens, 0)

    def test_pokemon_center_auto_presses_a(self):
        """In POKEMON_CENTER state, agent auto-presses A."""
        agent, llm = _make_agent()
        self._set_pokemon_center(agent.emulator)
        result = agent.step()
        self.assertEqual(llm.call_count, 0)

    def test_overworld_calls_llm(self):
        """In OVERWORLD state, agent calls LLM normally."""
        agent, llm = _make_agent()
        self._clear_menu_state(agent.emulator)
        result = agent.step()
        self.assertEqual(llm.call_count, 1)

    def test_auto_advance_count_tracked(self):
        """Auto-advance count increments for each auto step."""
        agent, llm = _make_agent()
        self._set_dialog(agent.emulator)
        agent.step()
        agent.step()
        agent.step()
        self.assertEqual(agent.auto_advance_count, 3)
        self.assertEqual(llm.call_count, 0)

    def test_dialog_escape_after_threshold(self):
        """After 7+ auto-A presses in dialog, switch to B."""
        agent, llm = _make_agent()
        self._set_dialog(agent.emulator)
        agent.DIALOG_ESCAPE_THRESHOLD = 3  # Lower for testing

        # First 3 steps: A (auto-advance)
        for _ in range(3):
            result = agent.step()
        self.assertIn("[auto-advance: a]", result.llm_text)

        # 4th step: should press B (escape attempt)
        result = agent.step()
        self.assertIn("[auto-advance: b]", result.llm_text)

    def test_b_press_resets_auto_counter(self):
        """After B escape attempt, consecutive counter resets."""
        agent, _ = _make_agent()
        self._set_dialog(agent.emulator)
        agent.DIALOG_ESCAPE_THRESHOLD = 2

        agent.step()  # a
        agent.step()  # a
        self.assertEqual(agent._consecutive_auto_a, 2)
        agent.step()  # b (escape)
        self.assertEqual(agent._consecutive_auto_a, 0)

    def test_leaving_dialog_resets_counter(self):
        """When exiting dialog to overworld, auto counter resets."""
        agent, _ = _make_agent()
        self._set_dialog(agent.emulator)
        agent.step()
        agent.step()
        self.assertEqual(agent._consecutive_auto_a, 2)

        # Switch to overworld
        self._clear_menu_state(agent.emulator)
        agent.step()  # This calls LLM
        self.assertEqual(agent._consecutive_auto_a, 0)

    def test_auto_advance_still_increments_step_count(self):
        """Auto-advance steps still count toward step_count."""
        agent, _ = _make_agent()
        self._set_dialog(agent.emulator)
        agent.step()
        agent.step()
        self.assertEqual(agent.step_count, 2)

    def test_auto_advance_fires_callback(self):
        """Step callbacks fire for auto-advance steps too."""
        captured = []
        agent, _ = _make_agent()
        agent.on_step(lambda r: captured.append(r.step_number))
        self._set_dialog(agent.emulator)
        agent.step()
        agent.step()
        self.assertEqual(captured, [1, 2])

    def test_mixed_auto_and_llm_steps(self):
        """Agent transitions between auto and LLM steps correctly."""
        agent, llm = _make_agent()

        # Step 1: dialog (auto)
        self._set_dialog(agent.emulator)
        r1 = agent.step()
        self.assertEqual(llm.call_count, 0)

        # Step 2: overworld (LLM)
        self._clear_menu_state(agent.emulator)
        r2 = agent.step()
        self.assertEqual(llm.call_count, 1)

        # Step 3: dialog again (auto)
        self._set_dialog(agent.emulator)
        r3 = agent.step()
        self.assertEqual(llm.call_count, 1)  # Still 1 — no new LLM call

    def test_auto_advance_zero_tokens(self):
        """Auto-advance steps use 0 tokens."""
        agent, _ = _make_agent()
        self._set_dialog(agent.emulator)
        agent.step()
        agent.step()
        agent.step()
        self.assertEqual(agent.total_input_tokens, 0)
        self.assertEqual(agent.total_output_tokens, 0)


if __name__ == "__main__":
    unittest.main()


class TestPersistentToolExecution(unittest.TestCase):
    """Persistent tool execution uses the existing agent_memory subsystem."""

    def _make_agent_with_temp_storage(self):
        agent, _ = _make_agent()
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        agent.agent_memory = AgentMemory(path=os.path.join(tmpdir.name, "memory.json"))
        agent.map_markers = MapMarkers(path=os.path.join(tmpdir.name, "markers.json"))
        agent.objectives = Objectives(path=os.path.join(tmpdir.name, "objectives.json"))
        return agent

    def test_write_memory_executes(self):
        agent = self._make_agent_with_temp_storage()
        result = agent._execute_tool(ToolUse(
            id="t1",
            name="write_memory",
            input={"key": "tips_intro", "value": "Clear dialog before moving"},
        ))
        self.assertEqual(result["memory_written"], "tips_intro")
        self.assertEqual(
            agent.agent_memory.read_all()["tips_intro"],
            "Clear dialog before moving",
        )

    def test_delete_memory_executes(self):
        agent = self._make_agent_with_temp_storage()
        agent.agent_memory.write("tips_intro", "Clear dialog before moving")
        result = agent._execute_tool(ToolUse(
            id="t2",
            name="delete_memory",
            input={"key": "tips_intro"},
        ))
        self.assertTrue(result["memory_deleted"])
        self.assertNotIn("tips_intro", agent.agent_memory.read_all())

    def test_add_marker_uses_current_map(self):
        agent = self._make_agent_with_temp_storage()
        result = agent._execute_tool(ToolUse(
            id="t3",
            name="add_marker",
            input={"x": 7, "y": 0, "label": "Stairs", "marker_type": "stairs"},
        ))
        current_map = agent.reader.read_game_state().position.map_id
        self.assertTrue(result["marker_added"])
        self.assertEqual(result["map_id"], current_map)
        markers = agent.map_markers.get_for_map(current_map)
        self.assertIn("7_0", markers)
        self.assertEqual(markers["7_0"]["label"], "Stairs")

    def test_delete_marker_uses_current_map(self):
        agent = self._make_agent_with_temp_storage()
        current_map = agent.reader.read_game_state().position.map_id
        agent.map_markers.add(current_map, 7, 0, "Stairs", "stairs")
        result = agent._execute_tool(ToolUse(
            id="t4",
            name="delete_marker",
            input={"x": 7, "y": 0},
        ))
        self.assertTrue(result["marker_deleted"])
        self.assertEqual(agent.map_markers.get_for_map(current_map), {})

    def test_update_objectives_executes(self):
        agent = self._make_agent_with_temp_storage()
        result = agent._execute_tool(ToolUse(
            id="t5",
            name="update_objectives",
            input={"objectives": [
                {
                    "description": "Leave Red's House",
                    "rationale": "Reach the overworld so the real run can begin",
                    "status": "active",
                },
                {
                    "description": "Talk to Oak",
                    "status": "completed",
                },
            ]},
        ))
        self.assertEqual(result["objectives_updated"], 2)
        self.assertEqual(result["active_objectives"], 1)
        self.assertEqual(agent.objectives.active()[0]["description"], "Leave Red's House")
