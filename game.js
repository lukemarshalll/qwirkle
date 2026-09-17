// game.js
// The turn-based game engine that ties Board + Player + TileBag together
// and enforces the house rules:
//
//   - 4 players, 6-tile hands, replenish to 6 immediately after playing.
//   - First player is chosen at random.
//   - The first player's opening move must use the MAXIMUM number of
//     tiles from their hand that share either a color (all different
//     shapes) or a shape (all different colors). Ties are resolved by
//     the player.
//   - Score for a placement = sum of the length of every line (row/col)
//     touched by the move (min length 2 to count), with a Qwirkle
//     (a complete line of 6) worth double (+6 bonus on top of the 6).
//   - The game ends the instant a player empties their hand and the bag
//     has no tiles left to refill them. That player gets a +6 bonus
//     added to the score of the turn that emptied their hand.
//
// Direct port of game.py.

import { TileBag, makeRng, shuffleInPlace } from "./tiles.js";
import { Board } from "./board.js";
import { Player } from "./player.js";

// Find the largest subset(s) of `hand` that could legally form a single
// straight line on an empty board (all same color w/ distinct shapes, OR
// all same shape w/ distinct colors).
//
// Returns { options, maxSize } where `options` is an array of tile
// arrays, one per distinct maximal set (more than one entry only when
// there's a genuine tie for the largest size).
export function findMaxMatchingSets(hand) {
  if (!hand || hand.length === 0) return { options: [], maxSize: 0 };

  const byColor = new Map(); // color -> Map(shape -> tile)
  const byShape = new Map(); // shape -> Map(color -> tile)
  for (const t of hand) {
    if (!byColor.has(t.color)) byColor.set(t.color, new Map());
    const shapeMap = byColor.get(t.color);
    if (!shapeMap.has(t.shape)) shapeMap.set(t.shape, t);

    if (!byShape.has(t.shape)) byShape.set(t.shape, new Map());
    const colorMap = byShape.get(t.shape);
    if (!colorMap.has(t.color)) colorMap.set(t.color, t);
  }

  const candidates = [
    ...Array.from(byColor.values(), (m) => Array.from(m.values())),
    ...Array.from(byShape.values(), (m) => Array.from(m.values())),
  ];

  const maxSize = Math.max(...candidates.map((c) => c.length));
  const best = candidates.filter((c) => c.length === maxSize);

  const unique = [];
  const seen = new Set();
  for (const c of best) {
    const sig = c.map((t) => t.sig()).sort().join(",");
    if (!seen.has(sig)) {
      seen.add(sig);
      unique.push(c);
    }
  }

  return { options: unique, maxSize };
}

export class TurnResult {
  constructor({ ok, reason = null, score = 0, qwirkles = 0, gameOver = false,
                winner = null, bonusAwarded = 0 }) {
    this.ok = ok;
    this.reason = reason;
    this.score = score;
    this.qwirkles = qwirkles;
    this.gameOver = gameOver;
    this.winner = winner;
    this.bonusAwarded = bonusAwarded;
  }
}

export class Game {
  // playerNames: array of 4 display names, in seat order
  //              (e.g. [You, Left, Across, Right])
  // bots: { name: botInstance } for any non-human players. A player with
  //       no entry / name not in bots is treated as human.
  constructor(playerNames, { bots = {}, seed = null } = {}) {
    if (playerNames.length !== 4) throw new Error("Qwirkle here is fixed to 4 players.");
    this.rng = makeRng(seed);
    this.bag = new TileBag(seed);
    this.board = new Board();
    this.players = playerNames.map(
      (name) => new Player(name, { isBot: name in bots, bot: bots[name] || null })
    );
    for (const p of this.players) p.refill(this.bag);

    this.currentIndex = this.rng.randint(4);
    this.firstPlayerIndex = this.currentIndex;
    this.firstMoveDone = false;
    this.turnNumber = 0;
    this.gameOver = false;
    this.winner = null;
    this.history = []; // list of {..} describing each turn, for UI/debug
  }

  // ---------- state accessors ----------

  get currentPlayer() {
    return this.players[this.currentIndex];
  }

  isFirstMoveOfGame() {
    return !this.firstMoveDone;
  }

  // Only meaningful when isFirstMoveOfGame() is true.
  openingOptionsForCurrentPlayer() {
    return findMaxMatchingSets(this.currentPlayer.hand);
  }

  // ---------- turn actions ----------

  // move: array of [x, y, tile]
  // Validates against Board rules AND, if this is the game's opening
  // move, against the "must play your max matching set" house rule.
  playPlace(move) {
    const player = this.currentPlayer;

    const placedTiles = move.map(([, , t]) => t);
    if (!player.hasTiles(placedTiles)) {
      return new TurnResult({ ok: false, reason: "You don't have those tiles in hand." });
    }

    if (this.isFirstMoveOfGame()) {
      const { options, maxSize } = this.openingOptionsForCurrentPlayer();
      if (placedTiles.length !== maxSize) {
        return new TurnResult({
          ok: false,
          reason: `Opening move must use your maximum matching set (${maxSize} tiles).`,
        });
      }
      const playedSig = placedTiles.map((t) => t.sig()).sort().join(",");
      const validSigs = options.map((opt) => opt.map((t) => t.sig()).sort().join(","));
      if (!validSigs.includes(playedSig)) {
        return new TurnResult({
          ok: false,
          reason: "Opening tiles must all share a color or all share a shape.",
        });
      }
      // opening move: any straight-line arrangement of these tiles is
      // fine, board.validateMove will confirm colinearity/order.
    }

    const result = this.board.validateMove(move);
    if (!result.ok) {
      return new TurnResult({ ok: false, reason: result.reason });
    }
    const lines = result.lines;

    const score = this.board.scoreMove(lines);
    const qwirkles = lines.filter((line) => line.length === 6).length;

    this.board.applyMove(move);
    player.removeTiles(placedTiles);
    player.refill(this.bag);

    player.score += score;

    let gameOver = false;
    let winner = null;
    let bonus = 0;
    if (player.hand.length === 0 && this.bag.isEmpty()) {
      bonus = 6;
      player.score += bonus;
      gameOver = true;
      this.gameOver = true;
      winner = this._determineWinner();
      this.winner = winner;
    }

    this.firstMoveDone = true;
    this.turnNumber += 1;
    const resultObj = new TurnResult({
      ok: true, score, qwirkles, gameOver, winner, bonusAwarded: bonus,
    });
    this.history.push({
      player: player.name, type: "place", score, qwirkles,
      tiles: placedTiles.map((t) => t.toString()),
    });
    if (!gameOver) this._advanceTurn();
    return resultObj;
  }

  // Discard `tiles` back into the bag and draw the same number of
  // replacements. Forfeits the turn (0 points). Not allowed as the very
  // first move of the game (there'd be nothing to swap for).
  playSwap(tiles) {
    const player = this.currentPlayer;
    if (this.isFirstMoveOfGame()) {
      return new TurnResult({ ok: false, reason: "You must make the opening move; you can't swap first." });
    }
    if (!tiles || tiles.length === 0) {
      return new TurnResult({ ok: false, reason: "Select at least one tile to swap." });
    }
    if (!player.hasTiles(tiles)) {
      return new TurnResult({ ok: false, reason: "You don't have those tiles in hand." });
    }
    if (tiles.length > this.bag.length) {
      return new TurnResult({ ok: false, reason: "Not enough tiles left in the bag to swap that many." });
    }

    player.removeTiles(tiles);
    const newTiles = this.bag.draw(tiles.length);
    player.hand.push(...newTiles);
    this.bag.tiles.push(...tiles);
    shuffleInPlace(this.bag.tiles, this.rng);

    this.turnNumber += 1;
    this.history.push({ player: player.name, type: "swap", count: tiles.length });
    this._advanceTurn();
    return new TurnResult({ ok: true, score: 0 });
  }

  // Cheap-ish check used by bots/UI to decide whether a swap is the only
  // option. Not exhaustive-search-optimal, just practical.
  hasAnyLegalMove(player = null) {
    player = player || this.currentPlayer;
    if (this.isFirstMoveOfGame()) return true; // opening move is always possible
    if (this.board.isEmpty()) return true;
    for (const [ax, ay] of this.board.legalAnchorSquares()) {
      for (const t of player.hand) {
        if (this.board.validateMove([[ax, ay, t]]).ok) return true;
      }
    }
    return false;
  }

  // ---------- internal ----------

  _advanceTurn() {
    this.currentIndex = (this.currentIndex + 1) % 4;
  }

  _determineWinner() {
    const best = this.players.reduce((a, b) => (b.score > a.score ? b : a));
    const ties = this.players.filter((p) => p.score === best.score);
    if (ties.length > 1) return null; // tie -- let the caller display all tied players
    return best;
  }

  standings() {
    return [...this.players].sort((a, b) => b.score - a.score);
  }
}
