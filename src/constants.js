// Shared constants and tile types

export const GRID_W = 24;
export const GRID_H = 16;
export const TILE = 32;

export const STARTING_MANA = 100;
export const COSTS = { room: 5, mob: 15, trap: 20, loot: 10 };
export const SPAWN_RATE = 16;
export const MAX_ADVENTURERS = 6;
export const POLITICAL_RAID_THRESHOLD = 100;
export const ECON_RAID_THRESHOLD = 100;

export const STORAGE_KEY = "dc_regular_memory_v1";

export const T = {
  WALL: 0,
  ROOM: 1,
  MOB: 2,
  TRAP: 3,
  LOOT: 4,
  ENTRANCE: 5,
  EXIT: 6,
};

export function inBounds(x, y) {
  return x >= 0 && y >= 0 && x < GRID_W && y < GRID_H;
}

export function isWalkableType(t) {
  return (
    t === T.ROOM ||
    t === T.MOB ||
    t === T.TRAP ||
    t === T.LOOT ||
    t === T.ENTRANCE ||
    t === T.EXIT
  );
}
