// Trap registry and helpers
// Supports typed traps with per-type behavior and costs.

export const TrapRegistry = new Map();

// Schema: {
//   id: string,
//   name: string,
//   color: string,
//   triggerChance: number, // 0..1
//   hitChance: number,     // 0..1
//   minDmg: number,
//   maxDmg: number,
//   rearm: number,         // ticks to rearm after triggering
//   cost?: number          // mana cost to place
// }

export function defineTrap(def) {
  if (!def?.id) throw new Error("Trap def requires id");
  TrapRegistry.set(def.id, def);
}

export function getTrap(id) { return TrapRegistry.get(id); }
export function listTraps() { return [...TrapRegistry.values()]; }

// Defaults
defineTrap({ id: "spike", name: "Spike Trap", color: "#ff5a47", triggerChance: 0.40, hitChance: 0.90, minDmg: 6, maxDmg: 12, rearm: 6, cost: 18 });
defineTrap({ id: "dart", name: "Dart Launcher", color: "#ffd447", triggerChance: 0.35, hitChance: 0.80, minDmg: 8, maxDmg: 14, rearm: 8, cost: 22 });
defineTrap({ id: "snare", name: "Snare", color: "#c58d3d", triggerChance: 0.50, hitChance: 0.75, minDmg: 4, maxDmg: 9, rearm: 5, cost: 15 });
