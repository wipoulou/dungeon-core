"""BeliefMap: sparse, confidence-weighted knowledge store.

Every entity (adventurer, mob, dungeon) has a BeliefMap. Beliefs are what the
entity *thinks* is true, not ground truth. AI decisions always read from beliefs.

Key properties:
- Sparse: only tiles the entity knows something about have entries
- Confidence-weighted: every belief has a [0.0, 1.0] confidence score
- Lazily decaying: confidence degrades with time, computed on read not per-tick
- Conflict-aware: disagreeing sources pull confidence toward uncertainty
- Source-tracked: each belief records who told the entity (self, party member, map, rumor)

Observability:
    belief_map.dump(now)  →  full state as a plain dict, human-readable
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Confidence decays at this rate per second of game time.
# After ~100s a direct observation degrades to ~13%, after ~200s to ~2% (forgotten).
DECAY_RATE: float = 0.02

# Below this confidence a belief is treated as forgotten and removed.
FORGET_THRESHOLD: float = 0.05

# Direct observation base confidence before trait/context modifiers are applied.
# Caller is expected to pass the already-modulated value.
DIRECT_OBSERVATION_BASE: float = 0.95


@dataclass
class Belief:
    value: Any            # what the entity believes is at this tile
    confidence: float     # [0.0, 1.0]
    observed_at: float    # game time when this belief was recorded
    source: str           # "self", entity_id, "map", "rumor", "guild"


@dataclass
class BeliefConflict:
    """Returned by observe() when new info contradicts an existing belief."""
    tile: tuple[int, int]
    held_value: Any        # what the entity believed before
    held_confidence: float # confidence at the moment of conflict
    new_value: Any         # what the new observation says
    new_confidence: float


class BeliefMap:
    """Sparse belief store for one entity."""

    def __init__(self) -> None:
        self._beliefs: dict[tuple[int, int], Belief] = {}

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def observe(
        self,
        tile: tuple[int, int],
        value: Any,
        confidence: float,
        source: str,
        now: float,
    ) -> BeliefConflict | None:
        """Record an observation. Returns a BeliefConflict if this contradicts
        an existing belief with meaningful confidence, else None.

        confidence should already include all entity modifiers
        (observation_confidence stat, illusion history, etc.).
        """
        existing = self._get_live(tile, now)

        if existing is None:
            self._beliefs[tile] = Belief(value, min(1.0, confidence), now, source)
            return None

        if existing.value == value:
            # Sources agree — merge upward (both can't be wrong)
            merged = 1.0 - (1.0 - existing.confidence) * (1.0 - confidence)
            self._beliefs[tile] = Belief(value, min(1.0, merged), now, source)
            return None

        # Sources conflict
        conflict = BeliefConflict(
            tile=tile,
            held_value=existing.value,
            held_confidence=existing.confidence,
            new_value=value,
            new_confidence=confidence,
        )

        if confidence > existing.confidence:
            # New info wins, but conflict reduces certainty
            result = max(FORGET_THRESHOLD + 0.01, confidence - existing.confidence * 0.4)
            self._beliefs[tile] = Belief(value, result, now, source)
        else:
            # Old info holds, but confidence erodes slightly
            result = max(FORGET_THRESHOLD + 0.01, existing.confidence - confidence * 0.3)
            self._beliefs[tile] = Belief(
                existing.value, result, existing.observed_at, existing.source
            )

        return conflict

    def get(self, tile: tuple[int, int], now: float) -> Belief | None:
        """Return the current belief for tile, with decayed confidence.
        Returns None if unknown or forgotten.
        """
        return self._get_live(tile, now)

    def get_value(self, tile: tuple[int, int], now: float) -> Any | None:
        """Convenience: return just the believed value, or None if unknown."""
        b = self._get_live(tile, now)
        return b.value if b is not None else None

    def knows(self, tile: tuple[int, int], now: float) -> bool:
        return self._get_live(tile, now) is not None

    def all_beliefs(self, now: float) -> dict[tuple[int, int], Belief]:
        """Return all live beliefs (with decayed confidence), pruning forgotten ones."""
        result = {}
        forgotten = []
        for tile, b in self._beliefs.items():
            live = self._decayed(b, now)
            if live is None:
                forgotten.append(tile)
            else:
                result[tile] = live
        for tile in forgotten:
            del self._beliefs[tile]
        return result

    def forget(self, tile: tuple[int, int]) -> None:
        """Explicitly remove a belief (e.g. after entering and observing a room)."""
        self._beliefs.pop(tile, None)

    def forget_source(self, source: str) -> None:
        """Remove all beliefs from a given source (e.g. stale map data)."""
        self._beliefs = {
            tile: b for tile, b in self._beliefs.items() if b.source != source
        }

    # ------------------------------------------------------------------
    # Knowledge propagation support
    # ------------------------------------------------------------------

    def merge_from(
        self,
        other: "BeliefMap",
        source_id: str,
        trust: float,
        now: float,
    ) -> int:
        """Absorb beliefs from another entity's map, scaled by trust.

        Returns the number of beliefs updated or added.
        Used by knowledge propagation during party sync.
        """
        updated = 0
        for tile, b in other.all_beliefs(now).items():
            effective_confidence = b.confidence * trust
            if effective_confidence < FORGET_THRESHOLD:
                continue
            conflict = self.observe(tile, b.value, effective_confidence, source_id, now)
            # Conflicts from merge are expected and not flagged here —
            # callers that need conflict events should check independently
            updated += 1
        return updated

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_live(self, tile: tuple[int, int], now: float) -> Belief | None:
        b = self._beliefs.get(tile)
        if b is None:
            return None
        live = self._decayed(b, now)
        if live is None:
            del self._beliefs[tile]
        return live

    def _decayed(self, b: Belief, now: float) -> Belief | None:
        elapsed = max(0.0, now - b.observed_at)
        conf = b.confidence * (1.0 - DECAY_RATE * elapsed)
        if conf < FORGET_THRESHOLD:
            return None
        return Belief(b.value, conf, b.observed_at, b.source)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def dump(self, now: float) -> list[dict]:
        """Full belief state as a list of dicts, sorted by confidence desc.

        Safe to call at any time. Prunes forgotten beliefs as a side effect.
        """
        result = []
        for tile, b in self.all_beliefs(now).items():
            result.append({
                "tile": tile,
                "value": str(b.value),
                "confidence": round(b.confidence, 3),
                "source": b.source,
                "age_s": round(now - b.observed_at, 1),
            })
        return sorted(result, key=lambda r: r["confidence"], reverse=True)

    def __len__(self) -> int:
        return len(self._beliefs)

    def __repr__(self) -> str:
        return f"BeliefMap({len(self._beliefs)} entries)"
