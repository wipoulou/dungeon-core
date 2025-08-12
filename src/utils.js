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