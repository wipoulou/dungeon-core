# Dungeon Symbiosis — Game Design Document

---

## 1. Core Philosophy

**You are the Dungeon.** Mana is the cost of everything — placing traps, stocking
chests, maintaining mobs, digging rooms. The only way to replenish it is to lure
adventurers in and extract it from their exertion.

Adventurers are not prey. They are gig workers exchanging physical exertion for
your fabricated rewards. A dead adventurer pays once. A regular adventurer pays
weekly.

**The Golden Rule:** Build a treadmill, not a deathtrap.

### The Economy of Exertion

```
Mana Income = (Damage Taken × 0.5) + (Stamina Spent) + (Spell Mana Cost × cut%) + (Emotional Spikes)
```

- Low yield: instantly killing a Level 1 adventurer
- High yield: terrifying a Level 50 Healer into casting Mass Resurrection
- The Healer is the most valuable entity in any party — they keep the party
  alive (more exertion) AND their spells feed you directly. Never kill the Healer.

### The Dungeon Core

The dungeon has a physical Core somewhere in its depths. If a party reaches and
removes the Core, the dungeon dies. This is the only real lose condition.

Normal adventurers don't come for the Core — they come for loot. But the world
has hostile factions (dark guilds, rival dungeons, inquisitors) who do. These are
crisis events, not the daily threat.

---

## 2. Visuals

### The Ant Farm

2D side-view cross-section, like Terraria or Fallout Shelter.

```
[ Town Skyline — Guild, Smithy, Tavern, visible from surface ]
────────────────────────────────────────────────────────────── ground
[ Layer 1: Dirt/Wood — Tutorial zone ]
[ Layer 2: Stone/Iron — Mid-game ]
[ Layer 3: Magma/Void — End-game ]
```

The town is visible at the top of the screen. Buildings appear and grow as the
dungeon's economy supports them. The dungeon master sees village progress without
leaving the main view — it's the skyline above their work.

### Grid Scale

- 1 block = master unit (currently 32px)
- Adventurer size: ~0.6 blocks wide, ~1.8 blocks tall
- Jump: 1 block high, 1 block wide gap (scout class: 1.5 high / 2 wide)

### UI

- Cursor: "Hand of God" — dig, place, link
- HUD: Mana pool, Heat/Rumor meter, Stockpile counters
- Entity debug overlay (toggleable): current state, cost map, buffs, knowledge boundary

---

## 3. Adventurers

### Classes

Parties of 3–4. Each class has a distinct role and mana generation profile:

| Class | Role | Primary Mana Source |
|-------|------|---------------------|
| Warrior | Tank — high HP/armor, blocks damage | Physical exertion, blocking |
| Rogue | DPS — fast, high attack speed | Skill usage, stamina drain |
| Mage | DPS — ranged, spell-based | Spell mana cost (cut goes to dungeon) |
| Healer | Support — keeps party alive | Healing spell cost (highest mana value per cast) |

### Party Types

**Locals (Regulars):**
- Live in the nearby town, have families and reputations
- Town cares deeply if they die — each death is a real reputation hit
- Steady predictable income; you know their capabilities over time
- Level up with repeated runs; become harder to challenge but generate more mana
- Treat them as assets

**Travellers / Mercenaries:**
- Passing through; stronger on average, unknown abilities
- Town has little attachment — death causes minimal reputation damage
- Carry exotic loot from distant regions (new analysis opportunities)
- Don't return — each group is a one-shot event
- Higher risk, higher research value

### The Engagement Meter

Each adventurer has an Engagement Meter — their read of whether this run is
worth their time.

**Decays when:**
- Walking through empty corridors with no stimulus
- Finding looted or empty chests
- Party members die or flee

**Refills when:**
- Finding loot (more for high-demand items)
- Surviving a dangerous encounter (adrenaline)
- Landing a critical hit or spell

**At zero:** adventurer casts Town Portal and leaves. They leave a bad review,
temporarily lowering the dungeon's reputation tier.

**Scanner mechanic:** adventurers "ping" visible chests. If estimated loot value
is less than the estimated effort to reach it, they ignore the room entirely.
This is the ROI check made explicit — a chest behind a hard mob in a long
corridor needs to contain something worth it.

### Adventurer Progression (Qualitative)

Level is not a stat multiplier. It's accumulated pattern recognition.

**Low level:**
- Reactive: charges whatever they see, steps on traps, stands in arrow lanes
- No threat assessment, no party coordination

**Mid level:**
- Threat triage: assesses before engaging (mob count, party HP, trap indicators)
- Basic positioning: mage stays at range, warrior steps forward
- Trap awareness: remembers trap types seen in past runs across the dungeon
- Pull tactics: lures mobs away from reinforcements

**High level:**
- Counter-prepared: carries specific items for known dungeon types
- Party synergy: coordinated focus fire, healer prioritizes wounded allies
- Dungeon reading: recognizes the master's patterns, anticipates rooms
- Precise retreat: knows exactly when to cut losses

**The implication:** a dungeon design that works on level-5 locals gets farmed
for free once they hit level 20. You must redesign as your regulars grow. This
is the core long-term challenge.

### "The Regular" — VIP Adventurers

Named persistent characters with career arcs. Example: "Flame Bobby" (Pyromancer).

- Level 1: dies to spikes
- Level 10: returns with fire resistance gear
- Level 50: demands Epic Loot, requires a purpose-built wing to challenge

High-level regulars generate enormous mana per run. Losing them is a major
setback. They may require dedicated "VIP wings" — rooms tuned specifically to
their abilities — to remain engaged and profitable.

---

## 4. Dungeon Construction

### Layers

| Layer | Material | Game Phase |
|-------|----------|------------|
| 1 | Dirt / Wood | Tutorial / Early |
| 2 | Stone / Iron | Mid-game |
| 3 | Magma / Void | End-game |

Deeper layers require more mana to excavate and maintain but house stronger
mobs, better loot, and generate more income per adventurer run.

### Trap Tiers

Traps evolve from lethal toward resource-draining — aligned with the philosophy
of extracting maximum mana rather than killing.

| Tier | Example | Effect |
|------|---------|--------|
| 1 | Spike pit | Physical damage. Kills newbies. |
| 2 | Jagged spikes / Bear trap | Bleed / DoT — forces Healer to spend mana |
| 3 | Acid trap | Destroys armor — forces visit to in-dungeon Smithy |
| 4+ | Fear trap, exhaustion trap | Emotional spikes, stamina drain |

Traps sit "recessed" in the floor (bottom ~50% of a block). They are not
visible to adventurers until triggered (no trap detection at low level).

### Hazard Knowledge

- First trigger: unavoidable, generates mana
- Subsequent: adventurer remembers, routes around, hops over
- Parties share hazard knowledge when within proximity
- Travellers/high-level adventurers may arrive with trap awareness from
  other dungeons (generic trap types, not your specific layout)

### Biomes and Zones

Rooms can have a biome tag that attracts or deters specific adventurer types:

- Green Zone (plant mobs): attracts Pyromancers (fire is effective)
- Blue Zone (water mobs): attracts Electric Mages
- Undead Zone: attracts Paladins and Clerics (but they target the Necromancer tenant)

Biomes let the dungeon master direct traffic and create "meta" party compositions
that optimize for specific mana sources.

---

## 5. Mobs

### Mob XP and Natural Progression

Mobs gain XP from combat — each hit landed and taken, more on kills. They level
up naturally through repeated fights. The dungeon master does not promote them;
they earn it.

**The dungeon master's lever is placement:**
- A slime that has survived ten parties is now level 4. Move it deeper.
- Room 1 gets a fresh level-1 slime.
- Deep rooms accumulate the most dangerous survivors.

The difficulty gradient emerges from history, not explicit design. The dungeon
master's job is to keep it intentional — a veteran mob left in the entrance room
by accident will crater your reputation with new locals.

Higher-level mobs cost more mana (upkeep + respawn) but generate more per fight.

### Mob Respawn

Dead mobs respawn at their home position. While respawning, the dungeon drains
mana proportional to mob strength. The respawn progress bar is visible to the
dungeon master. Letting all your mobs die simultaneously is an emergency — you're
bleeding mana with no income.

### Mob Equipment and Loot

Mobs can hold equipment in slots (where their body type allows):
- Skeleton: full humanoid slots (head, chest, hands, feet, weapon, offhand)
- Slime: no slots
- Bat: no slots

When an adventurer dies, their loot drops. A mob with `can_loot = True` and
available slots will pick it up and equip it. A skeleton can wear a fallen
warrior's armor. This makes veteran mobs progressively more dangerous — they
accumulate gear from fallen adventurers.

---

## 6. Loot and the Stockpile

### The Stockpile (Vault)

The dungeon has a Vault — a stockpile of items it has produced or analyzed.

- **Passive supply:** Tenant rooms produce items over time → items enter Vault
- **Chest auto-fill:** placing a chest pulls from the Vault for free
- **Emergency printing:** if the Vault is empty, the dungeon can pay mana to
  fabricate items directly — expensive, use sparingly

### Loot Analysis

When an adventurer dies, the dungeon can analyze their dropped items.
Analyzing an item unlocks the ability to produce it (adds it to the recipe library).

- Leather armor → dungeon can now produce leather armor (via Vault or mana print)
- Steel sword → dungeon can produce steel swords
- Exotic potion from distant region → rare recipe, valuable but expensive

This is the primary tech tree. The dungeon starts with basic loot and expands
only by exposing itself to what adventurers bring in. Travellers carrying exotic
gear from distant regions are the fastest path to unlock new recipes — which is
why their deaths, while costly to reputation, are uniquely valuable.

### Chest Contents as Economic Lever

The dungeon master chooses what each chest contains. This is the primary
strategic decision:

- Right item + right chest + right location = maximum adventurer engagement
- Village demand (active quests) temporarily inflates specific item values
- High-demand items keep the Engagement Meter high longer, adventurers push deeper
- Expensive-to-produce items attract high-level parties willing to fight for them

---

## 7. Tenants

Passive rooms staffed by NPCs that generate items (not mana directly).

### Licensed Tenants (Protected by Guild Treaty)

**Blacksmith:**
- Repairs adventurer armor mid-run (extends run duration = more exertion = more mana)
- Slowly produces common weapons/armor into the Vault
- Risk: none — guaranteed safe zone, adventurers trust it

### Illicit Tenants (High Risk / High Reward)

**Necromancer:**
- Revives dead adventurers, preventing permadeath for valued regulars
- Generates raw mana passively (tax-free)
- Risk: Paladins and Clerics will prioritize destroying this room — requires
  Bouncer mobs for protection

---

## 8. The Heat / Rumor System

### How Raids Work

Raids are triggered by **information leaks**, not just wealth.

- **Real Value:** actual gold value of items in your Vault
- **Rumor Value:** what the outside world believes you have

Rumor triggers:
- Escaped adventurers who witnessed a Legendary Item
- Spy kobolds talking too much in the village tavern
- Drunken regulars bragging about their finds
- Visible opulence at the dungeon entrance

### The Raid (Harvest Festival)

When Rumor hits 100%:
- Engagement Meters disabled — adventurers aren't here for ROI, they're here for the Vault
- 20–50 adventurers enter simultaneously
- They use coordinated tactics: ladders, sappers (wall-breakers), rush formations
- Goal: reach the Vault and loot it
- Risk: losing the Stockpile (no free chest fills for a while)
- Reward: massive mana spike from the chaotic multi-party combat

Raids can be deliberately baited (late-game strategy): intentionally inflate
Rumor Value with planted information, prepare a kill box, harvest the mana
spike. High risk, very high reward.

### Crisis Events

Beyond normal raids, the dungeon faces periodic crisis events:
- **Dark Guild seeks the Core:** an organization wants your Core for power or
  profit. They send assassin parties who ignore loot entirely — straight for
  the Core. Unlike normal adventurers, killing them carries no reputation penalty
  (the town doesn't mourn hired killers)
- **Rival Dungeon opens nearby:** splits adventurer traffic, reduces your income,
  may steal your regulars
- **Plague / drought in the village:** temporarily reduces adventurer supply
- **Inquisitor arrives:** targets Illicit Tenants (Necromancer), brings a
  Paladin-heavy party

---

## 9. The Village and Co-Evolution

The town skyline is visible above the dungeon at all times. Buildings appear
and grow as the dungeon's economy funds them.

**Village growth is driven by dungeon quality:**
- Better loot → adventurers earn more → village economy grows
- New buildings unlock: Smithy → Guild Hall → Alchemist → Training Grounds
- Better buildings → better-prepared adventurers → dungeon must keep pace

**Village board (dual purpose):**
- Adventurer quests: drive demand for specific items (inflates their value this week)
- Dungeon challenges: short-term goals for the dungeon master ("alchemist needs
  three fire-corridor runs this week," "merchant will pay for a rare recipe drop")

**The escalation loop:**
1. Dungeon offers good loot → adventurers come → village grows
2. Village grows → better-equipped adventurers → current dungeon gets farmed
3. Dungeon must evolve: deeper rooms, tougher mobs, better traps
4. Upgraded dungeon → higher-tier loot analysis → new recipes
5. Higher-tier loot → wealthier adventurers → larger village → repeat

---

## 10. Progression Phases

### Phase 1: The Filter (Early Game)
- Goal: Survival. Keep the Core safe, keep mana positive.
- Loop: Lethal traps, basic mobs, death mana from careless low-levels
- Tech: Spike pits, skeletons, basic loot

### Phase 2: The Gym (Mid Game)
- Goal: Sustain. Stop killing, start farming.
- Loop: DoT traps force Healer spend → Smithy Tenant extends runs → deep rooms
  provide escalating exertion
- Tech: Bleed/acid traps, Necromancer tenant, Blacksmith tenant, mob leveling

### Phase 3: The World Stage (Late Game)
- Goal: Reputation and Whales.
- Loop: Multi-path dungeon, biome zones, VIP wings for high-level regulars,
  deliberate raid baiting
- Tech: Legendary item printing, Raid strategy, Guild negotiations, Traveller farming

---

## 11. Economy Summary

**Mana in (exertion):**
- Damage taken by adventurers: `damage × 0.5`
- Stamina spent (sprinting, climbing, long routes)
- Spell mana cost: dungeon takes a cut of every spell cast
- Emotional spikes: fear, excitement, desperation, adrenaline
- Death mana: massive burst on adventurer kill (with reputation cost)

**Mana out (investment):**
- Placing traps: upfront cost
- Placing chests: upfront cost
- Emergency loot printing: per item, scaled by value
- Mob upkeep: small per-second drain per live mob
- Mob respawn: per-tick drain while reforming, scaled by mob strength
- Digging corridors: per tile
- Tenant upkeep: per tenant per second

**Profit = mana extracted from exertion − mana spent on loot + infrastructure**

---

## 12. Technical Principles

- Game logic is pure Python, fully testable, no rendering dependencies
- Renderer is a thin visual layer (raylib with Kenney Tiny Dungeon 16×16 sprites)
- All entities (adventurers and mobs) share the same AI architecture, physics,
  buff system, and equipment slots — only goals and faction differ
- State machine controls intent; physics runs unconditionally
- The world does not pause for entities
- uv for deps, ruff for code quality, pytest for tests
