"""Tests for battle_ai.py — Pokemon Red battle decision engine.

Tests deterministic move selection based on type effectiveness,
move power, PP availability, and battle context (wild vs trainer).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from game_state import Item, Pokemon, Move, BattleState, Party


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


class TestThreatAssessment(unittest.TestCase):
    """Test enemy threat assessment."""

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

    def test_high_threat_4x_weakness(self):
        from battle_ai import assess_threat
        # Water move vs Ground/Rock (4x effective)
        enemy = self._make_pokemon("Blastoise", ["Water"],
                                   moves=[self._make_move("Surf", "Water", 95)])
        defender = self._make_pokemon("Golem", ["Rock", "Ground"])
        threat = assess_threat(enemy, defender)
        self.assertEqual(threat["level"], "high")

    def test_medium_threat_2x_weakness(self):
        from battle_ai import assess_threat
        enemy = self._make_pokemon("Charmander", ["Fire"],
                                   moves=[self._make_move("Ember", "Fire", 40)])
        defender = self._make_pokemon("Bulbasaur", ["Grass", "Poison"])
        threat = assess_threat(enemy, defender)
        self.assertEqual(threat["level"], "medium")

    def test_low_threat_neutral(self):
        from battle_ai import assess_threat
        enemy = self._make_pokemon("Rattata", ["Normal"],
                                   moves=[self._make_move("Tackle", "Normal", 40)])
        defender = self._make_pokemon("Pidgey", ["Normal", "Flying"])
        threat = assess_threat(enemy, defender)
        self.assertEqual(threat["level"], "low")

    def test_unknown_threat_no_moves(self):
        from battle_ai import assess_threat
        enemy = self._make_pokemon("Rattata", ["Normal"], moves=[])
        defender = self._make_pokemon("Pidgey", ["Normal", "Flying"])
        threat = assess_threat(enemy, defender)
        self.assertEqual(threat["level"], "unknown")

    def test_threat_includes_best_move(self):
        from battle_ai import assess_threat
        enemy = self._make_pokemon("Charmander", ["Fire"],
                                   moves=[self._make_move("Ember", "Fire", 40),
                                          self._make_move("Scratch", "Normal", 40)])
        defender = self._make_pokemon("Bulbasaur", ["Grass", "Poison"])
        threat = assess_threat(enemy, defender)
        self.assertEqual(threat["best_move"], "Ember")


class TestThreatBasedFleeing(unittest.TestCase):
    """Test that choose_action flees from dangerous wild encounters."""

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

    def test_flee_high_threat_low_hp(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Golem", ["Rock", "Ground"],
                                  hp=10, hp_max=30, moves=our_moves)
        enemy = self._make_pokemon("Blastoise", ["Water"],
                                   moves=[self._make_move("Surf", "Water", 95)])
        party = Party(pokemon=[lead])
        action = choose_action(party, enemy, is_wild=True)
        self.assertEqual(action["type"], "run")

    def test_fight_high_threat_full_hp(self):
        """Don't flee if HP is high enough."""
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Golem", ["Rock", "Ground"],
                                  hp=30, hp_max=30, moves=our_moves)
        enemy = self._make_pokemon("Blastoise", ["Water"],
                                   moves=[self._make_move("Surf", "Water", 95)])
        party = Party(pokemon=[lead])
        action = choose_action(party, enemy, is_wild=True)
        self.assertEqual(action["type"], "fight")

    def test_no_flee_from_trainers(self):
        """Never flee trainer battles regardless of threat."""
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Golem", ["Rock", "Ground"],
                                  hp=5, hp_max=30, moves=our_moves)
        enemy = self._make_pokemon("Blastoise", ["Water"],
                                   moves=[self._make_move("Surf", "Water", 95)])
        party = Party(pokemon=[lead])
        action = choose_action(party, enemy, is_wild=False)
        self.assertEqual(action["type"], "fight")

    def test_flee_medium_threat_very_low_hp(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Bulbasaur", ["Grass", "Poison"],
                                  hp=5, hp_max=30, moves=our_moves)
        enemy = self._make_pokemon("Charmander", ["Fire"],
                                   moves=[self._make_move("Ember", "Fire", 40)])
        party = Party(pokemon=[lead])
        action = choose_action(party, enemy, is_wild=True)
        self.assertEqual(action["type"], "run")


class TestBestPotion(unittest.TestCase):
    """Test potion selection logic."""

    def test_picks_smallest_sufficient(self):
        from battle_ai import best_potion
        items = [
            Item(0x13, "POTION", 3),         # heals 20
            Item(0x12, "SUPER POTION", 2),   # heals 50
            Item(0x11, "HYPER POTION", 1),   # heals 200
        ]
        # Need 30 HP — Super Potion is smallest that covers it
        result = best_potion(items, 30)
        self.assertEqual(result.name, "SUPER POTION")

    def test_picks_strongest_when_none_covers(self):
        from battle_ai import best_potion
        items = [
            Item(0x13, "POTION", 3),         # heals 20
            Item(0x12, "SUPER POTION", 2),   # heals 50
        ]
        # Need 100 HP — nothing covers it, use strongest
        result = best_potion(items, 100)
        self.assertEqual(result.name, "SUPER POTION")

    def test_returns_none_with_no_potions(self):
        from battle_ai import best_potion
        items = [Item(0x04, "POKE BALL", 5)]
        result = best_potion(items, 30)
        self.assertIsNone(result)

    def test_returns_none_with_empty_items(self):
        from battle_ai import best_potion
        result = best_potion([], 30)
        self.assertIsNone(result)

    def test_skips_zero_quantity(self):
        from battle_ai import best_potion
        items = [Item(0x13, "POTION", 0)]
        result = best_potion(items, 10)
        self.assertIsNone(result)


class TestPotionUseInBattle(unittest.TestCase):
    """Test that choose_action uses potions when HP is critical."""

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

    def test_use_potion_at_critical_hp(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Charmander", ["Fire"], hp=5, hp_max=30, moves=our_moves)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        party = Party(pokemon=[lead])
        items = [Item(0x13, "POTION", 3)]
        action = choose_action(party, enemy, is_wild=False, items=items)
        self.assertEqual(action["type"], "item")
        self.assertEqual(action["item_name"], "POTION")

    def test_no_potion_at_healthy_hp(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Charmander", ["Fire"], hp=25, hp_max=30, moves=our_moves)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        party = Party(pokemon=[lead])
        items = [Item(0x13, "POTION", 3)]
        action = choose_action(party, enemy, is_wild=False, items=items)
        self.assertEqual(action["type"], "fight")

    def test_no_potion_without_items(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Charmander", ["Fire"], hp=5, hp_max=30, moves=our_moves)
        enemy = self._make_pokemon("Rattata", ["Normal"])
        party = Party(pokemon=[lead])
        action = choose_action(party, enemy, is_wild=False, items=None)
        self.assertEqual(action["type"], "fight")

    def test_item_buttons(self):
        from battle_ai import action_to_buttons
        action = {"type": "item", "item_id": 0x13, "item_name": "POTION"}
        buttons = action_to_buttons(action)
        self.assertIsInstance(buttons, list)
        self.assertIn("right", buttons)  # Navigate to ITEM in menu


class TestBestPokeball(unittest.TestCase):
    """Test pokeball selection logic."""

    def test_picks_weakest_first(self):
        from battle_ai import best_pokeball
        items = [
            Item(0x02, "ULTRA BALL", 2),
            Item(0x04, "POKE BALL", 5),
            Item(0x03, "GREAT BALL", 3),
        ]
        result = best_pokeball(items)
        self.assertEqual(result.name, "POKE BALL")

    def test_returns_none_with_no_balls(self):
        from battle_ai import best_pokeball
        items = [Item(0x13, "POTION", 3)]
        result = best_pokeball(items)
        self.assertIsNone(result)

    def test_skips_zero_quantity(self):
        from battle_ai import best_pokeball
        items = [Item(0x04, "POKE BALL", 0), Item(0x03, "GREAT BALL", 2)]
        result = best_pokeball(items)
        self.assertEqual(result.name, "GREAT BALL")


class TestCatchLogic(unittest.TestCase):
    """Test catch attempt in wild battles."""

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

    def test_catch_wild_with_room(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Charmander", ["Fire"], moves=our_moves)
        enemy = self._make_pokemon("Pidgey", ["Normal", "Flying"])
        party = Party(pokemon=[lead])  # 1 Pokemon = room for 5 more
        items = [Item(0x04, "POKE BALL", 5)]
        action = choose_action(party, enemy, is_wild=True, items=items)
        self.assertEqual(action["type"], "item")
        self.assertIn("catch", action["reason"])

    def test_no_catch_without_balls(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Charmander", ["Fire"], moves=our_moves)
        enemy = self._make_pokemon("Pidgey", ["Normal", "Flying"])
        party = Party(pokemon=[lead])
        items = [Item(0x13, "POTION", 3)]  # No balls
        action = choose_action(party, enemy, is_wild=True, items=items)
        self.assertEqual(action["type"], "fight")

    def test_no_catch_trainer_battle(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Charmander", ["Fire"], moves=our_moves)
        enemy = self._make_pokemon("Pidgey", ["Normal", "Flying"])
        party = Party(pokemon=[lead])
        items = [Item(0x04, "POKE BALL", 5)]
        action = choose_action(party, enemy, is_wild=False, items=items)
        self.assertEqual(action["type"], "fight")  # Can't catch trainer Pokemon

    def test_no_catch_full_party(self):
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        mons = [self._make_pokemon(f"Mon{i}", ["Normal"], moves=our_moves) for i in range(6)]
        enemy = self._make_pokemon("Pidgey", ["Normal", "Flying"])
        party = Party(pokemon=mons)  # Full party
        items = [Item(0x04, "POKE BALL", 5)]
        action = choose_action(party, enemy, is_wild=True, items=items)
        self.assertNotEqual(action.get("reason", ""), "catch")  # Should fight, not catch

    def test_potion_before_catch_when_critical(self):
        """Healing takes priority over catching when HP is critical."""
        from battle_ai import choose_action
        our_moves = [self._make_move("Tackle", "Normal", 40)]
        lead = self._make_pokemon("Charmander", ["Fire"], hp=3, hp_max=30, moves=our_moves)
        enemy = self._make_pokemon("Pidgey", ["Normal", "Flying"])
        party = Party(pokemon=[lead])
        items = [Item(0x04, "POKE BALL", 5), Item(0x13, "POTION", 2)]
        action = choose_action(party, enemy, is_wild=True, items=items)
        # Should heal first (potion check is before catch check)
        self.assertEqual(action["type"], "item")
        self.assertIn("heal", action["reason"])


if __name__ == "__main__":
    unittest.main()
