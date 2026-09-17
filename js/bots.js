// bots.js
// ========
// This is the file you edit to build your own Qwirkle AI opponents.
//
// Every bot is a class with one required method:
//
//     chooseMove(board, hand, info) -> ["place", move] | ["swap", tiles]
//
//     board : board.Board        - read-only view of the current board.
//                                   Do not mutate it. Use
//                                   board.validateMove(move) to check any
//                                   placement you're considering.
//     hand  : Array<tiles.Tile>  - this bot's current 6 (or fewer) tiles.
//     info  : object             - extra context:
//         info.isFirstMove       bool    - true only on the very first
//                                           turn of the whole game
//         info.openingOptions    Tile[][] | null
//                                 - if isFirstMove, the legal maximal
//                                   matching sets you're allowed to open
//                                   with (house rule). Pick one of these
//                                   EXACTLY (same multiset of tiles) if
//                                   isFirstMove is true.
//         info.bagCount          int     - tiles left in the bag
//         info.scores            object  name -> current score
//         info.handSizes         object  name -> tiles left in each hand
//         info.myName            string  - this bot's own player name
//
//     Return value:
//         ["place", [[x, y, tile], ...]]  - a legal placement (one
//                                            straight line, connected to
//                                            the board, per Qwirkle rules)
//         ["swap",  [tile, ...]]          - discard these tiles, draw
//                                            replacements, forfeit the
//                                            turn (not legal on the
//                                            opening move)
//
//     The game engine re-validates whatever you return and will treat an
//     illegal move as a forfeited turn, so it's in your interest to only
//     return moves you've checked with board.validateMove(...).
//
// Two helpers are provided so you don't have to write move-generation
// yourself:
//
//     generateLegalPlacements(board, hand)  -> array of legal moves
//     bestOpeningChoice(options)            -> picks an opening set
//
// Look at RandomBot and GreedyBot below for two complete, working
// examples. Scroll to the bottom for a blank template to fill in your
// own heuristic.

// ----------------------------------------------------------------------
// small utilities
// ----------------------------------------------------------------------

function randint(maxExclusive) {
  return Math.floor(Math.random() * maxExclusive);
}

function choice(arr) {
  return arr[randint(arr.length)];
}

function sample(arr, n) {
  const pool = [...arr];
  const out = [];
  for (let i = 0; i < n && pool.length; i++) {
    out.push(pool.splice(randint(pool.length), 1)[0]);
  }
  return out;
}

function* permutations(arr, size) {
  if (size === 0) {
    yield [];
    return;
  }
  for (let i = 0; i < arr.length; i++) {
    const rest = arr.slice(0, i).concat(arr.slice(i + 1));
    for (const p of permutations(rest, size - 1)) {
      yield [arr[i], ...p];
    }
  }
}

// ----------------------------------------------------------------------
// Move generation helpers -- shared by all bots, so you don't have to
// reimplement "what placements are even legal" every time.
// ----------------------------------------------------------------------

// Search for legal placements (single- and multi-tile) using the current
// board and hand. Not exhaustive on very crowded boards (it caps how
// many anchor squares and how long a run it tries, for speed) but it
// finds the large majority of legal moves, including all single-tile
// moves.
//
// Returns an array of moves, where each move is [[x, y, tile], ...].
//
// maxRun: largest number of tiles it will try to lay down in one line
//         (raise this for a stronger, slower bot).
// maxAnchors: cap on how many candidate anchor squares to explore (raise
//             this on a sparse board for more options, at a speed cost
//             on a crowded one).
export function generateLegalPlacements(board, hand, { maxRun = 4, maxAnchors = 50 } = {}) {
  if (board.isEmpty()) return []; // opening move is handled separately -- see bestOpeningChoice

  const moves = [];
  const seen = new Set();

  const record = (move) => {
    const key = move
      .map(([x, y, t]) => `${x},${y}:${t.sig()}`)
      .sort()
      .join("|");
    if (!seen.has(key)) {
      seen.add(key);
      moves.push(move);
    }
  };

  const uniqueHand = Array.from(new Map(hand.map((t) => [t.sig(), t])).values()); // dedupe identical tiles

  let anchors = board.legalAnchorSquares();
  if (anchors.length > maxAnchors) anchors = anchors.slice(0, maxAnchors);

  for (const [ax, ay] of anchors) {
    // single-tile placements
    for (const t of uniqueHand) {
      if (board.validateMove([[ax, ay, t]]).ok) {
        record([[ax, ay, t]]);
      }
    }

    // multi-tile runs starting at this anchor, in each direction
    for (const [sx, sy] of [[1, 0], [0, 1], [-1, 0], [0, -1]]) {
      const runLen = Math.min(maxRun, uniqueHand.length);
      for (let size = 2; size <= runLen; size++) {
        for (const combo of permutations(uniqueHand, size)) {
          const candidate = [];
          let okPositions = true;
          for (let i = 0; i < combo.length; i++) {
            const px = ax + sx * i, py = ay + sy * i;
            if (board.occupied(px, py)) {
              okPositions = false;
              break;
            }
            candidate.push([px, py, combo[i]]);
          }
          if (!okPositions) continue;
          if (board.validateMove(candidate).ok) record(candidate);
        }
      }
    }
  }

  return moves;
}

// Convenience: validate + score a candidate move in one call. Returns
// {score, qwirkles} or {score: null, qwirkles: null} if illegal.
export function scorePlacement(board, move) {
  const result = board.validateMove(move);
  if (!result.ok) return { score: null, qwirkles: null };
  const score = board.scoreMove(result.lines);
  const qwirkles = result.lines.filter((line) => line.length === 6).length;
  return { score, qwirkles };
}

// Pick which tied maximal opening set to play. `options` comes from
// info.openingOptions. strategy: 'random' or 'first'.
export function bestOpeningChoice(options, strategy = "random") {
  if (strategy === "first") return options[0];
  return choice(options);
}

// ----------------------------------------------------------------------
// Bot interface
// ----------------------------------------------------------------------

export class Bot {
  static name = "Bot";

  // eslint-disable-next-line no-unused-vars
  chooseMove(board, hand, info) {
    throw new Error("chooseMove not implemented");
  }
}

// ----------------------------------------------------------------------
// Example 1: RandomBot -- plays any legal move at random, swaps if it
// can't find one. Good baseline / sanity check opponent.
// ----------------------------------------------------------------------

export class RandomBot extends Bot {
  static name = "RandomBot";

  chooseMove(board, hand, info) {
    if (info.isFirstMove) {
      const chosen = bestOpeningChoice(info.openingOptions, "random");
      const move = chosen.map((t, i) => [i, 0, t]);
      return ["place", move];
    }

    const moves = generateLegalPlacements(board, hand);
    if (moves.length) return ["place", choice(moves)];

    // nothing legal found -- swap a random handful of tiles
    const n = 1 + randint(hand.length);
    return ["swap", sample(hand, n)];
  }
}

// ----------------------------------------------------------------------
// Example 2: GreedyBot -- among every legal move it can find, plays the
// one worth the most points this turn (ties broken by whichever was
// found first). This is a genuinely decent Qwirkle opponent despite
// being "just" greedy, because in Qwirkle immediate score correlates
// strongly with good positioning.
// ----------------------------------------------------------------------

export class GreedyBot extends Bot {
  static name = "GreedyBot";

  chooseMove(board, hand, info) {
    if (info.isFirstMove) {
      const chosen = bestOpeningChoice(info.openingOptions, "random");
      const move = chosen.map((t, i) => [i, 0, t]);
      return ["place", move];
    }

    const moves = generateLegalPlacements(board, hand);
    if (!moves.length) {
      const n = 1 + randint(Math.min(3, hand.length));
      return ["swap", sample(hand, n)];
    }

    let bestMove = null, bestScore = -1;
    for (const move of moves) {
      const { score } = scorePlacement(board, move);
      if (score === null) continue;
      if (score > bestScore) {
        bestMove = move;
        bestScore = score;
      }
    }
    return ["place", bestMove];
  }
}

// ----------------------------------------------------------------------
// Example 3: QwirkleHunterBot -- greedy, but breaks ties in favor of
// moves that complete a Qwirkle (a full line of 6), and secondarily
// prefers moves that use more tiles (empties its hand faster, useful
// near the end of the bag). Shows how to layer a richer heuristic on
// top of the same move list GreedyBot uses.
// ----------------------------------------------------------------------

export class QwirkleHunterBot extends Bot {
  static name = "QwirkleHunterBot";

  chooseMove(board, hand, info) {
    if (info.isFirstMove) {
      const chosen = bestOpeningChoice(info.openingOptions, "random");
      const move = chosen.map((t, i) => [i, 0, t]);
      return ["place", move];
    }

    const moves = generateLegalPlacements(board, hand);
    if (!moves.length) {
      const n = 1 + randint(Math.min(3, hand.length));
      return ["swap", sample(hand, n)];
    }

    let bestMove = null;
    let bestKey = [-1, -1, -1];
    for (const move of moves) {
      const { score, qwirkles } = scorePlacement(board, move);
      const key = score === null ? [-1, -1, -1] : [qwirkles, score, move.length];
      if (key[0] > bestKey[0] || (key[0] === bestKey[0] && key[1] > bestKey[1]) ||
          (key[0] === bestKey[0] && key[1] === bestKey[1] && key[2] > bestKey[2])) {
        bestKey = key;
        bestMove = move;
      }
    }
    return ["place", bestMove];
  }
}

// ----------------------------------------------------------------------
// Write your own bot here. `board` is read-only; use
// board.validateMove(move) to check anything before returning it. See
// generateLegalPlacements() and scorePlacement() above -- you're welcome
// to call them, or write your own smarter search.
// ----------------------------------------------------------------------

export class MyCustomBot extends Bot {
  static name = "MyCustomBot";

  chooseMove(board, hand, info) {
    if (info.isFirstMove) {
      // info.openingOptions is an array of tied maximal tile sets -- you
      // must play one of them exactly, as the opening move.
      const chosen = bestOpeningChoice(info.openingOptions);
      const move = chosen.map((t, i) => [i, 0, t]);
      return ["place", move];
    }

    const moves = generateLegalPlacements(board, hand);
    if (!moves.length) return ["swap", hand.slice(0, 1)];

    // TODO: replace this with your own heuristic. A few ideas:
    //  - prefer moves that set up (but don't complete) long lines for
    //    yourself next turn
    //  - avoid leaving juicy multi-color/shape intersections open for
    //    opponents
    //  - weight by hand composition (e.g. dump colors you're holding too
    //    many of)
    let bestMove = null, bestScore = -1;
    for (const move of moves) {
      const { score } = scorePlacement(board, move);
      if (score !== null && score > bestScore) {
        bestMove = move;
        bestScore = score;
      }
    }
    return ["place", bestMove];
  }
}
