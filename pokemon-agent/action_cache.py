"""Action cache for skipping LLM calls on known game states.

When the agent encounters a game state it has seen before and previously
chose an action that worked, it can reuse that action without calling
the LLM. This saves tokens for repetitive situations like:
- Walking through the same route
- Grinding the same area
- Navigating familiar menus

Cache keys are derived from the game state (menu state, position, battle
status). Cache entries expire after a configurable number of hits to
prevent staleness.

Inspired by mewtoo's ActionCache pattern.
Stdlib only. No external dependencies.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class CacheEntry:
    """A cached action for a specific game state."""
    buttons: List[str]
    hits: int = 0
    successes: int = 0  # Times this action led to a state change
    failures: int = 0   # Times this action had no effect


class ActionCache:
    """LRU cache mapping game state keys to proven actions.

    Keys are strings derived from game state. Values are button sequences
    that previously worked in that state. Entries are evicted LRU when
    the cache exceeds max_size.
    """

    def __init__(self, max_size: int = 256, max_hits: int = 50):
        """Initialize the cache.

        Args:
            max_size: Maximum number of cached state->action mappings.
            max_hits: After this many hits, expire the entry (forces re-evaluation).
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_size = max_size
        self.max_hits = max_hits
        self.total_hits = 0
        self.total_misses = 0

    def make_key(
        self,
        menu_state: str,
        map_id: int,
        x: int,
        y: int,
        in_battle: bool,
        battle_type: str = "none",
    ) -> str:
        """Create a cache key from game state components.

        The key captures the essential state that determines what action
        to take. Position + menu state + battle status covers most cases.
        """
        return f"{menu_state}:{map_id}:{x},{y}:{battle_type if in_battle else 'no_battle'}"

    def get(self, key: str) -> Optional[List[str]]:
        """Look up a cached action for the given state key.

        Returns the button list if cached, or None on miss.
        Increments hit counter and evicts if expired.
        """
        if key not in self._cache:
            self.total_misses += 1
            return None

        entry = self._cache[key]

        # Expire if too many hits (force re-evaluation)
        if entry.hits >= self.max_hits:
            del self._cache[key]
            self.total_misses += 1
            return None

        # Expire if success rate is poor (< 30% after 5+ uses)
        if entry.hits >= 5 and entry.successes / entry.hits < 0.3:
            del self._cache[key]
            self.total_misses += 1
            return None

        entry.hits += 1
        self.total_hits += 1

        # Move to end (most recently used)
        self._cache.move_to_end(key)

        return entry.buttons

    def put(self, key: str, buttons: List[str]) -> None:
        """Store an action for a state key.

        If the cache is full, evicts the least recently used entry.
        If max_size is 0, caching is disabled (no-op).
        """
        if self.max_size <= 0:
            return
        if key in self._cache:
            # Update existing entry
            self._cache[key].buttons = buttons
            self._cache.move_to_end(key)
        else:
            # Add new entry
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # Evict LRU
            self._cache[key] = CacheEntry(buttons=buttons)

    def record_outcome(self, key: str, success: bool) -> None:
        """Record whether a cached action succeeded (state changed) or failed."""
        if key in self._cache:
            if success:
                self._cache[key].successes += 1
            else:
                self._cache[key].failures += 1

    def size(self) -> int:
        """Number of entries in the cache."""
        return len(self._cache)

    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self.total_hits + self.total_misses
        if total == 0:
            return 0.0
        return self.total_hits / total

    def stats(self) -> dict:
        """Return cache performance stats."""
        return {
            "size": self.size(),
            "max_size": self.max_size,
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "hit_rate": round(self.hit_rate(), 3),
        }

    def clear(self) -> None:
        """Clear all cached entries. Stats are preserved."""
        self._cache.clear()
