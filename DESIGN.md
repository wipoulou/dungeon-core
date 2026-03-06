# Dungeon Symbiosis - Game Design Vision

## Core Fantasy

You ARE the dungeon. Adventurers are your livestock — you farm mana from their
exertion, not their death. A dead adventurer is a lost customer. The goal is to
build a treadmill, not a deathtrap.

## The Dungeon

- 2D side-view ant-farm layout
- Tile-based: dirt (walls), empty (air), spikes (hazards), chests (loot), spawn, exit
- The dungeon master digs corridors, places traps, chests, and creatures
- Thoughtful design beats large design — a compact, well-placed dungeon forces
  adventurers through more hazards per chest
- Placement matters: your own creatures are hurt by your traps, so spike
  placement near patrol routes requires thought

## Entities

All creatures (adventurers and mobs) share a common Entity base with:

- **Stats**: HP, attack, defense, speed, attack speed
- **Resources**: stamina, mana (for casters)
- **Faction**: adventurer or dungeon — enables PvP down the line
- **Combat state**: engaged/idle, attack cooldowns

### Adventurers

#### Behavior Model

- Adventurers explore **blind** — they don't know the layout until they see it
  (fog of war, limited vision range)
- They **cannot see traps** (until higher levels with trap detection)
- Default behavior is always to **find the exit** — they should never stand still
- Chests are **detours**, not the primary goal

#### Classes

Four classes with distinct stat profiles:

- **Warrior**: high HP (120), high attack (15), defense (3), slow (3.5)
- **Rogue**: low HP (80), fast (5.0), high attack speed (1.5)
- **Mage**: fragile (70 HP), slow attacks, mana pool for future spells
- **Healer**: balanced (90 HP), mana pool for future healing

Classes affect combat effectiveness, movement speed, and jump arcs (slower
classes travel less horizontal distance per jump).

#### Greed vs. Risk

Adventurers have a greed meter that shifts mid-run:

- **Start greedy** (1.0): willing to explore, take detours for loot, push deeper
- **After looting** (-0.35 per chest): risk tolerance drops
- **After taking damage** (-0.10 per hit): risk tolerance drops further
- **Flee at 50% HP**: regardless of greed, self-preservation kicks in
- This means a huge dungeon with spread-out loot just means they grab the first
  chest and beeline for the exit — you want them to suffer *on the way* to the loot

#### Hazard Knowledge

- Adventurers learn trap locations by stepping on them (first hit is unavoidable)
- On subsequent encounters, they hop over known hazards
- Hop arc is tuned to clear spikes without hitting low ceilings
- Future: calculate optimal hop arc based on speed, aiming apex at trap center

### Parties and Waves

- Adventurers arrive in **parties** of 2-3, spawning staggered (0.6s apart)
- Waves auto-spawn every ~10 seconds, waiting for the previous wave to finish
- Party members explore independently but share information

#### Party Dynamics

- **Knowledge sharing**: nearby party members (within 5 tiles manhattan) sync
  known hazard locations, so one member's discovery helps the others dodge
- **Sympathy**: when a party member flees, dies, or exits, remaining members
  lose greed over time (0.15/sec per missing member). This creates natural
  party cohesion — the longer someone is gone, the more the rest want to leave.
  Allows a quick nearby chest grab but prevents deep solo exploration.

### Mobs

Dungeon creatures that patrol and fight adventurers:

- **Slime** (current): patrols back and forth, reverses at walls and edges,
  60 HP, 15 damage on contact. Hurt by spikes (20 damage/sec).

#### Combat

- Mobs have an aggro range (~4 tiles). When an adventurer enters, the mob
  stops patrolling and engages.
- Both combatants stand and fight, trading hits based on attack speed.
- Exploring adventurers fight back immediately.
- Fleeing adventurers try to run; only fight if cornered (within 1 tile).
- Combat ends when target dies or leaves aggro range.
- Future: mob types with different behaviors (skeleton chaser, bat flyer)

## Economy

### Mana

- Mana is generated from adventurer **damage taken** (0.5x damage = mana)
- Mana is spent on dungeon modifications (placing traps, chests, digging)
- Dead adventurers = lost future income, not a win condition

### Vault and Loot

- The vault is the dungeon's stockpile of loot items
- Placing a chest takes 1 item from the vault to fill it
- Looted chests auto-refill from the vault after 5 seconds
- If vault is empty, chests cost mana to fill instead

### The Core Loop

Adventurers loot chests -> loot goes to adventurers -> adventurers suffer through
hazards and mobs -> suffering generates mana -> mana funds more traps, chests,
and creatures -> repeat

## Village and Reputation

### Regulars vs. Visitors

- **Regulars**: groups from the nearby village, your steady income. You know their
  capabilities and tune the dungeon for them
- **Visitors**: stronger, less predictable groups that pass through. Higher
  risk/reward

### Pacing Tension

- Groups balance **greed and risk** — they decide whether the dungeon is worth running
- If loot doesn't refresh fast enough (dungeon too small, too many groups),
  adventurers find empty chests and the dungeon's reputation drops
- If the dungeon is too big without enough regulars to sustain it, expansion was
  wasted — not costly to maintain, but no benefit
- The sweet spot: enough dungeon depth to stagger groups so loot refreshes between
  runs, while maximizing exertion per adventurer per run

### Adventurer Progression

- Regulars gain XP, gold, equipment over repeated runs
- Higher-level adventurers are harder to challenge but generate more mana
- Future: adventurers can buy maps (know layout), detect traps, have better stats
- Adventurer priorities vary: XP-focused, gold-focused, exploration-focused, loot-focused

## Technical Principles

- Game logic is pure Python, fully testable, no rendering dependencies
- Renderer is a thin visual layer (currently raylib)
- Use uv for deps, ruff for code quality, pytest for tests
- Code-first: state as code, not editor-based
- All creatures share a common Entity base for combat compatibility and future PvP
