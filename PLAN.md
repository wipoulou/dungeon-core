# Overhaul Plan

## Guiding Principles

**The world is independent from entities.** Physics, interactions, and the tick
loop run unconditionally. Entities live and die inside that world — the world
doesn't pause for them. Dead adventurers fall. Traps rearm. Mobs respawn.

**All entities follow the same rules.** Adventurers and mobs share the same AI
architecture, the same physics, the same stat/buff/slot systems. The only
difference is who controls them (player vs. dungeon) and what goals they pursue.
This opens the door to neural-net experimentation later — same observation space,
same action space, different policy.

**The player is the dungeon.** The dungeon has agency. Mobs are paid employees,
not mindless automatons. Traps cost mana to maintain. Respawning costs mana.
The dungeon invests in infrastructure and takes a cut of the suffering.

---

## Problem Statement

`update_adventurer` is ~230 lines of flat if/else where every behavior competes
for movement control. No state ownership. Adding any feature breaks others.
Same structural problem exists in `update_mob`. This needs a unified fix.

Current symptoms:
- Adventurers ignore hazards while chasing mobs
- Standing fights don't reliably trigger trap interactions
- Party coordination is bolted on post-hoc
- Projectile collision is tile-snapped, not distance-based

---

## Architectural Pillars

These are the foundational decisions everything else is built on. Getting these
right early means adding features is data entry, not surgery.

### Pillar 1: Beliefs Separate from Ground Truth

The world has a state. Each entity has a *belief* about that state. AI always
acts on beliefs, never ground truth. The gap between them is the information
asymmetry — made concrete, not metaphorical.

```python
world.get_tile(4, 3)        → Tile.MIMIC   # ground truth
adv.believes.get_tile(4, 3) → Tile.CHEST   # what they think
```

Every belief entry is `(value, confidence, timestamp, source)`. Confidence
decays are computed lazily on read — no per-tick maintenance. The belief dict
is sparse: only tiles the entity knows anything about.

Conflict resolution is Bayesian: agreeing sources raise confidence, conflicting
sources pull it toward uncertainty. Higher source trust and recency win, but
nothing reaches certainty when sources disagree.

Direct observation sets confidence via the entity's `observation_confidence`
stat (see Pillar 6) — not always 1.0. A suspicious adventurer doesn't fully
trust their own eyes. An adventurer fooled by illusions before trusts them less.

Patrol ambiguity, stale maps, and inter-party knowledge gaps all emerge from
this one structure without special cases.

### Pillar 2: Universal Event Bus

Everything that happens is a formal Event fired through a central bus. No system
talks to another directly.

```python
@dataclass
class Event:
    type: EventType          # BELIEF_VIOLATED, TRAP_TRIGGERED, MOB_SPOTTED...
    actor: Entity
    location: tuple
    ground_truth: Any        # what actually happened
    actor_belief: Any        # what actor expected
    surprise: float          # magnitude = old belief confidence
    observers: list[Entity]  # who witnessed it
    timestamp: float
```

Systems subscribe to event types they care about:
- Belief system: updates beliefs on any observation event
- Knowledge propagation: syncs beliefs between nearby entities on PROXIMITY events
- Dialogue system: generates lines on BELIEF_VIOLATED, QUEST_ITEM_FOUND, etc.
- Gossip system: logs information-carrying events for village propagation
- Mana system: computes income from DAMAGE, STAMINA_SPENT, SPELL_CAST events
- UI: visualizes events without touching game logic

Surprise magnitude (the old belief's confidence) drives the *behavioral* response
— adventurers stop optimizing, explore more, cast more spells. Surprise does not
directly generate mana; the downstream behavior change does, through normal channels.

### Pillar 3: Traits and Buffs as Modifiers (StatBlock)

No trait, buff, item, or debuff adds a code branch. They all register modifiers
on a StatBlock. The hot path never iterates — it serves a cached value.

```python
@dataclass
class Modifier:
    source: str   # "trait:suspicious", "buff:illusion_doubt", "item:boots"
    stat: str     # "observation_confidence", "speed", "flee_threshold"...
    op: Literal["add", "multiply"]
    value: float

class StatBlock:
    # Recomputes only when inputs change (dirty flagging)
    # Serves cache on every read — O(1) hot path

    def get(self, stat: str) -> float: ...
    def add_modifier(self, mod: Modifier): ...   # marks stat dirty
    def remove_modifier(self, mod: Modifier): ... # marks stat dirty
```

Every derived value in the game lives here: `speed`, `observation_confidence`,
`flee_threshold`, `knowledge_share_rate`, `spell_cost_mult`, `attack_range`,
`loot_report_rate`, `encumbrance_penalty`, etc.

Traits register at entity creation. Items register on equip. Buffs register on
application and deregister on expiry — a buff is just a set of modifiers with
a duration. Adding a new trait or buff is a data entry, not a code change.

Environmental context (dungeon illusion reputation, room lighting) is applied
as a single multiply at the call site — not part of the entity stat:
```python
final_confidence = entity.stats.get("observation_confidence") * context.illusion_factor
```

### Pillar 4: Formal Knowledge Propagation

One function handles all information flow: party sync, inter-party gossip,
village rumor spread, dungeon city-awareness. Same process, different parameters.

```python
def propagate_knowledge(source: Entity, target: Entity, dt: float):
    rate = (base_rate
            * source.stats.get("knowledge_share_rate")
            * trust(source, target)
            * proximity_factor(source, target))
    for tile, belief in source.believes.items():
        if belief.confidence > PROPAGATION_THRESHOLD:
            target.believes.update(tile, belief.degrade(rate), source)
```

Knowledge only propagates on sync events (proximity trigger, party camp, guild
debrief) — not every tick. The dungeon's growing city-awareness is this same
function with the dungeon as target and village NPCs as sources, unlocked at
influence thresholds.

### Pillar 5: Presentation as Pure Observer

The simulation knows nothing about dialogue, UI, or visualization. It fires
events. The presentation layer subscribes and decides how to represent them.
If presentation is down, the simulation runs identically.

This is what makes the dialogue system swappable: template generation and
LLM generation are both valid subscribers to the same event stream, producing
the same output format. The game logic doesn't know or care which is running.

Dialogue lines carry an information tag (what they reveal mechanically) used
by the gossip system — separate from the display text.

### Pillar 6: Unified Entity State Machine

Both adventurers and mobs use the same structure. States are named values;
transitions are explicit; each state owns its movement intent and actions.
Physics runs unconditionally underneath — the state machine only outputs a
desired direction. The same structure accommodates a hand-written policy today
and a learned neural policy later: same observation space, same action space.

---

## Architecture (Detail)

### State Transitions

Both adventurers and mobs use the same state machine structure. States are simple
named values; transitions are explicit. The state machine controls *intent* only —
physics runs unconditionally underneath it.

**Adventurer states:**
```
EXPLORING   → spot mob                 → APPROACHING
            → bear trap triggered      → TRAPPED
            → reach chest (has loot)   → LOOTING
            → greed=0 or HP<threshold  → FLEEING
            → casting spell (future)   → CASTING

APPROACHING → within attack_range      → FIGHTING
            → target died              → EXPLORING
            → HP critical              → FLEEING

FIGHTING    → target dead/fled         → EXPLORING
            → HP critical              → FLEEING
            → target out of range+0.5  → APPROACHING

LOOTING     → timer done               → EXPLORING or FLEEING

TRAPPED     → timer done               → EXPLORING or FLEEING

FLEEING     → at entrance              → EXITED
            → cornered (mob <1 tile)   → FIGHTING

CASTING     → channel done             → EXPLORING (future)
```

**Mob states:**
```
PATROLLING  → adventurer in aggro_range → CHASING
CHASING     → within attack_range       → ATTACKING
            → target left leash_range   → PATROLLING
ATTACKING   → target dead               → PATROLLING
            → target left attack_range  → CHASING
DEAD        → respawn_timer elapsed     → PATROLLING
```

Each state owns:
- What movement target to request (or none)
- What pathfinding mode to use (avoid hazards? sprint? ignore mobs?)
- Transition conditions to check each tick
- What actions to perform (attack, loot, cast)

Physics (gravity, jumping, wall collision, hop arc) runs unconditionally every
tick regardless of state. The state machine outputs a desired horizontal direction;
physics applies it.

### 2. Interaction Pass

`game_state.update()` is restructured into three phases:

```
Phase 1 — Move everything
  apply physics to all entities (gravity, velocity, collision)
  move all projectiles

Phase 2 — Interactions (order matters within phase)
  for each adventurer:
    a. hazard tile check (spike, bear trap arm/trigger)
    b. chest proximity check
    c. mob visibility check (EXPLORING → APPROACHING)
  for each mob:
    d. adventurer aggro check (within aggro_range)
  for each projectile:
    e. wall collision (destroy projectile)
    f. entity hit (distance-based float, not tile-snap)
  apply all damage events → generate mana
  apply all state transitions

Phase 3 — Party coordination
  sync deferred knowledge (see below)
  apply sympathy greed drain
```

Events within a tick are applied sequentially. An entity that dies mid-tick
stops receiving further events for that tick. The world doesn't care — other
events still process for other entities.

### 3. Cost-Map Pathfinding

Replace binary `avoid: set` with a weighted cost grid.

```python
def build_cost_map(grid, known_hazards, mobs, entity_level=1) -> dict[tuple, float]:
    costs = {}
    for pos in known_hazards:
        costs[pos] = 10.0 / entity_level   # experienced entities navigate better
    for mob in mobs:
        for tile in tiles_near(mob, radius=2):
            costs[tile] = costs.get(tile, 0) + 4.0
    # future: AoE spell zones, fire, flood
    return costs
```

A fleeing adventurer with no clean path will route through known hazards rather
than stand still. Pathfinding returns lowest-cost path, not avoid-or-fail.

### 4. Party Knowledge Model

Knowledge does not teleport. Scouts don't instantly share discoveries with the
party — they carry knowledge back with them.

```python
class PartyMember:
    local_hazards: set[tuple]   # what THIS member knows
    local_map: set[tuple]       # what THIS member has seen

class Party:
    members: list[PartyMember]
    shared_hazards: set[tuple]  # synchronized at proximity threshold
    shared_map: set[tuple]

    def sync_knowledge(self):
        # Only share between members within SYNC_RANGE tiles of each other
        for a, b in pairs(self.members):
            if distance(a, b) <= SYNC_RANGE:
                merged = a.local_hazards | b.local_hazards
                a.local_hazards = merged
                b.local_hazards = merged
        # Persistent team returning: merge local into shared on EXITED
        # Cache invalidation: shared_map tiles with STALE_AGE are flagged
        # uncertain — adventurers treat them as unknown until re-explored

    def sync_sympathy(self, dt):
        missing = [m for m in members if m.reached_exit or not m.alive]
        greed_drain = len(missing) * SYMPATHY_DRAIN_PER_SEC * dt
        for m in self.active_members:
            m.greed -= greed_drain
```

For persistent teams: when a member exits, their `local_map` merges into the
party's `shared_map` with a timestamp. On the next run, tiles older than
`STALE_THRESHOLD` are flagged as potentially invalid (dungeon may have changed).
Returning adventurers explore flagged tiles as if new.

### 5. Buff/Debuff System

All entities have a buff list. Buffs are time-limited stat modifiers or
behavior overrides.

```python
@dataclass
class Buff:
    name: str
    duration: float          # remaining seconds (-1 = permanent)
    stat_mods: dict[str, float]  # e.g. {"speed": -0.5, "defense": +2}
    on_tick: Callable | None     # e.g. poison deals damage per tick
    blocks_state: str | None     # e.g. "FLEEING" (courage buff)
    source: Entity | None        # who applied it

class Entity:
    buffs: list[Buff]

    @property
    def effective_speed(self):
        base = self.speed
        return base + sum(b.stat_mods.get("speed", 0) for b in self.buffs)
```

Examples: TRAPPED is a buff (speed=0, duration=2.5). Poison is a buff
(on_tick=deal_damage). Fear is a buff (blocks_state="FIGHTING"). Armor is
a permanent buff from an equipment slot.

### 6. Equipment Slots

Entities have slots determined by their type. Items in slots provide permanent
buffs. Items not in a slot are carried (encumbered rate reduces speed per item).

```python
SLOTS_BY_MOB_TYPE = {
    MobType.SKELETON: ["head", "chest", "hands", "feet", "weapon", "offhand"],
    MobType.SLIME:    [],   # no slots, can't hold equipment
    MobType.BAT:      [],
}

SLOTS_BY_ADV_CLASS = {
    AdventurerClass.WARRIOR: ["head", "chest", "hands", "feet", "weapon", "offhand"],
    AdventurerClass.MAGE:    ["head", "chest", "hands", "feet", "weapon", "catalyst"],
    AdventurerClass.ROGUE:   ["head", "chest", "hands", "feet", "weapon", "weapon"],  # dual wield
    AdventurerClass.HEALER:  ["head", "chest", "hands", "feet", "weapon", "catalyst"],
}

class Entity:
    slots: dict[str, Item | None]   # slot_name → equipped item or None
    inventory: list[Item]           # carried but unequipped (causes encumbrance)

    @property
    def encumbrance_penalty(self):
        return len(self.inventory) * ENCUMBRANCE_PER_ITEM
```

When a mob kills an adventurer (or vice versa), if the killer has a loot
behavior, it checks the corpse's inventory and equipped items and picks them up.
A skeleton can equip a fallen warrior's sword. A slime cannot.

### 7. World Economy

The dungeon is not farming damage. It is farming *exertion*. Loot is bait.

**The one rule:**
Mana is the cost of everything. The only way to replenish it is to lure
adventurers in and extract it from their exertion.

**The fundamental tension:**
- Adventurers are rational economic actors. Loot value ÷ (risk + time) = ROI.
  They will tolerate damage, traps, and mobs as long as the expected loot
  justifies it. If ROI drops below their threshold, they stop coming.
- The dungeon spends mana to produce loot and maintain infrastructure. Every
  chest stocked is an investment. It only pays off if the adventurers suffer
  enough on the way to it.

**Mana income (exertion):**
- Damage taken by adventurers: `damage * 0.5`
- Stamina drained (sprinting, climbing, long routes)
- Emotional spikes: fear (trap triggered), excitement (tough fight survived),
  desperation (low HP, fleeing)
- Higher adventurer morale while fighting → richer emotional experience → more mana

**Mana costs (investment):**
- Placing a chest: small upfront cost
- Restocking chest loot: mana drains per tick while regenerating, scaled by item
  value. A major health potion costs more to regenerate than a coin purse.
  The better the bait, the more it costs to maintain.
- Mob upkeep: small drain per second per live mob
- Mob respawn: mana drains per tick proportional to `respawn_cost * (1 - progress)`
  — paying while the mob reforms. Stronger mobs cost more, take longer.
- Placing traps: upfront cost
- Digging new corridors: per tile

**Adventurer ROI (patience bar):**
- Each adventurer tracks a satisfaction score: loot value gained vs. risk
  and damage taken so far this run
- High satisfaction → push deeper, fight harder, generate more mana per hit
  (emotionally engaged, adrenaline up)
- Low satisfaction → leave early even if healthy
- Filled by: looting high-value or high-demand items, defeating strong mobs,
  finding unexpected treasure
- Drained by: empty chests, repeated damage with no reward, long stretches
  with nothing happening

**Village demand:**
- Items have a base value but their *effective value to adventurers* fluctuates
  based on active village quests and shortages
- Example: village alchemist needs fire resistance potions → water potions jump
  in value this week → adventurers willing to take more risk for them → dungeon
  can charge higher "exertion price" for the same loot
- The dungeon master who reads demand and stocks accordingly earns far more mana
  per item than one stocking generic loot

**The core puzzle:**
- Put high-value loot deep behind difficult rooms
- Adventurers will suffer through your dungeon because the expected payout
  justifies it
- Extract maximum exertion mana before they reach the chest
- Restock the chest with mana you earned
- Profit margin = mana earned from exertion − mana spent on loot + infrastructure

**Failure modes:**
- Too many traps, too little loot → bad ROI → adventurers stop coming
- Too much good loot too easily → great ROI for adventurers → dungeon bleeds mana
- Miss the village demand window → stocked the wrong items, half the potential value
- All mobs die simultaneously → bleeding mana on respawns with no income

### 8. Chest Management

- Chests cost a flat mana fee to place (no vault inventory consumed)
- The dungeon master configures what each chest contains — this persists between
  loot cycles
- After looting, chest shows a refill progress bar (same indicator as mob respawn)
- While refilling, dungeon drains mana per tick based on item value
- Chest contents are the primary economic lever: right item, right location,
  right time

---

## Visual Debug: Entity Decision View

A toggleable overlay (key: D) shows the current state and intent of each entity:

- State label above entity: `[FLEEING]`, `[FIGHTING slime]`, `[EXPLORING]`
- Intended path: colored line to current waypoint
- Cost map: tile tint by cost (green=cheap, red=expensive) in a radius around entity
- Buff icons: small symbols for active buffs
- Knowledge boundary: faint outline of what the entity has seen

This gives the dungeon master direct feedback on why entities make the decisions
they do, and is the foundation for a future neural-net policy visualization
(observation space, action weights, reward signal).

---

## UI Roadmap

Current keyboard shortcut system doesn't scale. Planned UI layers:

**Build palette** (near-term): a proper sidebar or radial menu showing available
traps, terrain tools, and mob types with their mana cost. Click to select,
LMB/RMB to place/remove.

**Mob management panel** (mid-term): select a mob to see its stats, current
state, patrol path, equipment slots. Drag items between slots.

**Loot/vault panel** (mid-term): view vault contents, set auto-refill rules for
chests, see what adventurers are carrying.

**Dungeon ledger** (long-term): mana income/expense over time, adventurer visit
history, reputation metrics.

---

## Files Affected (Immediate Overhaul)

| File | Change |
|------|--------|
| `dungeon/entity.py` | Add `buffs`, `slots`, `inventory`, `effective_*` properties |
| `dungeon/adventurer.py` | Replace `update_adventurer` with state machine + cost-map pathfinding |
| `dungeon/mob.py` | Replace `update_mob` with same-structure state machine |
| `dungeon/pathfinding.py` | Add cost-map variant of `find_path` |
| `dungeon/party.py` | New: `Party` with proximity-gated knowledge sync |
| `dungeon/buff.py` | New: `Buff` dataclass + `apply_buffs(entity, dt)` |
| `dungeon/game_state.py` | Restructure `update()` into move + interact + coordinate phases |
| `dungeon/trap.py` | Minor: trap triggering moves to interaction pass |
| `dungeon/mob.py` | Minor: mob aggro moves to interaction pass |
| `tests/` | State transition tests, cost-map routing tests |

**Unchanged:** `main.py`, `grid.py`, `loot.py`, `log.py`

---

## Implementation Order

1. `buff.py` + `entity.py` buff/slot fields — foundational, no behavior change yet
2. `pathfinding.py` cost-map — self-contained, testable, no behavior change yet
3. `adventurer.py` state machine — replaces current update, biggest change
4. `mob.py` state machine — same structure as adventurer, easier second pass
5. `game_state.py` interaction pass — replaces scattered checks
6. `party.py` proximity-gated knowledge — replaces current instant-sync

Each step can be shipped and tested independently.

---

### 9. Mana from Spells

When adventurers cast spells, the dungeon takes a cut of the mana cost. This
changes everything about how the dungeon should think about spellcasters.

- Every heal cast by a healer: dungeon earns mana
- Every fireball cast by a mage: dungeon earns mana
- The more spells cast per run, the better — a healer keeping a party alive
  through a hard fight is generating mana twice (combat damage + heal cost)

**Implication for dungeon design:**
- Killing the healer is the worst possible move. Healer alive = party survives
  longer = more exertion = more mana. Healer casting = direct mana income.
- The optimal dungeon routes adventurers *toward* hard fights that stress them
  enough to need healing, not toward instant kills
- Sustain-oriented dungeons (tough but survivable) beat spike-damage dungeons
  (kill fast, no mana extracted)
- Mage in party: design rooms that force them to spend mana (large mob groups,
  ranged harassment, terrain that makes melee unsafe)

### 10. Adventurer Progression (Qualitative, Not Just Numerical)

Level is not a stat multiplier. Level represents accumulated experience with
dungeons — pattern recognition, threat assessment, tactical judgment.

**Low-level adventurers:**
- Reactive: charge whatever they see, step on traps, stand in arrow lanes
- No threat assessment: engage the skeleton even though the party is wounded
- No party coordination: everyone does their own thing
- Single-target thinking: fight the mob in front of them

**Mid-level adventurers:**
- Threat triage: assess before engaging (how many mobs? what types? party HP?)
- Basic positioning: mage stays at range, warrior steps forward
- Trap awareness: recognize trap types they've seen before across multiple dungeons
  (not just this run — they remember from past runs)
- Pull tactics: lure a mob away from reinforcements before engaging

**High-level adventurers:**
- Counter-prepared: bring specific items for known dungeon types (fire dungeon?
  bring fireproof oil, healing burns the dungeon's mana more)
- Party synergy: coordinated focus fire, healer prioritizes lowest-HP member,
  rogue flanks while warrior draws attention
- Dungeon reading: recognize that a suspiciously easy corridor probably has a
  trap around the corner; identify the dungeon master's patterns over time
- Risk-calibrated retreat: know the exact moment to cut losses and leave with
  what they have, rather than pushing for the last chest

**What this means for the dungeon master:**
- A dungeon that worked on low-level regulars will fail on high-level visitors
- You have to redesign layouts as regulars level up — same traps in the same
  spots stop working
- The dungeon's own progression (deeper rooms, stronger mobs, better traps) is
  a direct response to adventurer progression
- The meta-game: your regulars level up, which forces you to upgrade the dungeon,
  which makes the dungeon more profitable for high-level visitors, which attracts
  harder groups, which requires even more upgrades

**Implementation approach:**
- Each adventurer has an `experience: int` and a derived `tactics_level: int`
- `tactics_level` gates behaviors: threat assessment, pull tactics, positioning
- Higher `tactics_level` means more conservative transition thresholds (won't
  engage unless odds are favorable), better cost map estimates, and access to
  cross-run dungeon memory
- Party `tactics_level` = average of members (a veteran carrying two novices is
  still somewhat anchored)

### 11. Dungeon Progression: Kills, Loot Analysis, and Mob XP

**Killing an adventurer is a deliberate choice with a real cost.**

On death, an adventurer drops everything: equipped items and inventory. The
dungeon gets a massive mana burst (relatively speaking — the largest single
mana event in the game). But the dungeon's reputation takes a hit. Fewer
adventurers come after word spreads. Systematic killing is self-defeating.
Occasional targeted killing — when the research value of the loot is high — is
a calculated investment.

**Loot analysis:**
- After an adventurer dies, the dungeon can analyze their dropped items
- Analyzing an item unlocks the ability to produce it in chests (adds it to the
  dungeon's "recipe" library)
- Example: warrior dies carrying leather armor + steel sword + health potion →
  dungeon can now stock those items, at their respective mana restock costs
- This is the dungeon's tech tree. It starts with basic loot and expands based
  on what higher-level adventurers bring in
- Items analyzed from high-level adventurers are expensive to produce but
  attract and incentivize high-level visitors — closing the loop

**Mob XP:**
- Mobs gain XP from combat: small amount per hit landed, larger on kill
- Same XP formula as adventurers — fighting is what makes you better
- When a mob naturally levels up (through repeated combat, not player action),
  the dungeon is notified: "your slime in room 2 has reached level 3"
- The dungeon master can then choose to promote: future spawns of that mob type
  cost more mana (upkeep + respawn) but are stronger, generate more mana per
  fight, and may unlock new behaviors at certain level thresholds
- Leveled mobs retain the same state machine but with upgraded stats and
  potentially new abilities (level 5 skeleton can summon a bone shield buff,
  level 3 slime splits on death)
- The dungeon can have a mix of levels — cheap low-level mobs as fodder,
  expensive high-level champions guarding the deep rooms

**The kill incentive balance:**
- Kill an adventurer: massive mana burst + potential tech unlock
- Cost: reputation damage, fewer adventurers visit for a while
- The temptation is real, especially for a heavily-equipped veteran carrying
  items you haven't analyzed yet
- But killing your best regulars destroys your steady income
- Ideal play: let regulars run freely (steady mana income), occasionally let
  a high-level visitor die to unlock their gear, never make it look intentional

### 12. The Ecosystem: Dungeon and Village Co-Evolution

The dungeon and village are in a symbiotic arms race. Neither "wins" —
the ecosystem escalates.

**Village growth is driven by dungeon quality:**
- Better loot available → adventurers earn more → village economy grows
- Village earns taxes/fees from adventurers spending their dungeon earnings
- As village grows, it develops infrastructure:
  - Shops (adventurers can buy equipment before runs)
  - Training facilities (faster XP gain, ability unlocks)
  - Guild hall (party formation, quest boards, reputation tracking)
  - Alchemist (potions for sale, demand for specific ingredients)
  - Blacksmith (weapon/armor upgrades from dungeon-dropped materials)

**Adventurer growth is driven by village infrastructure:**
- Training facilities → higher tactics_level at lower XP thresholds
- Shops → counter-items available → dungeon's current mobs get neutralized
- Guild hall → better party composition (parties formed by role, not random)
- This is what forces the dungeon to keep evolving: the village keeps producing
  better-equipped, better-prepared adventurers

**The escalation loop:**
1. Dungeon offers good loot → adventurers come → village grows
2. Village grows → better adventurers → dungeon's current design gets farmed
3. Dungeon must upgrade (new mobs, deeper rooms, better traps) to stay profitable
4. Upgraded dungeon → better loot analysis possible → higher-tier recipes
5. Higher-tier loot → wealthier adventurers → larger village → repeat

**The endgame (undefined, but direction):**
- The loop doesn't end, it escalates until the dungeon is a legendary site
  that attracts heroes from distant lands (visitors with exotic gear and
  abilities the dungeon has never seen)
- Or the dungeon overreaches, kills too many regulars, reputation craters,
  the village stagnates — a recoverable setback but a real one
- The "win condition" may not be a single moment but a sustained state:
  a thriving village sending waves of well-equipped adventurers into a deep,
  complex dungeon that extracts maximum mana from every run

### 14. Two Types of Parties

**Locals** (regulars from the village):
- Live in the nearby town, have families and reputations
- Town cares deeply if they die — each death is a significant reputation hit
- Steady income: you know their capabilities, they know your dungeon
- As they level up they become harder to challenge but generate more mana
- Your core business; treat them as assets

**Travellers / Mercenaries** (passing through):
- Stronger on average than locals at equivalent level — they've seen more dungeons
- Town has little attachment to them; death causes minimal reputation damage
- Carry exotic loot: items from distant regions the dungeon hasn't seen (new
  analysis opportunities)
- Unpredictable: unknown abilities, unfamiliar tactics, may have counters for
  your standard mobs
- High-risk high-reward: worth letting one die for the research, less political cost
- Don't return — each traveller group is a one-shot event

**Implications:**
- The dungeon master has to read the party type and adjust strategy mid-run
- Travellers are the primary source of new item unlocks via loot analysis
- A famous dungeon (high notoriety) attracts more travellers from further away —
  escalating the quality and exoticism of available loot

### 15. Mob Placement and Natural Progression

Mobs gain XP from combat — every hit landed and taken, more on kills. They level
up naturally. The dungeon master does not "promote" them; they just get better.

The dungeon master's lever is **placement**:
- A slime that has survived ten parties is now level 4. Move it to a deeper,
  harder corridor where it belongs.
- Room 1 gets a fresh level-1 slime — cheap, manageable for new locals.
- The deep vault gets the veterans.

This creates a natural difficulty gradient that emerges from the dungeon's history
rather than explicit design. Early rooms stay accessible. Deep rooms accumulate
the most dangerous survivors. The dungeon master's job is to keep the gradient
intentional — a level-7 mob accidentally left in the entrance room will kill
every new local and crater your reputation.

### 16. Village Visibility and Player Purpose

**The village should be directly visible** — it's the clearest readout of whether
your dungeon is working. A growing village with new buildings is tangible progress.

But the deeper question is: what is the player *working toward*? Village growth
is a consequence, not a goal. Candidates:

- **Notoriety**: become the most famous dungeon in the region. Measured by visitor
  origin distance. Travellers from distant kingdoms are the late-game benchmark.
- **Survival**: a legendary hero is coming in N days to "cleanse" the dungeon.
  Build fast enough to survive it.
- **Crisis events**: rival dungeon opens nearby and steals your adventurers,
  a plague reduces the village population, a drought cuts adventurer income —
  systemic pressures that require active dungeon management to weather.

**The village board as dual purpose:**
- Adventurer quests: drive loot demand (water potions in demand this week)
- Dungeon master challenges: short-term goals that give purpose within the long
  arc ("the alchemist needs 3 parties through the fire corridor this week",
  "a merchant will pay for a rare drop if you can produce it")

**Ambient world-building instead of pure UI:**
- Adventurers could carry dialogue that reflects village state: "heard the
  blacksmith just set up shop, check out my new sword" — you infer village
  progress from who walks through your door and what they're carrying
- This is complementary to direct village view, not a replacement
- Makes the village feel alive rather than a progress bar

**Open question: what is the endgame?**
The escalation loop (dungeon ↔ village) doesn't naturally terminate. Options:
- No win condition — it's a management sandbox with crises to weather
- Notoriety milestone — "your dungeon is now legendary, travellers come from
  the far continent" — a soft climax that opens a new difficulty tier
- Legacy — the dungeon outlives you somehow (dungeon consciousness transcends,
  becomes a myth, the village becomes a city)
This needs more thought. The mechanics support any of these; the choice is
about what kind of game this wants to be.

### 18. Party Composition and Counters

---

### 19. Information Asymmetry — Tools and Visibility

#### Dungeon Master Tools

**Rearrange mode:** move traps, chests, mob positions without rebuilding walls.
Low mana cost. Primary "reset their mental map" action. The dungeon that never
changes gets farmed; the one that reshuffles forces re-exploration.

**Mimics:** a mob type that impersonates a chest and has a spell that fools the
adventurer scanner. Parties need to invest levels in detection to see through it.
This is an arms race — mimic levels up its deception, high-level parties invest
in counter-scanning. A proper metagame, not a passive trap.

**Patrol ambiguity (emergent, not managed):** mobs on patrol routes create
free information uncertainty. Party A saw the skeleton at the corridor entrance.
Party B saw it at the far end. Did it move, or was it patrolling? The dungeon
master doesn't orchestrate this — it happens from normal patrol behavior. The
knowledge gap between party reports is already enough.

**Rumor seeding:** plant specific information in the village to drive traffic.
Can be true or false. False rumors carry two failure modes:
- Hurts the informant's credibility (they get ignored over time)
- Hurts the dungeon's desirability (parties stop trusting your loot signals)
The dungeon master who lies too often loses the ability to attract targeted traffic.

**Dungeon influence as threshold capability (replaces kobold network):** as the
dungeon hits power milestones, it unlocks capabilities organically — not through
a purchased spy network. Growing influence extends the dungeon's spatial reach
(build further from the Core) and eventually grants city-level awareness: seeing
what parties are planning, what the quest board shows, what maps were purchased.
Feels earned, not bought.

**Teleport consumables (party side, not dungeon):** high-level parties carry
escape scrolls. A single-use Town Portal that lets them survive a kill-box run
at the cost of the scroll. Creates tension: the dungeon that designs around the
scroll (force them to use it *before* reaching the Core) is playing at a higher
level than one that just builds a lethal room.

**One-way drops:** architectural. Parties enter a room one way, must exit
differently. Breaks the "optimal path backwards" habit and creates genuine
route uncertainty on exit.

**Secret rooms:** not on any guild map — map sellers never found them, or the
dungeon actively concealed them. A party that stumbles in adds it to personal
knowledge, which propagates through gossip over time. Once enough parties know,
it may leak to a map. "Secret" is a temporary information state, not permanent.
The dungeon master can seal or relocate a compromised secret room.

#### Making the Asymmetry Legible (Without Spelling It Out)

**Movement as readable state:** a confident party moves fast, in formation, skips
rooms without checking. An uncertain party spreads out, slows, checks every tile.
The dungeon master reads their state from behavior alone — no number needed.

**Party communication as the visibility system:** parties talk to each other
constantly. A careful player can follow a dive and read the party's reasoning
in real time. "I expected a chest here." "The skeleton was further back last
time." "Something moved." This is very hard to implement well but is the right
vision — behavior and dialogue are the primary signal, not a UI overlay.

**"I expected X here!" reactions:** when a confident party finds something other
than what they expected, they say so. This tells the dungeon master exactly what
their mental model was — not just that they were surprised, but *what they
believed*. That's actionable intelligence: you know what they expected, you know
what changed, you know whether to press the advantage or reset.

**Observation as an unlockable skill:** early game, you read parties through
behavior and overheard dialogue. Later, a dungeon upgrade passively "stalks"
parties and surfaces a dashboard of their current goal, confidence, and mental
map. By the time you unlock it, you already understand what it measures — you've
been reading it manually since the start.

**Negative mana runs displayed starkly:** when a party exits, calculate:
`mana earned − (loot restock cost + mob respawn cost)`. If negative, show it
clearly after the run — "that run cost you 40 mana" in a distinct color. One
number, no graph, no explanation. The dungeon master who sees veterans regularly
generating negative runs has all the signal they need to act.

**Surprised parties don't give bonus mana directly — they stop optimizing.** The
mana comes from the behavior change: they re-explore, engage mobs they'd have
skipped, panic-cast spells. The surprise is the cause; the elevated mana over
the rest of their run is the effect. No correlation chart needed — the run total
tells the story.

### 20. Knowledge Confidence and Map Sellers

**Every party has a Knowledge Confidence score for the dungeon.**

- Starts at 0 on first visit (full exploration mode)
- Rises as they successfully navigate rooms matching their mental map
- High confidence → party speedruns known route, skips low-value rooms
- Confidence is subverted when: a trap moved, a mob is new/stronger/weaker,
  expected loot isn't there, a new room exists
- Subversion event → confidence drops → party switches back to exploration mode
  → more exertion → more mana

The dungeon master who never changes anything gets farmed by veterans running
the same optimal route every time. The one who keeps reshuffling forces
re-exploration. You don't need to announce changes — the surprise *is* the mechanic.

**Map Seller parties:**
- A specific party archetype whose goal is documentation, not loot
- Exploration-optimized: dodge fights, avoid traps, cover maximum area
- Sell the resulting map to the guild → other parties buy it before runs
- This is adversarial: a widely-sold accurate map neutralizes your dungeon's
  information advantage and locks in the optimal route for everyone
- Response options: kill them (reputation hit, but worth it sometimes), change
  the dungeon right after they visit, send misinformation through kobold merchants
- Map accuracy decays over time as the dungeon changes

### 20. Adventurer Traits and Party Personality

**Individual traits** modify an adventurer's behavior and generate emergent
party dynamics when combined.

Example traits:
| Trait | Effect |
|-------|--------|
| Greedy | Stays longer than safe, pushes deeper — higher mana but higher mortality risk |
| Cautious | Early exits, conservative engagement threshold |
| Inefficient | Spell/stamina costs 20% higher — more mana per spell for the dungeon |
| Brave | Doesn't flee until much lower HP, fights when others would run |
| Cowardly | Flees at higher HP threshold, contagious — triggers party sympathy faster |
| Thorough | Explores every room, never skips — low confidence tolerance |
| Pragmatic | Pure ROI — ignores rooms that don't scan well, efficient route |
| Glory-seeking | Engagement fills on difficult kills, drains on easy ones |

Traits change slowly over time: a Greedy adventurer who nearly died twice may
drift Cautious. A Cowardly adventurer who survived a harrowing run may gain
Brave. Traits are not permanent — they reflect lived experience.

**Party personality emerges from trait combinations:**
- Three Greedy adventurers = reckless party that regularly overextends
- Pragmatic + Cautious + Thorough = slow methodical group that covers everything
  but leaves early if ROI dips
- Two Brave + one Cowardly = internal tension, Cowardly member triggers sympathy
  drain on the others when they want to leave

The dungeon master reads party composition and adjusts accordingly — a reckless
party benefits from a kill box deep in the dungeon, a pragmatic party needs
consistently high-value chests or they skip your hard rooms.

### 21. Dungeon Reputation Catalog

Parties can only seek specific items from your dungeon if they know you produce them.

**Information flow:**
1. Adventurer finds water potion in your dungeon → reports to village
2. Village knowledge base gets tagged: "south dungeon produces water potions"
3. Quest board can now route water-potion quests your way
4. Parties know *that* you have it, not *where* — they still search for it
5. Your "catalog" builds over time; each new item type found adds an entry

**Dungeon master controls:**
- **Advertise:** deliberately leak specific item information (kobold merchants
  in the village, let a party escape with something visible) to attract
  targeted traffic
- **De-list:** stop producing an item; catalog entry decays as parties stop
  finding it
- **Misdirect:** plant false information about what rooms contain what

**The catalog creates pull-based traffic:** instead of designing for generic
parties, the dungeon attracts parties who specifically want what you offer.
A dungeon known for rare potions draws alchemist-quest parties. One known for
exotic weapons draws armory-focused parties. Specialization is a viable strategy.

### 22. Dungeon Building Depth

The dungeon building tools must be deep enough to support all of the above.
Core design principles for the building layer:

- **Multi-path as default:** every meaningful loot location should have at
  least two viable approaches — one fast/dangerous, one slow/safe. Parties
  self-sort by confidence and health state.
- **Traffic flow as a design skill:** chokepoints, one-way drops, room
  adjacency — the dungeon master is an architect optimizing for exertion-per-tile
- **Trap synergies:** an arrow trap pointing toward a bear trap location; a
  bleed trap before a long corridor without a healer rest point; acid trap
  before the Blacksmith tenant (forces purchase)
- **Mob patrol design:** mobs aren't just placed, they have patrol routes the
  dungeon master can set — creating coverage patterns, ambush positions, and
  intentional gaps that feel like safe routes until they aren't
- **Secret rooms:** not on any map, accessible via hidden passages — high-value
  loot for thorough explorers, permanently subverts confident speedrunners
- **Room typing:** rooms have designations (trap room, mob room, rest area,
  tenant room, loot room) that affect adventurer scanner behavior and biome
  assignment
- **Vertical design:** deeper layers aren't just harder — they have different
  physics (magma slows movement, void has low gravity), different mob types,
  and different loot categories

## Open Questions

- **Neural net hook**: the state machine's transition-check function is the natural
  plug point for a learned policy. The observation vector (nearby tiles, entity
  stats, buff list, known hazards, party state, run satisfaction) maps cleanly to
  features. `tactics_level` could eventually be replaced by a trained policy.
  Keep the interface clean.

- **Mob loot behavior flag**: not all mobs should pick up loot (slimes can't, rats
  shouldn't bother). Needs a `can_loot: bool` field on mob type definition.

- **Stale map threshold**: how long before shared party knowledge becomes uncertain?
  Probably a function of how many runs have happened since last visit, not wall
  clock time.

- **Spell mana cut percentage**: what fraction does the dungeon take? Probably
  varies by dungeon upgrade level — a more powerful dungeon is a better mana
  siphon. Starts at maybe 20%, upgradeable.
