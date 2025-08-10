// Mob registry and helpers
// A minimal system to support different mob types with stats and regen.

export const MobRegistry = new Map();

// Schema: {
//   id: string,
//   name: string,
//   color: string, // dot color
//   maxHp: number,
//   regen: number,
//   onHit?: (ctx) => void, // optional hooks later
// }

export function defineMob(def) {
    if (!def?.id) throw new Error("Mob def requires id");
    MobRegistry.set(def.id, def);
}

export function getMob(id) {
    return MobRegistry.get(id);
}

export function listMobs() {
    return [...MobRegistry.values()];
}

// Default/base mobs
defineMob({ id: "slime", name: "Slime", color: "#47ff88", maxHp: 20, regen: 1 });
defineMob({ id: "goblin", name: "Goblin", color: "#8cff47", maxHp: 28, regen: 0 });
defineMob({ id: "sentry", name: "Sentry", color: "#47c6ff", maxHp: 16, regen: 2 });
