from dungeon.adventurer import Adventurer
from dungeon.mob import AGGRO_RANGE, Mob, make_mob, update_mob
from dungeon.grid import Grid, Tile


def _make_platform() -> Grid:
    """Small grid: floor at y=0 (DIRT), empty above."""
    g = Grid(10, 5)
    for x in range(10):
        g.set(x, 0, Tile.DIRT)
    return g


def test_slime_patrols():
    g = _make_platform()
    mob = Mob(x=5.0, y=1.0, direction=1.0)
    start_x = mob.x
    for _ in range(60):
        update_mob(mob, g, 1 / 60)
    assert mob.x > start_x  # moved right
    assert mob.alive


def test_slime_reverses_at_wall():
    g = _make_platform()
    g.set(8, 1, Tile.DIRT)  # wall at x=8
    mob = Mob(x=7.0, y=1.0, direction=1.0)
    for _ in range(120):
        update_mob(mob, g, 1 / 60)
    # Should have reversed and be heading left
    assert mob.direction == -1.0 or mob.x < 7.0


def test_slime_reverses_at_edge():
    g = Grid(10, 5)
    # Only floor from x=3 to x=6
    for x in range(3, 7):
        g.set(x, 0, Tile.DIRT)
    mob = Mob(x=5.0, y=1.0, direction=1.0)
    for _ in range(300):
        update_mob(mob, g, 1 / 60)
    # Should stay on the platform
    assert 3.0 <= mob.x <= 7.0


def test_slime_takes_spike_damage():
    g = _make_platform()
    g.set(5, 1, Tile.SPIKE)
    mob = Mob(x=5.0, y=1.0)
    mob.grounded = True
    update_mob(mob, g, 1 / 60)
    assert mob.hp < mob.max_hp


def test_slime_dies():
    mob = Mob(x=0.0, y=0.0, hp=10)
    mob.take_damage(15)
    assert not mob.alive
    assert mob.hp == 0


def test_slime_engages_adventurer():
    g = _make_platform()
    mob = make_mob(5.0, 1.0)
    adv = Adventurer(x=7.0, y=1.0)  # within aggro range
    mob.engage(adv)
    assert mob.in_combat
    # Mob attacks
    dmg = mob.try_attack(0.0)
    assert dmg == mob.attack
    actual = adv.take_damage(dmg)
    assert adv.hp < adv.max_hp


def test_slime_stops_when_fighting():
    g = _make_platform()
    mob = make_mob(5.0, 1.0)
    adv = Adventurer(x=6.0, y=1.0)
    mob.engage(adv)
    start_x = mob.x
    update_mob(mob, g, 1 / 60)
    assert mob.x == start_x  # didn't move — fighting
