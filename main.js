import { GRID_W, GRID_H, TILE, STARTING_MANA, COSTS, SPAWN_RATE, MAX_ADVENTURERS, POLITICAL_RAID_THRESHOLD, ECON_RAID_THRESHOLD, STORAGE_KEY, T, isWalkableType } from "./src/constants.js";
import { MobRegistry, getMob, listMobs } from "./src/mobs.js";
import { makeMember, ClassRegistry, getClassSkills } from "./src/classes.js";

// Blink overlay constants for invalid actions
const BLINK_CYCLE_FRAMES = 4;
const BLINK_HIGH_ALPHA = 0.45;
const BLINK_LOW_ALPHA = 0.2;
const BLINK_HIGH_PHASE = 2;

(() => {
  // ----- Config (migrated to modules) -----

  // ----- State -----
  let tick = 0;
  let mana = STARTING_MANA;
  let politicalRisk = 0;
  let economicPressure = 0;
  let running = false;
  let tool = "room";
  let adventurers = [];
  let particles = [];
  let killsLastWindow = 0;
  let lootLastWindow = 0;
  let windowSize = 50;
  let cultOffer = null;
  let cultTimer = 0;
  let killBoostActive = 0;
  // Hover state for build preview
  let hoverX = -1, hoverY = -1;
  // Drag-build state for room placement
  let isMouseDown = false;
  let lastPlacedX = -1, lastPlacedY = -1;
  let suppressNextClickForRoom = false;
  // Blink overlays for invalid actions
  let blinks = [];

  // Regular memory pool (they come back with learned maps)
  const REGULAR_POOL_SIZE = 3;
  const RegularMemory = new Map(); // id -> {knowledge, exitKnown, exitPos, members}
  const RegularRoster = []; // ids we cycle through

  // Grid & mob data
  const grid = Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => T.WALL));
  // mobHp and mobType per tile for typed mobs
  const mobHp = Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => 0));
  const mobType = Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => null)); // string mob id
  // mob respawn timers (ticks until respawn), 0 when not pending
  const mobRespawn = Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => 0));

  // Pre-place entrance + exit
  grid[Math.floor(GRID_H / 2)][1] = T.ENTRANCE;
  grid[Math.floor(GRID_H / 2)][GRID_W - 2] = T.EXIT;
  for (let x = 2; x < GRID_W - 2; x++) grid[Math.floor(GRID_H / 2)][x] = T.ROOM;

  // ----- DOM -----
  const el = {
    mana: document.getElementById("mana"),
    tick: document.getElementById("tick"),
    political: document.getElementById("political"),
    economic: document.getElementById("economic"),
    tension: document.getElementById("tension"),
    start: document.getElementById("start"),
    pause: document.getElementById("pause"),
    step: document.getElementById("step"),
    reset: document.getElementById("reset"),
    grid: document.getElementById("grid"),
    log: document.getElementById("log"),
    cultOffer: document.getElementById("cult-offer"),
    cultAccept: document.getElementById("cult-accept"),
    cultDecline: document.getElementById("cult-decline"),
    overlayToggle: document.getElementById("overlayToggle"),
    partySelect: document.getElementById("partySelect"),
    cycleParty: document.getElementById("cycleParty"),
    clearMemory: document.getElementById("clearMemory"),
    forgetSelected: document.getElementById("forgetSelected"),
    highlightToggle: document.getElementById("highlightToggle"),
    partyInspector: document.getElementById("partyInspector"),
  };

  function updateToolSelection() {
    document.querySelectorAll('.toolbar button[data-tool]').forEach(btn => {
      btn.classList.toggle('selected', btn.dataset.tool === tool);
    });
  }
  document.querySelectorAll('.toolbar button[data-tool]').forEach(b => {
    b.addEventListener('click', () => { tool = b.dataset.tool; updateToolSelection(); });
  });
  el.start.onclick = () => running = true;
  el.pause.onclick = () => running = false;
  el.step.onclick = () => { running = false; advance(); render(); };
  el.reset.onclick = () => window.location.reload();
  el.cultAccept.onclick = () => acceptCult();
  el.cultDecline.onclick = () => declineCult();
  el.cycleParty.onclick = () => cyclePartySelection();
  el.clearMemory.onclick = () => clearSavedMemory();
  el.forgetSelected.onclick = () => forgetSelectedMemory();
  el.partySelect.onchange = () => updatePartyInspector();
  el.overlayToggle?.addEventListener("change", () => updatePartyInspector());
  el.highlightToggle?.addEventListener("change", () => { });

  const ctx = el.grid.getContext("2d");
  // hover tracking for build preview
  el.grid.addEventListener("mousemove", (e) => {
    const rect = el.grid.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / TILE);
    const y = Math.floor((e.clientY - rect.top) / TILE);
    if (x >= 0 && y >= 0 && x < GRID_W && y < GRID_H) { hoverX = x; hoverY = y; }
    else { hoverX = -1; hoverY = -1; }
    // Drag-to-build for rooms: place as we move while mouse is down
    if (isMouseDown && tool === "room" && x >= 0 && y >= 0 && x < GRID_W && y < GRID_H) {
      if (x !== lastPlacedX || y !== lastPlacedY) {
        tryPlaceRoom(x, y);
        lastPlacedX = x; lastPlacedY = y;
      }
    }
  });
  el.grid.addEventListener("mouseleave", () => { hoverX = -1; hoverY = -1; isMouseDown = false; });
  el.grid.addEventListener("mousedown", (e) => {
    const rect = el.grid.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / TILE);
    const y = Math.floor((e.clientY - rect.top) / TILE);
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return;
    isMouseDown = true;
    lastPlacedX = -1; lastPlacedY = -1;
    if (tool === "room") {
      // For room tool, start placement on mousedown to enable smooth dragging
      const placed = tryPlaceRoom(x, y);
      suppressNextClickForRoom = !!placed;
      lastPlacedX = x; lastPlacedY = y;
      e.preventDefault();
    }
  });
  window.addEventListener("mouseup", () => { isMouseDown = false; });

  function tryPlaceRoom(x, y) {
    if (mana < COSTS.room) return false;
    if (!canPlace("room", x, y)) return false; // do not blink on drag; just skip
    if (grid[y][x] === T.ROOM) return false; // nothing to do
    grid[y][x] = T.ROOM;
    mana -= COSTS.room;
    updateUI();
    return true;
  }

  // ----- Utilities -----
  function log(msg) {
    const line = document.createElement("div");
    line.textContent = msg;
    el.log.appendChild(line);
    el.log.scrollTop = el.log.scrollHeight;
  }
  function neighbors(x, y) { return [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]].filter(([a, b]) => a >= 0 && a < GRID_W && b >= 0 && b < GRID_H); }
  function rnd(a, b) { return Math.floor(Math.random() * (b - a + 1)) + a; }
  function getTileAt(x, y) {
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return T.WALL;
    return grid[y][x];
  }

  function findEntranceExit() {
    let ent = null, ext = null;
    for (let y = 0; y < GRID_H; y++) {
      for (let x = 0; x < GRID_W; x++) {
        const t = grid[y][x];
        if (t === T.ENTRANCE) ent = { x, y };
        if (t === T.EXIT) ext = { x, y };
      }
    }
    return { ent, ext };
  }

  function hasPathIfRemoved(rx, ry) {
    const { ent, ext } = findEntranceExit();
    if (!ent || !ext) return false; // fail-closed
    // helper BFS from entrance, optionally skipping one tile as if it were a wall
    function bfs(skipX = null, skipY = null) {
      const q = [ent];
      const seen = new Set([`${ent.x},${ent.y}`]);
      while (q.length) {
        const cur = q.shift();
        // Early exit if we reach the exit position
        if (cur.x === ext.x && cur.y === ext.y) break;
        for (const [nx, ny] of neighbors(cur.x, cur.y)) {
          if (skipX === nx && skipY === ny) continue;
          const t = grid[ny][nx];
          if (!isWalkableType(t)) continue;
          const k = `${nx},${ny}`;
          if (!seen.has(k)) { seen.add(k); q.push({ x: nx, y: ny }); }
        }
      }
      return seen;
    }
    const reachableNow = bfs();
    // Only allow removal if exit is currently reachable
    if (!reachableNow.has(`${ext.x},${ext.y}`)) return false;
    const reachableAfter = bfs(rx, ry);
    // must still reach exit
    if (!reachableAfter.has(`${ext.x},${ext.y}`)) return false;
    // ensure we didn't strand any walkable tile that was reachable before (except the removed tile itself)
    for (const key of reachableNow) {
      if (key === `${rx},${ry}`) continue;
      const [kx, ky] = key.split(",").map(Number);
      if (!isWalkableType(grid[ky][kx])) continue; // ignore if it changed to non-walkable (shouldn't happen here)
      if (!reachableAfter.has(key)) return false;
    }
    return true;
  }

  // ----- Build Interaction -----
  function canPlace(toolName, x, y) {
    const current = grid[y][x];
    if (toolName === "erase") return current !== T.ENTRANCE && current !== T.EXIT;
    if (!(toolName in COSTS)) return false;
    if (toolName === "room") {
      if (current === T.ENTRANCE || current === T.EXIT) return false;
      if (current === T.ROOM) return false; // no-op, don't allow spending on an existing room
      // must be adjacent to an existing room
      const adj = neighbors(x, y);
      const hasAdjRoom = adj.some(([ax, ay]) => grid[ay][ax] === T.ROOM);
      return hasAdjRoom;
    }
    // other builds require an existing room and empty of other specials
    return current === T.ROOM;
  }

  el.grid.addEventListener("click", (e) => {
    const rect = el.grid.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / TILE);
    const y = Math.floor((e.clientY - rect.top) / TILE);
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return;
    // Suppress the trailing click after a drag-based room placement
    if (tool === "room" && suppressNextClickForRoom) { suppressNextClickForRoom = false; return; }
    const current = grid[y][x];
    if (tool === "erase") {
      if (current === T.ENTRANCE || current === T.EXIT) {
        if (current === T.ENTRANCE) {
          log("Cannot erase entrance tile.");
        }
        blinks.push({ x, y, life: 10 });
        return;
      }
      if (current === T.MOB) {
        grid[y][x] = T.ROOM;
        mobType[y][x] = null;
        mobHp[y][x] = 0;
        mobRespawn[y][x] = 0;
        return;
      }
      if (current === T.TRAP || current === T.LOOT) { grid[y][x] = T.ROOM; return; }
      if (current === T.ROOM) {
        // only allow if path still exists after removal
        if (hasPathIfRemoved(x, y)) { grid[y][x] = T.WALL; return; }
        else {
          log("Cannot erase this room: it would block the path between entrance and exit.");
        }
        // invalid: blink red overlay
        blinks.push({ x, y, life: 10 });
        return;
      }
      return;
    }
    if (tool in COSTS) {
      const cost = COSTS[tool];
      if (mana < cost) { log(`Not enough mana for ${tool} (${cost})`); return; }
      let placed = false;
      if (!canPlace(tool, x, y)) {
        // invalid placement; do not spend mana
        blinks.push({ x, y, life: 10 });
        return;
      }
      if (tool === "room") { grid[y][x] = T.ROOM; placed = true; }
      else if (tool === "mob") {
        if (grid[y][x] === T.ROOM) {
          const mobDefs = listMobs();
          const chosen = mobDefs[Math.floor(Math.random() * mobDefs.length)];
          if (chosen) {
            grid[y][x] = T.MOB;
            mobType[y][x] = chosen.id;
            mobHp[y][x] = chosen.maxHp;
            mobRespawn[y][x] = 0;
            placed = true;
          }
        }
      }
      else if (tool === "trap") { if (grid[y][x] === T.ROOM) { grid[y][x] = T.TRAP; placed = true; } }
      else if (tool === "loot") { if (grid[y][x] === T.ROOM) { grid[y][x] = T.LOOT; placed = true; } }
      if (placed) { mana -= cost; updateUI(); }
    }
  });

  // ----- Adventurers -----
  const PARTY_KIND = { REGULAR: "Regulars", TRAVELER: "Traveler" };
  // class/traits are now provided by registry in src/classes.js

  // --- Combat config ---
  const MOB_RESPAWN_DELAY = 8; // ticks
  const MOB_RESPAWN_COST_FRAC = 0.5; // fraction of COSTS.mob mana to respawn

  function pickSkill(m) {
    const classSkills = getClassSkills(m.cls);
    const skills = classSkills.length ? classSkills : [{ name: "Strike", type: "phys", min: 4, max: 7, cost: 0 }];
    // prefer the stronger skill if affordable, else basic
    const strong = skills[1];
    if (strong && m.mp >= strong.cost) return strong;
    return skills[0];
  }

  function blankKnowledge() {
    return Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => ({ seen: false, type: -1, danger: 0, lastSeenTick: 0 })));
  }
  function copyKnowledge(k) {
    const src = Array.isArray(k) && k.length ? k : blankKnowledge();
    return src.map(row => row.map(c => ({ seen: !!c.seen, type: (c.type ?? -1), danger: (c.danger ?? 0), lastSeenTick: (c.lastSeenTick ?? 0) })));
  }

  // Build a fresh member from a saved template (level/cls/trait), healed with full MP
  function makeMemberFromTemplate(tmpl, spawnY) {
    const { level, cls, trait } = tmpl || {};
    const base = cls ? ClassRegistry.get(cls) : null;
    if (!base) {
      const m = makeMember(level || 1);
      m.x = 1; m.y = spawnY; return m;
    }
    const scale = 1 + (level - 1) * 0.25;
    const maxhp = Math.round(base.baseHp * scale);
    const mp = Math.round(base.baseMp * scale);
    return { hp: maxhp, maxhp, mp, cls, trait, level, x: 1, y: spawnY, loot: 0, bleeding: 0 };
  }

  // Reveal tiles around party members based on class bonuses (e.g., ranger)
  function reveal(party) {
    const base = 1;
    let bonus = 0;
    if (party.members.some(m => m.cls === "ranger")) bonus += 1;
    const R = base + bonus;
    party.members.forEach(m => {
      for (let dy = -R; dy <= R; dy++) {
        for (let dx = -R; dx <= R; dx++) {
          const x = m.x + dx, y = m.y + dy;
          if (x >= 0 && y >= 0 && x < GRID_W && y < GRID_H) {
            const cell = party.knowledge[y][x];
            cell.seen = true;
            cell.type = grid[y][x];
            cell.danger = (cell.type === T.TRAP ? 4 : 0) + (cell.type === T.MOB ? 2 : 0);
            cell.lastSeenTick = tick;
            if (grid[y][x] === T.EXIT) {
              party.exitKnown = true;
              party.exitPos = { x, y };
            }
          }
        }
      }
    });
  }

  // ---- Storage (Regular memory) ----
  function saveMemory() {
    const data = {
      roster: [...RegularRoster],
      memoryById: Object.fromEntries(
        [...RegularMemory.entries()].map(([id, mem]) => [id, {
          knowledge: mem.knowledge,
          exitKnown: !!mem.exitKnown,
          exitPos: mem.exitPos || null,
          members: Array.isArray(mem.members) ? mem.members : undefined,
        }])
      )
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) { /* ignore quota */ }
  }
  function loadMemory() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (Array.isArray(data.roster)) {
        data.roster.forEach(id => { if (!RegularRoster.includes(id)) RegularRoster.push(id); });
      }
      if (data.memoryById) {
        Object.keys(data.memoryById).forEach(id => {
          const mem = data.memoryById[id];
          RegularMemory.set(id, {
            knowledge: copyKnowledge(mem.knowledge),
            exitKnown: !!mem.exitKnown,
            exitPos: mem.exitPos ? { x: mem.exitPos.x, y: mem.exitPos.y } : null,
            members: Array.isArray(mem.members) ? mem.members.filter(m => m && m.cls && m.level) : undefined,
          });
        });
      }
      log("Loaded regular memory from localStorage.");
    } catch (e) { /* ignore parse errors */ }
  }
  function clearSavedMemory() {
    localStorage.removeItem(STORAGE_KEY);
    RegularMemory.clear();
    RegularRoster.splice(0, RegularRoster.length);
    updatePartySelect();
    log("Cleared saved memory.");
  }

  function forgetSelectedMemory() {
    const id = el.partySelect.value;
    if (!id) return;
    if (RegularMemory.has(id)) {
      RegularMemory.delete(id);
      const idx = RegularRoster.indexOf(id);
      if (idx >= 0) RegularRoster.splice(idx, 1);
      saveMemory();
      updatePartySelect();
      updatePartyInspector();
      log(`Forgot memory for ${id}.`);
    } else {
      log(`No saved memory for ${id}.`);
    }
  }

  function makeParty() {
    const regularSpawn = Math.random() < 0.6;
    const kind = regularSpawn ? PARTY_KIND.REGULAR : PARTY_KIND.TRAVELER;
    const spawnY = Math.floor(GRID_H / 2);
    let members = [];

    let id;
    let knowledge, exitKnown = false, exitPos = null;
    if (kind === PARTY_KIND.REGULAR && RegularRoster.length > 0 && Math.random() < 0.7) {
      id = RegularRoster[rnd(0, RegularRoster.length - 1)];
      const mem = RegularMemory.get(id);
      if (mem && mem.knowledge) {
        knowledge = copyKnowledge(mem.knowledge);
        exitKnown = !!mem.exitKnown;
        exitPos = mem.exitPos ? { x: mem.exitPos.x, y: mem.exitPos.y } : null;
        if (Array.isArray(mem.members) && mem.members.length > 0) {
          members = mem.members.map(t => makeMemberFromTemplate(t, spawnY));
        }
      } else {
        knowledge = blankKnowledge();
      }
    } else if (kind === PARTY_KIND.REGULAR) {
      id = Math.random().toString(36).slice(2, 7);
      if (!RegularRoster.includes(id)) {
        RegularRoster.push(id);
        if (RegularRoster.length > REGULAR_POOL_SIZE) RegularRoster.shift();
      }
      knowledge = blankKnowledge();
    } else {
      id = Math.random().toString(36).slice(2, 7);
      knowledge = blankKnowledge();
    }

    if (members.length === 0) {
      const size = rnd(2, 4);
      members = Array.from({ length: size }, () => {
        const level = rnd(1, 5);
        const m = makeMember(level);
        m.x = 1; m.y = spawnY; return m;
      });
    }

    const memberTemplates = members.map(m => ({ level: m.level, cls: m.cls, trait: m.trait }));
    const party = { id, kind, members, memberTemplates, alive: true, ticks: 0, knowledge, exitKnown, exitPos, returned: false, lastPos: { x: 1, y: spawnY } };
    log(`${kind} party ${id} enters.`);
    reveal(party);
    updatePartySelect();
    return party;
  }

  // ----- Pathing -----
  function tileAt(x, y) { return grid[y][x]; }

  function aStar(party, start, goal, allowDanger = true) {
    const { knowledge } = party;
    const key = (x, y) => `${x},${y}`;
    const open = new Set([key(start.x, start.y)]);
    const came = new Map();
    const g = new Map([[key(start.x, start.y), 0]]);
    const h = (x, y) => Math.abs(x - goal.x) + Math.abs(y - goal.y);
    const f = new Map([[key(start.x, start.y), h(start.x, start.y)]]);

    function lowestF() {
      let bestK = null, best = Infinity;
      for (const k of open) {
        const val = f.get(k) ?? Infinity;
        if (val < best) { best = val; bestK = k; }
      }
      return bestK;
    }

    while (open.size) {
      const currentK = lowestF();
      const [cx, cy] = currentK.split(",").map(Number);
      if (cx === goal.x && cy === goal.y) {
        const path = [{ x: cx, y: cy }];
        let k = currentK;
        while (came.has(k)) {
          k = came.get(k);
          const [px, py] = k.split(",").map(Number);
          path.push({ x: px, y: py });
        }
        path.reverse();
        return path;
      }
      open.delete(currentK);
      const cand = neighbors(cx, cy);
      for (const [nx, ny] of cand) {
        const row = knowledge[ny];
        const cell = row && row[nx];
        if (!cell || !cell.seen) continue;
        if (!isWalkableType(cell.type)) continue;
        const stepCost = 1 + (allowDanger ? cell.danger : 0);
        const tentative = (g.get(currentK) ?? Infinity) + stepCost;
        const nk = key(nx, ny);
        if (tentative < (g.get(nk) ?? Infinity)) {
          came.set(nk, currentK);
          g.set(nk, tentative);
          f.set(nk, tentative + h(nx, ny));
          open.add(nk);
        }
      }
    }
    return null;
  }

  function chooseTarget(party) {
    if (party.exitKnown && party.exitPos) { return { type: "exit", pos: party.exitPos }; }
    let best = null, bestDist = Infinity, bestAdj = null;
    for (let y = 0; y < GRID_H; y++) {
      for (let x = 0; x < GRID_W; x++) {
        const cell = party.knowledge[y][x];
        if (cell.seen) continue;
        const options = neighbors(x, y).filter(([ax, ay]) => {
          const c = party.knowledge[ay][ax];
          return c.seen && isWalkableType(c.type);
        });
        if (!options.length) continue;
        const mx = Math.round(party.members.reduce((s, m) => s + m.x, 0) / party.members.length);
        const my = Math.round(party.members.reduce((s, m) => s + m.y, 0) / party.members.length);
        const d = Math.abs(mx - x) + Math.abs(my - y);
        if (d < bestDist) {
          bestDist = d;
          best = { x, y };
          const [ax, ay] = options[0];
          bestAdj = { x: ax, y: ay };
        }
      }
    }
    if (best) return { type: "frontier", pos: bestAdj };
    return null;
  }

  function nextStepForMember(party, m) {
    const target = chooseTarget(party);
    let goal = target ? target.pos : null;
    if (!goal && party.exitKnown) goal = party.exitPos;
    let step = null;
    if (goal) {
      const path = aStar(party, { x: m.x, y: m.y }, goal, true);
      if (path && path.length >= 2) { step = path[1]; }
    }
    if (!step) {
      const options = neighbors(m.x, m.y).filter(([ax, ay]) => isWalkableType(tileAt(ax, ay)));
      if (options.length) {
        options.sort((A, B) => {
          const [ax, ay] = A, [bx, by] = B;
          const ca = party.knowledge[ay][ax], cb = party.knowledge[by][bx];
          const scoreA = (ca.seen ? 0 : -1) + (ca.danger ? -ca.danger : 0);
          const scoreB = (cb.seen ? 0 : -1) + (cb.danger ? -cb.danger : 0);
          return scoreB - scoreA + (Math.random() < 0.3 ? rnd(-1, 1) : 0);
        });
        const [nx, ny] = options[0];
        step = { x: nx, y: ny };
      } else {
        step = { x: m.x, y: m.y };
      }
    }
    return step;
  }

  // ----- Interactions -----
  function interact(party, m) {
    const t = tileAt(m.x, m.y);
    if (t === T.LOOT && Math.random() < 0.35) {
      m.loot += rnd(1, 3);
      mana += 1;
      lootLastWindow += 1;
      particles.push({ x: m.x, y: m.y, life: 12, color: "#ffd447" });
      if (Math.random() < 0.15) { grid[m.y][m.x] = T.ROOM; }
    }
    if (t === T.MOB) {
      resolveCombatAt(party, m.x, m.y);
    }
    if (t === T.TRAP && Math.random() < 0.35) {
      const dmg = rnd(6, 12);
      m.hp -= dmg;
      mana += Math.floor(dmg / 3);
      particles.push({ x: m.x, y: m.y, life: 10, color: "#ff5a47" });
      if (Math.random() < 0.1) grid[m.y][m.x] = T.ROOM;
    }
    if (m.bleeding > 0) { m.bleeding--; m.hp -= 1; mana += 1; }
  }
  function combatFleeChance(party, mobDef) {
    const avgHpPct = party.members.length ? party.members.reduce((s, mm) => s + Math.max(0, mm.hp / mm.maxhp), 0) / party.members.length : 0;
    let chance = 0.25;
    if (party.members.some(mm => mm.cls === "ranger")) chance += 0.15;
    if (party.members.some(mm => mm.cls === "assassin")) chance += 0.1;
    if (avgHpPct < 0.5) chance += 0.15; // more desperate when hurt
    chance = Math.max(0.05, Math.min(0.85, chance));
    return chance;
  }

  function resolveCombatAt(party, x, y) {
    const mobId = mobType[y][x];
    const def = getMob(mobId);
    if (!def) return;

    // Optionally attempt flee back to lastPos
    const attemptFlee = () => {
      const ch = combatFleeChance(party, def);
      if (Math.random() < ch && party.lastPos) {
        log(`[Combat] ${party.id} flees from ${def.name} to (${party.lastPos.x},${party.lastPos.y}).`);
        party.members.forEach(m => { m.x = party.lastPos.x; m.y = party.lastPos.y; });
        return true;
      }
      return false;
    };

    // Try to flee if badly hurt; otherwise 15% chance
    const avgHpPct = party.members.length ? party.members.reduce((s, mm) => s + Math.max(0, mm.hp / mm.maxhp), 0) / party.members.length : 0;
    if (avgHpPct < 0.4 || Math.random() < 0.15) {
      if (attemptFlee()) return;
      log(`[Combat] ${party.id} failed to flee!`);
    }

    log(`[Combat] ${party.id} engages ${def.name} at (${x},${y}).`);

    let mobCurrentHp = mobHp[y][x];
    const maxRounds = 12;
    for (let round = 1; round <= maxRounds; round++) {
      // party turn
      for (const m of party.members) {
        if (m.hp <= 0) continue;
        const skill = pickSkill(m);
        if (skill.type === "heal") {
          if (m.mp >= skill.cost) {
            m.mp -= skill.cost;
            const target = party.members.reduce((best, mm) => (mm.hp / mm.maxhp) < (best.hp / best.maxhp) ? mm : best, party.members[0]);
            const heal = rnd(skill.min, skill.max);
            const old = target.hp;
            target.hp = Math.min(target.maxhp, target.hp + heal);
            log(`[Combat] ${party.id} ${m.cls} casts ${skill.name} on ${target.cls} (+${target.hp - old} HP).`);
          }
          continue;
        }
        if (m.mp < skill.cost) {
          // fallback to basic if insufficient MP
          const basic = { name: "Strike", type: "phys", min: 3, max: 6, cost: 0 };
          const dmg = rnd(basic.min, basic.max);
          mobCurrentHp -= dmg;
          log(`[Combat] ${party.id} ${m.cls} uses ${basic.name} (-${dmg} HP to ${def.name}).`);
        } else {
          m.mp -= skill.cost;
          const dmg = rnd(skill.min, skill.max);
          mobCurrentHp -= dmg;
          log(`[Combat] ${party.id} ${m.cls} uses ${skill.name} (-${dmg} HP to ${def.name}).`);
        }
        if (mobCurrentHp <= 0) break;
      }
      if (mobCurrentHp <= 0) break;

      // mob turn: pick a random alive member
      const target = party.members.filter(mm => mm.hp > 0)[Math.floor(Math.random() * party.members.filter(mm => mm.hp > 0).length)];
      if (!target) break;
      const mobAtk = (def.attacks && def.attacks.length) ? def.attacks[Math.floor(Math.random() * def.attacks.length)] : { name: def.name + " Hit", min: 4, max: 8 };
      const dmgToMember = rnd(mobAtk.min, mobAtk.max);
      target.hp -= dmgToMember;
      mana += dmgToMember; // dungeon gains mana when adventurers lose HP
      log(`[Combat] ${def.name} uses ${mobAtk.name} on ${target.cls} (-${dmgToMember} HP).`);
      // party wipe check
      if (!party.members.some(mm => mm.hp > 0)) break;
    }

    // resolve outcomes
    if (mobCurrentHp <= 0) {
      log(`[Combat] ${def.name} is defeated.`);
      grid[y][x] = T.ROOM;
      mobType[y][x] = null;
      mobHp[y][x] = 0;
      mobRespawn[y][x] = MOB_RESPAWN_DELAY;
      mana += 5; // reward for kill
      particles.push({ x, y, life: 14, color: "#ff8aa8" });
      return;
    }

    if (!party.members.some(mm => mm.hp > 0)) {
      log(`[Combat] ${party.id} is wiped out by ${def.name}.`);
      // mark dead; members will be removed in the cleanup below
      return;
    }
  }

  // Apply just bleeding tick to a member (used for non-leaders)
  function bleedTick(m) {
    if (m.bleeding > 0) { m.bleeding--; m.hp -= 1; mana += 1; }
  }

  function resolveDeath(party, m) {
    if (m.hp > 0) return false;
    killsLastWindow++;
    let gain = 10;
    if (killBoostActive > 0) gain += 10;
    mana += gain;
    particles.push({ x: m.x, y: m.y, life: 14, color: "#ff8aa8" });
    return true;
  }

  function maybeExit(party, m) {
    if (tileAt(m.x, m.y) === T.EXIT) {
      mana += Math.floor(m.loot / 2);
      party.returned = true;
      return true;
    }
    return false;
  }
  // Party-level exit: if leader reaches exit, cash out all loot and remove the party
  function maybePartyExit(party, leader) {
    if (tileAt(leader.x, leader.y) === T.EXIT) {
      const totalLoot = party.members.reduce((s, mm) => s + (mm.loot || 0), 0);
      mana += Math.floor(totalLoot / 2);
      party.returned = true;
      party.alive = false;
      return true;
    }
    return false;
  }

  // ----- UI helpers -----
  function updatePartySelect() {
    const selected = el.partySelect.value;
    const options = [];
    // active parties
    for (const p of adventurers) {
      options.push({ id: p.id, label: `${p.kind} ${p.id} (active)` });
    }
    // known regulars from saved memory not currently active
    for (const id of RegularMemory.keys()) {
      if (!adventurers.some(p => p.id === id)) {
        options.push({ id, label: `Regulars ${id} (memory)` });
      }
    }
    el.partySelect.innerHTML = "";
    options.forEach(opt => {
      const o = document.createElement("option");
      o.value = opt.id; o.textContent = opt.label;
      el.partySelect.appendChild(o);
    });
    // keep previous selection if still present, else select first
    if (options.some(o => o.id === selected)) {
      el.partySelect.value = selected;
    } else if (options.length) {
      el.partySelect.value = options[0].id;
    }
    updatePartyInspector();
  }
  function cyclePartySelection() {
    const opts = el.partySelect.options;
    if (!opts.length) return;
    const i = el.partySelect.selectedIndex;
    el.partySelect.selectedIndex = (i + 1) % opts.length;
  }

  // ----- Game Loop -----
  function advance() {
    tick++;
    if (tick % SPAWN_RATE === 0 && adventurers.length < MAX_ADVENTURERS) {
      adventurers.push(makeParty());
    }
    adventurers.forEach(p => {
      p.ticks++;
      // pick leader (first alive member)
      const leader = p.members.find(m => m.hp > 0);
      if (!leader) { p.alive = false; return; }
      // Single step per party
      reveal(p);
      const step = nextStepForMember(p, leader);
      if (step) {
        // remember last position for flee
        p.lastPos = { x: leader.x, y: leader.y };
        p.members.forEach(m => { if (m.hp > 0) { m.x = step.x; m.y = step.y; } });
      }
      reveal(p);
      // One interaction per party at leader tile
      interact(p, leader);
      // Bleed ticks for other alive members
      p.members.forEach(m => { if (m !== leader && m.hp > 0) bleedTick(m); });

      // deaths cleanup
      p.members = p.members.filter(m => {
        if (m.hp <= 0) {
          if (p.kind === PARTY_KIND.REGULAR) politicalRisk += 6;
          else politicalRisk += 2;
          return !resolveDeath(p, m);
        }
        return true;
      });
      // party-level exit
      if (p.members.length > 0 && maybePartyExit(p, leader)) {
        // remove all members on exit
        p.members = [];
      }
      if (p.members.length === 0) p.alive = false;
    });
    adventurers.forEach(p => {
      if (p.kind === PARTY_KIND.REGULAR) {
        // Continuously checkpoint regular knowledge in-session; persisted to storage on window tick
        RegularMemory.set(p.id, {
          knowledge: copyKnowledge(p.knowledge),
          exitKnown: !!p.exitKnown,
          exitPos: p.exitPos ? { x: p.exitPos.x, y: p.exitPos.y } : null,
          members: Array.isArray(p.memberTemplates) ? p.memberTemplates : p.members.map(m => ({ level: m.level, cls: m.cls, trait: m.trait })),
        });
      }
    });
    adventurers = adventurers.filter(p => p.alive);

    if (tick % windowSize === 0) {
      const lootRate = lootLastWindow / windowSize;
      if (lootRate < 0.6) economicPressure += 8;
      else economicPressure = Math.max(0, economicPressure - 4);
      politicalRisk = Math.max(0, politicalRisk - 3);
      lootLastWindow = 0;
      killsLastWindow = 0;
      saveMemory(); // checkpoint memory periodically
    }

    cultTimer--;
    if (!cultOffer && cultTimer <= 0 && Math.random() < 0.04) {
      cultOffer = generateCultOffer();
      el.cultOffer.textContent = cultOffer.text;
      el.cultAccept.disabled = false;
      el.cultDecline.disabled = false;
      log(`[Cult] ${cultOffer.text}`);
    }
    if (killBoostActive > 0) killBoostActive--;

    // passive mob regeneration (typed)
    for (let y = 0; y < GRID_H; y++) {
      for (let x = 0; x < GRID_W; x++) {
        if (grid[y][x] === T.MOB) {
          const def = getMob(mobType[y][x] || "slime");
          if (!def) continue;
          if (mobHp[y][x] < def.maxHp) {
            mobHp[y][x] = Math.min(def.maxHp, mobHp[y][x] + (def.regen || 0));
          }
        } else if (mobRespawn[y][x] > 0) {
          mobRespawn[y][x]--;
          if (mobRespawn[y][x] <= 0) {
            const mobDefs = listMobs();
            const chosen = mobDefs[Math.floor(Math.random() * mobDefs.length)];
            if (chosen && grid[y][x] === T.ROOM) {
              grid[y][x] = T.MOB;
              mobType[y][x] = chosen.id;
              mobHp[y][x] = chosen.maxHp;
              log(`[Respawn] ${chosen.name} returns at (${x},${y}).`);
            } else {
              // retry next tick
              mobRespawn[y][x] = 1;
            }
          }
        }
      }
    }

    const tension = politicalRisk + economicPressure;
    el.tension.textContent = tension < 60 ? "Calm" : tension < 120 ? "Worried" : "Hostile";

    if (politicalRisk >= POLITICAL_RAID_THRESHOLD) {
      running = false; log("⚠ Political Raid! The guard leads a punitive expedition. (Game over)");
    }
    if (economicPressure >= ECON_RAID_THRESHOLD) {
      running = false; log("⚠ Economic Raid! Town deems you unprofitable. (Game over)");
    }

    updateUI();
    updatePartySelect();
    updatePartyInspector();
  }

  function selectedPartyOrMemory() {
    const id = el.partySelect.value;
    const party = adventurers.find(p => p.id === id) || null;
    const mem = party ? null : RegularMemory.get(id) || null;
    return { party, mem };
  }

  function updatePartyInspector() {
    if (!el.partyInspector) return;
    const { party, mem } = selectedPartyOrMemory();
    const container = el.partyInspector;
    container.innerHTML = "";
    if (!party && !mem) {
      container.textContent = "No party selected.";
      return;
    }
    const title = document.createElement("div");
    const id = el.partySelect.value;
    const kind = party ? party.kind : "Regulars";
    title.innerHTML = `<strong>${kind} ${id}</strong>`;
    container.appendChild(title);

    const stats = document.createElement("div");
    const ticks = party ? party.ticks : "—";
    const exitKnown = party ? party.exitKnown : (mem?.exitKnown ? "yes" : "no");
    const knowledge = party ? party.knowledge : mem?.knowledge;
    let exploredPct = "—";
    if (knowledge) {
      let seen = 0, total = 0;
      for (let y = 0; y < GRID_H; y++) {
        for (let x = 0; x < GRID_W; x++) {
          if (grid[y][x] === T.ROOM) {
            total++;
            if (knowledge[y][x]?.seen) seen++;
          }
        }
      }
      exploredPct = total > 0 ? Math.round((seen / total) * 100) + "%" : "0%";
    }
    const exitPosStr = (party?.exitPos || mem?.exitPos) ? `@(${(party?.exitPos || mem?.exitPos).x},${(party?.exitPos || mem?.exitPos).y})` : "";
    stats.textContent = `ticks: ${ticks} | exitKnown: ${exitKnown} ${exitPosStr} | explored: ${exploredPct}`;
    container.appendChild(stats);

    const list = document.createElement("div");
    list.style.marginTop = "6px";
    const members = party ? party.members : [];
    if (members.length === 0 && party) {
      const dead = document.createElement("div");
      dead.textContent = "No surviving members.";
      list.appendChild(dead);
    }
    members.forEach((m, i) => {
      const row = document.createElement("div");
      const hpPct = Math.max(0, Math.round((m.hp / m.maxhp) * 100));
      row.textContent = `#${i + 1} L${m.level} ${m.cls} [HP ${m.hp}/${m.maxhp} ${hpPct}% | MP ${m.mp}] trait: ${m.trait} @(${m.x},${m.y}) loot:${m.loot}`;
      list.appendChild(row);
    });
    container.appendChild(list);

    // If viewing saved memory, render saved roster summary
    if (!party && mem && Array.isArray(mem.members)) {
      const roster = document.createElement("div");
      roster.style.marginTop = "6px";
      roster.textContent = `Saved roster: ${mem.members.map((t, i) => `#${i + 1} L${t.level} ${t.cls} (${t.trait})`).join(", ")}`;
      container.appendChild(roster);
    }
  }

  function generateCultOffer() {
    if (Math.random() < 0.5) {
      return {
        kind: "mark_regulars",
        text: "Spill noble blood: slay a Regular party within 40 ticks for +20 mana per kill. Risk +10 politics.",
        duration: 40,
        onAccept() { politicalRisk += 10; killBoostActive = 40; }
      };
    } else {
      return {
        kind: "withhold_loot",
        text: "Starve the markets: remove 3 loot nodes within 40 ticks for +60 mana now. Risk +15 economics.",
        duration: 40,
        onAccept() {
          economicPressure += 15;
          mana += 60;
          let removed = 0;
          for (let y = 0; y < GRID_H; y++) {
            for (let x = 0; x < GRID_W; x++) {
              if (grid[y][x] === T.LOOT && removed < 3) { grid[y][x] = T.ROOM; removed++; }
            }
          }
        }
      };
    }
  }
  function acceptCult() { if (!cultOffer) return; cultOffer.onAccept(); el.cultOffer.textContent = "Offer active."; el.cultAccept.disabled = true; el.cultDecline.disabled = true; cultTimer = rnd(80, 140); updateUI(); }
  function declineCult() { cultOffer = null; el.cultOffer.textContent = "No offer."; el.cultAccept.disabled = true; el.cultDecline.disabled = true; cultTimer = rnd(80, 140); }

  function updateUI() {
    el.mana.textContent = mana;
    el.tick.textContent = tick;
    el.political.textContent = politicalRisk;
    el.economic.textContent = economicPressure;
  }

  // ----- Rendering -----
  function render() {
    const ctx = el.grid.getContext("2d");
    ctx.clearRect(0, 0, el.grid.width, el.grid.height);
    // tiles
    for (let y = 0; y < GRID_H; y++) {
      for (let x = 0; x < GRID_W; x++) {
        const t = grid[y][x];
        ctx.fillStyle = {
          [T.WALL]: "#090c10",
          [T.ROOM]: "#1e293b",
          [T.MOB]: "#102c20",
          [T.TRAP]: "#2a1616",
          [T.LOOT]: "#2a2410",
          [T.ENTRANCE]: "#142637",
          [T.EXIT]: "#231c38",
        }[t];
        ctx.fillRect(x * TILE, y * TILE, TILE - 1, TILE - 1);
        if (t === T.MOB) {
          const def = getMob(mobType[y][x] || "slime");
          drawDot(x, y, def?.color || "#47ff88");
        }
        if (t === T.TRAP) { drawDot(x, y, "#ff5a47"); }
        if (t === T.LOOT) { drawDot(x, y, "#ffd447"); }
        if (t === T.ENTRANCE) { drawDot(x, y, "#7cc1ff"); }
        if (t === T.EXIT) { drawDot(x, y, "#b084ff"); }
      }
    }

    // build hover preview (drawn over tiles, under parties)
    if (hoverX >= 0 && hoverY >= 0) {
      let valid = canPlace(tool, hoverX, hoverY);
      // refine validity for erase on rooms: must preserve entrance-exit path
      if (tool === "erase") {
        const t = getTileAt(hoverX, hoverY);
        if (t === T.ROOM) {
          valid = valid && hasPathIfRemoved(hoverX, hoverY);
        }
      }
      let color = "#ffffff";
      if (tool === "room") color = "#1e293b";
      else if (tool === "mob") color = "#102c20";
      else if (tool === "trap") color = "#2a1616";
      else if (tool === "loot") color = "#2a2410";
      else if (tool === "erase") color = "#333"
      if (!valid) color = "#6b2222";
      ctx.save();
      ctx.globalAlpha = 0.45;
      ctx.fillStyle = color;
      ctx.fillRect(hoverX * TILE, hoverY * TILE, TILE - 1, TILE - 1);
      if (!valid) {
        ctx.globalAlpha = 1;
        ctx.strokeStyle = "#b33";
        ctx.lineWidth = 2;
        ctx.strokeRect(hoverX * TILE + 1, hoverY * TILE + 1, TILE - 3, TILE - 3);
      }
      ctx.restore();
    }
    // adventurers rendered as a single marker per party
    const selectedId = el.partySelect.value;
    const highlight = !!el.highlightToggle?.checked;
    adventurers.forEach(p => {
      if (p.members.length === 0) return;
      const leader = p.members[0];
      const isSelected = highlight && p.id === selectedId;
      ctx.fillStyle = isSelected ? "#ffffff" : "#9ce2ff";
      ctx.fillRect(leader.x * TILE + 8, leader.y * TILE + 8, TILE - 16, TILE - 16);
      if (isSelected) {
        ctx.strokeStyle = "#ffd447";
        ctx.lineWidth = 2;
        ctx.strokeRect(leader.x * TILE + 7, leader.y * TILE + 7, TILE - 14, TILE - 14);
      }
    });
    // draw names and aggregated health bars
    adventurers.forEach(p => {
      if (p.members.length > 0) {
        const m0 = p.members[0];
        ctx.fillStyle = "#ffffff";
        ctx.font = "12px sans-serif";
        ctx.fillText(p.id, m0.x * TILE, m0.y * TILE - 2);

        const totalHp = p.members.reduce((s, m) => s + Math.max(0, m.hp), 0);
        const totalMax = p.members.reduce((s, m) => s + m.maxhp, 0);
        const ratio = totalMax > 0 ? totalHp / totalMax : 0;
        const barWidth = TILE - 4;
        const x0 = m0.x * TILE + 2;
        const y0 = m0.y * TILE - 6;
        ctx.fillStyle = "#555";
        ctx.fillRect(x0, y0, barWidth, 4);
        ctx.fillStyle = "#f00";
        ctx.fillRect(x0, y0, ratio * barWidth, 4);
      }
    });

    // overlay: selected party knowledge
    if (el.overlayToggle.checked) {
      const id = el.partySelect.value;
      let knowledge = null;
      // active party first
      const party = adventurers.find(p => p.id === id);
      if (party) knowledge = party.knowledge;
      else {
        const mem = RegularMemory.get(id);
        if (mem) knowledge = mem.knowledge;
      }
      if (knowledge) {
        ctx.save();
        // shade unknown tiles
        ctx.globalAlpha = 0.55;
        ctx.fillStyle = "#000000";
        for (let y = 0; y < GRID_H; y++) {
          for (let x = 0; x < GRID_W; x++) {
            const c = knowledge[y][x];
            if (!c.seen) {
              ctx.fillRect(x * TILE, y * TILE, TILE - 1, TILE - 1);
            }
          }
        }
        // age-based dimming for seen tiles (stale memory darker)
        for (let y = 0; y < GRID_H; y++) {
          for (let x = 0; x < GRID_W; x++) {
            const c = knowledge[y][x];
            if (!c.seen) continue;
            const age = Math.max(0, tick - (c.lastSeenTick || 0));
            if (age <= 0) continue;
            const alpha = Math.min(0.35, age / 120); // older -> darker
            if (alpha > 0.01) {
              ctx.globalAlpha = alpha;
              ctx.fillStyle = "#000000";
              ctx.fillRect(x * TILE, y * TILE, TILE - 1, TILE - 1);
            }
          }
        }
        ctx.globalAlpha = 1;
        // draw known hazards/points
        for (let y = 0; y < GRID_H; y++) {
          for (let x = 0; x < GRID_W; x++) {
            const c = knowledge[y][x];
            if (!c.seen) continue;
            if (c.type === T.TRAP) drawDot(x, y, "#ff5a47");
            if (c.type === T.MOB) drawDot(x, y, "#47ff88");
            if (c.type === T.LOOT) drawDot(x, y, "#ffd447");
            if (c.type === T.ENTRANCE) drawDot(x, y, "#7cc1ff");
            if (c.type === T.EXIT) drawDot(x, y, "#b084ff");
          }
        }
        ctx.restore();
      }
    }

    // particles
    particles = particles.filter(pt => {
      pt.life--;
      if (pt.life <= 0) return false;
      ctx.globalAlpha = pt.life / 14;
      ctx.fillStyle = pt.color;
      ctx.fillRect(pt.x * TILE + 12, pt.y * TILE + 12, TILE - 24, TILE - 24);
      ctx.globalAlpha = 1;
      return true;
    });
    // blinks for invalid actions
    blinks = blinks.filter(b => {
      b.life--;
      if (b.life <= 0) return false;
      const alpha = (b.life % BLINK_CYCLE_FRAMES) < BLINK_HIGH_PHASE ? BLINK_HIGH_ALPHA : BLINK_LOW_ALPHA;
      ctx.globalAlpha = alpha;
      ctx.fillStyle = "#b33";
      ctx.fillRect(b.x * TILE, b.y * TILE, TILE - 1, TILE - 1);
      ctx.globalAlpha = 1;
      return true;
    });
    requestAnimationFrame(render);
  }

  function drawDot(x, y, color) {
    const c = ctx;
    c.fillStyle = color;
    c.beginPath();
    c.arc(x * TILE + TILE / 2, y * TILE + TILE / 2, 5, 0, Math.PI * 2);
    c.fill();
  }

  function loop() { if (running) advance(); setTimeout(loop, 150); }

  // Init
  loadMemory();
  updatePartySelect();
  updateUI();
  // initialize selected build tool button UI
  updateToolSelection();
  loop();
  render();
})();
