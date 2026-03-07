"""Tests for dungeon/beliefs.py — BeliefMap."""

import pytest
from dungeon.beliefs import Belief, BeliefConflict, BeliefMap, DECAY_RATE, FORGET_THRESHOLD
from dungeon.grid import Tile


T = (5, 3)   # a tile coordinate used throughout
NOW = 100.0  # arbitrary game timestamp


class TestObserve:
    def test_first_observation_stored(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        b = bm.get(T, NOW)
        assert b is not None
        assert b.value == Tile.CHEST
        assert b.confidence == pytest.approx(0.9)

    def test_first_observation_returns_no_conflict(self):
        bm = BeliefMap()
        result = bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        assert result is None

    def test_agreeing_observation_increases_confidence(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.7, "self", NOW)
        bm.observe(T, Tile.CHEST, 0.7, "adv_2", NOW)
        b = bm.get(T, NOW)
        assert b.confidence > 0.7

    def test_agreeing_confidence_caps_at_one(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.99, "self", NOW)
        bm.observe(T, Tile.CHEST, 0.99, "party", NOW)
        b = bm.get(T, NOW)
        assert b.confidence <= 1.0

    def test_conflicting_observation_returns_conflict(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        conflict = bm.observe(T, Tile.EMPTY, 0.95, "self", NOW)
        assert conflict is not None
        assert isinstance(conflict, BeliefConflict)
        assert conflict.held_value == Tile.CHEST
        assert conflict.new_value == Tile.EMPTY

    def test_conflicting_higher_confidence_wins(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.6, "map", NOW)
        bm.observe(T, Tile.EMPTY, 0.95, "self", NOW)
        b = bm.get(T, NOW)
        assert b.value == Tile.EMPTY

    def test_conflicting_lower_confidence_loses(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.95, "self", NOW)
        bm.observe(T, Tile.EMPTY, 0.4, "rumor", NOW)
        b = bm.get(T, NOW)
        assert b.value == Tile.CHEST

    def test_conflicting_reduces_confidence(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        bm.observe(T, Tile.EMPTY, 0.95, "self", NOW)
        b = bm.get(T, NOW)
        # Winner should have reduced confidence vs. if sources had agreed
        assert b.confidence < 0.95

    def test_conflicting_confidence_never_below_forget_threshold(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        bm.observe(T, Tile.EMPTY, 0.9, "self", NOW)
        b = bm.get(T, NOW)
        assert b is not None  # not forgotten
        assert b.confidence > FORGET_THRESHOLD


class TestGet:
    def test_unknown_tile_returns_none(self):
        bm = BeliefMap()
        assert bm.get(T, NOW) is None

    def test_known_tile_returns_belief(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        assert bm.get(T, NOW) is not None

    def test_knows(self):
        bm = BeliefMap()
        assert not bm.knows(T, NOW)
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        assert bm.knows(T, NOW)

    def test_get_value(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        assert bm.get_value(T, NOW) == Tile.CHEST

    def test_get_value_unknown_returns_none(self):
        bm = BeliefMap()
        assert bm.get_value(T, NOW) is None


class TestDecay:
    def test_confidence_decays_over_time(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        later = NOW + 10.0
        b = bm.get(T, later)
        assert b is not None
        expected = 0.9 * (1.0 - DECAY_RATE * 10.0)
        assert b.confidence == pytest.approx(expected)

    def test_fully_decayed_belief_forgotten(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        # Time needed to reach FORGET_THRESHOLD
        # conf * (1 - DECAY_RATE * t) < FORGET_THRESHOLD
        # t > (1 - FORGET_THRESHOLD/conf) / DECAY_RATE
        t = (1.0 - FORGET_THRESHOLD / 0.9) / DECAY_RATE + 1.0
        assert bm.get(T, NOW + t) is None

    def test_fresh_observation_resets_decay(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        later = NOW + 20.0
        # Re-observe resets the clock
        bm.observe(T, Tile.CHEST, 0.9, "self", later)
        b = bm.get(T, later + 1.0)
        # Should only have decayed 1 second, not 21
        expected = 0.9 * (1.0 - DECAY_RATE * 1.0)  # approximately
        # Merged confidence will be higher, but decay from `later` should be ~1s
        assert b.confidence > 0.9 * (1.0 - DECAY_RATE * 20.0)


class TestForget:
    def test_forget_removes_belief(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        bm.forget(T)
        assert bm.get(T, NOW) is None

    def test_forget_nonexistent_is_safe(self):
        bm = BeliefMap()
        bm.forget(T)  # should not raise

    def test_forget_source_removes_matching(self):
        bm = BeliefMap()
        t1, t2, t3 = (1, 0), (2, 0), (3, 0)
        bm.observe(t1, Tile.CHEST, 0.9, "map_v1", NOW)
        bm.observe(t2, Tile.SPIKE, 0.8, "map_v1", NOW)
        bm.observe(t3, Tile.EMPTY, 0.7, "self", NOW)
        bm.forget_source("map_v1")
        assert bm.get(t1, NOW) is None
        assert bm.get(t2, NOW) is None
        assert bm.get(t3, NOW) is not None  # self-observed, unaffected


class TestMergeFrom:
    def test_merge_adds_new_beliefs(self):
        source = BeliefMap()
        source.observe(T, Tile.CHEST, 0.9, "self", NOW)
        target = BeliefMap()
        count = target.merge_from(source, "adv_1", trust=0.8, now=NOW)
        assert count == 1
        assert target.knows(T, NOW)

    def test_merge_scales_by_trust(self):
        source = BeliefMap()
        source.observe(T, Tile.CHEST, 0.9, "self", NOW)
        target = BeliefMap()
        target.merge_from(source, "adv_1", trust=0.5, now=NOW)
        b = target.get(T, NOW)
        assert b.confidence == pytest.approx(0.9 * 0.5)

    def test_merge_low_trust_below_threshold_skipped(self):
        source = BeliefMap()
        source.observe(T, Tile.CHEST, 0.1, "self", NOW)
        target = BeliefMap()
        target.merge_from(source, "adv_1", trust=0.3, now=NOW)
        # 0.1 * 0.3 = 0.03 < FORGET_THRESHOLD — should be skipped
        assert not target.knows(T, NOW)

    def test_merge_returns_count(self):
        source = BeliefMap()
        for i in range(5):
            source.observe((i, 0), Tile.EMPTY, 0.8, "self", NOW)
        target = BeliefMap()
        count = target.merge_from(source, "adv_1", trust=1.0, now=NOW)
        assert count == 5


class TestObservability:
    def test_dump_contains_entries(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        dump = bm.dump(NOW)
        assert len(dump) == 1
        assert dump[0]["value"] == str(Tile.CHEST)
        assert dump[0]["confidence"] == pytest.approx(0.9)
        assert dump[0]["source"] == "self"

    def test_dump_sorted_by_confidence_desc(self):
        bm = BeliefMap()
        bm.observe((1, 0), Tile.CHEST, 0.9, "self", NOW)
        bm.observe((2, 0), Tile.SPIKE, 0.5, "self", NOW)
        bm.observe((3, 0), Tile.EMPTY, 0.7, "self", NOW)
        dump = bm.dump(NOW)
        confidences = [d["confidence"] for d in dump]
        assert confidences == sorted(confidences, reverse=True)

    def test_dump_excludes_forgotten(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.06, "self", NOW)
        # Far future — belief should be forgotten
        far_future = NOW + 1000.0
        dump = bm.dump(far_future)
        assert len(dump) == 0

    def test_len(self):
        bm = BeliefMap()
        assert len(bm) == 0
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        assert len(bm) == 1

    def test_repr(self):
        bm = BeliefMap()
        bm.observe(T, Tile.CHEST, 0.9, "self", NOW)
        assert "1" in repr(bm)
