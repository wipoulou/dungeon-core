"""Dungeon Symbiosis - Room Slice Prototype"""

import pyray as rl

from dungeon.adventurer import AdventurerClass
from dungeon.game_state import new_game
from dungeon.grid import Tile
from dungeon.log import clear as log_clear, dump as log_dump
from dungeon.mob import MobType

# -- Constants --
SCREEN_W, SCREEN_H = 960, 600
TILE_SIZE = 32
HUD_HEIGHT = 40

TILE_COLORS = {
    Tile.DIRT: rl.Color(100, 70, 50, 255),
    Tile.ENTRANCE: rl.Color(50, 180, 120, 255),
    Tile.SPIKE: rl.Color(200, 40, 40, 255),
    Tile.CHEST: rl.Color(200, 170, 50, 255),
    Tile.LADDER: rl.Color(160, 120, 60, 255),
    Tile.BEAR_TRAP: rl.Color(180, 140, 60, 255),
    Tile.ARROW_TRAP_L: rl.Color(140, 140, 160, 255),
    Tile.ARROW_TRAP_R: rl.Color(140, 140, 160, 255),
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

MOB_COLOR = rl.Color(60, 180, 60, 255)
MOB_DAMAGE_COLOR = rl.Color(255, 255, 255, 255)
MOB_DEAD_COLOR = rl.Color(40, 80, 40, 120)
PROJECTILE_COLOR = rl.Color(255, 200, 50, 255)

# -- Sprite tile IDs (Kenney Tiny Dungeon) --
SPRITE_DIR = "kenney_tiny-dungeon/Tiles"
SPRITE_MAP = {
    "dirt0": "tile_0000",
    "dirt1": "tile_0001",
    "dirt2": "tile_0012",
    "entrance": "tile_0063",
    "chest_full": "tile_0066",
    "chest_empty": "tile_0064",
    "ladder": "tile_0075",
    "warrior": "tile_0087",
    "rogue": "tile_0088",
    "mage": "tile_0084",
    "healer": "tile_0099",
    "slime": "tile_0108",
    "skeleton": "tile_0100",
    "bat": "tile_0121",
    "arrow_trap": "tile_0071",
    "bear_trap": "tile_0069",
}

ADV_CLASS_SPRITES = {
    AdventurerClass.WARRIOR: "warrior",
    AdventurerClass.ROGUE: "rogue",
    AdventurerClass.MAGE: "mage",
    AdventurerClass.HEALER: "healer",
}

MOB_SPRITES = {
    MobType.SLIME: "slime",
    MobType.BAT: "bat",
    MobType.SKELETON: "skeleton",
}

# Tools
TOOL_DIG = 0
TOOL_CHEST = 1
TOOL_SPIKE = 2
TOOL_LADDER = 3
TOOL_SLIME = 4
TOOL_BEAR_TRAP = 5
TOOL_ARROW_TRAP = 6
TOOL_BAT = 7
TOOL_SKELETON = 8
tool_names = ["Dig/Place", "Chest", "Spike", "Ladder", "Slime", "BearTrap", "ArrowTrap", "Bat", "Skeleton"]

# -- Init --
rl.init_window(SCREEN_W, SCREEN_H, "Dungeon Symbiosis")
rl.set_target_fps(60)

gs = new_game()
gs.auto_spawn = True
grid = gs.grid
current_tool = TOOL_DIG

# Load sprite textures
sprites: dict[str, rl.Texture2D] = {}
for name, tile_id in SPRITE_MAP.items():
    path = f"{SPRITE_DIR}/{tile_id}.png"
    sprites[name] = rl.load_texture(path)
    rl.set_texture_filter(sprites[name], rl.TextureFilter.TEXTURE_FILTER_POINT)

# Precompute source rect for all sprites (full 16x16 tile)
SPRITE_SRC = rl.Rectangle(0, 0, 16, 16)
SPRITE_SRC_FLIP = rl.Rectangle(0, 0, -16, 16)  # horizontally flipped

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


def draw_sprite(name: str, wx: float, wy: float, w: float = TILE_SIZE, h: float = TILE_SIZE,
                 tint: rl.Color = rl.WHITE, flip: bool = False):
    tex = sprites.get(name)
    if tex is None:
        return
    src = SPRITE_SRC_FLIP if flip else SPRITE_SRC
    dest = rl.Rectangle(wx, wy, w, h)
    rl.draw_texture_pro(tex, src, dest, rl.Vector2(0, 0), 0.0, tint)


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
    if rl.is_key_pressed(rl.KeyboardKey.KEY_FOUR):
        current_tool = TOOL_LADDER
    if rl.is_key_pressed(rl.KeyboardKey.KEY_FIVE):
        current_tool = TOOL_SLIME
    if rl.is_key_pressed(rl.KeyboardKey.KEY_SIX):
        current_tool = TOOL_BEAR_TRAP
    if rl.is_key_pressed(rl.KeyboardKey.KEY_SEVEN):
        current_tool = TOOL_ARROW_TRAP
    if rl.is_key_pressed(rl.KeyboardKey.KEY_EIGHT):
        current_tool = TOOL_BAT
    if rl.is_key_pressed(rl.KeyboardKey.KEY_NINE):
        current_tool = TOOL_SKELETON
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
        elif current_tool == TOOL_LADDER:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                gs.place_ladder(hover_gx, hover_gy)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.remove_ladder(hover_gx, hover_gy)
        elif current_tool == TOOL_SLIME:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                gs.place_mob(hover_gx, hover_gy, MobType.SLIME)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.remove_mob(hover_gx, hover_gy)
        elif current_tool == TOOL_BEAR_TRAP:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                gs.place_bear_trap(hover_gx, hover_gy)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.remove_bear_trap(hover_gx, hover_gy)
        elif current_tool == TOOL_ARROW_TRAP:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                gs.place_arrow_trap(hover_gx, hover_gy)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.remove_arrow_trap(hover_gx, hover_gy)
        elif current_tool == TOOL_BAT:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                gs.place_mob(hover_gx, hover_gy, MobType.BAT)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.remove_mob(hover_gx, hover_gy)
        elif current_tool == TOOL_SKELETON:
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
                gs.place_mob(hover_gx, hover_gy, MobType.SKELETON)
            if rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_RIGHT):
                gs.remove_mob(hover_gx, hover_gy)

    # Manual spawn party
    if rl.is_key_pressed(rl.KeyboardKey.KEY_R):
        log_dump()
        log_clear()
        gs.spawn_party()

    # Toggle auto-spawn
    if rl.is_key_pressed(rl.KeyboardKey.KEY_A):
        gs.auto_spawn = not gs.auto_spawn

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
            wx, wy = world_pos(x, y)
            if tile == Tile.DIRT:
                variant = hash((x, y)) % 3
                draw_sprite(f"dirt{variant}", wx, wy)
            elif tile == Tile.ENTRANCE:
                draw_sprite("entrance", wx, wy)
            elif tile == Tile.CHEST:
                chest = gs.vault.chests.get((x, y))
                sprite = "chest_full" if chest and chest.has_loot else "chest_empty"
                draw_sprite(sprite, wx, wy)
            elif tile == Tile.LADDER:
                draw_sprite("ladder", wx, wy)
            elif tile == Tile.SPIKE:
                # Spikes are short — only 0.1 tile height, sitting on the floor
                spike_h = int(0.1 * TILE_SIZE)
                c = TILE_COLORS[Tile.SPIKE]
                rl.draw_rectangle(int(wx), int(wy - spike_h + TILE_SIZE), TILE_SIZE, spike_h, c)
            elif tile == Tile.BEAR_TRAP:
                # Bear trap — jaw shape on the floor
                bt_timer = gs.trap_state.bear_traps.get((x, y), 0.0)
                if bt_timer == 0.0:
                    # Armed — bright
                    draw_sprite("bear_trap", wx, wy)
                else:
                    # Sprung — dim
                    draw_sprite("bear_trap", wx, wy, tint=rl.Color(100, 100, 100, 180))
            elif tile in (Tile.ARROW_TRAP_L, Tile.ARROW_TRAP_R):
                flip = tile == Tile.ARROW_TRAP_R
                draw_sprite("arrow_trap", wx, wy, flip=flip)

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
        elif current_tool == TOOL_LADDER:
            if hover_tile in (Tile.EMPTY, Tile.DIRT):
                rl.draw_rectangle_rec(r, rl.Color(160, 120, 60, 80))
            elif hover_tile == Tile.LADDER:
                rl.draw_rectangle_rec(r, HOVER_DIG_COLOR)
        elif current_tool == TOOL_SLIME:
            if hover_tile in (Tile.EMPTY, Tile.SPIKE):
                rl.draw_rectangle_rec(r, rl.Color(60, 180, 60, 80))
        elif current_tool == TOOL_BEAR_TRAP:
            if hover_tile == Tile.EMPTY:
                rl.draw_rectangle_rec(r, rl.Color(180, 140, 60, 80))
            elif hover_tile == Tile.BEAR_TRAP:
                rl.draw_rectangle_rec(r, HOVER_DIG_COLOR)
        elif current_tool == TOOL_ARROW_TRAP:
            if hover_tile == Tile.EMPTY:
                rl.draw_rectangle_rec(r, rl.Color(140, 140, 160, 80))
            elif hover_tile in (Tile.ARROW_TRAP_L, Tile.ARROW_TRAP_R):
                rl.draw_rectangle_rec(r, HOVER_DIG_COLOR)
        elif current_tool in (TOOL_BAT, TOOL_SKELETON):
            if hover_tile in (Tile.EMPTY, Tile.SPIKE):
                rl.draw_rectangle_rec(r, rl.Color(60, 180, 60, 80))

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
        sprite_name = ADV_CLASS_SPRITES.get(a.adv_class, "warrior")
        ax, ay = world_pos(a.x, a.y)
        # Chunky dwarf-style sprites
        sw = int(TILE_SIZE * 1.2)
        sh = int(TILE_SIZE * 1.2)
        sx = ax - (sw - TILE_SIZE) / 2
        sy = ay - (sh - TILE_SIZE) * 0.7
        # Determine facing: flip sprite when moving left
        facing_left = hasattr(a, '_path') and a._path and a._path_index < len(a._path) and a._path[a._path_index][0] < a.x
        if a.alive:
            if a._damage_flash > 0:
                tint = rl.Color(255, 80, 80, 255)
            elif a.looting:
                tint = rl.Color(200, 150, 255, 255)
            elif a.reached_exit:
                tint = rl.Color(80, 255, 80, 255)
            else:
                tint = rl.WHITE
        else:
            tint = rl.Color(100, 100, 100, 150)
        draw_sprite(sprite_name, sx, sy, sw, sh, tint=tint, flip=facing_left)
        # HP bar
        if a.alive and a.hp < a.max_hp:
            bar_w = int(0.8 * TILE_SIZE)
            bar_h = 3
            bar_x = int(ax - 0.1 * TILE_SIZE)
            bar_y = int(sy - 4)
            hp_frac = a.hp / a.max_hp
            rl.draw_rectangle(bar_x, bar_y, bar_w, bar_h, rl.Color(40, 40, 40, 200))
            bar_color = rl.GREEN if hp_frac > 0.5 else rl.YELLOW if hp_frac > 0.25 else rl.RED
            rl.draw_rectangle(bar_x, bar_y, int(bar_w * hp_frac), bar_h, bar_color)

    # Mobs
    for m in gs.mobs:
        sprite_name = MOB_SPRITES.get(m.mob_type, "slime")
        mx_w, my_w = world_pos(m.x, m.y)
        sw = int(TILE_SIZE * 0.9)
        sh = int(TILE_SIZE * 0.9)
        sx = mx_w + (TILE_SIZE - sw) / 2
        sy = my_w + (TILE_SIZE - sh)
        facing_left = m.direction < 0
        if m.alive:
            tint = rl.Color(255, 200, 200, 255) if m._damage_flash > 0 else rl.WHITE
        else:
            tint = rl.Color(100, 100, 100, 120)
        draw_sprite(sprite_name, sx, sy, sw, sh, tint=tint, flip=facing_left)
        # HP bar (alive) or respawn loading bar (dead)
        bar_w = int(0.8 * TILE_SIZE)
        bar_h = 3
        bar_x = int(mx_w)
        bar_y = int(sy - 4)
        if m.alive and m.hp < m.max_hp:
            hp_frac = m.hp / m.max_hp
            rl.draw_rectangle(bar_x, bar_y, bar_w, bar_h, rl.Color(40, 40, 40, 200))
            bar_color = rl.GREEN if hp_frac > 0.5 else rl.YELLOW if hp_frac > 0.25 else rl.RED
            rl.draw_rectangle(bar_x, bar_y, int(bar_w * hp_frac), bar_h, bar_color)
        elif not m.alive and m._respawn_timer > 0:
            frac = m.respawn_progress
            rl.draw_rectangle(bar_x, bar_y, bar_w, bar_h, rl.Color(40, 40, 40, 200))
            rl.draw_rectangle(bar_x, bar_y, int(bar_w * frac), bar_h, rl.Color(100, 100, 255, 200))

    # Projectiles (arrows)
    for proj in gs.trap_state.projectiles:
        if not proj.alive:
            continue
        px_w, py_w = world_pos(proj.x, proj.y)
        arrow_w = int(TILE_SIZE * 0.4)
        arrow_h = int(TILE_SIZE * 0.15)
        ax = int(px_w + (TILE_SIZE - arrow_w) / 2)
        ay = int(py_w + (TILE_SIZE - arrow_h) / 2)
        rl.draw_rectangle(ax, ay, arrow_w, arrow_h, PROJECTILE_COLOR)

    rl.end_mode_2d()

    # HUD
    rl.draw_rectangle(0, 0, SCREEN_W, HUD_HEIGHT, rl.Color(0, 0, 0, 200))
    rl.draw_text(f"Mana: {gs.mana}", 10, 10, 20, rl.SKYBLUE)
    rl.draw_text(f"Vault: {gs.vault.items}", 130, 10, 20, rl.GOLD)

    active = gs.active_adventurers
    rl.draw_text(f"Adv: {len(active)}", 260, 10, 20, rl.WHITE)
    rl.draw_text(f"Wave: {gs._wave_count}", 350, 10, 20, rl.WHITE)

    # Tool indicator
    tool_text = f"[{current_tool + 1}] {tool_names[current_tool]}"
    rl.draw_text(tool_text, 440, 10, 20, rl.ORANGE)

    status = "PAUSED" if paused else "RUNNING"
    rl.draw_text(status, SCREEN_W - 120, 10, 20, rl.YELLOW if paused else rl.GREEN)

    auto_text = "Auto:ON" if gs.auto_spawn else "Auto:OFF"
    auto_color = rl.GREEN if gs.auto_spawn else rl.GRAY
    rl.draw_text(auto_text, SCREEN_W - 260, 10, 20, auto_color)

    # Debug: grid coords under mouse
    if hover_in_bounds:
        tile_name = hover_tile.value if hover_tile else "?"
        rl.draw_text(
            f"({hover_gx},{hover_gy}) {tile_name}",
            SCREEN_W - 200, SCREEN_H - 25, 16, rl.WHITE,
        )

    # Controls
    rl.draw_text(
        "LMB/RMB: Tool | 1-9/Tab: Tool | Scroll: Zoom | Space: Pause | F: Fog | R: Spawn | A: Auto",
        10, SCREEN_H - 25, 16, rl.Color(180, 180, 180, 255),
    )

    rl.end_drawing()

log_dump()
for tex in sprites.values():
    rl.unload_texture(tex)
rl.close_window()
