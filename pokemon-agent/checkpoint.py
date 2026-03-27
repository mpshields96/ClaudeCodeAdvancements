"""Save-state checkpointing before risky actions.

Automatically saves emulator state before situations where the player
could lose progress: trainer battles, gym leaders, low HP, map transitions.

The agent can reload these checkpoints if things go wrong (e.g., party wipe).

Usage:
    from checkpoint import CheckpointManager
    mgr = CheckpointManager(emulator, state_dir="states")

    # In the agent loop:
    reasons = mgr.should_checkpoint(prev_state, curr_state)
    if reasons:
        mgr.save_checkpoint(step=agent.step_count, reasons=reasons)

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Dict, List, Optional, Set

from emulator_control import EmulatorControl
from game_state import GameState


class CheckpointReason(Enum):
    """Why a checkpoint was created."""
    TRAINER_BATTLE = "trainer_battle"
    LOW_HP = "low_hp"
    GYM_LEADER = "gym_leader"
    MAP_TRANSITION = "map_transition"
    BADGE_EARNED = "badge_earned"
    MANUAL = "manual"


# Default cooldown: minimum steps between checkpoints of the same reason
DEFAULT_COOLDOWN = 10

# Pokemon Crystal gym map IDs (group << 8 | number)
# Source: pret/pokecrystal maps/
CRYSTAL_GYM_MAPS = {
    0x0304: "Violet City Gym (Falkner)",
    0x0605: "Azalea Town Gym (Bugsy)",
    0x0709: "Goldenrod City Gym (Whitney)",
    0x0905: "Ecruteak City Gym (Morty)",
    0x0A06: "Cianwood City Gym (Chuck)",
    0x0A04: "Olivine City Gym (Jasmine)",
    0x0B04: "Mahogany Town Gym (Pryce)",
    0x0C06: "Blackthorn City Gym (Clair)",
    # Kanto gyms
    0x0207: "Pewter City Gym (Brock)",
    0x0306: "Cerulean City Gym (Misty)",
    0x0504: "Vermilion City Gym (Lt. Surge)",
    0x0706: "Celadon City Gym (Erika)",
    0x0806: "Fuchsia City Gym (Janine)",
    0x0905: "Saffron City Gym (Sabrina)",
    0x0103: "Viridian City Gym (Blue)",
    0x0A03: "Cinnabar Gym (Blaine)",
}


class CheckpointManager:
    """Manages automatic save-state checkpoints.

    Monitors game state transitions and saves emulator state before
    risky situations. Keeps a bounded history of checkpoints and
    prunes old ones when the limit is reached.
    """

    def __init__(
        self,
        emulator: EmulatorControl,
        state_dir: str = "states",
        low_hp_threshold: float = 0.25,
        cooldown: int = DEFAULT_COOLDOWN,
        max_checkpoints: int = 20,
    ):
        self.emulator = emulator
        self.state_dir = state_dir
        self.low_hp_threshold = low_hp_threshold
        self.cooldown = cooldown
        self.max_checkpoints = max_checkpoints

        self._gym_maps: Set[int] = set()
        self._last_checkpoint_step: int = -100
        self.checkpoint_history: List[Dict] = []

    def register_gym_map(self, map_id: int) -> None:
        """Register a map ID as a gym (triggers GYM_LEADER checkpoints)."""
        self._gym_maps.add(map_id)

    def register_crystal_gyms(self) -> None:
        """Register all Pokemon Crystal gym map IDs."""
        for map_id in CRYSTAL_GYM_MAPS:
            self._gym_maps.add(map_id)

    def should_checkpoint(
        self, prev_state: GameState, curr_state: GameState,
        current_step: int = 0,
    ) -> List[CheckpointReason]:
        """Check if the state transition warrants a checkpoint.

        Returns a list of reasons (empty = no checkpoint needed).
        Multiple reasons can fire simultaneously (e.g., trainer battle + gym leader).
        """
        # Apply cooldown — suppress if too close to last checkpoint
        if self._last_checkpoint_step >= 0:
            if (current_step - self._last_checkpoint_step) < self.cooldown:
                return []

        reasons: List[CheckpointReason] = []

        # Trainer battle started (not wild — wild battles are low-risk)
        if (not prev_state.battle.in_battle and
                curr_state.battle.in_battle and
                curr_state.battle.is_trainer):
            reasons.append(CheckpointReason.TRAINER_BATTLE)

            # Check if this is a gym map
            if curr_state.position.map_id in self._gym_maps:
                reasons.append(CheckpointReason.GYM_LEADER)

        # Low HP on party lead
        lead = curr_state.party.lead()
        if lead and lead.hp_max > 0:
            hp_pct = lead.hp / lead.hp_max
            prev_lead = prev_state.party.lead()
            prev_hp_pct = (prev_lead.hp / prev_lead.hp_max
                           if prev_lead and prev_lead.hp_max > 0 else 1.0)
            # Only trigger when crossing the threshold (not every step while low)
            if hp_pct < self.low_hp_threshold and prev_hp_pct >= self.low_hp_threshold:
                reasons.append(CheckpointReason.LOW_HP)

        # Map transition
        if prev_state.position.map_id != curr_state.position.map_id:
            reasons.append(CheckpointReason.MAP_TRANSITION)

        # Badge earned
        if curr_state.badges.count() > prev_state.badges.count():
            reasons.append(CheckpointReason.BADGE_EARNED)

        return reasons

    def save_checkpoint(
        self,
        step: int,
        reasons: List[CheckpointReason],
    ) -> str:
        """Save an emulator state checkpoint.

        Returns the path to the saved state file.
        """
        os.makedirs(self.state_dir, exist_ok=True)

        reason_str = "_".join(r.value for r in reasons)
        name = f"checkpoint_step_{step}_{reason_str}"
        path = os.path.join(self.state_dir, f"{name}.state")
        self.emulator.save_state(name)

        # Track history
        entry = {
            "step": step,
            "reasons": [r.value for r in reasons],
            "path": path,
        }
        self.checkpoint_history.append(entry)
        self._last_checkpoint_step = step

        # Prune old checkpoints
        self._prune()

        return path

    def latest_checkpoint(self) -> Optional[Dict]:
        """Get the most recent checkpoint entry, or None."""
        if self.checkpoint_history:
            return self.checkpoint_history[-1]
        return None

    def _prune(self) -> None:
        """Remove oldest checkpoints if over the limit."""
        while len(self.checkpoint_history) > self.max_checkpoints:
            self.checkpoint_history.pop(0)
