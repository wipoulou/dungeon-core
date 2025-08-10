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
//   attacks?: Array<{ name: string, min: number, max: number }>
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
defineMob({ id: "slime", name: "Slime", color: "#47ff88", maxHp: 20, regen: 1, attacks: [{ name: "Pseudopod", min: 3, max: 6 }] });
defineMob({ id: "goblin", name: "Goblin", color: "#8cff47", maxHp: 28, regen: 0, attacks: [{ name: "Slash", min: 4, max: 8 }, { name: "Stab", min: 5, max: 9 }] });
defineMob({ id: "sentry", name: "Sentry", color: "#47c6ff", maxHp: 16, regen: 2, attacks: [{ name: "Zap", min: 3, max: 7 }] });
