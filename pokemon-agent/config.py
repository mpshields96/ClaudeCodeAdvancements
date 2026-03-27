"""Pokemon agent configuration.

Central configuration for the Pokemon bot. Supports Red, Crystal, and FireRed.
All tunable parameters live here. No external dependencies.
"""

# ── Model configuration ──────────────────────────────────────────────────────

MODEL_NAME = "claude-opus-4-6"
MAX_TOKENS = 4096
TEMPERATURE = 0.0  # Deterministic for reproducibility

# ── Agent loop parameters ────────────────────────────────────────────────────

MAX_HISTORY = 60           # Messages before summarization kicks in
SCREENSHOT_UPSCALE = 2     # Upscale Game Boy screenshots for better vision
SAVE_INTERVAL = 50         # Save emulator state every N steps
TICKS_PER_BUTTON = 4       # Frames to hold a button press
TICKS_AFTER_BUTTON = 8     # Frames to wait after releasing

# ── Stuck detection ──────────────────────────────────────────────────────────

STUCK_THRESHOLD = 10       # Same location for N steps = stuck
STUCK_FORCE_NEW = True     # Force model to try something new when stuck
STUCK_STRATEGY_MEMORY = 5  # Track last N failed strategies for anonymized replay
STUCK_ENCOURAGE_LEVELS = 3 # Number of escalating encouragement levels

# ── Navigation ───────────────────────────────────────────────────────────────

USE_NAVIGATOR = True       # Enable A* pathfinding
AVOID_ENCOUNTERS = False   # Penalize grass tiles in pathfinding

# ── Offline mode ─────────────────────────────────────────────────────────────

# When True, skip API calls and run in test/debug mode.
# The emulator, RAM reading, and navigation all work offline.
# Only the LLM decision-making requires an API connection.
OFFLINE_MODE = False

# ── File paths (relative to pokemon-agent/) ──────────────────────────────────

DEFAULT_ROM = "pokemon_red.gb"
STATE_DIR = "states"       # Directory for save states
SCREENSHOT_DIR = "screenshots"  # Directory for screenshots
LOG_DIR = "logs"           # Directory for agent logs
