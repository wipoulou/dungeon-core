# Main Decisions

This file tracks major design and implementation decisions for the Dungeon Core project.

## 2025-08-10: Modularization for mobs and classes

- Switched to ES modules. `index.html` now loads `main.js` as `type="module"`.
- Added `src/constants.js` for shared constants and tile helpers.
- Added `src/mobs.js` with a MobRegistry and a few default mob types (slime, goblin, sentry).
- Added `src/classes.js` with registries for classes/traits and a `makeMember(level)` helper.
- `main.js` refactored to place typed mobs and to generate party members via the class registry.
- Mob tiles now track type and HP per tile; regen respects mob type.

Next: add UI to choose mob type to place; expose hooks for class/trait abilities in interactions.

## 2025-08-10: Persist Regular party rosters

- Extended Regulars memory to save a lightweight party roster template: each member's level, class, and trait.
- When a Regular party re-enters later, they respawn with the same roster, fully healed (HP) and with fresh MP.
- Memory format in localStorage now includes `members` array per party id. Backward compatible: absence of `members` falls back to random generation.
- Party Inspector shows a "Saved roster" summary when viewing a memory-only party.
