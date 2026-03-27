"""Pokemon Red battle AI — deterministic move selection.

Chooses the best move based on type effectiveness, power, and PP.
Runs entirely offline — no LLM calls needed for routine battles.
The agent can fall back to this for wild encounters and use the
LLM only for complex trainer battles or strategic decisions.

Gen 1 type chart sourced from:
- https://bulbapedia.bulbagarden.net/wiki/Type/Type_chart#Generation_I

Usage:
    from battle_ai import choose_action, action_to_buttons
    action = choose_action(party, enemy_pokemon, is_wild=True)
    buttons = action_to_buttons(action)

Stdlib only. No external dependencies.
"""
from __future__ import annotations

from typing import List, Optional

from game_state import Move, Party, Pokemon

# ── Gen 1 Type Effectiveness ────────────────────────────────────────────
# Keys: (attack_type, defend_type) -> multiplier
# Only non-1.0 entries stored. Missing = neutral (1.0).

_SUPER_EFFECTIVE = {
    ("Water", "Fire"), ("Water", "Ground"), ("Water", "Rock"),
    ("Fire", "Grass"), ("Fire", "Ice"), ("Fire", "Bug"),
    ("Grass", "Water"), ("Grass", "Ground"), ("Grass", "Rock"),
    ("Electric", "Water"), ("Electric", "Flying"),
    ("Ice", "Grass"), ("Ice", "Ground"), ("Ice", "Flying"), ("Ice", "Dragon"),
    ("Fighting", "Normal"), ("Fighting", "Ice"), ("Fighting", "Rock"),
    ("Poison", "Grass"), ("Poison", "Bug"),
    ("Ground", "Fire"), ("Ground", "Electric"), ("Ground", "Poison"), ("Ground", "Rock"),
    ("Flying", "Grass"), ("Flying", "Fighting"), ("Flying", "Bug"),
    ("Psychic", "Fighting"), ("Psychic", "Poison"),
    ("Bug", "Grass"), ("Bug", "Psychic"), ("Bug", "Poison"),
    ("Rock", "Fire"), ("Rock", "Ice"), ("Rock", "Flying"), ("Rock", "Bug"),
    ("Ghost", "Ghost"),
    ("Dragon", "Dragon"),
}

_NOT_VERY_EFFECTIVE = {
    ("Water", "Water"), ("Water", "Grass"), ("Water", "Dragon"),
    ("Fire", "Fire"), ("Fire", "Water"), ("Fire", "Rock"), ("Fire", "Dragon"),
    ("Grass", "Fire"), ("Grass", "Grass"), ("Grass", "Poison"),
    ("Grass", "Flying"), ("Grass", "Bug"), ("Grass", "Dragon"),
    ("Electric", "Electric"), ("Electric", "Grass"), ("Electric", "Dragon"),
    ("Ice", "Fire"), ("Ice", "Water"), ("Ice", "Ice"),
    ("Fighting", "Poison"), ("Fighting", "Flying"), ("Fighting", "Psychic"),
    ("Fighting", "Bug"),
    ("Poison", "Poison"), ("Poison", "Ground"), ("Poison", "Rock"),
    ("Poison", "Ghost"),
    ("Ground", "Grass"), ("Ground", "Bug"),
    ("Flying", "Electric"), ("Flying", "Rock"),
    ("Psychic", "Psychic"),
    ("Bug", "Fire"), ("Bug", "Fighting"), ("Bug", "Flying"), ("Bug", "Ghost"),
    ("Rock", "Fighting"), ("Rock", "Ground"),
    ("Ghost", "Normal"),
    ("Normal", "Rock"),
}

_IMMUNE = {
    ("Normal", "Ghost"), ("Ghost", "Normal"),
    ("Electric", "Ground"), ("Ground", "Flying"),
    ("Psychic", "Dark"),  # Gen 2+ but included for safety
    ("Fighting", "Ghost"),
}


def type_multiplier(attack_type: str, defend_type: str) -> float:
    """Get type effectiveness multiplier for a single type matchup.

    Returns 2.0 (super effective), 0.5 (not very effective),
    0.0 (immune), or 1.0 (neutral).
    """
    pair = (attack_type, defend_type)
    if pair in _IMMUNE:
        return 0.0
    if pair in _SUPER_EFFECTIVE:
        return 2.0
    if pair in _NOT_VERY_EFFECTIVE:
        return 0.5
    return 1.0


def _full_type_multiplier(attack_type: str, defend_types: List[str]) -> float:
    """Calculate combined type multiplier against a dual-type defender."""
    mult = 1.0
    for dt in defend_types:
        mult *= type_multiplier(attack_type, dt)
    return mult


def score_move(move: Move, enemy: Pokemon) -> float:
    """Score a move's expected effectiveness against an enemy.

    Score = power * type_effectiveness * accuracy_factor
    Zero PP or zero power = 0 score.
    """
    if move.pp <= 0:
        return 0.0
    if move.power <= 0:
        return 0.0

    effectiveness = _full_type_multiplier(move.move_type, enemy.pokemon_type)
    if effectiveness == 0.0:
        return 0.0

    accuracy_factor = move.accuracy / 100.0 if move.accuracy > 0 else 1.0
    return move.power * effectiveness * accuracy_factor


def assess_threat(enemy: Pokemon, defender: Pokemon) -> dict:
    """Assess how threatening an enemy is to our Pokemon.

    Scores each enemy move against the defender's types.
    Returns a dict with threat level and best enemy move info.

    Threat levels:
        "low"    — best enemy move effectiveness <= 1.0
        "medium" — best enemy move is super effective (2.0x)
        "high"   — best enemy move is 4x effective (dual weakness)
    """
    if not enemy.moves:
        return {"level": "unknown", "best_move": None, "best_score": 0.0}

    best_score = 0.0
    best_move = None
    for move in enemy.moves:
        if move.power <= 0:
            continue
        s = score_move(move, defender)
        if s > best_score:
            best_score = s
            best_move = move

    if best_move is None:
        return {"level": "low", "best_move": None, "best_score": 0.0}

    eff = _full_type_multiplier(best_move.move_type, defender.pokemon_type)
    if eff >= 4.0:
        level = "high"
    elif eff >= 2.0:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "best_move": best_move.name,
        "best_score": best_score,
        "effectiveness": eff,
    }


def choose_action(party: Party, enemy: Pokemon, is_wild: bool = True) -> dict:
    """Choose the best battle action given party and enemy state.

    Returns a dict:
        {"type": "fight", "move_index": int, "reason": str}
        {"type": "run", "reason": str}

    Logic:
    1. Score each of the lead Pokemon's moves
    2. Pick the highest-scoring move
    3. If no usable damaging moves and wild: run
    4. If no usable damaging moves and trainer: use move index 0 (struggle)
    """
    lead = party.lead()
    if lead is None or lead.is_fainted():
        return {"type": "run", "reason": "no usable pokemon"}

    # Threat-based flee: run from dangerous wild Pokemon when HP is low
    if is_wild and enemy.moves:
        threat = assess_threat(enemy, lead)
        if threat["level"] == "high" and lead.hp_pct() < 0.5:
            return {"type": "run",
                    "reason": f"high threat ({threat['best_move']}) at {lead.hp_pct():.0%} HP"}
        if threat["level"] == "medium" and lead.hp_pct() < 0.25:
            return {"type": "run",
                    "reason": f"medium threat ({threat['best_move']}) at {lead.hp_pct():.0%} HP"}

    # Score all moves
    scored = []
    for i, move in enumerate(lead.moves):
        s = score_move(move, enemy)
        scored.append((s, i, move))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Pick best damaging move
    if scored and scored[0][0] > 0:
        best_score, best_idx, best_move = scored[0]
        eff = _full_type_multiplier(best_move.move_type, enemy.pokemon_type)
        eff_str = ""
        if eff >= 2.0:
            eff_str = " (super effective!)"
        elif eff <= 0.5:
            eff_str = " (not very effective)"
        reason = f"{best_move.name} (power {best_move.power}, score {best_score:.0f}){eff_str}"
        return {"type": "fight", "move_index": best_idx, "reason": reason}

    # No damaging moves available
    if is_wild:
        return {"type": "run", "reason": "no effective moves, fleeing wild battle"}

    # Trainer battle — must fight, use first move (will become Struggle if all 0 PP)
    return {
        "type": "fight",
        "move_index": 0,
        "reason": "no effective moves, forced to struggle",
    }


def action_to_buttons(action: dict) -> List[str]:
    """Convert a battle action to Game Boy button presses.

    Pokemon Red battle menu:
        FIGHT  ITEM
        PKMN   RUN

    Fight submenu (moves):
        Move1  Move2
        Move3  Move4

    Returns list of buttons to press.
    """
    if action["type"] == "run":
        # Select RUN: down then right from FIGHT, then A
        return ["down", "right", "a"]

    if action["type"] == "fight":
        idx = action["move_index"]
        # Select FIGHT first (top-left, just press A)
        buttons = ["a"]
        # Navigate to the move in the 2x2 grid
        # 0=top-left, 1=top-right, 2=bottom-left, 3=bottom-right
        if idx == 1:
            buttons.append("right")
        elif idx == 2:
            buttons.append("down")
        elif idx == 3:
            buttons.extend(["down", "right"])
        # Confirm move selection
        buttons.append("a")
        return buttons

    return ["a"]  # Fallback: press A
