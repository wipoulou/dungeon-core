from dungeon.game_state import new_game
from dungeon.grid import Tile


def test_spawn_adventurer():
    gs = new_game()
    adv = gs.spawn_adventurer()
    assert adv is not None
    sx, sy = gs.grid.entrance_pos
    assert adv.x == float(sx)
    assert adv.y == float(sy)
    assert len(gs.adventurers) == 1


def test_adventurer_completes_run():
    """Simulate the full room slice: adventurer explores, earns mana, completes."""
    gs = new_game()
    gs.spawn_adventurer()

    dt = 1 / 60
    for _ in range(120 * 60):  # up to 120 seconds (exploration is slower)
        gs.update(dt)
        if gs.is_complete:
            break

    adv = gs.adventurers[0]
    assert gs.is_complete, f"Stuck at ({adv.x:.1f}, {adv.y:.1f}), alive={adv.alive}"
    assert gs.mana > 0, "Should have earned mana"


def test_dig_removes_dirt():
    gs = new_game()
    # Find a dirt tile
    x, y = 5, 0  # bottom floor is dirt
    assert gs.grid.get(x, y) == Tile.DIRT
    assert gs.dig(x, y)
    assert gs.grid.get(x, y) == Tile.EMPTY


def test_dig_non_dirt_fails():
    gs = new_game()
    sx, sy = gs.grid.entrance_pos
    assert not gs.dig(sx, sy)  # can't dig entrance


def test_place_on_empty():
    gs = new_game()
    gs.dig(5, 0)  # make a hole
    assert gs.place(5, 0)
    assert gs.grid.get(5, 0) == Tile.DIRT


def test_dig_invalidates_path():
    gs = new_game()
    adv = gs.spawn_adventurer()
    gs.update(0.016)  # tick to compute path
    assert not adv._path_dirty
    gs.dig(5, 0)
    assert adv._path_dirty
