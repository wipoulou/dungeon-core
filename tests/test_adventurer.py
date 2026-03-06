from dungeon.adventurer import Adventurer


def test_take_damage_generates_mana():
    adv = Adventurer(x=0, y=0)
    mana = adv.take_damage(30)
    assert mana == 15  # 0.5x damage
    assert adv.hp == 70
    assert adv.total_damage_taken == 30


def test_lethal_damage_kills():
    adv = Adventurer(x=0, y=0, hp=10)
    mana = adv.take_damage(20)
    assert not adv.alive
    assert adv.hp == 0
    assert mana == 10


def test_dead_adventurer_no_mana():
    adv = Adventurer(x=0, y=0, hp=0, alive=False)
    mana = adv.take_damage(50)
    assert mana == 0
