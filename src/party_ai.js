
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

function chooseFrontier(party) {
    let best = null;
    let bestScore = Infinity;
    const hWeight = 1.5; // hazard weight; tune later
    for (let y = 0; y < GRID_H; y++) {
        for (let x = 0; x < GRID_W; x++) {
            const cell = party.knowledge[y][x];
            if (cell?.seen) continue;
            // must be adjacent to at least one seen, walkable tile
            const adj = neighbors(x, y).filter(([ax, ay]) => {
                const c = party.knowledge[ay]?.[ax];
                return c?.seen && isWalkableType(c.type);
            });
            if (!adj.length) continue;
            // compute distance to party centroid
            const mx = party.members.reduce((s, m) => s + m.x, 0) / party.members.length;
            const my = party.members.reduce((s, m) => s + m.y, 0) / party.members.length;
            const d = Math.abs(mx - x) + Math.abs(my - y);
            // compute average danger of adjacent known cells
            let danger = 0;
            adj.forEach(([ax, ay]) => { danger += (party.knowledge[ay][ax].danger || 0); });
            danger /= adj.length;
            const score = d + hWeight * danger;
            if (score < bestScore) {
                bestScore = score;
                // step to one of the adjacent known tiles
                const [nx, ny] = adj[0];
                best = { type: "frontier", pos: { x: nx, y: ny } };
            }
        }
    }
    return best;
}

function chooseTarget(party) {
    const avgHp = avgHpPct(party);
    const loot = totalLoot(party);
    // if we know the exit and we’re weak or rich, bail
    if (party.exitKnown && (avgHp < 0.3 || loot >= 5 * party.members.length)) {
        return { type: "exit", pos: party.exitPos };
    }
    // if we know loot within reach, go grab it
    const lootPos = findNearestLoot(party);
    if (lootPos) return { type: "loot", pos: lootPos };
    // otherwise explore the safest frontier
    const frontier = chooseFrontier(party);
    if (frontier) return frontier;
    // default: wander
    return null;
}

export function nextStepForMember(party, m) {
    const target = chooseTarget(party);
    let goal = target ? target.pos : null;
    // dynamic danger allowance: healthy parties will risk traps
    const allowDanger = avgHpPct(party) > 0.5;
    let step = null;
    if (goal) {
        const path = aStar(party, { x: m.x, y: m.y }, goal, allowDanger);
        if (path && path.length >= 2) {
            step = path[1];
        }
    }
    if (!step) {
        // fallback: prefer unseen & less dangerous neighbors
        const options = neighbors(m.x, m.y).filter(([ax, ay]) => isWalkableType(tileAt(ax, ay)));
        if (options.length) {
            options.sort((A, B) => {
                const [ax, ay] = A, [bx, by] = B;
                const ca = party.knowledge[ay][ax], cb = party.knowledge[by][bx];
                // unseen tiles are attractive; higher danger is undesirable
                const scoreA = (ca?.seen ? 0 : -1) + (ca?.danger || 0);
                const scoreB = (cb?.seen ? 0 : -1) + (cb?.danger || 0);
                return scoreA - scoreB;
            });
            const [nx, ny] = options[0];
            step = { x: nx, y: ny };
        } else {
            step = { x: m.x, y: m.y };
        }
    }
    return step;
}