// Adventurer classes and traits registry

export const ClassRegistry = new Map();
export const TraitRegistry = new Map();

export function defineClass(id, def) {
  ClassRegistry.set(id, { id, ...def });
}
export function defineTrait(id, def) {
  TraitRegistry.set(id, { id, ...def });
}

export function pickRandomFrom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function makeMember(level = 1) {
  const cls = pickRandomFrom([...ClassRegistry.keys()]);
  const trait = pickRandomFrom([...TraitRegistry.keys()]);
  const base = ClassRegistry.get(cls);
  const scale = 1 + (level - 1) * 0.25;
  const maxhp = Math.round(base.baseHp * scale);
  const mp = Math.round(base.baseMp * scale);
  return {
    hp: maxhp,
    maxhp,
    mp,
    cls,
    trait,
    level,
    x: 1,
    y: 0, // caller should set y
    loot: 0,
    bleeding: 0,
  };
}

// Defaults
defineClass("warrior", { label: "Warrior", baseHp: 60, baseMp: 5 });
defineClass("ranger", { label: "Ranger", baseHp: 40, baseMp: 15 });
defineClass("assassin", { label: "Assassin", baseHp: 35, baseMp: 20 });
defineClass("mage", { label: "Mage", baseHp: 28, baseMp: 40 });
defineClass("healer", { label: "Healer", baseHp: 32, baseMp: 35 });
defineClass("bard", { label: "Bard", baseHp: 30, baseMp: 25 });
defineClass("engineer", { label: "Engineer", baseHp: 36, baseMp: 20 });

// Traits
defineTrait("Mana Sink", { label: "Mana Sink" });
defineTrait("Trap Enthusiast", { label: "Trap Enthusiast" });
defineTrait("Show-off", { label: "Show-off" });
defineTrait("Efficient Caster", { label: "Efficient Caster" });
