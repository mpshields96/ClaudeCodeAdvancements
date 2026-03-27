"""Pokemon game state dataclasses.

Structured representation of Pokemon Crystal game state, read from
emulator RAM. These dataclasses are the bridge between raw memory
values and the decision engine.

Usage:
    from game_state import Pokemon, Party, GameState, BattleState, MapPosition
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class MenuState(Enum):
    """Current game UI mode detected from RAM flags.

    The agent needs to know what screen it's on to make appropriate decisions.
    Overworld = free movement. Battle handled separately. Menu/dialog/shop
    require specific button sequences to navigate.
    """
    OVERWORLD = "overworld"
    MENU = "menu"             # Start menu or submenu open
    DIALOG = "dialog"         # NPC dialog / text box active
    BATTLE = "battle"         # In battle (also tracked by BattleState)
    SHOP = "shop"             # Mart / buy-sell screen
    POKEMON_CENTER = "pokemon_center"  # Healing animation
    UNKNOWN = "unknown"


# Pokemon Crystal type chart (18 types)
TYPES = [
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock",
    "Bug", "Ghost", "Steel", "Fire", "Water", "Grass",
    "Electric", "Psychic", "Ice", "Dragon", "Dark",
]


@dataclass
class Move:
    """A Pokemon move."""
    name: str
    move_type: str  # from TYPES
    power: int  # 0 for status moves
    accuracy: int  # 0-100
    pp: int
    pp_max: int
    category: str = "physical"  # physical, special, status

    def is_damaging(self) -> bool:
        return self.power > 0

    def pp_remaining_pct(self) -> float:
        if self.pp_max == 0:
            return 0.0
        return self.pp / self.pp_max


@dataclass
class Pokemon:
    """A Pokemon in the party or battle."""
    species: str
    nickname: str
    level: int
    hp: int
    hp_max: int
    attack: int
    defense: int
    speed: int
    sp_attack: int
    sp_defense: int
    pokemon_type: List[str] = field(default_factory=list)  # 1-2 types
    moves: List[Move] = field(default_factory=list)  # up to 4
    status: str = "healthy"  # healthy, poisoned, paralyzed, asleep, burned, frozen
    held_item: str = ""
    xp: int = 0  # Total experience points

    def hp_pct(self) -> float:
        if self.hp_max == 0:
            return 0.0
        return self.hp / self.hp_max

    def is_fainted(self) -> bool:
        return self.hp <= 0

    def is_healthy(self) -> bool:
        return self.hp > 0 and self.status == "healthy"

    def has_usable_moves(self) -> bool:
        return any(m.pp > 0 for m in self.moves)

    def best_move_power(self) -> int:
        damaging = [m for m in self.moves if m.is_damaging() and m.pp > 0]
        if not damaging:
            return 0
        return max(m.power for m in damaging)


@dataclass
class Party:
    """The player's party (up to 6 Pokemon)."""
    pokemon: List[Pokemon] = field(default_factory=list)

    def size(self) -> int:
        return len(self.pokemon)

    def alive_count(self) -> int:
        return sum(1 for p in self.pokemon if not p.is_fainted())

    def lead(self) -> Optional[Pokemon]:
        if self.pokemon:
            return self.pokemon[0]
        return None

    def all_fainted(self) -> bool:
        return all(p.is_fainted() for p in self.pokemon) if self.pokemon else True

    def avg_level(self) -> float:
        if not self.pokemon:
            return 0.0
        return sum(p.level for p in self.pokemon) / len(self.pokemon)

    def strongest(self) -> Optional[Pokemon]:
        alive = [p for p in self.pokemon if not p.is_fainted()]
        if not alive:
            return None
        return max(alive, key=lambda p: p.level)


@dataclass
class MapPosition:
    """Player position on the overworld map."""
    map_id: int  # Composite: (map_group << 8) | map_number
    map_group: int = 0  # Raw map group byte from 0xDCB5
    map_number: int = 0  # Raw map number byte from 0xDCB6
    map_name: str = ""
    x: int = 0
    y: int = 0

    def __eq__(self, other):
        if not isinstance(other, MapPosition):
            return False
        return self.map_id == other.map_id and self.x == other.x and self.y == other.y


@dataclass
class BattleState:
    """State during a Pokemon battle."""
    in_battle: bool = False
    is_wild: bool = False
    is_trainer: bool = False
    enemy: Optional[Pokemon] = None
    turn_number: int = 0

    def battle_type(self) -> str:
        if not self.in_battle:
            return "none"
        if self.is_wild:
            return "wild"
        return "trainer"


@dataclass
class Badges:
    """Gym badges obtained."""
    zephyr: bool = False     # Falkner (Violet City)
    hive: bool = False       # Bugsy (Azalea Town)
    plain: bool = False      # Whitney (Goldenrod)
    fog: bool = False        # Morty (Ecruteak)
    storm: bool = False      # Chuck (Cianwood)
    mineral: bool = False    # Jasmine (Olivine)
    glacier: bool = False    # Pryce (Mahogany)
    rising: bool = False     # Clair (Blackthorn)

    def count(self) -> int:
        return sum([
            self.zephyr, self.hive, self.plain, self.fog,
            self.storm, self.mineral, self.glacier, self.rising,
        ])

    def all_johto(self) -> bool:
        return self.count() == 8


@dataclass
class GameState:
    """Complete game state snapshot."""
    party: Party = field(default_factory=Party)
    position: MapPosition = field(default_factory=lambda: MapPosition(map_id=0))
    battle: BattleState = field(default_factory=BattleState)
    badges: Badges = field(default_factory=Badges)
    money: int = 0
    play_time_minutes: int = 0
    step_count: int = 0
    menu_state: MenuState = MenuState.OVERWORLD

    def is_in_battle(self) -> bool:
        return self.battle.in_battle

    def progress_pct(self) -> float:
        """Rough progress estimate based on badges and party level."""
        badge_progress = self.badges.count() / 8.0 * 60.0  # badges = 60% weight
        level_progress = min(self.party.avg_level() / 50.0, 1.0) * 40.0  # level = 40% weight
        return min(badge_progress + level_progress, 100.0)
