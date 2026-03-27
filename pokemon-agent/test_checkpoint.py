"""Tests for save-state checkpointing before risky actions.

The checkpoint system auto-saves emulator state before:
- Trainer/gym battles (can't retry without reload)
- Low HP situations (party lead < 25%)
- Badge attempts (gym leader fights)
- Map transitions to dangerous areas

Uses MockBackend so no ROM/PyBoy needed.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from checkpoint import CheckpointManager, CheckpointReason
from emulator_control import EmulatorControl
from game_state import (
    GameState, Party, Pokemon, MapPosition, BattleState, Badges, MenuState,
)


def make_pokemon(hp=50, hp_max=50, level=10, species="Cyndaquil"):
    return Pokemon(
        species=species, nickname=species, level=level,
        hp=hp, hp_max=hp_max,
        attack=30, defense=25, speed=35, sp_attack=40, sp_defense=30,
    )


def make_state(
    hp=50, hp_max=50, in_battle=False, is_trainer=False, is_wild=False,
    map_id=0x0301, x=5, y=5, badges=0, menu_state=MenuState.OVERWORLD,
):
    party = Party(pokemon=[make_pokemon(hp=hp, hp_max=hp_max)])
    battle = BattleState(
        in_battle=in_battle, is_trainer=is_trainer, is_wild=is_wild,
        enemy=make_pokemon(species="Rattata") if in_battle else None,
    )
    badge_obj = Badges(
        zephyr=bool(badges & 1), hive=bool(badges & 2),
        plain=bool(badges & 4), fog=bool(badges & 8),
    )
    return GameState(
        party=party,
        position=MapPosition(map_id=map_id, x=x, y=y),
        battle=battle,
        badges=badge_obj,
        menu_state=menu_state,
    )


class TestCheckpointReason(unittest.TestCase):
    """Test CheckpointReason enum."""

    def test_all_reasons_have_string_values(self):
        for reason in CheckpointReason:
            self.assertIsInstance(reason.value, str)

    def test_expected_reasons_exist(self):
        names = [r.name for r in CheckpointReason]
        self.assertIn("TRAINER_BATTLE", names)
        self.assertIn("LOW_HP", names)
        self.assertIn("GYM_LEADER", names)
        self.assertIn("MAP_TRANSITION", names)
        self.assertIn("MANUAL", names)


class TestCheckpointManager(unittest.TestCase):
    """Test CheckpointManager logic."""

    def setUp(self):
        self.emu = EmulatorControl.mock()
        self.emu.set_state_dir("/tmp/pokemon_test_states")
        self.mgr = CheckpointManager(self.emu, state_dir="/tmp/pokemon_test_states")

    def test_trainer_battle_triggers_checkpoint(self):
        prev = make_state(in_battle=False)
        curr = make_state(in_battle=True, is_trainer=True)
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertIn(CheckpointReason.TRAINER_BATTLE, reasons)

    def test_wild_battle_does_not_trigger(self):
        prev = make_state(in_battle=False)
        curr = make_state(in_battle=True, is_wild=True)
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertNotIn(CheckpointReason.TRAINER_BATTLE, reasons)

    def test_low_hp_triggers_checkpoint(self):
        prev = make_state(hp=50, hp_max=50)
        curr = make_state(hp=10, hp_max=50)  # 20% HP
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertIn(CheckpointReason.LOW_HP, reasons)

    def test_healthy_hp_does_not_trigger(self):
        prev = make_state(hp=50, hp_max=50)
        curr = make_state(hp=40, hp_max=50)  # 80% HP
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertNotIn(CheckpointReason.LOW_HP, reasons)

    def test_map_transition_triggers_checkpoint(self):
        prev = make_state(map_id=0x0301)
        curr = make_state(map_id=0x0302)
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertIn(CheckpointReason.MAP_TRANSITION, reasons)

    def test_same_map_does_not_trigger(self):
        prev = make_state(map_id=0x0301, x=5)
        curr = make_state(map_id=0x0301, x=6)
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertNotIn(CheckpointReason.MAP_TRANSITION, reasons)

    def test_gym_leader_triggers_checkpoint(self):
        """Entering a trainer battle on a gym map triggers GYM_LEADER."""
        prev = make_state(in_battle=False, map_id=0x0301)
        curr = make_state(in_battle=True, is_trainer=True, map_id=0x0301)
        # Register map as a gym
        self.mgr.register_gym_map(0x0301)
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertIn(CheckpointReason.GYM_LEADER, reasons)

    def test_non_gym_trainer_no_gym_reason(self):
        prev = make_state(in_battle=False, map_id=0x0505)
        curr = make_state(in_battle=True, is_trainer=True, map_id=0x0505)
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertNotIn(CheckpointReason.GYM_LEADER, reasons)

    def test_checkpoint_creates_state_file(self):
        reasons = [CheckpointReason.TRAINER_BATTLE]
        path = self.mgr.save_checkpoint(step=42, reasons=reasons)
        self.assertIn("step_42", path)
        self.assertIn("trainer_battle", path)

    def test_no_duplicate_checkpoints_within_cooldown(self):
        prev = make_state(map_id=0x0301)
        curr = make_state(map_id=0x0302)
        reasons1 = self.mgr.should_checkpoint(prev, curr, current_step=1)
        self.assertIn(CheckpointReason.MAP_TRANSITION, reasons1)

        # Save it
        self.mgr.save_checkpoint(step=1, reasons=reasons1)

        # Same transition right after (step 2) should be on cooldown
        reasons2 = self.mgr.should_checkpoint(prev, curr, current_step=2)
        self.assertEqual(len(reasons2), 0)

    def test_cooldown_expires(self):
        prev = make_state(map_id=0x0301)
        curr = make_state(map_id=0x0302)
        reasons1 = self.mgr.should_checkpoint(prev, curr, current_step=1)
        self.mgr.save_checkpoint(step=1, reasons=reasons1)

        # After cooldown (default=10), should trigger again
        reasons2 = self.mgr.should_checkpoint(prev, curr, current_step=100)
        self.assertIn(CheckpointReason.MAP_TRANSITION, reasons2)

    def test_manual_checkpoint_always_works(self):
        path = self.mgr.save_checkpoint(
            step=99, reasons=[CheckpointReason.MANUAL],
        )
        self.assertIn("step_99", path)
        self.assertIn("manual", path)

    def test_max_checkpoints_limit(self):
        """Old checkpoints get pruned when limit is reached."""
        self.mgr.max_checkpoints = 3
        paths = []
        for i in range(5):
            p = self.mgr.save_checkpoint(
                step=i, reasons=[CheckpointReason.MANUAL],
            )
            paths.append(p)
        self.assertLessEqual(len(self.mgr.checkpoint_history), 3)

    def test_checkpoint_history_tracking(self):
        self.mgr.save_checkpoint(step=10, reasons=[CheckpointReason.LOW_HP])
        self.mgr.save_checkpoint(step=20, reasons=[CheckpointReason.TRAINER_BATTLE])
        self.assertEqual(len(self.mgr.checkpoint_history), 2)
        self.assertEqual(self.mgr.checkpoint_history[0]["step"], 10)
        self.assertEqual(self.mgr.checkpoint_history[1]["step"], 20)

    def test_low_hp_threshold_configurable(self):
        mgr = CheckpointManager(self.emu, low_hp_threshold=0.5)
        prev = make_state(hp=50, hp_max=50)
        curr = make_state(hp=24, hp_max=50)  # 48% — below 50% threshold
        reasons = mgr.should_checkpoint(prev, curr)
        self.assertIn(CheckpointReason.LOW_HP, reasons)

    def test_badge_change_triggers_checkpoint(self):
        """Getting a new badge should trigger a checkpoint."""
        prev = make_state(badges=0)
        curr = make_state(badges=1)  # Got Zephyr badge
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertIn(CheckpointReason.BADGE_EARNED, reasons)

    def test_no_badge_change_no_trigger(self):
        prev = make_state(badges=1)
        curr = make_state(badges=1)
        reasons = self.mgr.should_checkpoint(prev, curr)
        self.assertNotIn(CheckpointReason.BADGE_EARNED, reasons)


if __name__ == "__main__":
    unittest.main()
