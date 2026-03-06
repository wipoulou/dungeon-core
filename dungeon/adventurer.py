"""Adventurer entity - the 'livestock' that generates mana."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

from dungeon.grid import Grid, Tile
from dungeon.loot import Vault
from dungeon.pathfinding import _can_stand, find_path

GRAVITY = -20.0
SPIKE_DAMAGE = 30
WAYPOINT_THRESHOLD = 0.3
STUCK_TIME = 2.0
LOOT_TIME = 0.8
LOOT_MANA = 5
VISION_RANGE = 5
CHEST_DETOUR_RANGE = 10  # max BFS distance to consider a chest worth a detour


@dataclass
class Adventurer:
    x: float
    y: float
    hp: int = 100
    max_hp: int = 100
    speed: float = 4.0
    jump_force: float = 10.0
    vy: float = 0.0
    grounded: bool = False
    alive: bool = True
    reached_exit: bool = False
    looting: bool = False
    loot_timer: float = 0.0
    loot_collected: int = 0
    damage_log: list[int] = field(default_factory=list)
    _hazard_cooldown: float = 0.0
    _last_hazard_tile: tuple[int, int] | None = None
    _damage_flash: float = 0.0
    _path: list[tuple[int, int]] = field(default_factory=list)
    _path_index: int = 0
    _path_dirty: bool = True
    _stuck_timer: float = 0.0
    _last_grid_pos: tuple[int, int] = (0, 0)
    _current_goal: tuple[int, int] | None = None
    _looted_chests: set[tuple[int, int]] = field(default_factory=set)
    _seen: set[tuple[int, int]] = field(default_factory=set)
    _known_exit: tuple[int, int] | None = None
    _known_chests: set[tuple[int, int]] = field(default_factory=set)
    # _known_hazards reserved for future use (leveled-up adventurers with trap detection)

    @property
    def grid_x(self) -> int:
        return int(self.x)

    @property
    def grid_y(self) -> int:
        return int(self.y)

    def take_damage(self, amount: int) -> int:
        """Apply damage and return mana generated (0.5x damage per GDD)."""
        if not self.alive:
            return 0
        self.hp = max(0, self.hp - amount)
        self.damage_log.append(amount)
        self._damage_flash = 0.15
        if self.hp <= 0:
            self.alive = False
        return int(amount * 0.5)

    @property
    def total_damage_taken(self) -> int:
        return sum(self.damage_log)


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
        if tile == Tile.EXIT:
            adv._known_exit = (x, y)
        elif tile == Tile.CHEST:
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

        # Expand BFS through walkable tiles
        grounded = grid.is_solid(x, y - 1)
        for dx in (-1, 1):
            nx = x + dx
            if _can_stand(grid, nx, y) and (nx, y) not in visited:
                if grounded or grid.is_solid(nx, y - 1):
                    visited.add((nx, y))
                    queue.append((nx, y))
        # Up
        if grounded and _can_stand(grid, x, y + 1) and (x, y + 1) not in visited:
            visited.add((x, y + 1))
            queue.append((x, y + 1))
        # Down
        if not grounded and _can_stand(grid, x, y - 1) and (x, y - 1) not in visited:
            visited.add((x, y - 1))
            queue.append((x, y - 1))
        # Drop off edges
        if grounded:
            for dx in (-1, 1):
                nx = x + dx
                if _can_stand(grid, nx, y) and not grid.is_solid(nx, y - 1):
                    land_y = y - 1
                    while land_y > 0 and not grid.is_solid(nx, land_y - 1):
                        land_y -= 1
                    if _can_stand(grid, nx, land_y) and (nx, land_y) not in visited:
                        visited.add((nx, land_y))
                        queue.append((nx, land_y))

    return None  # Explored everything reachable


def _pick_wander_target(adv: Adventurer, grid: Grid) -> tuple[int, int] | None:
    """Pick a random reachable tile to wander to when there's nothing left to explore."""
    pos = (adv.grid_x, adv.grid_y)
    queue: deque[tuple[int, int]] = deque()
    queue.append(pos)
    visited: set[tuple[int, int]] = {pos}

    while queue:
        x, y = queue.popleft()
        grounded = grid.is_solid(x, y - 1)
        for dx in (-1, 1):
            nx = x + dx
            if _can_stand(grid, nx, y) and (nx, y) not in visited:
                if grounded or grid.is_solid(nx, y - 1):
                    visited.add((nx, y))
                    queue.append((nx, y))
        if grounded and _can_stand(grid, x, y + 1) and (x, y + 1) not in visited:
            visited.add((x, y + 1))
            queue.append((x, y + 1))
        if not grounded and _can_stand(grid, x, y - 1) and (x, y - 1) not in visited:
            visited.add((x, y - 1))
            queue.append((x, y - 1))
        if grounded:
            for dx in (-1, 1):
                nx = x + dx
                if _can_stand(grid, nx, y) and not grid.is_solid(nx, y - 1):
                    land_y = y - 1
                    while land_y > 0 and not grid.is_solid(nx, land_y - 1):
                        land_y -= 1
                    if _can_stand(grid, nx, land_y) and (nx, land_y) not in visited:
                        visited.add((nx, land_y))
                        queue.append((nx, land_y))

    visited.discard(pos)
    if not visited:
        return None
    # Pick a random tile, biased toward farther ones
    candidates = list(visited)
    return random.choice(candidates)


def _pick_goal(
    adv: Adventurer, grid: Grid, vault: Vault
) -> tuple[int, int] | None:
    """Pick next goal. The adventurer always wants to be moving somewhere.

    Priority:
    1. Known exit — always the base goal once discovered
    2. Nearby chest — quick detour if spotted and not too far
    3. Explore — push toward the unknown to find the exit
    """
    pos = (adv.grid_x, adv.grid_y)

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
        return best_chest

    # Head to exit if known
    if adv._known_exit is not None:
        return adv._known_exit

    # No exit found yet — explore toward the unknown
    explore = _find_explore_target(adv, grid)
    if explore is not None:
        return explore

    # Fully explored reachable area — wander to a random distant tile
    return _pick_wander_target(adv, grid)


def _ensure_path(adv: Adventurer, grid: Grid, vault: Vault) -> None:
    """Compute or refresh the path to the current goal."""
    if not adv._path_dirty:
        return

    _update_vision(adv, grid)

    goal = _pick_goal(adv, grid, vault)
    if goal is None:
        adv._path = []
        adv._path_dirty = False
        return

    adv._current_goal = goal
    adv._path = find_path(grid, (adv.grid_x, adv.grid_y), goal)
    adv._path_index = 1 if len(adv._path) > 1 else 0
    adv._path_dirty = False


def update_adventurer(adv: Adventurer, grid: Grid, vault: Vault, dt: float) -> int:
    """Advance adventurer by dt seconds. Returns mana generated this tick."""
    if not adv.alive or adv.reached_exit:
        return 0

    mana = 0
    adv._damage_flash = max(0.0, adv._damage_flash - dt)

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
        else:
            reached = abs(dx) < WAYPOINT_THRESHOLD and abs(dy) < WAYPOINT_THRESHOLD
        if reached:
            adv._path_index += 1
            if adv._path_index < len(adv._path):
                tx, ty = adv._path[adv._path_index]
                target_x, target_y = float(tx), float(ty)

    # --- Gravity ---
    adv.vy += GRAVITY * dt
    new_y = adv.y + adv.vy * dt

    if adv.vy > 0:
        head_y = int(new_y + 1.7)
        if grid.is_solid(adv.grid_x, head_y):
            adv.vy = 0.0
            new_y = adv.y

    feet_tile_y = int(new_y)
    if grid.is_solid(adv.grid_x, feet_tile_y):
        adv.y = feet_tile_y + 1.0
        adv.vy = 0.0
        adv.grounded = True
    else:
        adv.y = new_y
        adv.grounded = False

    # --- Horizontal movement toward target ---
    if target_x is not None:
        dx = target_x - adv.x
        need_drop = target_y is not None and target_y < adv.y - 0.3

        if abs(dx) > 0.05 or (need_drop and adv.grounded):
            move_dir = 1.0 if dx >= 0 else -1.0
            new_x = adv.x + move_dir * adv.speed * dt

            ahead_x = int(new_x + 0.3 * move_dir)
            if grid.is_solid(ahead_x, adv.grid_y):
                if adv.grounded:
                    adv.vy = adv.jump_force
            else:
                adv.x = new_x

        if target_y is not None and target_y > adv.y + 0.5 and adv.grounded:
            adv.vy = adv.jump_force

    # --- Chest interaction ---
    current_tile = (adv.grid_x, adv.grid_y)
    if grid.get(*current_tile) == Tile.CHEST and current_tile not in adv._looted_chests:
        if vault.loot_chest(*current_tile):
            adv.looting = True
            adv.loot_timer = 0.0
            adv.loot_collected += 1
            adv._looted_chests.add(current_tile)
            mana += LOOT_MANA
        else:
            # Chest is empty — mark as looted so we don't keep targeting it
            adv._looted_chests.add(current_tile)
            adv._path_dirty = True

    # --- Hazard check ---
    adv._hazard_cooldown = max(0.0, adv._hazard_cooldown - dt)
    if grid.is_hazard(*current_tile):
        new_hazard = current_tile != adv._last_hazard_tile
        if adv._hazard_cooldown <= 0 or new_hazard:
            mana += adv.take_damage(SPIKE_DAMAGE)
            adv._hazard_cooldown = 1.0
            adv._last_hazard_tile = current_tile

    # --- Stuck detection ---
    if current_tile == adv._last_grid_pos:
        adv._stuck_timer += dt
        if adv._stuck_timer >= STUCK_TIME:
            adv._path_dirty = True
            adv._stuck_timer = 0.0
    else:
        adv._last_grid_pos = current_tile
        adv._stuck_timer = 0.0

    # --- Exit check ---
    if grid.get(adv.grid_x, adv.grid_y) == Tile.EXIT:
        adv.reached_exit = True

    return mana
