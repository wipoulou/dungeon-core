"""The dungeon grid - a 2D tile map."""

from enum import Enum


class Tile(Enum):
    EMPTY = "empty"
    DIRT = "dirt"
    SPAWN = "spawn"
    EXIT = "exit"
    SPIKE = "spike"
    CHEST = "chest"


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
        self.spawn_pos: tuple[int, int] | None = None
        self.exit_pos: tuple[int, int] | None = None

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
        if tile == Tile.SPAWN:
            self.spawn_pos = (x, y)
        elif tile == Tile.EXIT:
            self.exit_pos = (x, y)

    def is_solid(self, x: int, y: int) -> bool:
        return self.get(x, y) in SOLID_TILES

    def is_hazard(self, x: int, y: int) -> bool:
        return self.get(x, y) in HAZARD_TILES


def _fill_rect(g: Grid, x1: int, y1: int, x2: int, y2: int, tile: Tile) -> None:
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            g.set(x, y, tile)


def make_room_slice() -> Grid:
    """Multi-level dungeon: 30x20 ant-farm layout.

    Layout sketch (y=0 is bottom):
        y19: [ceiling]
        y18: SPAWN on left
        y17: ............platform with gap to drop down
        y13: ............second level floor
        y12: .......spike....corridor
        y9:  ............third level floor
        y8:  .......corridor to exit
        y5:  ............bottom floor
        y4:  ...EXIT on right
        y0-4: solid earth
    """
    g = Grid(30, 20)

    # === Solid earth base (y 0-4) ===
    _fill_rect(g, 0, 0, 29, 4, Tile.DIRT)

    # === Bottom corridor floor (y=5), walls on sides ===
    _fill_rect(g, 0, 5, 29, 5, Tile.DIRT)
    # Left wall
    _fill_rect(g, 0, 5, 0, 19, Tile.DIRT)
    # Right wall
    _fill_rect(g, 29, 5, 29, 19, Tile.DIRT)
    # Ceiling
    _fill_rect(g, 0, 19, 29, 19, Tile.DIRT)

    # === Level 1 (top): spawn platform y=13 ===
    _fill_rect(g, 1, 13, 20, 13, Tile.DIRT)
    g.set(1, 14, Tile.SPAWN)
    # Gap at x=18-20 to drop down to level 2

    # === Level 2 (middle): floor at y=9 with gap at right end ===
    _fill_rect(g, 8, 9, 25, 9, Tile.DIRT)  # floor stops at x=25, gap at x=26-28
    # Spike gauntlet on this level
    g.set(15, 10, Tile.SPIKE)
    g.set(18, 10, Tile.SPIKE)
    # Small wall to jump over
    g.set(22, 10, Tile.DIRT)

    # === Level 3 (bottom corridor): floor at y=5 (already placed) ===
    # Spike near the end
    g.set(10, 6, Tile.SPIKE)
    # Exit on the left side of bottom floor
    g.set(3, 6, Tile.EXIT)

    return g
