"""Tests for battle_ai.py — Pokemon Red battle decision engine.

Tests deterministic move selection based on type effectiveness,
move power, PP availability, and battle context (wild vs trainer).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from game_state import Pokemon, Move, BattleState, Party


class TestTypeEffectiveness(unittest.TestCase):
    """Test the Gen 1 type effectiveness chart."""

    def test_super_effective(self):
        from battle_ai import type_multiplier
        self.assertEqual(type_multiplier("Water", "Fire"), 2.0)
        self.assertEqual(type_multiplier("Fire", "Grass"), 2.0)
        self.assertEqual(type_multiplier("Electric", "Water"), 2.0)

    def test_not_very_effective(self):
        from battle_ai import type_multiplier
        self.assertEqual(type_multiplier("Fire", "Water"), 0.5)
        self.assertEqual(type_multiplier("Grass", "Fire"), 0.5)

    def test_immune(self):
        from battle_ai import type_multiplier
        self.assertEqual(type_multiplier("Normal", "Ghost"), 0.0)
        self.assertEqual(type_multiplier("Electric", "Ground"), 0.0)
        self.assertEqual(type_multiplier("Ground", "Flying"), 0.0)

    def test_neutral(self):
        from battle_ai import type_multiplier
        self.assertEqual(type_multiplier("Normal", "Normal"), 1.0)
        self.assertEqual(type_multiplier("Fire", "Normal"), 1.0)

    def test_unknown_type_returns_neutral(self):
        from battle_ai import type_multiplier
        self.assertEqual(type_multiplier("Fake", "Water"), 1.0)


class TestMoveScoring(unittest.TestCase):
    """Test move scoring for battle decisions."""

    def _make_move(self, name="Tackle", move_type="Normal", power=40, pp=35,
                   pp_max=35, accuracy=100):
        return Move(name=name, move_type=move_type, power=power,
                    accuracy=accuracy, pp=pp, pp_max=pp_max)

    def _make_pokemon(self, species="Charmander", types=None, level=10,
                      hp=30, hp_max=30, moves=None):
        return Pokemon(
            species=species, nickname=species, level=level,
            hp=hp, hp_max=hp_max, attack=20, defense=15,
            speed=20, sp_attack=20, sp_defense=15,
            pokemon_type=types or ["Fire"],
            moves=moves or [],
        )

    def test_higher_power_scores_higher(self):
        from battle_ai import score_move
        weak = self._make_move("Tackle", "Normal", power=40)
        strong = self._make_move("Strength", "Normal", power=80)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        self.assertGreater(score_move(strong, enemy), score_move(weak, enemy))

    def test_super_effective_boosts_score(self):
        from battle_ai import score_move
        water_gun = self._make_move("Water Gun", "Water", power=40)
        tackle = self._make_move("Tackle", "Normal", power=40)
        fire_enemy = self._make_pokemon("Charmander", ["Fire"])
        self.assertGreater(
            score_move(water_gun, fire_enemy),
            score_move(tackle, fire_enemy),
        )

    def test_zero_pp_scores_zero(self):
        from battle_ai import score_move
        empty = self._make_move("Tackle", "Normal", power=40, pp=0)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        self.assertEqual(score_move(empty, enemy), 0.0)

    def test_immune_scores_zero(self):
        from battle_ai import score_move
        normal_move = self._make_move("Tackle", "Normal", power=40)
        ghost_enemy = self._make_pokemon("Gastly", ["Ghost", "Poison"])
        self.assertEqual(score_move(normal_move, ghost_enemy), 0.0)

    def test_status_move_scores_zero(self):
        from battle_ai import score_move
        status = self._make_move("Growl", "Normal", power=0)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        self.assertEqual(score_move(status, enemy), 0.0)


class TestChooseAction(unittest.TestCase):
    """Test the main battle action chooser."""

    def _make_move(self, name, move_type, power, pp=35, pp_max=35, accuracy=100):
        return Move(name=name, move_type=move_type, power=power,
                    accuracy=accuracy, pp=pp, pp_max=pp_max)

    def _make_pokemon(self, species, types, level=10, hp=30, hp_max=30, moves=None):
        return Pokemon(
            species=species, nickname=species, level=level,
            hp=hp, hp_max=hp_max, attack=20, defense=15,
            speed=20, sp_attack=20, sp_defense=15,
            pokemon_type=types, moves=moves or [],
        )

    def test_choose_best_move(self):
        from battle_ai import choose_action
        moves = [
            self._make_move("Tackle", "Normal", 40),
            self._make_move("Ember", "Fire", 40),
        ]
        lead = self._make_pokemon("Charmander", ["Fire"], moves=moves)
        enemy = self._make_pokemon("Bulbasaur", ["Grass", "Poison"])
        party = Party(pokemon=[lead])

        action = choose_action(party, enemy, is_wild=True)
        self.assertEqual(action["type"], "fight")
        self.assertEqual(action["move_index"], 1)  # Ember is super effective

    def test_run_from_wild_when_no_damaging_moves(self):
        from battle_ai import choose_action
        moves = [self._make_move("Growl", "Normal", 0)]
        lead = self._make_pokemon("Charmander", ["Fire"], moves=moves)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        party = Party(pokemon=[lead])

        action = choose_action(party, enemy, is_wild=True)
        self.assertEqual(action["type"], "run")

    def test_fight_trainer_even_with_no_good_moves(self):
        """Can't run from trainers — must fight even with bad moves."""
        from battle_ai import choose_action
        moves = [self._make_move("Tackle", "Normal", 40, pp=1)]
        lead = self._make_pokemon("Charmander", ["Fire"], moves=moves)
        enemy = self._make_pokemon("Onix", ["Rock", "Ground"])
        party = Party(pokemon=[lead])

        action = choose_action(party, enemy, is_wild=False)
        self.assertEqual(action["type"], "fight")

    def test_struggle_when_all_pp_empty(self):
        """When no PP left, must use struggle (index 0)."""
        from battle_ai import choose_action
        moves = [self._make_move("Tackle", "Normal", 40, pp=0)]
        lead = self._make_pokemon("Charmander", ["Fire"], moves=moves)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        party = Party(pokemon=[lead])

        action = choose_action(party, enemy, is_wild=False)
        self.assertEqual(action["type"], "fight")
        self.assertEqual(action["move_index"], 0)  # Struggle fallback

    def test_action_includes_reasoning(self):
        from battle_ai import choose_action
        moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Charmander", ["Fire"], moves=moves)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        party = Party(pokemon=[lead])

        action = choose_action(party, enemy, is_wild=True)
        self.assertIn("reason", action)

    def test_to_buttons_fight(self):
        """Convert fight action to button presses."""
        from battle_ai import action_to_buttons
        action = {"type": "fight", "move_index": 0}
        buttons = action_to_buttons(action)
        self.assertIsInstance(buttons, list)
        self.assertTrue(len(buttons) > 0)

    def test_to_buttons_run(self):
        from battle_ai import action_to_buttons
        action = {"type": "run"}
        buttons = action_to_buttons(action)
        self.assertIsInstance(buttons, list)
        self.assertTrue(len(buttons) > 0)


class TestRedAgentBattleAI(unittest.TestCase):
    """Test battle AI integration in RedAgent."""

    def test_try_battle_ai_returns_none_outside_battle(self):
        from red_agent import RedAgent
        from emulator_control import EmulatorControl
        import memory_reader_red as mrr

        emu = EmulatorControl.mock(ram_size=0x10000)
        emu.write_byte(mrr.MAP_ID, 0)
        emu.write_byte(mrr.PLAYER_X, 5)
        emu.write_byte(mrr.PLAYER_Y, 5)
        emu.write_byte(mrr.PARTY_COUNT, 1)
        base = mrr.PARTY_BASE_ADDRS[0]
        emu.write_byte(base + mrr.OFF_SPECIES, 0xB0)
        emu.write_byte(base + mrr.OFF_LEVEL, 5)
        emu.write_byte(base + mrr.OFF_HP_LO, 20)
        emu.write_byte(base + mrr.OFF_MAX_HP_LO, 20)
        emu.write_byte(mrr.BATTLE_MODE, 0)  # Not in battle

        agent = RedAgent(emulator=emu)
        result = agent.try_battle_ai()
        self.assertIsNone(result)

    def test_try_battle_ai_returns_step_in_battle(self):
        from red_agent import RedAgent
        from emulator_control import EmulatorControl
        import memory_reader_red as mrr

        emu = EmulatorControl.mock(ram_size=0x10000)
        emu.write_byte(mrr.MAP_ID, 0)
        emu.write_byte(mrr.PLAYER_X, 5)
        emu.write_byte(mrr.PLAYER_Y, 5)
        emu.write_byte(mrr.PARTY_COUNT, 1)
        base = mrr.PARTY_BASE_ADDRS[0]
        emu.write_byte(base + mrr.OFF_SPECIES, 0xB0)  # Charmander
        emu.write_byte(base + mrr.OFF_LEVEL, 10)
        emu.write_byte(base + mrr.OFF_HP_LO, 30)
        emu.write_byte(base + mrr.OFF_MAX_HP_LO, 30)
        # Set move 1: Scratch (Normal, power 40)
        emu.write_byte(base + mrr.OFF_MOVE1, 10)  # Scratch
        emu.write_byte(base + mrr.OFF_PP1, 35)

        # Set battle state
        emu.write_byte(mrr.BATTLE_MODE, 1)  # Wild battle
        emu.write_byte(mrr.ENEMY_MON_SPECIES, 0xA5)  # Rattata
        emu.write_byte(mrr.ENEMY_MON_LEVEL, 3)
        emu.write_byte(mrr.ENEMY_MON_HP_LO, 12)
        emu.write_byte(mrr.ENEMY_MON_MAX_HP_LO, 12)

        agent = RedAgent(emulator=emu)
        result = agent.try_battle_ai()
        self.assertIsNotNone(result)
        self.assertIn("battle_ai", result.llm_text)

    def test_try_battle_ai_method_exists(self):
        from red_agent import RedAgent
        self.assertTrue(hasattr(RedAgent, 'try_battle_ai'))


if __name__ == "__main__":
    unittest.main()
