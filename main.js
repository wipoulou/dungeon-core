import { GRID_W, GRID_H, TILE, STARTING_MANA, COSTS, SPAWN_RATE, MAX_ADVENTURERS, POLITICAL_RAID_THRESHOLD, ECON_RAID_THRESHOLD, STORAGE_KEY, T, isWalkableType } from "./src/constants.js";
import { MobRegistry, getMob, listMobs } from "./src/mobs.js";
import { makeMember } from "./src/classes.js";

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

  // Regular memory pool (they come back with learned maps)
  const REGULAR_POOL_SIZE = 3;
  const RegularMemory = new Map(); // id -> {knowledge, exitKnown, exitPos}
  const RegularRoster = []; // ids we cycle through

  // Grid & mob data
  const grid = Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => T.WALL));
  // mobHp and mobType per tile for typed mobs
  const mobHp = Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => 0));
  const mobType = Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => null)); // string mob id

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
  highlightToggle: document.getElementById("highlightToggle"),
  partyInspector: document.getElementById("partyInspector"),
  };

  document.querySelectorAll('.toolbar button[data-tool]').forEach(b => {
    b.addEventListener('click', () => tool = b.dataset.tool);
  });
  el.start.onclick = () => running = true;
  el.pause.onclick = () => running = false;
  el.step.onclick = () => { running = false; advance(); render(); };
  el.reset.onclick = () => window.location.reload();
  el.cultAccept.onclick = () => acceptCult();
  el.cultDecline.onclick = () => declineCult();
  el.cycleParty.onclick = () => cyclePartySelection();
  el.clearMemory.onclick = () => clearSavedMemory();
  el.partySelect.onchange = () => updatePartyInspector();
  el.overlayToggle?.addEventListener("change", () => updatePartyInspector());
  el.highlightToggle?.addEventListener("change", () => {});

  const ctx = el.grid.getContext("2d");

  // ----- Utilities -----
  function log(msg) {
    const line = document.createElement("div");
    line.textContent = msg;
    el.log.appendChild(line);
    el.log.scrollTop = el.log.scrollHeight;
  }
  function neighbors(x, y) { return [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]].filter(([a, b]) => a >= 0 && a < GRID_W && b >= 0 && b < GRID_H); }
  function rnd(a, b) { return Math.floor(Math.random() * (b - a + 1)) + a; }

  // ----- Build Interaction -----
  el.grid.addEventListener("click", (e) => {
    const rect = el.grid.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / TILE);
    const y = Math.floor((e.clientY - rect.top) / TILE);
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return;
    const current = grid[y][x];
    if (tool === "erase") {
      if (current !== T.ENTRANCE && current !== T.EXIT) { grid[y][x] = T.WALL; }
      return;
    }
    if (tool in COSTS) {
      const cost = COSTS[tool];
      if (mana < cost) { log(`Not enough mana for ${tool} (${cost})`); return; }
      if (current === T.ENTRANCE || current === T.EXIT) return;
      if (tool === "room") { grid[y][x] = T.ROOM; }
      else if (tool === "mob") {
        if (grid[y][x] === T.ROOM) {
          // Pick first registered mob type for now
          const mobDefs = listMobs();
          const chosen = mobDefs[0];
          if (chosen) {
            grid[y][x] = T.MOB;
            mobType[y][x] = chosen.id;
            mobHp[y][x] = chosen.maxHp;
          }
        }
      }
      else if (tool === "trap") { if (grid[y][x] === T.ROOM) grid[y][x] = T.TRAP; }
      else if (tool === "loot") { if (grid[y][x] === T.ROOM) grid[y][x] = T.LOOT; }
      mana -= cost;
    }
  });

  // ----- Adventurers -----
  const PARTY_KIND = { REGULAR: "Regulars", TRAVELER: "Traveler" };
  // class/traits are now provided by registry in src/classes.js

  function blankKnowledge() {
    return Array.from({ length: GRID_H }, () => Array.from({ length: GRID_W }, () => ({ seen: false, type: -1, danger: 0 })));
  }
  function copyKnowledge(k) {
    const src = Array.isArray(k) && k.length ? k : blankKnowledge();
    return src.map(row => row.map(c => ({ seen: !!c.seen, type: (c.type ?? -1), danger: (c.danger ?? 0) })));
  }

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
          exitPos: mem.exitPos || null
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
            exitPos: mem.exitPos ? { x: mem.exitPos.x, y: mem.exitPos.y } : null
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

  function makeParty() {
    const regularSpawn = Math.random() < 0.6;
    const kind = regularSpawn ? PARTY_KIND.REGULAR : PARTY_KIND.TRAVELER;
    const size = rnd(2, 4);
    const members = Array.from({ length: size }, () => {
      const level = rnd(1, 5);
      const m = makeMember(level);
      m.x = 1;
      m.y = Math.floor(GRID_H / 2);
      return m;
    });

    let id;
    let knowledge, exitKnown = false, exitPos = null;
    if (kind === PARTY_KIND.REGULAR && RegularRoster.length > 0 && Math.random() < 0.7) {
      id = RegularRoster[rnd(0, RegularRoster.length - 1)];
      const mem = RegularMemory.get(id);
      if (mem && mem.knowledge) {
        knowledge = copyKnowledge(mem.knowledge);
        exitKnown = !!mem.exitKnown;
        exitPos = mem.exitPos ? { x: mem.exitPos.x, y: mem.exitPos.y } : null;
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

    const party = { id, kind, members, alive: true, ticks: 0, knowledge, exitKnown, exitPos, returned: false };
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
      const id = mobType[m.y][m.x] || "slime";
      const def = getMob(id) || { maxHp: 20 };
      const dmgToMob = rnd(4, 10);
      mobHp[m.y][m.x] -= dmgToMob;
      particles.push({ x: m.x, y: m.y, life: 12, color: "#7fffd4" });
      if (mobHp[m.y][m.x] <= 0) {
        grid[m.y][m.x] = T.ROOM;
        mobType[m.y][m.x] = null;
        mana += 5;
        particles.push({ x: m.x, y: m.y, life: 14, color: "#ff8aa8" });
      } else {
        // optional: bleed retaliation could go here based on def
      }
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

  // ----- UI helpers -----
  function updatePartySelect() {
    const selected = el.partySelect.value;
    const options = [];
    // active parties
    for (const p of adventurers) {
      options.push({ id: p.id, label: `${p.kind} ${p.id} (active)` });
    }
    // known regulars not currently active
    for (const id of RegularRoster) {
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
      p.members.forEach(m => {
        if (m.hp <= 0) return;
        reveal(p);
        const step = nextStepForMember(p, m);
        if (step) { m.x = step.x; m.y = step.y; }
        reveal(p);
        interact(p, m);
      });
      p.members = p.members.filter(m => {
        if (m.hp <= 0) {
          if (p.kind === PARTY_KIND.REGULAR) politicalRisk += 6;
          else politicalRisk += 2;
          return !resolveDeath(p, m);
        }
        if (maybeExit(p, m)) { return false; }
        return true;
      });
      if (p.members.length === 0) p.alive = false;
    });
    adventurers.forEach(p => {
      if (p.kind === PARTY_KIND.REGULAR && (p.returned || p.exitKnown)) {
        RegularMemory.set(p.id, {
          knowledge: copyKnowledge(p.knowledge),
          exitKnown: !!p.exitKnown,
          exitPos: p.exitPos ? { x: p.exitPos.x, y: p.exitPos.y } : null
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
    stats.textContent = `ticks: ${ticks} | exitKnown: ${exitKnown}`;
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
  function acceptCult() { if (!cultOffer) return; cultOffer.onAccept(); el.cultOffer.textContent = "Offer active."; el.cultAccept.disabled = true; el.cultDecline.disabled = true; cultTimer = rnd(80, 140); }
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
    // adventurers
    const selectedId = el.partySelect.value;
    const highlight = !!el.highlightToggle?.checked;
    adventurers.forEach(p => {
      p.members.forEach(m => {
        const isSelected = highlight && p.id === selectedId;
        ctx.fillStyle = isSelected ? "#ffffff" : "#9ce2ff";
        ctx.fillRect(m.x * TILE + 8, m.y * TILE + 8, TILE - 16, TILE - 16);
        if (isSelected) {
          // subtle outline
          ctx.strokeStyle = "#ffd447";
          ctx.lineWidth = 2;
          ctx.strokeRect(m.x * TILE + 7, m.y * TILE + 7, TILE - 14, TILE - 14);
        }
      });
    });
    // draw names and health bars
    adventurers.forEach(p => {
      if (p.members.length > 0) {
        const m0 = p.members[0];
        ctx.fillStyle = "#ffffff";
        ctx.font = "12px sans-serif";
        ctx.fillText(p.id, m0.x * TILE, m0.y * TILE - 2);
      }
      p.members.forEach(m => {
        const barWidth = TILE - 4;
        const x0 = m.x * TILE + 2;
        const y0 = m.y * TILE - 6;
        ctx.fillStyle = "#555";
        ctx.fillRect(x0, y0, barWidth, 4);
        ctx.fillStyle = "#f00";
        ctx.fillRect(x0, y0, (m.hp / m.maxhp) * barWidth, 4);
        ctx.fillStyle = "#fff";
        ctx.font = "8px sans-serif";
        ctx.fillText(`L${m.level}`, x0, y0 - 2);
      });
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
  loop();
  render();
  log("v2.2: Overlay of a selected party's known map (toggle in Debug) + Regular memory persisted to localStorage.");
})();
