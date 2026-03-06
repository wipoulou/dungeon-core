# Dungeon Symbiosis - Game Design Vision

## Core Fantasy

You ARE the dungeon. Adventurers are your livestock — you farm mana from their
exertion, not their death. A dead adventurer is a lost customer. The goal is to
build a treadmill, not a deathtrap.

## The Dungeon

- 2D side-view ant-farm layout (Terraria/Fallout Shelter style)
- Tile-based: dirt (walls), empty (air), spikes, chests, ladders, traps, spawn, exit
- The dungeon master digs corridors, places traps, chests, and creatures
- Thoughtful design beats large design — a compact, well-placed dungeon forces
  adventurers through more hazards per chest
- Placement matters: your own creatures are hurt by your traps, so spike
  placement near patrol routes requires thought

## Entities

All creatures (adventurers and mobs) share a common Entity base with:

- **Stats**: HP, attack, defense, speed, attack speed, attack range
- **Resources**: stamina, mana (for casters)
- **Faction**: adventurer or dungeon — enables PvP down the line
- **Combat state**: engaged/idle, attack cooldowns, damage flash

### Adventurers

#### Behavior Model

- Adventurers explore **blind** — they don't know the layout until they see it
  (fog of war, limited vision range of 5 tiles)
- They **cannot see traps** (until higher levels with trap detection)
- Default behavior is always to **find the exit** — they should never stand still
- Chests are **detours**, not the primary goal
- Adventurers hop over **known hazards** (learned by stepping on them once)

#### Classes

Four classes with distinct stat profiles:

- **Warrior**: high HP (120), high attack (15), defense (3), slow (3.5), melee range (1.5)
- **Rogue**: low HP (80), fast (5.0), high attack speed (1.5), melee range (1.5)
- **Mage**: fragile (70 HP), slow attacks, long range (3.5), mana pool for future spells
- **Healer**: balanced (90 HP), mid range (3.0), mana pool for future healing

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

- Adventurers arrive in **parties** of 2-3, spawning staggered (0.2s apart)
- Waves auto-spawn every ~10 seconds, waiting for the previous wave to finish
- Party members explore independently but share information

#### Party Dynamics

- **Knowledge sharing**: nearby party members (within 5 tiles manhattan) sync
  known hazard locations, so one member's discovery helps the others dodge
- **Sympathy**: when a party member flees, dies, or exits, remaining members
  lose greed over time (0.15/sec per missing member). This creates natural
  party cohesion — the longer someone is gone, the more the rest want to leave.
- **Speed matching**: grouped members walk at the slowest member's speed
- **Wait during actions**: party waits while a member is fighting or looting
- **Rally to combat**: non-fighting members walk toward ongoing fights to help

### Mobs

Dungeon creatures that patrol and fight adventurers. All mobs respawn at their
home position after 30 seconds (health bar shows respawn progress).

#### Mob Types

- **Slime**: ground patrol, 60 HP, 15 damage, slow (2.0), melee. Reverses at
  walls and edges. Hurt by spikes (20 damage/sec).
- **Bat**: flying mob, 30 HP, 8 damage, fast (3.5), melee. Bounces off walls,
  ceiling, and floor. No gravity. Doesn't need floor to place.
- **Skeleton**: ground patrol, 80 HP, 12 damage, slow (1.5), ranged (4.0 tiles).
  High defense (2). Fires slower but hits from distance.

#### Combat

- Adventurers spot mobs within vision range (5 tiles) and approach to attack
- Mobs aggro adventurers within their attack range
- Both combatants stand and fight, trading hits based on attack speed
- Party members rally toward ongoing fights
- Combat disengages when target dies or leaves attack range + 0.5 tiles
- Damage dealt to adventurers generates mana (0.5x damage)

### Traps

#### Spike Traps

- Placed on floor tiles (needs solid ground below)
- Deal 30 damage on contact (45 if landing from a fall)
- Continuous damage with 1-second cooldown
- Hurt mobs too (20 damage/sec) — placement matters
- Adventurers learn spike locations and hop over them on return trips

#### Bear Traps

- Placed on floor tiles
- 25 damage on trigger + immobilizes for 2.5 seconds
- Rearms after 8 seconds
- Adventurers learn locations after triggering (avoid on future paths)

#### Arrow Traps

- Placed adjacent to a wall (auto-detects direction: fires away from wall)
- Needs exactly one wall on left or right side
- Fires a projectile every 3 seconds
- Arrows travel at 12 tiles/sec, deal 20 damage, max range 15 tiles
- Arrows stop on hitting walls
- Projectiles hit any adventurer in the same grid tile

## Economy

### Mana

- Mana is generated from adventurer **damage taken** (0.5x damage = mana)
- Mana is spent on dungeon modifications (placing traps, chests, digging)
- Dead adventurers = lost future income, not a win condition
- Starting mana: 50

### Vault and Loot

- The vault is the dungeon's stockpile of loot items
- Placing a chest takes 1 item from the vault to fill it
- Looted chests auto-refill from the vault after 5 seconds
- If vault is empty, chests cost mana to fill instead
- Looting a chest generates 5 mana

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

## Roadmap

Planned feature progression (each builds on the last):

1. **Traps and mobs** (done) — bear traps, arrow traps, bats, skeletons
2. **Adventurer AI overhaul** — state machine replacing ad-hoc if/else spaghetti
3. **Mana system improvements** — costs for placement, mana drain, richer economy
4. **Level system** — adventurer and mob progression, scaling difficulty
5. **Persistent adventurer teams** — regulars that return, remember the dungeon
6. **Spells for classes and mobs** — mage fireballs, healer heals, skeleton arrows
7. **Equipment and consumables** — gear drops, potions, adventurer loadouts

## Current Problems (pre-overhaul)

The adventurer AI is a pile of `if/else` checks in `update_adventurer` with no
clear state ownership. Every new feature (combat, traps, approach targets,
looting, fleeing) fights for control of the same movement code. Symptoms:

- Adventurers run through traps while chasing mobs
- Approach targets override hazard avoidance
- No clear priority between fighting, fleeing, looting, and exploring
- Adding any interaction breaks other interactions

The fix: a proper state machine where each state owns its movement and
pathfinding logic, with explicit transitions and priorities.

## Technical Principles

- Game logic is pure Python, fully testable, no rendering dependencies
- Renderer is a thin visual layer (currently raylib with Kenney Tiny Dungeon 16x16 sprites)
- Use uv for deps, ruff for code quality, pytest for tests
- Code-first: state as code, not editor-based
- All creatures share a common Entity base for combat compatibility and future PvP
