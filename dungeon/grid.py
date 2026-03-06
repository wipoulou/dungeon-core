"""The dungeon grid - a 2D tile map."""

from enum import Enum


class Tile(Enum):
    EMPTY = "empty"
    DIRT = "dirt"
    ENTRANCE = "entrance"
    SPIKE = "spike"
    CHEST = "chest"
    LADDER = "ladder"


# Tiles that block movement
SOLID_TILES = {Tile.DIRT}
# Tiles that hurt
HAZARD_TILES = {Tile.SPIKE}


class Grid:
    """A width x height grid of tiles. (0,0) is bottom-left."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # Fill with empty by default
        self._tiles: list[list[Tile]] = [
            [Tile.EMPTY for _ in range(width)] for _ in range(height)
        ]
        self.entrance_pos: tuple[int, int] | None = None

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> Tile:
        if not self.in_bounds(x, y):
            return Tile.DIRT  # Out of bounds = solid wall
        return self._tiles[y][x]

    def set(self, x: int, y: int, tile: Tile) -> None:
        if not self.in_bounds(x, y):
            return
        self._tiles[y][x] = tile
        if tile == Tile.ENTRANCE:
            self.entrance_pos = (x, y)

    def is_solid(self, x: int, y: int) -> bool:
        return self.get(x, y) in SOLID_TILES

    def is_hazard(self, x: int, y: int) -> bool:
        return self.get(x, y) in HAZARD_TILES


def _fill_rect(g: Grid, x1: int, y1: int, x2: int, y2: int, tile: Tile) -> None:
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            g.set(x, y, tile)


def make_room_slice() -> Grid:
    """Multi-level dungeon: 30x20 ant-farm layout with traversable staircases.

    Layout sketch (y=0 is bottom):
        y19: [ceiling]
        y14: ENTRANCE on left
        y13: ............top platform
        y9:  ............middle floor (staircase left connects to top)
        y5:  ............bottom floor (staircase left connects to middle)
        y0-4: solid earth

    Left side has staircases (1-block steps) so adventurers can go back up.
    """
    g = Grid(30, 20)

    # === Solid earth base (y 0-4) ===
    _fill_rect(g, 0, 0, 29, 4, Tile.DIRT)

    # === Walls and ceiling ===
    _fill_rect(g, 0, 5, 29, 5, Tile.DIRT)   # bottom floor
    _fill_rect(g, 0, 5, 0, 19, Tile.DIRT)   # left wall
    _fill_rect(g, 29, 5, 29, 19, Tile.DIRT)  # right wall
    _fill_rect(g, 0, 19, 29, 19, Tile.DIRT)  # ceiling

    # === Level 1 (top): entrance platform y=13 ===
    _fill_rect(g, 1, 13, 22, 13, Tile.DIRT)
    g.set(1, 14, Tile.ENTRANCE)
    # Gap at x=21-28 to drop down to level 2

    # === Level 2 (middle): floor at y=9 ===
    _fill_rect(g, 7, 9, 25, 9, Tile.DIRT)
    # Spike gauntlet
    g.set(15, 10, Tile.SPIKE)
    g.set(18, 10, Tile.SPIKE)

    # === Ladder: middle to top on the right side ===
    # Goes from floor level (y=10) up through top platform, one above floor
    for y in range(10, 15):
        g.set(22, y, Tile.LADDER)

    # === Ladder: bottom to middle on the left side ===
    # Goes from floor level (y=6) up through middle platform, one above floor
    for y in range(6, 11):
        g.set(7, y, Tile.LADDER)

    # === Level 3 (bottom): floor at y=5 (already placed) ===
    g.set(15, 6, Tile.SPIKE)

    return g
