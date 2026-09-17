# Qwirkle (browser version)

A straight port of the pygame Qwirkle project to plain HTML5 Canvas +
JavaScript, so it can run as a static site on GitHub Pages (or any static
host) with no build step and no server-side code.

## Deploying to GitHub Pages

1. Put this folder's contents (`index.html` and `js/`) at the root of a
   GitHub repo -- or in a `/docs` folder on your default branch if you'd
   rather keep them alongside other project files.
2. In the repo: **Settings -> Pages -> Build and deployment -> Source**,
   pick "Deploy from a branch," then pick the branch and the `/ (root)`
   or `/docs` folder, whichever you used.
3. Save. GitHub gives you a URL (usually
   `https://<username>.github.io/<repo>/`) that's live within a minute
   or two.

That's it -- no build step, no `npm install`, nothing to compile. It's
plain ES modules loaded straight by the browser.

## Running it locally

Opening `index.html` directly via `file://` won't work -- browsers block
ES module imports from `file://` for security reasons. Serve it over
plain HTTP instead, from this folder:

```
python3 -m http.server 8000
```

then visit `http://localhost:8000`. (Any static server works --
`npx serve`, VS Code's Live Server extension, etc.)

## How it maps to the original Python project

Every file is a direct, faithful port -- same rules, same structure, just
JavaScript syntax and Canvas 2D instead of pygame:

| Python | JS | |
|---|---|---|
| `tiles.py` | `js/tiles.js` | `Tile`, `TileBag`, colors/shapes |
| `board.py` | `js/board.js` | placement validation + scoring |
| `player.py` | `js/player.js` | hand + score bookkeeping |
| `game.py` | `js/game.js` | turn engine, opening-move rule, end-game bonus |
| `bots.py` | `js/bots.js` | **edit this to build your own AI** |
| `shapes.py` | `js/shapes.js` | canvas drawing for the six shapes |
| `gui.py` | `js/gui.js` | canvas rendering, camera/zoom, input handling |
| `main.py` | `js/main.js` | entry point -- pick your opponents here |

A few things changed because the target is a browser instead of a
desktop window:

- **The window is always "full screen"** in the sense that the canvas
  fills the browser viewport and reflows live on resize (desktop,
  tablet, whatever) -- there's no separate fullscreen mode to toggle.
- **"Quit" doesn't exist** -- closing a browser tab isn't something a
  page should do to itself. The **Play Again** button on the game-over
  screen is new: it starts a fresh game (new random deal, new random
  first player) with the same opponents, without a page reload.
- Mouse panning/dragging the board was already replaced by automatic
  zoom in the pygame version; that behavior carries over unchanged.

## Writing your own bot

Exactly the same as the Python version -- open `js/bots.js`. A bot is a
class with one method:

```js
class MyCustomBot extends Bot {
  static name = "MyCustomBot";

  chooseMove(board, hand, info) {
    // board: board.Board (read-only) -- use board.validateMove(move)
    //        to check anything before returning it
    // hand:  Tile[] -- your current tiles
    // info:  { isFirstMove, openingOptions, bagCount, scores,
    //          handSizes, myName }
    ...
    return ["place", [[x, y, tile], ...]];   // or:
    return ["swap", [tile, ...]];
  }
}
```

`generateLegalPlacements(board, hand)` and `scorePlacement(board, move)`
in `bots.js` do the legwork of finding and scoring legal moves, same as
before. Copy `GreedyBot` or `QwirkleHunterBot` as a starting point.

Then wire your bot in for a seat in `main.js`:

```js
const OPPONENT_BOTS = {
  Left: new MyCustomBot(),
  Across: new GreedyBot(),
  Right: new RandomBot(),
};
```

## Testing the rules engine without the GUI

The engine files (`tiles.js`, `board.js`, `player.js`, `game.js`,
`bots.js`) have zero DOM dependencies, so you can run and test them
headlessly with plain Node:

```js
import { Game } from "./js/game.js";
import { GreedyBot } from "./js/bots.js";

const g = new Game(["You", "Left", "Across", "Right"], {
  bots: { Left: new GreedyBot(), Across: new GreedyBot(), Right: new GreedyBot() },
});

g.currentPlayer;              // whose turn it is
g.isFirstMoveOfGame();        // true only for the very first move of the game
g.openingOptionsForCurrentPlayer();  // { options, maxSize } for that rule
g.playPlace([[0, 0, someTile], ...]);  // returns a TurnResult
g.playSwap([someTile]);
```

## Verification

Before delivery this was actually run end-to-end in headless Chromium
(not just read over) -- opening-tie selection, tile arming and the
valid-square highlighting, placement + scoring, bot turns running
automatically, Sort by Color/Shape persisting across hand refills,
window resize reflow, and the Game Over -> Play Again flow were all
exercised and confirmed working, with zero console errors. The rules
engine itself was additionally regression-tested with multi-seed
simulated games run to completion in Node, matching the same testing
the original Python version got.
