// tiles.js
// Defines the Tile object and the TileBag (the draw pile of all 108 tiles).
// Port of tiles.py -- same data, same rules.

export const COLORS = ["Red", "Orange", "Yellow", "Green", "Blue", "Purple"];
export const SHAPES = ["Circle", "Star", "Diamond", "Square", "Clover", "Triangle"];

// How each shape/color is drawn (used by the GUI). Kept here so both the
// GUI and any headless/debug rendering share one source of truth.
export const COLOR_RGB = {
  Red: "rgb(211, 47, 47)",
  Orange: "rgb(245, 124, 0)",
  Yellow: "rgb(251, 192, 45)",
  Green: "rgb(56, 142, 60)",
  Blue: "rgb(25, 118, 210)",
  Purple: "rgb(123, 31, 162)",
};

export class Tile {
  constructor(color, shape) {
    if (!COLORS.includes(color)) throw new Error(`Invalid color: ${color}`);
    if (!SHAPES.includes(shape)) throw new Error(`Invalid shape: ${shape}`);
    this.color = color;
    this.shape = shape;
  }

  // Tiles are compared by value everywhere in this codebase (JS objects
  // compare by reference, so Python's `==` on Tile becomes this helper).
  equals(other) {
    return !!other && this.color === other.color && this.shape === other.shape;
  }

  // Canonical string key, used anywhere Python relied on Tile's __hash__
  // (dedupe sets, dict keys, etc).
  sig() {
    return `${this.color}|${this.shape}`;
  }

  toString() {
    return `${this.color} ${this.shape}`;
  }
}

export function tilesEqual(a, b) {
  return !!a && !!b && a.color === b.color && a.shape === b.shape;
}

// Small seedable RNG (mulberry32) so a numeric seed gives a reproducible
// shuffle/first-player choice, same spirit as Python's random.Random(seed).
// With no seed it falls back to Math.random().
export function makeRng(seed) {
  if (seed === null || seed === undefined) {
    return {
      random: () => Math.random(),
      randint: (maxExclusive) => Math.floor(Math.random() * maxExclusive),
    };
  }
  let a = seed >>> 0;
  const random = () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    random,
    randint: (maxExclusive) => Math.floor(random() * maxExclusive),
  };
}

export function shuffleInPlace(arr, rng) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// The shared draw pile. Starts with 3 copies of each of the 36 unique
// tiles (108 total).
export class TileBag {
  constructor(seed = null) {
    this._rng = makeRng(seed);
    this.tiles = [];
    for (const color of COLORS) {
      for (const shape of SHAPES) {
        for (let i = 0; i < 3; i++) {
          this.tiles.push(new Tile(color, shape));
        }
      }
    }
    shuffleInPlace(this.tiles, this._rng);
  }

  get length() {
    return this.tiles.length;
  }

  isEmpty() {
    return this.tiles.length === 0;
  }

  // Draw up to `count` tiles. Returns fewer if the bag runs low.
  draw(count) {
    const drawn = this.tiles.slice(0, count);
    this.tiles = this.tiles.slice(count);
    return drawn;
  }

  drawOne() {
    const drawn = this.draw(1);
    return drawn.length ? drawn[0] : null;
  }
}
