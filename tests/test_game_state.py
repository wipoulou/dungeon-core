from dungeon.game_state import PARTY_SHARE_RANGE, SPAWN_STAGGER, SYMPATHY_GREED_DRAIN, Party, new_game
from dungeon.adventurer import Adventurer, AdventurerClass
from dungeon.grid import Tile


def test_spawn_adventurer():
    gs = new_game()
    adv = gs.spawn_adventurer(AdventurerClass.WARRIOR)
    assert adv is not None
    sx, sy = gs.grid.entrance_pos
    assert adv.x == float(sx)
    assert adv.y == float(sy)
    assert len(gs.adventurers) == 1


def test_adventurer_completes_run():
    """Simulate the full room slice: adventurer explores, earns mana, completes."""
    gs = new_game()
    gs.spawn_adventurer(AdventurerClass.WARRIOR)

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


def test_spawn_party():
    gs = new_game()
    gs.auto_spawn = False
    party = gs.spawn_party()
    assert party._pending_spawns > 0
    # Tick enough to spawn all members
    for _ in range(int(5 / 0.016)):
        gs.update(0.016)
    assert party._pending_spawns == 0
    assert len(party.members) >= 2


def test_auto_spawn_creates_wave():
    gs = new_game()
    gs.auto_spawn = True  # off by default
    gs._wave_timer = 0.1  # trigger quickly
    # Tick past the timer
    for _ in range(20):
        gs.update(0.016)
    assert gs._wave_count >= 1
    assert len(gs.parties) >= 1


def test_party_share_hazards_when_close():
    gs = new_game()
    a = Adventurer(x=5.0, y=14.0)
    b = Adventurer(x=7.0, y=14.0)  # 2 tiles away — within range
    a._known_hazards = {(10, 10)}
    party = Party(members=[a, b])
    gs.parties.append(party)
    gs.adventurers.extend([a, b])
    gs.update(0.016)
    assert (10, 10) in b._known_hazards


def test_party_sympathy_drains_greed():
    gs = new_game()
    a = Adventurer(x=5.0, y=14.0)
    b = Adventurer(x=7.0, y=14.0)
    a._returning = True  # a is fleeing
    b._greed = 1.0
    party = Party(members=[a, b])
    gs.parties.append(party)
    gs.adventurers.extend([a, b])
    # Tick for a few seconds
    for _ in range(60):
        gs.update(0.016)
    assert b._greed < 1.0  # sympathy kicked in


def test_party_sympathy_scales_with_missing():
    gs = new_game()
    a = Adventurer(x=5.0, y=14.0, alive=False)  # dead
    b = Adventurer(x=6.0, y=14.0)
    b._returning = True  # also fleeing
    c = Adventurer(x=7.0, y=14.0)
    c._greed = 1.0
    party = Party(members=[a, b, c])
    gs.parties.append(party)
    gs.adventurers.extend([a, b, c])
    # 2 members gone — drain should be 2x
    gs.update(1.0)
    expected_drain = SYMPATHY_GREED_DRAIN * 2 * 1.0
    assert abs(c._greed - (1.0 - expected_drain)) < 0.01


def test_party_no_share_when_far():
    gs = new_game()
    a = Adventurer(x=1.0, y=14.0)
    b = Adventurer(x=20.0, y=14.0)  # far apart
    a._known_hazards = {(10, 10)}
    party = Party(members=[a, b])
    gs.parties.append(party)
    gs.adventurers.extend([a, b])
    gs.update(0.016)
    assert (10, 10) not in b._known_hazards


def test_party_stagger():
    gs = new_game()
    gs.auto_spawn = False
    party = gs.spawn_party()
    initial_pending = party._pending_spawns
    # First member spawns immediately (timer starts at 0)
    gs.update(0.016)
    assert party._pending_spawns == initial_pending - 1
    # Second member spawns after stagger delay
    assert party._pending_spawns > 0
    for _ in range(int(SPAWN_STAGGER / 0.016) + 2):
        gs.update(0.016)
    assert party._pending_spawns < initial_pending - 1
