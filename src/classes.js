// Adventurer classes and traits registry

export const ClassRegistry = new Map();
export const TraitRegistry = new Map();
export const ClassSkills = new Map(); // id -> [{ name, type, min, max, cost }]

export function defineClass(id, def) {
    ClassRegistry.set(id, { id, ...def });
}
export function defineClassSkills(id, skills) {
    ClassSkills.set(id, skills);
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
        loot: 0,
        bleeding: 0,
    };
}

export function getClassSkills(id) {
    return ClassSkills.get(id) || [];
}

// Defaults
defineClass("warrior", { label: "Warrior", baseHp: 60, baseMp: 5 });
defineClassSkills("warrior", [
    { name: "Slash", type: "phys", min: 6, max: 10, cost: 0 },
    { name: "Cleave", type: "phys", min: 9, max: 14, cost: 2 },
]);

defineClass("ranger", { label: "Ranger", baseHp: 40, baseMp: 15 });
defineClassSkills("ranger", [
    { name: "Arrow Shot", type: "phys", min: 5, max: 9, cost: 0 },
    { name: "Power Shot", type: "phys", min: 8, max: 12, cost: 3 },
]);

defineClass("assassin", { label: "Assassin", baseHp: 35, baseMp: 20 });
defineClassSkills("assassin", [
    { name: "Stab", type: "phys", min: 5, max: 9, cost: 0 },
    { name: "Backstab", type: "phys", min: 10, max: 16, cost: 4 },
]);

defineClass("mage", { label: "Mage", baseHp: 28, baseMp: 40 });
defineClassSkills("mage", [
    { name: "Magic Bolt", type: "magic", min: 7, max: 12, cost: 3 },
    { name: "Fireball", type: "magic", min: 10, max: 16, cost: 5 },
]);

defineClass("healer", { label: "Healer", baseHp: 32, baseMp: 35 });
defineClassSkills("healer", [
    { name: "Smite", type: "magic", min: 4, max: 7, cost: 2 },
    { name: "Heal", type: "heal", min: 8, max: 14, cost: 4 },
]);

defineClass("bard", { label: "Bard", baseHp: 30, baseMp: 25 });
defineClassSkills("bard", [
    { name: "Taunt", type: "buff", min: 0, max: 0, cost: 2 },
    { name: "Lute Bash", type: "phys", min: 3, max: 6, cost: 0 },
]);

defineClass("engineer", { label: "Engineer", baseHp: 36, baseMp: 20 });
defineClassSkills("engineer", [
    { name: "Wrench Whack", type: "phys", min: 4, max: 8, cost: 0 },
    { name: "Shock Prod", type: "magic", min: 7, max: 11, cost: 3 },
]);

// Traits
defineTrait("Mana Sink", { label: "Mana Sink" });
defineTrait("Trap Enthusiast", { label: "Trap Enthusiast" });
defineTrait("Show-off", { label: "Show-off" });
defineTrait("Efficient Caster", { label: "Efficient Caster" });
