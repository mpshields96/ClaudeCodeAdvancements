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

from config import STUCK_STRATEGY_MEMORY, STUCK_ENCOURAGE_LEVELS
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


# ── Encouragement levels (anti-blackpilling, S201 Agent 3) ──────────────────

ENCOURAGEMENT_LEVELS = [
    # Level 1: mild (threshold to 2x threshold)
    "Try a different approach — you've got this. Exploration is part of the game.",
    # Level 2: moderate (2x to 3x threshold)
    "This is a tricky section, but persistence pays off. Think about what's different "
    "about this area. Is there a door, NPC, or item you haven't interacted with?",
    # Level 3: strong (3x+ threshold)
    "This is one of the hardest parts of the game — even experienced players get stuck here. "
    "Try something you haven't tried at all: check your bag for usable items, talk to every "
    "NPC, or backtrack to the last Pokemon Center and approach from a different direction.",
]


def get_encouragement(stuck_turns: int, threshold: int = 10) -> str:
    """Return escalating encouragement based on how long stuck.

    Level 1: threshold to 2x threshold
    Level 2: 2x to 3x threshold
    Level 3: 3x+ threshold (capped here)
    """
    if threshold <= 0:
        threshold = 10
    ratio = stuck_turns / threshold
    if ratio >= 3:
        level = 2  # 0-indexed
    elif ratio >= 2:
        level = 1
    else:
        level = 0
    return ENCOURAGEMENT_LEVELS[min(level, len(ENCOURAGEMENT_LEVELS) - 1)]


def format_stuck_context(
    failed_strategies: list[list[str]],
    stuck_turns: int,
) -> str:
    """Format failed strategies as anonymized 'another AI' attempts.

    This leverages the self-anchoring bias (S201 Agent 8): models are less
    likely to repeat a strategy if told 'another AI' tried it and failed,
    vs being shown their own previous attempt.
    """
    if not failed_strategies:
        return ""

    # Only show last N strategies
    recent = failed_strategies[-STUCK_STRATEGY_MEMORY:]

    lines = [f"\nYou've been stuck for {stuck_turns} turns. Here's what hasn't worked:"]
    for i, buttons in enumerate(recent, 1):
        btn_str = ", ".join(buttons[:10])  # Cap display length
        if len(buttons) > 10:
            btn_str += f" ... ({len(buttons)} total)"
        lines.append(f"- A previous AI tried: [{btn_str}] — it did NOT work.")

    lines.append("\nWhat would YOU try instead? Think of something none of these approaches cover.")
    return "\n".join(lines)


def build_stuck_message(
    stuck_turns: int,
    failed_strategies: list[list[str]] | None = None,
    threshold: int = 10,
) -> str:
    """Build the complete stuck injection: base prompt + context + encouragement.

    This replaces the simple STUCK_PROMPT.format() for enhanced stuck detection.
    """
    parts = [STUCK_PROMPT.format(turns=stuck_turns)]

    # Add anonymized failed strategy context
    if failed_strategies:
        parts.append(format_stuck_context(failed_strategies, stuck_turns))

    # Add escalating encouragement
    parts.append("\n" + get_encouragement(stuck_turns, threshold))

    return "\n".join(parts)


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
    failed_strategies: list[list[str]] | None = None,
    stuck_threshold: int = 10,
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

    # Add stuck warning if applicable (enhanced with self-anchoring counter)
    if stuck_turns > 0:
        state_text += "\n\n" + build_stuck_message(
            stuck_turns=stuck_turns,
            failed_strategies=failed_strategies or [],
            threshold=stuck_threshold,
        )

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
