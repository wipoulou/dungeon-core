"""Adventurer entity - the 'livestock' that generates mana."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from dungeon.entity import Entity, Faction, GRAVITY
from dungeon.grid import Grid, Tile
from dungeon.log import log
from dungeon.loot import Vault
from dungeon.pathfinding import _can_stand, _neighbors, _on_ladder, find_path

SPIKE_DAMAGE = 30
WAYPOINT_THRESHOLD = 0.3
STUCK_TIME = 2.0
LOOT_TIME = 0.8
LOOT_MANA = 5
VISION_RANGE = 5
CHEST_DETOUR_RANGE = 10  # max BFS distance to consider a chest worth a detour
GREED_START = 1.0
GREED_PER_CHEST = 0.35   # greed lost per chest looted
GREED_PER_DAMAGE = 0.10  # greed lost per damage event
FLEE_HP_THRESHOLD = 0.5   # below this HP fraction, adventurer wants out
SPIKE_FALL_MULTIPLIER = 1.5  # extra damage when landing on spike from air
HAZARD_HOP_FORCE = 7.0  # hop to clear spikes — sized to fit under low ceilings
MANA_PER_DAMAGE = 0.5  # mana generated per point of damage taken


class AdventurerClass(Enum):
    WARRIOR = "warrior"
    ROGUE = "rogue"
    MAGE = "mage"
    HEALER = "healer"


# Base stat overrides per class: (hp, attack, defense, speed, attack_speed, stamina, mana)
CLASS_STATS: dict[AdventurerClass, dict[str, int | float]] = {
    AdventurerClass.WARRIOR: {
        "hp": 120, "max_hp": 120, "attack": 15, "defense": 3,
        "speed": 3.5, "attack_speed": 0.8, "attack_range": 1.5,
        "stamina": 120.0, "max_stamina": 120.0,
    },
    AdventurerClass.ROGUE: {
        "hp": 80, "max_hp": 80, "attack": 12, "defense": 1,
        "speed": 5.0, "attack_speed": 1.5, "attack_range": 1.5,
        "stamina": 100.0, "max_stamina": 100.0,
    },
    AdventurerClass.MAGE: {
        "hp": 70, "max_hp": 70, "attack": 8, "defense": 0,
        "speed": 3.5, "attack_speed": 0.7, "attack_range": 3.5,
        "stamina": 60.0, "max_stamina": 60.0,
        "mana": 100.0, "max_mana": 100.0,
    },
    AdventurerClass.HEALER: {
        "hp": 90, "max_hp": 90, "attack": 8, "defense": 2,
        "speed": 3.5, "attack_speed": 0.8, "attack_range": 3.0,
        "stamina": 80.0, "max_stamina": 80.0,
        "mana": 80.0, "max_mana": 80.0,
    },
}


@dataclass
class Adventurer(Entity):
    adv_class: AdventurerClass = AdventurerClass.WARRIOR
    reached_exit: bool = False
    looting: bool = False
    loot_timer: float = 0.0
    loot_collected: int = 0
    damage_log: list[int] = field(default_factory=list)
    _hazard_cooldown: float = 0.0
    _last_hazard_tile: tuple[int, int] | None = None
    _path: list[tuple[int, int]] = field(default_factory=list)
    _path_index: int = 0
    _path_dirty: bool = True
    _stuck_timer: float = 0.0
    _last_grid_pos: tuple[int, int] = (0, 0)
    _current_goal: tuple[int, int] | None = None
    _looted_chests: set[tuple[int, int]] = field(default_factory=set)
    _seen: set[tuple[int, int]] = field(default_factory=set)
    _entrance: tuple[int, int] | None = None
    _returning: bool = False
    _known_chests: set[tuple[int, int]] = field(default_factory=set)
    _greed: float = GREED_START
    _known_hazards: set[tuple[int, int]] = field(default_factory=set)
    _hazard_hopping: bool = False  # True during a controlled spike hop
    _party_speed: float | None = None  # if set, overrides speed for party cohesion
    _approach_target: Entity | None = field(default=None, repr=False)  # mob to walk toward

    def __post_init__(self) -> None:
        self.faction = Faction.ADVENTURER

    def take_damage(self, amount: int) -> int:
        """Apply damage, drain greed, return mana generated."""
        if not self.alive:
            return 0
        actual = max(1, amount - self.defense)
        self.hp = max(0, self.hp - actual)
        self.damage_log.append(actual)
        self._damage_flash = 0.15
        self._greed = max(0.0, self._greed - GREED_PER_DAMAGE)
        log(f"DAMAGE {actual} hp={self.hp}/{self.max_hp} greed={self._greed:.2f} pos=({self.grid_x},{self.grid_y})")
        if self.hp <= 0:
            self.alive = False
            self.disengage()
        return int(actual * MANA_PER_DAMAGE)

    @property
    def total_damage_taken(self) -> int:
        return sum(self.damage_log)


def make_adventurer(
    x: float, y: float, adv_class: AdventurerClass = AdventurerClass.WARRIOR,
    entrance: tuple[int, int] | None = None,
) -> Adventurer:
    """Create an adventurer with class-based stats."""
    stats = CLASS_STATS.get(adv_class, {})
    adv = Adventurer(
        x=x, y=y, adv_class=adv_class, _entrance=entrance,
        **stats,
    )
    return adv


def _update_vision(adv: Adventurer, grid: Grid) -> None:
    """Reveal tiles within vision range using BFS flood fill through open tiles."""
    cx, cy = adv.grid_x, adv.grid_y
    queue: deque[tuple[int, int]] = deque()
    queue.append((cx, cy))
    visited: set[tuple[int, int]] = {(cx, cy)}

    while queue:
        x, y = queue.popleft()
        adv._seen.add((x, y))

        # Check for interesting things
        tile = grid.get(x, y)
        if tile == Tile.CHEST:
            adv._known_chests.add((x, y))
        # Traps are hidden — adventurers can't see them (until leveled up)

        # BFS expand within vision range (manhattan distance)
        if abs(x - cx) + abs(y - cy) >= VISION_RANGE:
            continue

        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in visited:
                continue
            if not grid.in_bounds(nx, ny):
                continue
            visited.add((nx, ny))
            # Can see through all tiles (you can see a wall)
            # but only continue BFS through non-solid tiles for "reachable" vision
            adv._seen.add((nx, ny))
            if not grid.is_solid(nx, ny):
                queue.append((nx, ny))


def _find_explore_target(adv: Adventurer, grid: Grid) -> tuple[int, int] | None:
    """Find the nearest reachable tile adjacent to unexplored space."""
    pos = (adv.grid_x, adv.grid_y)
    queue: deque[tuple[int, int]] = deque()
    queue.append(pos)
    visited: set[tuple[int, int]] = {pos}

    while queue:
        x, y = queue.popleft()

        # Is this tile next to something we haven't seen?
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if grid.in_bounds(nx, ny) and (nx, ny) not in adv._seen:
                # This tile borders the unknown — go here (but not our current tile)
                if (x, y) == pos:
                    continue
                path = find_path(grid, pos, (x, y))
                if path:
                    return (x, y)

        # Expand BFS through walkable tiles using shared movement rules
        grounded = grid.is_solid(x, y - 1) or _on_ladder(grid, x, y)
        for nx, ny in _neighbors(x, y, grounded, grid):
            if (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))

    return None  # Explored everything reachable


def _pick_wander_target(adv: Adventurer, grid: Grid) -> tuple[int, int] | None:
    """Pick a random reachable tile to wander to when there's nothing left to explore."""
    pos = (adv.grid_x, adv.grid_y)
    queue: deque[tuple[int, int]] = deque()
    queue.append(pos)
    visited: set[tuple[int, int]] = {pos}

    while queue:
        x, y = queue.popleft()
        grounded = grid.is_solid(x, y - 1) or _on_ladder(grid, x, y)
        for nx, ny in _neighbors(x, y, grounded, grid):
            if (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))

    visited.discard(pos)
    if not visited:
        return None
    return random.choice(list(visited))


def _pick_goal(
    adv: Adventurer, grid: Grid, vault: Vault
) -> tuple[int, int] | None:
    """Pick next goal. The adventurer always wants to be moving somewhere.

    Priority when exploring (greed > 0):
    1. Nearby chest — quick detour if spotted and not too far
    2. Explore — push toward the unknown
    3. Wander — random reachable tile (keep moving while greedy)

    When returning (greed depleted or nothing left to do):
    - Head back to entrance
    """
    pos = (adv.grid_x, adv.grid_y)

    # Greed depleted or HP too low — head home
    if adv._greed <= 0 or (adv.hp / adv.max_hp) < FLEE_HP_THRESHOLD:
        if not adv._returning:
            log(f"RETURN greed={adv._greed:.2f} hp={adv.hp}/{adv.max_hp} pos={pos}")
        adv._returning = True

    if not adv._returning:
        # Check for nearby chests worth a detour
        best_chest = None
        best_dist = CHEST_DETOUR_RANGE + 1
        stale = []
        for cpos in adv._known_chests:
            if cpos in adv._looted_chests:
                continue
            chest = vault.chests.get(cpos)
            if chest is None or not chest.has_loot:
                stale.append(cpos)
                continue
            path = find_path(grid, pos, cpos)
            if path and len(path) < best_dist:
                best_dist = len(path)
                best_chest = cpos
        for s in stale:
            adv._known_chests.discard(s)

        if best_chest is not None:
            log(f"GOAL chest={best_chest} pos={pos} greed={adv._greed:.2f}")
            return best_chest

        # Explore toward the unknown
        explore = _find_explore_target(adv, grid)
        if explore is not None:
            log(f"GOAL explore={explore} pos={pos} seen={len(adv._seen)}")
            return explore

        # Seen everything reachable but still greedy — wander around
        wander = _pick_wander_target(adv, grid)
        if wander is not None:
            log(f"GOAL wander={wander} pos={pos} seen={len(adv._seen)}")
            return wander

        # Truly nothing left to do — head back
        log(f"RETURN nothing_left pos={pos} seen={len(adv._seen)} greed={adv._greed:.2f}")
        adv._returning = True

    # Return to entrance
    if adv._entrance is not None:
        return adv._entrance

    # No entrance known (shouldn't happen) — wander
    return _pick_wander_target(adv, grid)


def _ensure_path(adv: Adventurer, grid: Grid, vault: Vault) -> None:
    """Compute or refresh the path to the current goal."""
    if not adv._path_dirty:
        return

    _update_vision(adv, grid)

    # If approaching a mob, override goal to mob's position
    if adv._approach_target is not None and adv._approach_target.alive:
        goal = (adv._approach_target.grid_x, adv._approach_target.grid_y)
    else:
        goal = _pick_goal(adv, grid, vault)
    if goal is None:
        adv._path = []
        adv._path_dirty = False
        return

    adv._current_goal = goal
    start = (adv.grid_x, adv.grid_y)
    # Try to route around known hazards; fall back to routing through them
    adv._path = find_path(grid, start, goal, avoid=adv._known_hazards)
    if not adv._path and adv._known_hazards:
        adv._path = find_path(grid, start, goal)
    adv._path_index = 1 if len(adv._path) > 1 else 0
    adv._path_dirty = False


def update_adventurer(adv: Adventurer, grid: Grid, vault: Vault, dt: float) -> int:
    """Advance adventurer by dt seconds. Returns mana generated this tick."""
    if not adv.alive or adv.reached_exit:
        return 0

    mana = 0
    adv._damage_flash = max(0.0, adv._damage_flash - dt)

    # --- Combat: stand and fight ---
    if adv.in_combat:
        target = adv._combat_target
        # Disengage if target dead or too far
        if not target.alive or abs(adv.x - target.x) + abs(adv.y - target.y) > adv.attack_range + 0.5:
            adv.disengage()
            adv._approach_target = None
            adv._path_dirty = True
        else:
            dmg = adv.try_attack(dt)
            if dmg > 0:
                target.take_damage(dmg)
            return mana  # no movement while fighting

    # --- Approaching a mob: engage when in range ---
    if adv._approach_target is not None:
        at = adv._approach_target
        if not at.alive:
            adv._approach_target = None
            adv._path_dirty = True
        else:
            dist = abs(adv.x - at.x) + abs(adv.y - at.y)
            if dist <= adv.attack_range:
                adv.engage(at)
                adv._approach_target = None
                return mana
            # Re-path if mob moved
            mob_tile = (at.grid_x, at.grid_y)
            if adv._current_goal != mob_tile:
                adv._path_dirty = True

    # --- Looting animation ---
    if adv.looting:
        adv.loot_timer += dt
        if adv.loot_timer >= LOOT_TIME:
            adv.looting = False
            adv.loot_timer = 0.0
            adv._path_dirty = True
        return 0

    # --- Vision update (every frame to catch new tiles) ---
    old_seen_count = len(adv._seen)
    _update_vision(adv, grid)
    if len(adv._seen) > old_seen_count:
        # Saw something new — reconsider goals
        adv._path_dirty = True

    # --- Pathfinding ---
    _ensure_path(adv, grid, vault)

    # --- Effective speed (party cohesion may override) ---
    eff_speed = adv._party_speed if adv._party_speed is not None else adv.speed

    # --- Determine movement target ---
    target_x: float | None = None
    target_y: float | None = None

    if adv._path and adv._path_index < len(adv._path):
        tx, ty = adv._path[adv._path_index]
        target_x, target_y = float(tx), float(ty)

        dx = target_x - adv.x
        dy = target_y - adv.y
        # Final waypoint: must actually reach the grid tile
        # Intermediate: skip early within WAYPOINT_THRESHOLD
        is_last = adv._path_index >= len(adv._path) - 1
        if is_last:
            reached = adv.grid_x == tx and abs(dy) < WAYPOINT_THRESHOLD
        elif not adv.grounded:
            # Airborne: advance waypoints on x alone (don't stall mid-air)
            reached = abs(dx) <= WAYPOINT_THRESHOLD
            # Don't skip past vertical-climb waypoints (ladders) while airborne
            if reached and adv._path_index + 1 < len(adv._path):
                next_tx, next_ty = adv._path[adv._path_index + 1]
                if next_tx == tx and next_ty > ty:
                    reached = False
        else:
            reached = abs(dx) <= WAYPOINT_THRESHOLD and abs(dy) <= WAYPOINT_THRESHOLD
        if reached:
            adv._path_index += 1
            if adv._path_index < len(adv._path):
                tx, ty = adv._path[adv._path_index]
                target_x, target_y = float(tx), float(ty)

    # --- Ladder check ---
    on_ladder = grid.get(adv.grid_x, adv.grid_y) == Tile.LADDER
    landed_hard = False  # set by gravity block when landing from a fast fall

    # --- Gravity (suppressed on ladders) ---
    if on_ladder and target_y is not None:
        # Climb toward target y
        dy_climb = target_y - adv.y
        step = eff_speed * dt
        if abs(dy_climb) > step:
            climb_dir = 1.0 if dy_climb > 0 else -1.0
            adv.y += climb_dir * step
        else:
            adv.y = target_y  # snap when close to avoid overshooting
        adv.vy = 0.0
        adv.grounded = True
    else:
        adv.vy += GRAVITY * dt
        new_y = adv.y + adv.vy * dt

        if adv.vy > 0:
            head_y = int(new_y + 1.7)
            if grid.is_solid(adv.grid_x, head_y):
                adv.vy = 0.0
                new_y = adv.y

        feet_tile_y = int(new_y)
        if grid.is_solid(adv.grid_x, feet_tile_y):
            landed_hard = adv.vy < -3.0 and not adv._hazard_hopping
            adv._hazard_hopping = False
            adv.y = feet_tile_y + 1.0
            adv.vy = 0.0
            adv.grounded = True
        else:
            landed_hard = False
            adv.y = new_y
            adv.grounded = False

    # --- Horizontal movement toward target (suppressed while actively climbing) ---
    climbing = on_ladder and target_y is not None and abs(target_y - adv.y) > 0.3
    pre_move_gx = adv.grid_x  # save for hop check (movement can shift grid_x onto spike)
    if target_x is not None and not climbing:
        dx = target_x - adv.x
        need_drop = target_y is not None and target_y < adv.y - 0.3

        if abs(dx) > 0.05 or (need_drop and adv.grounded):
            move_dir = 1.0 if dx >= 0 else -1.0
            new_x = adv.x + move_dir * eff_speed * dt

            ahead_x = int(new_x + 0.3 * move_dir)
            if grid.is_solid(ahead_x, adv.grid_y):
                if adv.grounded:
                    adv.vy = adv.jump_force
            else:
                adv.x = new_x
        elif adv.grounded:
            # Snap to target x to avoid int() truncation leaving us off-grid
            # Don't snap while airborne — keep horizontal momentum
            adv.x = target_x

        # Hop over known hazards — controlled hop, no fall damage
        # Use pre-movement grid_x so we detect the spike BEFORE stepping onto it
        if adv.grounded and adv._known_hazards and target_x is not None:
            move_dir_i = 1 if target_x >= adv.x else -1
            ahead_tile = (pre_move_gx + move_dir_i, adv.grid_y)
            if ahead_tile in adv._known_hazards:
                adv.vy = HAZARD_HOP_FORCE
                adv._hazard_hopping = True

        target_is_ladder = target_x is not None and target_y is not None and grid.get(int(target_x), int(target_y)) == Tile.LADDER
        if target_y is not None and target_y > adv.y + 0.5 and adv.grounded and not on_ladder and not target_is_ladder:
            adv.vy = adv.jump_force

    # --- Sanity: detect if adventurer is inside a solid tile ---
    if grid.is_solid(adv.grid_x, adv.grid_y):
        log(f"BUG solid! pos=({adv.x:.3f},{adv.y:.3f}) grid=({adv.grid_x},{adv.grid_y}) on_ladder={on_ladder} target=({target_x},{target_y}) vy={adv.vy:.2f}")

    # --- Chest interaction ---
    current_tile = (adv.grid_x, adv.grid_y)
    if grid.get(*current_tile) == Tile.CHEST and current_tile not in adv._looted_chests:
        if vault.loot_chest(*current_tile):
            adv.looting = True
            adv.loot_timer = 0.0
            adv.loot_collected += 1
            adv._looted_chests.add(current_tile)
            adv._greed = max(0.0, adv._greed - GREED_PER_CHEST)
            mana += LOOT_MANA
        else:
            # Chest is empty — mark as looted so we don't keep targeting it
            adv._looted_chests.add(current_tile)
            adv._path_dirty = True

    # --- Hazard check ---
    adv._hazard_cooldown = max(0.0, adv._hazard_cooldown - dt)
    if grid.is_hazard(*current_tile):
        # Spikes only trigger when grounded and not jumping away
        if not adv.grounded or adv.vy > 0:
            pass
        else:
            new_hazard = current_tile != adv._last_hazard_tile
            if adv._hazard_cooldown <= 0 or new_hazard:
                damage = SPIKE_DAMAGE
                if landed_hard:
                    # Falling onto a spike hurts more
                    damage = int(damage * SPIKE_FALL_MULTIPLIER)
                mana += adv.take_damage(damage)
                adv._hazard_cooldown = 1.0
                adv._last_hazard_tile = current_tile
                adv._known_hazards.add(current_tile)
                adv._path_dirty = True  # rethink path now that we know about this trap

    # --- Stuck detection ---
    if current_tile == adv._last_grid_pos:
        adv._stuck_timer += dt
        if adv._stuck_timer >= STUCK_TIME:
            adv._path_dirty = True
            adv._stuck_timer = 0.0
    else:
        adv._last_grid_pos = current_tile
        adv._stuck_timer = 0.0

    # --- Exit check (return to entrance) ---
    if adv._returning and grid.get(adv.grid_x, adv.grid_y) == Tile.ENTRANCE:
        adv.reached_exit = True

    return mana
