"""Entity - shared base for all creatures (adventurers, mobs)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Faction(Enum):
    ADVENTURER = "adventurer"
    DUNGEON = "dungeon"


class CombatState(Enum):
    IDLE = "idle"
    ENGAGED = "engaged"  # standing and fighting


GRAVITY = -20.0


@dataclass
class Entity:
    """Base class for all creatures in the dungeon."""
    x: float
    y: float

    # Core stats
    hp: int = 100
    max_hp: int = 100
    attack: int = 10
    defense: int = 0
    speed: float = 4.0
    attack_speed: float = 1.0  # attacks per second (cooldown = 1/attack_speed)
    attack_range: float = 1.5  # manhattan distance to hit target
    jump_force: float = 10.0

    # Resources
    stamina: float = 100.0
    max_stamina: float = 100.0
    mana: float = 0.0
    max_mana: float = 0.0

    # Physics
    vy: float = 0.0
    grounded: bool = False
    alive: bool = True
    faction: Faction = Faction.ADVENTURER

    # Combat
    combat_state: CombatState = CombatState.IDLE
    _combat_target: Entity | None = field(default=None, repr=False)
    _attack_cooldown: float = 0.0
    _damage_flash: float = 0.0

    @property
    def grid_x(self) -> int:
        return int(self.x)

    @property
    def grid_y(self) -> int:
        return int(self.y)

    @property
    def in_combat(self) -> bool:
        return self.combat_state == CombatState.ENGAGED and self._combat_target is not None

    def take_damage(self, amount: int) -> int:
        """Apply damage after defense. Returns actual damage dealt."""
        if not self.alive:
            return 0
        actual = max(1, amount - self.defense)
        self.hp = max(0, self.hp - actual)
        self._damage_flash = 0.15
        if self.hp <= 0:
            self.alive = False
            self.disengage()
        return actual

    def engage(self, target: Entity) -> None:
        """Enter combat with a target."""
        self.combat_state = CombatState.ENGAGED
        self._combat_target = target

    def disengage(self) -> None:
        """Leave combat."""
        self.combat_state = CombatState.IDLE
        self._combat_target = None

    def try_attack(self, dt: float) -> int:
        """Tick attack cooldown. Returns damage dealt if attack fires, else 0."""
        self._attack_cooldown = max(0.0, self._attack_cooldown - dt)
        if self._attack_cooldown > 0:
            return 0
        if not self.in_combat or not self._combat_target.alive:
            self.disengage()
            return 0
        self._attack_cooldown = 1.0 / self.attack_speed
        return self.attack
