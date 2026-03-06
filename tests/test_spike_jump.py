"""Regression tests for spike jumping behavior.

These simulate adventurers walking toward known spikes at various speeds
and verify they jump BEFORE the spike and clear it without taking damage.
"""

from dungeon.adventurer import Adventurer, update_adventurer, SPIKE_DAMAGE
from dungeon.grid import Grid, Tile
from dungeon.loot import Vault


def _make_spike_corridor(spike_x: int = 10) -> Grid:
    """Flat corridor with a spike. Floor at y=0 (DIRT), high ceiling for jump room."""
    g = Grid(20, 15)  # tall enough for jump arcs
    for x in range(20):
        g.set(x, 0, Tile.DIRT)  # floor
    g.set(spike_x, 1, Tile.SPIKE)  # spike on floor level
    g.set(0, 1, Tile.ENTRANCE)
    return g


def _preseed_vision(adv: Adventurer, grid: Grid) -> None:
    """Mark all tiles as seen so vision won't trigger path recalculation."""
    for y in range(grid.height):
        for x in range(grid.width):
            adv._seen.add((x, y))


def _walk_adventurer(adv: Adventurer, grid: Grid, vault: Vault,
                     seconds: float, dt: float = 1/60) -> int:
    """Simulate an adventurer for N seconds, return total mana generated."""
    mana = 0
    steps = int(seconds / dt)
    for _ in range(steps):
        mana += update_adventurer(adv, grid, vault, dt)
    return mana


def _trace_known_spike(speed: float, spike_x: int = 10, direction: int = 1):
    """Trace an adventurer walking toward a KNOWN spike.

    Returns (hp_lost, jumped_x, landed_x) for analysis.
    direction: 1=right, -1=left
    """
    grid = _make_spike_corridor(spike_x)
    vault = Vault()

    if direction == 1:
        start_x = spike_x - 5.0
        path = [(x, 1) for x in range(spike_x - 4, spike_x + 6)]
    else:
        start_x = spike_x + 5.0
        path = [(x, 1) for x in range(spike_x + 4, spike_x - 6, -1)]

    adv = Adventurer(x=start_x, y=1.0, speed=speed, hp=200, max_hp=200)
    adv._entrance = (0, 1)
    adv.grounded = True
    adv._known_hazards = {(spike_x, 1)}  # already knows about spike
    _preseed_vision(adv, grid)  # prevent vision from overriding path
    adv._path = path
    adv._path_index = 0
    adv._path_dirty = False

    jumped_x = None
    landed_x = None
    was_airborne = False
    start_hp = adv.hp

    for frame in range(600):  # 10 seconds
        old_grounded = adv.grounded
        old_vy = adv.vy
        update_adventurer(adv, grid, vault, 1/60)

        # Detect jump start
        if old_vy <= 0 and adv.vy > 0 and old_grounded:
            jumped_x = adv.x
            was_airborne = True

        # Detect landing after jump
        if was_airborne and not old_grounded and adv.grounded:
            landed_x = adv.x
            was_airborne = False

        # Stop once well past the spike
        if direction == 1 and adv.x > spike_x + 4:
            break
        if direction == -1 and adv.x < spike_x - 4:
            break

    hp_lost = start_hp - adv.hp
    return hp_lost, jumped_x, landed_x


def test_first_encounter_takes_one_hit():
    """First time hitting an unknown spike should deal exactly one hit of damage."""
    grid = _make_spike_corridor()
    vault = Vault()
    adv = Adventurer(x=3.0, y=1.0, speed=4.0, hp=200, max_hp=200)
    adv._entrance = (0, 1)
    adv.grounded = True
    _preseed_vision(adv, grid)  # prevent path recalc from vision
    adv._path = [(x, 1) for x in range(4, 18)]
    adv._path_index = 0
    adv._path_dirty = False

    _walk_adventurer(adv, grid, vault, 5.0)

    # Should have taken exactly one spike hit (first encounter)
    assert len(adv.damage_log) == 1, f"Expected 1 hit, got {len(adv.damage_log)}: {adv.damage_log}"
    assert adv.damage_log[0] == SPIKE_DAMAGE
    # Should have learned about the spike
    assert (10, 1) in adv._known_hazards


def test_known_spike_jumped_at_speed_5():
    """Fast adventurer (speed=5.0) should jump before and clear the spike."""
    hp_lost, jx, lx = _trace_known_spike(5.0)
    assert hp_lost == 0, f"Should take no damage, lost {hp_lost}"
    assert jx is not None and jx < 10, f"Should jump before spike, jumped at x={jx}"
    assert lx is not None and lx > 11, f"Should land past spike, landed at x={lx}"


def test_known_spike_jumped_at_speed_4():
    """Default speed (4.0) should jump before and clear."""
    hp_lost, jx, lx = _trace_known_spike(4.0)
    assert hp_lost == 0, f"Should take no damage, lost {hp_lost}"
    assert jx is not None and jx < 10, f"jumped at x={jx}"
    assert lx is not None and lx > 11, f"landed at x={lx}"


def test_known_spike_jumped_at_speed_3_5():
    """Slow adventurer (speed=3.5) should still jump before and clear."""
    hp_lost, jx, lx = _trace_known_spike(3.5)
    assert hp_lost == 0, f"Should take no damage, lost {hp_lost}"
    assert jx is not None and jx < 10, f"jumped at x={jx}"
    assert lx is not None and lx > 11, f"landed at x={lx}"


def test_known_spike_no_second_hit():
    """After discovering a spike, crossing it again should deal 0 damage."""
    grid = _make_spike_corridor()
    vault = Vault()
    adv = Adventurer(x=3.0, y=1.0, speed=4.0, hp=200, max_hp=200)
    adv._entrance = (0, 1)
    adv.grounded = True
    adv._known_hazards = {(10, 1)}
    _preseed_vision(adv, grid)
    adv._path = [(x, 1) for x in range(4, 18)]
    adv._path_index = 0
    adv._path_dirty = False

    _walk_adventurer(adv, grid, vault, 5.0)

    assert adv.hp == 200, f"Should take no damage crossing known spike, hp={adv.hp}, log={adv.damage_log}"


def test_known_spike_no_second_hit_slow():
    """Slow adventurer crossing a known spike should also take 0 damage."""
    grid = _make_spike_corridor()
    vault = Vault()
    adv = Adventurer(x=3.0, y=1.0, speed=3.5, hp=200, max_hp=200)
    adv._entrance = (0, 1)
    adv.grounded = True
    adv._known_hazards = {(10, 1)}
    _preseed_vision(adv, grid)
    adv._path = [(x, 1) for x in range(4, 18)]
    adv._path_index = 0
    adv._path_dirty = False

    _walk_adventurer(adv, grid, vault, 5.0)

    assert adv.hp == 200, f"Slow adv should clear known spike, hp={adv.hp}, log={adv.damage_log}"


def test_return_trip_jumps_spike():
    """Adventurer heading LEFT past a known spike should also jump and clear."""
    grid = _make_spike_corridor()
    vault = Vault()
    adv = Adventurer(x=15.0, y=1.0, speed=4.0, hp=200, max_hp=200)
    adv._entrance = (0, 1)
    adv.grounded = True
    adv._known_hazards = {(10, 1)}
    _preseed_vision(adv, grid)
    adv._path = [(x, 1) for x in range(14, 2, -1)]
    adv._path_index = 0
    adv._path_dirty = False

    _walk_adventurer(adv, grid, vault, 8.0)

    assert adv.hp == 200, f"Return trip should clear spike, hp={adv.hp}, log={adv.damage_log}"


def test_known_spike_low_ceiling():
    """Spike with a ceiling 3 tiles above — must not bonk and fall on spike."""
    g = Grid(20, 15)
    for x in range(20):
        g.set(x, 0, Tile.DIRT)   # floor
        g.set(x, 4, Tile.DIRT)   # ceiling 3 tiles above floor (y=1,2,3 open)
    g.set(10, 1, Tile.SPIKE)
    g.set(0, 1, Tile.ENTRANCE)

    vault = Vault()
    adv = Adventurer(x=5.0, y=1.0, speed=4.0, hp=200, max_hp=200)
    adv._entrance = (0, 1)
    adv.grounded = True
    adv._known_hazards = {(10, 1)}
    _preseed_vision(adv, g)
    adv._path = [(x, 1) for x in range(6, 18)]
    adv._path_index = 0
    adv._path_dirty = False

    _walk_adventurer(adv, g, vault, 5.0)

    assert adv.hp == 200, f"Low ceiling spike should be cleared, hp={adv.hp}, log={adv.damage_log}"


def test_known_spike_game_map_geometry():
    """Test spike hopping in a corridor matching game map ceiling height."""
    # Build a simple corridor with game-map proportions (3 tiles headroom)
    g = Grid(20, 10)
    for x in range(20):
        g.set(x, 0, Tile.DIRT)   # floor
        g.set(x, 4, Tile.DIRT)   # ceiling (3 tiles headroom: y=1,2,3)
    g.set(10, 1, Tile.SPIKE)
    g.set(13, 1, Tile.SPIKE)
    g.set(0, 1, Tile.ENTRANCE)

    vault = Vault()
    adv = Adventurer(x=5.0, y=1.0, speed=3.5, hp=200, max_hp=200)
    adv._entrance = (0, 1)
    adv.grounded = True
    adv._known_hazards = {(10, 1), (13, 1)}
    _preseed_vision(adv, g)
    adv._path = [(x, 1) for x in range(6, 18)]
    adv._path_index = 0
    adv._path_dirty = False

    _walk_adventurer(adv, g, vault, 8.0)

    assert adv.hp == 200, f"Corridor spikes should be cleared, hp={adv.hp}, log={adv.damage_log}"


def test_return_trip_slow():
    """Slow adventurer heading LEFT should also clear."""
    grid = _make_spike_corridor()
    vault = Vault()
    adv = Adventurer(x=15.0, y=1.0, speed=3.5, hp=200, max_hp=200)
    adv._entrance = (0, 1)
    adv.grounded = True
    adv._known_hazards = {(10, 1)}
    _preseed_vision(adv, grid)
    adv._path = [(x, 1) for x in range(14, 2, -1)]
    adv._path_index = 0
    adv._path_dirty = False

    _walk_adventurer(adv, grid, vault, 8.0)

    assert adv.hp == 200, f"Slow return should clear spike, hp={adv.hp}, log={adv.damage_log}"


def _make_spike_ladder_corridor(spike_x: int = 10, ladder_x: int = 11) -> Grid:
    """Corridor with a spike immediately before a ladder."""
    g = Grid(20, 15)
    for x in range(20):
        g.set(x, 0, Tile.DIRT)  # floor
    g.set(spike_x, 1, Tile.SPIKE)
    for y in range(1, 8):
        g.set(ladder_x, y, Tile.LADDER)
    g.set(0, 1, Tile.ENTRANCE)
    return g


def _walk_and_track(adv, grid, vault, seconds, dt=1/60):
    """Walk adventurer and track hop count and peak Y."""
    hop_count = 0
    peak_y = adv.y
    for _ in range(int(seconds / dt)):
        old_vy = adv.vy
        old_grounded = adv.grounded
        update_adventurer(adv, grid, vault, dt)
        if adv.y > peak_y:
            peak_y = adv.y
        if old_vy <= 0 and adv.vy > 0 and old_grounded:
            hop_count += 1
    return hop_count, peak_y


def test_spike_before_ladder_right():
    """Walking right through spike then up ladder — no damage, reaches ladder."""
    for speed in (4.0, 3.5):
        grid = _make_spike_ladder_corridor(spike_x=10, ladder_x=11)
        vault = Vault()
        adv = Adventurer(x=7.0, y=1.0, speed=speed, hp=200, max_hp=200)
        adv._entrance = (0, 1)
        adv.grounded = True
        adv._known_hazards = {(10, 1)}
        _preseed_vision(adv, grid)
        adv._path = [(x, 1) for x in range(8, 12)] + [(11, y) for y in range(2, 8)]
        adv._path_index = 0
        adv._path_dirty = False

        hops, peak_y = _walk_and_track(adv, grid, vault, 4.0)

        assert adv.hp == 200, f"speed={speed}: should clear spike, hp={adv.hp}, log={adv.damage_log}"
        assert peak_y >= 3.0, f"speed={speed}: should have climbed ladder, peak_y={peak_y:.1f}"
        assert hops <= 2, f"speed={speed}: infinite-hop, hopped {hops} times"
