"""StatBlock: aggregated stat system with dirty-flag caching.

Every derived value in the game (speed, flee_threshold, observation_confidence,
spell_cost_mult, etc.) lives here. Traits, buffs, items, and debuffs register
Modifiers. The hot path is O(1) — it serves a cached value. Recomputation only
runs when a modifier is added or removed.

Usage:
    stats = StatBlock({"speed": 3.5, "flee_threshold": 0.5})
    stats.add_modifier(Modifier("trait:cautious", "flee_threshold", "add", 0.15))
    stats.get("flee_threshold")  # 0.65, recomputed once then cached
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Modifier:
    """A single stat modifier from any source (trait, buff, item, debuff).

    Additive modifiers are summed first, then all multiplicative modifiers
    are applied as a product:
        final = (base + sum(additive)) * product(multiplicative)
    """
    source: str                      # e.g. "trait:cautious", "buff:haste", "item:boots_of_speed"
    stat: str                        # which stat this modifies
    op: Literal["add", "multiply"]
    value: float


class StatBlock:
    """Cached, dirty-flagged stat aggregator.

    Base values are set at construction and rarely change. Modifiers are
    added/removed dynamically. Derived values are cached until invalidated.
    """

    def __init__(self, base: dict[str, float]) -> None:
        self._base: dict[str, float] = dict(base)
        self._modifiers: dict[str, list[Modifier]] = {}
        self._cache: dict[str, float] = {}
        self._dirty: set[str] = set()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, stat: str, default: float = 0.0) -> float:
        """Return the current computed value for stat."""
        if stat in self._dirty:
            self._recompute(stat)
        if stat in self._cache:
            return self._cache[stat]
        return self._base.get(stat, default)

    def _recompute(self, stat: str) -> None:
        base = self._base.get(stat, 0.0)
        mods = self._modifiers.get(stat, [])
        additive = sum(m.value for m in mods if m.op == "add")
        multiplicative = math.prod(m.value for m in mods if m.op == "multiply")
        self._cache[stat] = (base + additive) * multiplicative
        self._dirty.discard(stat)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_modifier(self, mod: Modifier) -> None:
        """Register a modifier and invalidate the affected stat."""
        self._modifiers.setdefault(mod.stat, []).append(mod)
        self._dirty.add(mod.stat)
        self._cache.pop(mod.stat, None)

    def remove_modifier(self, mod: Modifier) -> None:
        """Remove a modifier and invalidate the affected stat.

        Safe to call with a modifier that is not currently registered.
        """
        mods = self._modifiers.get(mod.stat, [])
        try:
            mods.remove(mod)
        except ValueError:
            pass
        self._dirty.add(mod.stat)
        self._cache.pop(mod.stat, None)

    def remove_by_source(self, source: str) -> None:
        """Remove all modifiers from a given source (e.g. when a buff expires)."""
        affected: set[str] = set()
        for stat, mods in self._modifiers.items():
            before = len(mods)
            self._modifiers[stat] = [m for m in mods if m.source != source]
            if len(self._modifiers[stat]) != before:
                affected.add(stat)
        for stat in affected:
            self._dirty.add(stat)
            self._cache.pop(stat, None)

    def set_base(self, stat: str, value: float) -> None:
        """Update a base value and invalidate the affected stat."""
        self._base[stat] = value
        self._dirty.add(stat)
        self._cache.pop(stat, None)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def dump(self) -> dict:
        """Full state dump for debugging and tests.

        Returns a dict keyed by stat name with base, modifiers, and
        computed value. Safe to call at any time.
        """
        all_stats = set(self._base) | set(self._modifiers)
        return {
            stat: {
                "value": round(self.get(stat), 6),
                "base": self._base.get(stat, 0.0),
                "modifiers": [
                    {"source": m.source, "op": m.op, "value": m.value}
                    for m in self._modifiers.get(stat, [])
                ],
            }
            for stat in sorted(all_stats)
        }

    def __repr__(self) -> str:
        stats = {s: round(self.get(s), 3) for s in sorted(set(self._base) | set(self._modifiers))}
        return f"StatBlock({stats})"
