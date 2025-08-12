import { GRID_W, GRID_H, T, isWalkableType } from "./constants.js";
export function avgHpPct(party) {
    if (!party.members || !party.members.length) return 0;
    return party.members.reduce((s, m) => s + (m.hp / m.maxhp), 0) / party.members.length;
}
export function totalLoot(party) {
    return party.members.reduce((s, m) => s + m.loot, 0);
}
export function findNearestLoot(party) {
    let best = null, bestDist = Infinity;
    for (let y = 0; y < GRID_H; y++) {
        for (let x = 0; x < GRID_W; x++) {
            const cell = party.knowledge[y][x];
            if (cell?.seen && cell.type === T.LOOT && isWalkableType(cell.type)) {
                // Manhattan distance from party centroid; you could use aStar() instead
                const mx = party.members.reduce((s, m) => s + m.x, 0) / party.members.length;
                const my = party.members.reduce((s, m) => s + m.y, 0) / party.members.length;
                const d = Math.abs(mx - x) + Math.abs(my - y);
                if (d < bestDist) { bestDist = d; best = { x, y }; }
            }
        }
    }
    return best;
}

// General utilities moved from main.js
export function neighbors(x, y) {
    return [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]].filter(([a, b]) => a >= 0 && a < GRID_W && b >= 0 && b < GRID_H);
}

export function rnd(a, b) {
    return Math.floor(Math.random() * (b - a + 1)) + a;
}

export function getTileAt(grid, x, y) {
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return T.WALL;
    return grid[y][x];
}

export function findEntranceExit(grid) {
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

export function hasPathIfRemoved(grid, rx, ry) {
    const { ent, ext } = findEntranceExit(grid);
    if (!ent || !ext) return false;
    function bfs(skipX = null, skipY = null) {
        const q = [ent];
        const seen = new Set([`${ent.x},${ent.y}`]);
        while (q.length) {
            const cur = q.shift();
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
    if (!reachableNow.has(`${ext.x},${ext.y}`)) return false;
    const reachableAfter = bfs(rx, ry);
    if (!reachableAfter.has(`${ext.x},${ext.y}`)) return false;
    for (const key of reachableNow) {
        if (key === `${rx},${ry}`) continue;
        const [kx, ky] = key.split(",").map(Number);
        if (!isWalkableType(grid[ky][kx])) continue;
        if (!reachableAfter.has(key)) return false;
    }
    return true;
}

export function tileTypeName(t) {
    return {
        [T.WALL]: "Wall",
        [T.ROOM]: "Room",
        [T.MOB]: "Mob",
        [T.TRAP]: "Trap",
        [T.LOOT]: "Loot",
        [T.ENTRANCE]: "Entrance",
        [T.EXIT]: "Teleporter",
    }[t] || "Unknown";
}

export function drawDot(ctx, x, y, color, TILE) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x * TILE + TILE / 2, y * TILE + TILE / 2, 5, 0, Math.PI * 2);
    ctx.fill();
}