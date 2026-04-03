"""Pokemon Crystal autonomous agent — core loop.

Connects emulator (RAM reading + screenshots) to Opus 4.6 (reasoning + tool use).
This is the heart of the system. Minimal harness, maximum model reasoning.

Design (from PHASE3_PLAN.md):
1. Read game state from RAM (ground truth)
2. Capture screenshot (upscaled 2x)
3. Send state + screenshot to Opus 4.6
4. Opus responds with reasoning + tool call
5. Execute tool call
6. Check for summarization threshold
7. Save state periodically
Repeat.

The agent works offline except for the LLM API call. Emulator, RAM reading,
navigation, and state management all run locally.
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from action_cache import ActionCache
from checkpoint import CheckpointManager
from text_reader import TextReader
from agent_memory import AgentMemory, MapMarkers, Objectives
from config import (
    MAX_HISTORY, MAX_TOKENS, MODEL_NAME, SAVE_INTERVAL,
    SCREENSHOT_UPSCALE, STUCK_THRESHOLD, STUCK_FORCE_NEW,
    STUCK_STRATEGY_MEMORY,
    TEMPERATURE, STATE_DIR, SCREENSHOT_DIR, LOG_DIR,
)
from movement_validator import MovementValidator
from diversity_checker import DiversityChecker
from screen_detector import ScreenDetector, ScreenState
from emulator_control import EmulatorControl
from game_state import GameState, MapPosition, MenuState
from memory_reader import MemoryReader
from prompts import (
    SYSTEM_PROMPT, build_user_message, build_summary_request,
    encode_screenshot_b64,
)
from tools import TOOLS, validate_tool_call

logger = logging.getLogger(__name__)


# ── LLM client protocol (for testability) ───────────────────────────────────

class LLMClient(Protocol):
    """Protocol for LLM API calls. Real impl uses Anthropic SDK."""

    def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list,
        tools: list,
        temperature: float,
    ) -> "LLMResponse": ...


@dataclass
class ToolUse:
    """A tool call from the LLM response."""
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    """Parsed LLM response."""
    text: str = ""
    tool_uses: List[ToolUse] = field(default_factory=list)
    stop_reason: str = "end_turn"
    input_tokens: int = 0
    output_tokens: int = 0


# ── Anthropic SDK wrapper ───────────────────────────────────────────────────

class AnthropicClient:
    """Real LLM client using Anthropic SDK."""

    def __init__(self):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic not installed. Run: pip install anthropic")
        self._client = Anthropic()

    def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list,
        tools: list,
        temperature: float,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
            temperature=temperature,
        )

        text_parts = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(ToolUse(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        return LLMResponse(
            text="\n".join(text_parts),
            tool_uses=tool_uses,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


# ── Mock LLM client (for testing) ──────────────────────────────────────────

class MockLLMClient:
    """Mock LLM for testing without API calls."""

    def __init__(self, responses: Optional[List[LLMResponse]] = None):
        self._responses = list(responses or [])
        self._call_count = 0
        self.last_messages: list = []
        self.last_system: str = ""
        self.last_tools: list = []

    def add_response(self, response: LLMResponse) -> None:
        self._responses.append(response)

    def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list,
        tools: list,
        temperature: float,
    ) -> LLMResponse:
        self.last_messages = messages
        self.last_system = system
        self.last_tools = tools

        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            # Default: press A
            resp = LLMResponse(
                text="I'll press A to continue.",
                tool_uses=[ToolUse(id="test_1", name="press_buttons",
                                   input={"buttons": ["a"]})],
            )

        self._call_count += 1
        return resp

    @property
    def call_count(self) -> int:
        return self._call_count


# ── Agent step result ───────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Result of one agent step."""
    step_number: int
    state: GameState
    llm_text: str = ""
    tool_calls: List[ToolUse] = field(default_factory=list)
    tool_results: List[dict] = field(default_factory=list)
    was_stuck: bool = False
    was_summarized: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


# ── Crystal Agent ───────────────────────────────────────────────────────────

class CrystalAgent:
    """Autonomous Pokemon Crystal agent.

    Connects mGBA emulator to Opus 4.6 via a minimal tool interface.
    RAM reading provides ground truth. Screenshots provide visual context.
    The model reasons and acts through tool calls.
    """

    def __init__(
        self,
        emulator: EmulatorControl,
        reader: MemoryReader,
        llm: Optional[LLMClient] = None,
        navigator=None,
        max_history: int = MAX_HISTORY,
        save_interval: int = SAVE_INTERVAL,
        stuck_threshold: int = STUCK_THRESHOLD,
        model_name: str = MODEL_NAME,
    ):
        self.emulator = emulator
        self.reader = reader
        self.llm = llm
        self.navigator = navigator
        self.max_history = max_history
        self.save_interval = save_interval
        self.stuck_threshold = stuck_threshold
        self.model_name = model_name

        # Conversation state
        self.messages: List[dict] = []
        self.step_count: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0

        # Stuck detection
        self._last_positions: List[MapPosition] = []
        self._failed_strategies: List[List[str]] = []  # Track button sequences when stuck

        # Auto-advance: skip LLM for mechanical actions (mewtoo pattern)
        self._consecutive_auto_a: int = 0  # Consecutive auto A-presses
        self.auto_advance_count: int = 0   # Total auto-advances this session
        self.DIALOG_ESCAPE_THRESHOLD: int = 7  # After N auto-A, try B to escape

        # Action cache: skip LLM for previously successful actions
        self.action_cache = ActionCache()
        self._last_cache_key: Optional[str] = None  # For outcome tracking

        # Movement validation: track blocked directions (mewtoo pattern)
        self.movement_validator = MovementValidator()
        self._last_map_id: Optional[int] = None  # For map change detection

        # Screen transition detection: skip LLM on blank/transition screens
        self.screen_detector = ScreenDetector()

        # Action diversity: flag repetitive button presses (mewtoo pattern)
        self.diversity_checker = DiversityChecker()

        # Checkpoint manager: auto-save before risky actions
        self.checkpoint_mgr = CheckpointManager(emulator, state_dir=STATE_DIR)
        self.checkpoint_mgr.register_crystal_gyms()

        # Text reader: extract on-screen text from RAM
        self.text_reader = TextReader(emulator)

        # Persistent memory/tool state
        self.agent_memory = AgentMemory()
        self.map_markers = MapMarkers()
        self.objectives = Objectives()

        # Previous state for checkpoint comparisons
        self._prev_state: Optional[GameState] = None

        # Callbacks
        self._on_step: Optional[Callable[[StepResult], None]] = None

    def on_step(self, callback: Callable[[StepResult], None]) -> None:
        """Register a callback that fires after each step."""
        self._on_step = callback

    def _available_tools(self) -> list[dict]:
        """Return the tool surface supported by this agent instance."""
        if self.navigator is None:
            return [tool for tool in TOOLS if tool["name"] != "navigate_to"]
        try:
            current_map_id = self.reader.read_position().map_id
        except Exception:
            current_map_id = None
        if current_map_id is None or not self.navigator.has_map(current_map_id):
            return [tool for tool in TOOLS if tool["name"] != "navigate_to"]
        return TOOLS

    def _screen_detection_addresses(self) -> dict:
        """Return RAM addresses for screen transition detection.

        Override in subclasses for different games (e.g., RedAgent).
        """
        from memory_reader import JOY_DISABLED, BATTLE_MODE, WINDOW_STACK_SIZE
        return {
            "joy_disabled": JOY_DISABLED,
            "battle_mode": BATTLE_MODE,
            "window_stack": WINDOW_STACK_SIZE,
        }

    def _should_auto_advance(self, state: GameState) -> Optional[str]:
        """Check if we can skip the LLM and auto-press a button.

        Returns the button to press ("a" or "b") or None if LLM is needed.

        Auto-advance conditions (from mewtoo patterns):
        - DIALOG state: press A to advance text (no reasoning needed)
        - POKEMON_CENTER state: press A to advance healing animation
        - After 7+ consecutive auto-A presses in same state: press B to escape loops

        Crystal dialog detection: menu_state.DIALOG is unreliable from RAM flags alone
        (S208: WINDOW_STACK=10 and JOY_DISABLED=146 are normal overworld values).
        Fallback: text_reader.is_text_active() checks the actual text buffer content
        at 0xD073, which is populated only when dialog is actively displayed.
        """
        if state.menu_state == MenuState.DIALOG:
            if self._consecutive_auto_a >= self.DIALOG_ESCAPE_THRESHOLD:
                return "b"  # Escape dialog loop
            return "a"  # Advance text
        if state.menu_state == MenuState.POKEMON_CENTER:
            return "a"  # Advance healing animation

        # Crystal fallback: text reader checks actual text buffer content.
        # More reliable than WINDOW_STACK/JOY_DISABLED flags (S208 fix).
        if self.text_reader.is_text_active():
            if self._consecutive_auto_a >= self.DIALOG_ESCAPE_THRESHOLD:
                return "b"
            return "a"

        # Not an auto-advance situation — reset counter
        self._consecutive_auto_a = 0
        return None

    def _auto_advance_step(self, state: GameState, button: str) -> StepResult:
        """Execute a step without calling the LLM — just press the button.

        This saves tokens for mechanical actions like advancing dialog text
        or healing animations. The step still counts, still updates position
        tracking, and still triggers callbacks/saves.
        """
        # Press the button
        self.emulator.press(button)

        # Track auto-advance stats
        if button == "a":
            self._consecutive_auto_a += 1
        elif button == "b":
            self._consecutive_auto_a = 0  # Reset after B escape attempt
        self.auto_advance_count += 1

        # Update position tracking (for stuck detection continuity)
        self._last_positions.append(state.position)
        max_track = self.stuck_threshold * 2
        if len(self._last_positions) > max_track:
            self._last_positions = self._last_positions[-max_track:]

        # Periodic save still runs
        if self.step_count % self.save_interval == 0:
            self._save_state()

        result = StepResult(
            step_number=self.step_count,
            state=state,
            llm_text=f"[auto-advance: {button}]",
            tool_calls=[ToolUse(id="auto", name="press_buttons",
                                input={"buttons": [button]})],
            tool_results=[{"pressed": [button], "count": 1, "auto": True}],
            was_stuck=False,
            was_summarized=False,
            input_tokens=0,
            output_tokens=0,
        )

        if self._on_step:
            self._on_step(result)

        logger.info("Step %d: auto-%s (dialog/healing)", self.step_count, button)
        return result

    def _state_cache_key(self, state: GameState) -> str:
        """Build a cache key from the current game state."""
        return self.action_cache.make_key(
            menu_state=state.menu_state.value,
            map_id=state.position.map_id,
            x=state.position.x,
            y=state.position.y,
            in_battle=state.battle.in_battle,
            battle_type=state.battle.battle_type(),
        )

    def _cached_action_step(self, state: GameState, buttons: List[str], cache_key: str) -> StepResult:
        """Execute a cached action without calling the LLM.

        Records the outcome (state change) so the cache can expire bad entries.
        """
        # Record pre-action state for outcome tracking
        pre_position = state.position

        # Execute the cached buttons
        for button in buttons:
            self.emulator.press(button)

        # Check if action had effect (position changed)
        post_state = self.reader.read_game_state()
        state_changed = (pre_position != post_state.position or
                         state.battle.in_battle != post_state.battle.in_battle or
                         state.menu_state != post_state.menu_state)
        self.action_cache.record_outcome(cache_key, state_changed)

        # Update position tracking
        self._last_positions.append(state.position)
        max_track = self.stuck_threshold * 2
        if len(self._last_positions) > max_track:
            self._last_positions = self._last_positions[-max_track:]

        # Periodic save
        if self.step_count % self.save_interval == 0:
            self._save_state()

        result = StepResult(
            step_number=self.step_count,
            state=state,
            llm_text=f"[cached: {','.join(buttons)}]",
            tool_calls=[ToolUse(id="cache", name="press_buttons",
                                input={"buttons": buttons})],
            tool_results=[{"pressed": buttons, "count": len(buttons), "cached": True}],
            was_stuck=False,
            was_summarized=False,
            input_tokens=0,
            output_tokens=0,
        )

        if self._on_step:
            self._on_step(result)

        logger.info("Step %d: cached [%s] (hit_rate=%.1f%%)",
                     self.step_count, ",".join(buttons),
                     self.action_cache.hit_rate() * 100)
        return result

    def try_battle_ai(self, state: GameState) -> Optional[StepResult]:
        """If in battle, use deterministic battle AI instead of LLM.

        Saves tokens for routine wild encounters. Returns a StepResult
        if battle AI handled the step, or None to fall through to LLM.
        """
        if not state.battle.in_battle or state.battle.enemy is None:
            return None

        try:
            from battle_ai import assess_threat, choose_action, action_to_buttons
        except ImportError:
            return None  # battle_ai not available

        enemy = state.battle.enemy
        is_wild = state.battle.is_wild

        action = choose_action(state.party, enemy, is_wild=is_wild,
                               items=state.items)
        buttons = action_to_buttons(action)

        lead = state.party.lead()
        threat = assess_threat(enemy, lead) if lead else {"level": "unknown"}

        logger.info("Battle AI: %s vs %s Lv%d (threat:%s) — %s: %s",
                     lead.species if lead else "???",
                     enemy.species, enemy.level, threat["level"],
                     action["type"], action.get("reason", ""))

        for button in buttons:
            if button in ("up", "down", "left", "right"):
                self.emulator.press(button, hold_frames=4, wait_frames=8)
            else:
                self.emulator.press(button, hold_frames=4, wait_frames=12)

        self.auto_advance_count += 1

        result = StepResult(
            step_number=self.step_count,
            state=state,
            llm_text=f"[battle_ai: {action['type']} — {action.get('reason', '')}]",
            tool_calls=[],
            tool_results=[{"auto": True, "battle_ai": True}],
        )

        if self._on_step:
            self._on_step(result)

        return result

    def step(self) -> StepResult:
        """Execute one agent step: observe -> think -> act.

        Returns a StepResult with all the details.
        """
        self.step_count += 1

        # 1. Read game state from RAM (ground truth)
        state = self.reader.read_game_state()

        # 1.01. Battle AI: use deterministic moves for routine battles
        battle_result = self.try_battle_ai(state)
        if battle_result is not None:
            return battle_result

        # 1.05. Checkpoint check: auto-save before risky actions
        if self._prev_state is not None:
            reasons = self.checkpoint_mgr.should_checkpoint(
                self._prev_state, state, current_step=self.step_count,
            )
            if reasons:
                self.checkpoint_mgr.save_checkpoint(
                    step=self.step_count, reasons=reasons,
                )
                logger.info("Checkpoint saved: %s",
                            [r.value for r in reasons])
        self._prev_state = state

        # 1.1. Map change detection — clear stale movement data
        if self._last_map_id is not None and state.position.map_id != self._last_map_id:
            self.movement_validator.on_map_change(self._last_map_id, state.position.map_id)
        self._last_map_id = state.position.map_id

        # 1.5. Auto-advance check: skip LLM for mechanical actions
        auto_button = self._should_auto_advance(state)
        if auto_button is not None:
            return self._auto_advance_step(state, auto_button)

        # 1.7. Screen transition detection: skip LLM on blank/transition screens
        screen_addrs = self._screen_detection_addresses()
        joy_disabled = self.emulator.read_byte(screen_addrs["joy_disabled"])
        battle_mode = self.emulator.read_byte(screen_addrs["battle_mode"])
        window_stack = self.emulator.read_byte(screen_addrs["window_stack"])
        screen_state = self.screen_detector.classify(joy_disabled, battle_mode, window_stack)
        self.screen_detector.update(screen_state)
        if screen_state != ScreenState.ACTIVE:
            action = self.screen_detector.recommended_action(screen_state)
            if action == "wait":
                self.emulator.tick(12)  # Wait ~200ms for transition to finish
            elif action == "start":
                self.emulator.press("start")  # Try to unstick long transitions
            return StepResult(
                step_number=self.step_count, state=state,
                llm_text=f"[transition: {action}]",
                tool_calls=[], tool_results=[],
            )

        # 2. Check if stuck
        stuck_turns = self._check_stuck(state.position)
        is_stuck = stuck_turns >= self.stuck_threshold

        # 2.5. Action cache lookup (skip when stuck — need fresh LLM reasoning)
        if not is_stuck:
            cache_key = self._state_cache_key(state)
            cached_buttons = self.action_cache.get(cache_key)
            if cached_buttons is not None:
                return self._cached_action_step(state, cached_buttons, cache_key)

        # 3. Capture screenshot (if emulator supports it)
        screenshot_b64 = self._capture_screenshot()
        blocked_info = self.movement_validator.format_for_prompt(state.position)
        diversity_info = self.diversity_checker.format_for_prompt()
        if blocked_info and diversity_info:
            blocked_info = blocked_info + " " + diversity_info
        elif diversity_info:
            blocked_info = diversity_info
        # 3.5. Read on-screen text from RAM (more reliable than OCR)
        text_context = self.text_reader.format_for_prompt()
        user_msg = build_user_message(
            state=state,
            screenshot_b64=screenshot_b64,
            stuck_turns=stuck_turns if is_stuck else 0,
            step_number=self.step_count,
            failed_strategies=self._failed_strategies if is_stuck else None,
            stuck_threshold=self.stuck_threshold,
            blocked_directions=blocked_info,
            text_context=text_context,
        )
        self.messages.append(user_msg)

        # Reset auto-advance counter (LLM is being called = not in auto-advance)
        self._consecutive_auto_a = 0

        # 5. Call LLM (or fallback to random input in offline mode)
        if self.llm is None:
            # Offline mode: press A to advance (title screen, dialogs, etc.)
            self.emulator.press("a")
            self.messages.pop()  # Remove the user message we just added
            return StepResult(
                step_number=self.step_count, state=state,
                llm_text="[offline: press a]",
                tool_calls=[ToolUse(id="offline", name="press_buttons", input={"buttons": ["a"]})],
                tool_results=[{"pressed": ["a"], "count": 1, "offline": True}],
            )

        response = self.llm.create_message(
            model=self.model_name,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=self.messages,
            tools=self._available_tools(),
            temperature=TEMPERATURE,
        )

        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens

        # 6. Add assistant response to history
        assistant_msg = self._response_to_message(response)
        self.messages.append(assistant_msg)

        # 7. Execute tool calls + track strategies for stuck detection
        tool_results = []
        for tool_use in response.tool_uses:
            result = self._execute_tool(tool_use)
            tool_results.append(result)

            # Track button sequences for stuck detection + diversity
            if tool_use.name == "press_buttons":
                buttons = tool_use.input.get("buttons", [])
                # Record each button for diversity tracking
                for b in buttons:
                    self.diversity_checker.record(b)
                # Track failed strategies when stuck
                if is_stuck and buttons:
                    self._failed_strategies.append(buttons)
                    if len(self._failed_strategies) > STUCK_STRATEGY_MEMORY:
                        self._failed_strategies = self._failed_strategies[-STUCK_STRATEGY_MEMORY:]

            # Add tool result to message history
            self.messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                }],
            })

        # 7.5. Cache successful LLM actions for future reuse
        if not is_stuck:
            for tool_use in response.tool_uses:
                if tool_use.name == "press_buttons":
                    buttons = tool_use.input.get("buttons", [])
                    if buttons:
                        cache_key = self._state_cache_key(state)
                        self.action_cache.put(cache_key, buttons)

        # 8. Check summarization threshold
        was_summarized = False
        if len(self.messages) >= self.max_history:
            self._summarize()
            was_summarized = True

        # 9. Periodic save
        if self.step_count % self.save_interval == 0:
            self._save_state()

        # Build result
        result = StepResult(
            step_number=self.step_count,
            state=state,
            llm_text=response.text,
            tool_calls=response.tool_uses,
            tool_results=tool_results,
            was_stuck=(stuck_turns >= self.stuck_threshold),
            was_summarized=was_summarized,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        if self._on_step:
            self._on_step(result)

        return result

    def run(self, num_steps: int = 1000) -> List[StepResult]:
        """Run the agent for N steps.

        Returns list of step results.
        """
        results = []
        for _ in range(num_steps):
            result = self.step()
            results.append(result)
            logger.info(
                "Step %d: %s | Tokens: %d in, %d out",
                result.step_number, result.llm_text[:80],
                result.input_tokens, result.output_tokens,
            )
        return results

    # ── Internal methods ──

    def _check_stuck(self, position: MapPosition) -> int:
        """Track position history and return how many consecutive steps at same location."""
        self._last_positions.append(position)

        # Only keep last N positions
        max_track = self.stuck_threshold * 2
        if len(self._last_positions) > max_track:
            self._last_positions = self._last_positions[-max_track:]

        # Count consecutive same-position steps from the end
        count = 0
        for pos in reversed(self._last_positions):
            if pos == position:
                count += 1
            else:
                break

        return count

    def _capture_screenshot(self) -> Optional[str]:
        """Capture and encode a screenshot, or None if unavailable."""
        try:
            # Save to an in-memory buffer
            tmp_path = "/tmp/crystal_screenshot.png"
            self.emulator.screenshot("crystal_screenshot")
            # Read it back and encode
            path = self.emulator._state_path("crystal_screenshot", ext=".png")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read()
                return encode_screenshot_b64(data)
        except Exception as e:
            logger.debug("Screenshot failed: %s", e)
        return None

    def _response_to_message(self, response: LLMResponse) -> dict:
        """Convert LLM response to assistant message format."""
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tool_use in response.tool_uses:
            content.append({
                "type": "tool_use",
                "id": tool_use.id,
                "name": tool_use.name,
                "input": tool_use.input,
            })
        return {"role": "assistant", "content": content}

    def _execute_tool(self, tool_use: ToolUse) -> dict:
        """Execute a tool call and return the result.

        Includes post-action verification: reads RAM after execution to
        confirm the action took effect. This catches frozen game states
        and failed navigations (Gemini Crystal lesson: "HALLUCINATION CHECK").
        """
        valid, error = validate_tool_call(tool_use.name, tool_use.input)
        if not valid:
            return {"error": error}

        # Capture pre-action state for verification
        pre_state = self.reader.read_game_state()

        if tool_use.name == "press_buttons":
            result = self._tool_press_buttons(tool_use.input)
        elif tool_use.name == "navigate_to":
            result = self._tool_navigate_to(tool_use.input)
        elif tool_use.name == "wait":
            result = self._tool_wait(tool_use.input)
        elif tool_use.name == "reload_checkpoint":
            result = self._tool_reload_checkpoint(tool_use.input)
        elif tool_use.name == "write_memory":
            result = self._tool_write_memory(tool_use.input)
        elif tool_use.name == "delete_memory":
            result = self._tool_delete_memory(tool_use.input)
        elif tool_use.name == "add_marker":
            result = self._tool_add_marker(tool_use.input, pre_state)
        elif tool_use.name == "delete_marker":
            result = self._tool_delete_marker(tool_use.input, pre_state)
        elif tool_use.name == "update_objectives":
            result = self._tool_update_objectives(tool_use.input)
        else:
            return {"error": f"Unknown tool: {tool_use.name}"}

        # Post-action verification
        verification = self._verify_action(tool_use.name, tool_use.input,
                                            pre_state, result)
        if verification:
            result["verification"] = verification

        return result

    def _tool_press_buttons(self, input_data: dict) -> dict:
        """Execute press_buttons tool."""
        buttons = input_data["buttons"]
        for button in buttons:
            self.emulator.press(button)

        # Extra wait if requested
        wait_frames = input_data.get("wait_frames", 0)
        if wait_frames > 0:
            self.emulator.tick(wait_frames)

        return {"pressed": buttons, "count": len(buttons)}

    def _tool_navigate_to(self, input_data: dict) -> dict:
        """Execute navigate_to tool using A* pathfinding."""
        target_x = input_data["x"]
        target_y = input_data["y"]

        if self.navigator is None:
            return {"error": "Navigator not available"}

        # Get current position
        position = self.reader.read_position()
        target = MapPosition(map_id=position.map_id, x=target_x, y=target_y)

        # Find path
        path = self.navigator.find_path(position, target)
        if path is None:
            return {"error": f"No path found from ({position.x},{position.y}) to ({target_x},{target_y})"}

        if len(path) == 0:
            return {"already_at_target": True, "x": target_x, "y": target_y}

        # Execute path
        for step in path:
            if step.direction in ("up", "down", "left", "right"):
                self.emulator.move(step.direction)

        return {
            "navigated_to": {"x": target_x, "y": target_y},
            "steps": len(path),
        }

    def _tool_wait(self, input_data: dict) -> dict:
        """Execute wait tool."""
        frames = input_data.get("frames", 60)
        self.emulator.tick(frames)
        return {"waited_frames": frames}

    def _tool_reload_checkpoint(self, input_data: dict) -> dict:
        """Reload the most recent checkpoint."""
        reason = input_data.get("reason", "unknown")
        latest = self.checkpoint_mgr.latest_checkpoint()
        if latest is None:
            return {"error": "No checkpoint available to reload"}

        try:
            # Extract the state name from the path
            name = os.path.basename(latest["path"]).replace(".state", "")
            self.emulator.load_state(name)
            logger.info("Reloaded checkpoint step %d: %s", latest["step"], reason)
            return {
                "reloaded": True,
                "checkpoint_step": latest["step"],
                "reason": reason,
            }
        except Exception as e:
            return {"error": f"Failed to reload: {e}"}

    def _tool_write_memory(self, input_data: dict) -> dict:
        """Persist a strategic memory note."""
        key = input_data["key"]
        value = input_data["value"]
        message = self.agent_memory.write(key, value)
        return {"memory_written": key, "message": message}

    def _tool_delete_memory(self, input_data: dict) -> dict:
        """Delete a strategic memory note."""
        key = input_data["key"]
        message = self.agent_memory.delete(key)
        deleted = "not found" not in message.lower()
        return {"memory_deleted": deleted, "key": key, "message": message}

    def _tool_add_marker(self, input_data: dict, state: GameState) -> dict:
        """Add a marker on the current map."""
        x = input_data["x"]
        y = input_data["y"]
        label = input_data["label"]
        marker_type = input_data.get("marker_type", "poi")
        map_id = state.position.map_id
        message = self.map_markers.add(map_id, x, y, label, marker_type)
        return {
            "marker_added": True,
            "map_id": map_id,
            "x": x,
            "y": y,
            "label": label,
            "marker_type": marker_type,
            "message": message,
        }

    def _tool_delete_marker(self, input_data: dict, state: GameState) -> dict:
        """Delete a marker on the current map."""
        x = input_data["x"]
        y = input_data["y"]
        map_id = state.position.map_id
        message = self.map_markers.delete(map_id, x, y)
        deleted = "no marker" not in message.lower()
        return {
            "marker_deleted": deleted,
            "map_id": map_id,
            "x": x,
            "y": y,
            "message": message,
        }

    def _tool_update_objectives(self, input_data: dict) -> dict:
        """Replace the current objective list."""
        objectives = input_data.get("objectives", [])
        if not isinstance(objectives, list):
            return {"error": "objectives must be a list"}

        normalized = []
        for item in objectives:
            if not isinstance(item, dict):
                return {"error": "each objective must be an object"}
            description = item.get("description", "")
            if not isinstance(description, str) or not description.strip():
                return {"error": "each objective needs a non-empty description"}
            rationale = item.get("rationale", "")
            status = item.get("status", "active")
            if status not in {"active", "completed", "abandoned"}:
                return {"error": f"invalid objective status: {status}"}
            normalized.append({
                "description": description,
                "rationale": rationale if isinstance(rationale, str) else "",
                "status": status,
            })

        message = self.objectives.update(normalized)
        return {
            "objectives_updated": len(normalized),
            "active_objectives": self.objectives.count_active(),
            "message": message,
        }

    def _verify_action(
        self,
        tool_name: str,
        input_data: dict,
        pre_state: GameState,
        result: dict,
    ) -> Optional[dict]:
        """Post-action verification: check that the action took effect.

        Returns a verification dict if there's something notable, or None.
        Inspired by Gemini's self-discovered rule: "HALLUCINATION CHECK system."
        """
        if "error" in result:
            return None  # Already failed, no verification needed

        try:
            post_state = self.reader.read_game_state()
        except Exception:
            return None  # Can't verify if RAM read fails

        if tool_name == "press_buttons":
            # Check if game state changed at all after button presses
            buttons = input_data.get("buttons", [])
            direction_buttons = {"up", "down", "left", "right"}
            has_direction = any(b in direction_buttons for b in buttons)

            if has_direction:
                # Track movement success/failure per direction
                for b in buttons:
                    if b in direction_buttons:
                        self.movement_validator.verify_movement(
                            pre_state.position, post_state.position, b
                        )

                # If we pressed direction buttons, position should change
                # (unless blocked by a wall, which is normal)
                moved = (pre_state.position != post_state.position)
                if not moved and len(buttons) >= 3:
                    blocked_info = self.movement_validator.format_for_prompt(
                        pre_state.position
                    )
                    warning = {"warning": "pressed_directions_but_didnt_move",
                               "position": f"({post_state.position.x},{post_state.position.y})"}
                    if blocked_info:
                        warning["blocked"] = blocked_info
                    return warning

            # Check if battle state changed (entered or exited battle)
            if pre_state.battle.in_battle != post_state.battle.in_battle:
                if post_state.battle.in_battle:
                    enemy = post_state.battle.enemy
                    enemy_info = f"{enemy.species} Lv{enemy.level}" if enemy else "unknown"
                    return {"event": "battle_started",
                            "type": post_state.battle.battle_type(),
                            "enemy": enemy_info}
                else:
                    return {"event": "battle_ended"}

        elif tool_name == "navigate_to":
            target_x = input_data["x"]
            target_y = input_data["y"]
            actual_x = post_state.position.x
            actual_y = post_state.position.y

            # Check if we actually reached the target (± 1 tile tolerance)
            dx = abs(actual_x - target_x)
            dy = abs(actual_y - target_y)
            if dx > 1 or dy > 1:
                return {"warning": "navigation_missed_target",
                        "target": f"({target_x},{target_y})",
                        "actual": f"({actual_x},{actual_y})",
                        "distance": dx + dy}
            elif dx == 0 and dy == 0:
                return {"verified": "at_target"}

        return None

    def _summarize(self) -> None:
        """Summarize conversation history to free up context."""
        if self.llm is None:
            return

        # Ask the model to summarize
        summary_messages = list(self.messages)
        summary_messages.append(build_summary_request())

        response = self.llm.create_message(
            model=self.model_name,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=summary_messages,
            tools=[],  # No tools during summarization
            temperature=TEMPERATURE,
        )

        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens

        # Replace history with just the summary
        summary_text = response.text or "Summary unavailable."
        self.messages = [{
            "role": "user",
            "content": [{
                "type": "text",
                "text": f"[CONVERSATION SUMMARY — replacing {len(self.messages)} messages]\n\n{summary_text}",
            }],
        }, {
            "role": "assistant",
            "content": [{"type": "text", "text": "Understood. I'll continue from this summary."}],
        }]

        logger.info("Summarized %d messages into summary", len(summary_messages))

    def _save_state(self) -> None:
        """Save emulator state to disk."""
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            name = f"crystal_step_{self.step_count}"
            path = self.emulator.save_state(name)
            logger.info("Saved state: %s", path)
        except Exception as e:
            logger.warning("Failed to save state: %s", e)

    @property
    def token_usage(self) -> dict:
        """Get total token usage stats."""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "steps": self.step_count,
            "messages": len(self.messages),
        }
