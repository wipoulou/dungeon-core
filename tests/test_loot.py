from dungeon.grid import Grid, Tile
from dungeon.loot import CHEST_FILL_COST, Vault


def _simple_grid() -> Grid:
    """5-wide grid with a floor."""
    g = Grid(5, 5)
    for x in range(5):
        g.set(x, 0, Tile.DIRT)
    return g


def test_place_chest_from_vault():
    g = _simple_grid()
    v = Vault(items=3)
    ok, cost = v.place_chest(g, 2, 1, mana=0)
    assert ok
    assert cost == 0  # free from vault
    assert v.items == 2
    assert g.get(2, 1) == Tile.CHEST
    assert v.chests[(2, 1)].has_loot


def test_place_chest_costs_mana_when_vault_empty():
    g = _simple_grid()
    v = Vault(items=0)
    ok, cost = v.place_chest(g, 2, 1, mana=50)
    assert ok
    assert cost == CHEST_FILL_COST
    assert v.chests[(2, 1)].has_loot


def test_place_chest_empty_when_broke():
    g = _simple_grid()
    v = Vault(items=0)
    ok, cost = v.place_chest(g, 2, 1, mana=0)
    assert ok
    assert cost == 0
    assert not v.chests[(2, 1)].has_loot


def test_place_chest_needs_floor():
    g = _simple_grid()
    v = Vault(items=1)
    # y=3 has no floor below (y=2 is empty)
    ok, _ = v.place_chest(g, 2, 3, mana=0)
    assert not ok


def test_loot_chest():
    g = _simple_grid()
    v = Vault(items=1)
    v.place_chest(g, 2, 1, mana=0)
    assert v.loot_chest(2, 1)
    assert not v.chests[(2, 1)].has_loot
    # Can't loot twice
    assert not v.loot_chest(2, 1)


def test_remove_chest_returns_loot():
    g = _simple_grid()
    v = Vault(items=1)
    v.place_chest(g, 2, 1, mana=0)
    assert v.items == 0
    v.remove_chest(g, 2, 1)
    assert v.items == 1  # loot returned
    assert g.get(2, 1) == Tile.EMPTY


def test_chest_refills_from_vault():
    g = _simple_grid()
    v = Vault(items=2)
    v.place_chest(g, 2, 1, mana=0)
    v.loot_chest(2, 1)
    assert not v.chests[(2, 1)].has_loot
    assert v.items == 1
    # Simulate time passing
    for _ in range(310):  # just over 5 seconds at 60fps
        v.update(1 / 60)
    assert v.chests[(2, 1)].has_loot
    assert v.items == 0
