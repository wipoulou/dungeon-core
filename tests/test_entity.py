from dungeon.entity import Entity, Faction, CombatState


def test_take_damage_with_defense():
    e = Entity(x=0, y=0, hp=100, defense=5)
    actual = e.take_damage(20)
    assert actual == 15  # 20 - 5 defense
    assert e.hp == 85


def test_take_damage_minimum_one():
    e = Entity(x=0, y=0, hp=100, defense=50)
    actual = e.take_damage(10)
    assert actual == 1  # min 1 damage
    assert e.hp == 99


def test_lethal_damage_disengages():
    a = Entity(x=0, y=0, hp=10)
    b = Entity(x=1, y=0, hp=100)
    a.engage(b)
    assert a.in_combat
    a.take_damage(20)
    assert not a.alive
    assert not a.in_combat


def test_try_attack():
    a = Entity(x=0, y=0, attack=15, attack_speed=2.0)
    b = Entity(x=1, y=0, hp=100)
    a.engage(b)
    # First attack fires immediately (cooldown starts at 0)
    dmg = a.try_attack(0.0)
    assert dmg == 15
    # Next attack blocked by cooldown (0.5s for attack_speed=2.0)
    dmg = a.try_attack(0.1)
    assert dmg == 0
    # After cooldown expires
    dmg = a.try_attack(0.5)
    assert dmg == 15


def test_engage_disengage():
    a = Entity(x=0, y=0)
    b = Entity(x=1, y=0)
    a.engage(b)
    assert a.combat_state == CombatState.ENGAGED
    assert a._combat_target is b
    a.disengage()
    assert a.combat_state == CombatState.IDLE
    assert a._combat_target is None
