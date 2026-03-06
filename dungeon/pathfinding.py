"""BFS pathfinding for adventurers navigating the grid."""

from __future__ import annotations

from collections import deque

from dungeon.grid import Grid

# Adventurer is 1.8 blocks tall, needs 2 tiles of vertical clearance
ADVENTURER_HEIGHT = 2


def _can_stand(grid: Grid, x: int, y: int) -> bool:
    """Check if an adventurer can stand at (x, y): not solid, with headroom."""
    if grid.is_solid(x, y):
        return False
    for h in range(1, ADVENTURER_HEIGHT):
        if grid.is_solid(x, y + h):
            return False
    return True


def find_path(
    grid: Grid,
    start: tuple[int, int],
    goal: tuple[int, int],
    avoid: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int]]:
    """BFS over walkable tiles. Returns list of (x, y) grid positions from start to goal.

    A tile is walkable if it's not solid and has enough headroom.
    Tiles in `avoid` are skipped (unless they are the goal itself).
    """
    sx, sy = start
    gx, gy = goal

    if not _can_stand(grid, sx, sy) or not _can_stand(grid, gx, gy):
        return []

    queue: deque[tuple[int, int]] = deque()
    queue.append((sx, sy))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {(sx, sy): None}

    while queue:
        cx, cy = queue.popleft()

        if (cx, cy) == (gx, gy):
            path = []
            node: tuple[int, int] | None = (gx, gy)
            while node is not None:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path

        grounded = grid.is_solid(cx, cy - 1)

        for nx, ny in _neighbors(cx, cy, grounded, grid):
            if (nx, ny) in came_from:
                continue
            if avoid and (nx, ny) in avoid and (nx, ny) != (gx, gy):
                continue
            came_from[(nx, ny)] = (cx, cy)
            queue.append((nx, ny))

    return []


def _neighbors(
    x: int, y: int, grounded: bool, grid: Grid
) -> list[tuple[int, int]]:
    """Generate valid neighboring tiles for BFS."""
    result = []

    # Walk left/right
    for dx in (-1, 1):
        nx = x + dx
        if _can_stand(grid, nx, y):
            if grounded or grid.is_solid(nx, y - 1):
                result.append((nx, y))

    # Fall down (if not grounded)
    if not grounded and _can_stand(grid, x, y - 1):
        result.append((x, y - 1))

    # Jump up (only if grounded and headroom above)
    if grounded and _can_stand(grid, x, y + 1):
        result.append((x, y + 1))

    # Drop off edges: step into air and fall
    for dx in (-1, 1):
        nx = x + dx
        if grounded and _can_stand(grid, nx, y) and not grid.is_solid(nx, y - 1):
            # Find landing spot
            land_y = y - 1
            while land_y > 0 and not grid.is_solid(nx, land_y - 1):
                land_y -= 1
            if land_y != y and _can_stand(grid, nx, land_y):
                result.append((nx, land_y))

    return result
