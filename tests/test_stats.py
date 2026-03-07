"""Tests for dungeon/stats.py — StatBlock and Modifier."""

import math
import pytest
from dungeon.stats import Modifier, StatBlock


def make_block(**base) -> StatBlock:
    return StatBlock(base)


class TestBaseStats:
    def test_get_base_value(self):
        s = make_block(speed=3.5)
        assert s.get("speed") == pytest.approx(3.5)

    def test_get_missing_returns_default(self):
        s = make_block()
        assert s.get("nonexistent") == 0.0
        assert s.get("nonexistent", default=1.5) == 1.5

    def test_set_base_updates_value(self):
        s = make_block(speed=3.5)
        s.set_base("speed", 5.0)
        assert s.get("speed") == pytest.approx(5.0)


class TestAdditiveModifiers:
    def test_single_additive(self):
        s = make_block(speed=3.0)
        s.add_modifier(Modifier("trait:fast", "speed", "add", 1.0))
        assert s.get("speed") == pytest.approx(4.0)

    def test_multiple_additive_stack(self):
        s = make_block(speed=3.0)
        s.add_modifier(Modifier("trait:fast", "speed", "add", 1.0))
        s.add_modifier(Modifier("buff:haste", "speed", "add", 0.5))
        assert s.get("speed") == pytest.approx(4.5)

    def test_negative_additive(self):
        s = make_block(speed=3.0)
        s.add_modifier(Modifier("debuff:slow", "speed", "add", -1.0))
        assert s.get("speed") == pytest.approx(2.0)


class TestMultiplicativeModifiers:
    def test_single_multiply(self):
        s = make_block(speed=4.0)
        s.add_modifier(Modifier("buff:sprint", "speed", "multiply", 1.5))
        assert s.get("speed") == pytest.approx(6.0)

    def test_multiple_multiply_are_products(self):
        s = make_block(speed=4.0)
        s.add_modifier(Modifier("buff:a", "speed", "multiply", 2.0))
        s.add_modifier(Modifier("buff:b", "speed", "multiply", 0.5))
        assert s.get("speed") == pytest.approx(4.0)  # 4 * 2.0 * 0.5

    def test_no_multiplicative_defaults_to_one(self):
        # math.prod([]) == 1.0
        s = make_block(speed=3.0)
        s.add_modifier(Modifier("trait:x", "speed", "add", 1.0))
        assert s.get("speed") == pytest.approx(4.0)


class TestMixedModifiers:
    def test_additive_then_multiply(self):
        # (base + additive) * multiplicative
        s = make_block(spell_cost_mult=1.0)
        s.add_modifier(Modifier("trait:inefficient", "spell_cost_mult", "add", 0.2))
        s.add_modifier(Modifier("item:staff", "spell_cost_mult", "multiply", 0.9))
        assert s.get("spell_cost_mult") == pytest.approx(1.2 * 0.9)


class TestRemoveModifiers:
    def test_remove_modifier(self):
        s = make_block(speed=3.0)
        mod = Modifier("buff:haste", "speed", "add", 1.0)
        s.add_modifier(mod)
        assert s.get("speed") == pytest.approx(4.0)
        s.remove_modifier(mod)
        assert s.get("speed") == pytest.approx(3.0)

    def test_remove_nonexistent_is_safe(self):
        s = make_block(speed=3.0)
        mod = Modifier("buff:haste", "speed", "add", 1.0)
        s.remove_modifier(mod)  # should not raise
        assert s.get("speed") == pytest.approx(3.0)

    def test_remove_by_source(self):
        s = make_block(speed=3.0, flee_threshold=0.5)
        s.add_modifier(Modifier("buff:courage", "speed", "add", 0.5))
        s.add_modifier(Modifier("buff:courage", "flee_threshold", "add", -0.2))
        s.add_modifier(Modifier("trait:brave", "flee_threshold", "add", -0.1))

        s.remove_by_source("buff:courage")

        assert s.get("speed") == pytest.approx(3.0)
        # trait:brave modifier should remain
        assert s.get("flee_threshold") == pytest.approx(0.4)

    def test_remove_by_source_unrelated_untouched(self):
        s = make_block(speed=3.0)
        s.add_modifier(Modifier("buff:a", "speed", "add", 1.0))
        s.add_modifier(Modifier("buff:b", "speed", "add", 2.0))
        s.remove_by_source("buff:a")
        assert s.get("speed") == pytest.approx(5.0)  # base + buff:b


class TestDirtyFlagCaching:
    def test_value_is_cached_after_first_read(self):
        s = make_block(speed=3.0)
        s.add_modifier(Modifier("x", "speed", "add", 1.0))
        v1 = s.get("speed")
        # Manually corrupt cache to verify it's not recomputed
        s._cache["speed"] = 999.0
        s._dirty.discard("speed")
        assert s.get("speed") == 999.0  # served from cache, not recomputed

    def test_add_modifier_invalidates_cache(self):
        s = make_block(speed=3.0)
        _ = s.get("speed")  # prime cache
        s.add_modifier(Modifier("x", "speed", "add", 1.0))
        assert s.get("speed") == pytest.approx(4.0)  # recomputed

    def test_remove_modifier_invalidates_cache(self):
        s = make_block(speed=3.0)
        mod = Modifier("x", "speed", "add", 1.0)
        s.add_modifier(mod)
        _ = s.get("speed")  # prime cache
        s.remove_modifier(mod)
        assert s.get("speed") == pytest.approx(3.0)  # recomputed


class TestObservability:
    def test_dump_contains_all_stats(self):
        s = make_block(speed=3.0, defense=2.0)
        s.add_modifier(Modifier("trait:brave", "flee_threshold", "add", -0.1))
        dump = s.dump()
        assert "speed" in dump
        assert "defense" in dump
        assert "flee_threshold" in dump

    def test_dump_includes_modifiers(self):
        s = make_block(speed=3.0)
        s.add_modifier(Modifier("trait:fast", "speed", "add", 1.0))
        dump = s.dump()
        mods = dump["speed"]["modifiers"]
        assert len(mods) == 1
        assert mods[0]["source"] == "trait:fast"
        assert mods[0]["value"] == 1.0

    def test_dump_value_matches_get(self):
        s = make_block(speed=3.0)
        s.add_modifier(Modifier("x", "speed", "multiply", 2.0))
        dump = s.dump()
        assert dump["speed"]["value"] == pytest.approx(s.get("speed"))

    def test_repr_includes_values(self):
        s = make_block(speed=3.0)
        assert "speed" in repr(s)


class TestRealWorldScenarios:
    def test_observation_confidence_trait_modifiers(self):
        """Suspicious adventurer trusts their own eyes less."""
        stats = make_block(observation_confidence=0.95)
        stats.add_modifier(Modifier("trait:suspicious", "observation_confidence", "multiply", 0.85))
        assert stats.get("observation_confidence") == pytest.approx(0.95 * 0.85)

    def test_illusion_debuff_stacks_with_suspicious_trait(self):
        """After being fooled by an illusion, confidence drops further."""
        stats = make_block(observation_confidence=0.95)
        stats.add_modifier(Modifier("trait:suspicious", "observation_confidence", "multiply", 0.85))
        stats.add_modifier(Modifier("buff:illusion_exposure", "observation_confidence", "multiply", 0.80))
        expected = 0.95 * 0.85 * 0.80
        assert stats.get("observation_confidence") == pytest.approx(expected)

    def test_buff_expiry_restores_stat(self):
        """When a buff expires (removed by source), stat returns to base+traits."""
        stats = make_block(observation_confidence=0.95)
        stats.add_modifier(Modifier("trait:suspicious", "observation_confidence", "multiply", 0.85))
        stats.add_modifier(Modifier("buff:illusion_exposure", "observation_confidence", "multiply", 0.80))
        stats.remove_by_source("buff:illusion_exposure")
        assert stats.get("observation_confidence") == pytest.approx(0.95 * 0.85)

    def test_inefficient_spell_cost(self):
        stats = make_block(spell_cost_mult=1.0)
        stats.add_modifier(Modifier("trait:inefficient", "spell_cost_mult", "add", 0.2))
        assert stats.get("spell_cost_mult") == pytest.approx(1.2)

    def test_multiple_independent_stats(self):
        stats = make_block(speed=3.5, flee_threshold=0.5, observation_confidence=0.95)
        stats.add_modifier(Modifier("trait:cautious", "flee_threshold", "add", 0.15))
        stats.add_modifier(Modifier("trait:cautious", "speed", "multiply", 0.9))

        assert stats.get("flee_threshold") == pytest.approx(0.65)
        assert stats.get("speed") == pytest.approx(3.5 * 0.9)
        assert stats.get("observation_confidence") == pytest.approx(0.95)  # unaffected
