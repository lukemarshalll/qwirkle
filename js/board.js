// board.js
// The Qwirkle board: an unbounded grid of "x,y" -> Tile.
//
// A "move" is an array of [x, y, tile] triples representing everything a
// player places down on a single turn. This module validates moves
// against the real Qwirkle placement rules and computes the resulting
// score. Direct port of board.py.

function posKey(x, y) {
  return `${x},${y}`;
}

function parseKey(key) {
  const [x, y] = key.split(",").map(Number);
  return [x, y];
}

export class Board {
  constructor() {
    this.cells = new Map(); // "x,y" -> Tile
  }

  isEmpty() {
    return this.cells.size === 0;
  }

  get(x, y) {
    return this.cells.get(posKey(x, y)) || null;
  }

  occupied(x, y) {
    return this.cells.has(posKey(x, y));
  }

  // ---------- line helpers ----------

  // Returns the contiguous run of occupied cells through (x, y) in
  // `direction` ('h' = varying x, same y; 'v' = varying y, same x), as a
  // sorted array of {x, y, tile}.
  static _lineCells(tempCells, x, y, direction) {
    const step = direction === "h" ? [1, 0] : [0, 1];
    const cellsList = [[x, y]];

    let cx = x - step[0], cy = y - step[1];
    while (tempCells.has(posKey(cx, cy))) {
      cellsList.unshift([cx, cy]);
      cx -= step[0];
      cy -= step[1];
    }

    cx = x + step[0]; cy = y + step[1];
    while (tempCells.has(posKey(cx, cy))) {
      cellsList.push([cx, cy]);
      cx += step[0];
      cy += step[1];
    }

    return cellsList.map(([px, py]) => ({ x: px, y: py, tile: tempCells.get(posKey(px, py)) }));
  }

  // A line (array of {x,y,tile}) is valid if every tile shares a color
  // (with all-distinct shapes) or shares a shape (with all distinct
  // colors), has no duplicate tile, and is at most 6 long.
  static _lineValid(line) {
    const tiles = line.map((c) => c.tile);
    if (tiles.length > 6) return false;
    const sigs = new Set(tiles.map((t) => t.sig()));
    if (sigs.size !== tiles.length) return false; // duplicate tile in the line
    const colors = new Set(tiles.map((t) => t.color));
    const shapes = new Set(tiles.map((t) => t.shape));
    return colors.size === 1 || shapes.size === 1;
  }

  // ---------- validation ----------

  // move: array of [x, y, tile]
  // Returns { ok: true, lines } or { ok: false, reason }
  // `lines` is the list of resulting lines (each an array of {x,y,tile})
  // touched by this move.
  validateMove(move) {
    if (!move || move.length === 0) {
      return { ok: false, reason: "No tiles placed." };
    }

    const positions = move.map(([x, y]) => [x, y]);
    const posSet = new Set(positions.map(([x, y]) => posKey(x, y)));
    if (posSet.size !== positions.length) {
      return { ok: false, reason: "Can't place two tiles on the same square." };
    }

    for (const [x, y] of positions) {
      if (this.occupied(x, y)) {
        return { ok: false, reason: `Square (${x}, ${y}) is already occupied.` };
      }
    }

    const tempCells = new Map(this.cells);
    for (const [x, y, t] of move) tempCells.set(posKey(x, y), t);

    let mainDir = null;
    if (move.length > 1) {
      const xs = new Set(positions.map(([x]) => x));
      const ys = new Set(positions.map(([, y]) => y));
      if (xs.size === 1) mainDir = "v";
      else if (ys.size === 1) mainDir = "h";
      else return { ok: false, reason: "All tiles in a turn must be placed in a single straight line." };
    }

    const lines = [];

    if (mainDir) {
      const [x0, y0] = positions[0];
      const mainLine = Board._lineCells(tempCells, x0, y0, mainDir);
      const mainLinePositions = new Set(mainLine.map((c) => posKey(c.x, c.y)));
      for (const [x, y] of positions) {
        if (!mainLinePositions.has(posKey(x, y))) {
          return { ok: false, reason: "Tiles must form one contiguous line (no gaps)." };
        }
      }
      if (!Board._lineValid(mainLine)) {
        return { ok: false, reason: "The main line has a color/shape conflict or duplicate." };
      }
      lines.push(mainLine);

      const perpDir = mainDir === "v" ? "h" : "v";
      for (const [x, y] of positions) {
        const pline = Board._lineCells(tempCells, x, y, perpDir);
        if (pline.length > 1) {
          if (!Board._lineValid(pline)) {
            return { ok: false, reason: `Cross line through (${x}, ${y}) has a color/shape conflict or duplicate.` };
          }
          lines.push(pline);
        }
      }
    } else {
      const [x, y] = positions[0];
      for (const d of ["h", "v"]) {
        const line = Board._lineCells(tempCells, x, y, d);
        if (line.length > 1) {
          if (!Board._lineValid(line)) {
            return { ok: false, reason: "Placement conflicts with an existing line." };
          }
          lines.push(line);
        }
      }
    }

    if (!this.isEmpty()) {
      const touchesExisting = lines.some((line) =>
        line.some((c) => this.cells.has(posKey(c.x, c.y)))
      );
      if (!touchesExisting) {
        return { ok: false, reason: "Your tiles must connect to tiles already on the board." };
      }
    }

    return { ok: true, lines };
  }

  // Given the validated `lines` from validateMove, compute the score.
  scoreMove(lines) {
    let total = 0;
    for (const line of lines) {
      const n = line.length;
      if (n < 2) continue;
      total += n;
      if (n === 6) total += 6; // Qwirkle bonus
    }
    return total;
  }

  applyMove(move) {
    for (const [x, y, t] of move) {
      this.cells.set(posKey(x, y), t);
    }
  }

  // ---------- convenience for bots/GUI ----------

  // All empty squares adjacent to at least one occupied square -- useful
  // for bots scanning for candidate placements.
  legalAnchorSquares() {
    if (this.isEmpty()) return [[0, 0]];
    const anchors = new Set();
    for (const key of this.cells.keys()) {
      const [x, y] = parseKey(key);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const p = posKey(x + dx, y + dy);
        if (!this.cells.has(p)) anchors.add(p);
      }
    }
    return Array.from(anchors, parseKey);
  }

  // [minX, minY, maxX, maxY] of played tiles, or null if empty.
  bounds() {
    if (this.isEmpty()) return null;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const key of this.cells.keys()) {
      const [x, y] = parseKey(key);
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    return [minX, minY, maxX, maxY];
  }
}
