"""Tests for prompts.py — system prompts and message formatting."""
import unittest

from game_state import (
    Badges, BattleState, GameState, MapPosition, Move, Party, Pokemon,
)
from prompts import (
    SYSTEM_PROMPT, SUMMARY_PROMPT, STUCK_PROMPT,
    format_game_state, build_user_message, build_summary_request,
    encode_screenshot_b64,
)


def _make_pokemon(species="Cyndaquil", level=10, hp=30, hp_max=30,
                  status="healthy", moves=None):
    """Helper to build a Pokemon for tests."""
    if moves is None:
        moves = [Move(name="Tackle", move_type="Normal", power=40,
                      accuracy=100, pp=35, pp_max=35)]
    return Pokemon(
        species=species, nickname=species, level=level,
        hp=hp, hp_max=hp_max,
        attack=30, defense=25, speed=35, sp_attack=40, sp_defense=30,
        moves=moves, status=status,
    )


def _make_game_state(**kwargs):
    """Helper to build a GameState with sensible defaults."""
    defaults = {
        "party": Party(pokemon=[_make_pokemon()]),
        "position": MapPosition(map_id=0x0301, map_name="New Bark Town", x=5, y=4),
        "battle": BattleState(),
        "badges": Badges(),
        "money": 3000,
        "play_time_minutes": 95,
        "step_count": 42,
    }
    defaults.update(kwargs)
    return GameState(**defaults)


class TestSystemPrompt(unittest.TestCase):
    """Validate system prompt content."""

    def test_prompt_mentions_pokemon_crystal(self):
        self.assertIn("Pokemon Crystal", SYSTEM_PROMPT)

    def test_prompt_mentions_ram_ground_truth(self):
        self.assertIn("ground truth", SYSTEM_PROMPT.lower())

    def test_prompt_mentions_16_badges_goal(self):
        self.assertIn("Johto", SYSTEM_PROMPT)
        self.assertIn("Kanto", SYSTEM_PROMPT)
        self.assertIn("Red", SYSTEM_PROMPT)

    def test_prompt_has_stuck_advice(self):
        self.assertIn("stuck", SYSTEM_PROMPT.lower())

    def test_prompt_has_encouragement(self):
        # S201 agent finding: models blackpill without encouragement
        self.assertIn("doing great", SYSTEM_PROMPT.lower())

    def test_prompt_mentions_tools(self):
        self.assertIn("press_buttons", SYSTEM_PROMPT)
        self.assertIn("navigate_to", SYSTEM_PROMPT)


class TestSummaryPrompt(unittest.TestCase):
    """Validate summarization prompt."""

    def test_summary_mentions_location(self):
        self.assertIn("LOCATION", SUMMARY_PROMPT)

    def test_summary_mentions_team(self):
        self.assertIn("POKEMON TEAM", SUMMARY_PROMPT)

    def test_summary_mentions_badges(self):
        self.assertIn("BADGES", SUMMARY_PROMPT)

    def test_summary_mentions_obstacles(self):
        self.assertIn("OBSTACLES", SUMMARY_PROMPT)

    def test_summary_mentions_next_steps(self):
        self.assertIn("NEXT STEPS", SUMMARY_PROMPT)


class TestStuckPrompt(unittest.TestCase):
    """Validate stuck detection prompt."""

    def test_stuck_prompt_has_placeholder(self):
        self.assertIn("{turns}", STUCK_PROMPT)

    def test_stuck_prompt_formats_correctly(self):
        formatted = STUCK_PROMPT.format(turns=15)
        self.assertIn("15", formatted)
        self.assertNotIn("{turns}", formatted)

    def test_stuck_prompt_says_change_approach(self):
        lower = STUCK_PROMPT.lower()
        self.assertIn("different", lower)


class TestFormatGameState(unittest.TestCase):
    """Validate game state formatting for LLM."""

    def test_basic_format(self):
        state = _make_game_state()
        text = format_game_state(state)
        self.assertIn("GAME STATE", text)
        self.assertIn("ground truth", text.lower())

    def test_shows_position(self):
        state = _make_game_state()
        text = format_game_state(state)
        self.assertIn("New Bark Town", text)
        self.assertIn("X=5", text)
        self.assertIn("Y=4", text)

    def test_shows_badges_none(self):
        state = _make_game_state()
        text = format_game_state(state)
        self.assertIn("0/8", text)
        self.assertIn("none", text)

    def test_shows_badges_some(self):
        badges = Badges(zephyr=True, hive=True, plain=True)
        state = _make_game_state(badges=badges)
        text = format_game_state(state)
        self.assertIn("3/8", text)
        self.assertIn("Zephyr", text)
        self.assertIn("Hive", text)
        self.assertIn("Plain", text)

    def test_shows_party(self):
        state = _make_game_state()
        text = format_game_state(state)
        self.assertIn("Cyndaquil", text)
        self.assertIn("Lv10", text)
        self.assertIn("Tackle", text)

    def test_shows_hp_percentage(self):
        mon = _make_pokemon(hp=15, hp_max=30)
        state = _make_game_state(party=Party(pokemon=[mon]))
        text = format_game_state(state)
        self.assertIn("50%", text)

    def test_shows_status_condition(self):
        mon = _make_pokemon(status="poisoned")
        state = _make_game_state(party=Party(pokemon=[mon]))
        text = format_game_state(state)
        self.assertIn("[poisoned]", text)

    def test_shows_money(self):
        state = _make_game_state(money=12345)
        text = format_game_state(state)
        self.assertIn("$12345", text)

    def test_shows_play_time(self):
        state = _make_game_state(play_time_minutes=95)
        text = format_game_state(state)
        self.assertIn("1h 35m", text)

    def test_shows_battle_state_wild(self):
        enemy = _make_pokemon(species="Pidgey", level=5, hp=18, hp_max=18)
        battle = BattleState(in_battle=True, is_wild=True, enemy=enemy)
        state = _make_game_state(battle=battle)
        text = format_game_state(state)
        self.assertIn("BATTLE (Wild)", text)
        self.assertIn("Pidgey", text)
        self.assertIn("Lv5", text)

    def test_shows_battle_state_trainer(self):
        enemy = _make_pokemon(species="Geodude", level=12)
        battle = BattleState(in_battle=True, is_trainer=True, enemy=enemy)
        state = _make_game_state(battle=battle)
        text = format_game_state(state)
        self.assertIn("BATTLE (Trainer)", text)

    def test_not_in_battle(self):
        state = _make_game_state()
        text = format_game_state(state)
        self.assertIn("Not in battle", text)

    def test_multiple_pokemon(self):
        party = Party(pokemon=[
            _make_pokemon("Cyndaquil", level=14),
            _make_pokemon("Pidgey", level=8),
            _make_pokemon("Geodude", level=10),
        ])
        state = _make_game_state(party=party)
        text = format_game_state(state)
        self.assertIn("3 Pokemon", text)
        self.assertIn("1. Cyndaquil", text)
        self.assertIn("2. Pidgey", text)
        self.assertIn("3. Geodude", text)

    def test_fainted_pokemon_shows_zero_hp(self):
        mon = _make_pokemon(hp=0, hp_max=30)
        state = _make_game_state(party=Party(pokemon=[mon]))
        text = format_game_state(state)
        self.assertIn("0/30", text)
        self.assertIn("0%", text)


class TestBuildUserMessage(unittest.TestCase):
    """Validate user message construction."""

    def test_message_has_role_user(self):
        state = _make_game_state()
        msg = build_user_message(state)
        self.assertEqual(msg["role"], "user")

    def test_message_has_content_list(self):
        state = _make_game_state()
        msg = build_user_message(state)
        self.assertIsInstance(msg["content"], list)

    def test_text_only_no_screenshot(self):
        state = _make_game_state()
        msg = build_user_message(state)
        # Should have exactly 1 content block (text)
        self.assertEqual(len(msg["content"]), 1)
        self.assertEqual(msg["content"][0]["type"], "text")

    def test_with_screenshot(self):
        state = _make_game_state()
        msg = build_user_message(state, screenshot_b64="AAAA")
        # Should have 2 content blocks (image + text)
        self.assertEqual(len(msg["content"]), 2)
        self.assertEqual(msg["content"][0]["type"], "image")
        self.assertEqual(msg["content"][1]["type"], "text")

    def test_screenshot_format(self):
        state = _make_game_state()
        msg = build_user_message(state, screenshot_b64="AAAA")
        img = msg["content"][0]
        self.assertEqual(img["source"]["type"], "base64")
        self.assertEqual(img["source"]["media_type"], "image/png")
        self.assertEqual(img["source"]["data"], "AAAA")

    def test_stuck_warning_included(self):
        state = _make_game_state()
        msg = build_user_message(state, stuck_turns=15)
        text = msg["content"][0]["text"]  # text-only, no screenshot
        self.assertIn("STUCK", text)
        self.assertIn("15", text)

    def test_no_stuck_warning_at_zero(self):
        state = _make_game_state()
        msg = build_user_message(state, stuck_turns=0)
        text = msg["content"][0]["text"]
        self.assertNotIn("STUCK", text)

    def test_step_number_shown(self):
        state = _make_game_state()
        msg = build_user_message(state, step_number=42)
        text = msg["content"][0]["text"]
        self.assertIn("[Step 42]", text)


class TestBuildSummaryRequest(unittest.TestCase):
    """Validate summary request message."""

    def test_summary_request_role(self):
        msg = build_summary_request()
        self.assertEqual(msg["role"], "user")

    def test_summary_request_has_prompt(self):
        msg = build_summary_request()
        text = msg["content"][0]["text"]
        self.assertIn("Summarize", text)


class TestEncodeScreenshot(unittest.TestCase):
    """Validate screenshot encoding."""

    def test_encode_bytes(self):
        data = b"\x89PNG\r\n\x1a\n"  # PNG header
        result = encode_screenshot_b64(data)
        self.assertIsInstance(result, str)
        # Should round-trip
        import base64
        decoded = base64.b64decode(result)
        self.assertEqual(decoded, data)

    def test_empty_bytes(self):
        result = encode_screenshot_b64(b"")
        self.assertEqual(result, "")


class TestStuckContextFormatting(unittest.TestCase):
    """Test enhanced stuck detection: self-anchoring counter + encouragement."""

    def test_format_stuck_context_empty(self):
        """No failed strategies produces no anonymized section."""
        from prompts import format_stuck_context
        result = format_stuck_context([], stuck_turns=5)
        self.assertNotIn("previous AI", result)

    def test_format_stuck_context_anonymizes(self):
        """Failed strategies are presented as 'another AI' attempts."""
        from prompts import format_stuck_context
        strategies = [["right", "right", "right"], ["a", "a", "start"]]
        result = format_stuck_context(strategies, stuck_turns=10)
        self.assertIn("previous AI", result)
        # Should mention the button sequences
        self.assertIn("right", result)
        self.assertIn("start", result)

    def test_format_stuck_context_limits_strategies(self):
        """Only last N strategies are shown (not unlimited)."""
        from prompts import format_stuck_context
        strategies = [["a"]] * 20  # Way more than limit
        result = format_stuck_context(strategies, stuck_turns=15)
        # Should not include all 20
        count = result.count("previous AI") if "previous AI" in result else result.count("AI tried")
        self.assertLessEqual(count, 5)

    def test_format_stuck_context_includes_turn_count(self):
        """Stuck context mentions how many turns stuck."""
        from prompts import format_stuck_context
        strategies = [["up", "up"]]
        result = format_stuck_context(strategies, stuck_turns=12)
        self.assertIn("12", result)

    def test_get_encouragement_level_1(self):
        """Low stuck count gets mild encouragement."""
        from prompts import get_encouragement
        msg = get_encouragement(stuck_turns=10)
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 0)

    def test_get_encouragement_level_2(self):
        """Medium stuck count gets stronger encouragement."""
        from prompts import get_encouragement
        msg1 = get_encouragement(stuck_turns=10)
        msg2 = get_encouragement(stuck_turns=20)
        # Level 2 should be different from level 1
        self.assertNotEqual(msg1, msg2)

    def test_get_encouragement_level_3(self):
        """High stuck count gets strongest encouragement."""
        from prompts import get_encouragement
        msg2 = get_encouragement(stuck_turns=20)
        msg3 = get_encouragement(stuck_turns=30)
        # Level 3 should be different from level 2
        self.assertNotEqual(msg2, msg3)

    def test_get_encouragement_caps_at_level_3(self):
        """Very high stuck count still returns level 3 (no crash)."""
        from prompts import get_encouragement
        msg = get_encouragement(stuck_turns=100)
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 0)

    def test_build_stuck_message_integrates_context(self):
        """build_stuck_message combines prompt + context + encouragement."""
        from prompts import build_stuck_message
        strategies = [["down", "down", "a"]]
        result = build_stuck_message(stuck_turns=15, failed_strategies=strategies)
        # Should have stuck warning
        self.assertIn("STUCK", result)
        # Should have anonymized strategy
        self.assertIn("down", result)
        # Should have encouragement
        self.assertGreater(len(result), 100)

    def test_build_stuck_message_no_strategies(self):
        """build_stuck_message works with empty strategy list."""
        from prompts import build_stuck_message
        result = build_stuck_message(stuck_turns=10, failed_strategies=[])
        self.assertIn("STUCK", result)

    def test_build_user_message_uses_stuck_context(self):
        """build_user_message passes failed strategies when stuck."""
        from prompts import build_user_message
        state = _make_game_state()
        msg = build_user_message(
            state=state,
            stuck_turns=10,
            step_number=50,
            failed_strategies=[["right", "right"]],
        )
        text = msg["content"][-1]["text"]
        self.assertIn("STUCK", text)


class TestAgentStrategyTracking(unittest.TestCase):
    """Test that CrystalAgent tracks failed strategies for stuck detection."""

    def test_agent_tracks_strategies(self):
        """Agent should accumulate pressed button sequences."""
        from agent import CrystalAgent, MockLLMClient, LLMResponse, ToolUse
        from emulator_control import EmulatorControl
        from memory_reader import MemoryReader

        emu = EmulatorControl.mock()
        emu.write_byte(0xDCD7, 1)
        emu.write_byte(0xDCDF + 0, 155)
        emu.write_byte(0xDCDF + 31, 10)
        emu.write_byte(0xDCDF + 34, 0)
        emu.write_byte(0xDCDF + 35, 30)
        emu.write_byte(0xDCDF + 36, 0)
        emu.write_byte(0xDCDF + 37, 30)
        emu.write_byte(0xDCDF + 2, 33)
        emu.write_byte(0xDCB5, 3)
        emu.write_byte(0xDCB6, 1)
        emu.write_byte(0xDCB8, 5)
        emu.write_byte(0xDCB7, 4)

        reader = MemoryReader(emu)
        # Need threshold+1 steps at same position to be "stuck" and track strategies
        # Use stuck_threshold=3 so we hit stuck on step 3
        responses = []
        for i in range(5):
            responses.append(LLMResponse(
                text=f"step {i}", tool_uses=[
                    ToolUse(id=f"t{i}", name="press_buttons",
                            input={"buttons": ["right", "right"]})
                ],
            ))
        llm = MockLLMClient(responses=responses)
        agent = CrystalAgent(emulator=emu, reader=reader, llm=llm, stuck_threshold=3)

        # Run enough steps to trigger stuck (position never changes in mock)
        for _ in range(5):
            agent.step()

        # Agent should have tracked button sequences once stuck
        self.assertTrue(hasattr(agent, '_failed_strategies'))
        self.assertGreaterEqual(len(agent._failed_strategies), 1)

    def test_strategy_memory_limited(self):
        """Agent should only keep last N strategies."""
        from agent import CrystalAgent, MockLLMClient, LLMResponse, ToolUse
        from emulator_control import EmulatorControl
        from memory_reader import MemoryReader

        emu = EmulatorControl.mock()
        emu.write_byte(0xDCD7, 1)
        emu.write_byte(0xDCDF + 0, 155)
        emu.write_byte(0xDCDF + 31, 10)
        emu.write_byte(0xDCDF + 34, 0)
        emu.write_byte(0xDCDF + 35, 30)
        emu.write_byte(0xDCDF + 36, 0)
        emu.write_byte(0xDCDF + 37, 30)
        emu.write_byte(0xDCDF + 2, 33)
        emu.write_byte(0xDCB5, 3)
        emu.write_byte(0xDCB6, 1)
        emu.write_byte(0xDCB8, 5)
        emu.write_byte(0xDCB7, 4)

        reader = MemoryReader(emu)
        llm = MockLLMClient()  # Default responses
        agent = CrystalAgent(emulator=emu, reader=reader, llm=llm, stuck_threshold=5)

        # Run many steps (all same position = stuck)
        for _ in range(15):
            agent.step()

        # Should be capped
        from config import STUCK_STRATEGY_MEMORY
        self.assertLessEqual(len(agent._failed_strategies), STUCK_STRATEGY_MEMORY)


if __name__ == "__main__":
    unittest.main()
