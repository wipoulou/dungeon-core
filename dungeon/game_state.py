"""Core game state - ties grid + adventurers + mana together."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from dungeon.adventurer import Adventurer, AdventurerClass, make_adventurer, update_adventurer
from dungeon.grid import Grid, Tile, make_room_slice
from dungeon.loot import Vault
from dungeon.mob import AGGRO_RANGE, Mob, make_mob, update_mob

# Wave spawning
WAVE_COOLDOWN = 10.0  # seconds between waves
SPAWN_STAGGER = 0.6   # seconds between party members entering
PARTY_SIZE_MIN = 2
PARTY_SIZE_MAX = 3
PARTY_SHARE_RANGE = 5  # tiles — party members share knowledge when this close
SYMPATHY_GREED_DRAIN = 0.15  # greed/sec drained when a party member is fleeing/gone


@dataclass
class Party:
    """A group of adventurers that entered together."""
    members: list[Adventurer] = field(default_factory=list)
    _pending_spawns: int = 0  # members still waiting to enter
    _spawn_timer: float = 0.0  # countdown to next member spawn

    @property
    def active(self) -> bool:
        return any(a.alive and not a.reached_exit for a in self.members) or self._pending_spawns > 0


@dataclass
class GameState:
    grid: Grid
    vault: Vault = field(default_factory=Vault)
    adventurers: list[Adventurer] = field(default_factory=list)
    parties: list[Party] = field(default_factory=list)
    mobs: list[Mob] = field(default_factory=list)
    mana: int = 50  # starting mana to place some chests
    time_elapsed: float = 0.0
    auto_spawn: bool = False
    _wave_timer: float = 3.0  # first wave comes quickly
    _wave_count: int = 0

    def spawn_adventurer(self, adv_class: AdventurerClass | None = None) -> Adventurer | None:
        if self.grid.entrance_pos is None:
            return None
        sx, sy = self.grid.entrance_pos
        if adv_class is None:
            adv_class = random.choice(list(AdventurerClass))
        adv = make_adventurer(float(sx), float(sy), adv_class, entrance=(sx, sy))
        self.adventurers.append(adv)
        return adv

    def spawn_party(self) -> Party:
        """Spawn a new party. First member enters immediately, rest staggered."""
        size = random.randint(PARTY_SIZE_MIN, PARTY_SIZE_MAX)
        party = Party(_pending_spawns=size)
        self.parties.append(party)
        self._wave_count += 1
        return party

    def _spawn_party_member(self, party: Party) -> Adventurer | None:
        """Spawn the next member of a party."""
        adv = self.spawn_adventurer()
        if adv is not None:
            party.members.append(adv)
            party._pending_spawns -= 1
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

    def place_ladder(self, x: int, y: int) -> bool:
        """Place a ladder. Can go on empty or replace dirt."""
        if not self.grid.in_bounds(x, y):
            return False
        tile = self.grid.get(x, y)
        if tile not in (Tile.EMPTY, Tile.DIRT):
            return False
        self.grid.set(x, y, Tile.LADDER)
        self._invalidate_paths()
        return True

    def remove_ladder(self, x: int, y: int) -> bool:
        """Remove a ladder."""
        if not self.grid.in_bounds(x, y):
            return False
        if self.grid.get(x, y) != Tile.LADDER:
            return False
        self.grid.set(x, y, Tile.EMPTY)
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

    def place_mob(self, x: int, y: int) -> bool:
        """Place a slime on an empty floor tile."""
        if not self.grid.in_bounds(x, y):
            return False
        tile = self.grid.get(x, y)
        if tile not in (Tile.EMPTY, Tile.SPIKE):
            return False
        if not self.grid.is_solid(x, y - 1):
            return False
        mob = make_mob(float(x), float(y))
        self.mobs.append(mob)
        return True

    def remove_mob(self, x: int, y: int) -> bool:
        """Remove a mob at the given tile."""
        for mob in self.mobs:
            if mob.alive and mob.grid_x == x and mob.grid_y == y:
                self.mobs.remove(mob)
                return True
        return False

    def _invalidate_paths(self) -> None:
        for adv in self.adventurers:
            adv._path_dirty = True

    def update(self, dt: float) -> None:
        self.time_elapsed += dt
        self.vault.update(dt)

        # Staggered party member spawning
        for party in self.parties:
            if party._pending_spawns > 0:
                party._spawn_timer -= dt
                if party._spawn_timer <= 0:
                    self._spawn_party_member(party)
                    party._spawn_timer = SPAWN_STAGGER

        # Auto-spawn waves
        if self.auto_spawn:
            self._wave_timer -= dt
            if self._wave_timer <= 0:
                # Only spawn if no active parties (let current wave finish)
                if not any(p.active for p in self.parties):
                    self.spawn_party()
                    self._wave_timer = WAVE_COOLDOWN
                else:
                    # Check again soon
                    self._wave_timer = 1.0

        # Party dynamics — knowledge sharing and sympathy
        for party in self.parties:
            active_members = [a for a in party.members if a.alive and not a.reached_exit]
            fleeing_or_gone = sum(
                1 for a in party.members if a._returning or not a.alive or a.reached_exit
            )

            for i, a in enumerate(active_members):
                # Sympathy: each fleeing/dead/gone member drains greed over time
                if fleeing_or_gone > 0 and not a._returning:
                    drain = SYMPATHY_GREED_DRAIN * fleeing_or_gone * dt
                    old_greed = a._greed
                    a._greed = max(0.0, a._greed - drain)
                    if old_greed > 0 and a._greed <= 0:
                        a._path_dirty = True

                # Hazard sharing when close
                for b in active_members[i + 1:]:
                    dist = abs(a.x - b.x) + abs(a.y - b.y)
                    if dist <= PARTY_SHARE_RANGE:
                        shared = a._known_hazards | b._known_hazards
                        if shared != a._known_hazards:
                            a._known_hazards = shared
                            a._path_dirty = True
                        if shared != b._known_hazards:
                            b._known_hazards = shared
                            b._path_dirty = True

        # Update mobs
        for mob in self.mobs:
            update_mob(mob, self.grid, dt)

        # Combat engagement — mobs aggro nearby adventurers
        for mob in self.mobs:
            if not mob.alive or mob.in_combat:
                continue
            for adv in self.adventurers:
                if not adv.alive or adv.reached_exit:
                    continue
                dist = abs(adv.x - mob.x) + abs(adv.y - mob.y)
                if dist <= AGGRO_RANGE:
                    mob.engage(adv)
                    # Adventurer fights back (unless fleeing)
                    if not adv.in_combat and not adv._returning:
                        adv.engage(mob)
                    elif not adv.in_combat and adv._returning:
                        # Fleeing adventurer only fights if cornered (very close)
                        if dist <= 1.0:
                            adv.engage(mob)
                    break

        for adv in self.adventurers:
            mana_gained = update_adventurer(adv, self.grid, self.vault, dt)
            self.mana += mana_gained

    @property
    def active_adventurers(self) -> list[Adventurer]:
        return [a for a in self.adventurers if a.alive and not a.reached_exit]

    @property
    def active_mobs(self) -> list[Mob]:
        return [m for m in self.mobs if m.alive]

    @property
    def is_complete(self) -> bool:
        """True when all adventurers have either exited or died."""
        return len(self.adventurers) > 0 and len(self.active_adventurers) == 0


def new_game() -> GameState:
    """Create a fresh Room Slice game."""
    gs = GameState(grid=make_room_slice())
    gs.vault.items = 3  # start with some loot in the vault
    return gs
