"""The dungeon grid - a 2D tile map."""

from enum import Enum


class Tile(Enum):
    EMPTY = "empty"
    DIRT = "dirt"
    ENTRANCE = "entrance"
    SPIKE = "spike"
    CHEST = "chest"
    LADDER = "ladder"
    BEAR_TRAP = "bear_trap"
    ARROW_TRAP_L = "arrow_trap_l"  # fires left
    ARROW_TRAP_R = "arrow_trap_r"  # fires right


# Tiles that block movement
SOLID_TILES = {Tile.DIRT}
# Tiles that hurt
HAZARD_TILES = {Tile.SPIKE, Tile.BEAR_TRAP}
# Arrow traps (need periodic update)
ARROW_TRAP_TILES = {Tile.ARROW_TRAP_L, Tile.ARROW_TRAP_R}


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
    """Multi-level dungeon: 40x25 ant-farm layout.

    Layout sketch (y=0 is bottom):
        y24: [ceiling]
        y20: ENTRANCE on left
        y19: ............Level 1 - entry hall
        y14: ............Level 2 - spike corridor
        y9:  ............Level 3 - treasure room
        y4:  ............Level 4 - deep vault
        y0-3: solid earth
    """
    g = Grid(40, 25)

    # === Solid earth base ===
    _fill_rect(g, 0, 0, 39, 3, Tile.DIRT)

    # === Outer shell ===
    _fill_rect(g, 0, 4, 39, 4, Tile.DIRT)    # ground floor
    _fill_rect(g, 0, 4, 0, 24, Tile.DIRT)    # left wall
    _fill_rect(g, 39, 4, 39, 24, Tile.DIRT)  # right wall
    _fill_rect(g, 0, 24, 39, 24, Tile.DIRT)  # ceiling

    # === Level 1 (top): entry hall, floor y=19 ===
    _fill_rect(g, 1, 19, 30, 19, Tile.DIRT)
    g.set(1, 20, Tile.ENTRANCE)
    # Chest at end of hall — easy loot to draw them in
    g.set(28, 20, Tile.CHEST)
    # Gap at x=31-38 to drop to level 2

    # === Level 2: spike corridor, floor y=14 ===
    _fill_rect(g, 8, 14, 38, 14, Tile.DIRT)
    # Spikes guarding the path
    g.set(20, 15, Tile.SPIKE)
    g.set(23, 15, Tile.SPIKE)
    g.set(30, 15, Tile.SPIKE)
    # Chest past the spikes
    g.set(35, 15, Tile.CHEST)

    # Ladder: level 2 back up to level 1 (right side)
    for y in range(15, 21):
        g.set(31, y, Tile.LADDER)

    # === Level 3: treasure room, floor y=9 ===
    _fill_rect(g, 1, 9, 30, 9, Tile.DIRT)
    # Chests in the treasure room
    g.set(5, 10, Tile.CHEST)
    g.set(25, 10, Tile.CHEST)
    # Spike trap near treasure
    g.set(12, 10, Tile.SPIKE)

    # Ladder: level 3 back up to level 2 (left side)
    for y in range(10, 16):
        g.set(8, y, Tile.LADDER)

    # === Level 4: deep vault, floor y=4 (already placed) ===
    # Small platform extension for treasure
    _fill_rect(g, 18, 4, 38, 4, Tile.DIRT)  # extend floor right
    g.set(35, 5, Tile.CHEST)
    g.set(25, 5, Tile.SPIKE)
    g.set(28, 5, Tile.SPIKE)

    # Ladder: level 4 back up to level 3
    for y in range(5, 11):
        g.set(20, y, Tile.LADDER)

    return g
