"""Tests for game_state.py — Pokemon game state dataclasses."""
import unittest

from game_state import (
    Move, Pokemon, Party, MapPosition, BattleState, Badges, GameState, TYPES,
)


class TestMove(unittest.TestCase):

    def test_damaging_move(self):
        m = Move("Tackle", "Normal", 40, 100, 35, 35, "physical")
        self.assertTrue(m.is_damaging())

    def test_status_move(self):
        m = Move("Growl", "Normal", 0, 100, 40, 40, "status")
        self.assertFalse(m.is_damaging())

    def test_pp_remaining(self):
        m = Move("Tackle", "Normal", 40, 100, 20, 35, "physical")
        self.assertAlmostEqual(m.pp_remaining_pct(), 20 / 35)

    def test_pp_remaining_zero_max(self):
        m = Move("Struggle", "Normal", 50, 100, 0, 0, "physical")
        self.assertEqual(m.pp_remaining_pct(), 0.0)


class TestPokemon(unittest.TestCase):

    def _make_pokemon(self, hp=100, hp_max=100, level=50, status="healthy"):
        return Pokemon(
            species="Feraligatr", nickname="CHOMPER", level=level,
            hp=hp, hp_max=hp_max, attack=105, defense=100, speed=78,
            sp_attack=79, sp_defense=83, pokemon_type=["Water"],
            moves=[
                Move("Surf", "Water", 90, 100, 15, 15, "special"),
                Move("Ice Punch", "Ice", 75, 100, 15, 15, "physical"),
                Move("Slash", "Normal", 70, 100, 20, 20, "physical"),
                Move("Bite", "Dark", 60, 100, 25, 25, "physical"),
            ],
            status=status,
        )

    def test_hp_pct(self):
        p = self._make_pokemon(hp=50, hp_max=100)
        self.assertAlmostEqual(p.hp_pct(), 0.5)

    def test_hp_pct_zero_max(self):
        p = self._make_pokemon(hp=0, hp_max=0)
        self.assertEqual(p.hp_pct(), 0.0)

    def test_is_fainted(self):
        p = self._make_pokemon(hp=0)
        self.assertTrue(p.is_fainted())

    def test_not_fainted(self):
        p = self._make_pokemon(hp=50)
        self.assertFalse(p.is_fainted())

    def test_is_healthy(self):
        p = self._make_pokemon(hp=100, status="healthy")
        self.assertTrue(p.is_healthy())

    def test_not_healthy_status(self):
        p = self._make_pokemon(hp=100, status="poisoned")
        self.assertFalse(p.is_healthy())

    def test_not_healthy_fainted(self):
        p = self._make_pokemon(hp=0, status="healthy")
        self.assertFalse(p.is_healthy())

    def test_has_usable_moves(self):
        p = self._make_pokemon()
        self.assertTrue(p.has_usable_moves())

    def test_no_usable_moves(self):
        p = self._make_pokemon()
        for m in p.moves:
            m.pp = 0
        self.assertFalse(p.has_usable_moves())

    def test_best_move_power(self):
        p = self._make_pokemon()
        self.assertEqual(p.best_move_power(), 90)  # Surf

    def test_best_move_power_no_pp(self):
        p = self._make_pokemon()
        for m in p.moves:
            m.pp = 0
        self.assertEqual(p.best_move_power(), 0)


class TestParty(unittest.TestCase):

    def _make_party(self, count=3):
        pokemon = []
        for i in range(count):
            pokemon.append(Pokemon(
                species=f"Mon{i}", nickname=f"MON{i}", level=30 + i * 5,
                hp=100, hp_max=100, attack=80, defense=80, speed=80,
                sp_attack=80, sp_defense=80, pokemon_type=["Normal"],
            ))
        return Party(pokemon=pokemon)

    def test_size(self):
        p = self._make_party(3)
        self.assertEqual(p.size(), 3)

    def test_alive_count(self):
        p = self._make_party(3)
        p.pokemon[1].hp = 0
        self.assertEqual(p.alive_count(), 2)

    def test_lead(self):
        p = self._make_party(3)
        self.assertEqual(p.lead().species, "Mon0")

    def test_lead_empty(self):
        p = Party()
        self.assertIsNone(p.lead())

    def test_all_fainted(self):
        p = self._make_party(2)
        p.pokemon[0].hp = 0
        p.pokemon[1].hp = 0
        self.assertTrue(p.all_fainted())

    def test_not_all_fainted(self):
        p = self._make_party(2)
        p.pokemon[0].hp = 0
        self.assertFalse(p.all_fainted())

    def test_empty_party_all_fainted(self):
        p = Party()
        self.assertTrue(p.all_fainted())

    def test_avg_level(self):
        p = self._make_party(3)  # levels 30, 35, 40
        self.assertAlmostEqual(p.avg_level(), 35.0)

    def test_avg_level_empty(self):
        p = Party()
        self.assertEqual(p.avg_level(), 0.0)

    def test_strongest(self):
        p = self._make_party(3)
        self.assertEqual(p.strongest().species, "Mon2")  # level 40

    def test_strongest_skips_fainted(self):
        p = self._make_party(3)
        p.pokemon[2].hp = 0  # faint the highest level
        self.assertEqual(p.strongest().species, "Mon1")

    def test_strongest_all_fainted(self):
        p = self._make_party(2)
        p.pokemon[0].hp = 0
        p.pokemon[1].hp = 0
        self.assertIsNone(p.strongest())


class TestMapPosition(unittest.TestCase):

    def test_equality(self):
        a = MapPosition(map_id=5, x=10, y=20)
        b = MapPosition(map_id=5, x=10, y=20)
        self.assertEqual(a, b)

    def test_inequality_map(self):
        a = MapPosition(map_id=5, x=10, y=20)
        b = MapPosition(map_id=6, x=10, y=20)
        self.assertNotEqual(a, b)

    def test_inequality_position(self):
        a = MapPosition(map_id=5, x=10, y=20)
        b = MapPosition(map_id=5, x=11, y=20)
        self.assertNotEqual(a, b)

    def test_inequality_other_type(self):
        a = MapPosition(map_id=5, x=10, y=20)
        self.assertNotEqual(a, "not a position")


class TestBattleState(unittest.TestCase):

    def test_no_battle(self):
        b = BattleState()
        self.assertEqual(b.battle_type(), "none")

    def test_wild_battle(self):
        b = BattleState(in_battle=True, is_wild=True)
        self.assertEqual(b.battle_type(), "wild")

    def test_trainer_battle(self):
        b = BattleState(in_battle=True, is_trainer=True)
        self.assertEqual(b.battle_type(), "trainer")


class TestBadges(unittest.TestCase):

    def test_no_badges(self):
        b = Badges()
        self.assertEqual(b.count(), 0)
        self.assertFalse(b.all_johto())

    def test_some_badges(self):
        b = Badges(zephyr=True, hive=True, plain=True)
        self.assertEqual(b.count(), 3)
        self.assertFalse(b.all_johto())

    def test_all_badges(self):
        b = Badges(
            zephyr=True, hive=True, plain=True, fog=True,
            storm=True, mineral=True, glacier=True, rising=True,
        )
        self.assertEqual(b.count(), 8)
        self.assertTrue(b.all_johto())


class TestGameState(unittest.TestCase):

    def test_defaults(self):
        gs = GameState()
        self.assertFalse(gs.is_in_battle())
        self.assertEqual(gs.money, 0)
        self.assertEqual(gs.badges.count(), 0)

    def test_in_battle(self):
        gs = GameState(battle=BattleState(in_battle=True, is_wild=True))
        self.assertTrue(gs.is_in_battle())

    def test_progress_no_data(self):
        gs = GameState()
        self.assertAlmostEqual(gs.progress_pct(), 0.0)

    def test_progress_mid_game(self):
        party = Party(pokemon=[
            Pokemon("Typhlosion", "BURNER", 36, 120, 120, 90, 78, 100, 109, 85,
                    ["Fire"]),
        ])
        badges = Badges(zephyr=True, hive=True, plain=True, fog=True)
        gs = GameState(party=party, badges=badges)
        progress = gs.progress_pct()
        self.assertGreater(progress, 30.0)
        self.assertLess(progress, 70.0)

    def test_progress_capped_at_100(self):
        party = Party(pokemon=[
            Pokemon("Mewtwo", "PSYCHO", 100, 400, 400, 150, 130, 130, 154, 90,
                    ["Psychic"]),
        ])
        badges = Badges(
            zephyr=True, hive=True, plain=True, fog=True,
            storm=True, mineral=True, glacier=True, rising=True,
        )
        gs = GameState(party=party, badges=badges)
        self.assertAlmostEqual(gs.progress_pct(), 100.0)


class TestTypes(unittest.TestCase):

    def test_types_list(self):
        self.assertIn("Water", TYPES)
        self.assertIn("Fire", TYPES)
        self.assertIn("Dark", TYPES)
        self.assertEqual(len(TYPES), 17)  # Gen 2 has 17 types (no Fairy)


if __name__ == "__main__":
    unittest.main()
