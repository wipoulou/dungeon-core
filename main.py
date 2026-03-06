"""Dungeon Symbiosis - Room Slice Prototype"""

import pyray as rl

from dungeon.game_state import new_game
from dungeon.grid import Tile

# -- Constants --
SCREEN_W, SCREEN_H = 960, 600
TILE_SIZE = 32
HUD_HEIGHT = 40

TILE_COLORS = {
    Tile.DIRT: rl.Color(100, 70, 50, 255),
    Tile.SPAWN: rl.Color(50, 180, 80, 255),
    Tile.EXIT: rl.Color(50, 150, 220, 255),
    Tile.SPIKE: rl.Color(200, 40, 40, 255),
    Tile.CHEST: rl.Color(200, 170, 50, 255),
}
BG_COLOR = rl.Color(20, 20, 30, 255)
GRID_LINE_COLOR = rl.Color(255, 255, 255, 15)
ADV_COLOR = rl.Color(240, 220, 60, 255)
ADV_DEAD_COLOR = rl.Color(100, 100, 100, 255)
ADV_EXIT_COLOR = rl.Color(80, 220, 80, 255)
ADV_LOOTING_COLOR = rl.Color(200, 150, 255, 255)
ADV_DAMAGE_COLOR = rl.Color(255, 40, 40, 255)
PATH_COLOR = rl.Color(255, 255, 0, 40)
HOVER_DIG_COLOR = rl.Color(255, 100, 100, 80)
HOVER_PLACE_COLOR = rl.Color(100, 255, 100, 80)
CHEST_EMPTY_COLOR = rl.Color(120, 100, 40, 255)
FOG_COLOR = rl.Color(0, 0, 0, 160)

# Tools
TOOL_DIG = 0
TOOL_CHEST = 1
TOOL_SPIKE = 2
tool_names = ["Dig/Place", "Chest", "Spike"]

# -- Init --
rl.init_window(SCREEN_W, SCREEN_H, "Dungeon Symbiosis")
rl.set_target_fps(60)

gs = new_game()
grid = gs.grid
adv = gs.spawn_adventurer()
current_tool = TOOL_DIG

# Camera centered on grid
camera = rl.Camera2D()
camera.offset = rl.Vector2(SCREEN_W / 2, SCREEN_H / 2)
camera.target = rl.Vector2(
    grid.width * TILE_SIZE / 2,
    -(grid.height * TILE_SIZE) / 2,
)
camera.zoom = min(
    (SCREEN_W - 40) / (grid.width * TILE_SIZE),
    (SCREEN_H - HUD_HEIGHT - 40) / (grid.height * TILE_SIZE),
)

paused = False
show_fog = True


def world_pos(x: float, y: float) -> tuple[float, float]:
    return x * TILE_SIZE, -(y + 1) * TILE_SIZE


def world_rect(x: float, y: float, w: float = 1.0, h: float = 1.0) -> rl.Rectangle:
    wx, wy = world_pos(x, y + h - 1)
    return rl.Rectangle(wx, wy, int(w * TILE_SIZE), int(h * TILE_SIZE))


def screen_to_grid(screen_x: int, screen_y: int) -> tuple[int, int]:
    world = rl.get_screen_to_world_2d(rl.Vector2(screen_x, screen_y), camera)
    gx = int(world.x // TILE_SIZE)
    # y is flipped: world.y=0 is grid top, negative is up in grid coords
    gy = int((-world.y - 1) // TILE_SIZE)
    return gx, gy


while not rl.window_should_close():
    dt = rl.get_frame_time()

    # -- Input --
    if rl.is_key_pressed(rl.KeyboardKey.KEY_SPACE):
        paused = not paused

    if rl.is_key_pressed(rl.KeyboardKey.KEY_TAB):
        current_tool = (current_tool + 1) % len(tool_names)
    if rl.is_key_pressed(rl.KeyboardKey.KEY_ONE):
        current_tool = TOOL_DIG
    if rl.is_key_pressed(rl.KeyboardKey.KEY_TWO):
        current_tool = TOOL_CHEST
    if rl.is_key_pressed(rl.KeyboardKey.KEY_THREE):
        current_tool = TOOL_SPIKE
    if rl.is_key_pressed(rl.KeyboardKey.KEY_F):
        show_fog = not show_fog

    if not paused:
        gs.update(dt)

    # Zoom
    wheel = rl.get_mouse_wheel_move()
    if wheel != 0:
        camera.zoom = max(0.3, min(3.0, camera.zoom + wheel * 0.1))

    # Mouse -> grid
    mx, my = rl.get_mouse_x(), rl.get_mouse_y()
    hover_gx, hover_gy = screen_to_grid(mx, my)
    hover_in_bounds = grid.in_bounds(hover_gx, hover_gy)
    hover_tile = grid.get(hover_gx, hover_gy) if hover_in_bounds else None

    # Tool actions
    if my > HUD_HEIGHT:
        if current_tool == TOOL_DIG:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                if hover_tile == Tile.CHEST:
                    gs.remove_chest(hover_gx, hover_gy)
                else:
                    gs.dig(hover_gx, hover_gy)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.place(hover_gx, hover_gy)
        elif current_tool == TOOL_CHEST:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                gs.place_chest(hover_gx, hover_gy)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.remove_chest(hover_gx, hover_gy)
        elif current_tool == TOOL_SPIKE:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                gs.place_spike(hover_gx, hover_gy)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.remove_spike(hover_gx, hover_gy)

    # Respawn
    if rl.is_key_pressed(rl.KeyboardKey.KEY_R):
        adv = gs.spawn_adventurer()

    # -- Draw --
    rl.begin_drawing()
    rl.clear_background(BG_COLOR)
    rl.begin_mode_2d(camera)

    # Grid lines
    for x in range(grid.width + 1):
        px = x * TILE_SIZE
        rl.draw_line(px, 0, px, -grid.height * TILE_SIZE, GRID_LINE_COLOR)
    for y in range(grid.height + 1):
        py = -y * TILE_SIZE
        rl.draw_line(0, py, grid.width * TILE_SIZE, py, GRID_LINE_COLOR)

    # Tiles
    for y in range(grid.height):
        for x in range(grid.width):
            tile = grid.get(x, y)
            if tile == Tile.CHEST:
                chest = gs.vault.chests.get((x, y))
                c = TILE_COLORS[Tile.CHEST] if chest and chest.has_loot else CHEST_EMPTY_COLOR
            else:
                c = TILE_COLORS.get(tile)
            if c is None:
                continue
            r = world_rect(x, y)
            rl.draw_rectangle_rec(r, c)

    # Hover highlight
    if hover_in_bounds and my > HUD_HEIGHT:
        r = world_rect(hover_gx, hover_gy)
        if current_tool == TOOL_DIG:
            if hover_tile in (Tile.DIRT, Tile.CHEST):
                rl.draw_rectangle_rec(r, HOVER_DIG_COLOR)
            elif hover_tile == Tile.EMPTY:
                rl.draw_rectangle_rec(r, HOVER_PLACE_COLOR)
        elif current_tool == TOOL_CHEST:
            if hover_tile == Tile.EMPTY:
                rl.draw_rectangle_rec(r, rl.Color(200, 170, 50, 80))
        elif current_tool == TOOL_SPIKE:
            if hover_tile == Tile.EMPTY:
                rl.draw_rectangle_rec(r, rl.Color(200, 40, 40, 80))
            elif hover_tile == Tile.SPIKE:
                rl.draw_rectangle_rec(r, HOVER_DIG_COLOR)

    # Fog of war — dim tiles no adventurer has seen
    if show_fog:
        all_seen: set[tuple[int, int]] = set()
        for a in gs.adventurers:
            all_seen |= a._seen
        for y in range(grid.height):
            for x in range(grid.width):
                if (x, y) not in all_seen:
                    r = world_rect(x, y)
                    rl.draw_rectangle_rec(r, FOG_COLOR)

    # Adventurer paths
    for a in gs.active_adventurers:
        if a._path:
            for px, py in a._path:
                r = world_rect(px, py)
                rl.draw_rectangle_rec(r, PATH_COLOR)

    # Adventurers
    for a in gs.adventurers:
        if a.alive:
            if a._damage_flash > 0:
                c = ADV_DAMAGE_COLOR
            elif a.looting:
                c = ADV_LOOTING_COLOR
            elif a.reached_exit:
                c = ADV_EXIT_COLOR
            else:
                c = ADV_COLOR
        else:
            c = ADV_DEAD_COLOR
        ax, ay = world_pos(a.x, a.y)
        rl.draw_rectangle(
            int(ax), int(ay - 0.8 * TILE_SIZE),
            int(0.6 * TILE_SIZE), int(1.8 * TILE_SIZE), c,
        )
        # HP bar
        if a.alive and a.hp < a.max_hp:
            bar_w = int(0.8 * TILE_SIZE)
            bar_h = 3
            bar_x = int(ax - 0.1 * TILE_SIZE)
            bar_y = int(ay - 1.0 * TILE_SIZE)
            hp_frac = a.hp / a.max_hp
            rl.draw_rectangle(bar_x, bar_y, bar_w, bar_h, rl.Color(40, 40, 40, 200))
            bar_color = rl.GREEN if hp_frac > 0.5 else rl.YELLOW if hp_frac > 0.25 else rl.RED
            rl.draw_rectangle(bar_x, bar_y, int(bar_w * hp_frac), bar_h, bar_color)

    rl.end_mode_2d()

    # HUD
    rl.draw_rectangle(0, 0, SCREEN_W, HUD_HEIGHT, rl.Color(0, 0, 0, 200))
    rl.draw_text(f"Mana: {gs.mana}", 10, 10, 20, rl.SKYBLUE)
    rl.draw_text(f"Vault: {gs.vault.items}", 130, 10, 20, rl.GOLD)

    active = gs.active_adventurers
    rl.draw_text(f"Adventurers: {len(active)}", 260, 10, 20, rl.WHITE)

    # Tool indicator
    tool_text = f"[{current_tool + 1}] {tool_names[current_tool]}"
    rl.draw_text(tool_text, 440, 10, 20, rl.ORANGE)

    status = "PAUSED" if paused else "RUNNING"
    rl.draw_text(status, SCREEN_W - 120, 10, 20, rl.YELLOW if paused else rl.GREEN)

    if gs.is_complete and len(gs.adventurers) > 0:
        rl.draw_text("[R] Spawn", SCREEN_W - 260, 10, 20, rl.WHITE)

    # Debug: grid coords under mouse
    if hover_in_bounds:
        tile_name = hover_tile.value if hover_tile else "?"
        rl.draw_text(
            f"({hover_gx},{hover_gy}) {tile_name}",
            SCREEN_W - 200, SCREEN_H - 25, 16, rl.WHITE,
        )

    # Controls
    rl.draw_text(
        "LMB/RMB: Tool | 1-3: Tool | Scroll: Zoom | Space: Pause | F: Fog | R: Spawn",
        10, SCREEN_H - 25, 16, rl.Color(180, 180, 180, 255),
    )

    rl.end_drawing()

rl.close_window()
