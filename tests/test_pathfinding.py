from dungeon.grid import Grid, Tile, make_room_slice
from dungeon.pathfinding import find_path


def test_straight_line():
    g = Grid(10, 3)
    for x in range(10):
        g.set(x, 0, Tile.DIRT)
    path = find_path(g, (0, 1), (9, 1))
    assert len(path) > 0
    assert path[0] == (0, 1)
    assert path[-1] == (9, 1)


def test_jump_over_wall():
    g = Grid(5, 5)
    for x in range(5):
        g.set(x, 0, Tile.DIRT)
    # 1-block wall (jumpable, needs headroom above)
    g.set(2, 1, Tile.DIRT)
    path = find_path(g, (0, 1), (4, 1))
    assert len(path) > 0
    assert path[-1] == (4, 1)


def test_no_path_through_tall_wall():
    g = Grid(5, 4)
    for x in range(5):
        g.set(x, 0, Tile.DIRT)
    # 2-block wall (can't jump over with 1-block jump)
    g.set(2, 1, Tile.DIRT)
    g.set(2, 2, Tile.DIRT)
    g.set(2, 3, Tile.DIRT)
    path = find_path(g, (0, 1), (4, 1))
    assert len(path) == 0


def test_drop_down():
    """Test that pathfinding can find a path that drops down a level."""
    g = Grid(10, 6)
    # Bottom floor
    for x in range(10):
        g.set(x, 0, Tile.DIRT)
    # Upper platform with gap at x=5
    for x in range(6):
        g.set(x, 3, Tile.DIRT)
    # Start on upper platform, goal on bottom
    path = find_path(g, (3, 4), (8, 1))
    assert len(path) > 0
    assert path[-1] == (8, 1)


def test_room_slice_has_path():
    g = make_room_slice()
    assert g.entrance_pos is not None
    # Path from entrance down to deep vault and back
    path_down = find_path(g, g.entrance_pos, (35, 5))
    assert len(path_down) > 0, "Room slice must have a path from entrance to deep vault"
    path_up = find_path(g, (35, 5), g.entrance_pos)
    assert len(path_up) > 0, "Room slice must have a path from deep vault back to entrance"
