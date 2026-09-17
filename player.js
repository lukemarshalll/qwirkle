// player.js
// A player's hand + score bookkeeping. Works the same whether the player
// is the human or a bot -- the difference is only in who decides the
// move. Direct port of player.py.

import { COLORS, SHAPES } from "./tiles.js";

export const HAND_SIZE = 6;

export class Player {
  constructor(name, { isBot = false, bot = null } = {}) {
    this.name = name;
    this.isBot = isBot;
    this.bot = bot; // instance of a class from bots.js, or null for human
    this.hand = [];
    this.score = 0;
  }

  refill(bag) {
    const need = HAND_SIZE - this.hand.length;
    if (need > 0) this.hand.push(...bag.draw(need));
  }

  // Remove the given tiles (array of Tile) from hand.
  removeTiles(tiles) {
    for (const t of tiles) {
      const i = this.hand.findIndex((h) => h.equals(t));
      if (i === -1) throw new Error(`Tile ${t} not in ${this.name}'s hand`);
      this.hand.splice(i, 1);
    }
  }

  hasTiles(tiles) {
    const pool = [...this.hand];
    for (const t of tiles) {
      const i = pool.findIndex((h) => h.equals(t));
      if (i === -1) return false;
      pool.splice(i, 1);
    }
    return true;
  }

  sortByColor() {
    const order = Object.fromEntries(COLORS.map((c, i) => [c, i]));
    this.hand.sort((a, b) => order[a.color] - order[b.color] || a.shape.localeCompare(b.shape));
  }

  sortByShape() {
    const order = Object.fromEntries(SHAPES.map((s, i) => [s, i]));
    this.hand.sort((a, b) => order[a.shape] - order[b.shape] || a.color.localeCompare(b.color));
  }
}
