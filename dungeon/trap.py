"""Traps and projectiles — dungeon hazards that fire or trigger."""

from __future__ import annotations

from dataclasses import dataclass, field

from dungeon.grid import Grid, Tile, ARROW_TRAP_TILES


# Bear trap
BEAR_TRAP_DAMAGE = 25
BEAR_TRAP_HOLD_TIME = 2.5  # seconds adventurer is stuck
BEAR_TRAP_REARM_TIME = 8.0  # seconds before trap resets

# Arrow trap
ARROW_TRAP_INTERVAL = 3.0  # seconds between shots
ARROW_SPEED = 12.0  # tiles per second
ARROW_DAMAGE = 20
ARROW_MAX_RANGE = 15  # tiles before despawn


@dataclass
class Projectile:
    x: float
    y: float
    vx: float  # tiles/sec
    vy: float = 0.0
    damage: int = ARROW_DAMAGE
    alive: bool = True
    _travelled: float = 0.0


@dataclass
class TrapState:
    """Tracks state of individual trap tiles."""
    # Bear traps: {(x,y): rearm_timer} — 0 = armed, >0 = sprung
    bear_traps: dict[tuple[int, int], float] = field(default_factory=dict)
    # Arrow traps: {(x,y): cooldown_timer}
    arrow_traps: dict[tuple[int, int], float] = field(default_factory=dict)
    # Active projectiles
    projectiles: list[Projectile] = field(default_factory=list)

    def register_traps(self, grid: Grid) -> None:
        """Scan grid and register all trap tiles."""
        for y in range(grid.height):
            for x in range(grid.width):
                tile = grid.get(x, y)
                if tile == Tile.BEAR_TRAP and (x, y) not in self.bear_traps:
                    self.bear_traps[(x, y)] = 0.0  # armed
                if tile in ARROW_TRAP_TILES and (x, y) not in self.arrow_traps:
                    self.arrow_traps[(x, y)] = ARROW_TRAP_INTERVAL * 0.5  # stagger first shot

    def unregister(self, x: int, y: int) -> None:
        """Remove trap state when a trap tile is removed."""
        self.bear_traps.pop((x, y), None)
        self.arrow_traps.pop((x, y), None)


def update_traps(state: TrapState, grid: Grid, dt: float) -> None:
    """Update trap timers and fire projectiles."""
    # Bear trap rearm timers
    for pos in list(state.bear_traps):
        if state.bear_traps[pos] > 0:
            state.bear_traps[pos] = max(0.0, state.bear_traps[pos] - dt)

    # Arrow trap firing
    for pos, timer in list(state.arrow_traps.items()):
        new_timer = timer - dt
        if new_timer <= 0:
            # Fire!
            tile = grid.get(*pos)
            if tile == Tile.ARROW_TRAP_L:
                vx = -ARROW_SPEED
            elif tile == Tile.ARROW_TRAP_R:
                vx = ARROW_SPEED
            else:
                # Trap tile was removed
                continue
            # Spawn arrow at the trap position, offset into the open space
            ax = pos[0] + (0.5 if vx > 0 else -0.5)
            ay = pos[1]
            state.projectiles.append(Projectile(x=ax, y=float(ay), vx=vx))
            new_timer = ARROW_TRAP_INTERVAL
        state.arrow_traps[pos] = new_timer

    # Update projectiles
    for proj in state.projectiles:
        if not proj.alive:
            continue
        proj.x += proj.vx * dt
        proj.y += proj.vy * dt
        proj._travelled += abs(proj.vx * dt)
        # Hit wall?
        if grid.is_solid(int(proj.x), int(proj.y)):
            proj.alive = False
        # Max range?
        if proj._travelled >= ARROW_MAX_RANGE:
            proj.alive = False

    # Clean up dead projectiles
    state.projectiles = [p for p in state.projectiles if p.alive]
