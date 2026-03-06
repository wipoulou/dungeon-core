from dungeon.grid import Grid, Tile, make_room_slice


def test_grid_basics():
    g = Grid(5, 5)
    assert g.get(0, 0) == Tile.EMPTY
    g.set(0, 0, Tile.DIRT)
    assert g.get(0, 0) == Tile.DIRT
    assert g.is_solid(0, 0)
    assert not g.is_solid(1, 1)


def test_out_of_bounds_is_solid():
    g = Grid(5, 5)
    assert g.get(-1, 0) == Tile.DIRT
    assert g.get(5, 0) == Tile.DIRT


def test_entrance_tracking():
    g = Grid(10, 5)
    g.set(0, 1, Tile.ENTRANCE)
    assert g.entrance_pos == (0, 1)


def test_room_slice_structure():
    g = make_room_slice()
    assert g.width == 30
    assert g.height == 20
    assert g.entrance_pos is not None
    # Entrance is not solid
    assert not g.is_solid(*g.entrance_pos)
    # Walls on sides
    assert g.is_solid(0, 10)
    assert g.is_solid(29, 10)
    # Floor and ceiling
    assert g.is_solid(15, 0)
    assert g.is_solid(15, 19)
