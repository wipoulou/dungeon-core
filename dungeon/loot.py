"""Loot system: vault (stockpile) and chests."""

from __future__ import annotations

from dataclasses import dataclass, field

from dungeon.grid import Grid, Tile

CHEST_FILL_COST = 10  # mana cost to print loot when vault is empty


@dataclass
class Chest:
    x: int
    y: int
    has_loot: bool = True
    refill_timer: float = 0.0

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)


@dataclass
class Vault:
    """The dungeon's stockpile of loot items."""

    items: int = 0
    chests: dict[tuple[int, int], Chest] = field(default_factory=dict)

    def place_chest(self, grid: Grid, x: int, y: int, mana: int) -> tuple[bool, int]:
        """Place a chest on the grid. Returns (success, mana_spent).

        Fills from vault for free, or costs mana to print loot.
        """
        if not grid.in_bounds(x, y):
            return False, 0
        if grid.get(x, y) != Tile.EMPTY:
            return False, 0
        # Must be placed on a floor (solid tile below)
        if not grid.is_solid(x, y - 1):
            return False, 0

        mana_spent = 0
        has_loot = True
        if self.items > 0:
            self.items -= 1
        elif mana >= CHEST_FILL_COST:
            mana_spent = CHEST_FILL_COST
        else:
            has_loot = False

        grid.set(x, y, Tile.CHEST)
        self.chests[(x, y)] = Chest(x, y, has_loot=has_loot)
        return True, mana_spent

    def remove_chest(self, grid: Grid, x: int, y: int) -> bool:
        """Remove a chest from the grid."""
        if grid.get(x, y) != Tile.CHEST:
            return False
        chest = self.chests.pop((x, y), None)
        grid.set(x, y, Tile.EMPTY)
        # Return loot to vault if chest still had loot
        if chest and chest.has_loot:
            self.items += 1
        return True

    def loot_chest(self, x: int, y: int) -> bool:
        """Adventurer loots a chest. Returns True if there was loot."""
        chest = self.chests.get((x, y))
        if chest is None or not chest.has_loot:
            return False
        chest.has_loot = False
        return True

    def update(self, dt: float) -> None:
        """Refill empty chests from vault over time."""
        for chest in self.chests.values():
            if chest.has_loot or self.items <= 0:
                continue
            chest.refill_timer += dt
            if chest.refill_timer >= 5.0:  # 5 seconds to refill
                chest.has_loot = True
                chest.refill_timer = 0.0
                self.items -= 1
