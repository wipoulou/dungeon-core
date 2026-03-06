"""Core game state - ties grid + adventurers + mana together."""

from __future__ import annotations

from dataclasses import dataclass, field

from dungeon.adventurer import Adventurer, update_adventurer
from dungeon.grid import Grid, Tile, make_room_slice
from dungeon.loot import Vault


@dataclass
class GameState:
    grid: Grid
    vault: Vault = field(default_factory=Vault)
    adventurers: list[Adventurer] = field(default_factory=list)
    mana: int = 50  # starting mana to place some chests
    time_elapsed: float = 0.0

    def spawn_adventurer(self) -> Adventurer | None:
        if self.grid.spawn_pos is None:
            return None
        sx, sy = self.grid.spawn_pos
        adv = Adventurer(x=float(sx), y=float(sy))
        self.adventurers.append(adv)
        return adv

    def dig(self, x: int, y: int) -> bool:
        """Remove a dirt tile. Returns True if successful."""
        if not self.grid.in_bounds(x, y):
            return False
        if self.grid.get(x, y) != Tile.DIRT:
            return False
        self.grid.set(x, y, Tile.EMPTY)
        self._invalidate_paths()
        return True

    def place_chest(self, x: int, y: int) -> bool:
        """Place a chest. Returns True if successful."""
        ok, cost = self.vault.place_chest(self.grid, x, y, self.mana)
        if ok:
            self.mana -= cost
            self._invalidate_paths()
        return ok

    def remove_chest(self, x: int, y: int) -> bool:
        """Remove a chest. Returns True if successful."""
        ok = self.vault.remove_chest(self.grid, x, y)
        if ok:
            self._invalidate_paths()
        return ok

    def place(self, x: int, y: int, tile: Tile = Tile.DIRT) -> bool:
        """Place a dirt tile. Returns True if successful."""
        if not self.grid.in_bounds(x, y):
            return False
        if self.grid.get(x, y) != Tile.EMPTY:
            return False
        self.grid.set(x, y, tile)
        self._invalidate_paths()
        return True

    def place_spike(self, x: int, y: int) -> bool:
        """Place a spike trap. Must be on a floor (solid below)."""
        if not self.grid.in_bounds(x, y):
            return False
        if self.grid.get(x, y) != Tile.EMPTY:
            return False
        if not self.grid.is_solid(x, y - 1):
            return False
        self.grid.set(x, y, Tile.SPIKE)
        self._invalidate_paths()
        return True

    def remove_spike(self, x: int, y: int) -> bool:
        """Remove a spike trap."""
        if not self.grid.in_bounds(x, y):
            return False
        if self.grid.get(x, y) != Tile.SPIKE:
            return False
        self.grid.set(x, y, Tile.EMPTY)
        self._invalidate_paths()
        return True

    def _invalidate_paths(self) -> None:
        for adv in self.adventurers:
            adv._path_dirty = True

    def update(self, dt: float) -> None:
        self.time_elapsed += dt
        self.vault.update(dt)
        for adv in self.adventurers:
            mana_gained = update_adventurer(adv, self.grid, self.vault, dt)
            self.mana += mana_gained

    @property
    def active_adventurers(self) -> list[Adventurer]:
        return [a for a in self.adventurers if a.alive and not a.reached_exit]

    @property
    def is_complete(self) -> bool:
        """True when all adventurers have either exited or died."""
        return len(self.adventurers) > 0 and len(self.active_adventurers) == 0


def new_game() -> GameState:
    """Create a fresh Room Slice game."""
    gs = GameState(grid=make_room_slice())
    gs.vault.items = 3  # start with some loot in the vault
    return gs
