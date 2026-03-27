"""System prompts and message formatting for the Crystal agent.

Design philosophy (from PHASE3_PLAN.md):
- Minimal prompt — give advice, not strict orders
- Trust RAM state over vision
- Crystal-specific tips sparingly
- No walkthrough content
- Encouragement to prevent blackpilling (S201 agent finding)

Offline note: This module has zero external dependencies.
"""
from __future__ import annotations

import base64
from typing import List, Optional

from game_state import BattleState, GameState, MapPosition, Party


# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are playing Pokemon Crystal autonomously via a Game Boy Color emulator. You receive game state data from RAM (ground truth) and screenshots.

YOUR GOAL: Complete Pokemon Crystal — all 8 Johto badges, all 8 Kanto badges, defeat Red on Mt. Silver.

KEY FACTS:
- RAM state data is GROUND TRUTH. Trust it over what you see in screenshots.
- Screenshots help with visual context (menus, dialog text, map layout) but your vision of Game Boy screens is imperfect.
- The game has two regions: Johto (8 gyms) then Kanto (8 gyms), then Mt. Silver.
- Day/night cycle affects encounters and NPC availability.
- You have two tools: press_buttons (for all input) and navigate_to (A* pathfinding on current map).

STRATEGY ADVICE:
- Before starting a quest or entering a dungeon, check your team's HP and items.
- If your team is below 50% HP, heal at a Pokemon Center before continuing.
- Progress through the story takes priority over training, UNLESS your team is underleveled by 5+ levels for the next gym.
- When stuck: try something completely different. Don't repeat the same failed approach.
- For battles: consider type matchups. Switch Pokemon if the current one is at a disadvantage.
- Save your game periodically (the agent does this automatically).

VISION LIMITATIONS:
- Small Game Boy resolution means text can be hard to read in screenshots.
- Menu selections and cursor positions are easier to track via button counting than visual inspection.
- Map tiles may look similar — use RAM coordinates to know exactly where you are.

Before each action, briefly explain your reasoning (1-2 sentences). This helps with debugging and learning.

You're doing great. Take it one step at a time. If something doesn't work, that's normal — try a different approach."""


# ── Summarization prompt ─────────────────────────────────────────────────────

SUMMARY_PROMPT = """Summarize the conversation so far into a concise game state briefing. Include ALL of the following:

1. CURRENT LOCATION: Where are you? What map? What were you trying to reach?
2. CURRENT OBJECTIVE: What is your immediate goal? What story event or gym is next?
3. POKEMON TEAM: List each Pokemon with species, level, and key moves. Note any that need healing.
4. BADGES: Which badges do you have?
5. ITEMS: Any important items (HMs, key items, healing items count)?
6. RECENT PROGRESS: What did you accomplish in the last ~60 turns?
7. OBSTACLES: What problems did you encounter? What approaches failed?
8. DEAD ENDS: Places you explored that were blocked or unhelpful.
9. NEXT STEPS: What should you try next?

Be specific about locations (use map names and coordinates when possible). This summary replaces the full conversation history, so don't omit anything important."""


# ── Stuck detection prompt injection ─────────────────────────────────────────

STUCK_PROMPT = """IMPORTANT: You have been in the same location for {turns} consecutive turns. You are STUCK.

DO NOT repeat what you've been doing. Try something COMPLETELY different:
- If you've been walking in one direction, try the opposite
- If you've been pressing A, try pressing B or Start
- If you've been in a menu, exit all menus first
- If you're in a building, try leaving
- If you're outside, try entering a nearby building
- If you've been fighting, try running or using a different Pokemon

What you were doing is NOT WORKING. Change your approach NOW."""


# ── Message formatting ───────────────────────────────────────────────────────


def format_game_state(state: GameState) -> str:
    """Format game state as readable text for the LLM.

    This is what the model sees as the RAM ground truth each turn.
    """
    lines = ["=== GAME STATE (from RAM — ground truth) ==="]

    # Position
    pos = state.position
    lines.append(f"Location: Map {pos.map_id} ({pos.map_name or 'unknown'}), "
                 f"X={pos.x}, Y={pos.y}")

    # Badges
    badge_count = state.badges.count()
    badge_names = []
    for name, has in [
        ("Zephyr", state.badges.zephyr), ("Hive", state.badges.hive),
        ("Plain", state.badges.plain), ("Fog", state.badges.fog),
        ("Storm", state.badges.storm), ("Mineral", state.badges.mineral),
        ("Glacier", state.badges.glacier), ("Rising", state.badges.rising),
    ]:
        if has:
            badge_names.append(name)
    badges_str = ", ".join(badge_names) if badge_names else "none"
    lines.append(f"Badges: {badge_count}/8 Johto [{badges_str}]")

    # Money and time
    lines.append(f"Money: ${state.money} | Play time: {state.play_time_minutes // 60}h {state.play_time_minutes % 60}m")

    # Battle state
    if state.battle.in_battle:
        b = state.battle
        btype = "Wild" if b.is_wild else "Trainer"
        enemy = b.enemy
        if enemy:
            lines.append(f"BATTLE ({btype}): vs {enemy.species} Lv{enemy.level} "
                         f"HP:{enemy.hp}/{enemy.hp_max} [{enemy.status}]")
        else:
            lines.append(f"BATTLE ({btype}): enemy data unavailable")
    else:
        lines.append("Not in battle")

    # Party
    lines.append(f"\nPARTY ({state.party.size()} Pokemon, "
                 f"{state.party.alive_count()} alive):")
    for i, mon in enumerate(state.party.pokemon):
        hp_pct = int(mon.hp_pct() * 100)
        moves_str = ", ".join(
            f"{m.name} ({m.pp}pp)" for m in mon.moves
        ) if mon.moves else "no moves"
        status = f" [{mon.status}]" if mon.status != "healthy" else ""
        lines.append(
            f"  {i+1}. {mon.species} Lv{mon.level} "
            f"HP:{mon.hp}/{mon.hp_max} ({hp_pct}%){status} "
            f"| {moves_str}"
        )

    return "\n".join(lines)


def build_user_message(
    state: GameState,
    screenshot_b64: Optional[str] = None,
    stuck_turns: int = 0,
    step_number: int = 0,
) -> dict:
    """Build a user message with game state + optional screenshot.

    Returns a message dict in Claude API format.
    """
    content = []

    # Screenshot first (if available) — vision before text
    if screenshot_b64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": screenshot_b64,
            },
        })

    # Game state text
    state_text = format_game_state(state)

    # Add stuck warning if applicable
    if stuck_turns > 0:
        state_text += "\n\n" + STUCK_PROMPT.format(turns=stuck_turns)

    # Step counter for context
    state_text = f"[Step {step_number}]\n{state_text}"

    content.append({"type": "text", "text": state_text})

    return {"role": "user", "content": content}


def build_summary_request() -> dict:
    """Build the summarization request message."""
    return {
        "role": "user",
        "content": [{"type": "text", "text": SUMMARY_PROMPT}],
    }


def encode_screenshot_b64(image_bytes: bytes) -> str:
    """Encode raw PNG bytes to base64 string."""
    return base64.b64encode(image_bytes).decode("ascii")
