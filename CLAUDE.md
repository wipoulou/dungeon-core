# Dungeon Symbiosis

## Project
- Game: "Dungeon Tycoon" - you ARE the dungeon, farming mana from adventurers
- Renderer: raylib (pyray) — thin visual layer
- Style: 2D side-view "ant farm" (like Terraria/Fallout Shelter)

## Architecture
- `dungeon/` - Pure game logic (no rendering). Fully testable.
  - `grid.py` - Tile-based dungeon grid
  - `adventurer.py` - Adventurer entity + physics/AI update
  - `game_state.py` - Ties grid + adventurers + mana together
- `main.py` - raylib renderer (thin visual layer)
- `tests/` - pytest tests for game logic

## Commands
- `uv run python main.py` - Run the game
- `uv run python dev.py` - Run with auto-restart on code changes
- `uv run pytest -v` - Run tests
- `uv run ruff check .` - Lint
- `uv run ruff format .` - Format

## Conventions
- Game logic must stay independent of rendering (no pyray imports in `dungeon/`)
- Tests cover game logic only (no GPU/window needed)
- uv for deps, ruff for linting, pytest for tests
