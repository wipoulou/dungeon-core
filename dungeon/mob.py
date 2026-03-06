"""Mobs - dungeon creatures that patrol and damage adventurers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dungeon.entity import Entity, Faction, GRAVITY
from dungeon.grid import Grid, Tile

SPIKE_DAMAGE_TO_MOB = 20
AGGRO_RANGE = 4.0  # tiles — distance to spot and chase an adventurer
RESPAWN_TIME = 30.0  # seconds before a dead mob respawns


class MobType(Enum):
    SLIME = "slime"


# Base stats per mob type
MOB_STATS: dict[MobType, dict[str, int | float]] = {
    MobType.SLIME: {
        "hp": 60, "max_hp": 60, "attack": 15, "defense": 0,
        "speed": 2.0, "attack_speed": 1.0, "attack_range": 1.2,
    },
}


@dataclass
class Mob(Entity):
    mob_type: MobType = MobType.SLIME
    direction: float = 1.0  # 1.0 = right, -1.0 = left
    _hazard_cooldown: float = 0.0
    _home_x: float = 0.0  # patrol origin, returns here after combat
    _respawn_timer: float = 0.0  # counts down to respawn when dead

    def __post_init__(self) -> None:
        self.faction = Faction.DUNGEON
        self._home_x = self.x

    def take_damage(self, amount: int) -> int:
        was_alive = self.alive
        actual = super().take_damage(amount)
        if was_alive and not self.alive:
            self._respawn_timer = RESPAWN_TIME
        return actual

    @property
    def respawn_progress(self) -> float:
        """0.0 = just died, 1.0 = about to respawn."""
        if self.alive or self._respawn_timer <= 0:
            return 0.0
        return 1.0 - self._respawn_timer / RESPAWN_TIME


def make_mob(x: float, y: float, mob_type: MobType = MobType.SLIME) -> Mob:
    """Create a mob with type-based stats."""
    stats = MOB_STATS.get(mob_type, {})
    mob = Mob(x=x, y=y, mob_type=mob_type, **stats)
    return mob


def update_mob(mob: Mob, grid: Grid, dt: float) -> int:
    """Advance mob by dt seconds. Returns mana generated from combat."""
    if not mob.alive:
        if mob._respawn_timer > 0:
            mob._respawn_timer -= dt
            if mob._respawn_timer <= 0:
                # Respawn at home position
                stats = MOB_STATS.get(mob.mob_type, {})
                mob.hp = stats.get("max_hp", mob.max_hp)
                mob.alive = True
                mob.x = mob._home_x
                mob._respawn_timer = 0.0
        return 0

    mana = 0
    mob._damage_flash = max(0.0, mob._damage_flash - dt)

    # Combat: stand and fight
    if mob.in_combat:
        target = mob._combat_target
        if not target.alive or abs(mob.x - target.x) + abs(mob.y - target.y) > mob.attack_range + 0.5:
            mob.disengage()
        else:
            dmg = mob.try_attack(dt)
            if dmg > 0:
                mana += target.take_damage(dmg)
            # Face target
            if target.x > mob.x:
                mob.direction = 1.0
            elif target.x < mob.x:
                mob.direction = -1.0
            return mana  # no movement while fighting

    # Gravity
    mob.vy += GRAVITY * dt
    new_y = mob.y + mob.vy * dt
    feet_tile_y = int(new_y)
    if grid.is_solid(mob.grid_x, feet_tile_y):
        mob.y = feet_tile_y + 1.0
        mob.vy = 0.0
        mob.grounded = True
    else:
        mob.y = new_y
        mob.grounded = False

    # Horizontal patrol
    if mob.grounded:
        new_x = mob.x + mob.direction * mob.speed * dt

        # Check wall ahead
        ahead_x = int(new_x + 0.3 * mob.direction)
        if grid.is_solid(ahead_x, mob.grid_y):
            mob.direction *= -1.0
        # Check floor ahead (don't walk off edges)
        elif not grid.is_solid(int(new_x), mob.grid_y - 1):
            mob.direction *= -1.0
        else:
            mob.x = new_x

    # Hazard damage (spikes hurt mobs too)
    mob._hazard_cooldown = max(0.0, mob._hazard_cooldown - dt)
    if grid.is_hazard(mob.grid_x, mob.grid_y) and mob.grounded:
        if mob._hazard_cooldown <= 0:
            mob.take_damage(SPIKE_DAMAGE_TO_MOB)
            mob._hazard_cooldown = 1.0
    return mana
