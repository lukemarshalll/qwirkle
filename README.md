# Qwirkle (Python + pygame)

A 4-player Qwirkle clone: top-down table view, your hand face up, the
other three players' hands face down, real Qwirkle placement/scoring
rules, and a pluggable bot system so you can write your own AI opponents.

## Setup

```
pip install pygame
python main.py
```

Everything except `gui.py` / `shapes.py` / `main.py` is plain Python with
no dependencies, so the rules engine (`tiles.py`, `board.py`, `player.py`,
`game.py`, `bots.py`) can be imported and unit-tested without pygame at
all -- handy if you just want to test a bot headlessly.

> **Note:** I built and unit-tested the whole rules engine + bots in a
> sandbox without internet access, so I couldn't install pygame there to
> click through the GUI myself. The game logic (placement rules, scoring,
> turn order, first-move rule, end-of-game bonus) is solid -- I ran it
> through full simulated games. The GUI is written carefully against the
> pygame API but you're the first to actually run it, so if anything
> looks off visually or throws an error, tell me and I'll fix it fast.

## How to play

- **Seats / turn order:** You (bottom, face up) → Left → Across (top) →
  Right → back to You. Fixed seating, clockwise turn order.
- **Placing tiles:** click a tile in your hand (it gets a gold outline),
  then click an empty board square to drop it there. Repeat for more
  tiles in the same turn. Click a blue (pending) tile on the board to
  pick it back up. When you're happy, click **Confirm Move**. If it's
  illegal (not a straight line, doesn't touch the board, color/shape
  conflict, etc.) you'll get an error message and can rearrange.
- **Swapping:** click **Swap Tiles...**, click the tiles in your hand you
  want to discard, then **Confirm Swap**. You draw the same number of
  replacements and your turn ends with 0 points. (Not allowed as the
  very first move of the game.)
- **Sort by Color / Sort by Shape:** the two buttons under your hand.
- **Panning the board:** right-click-drag or middle-click-drag, or the
  arrow keys. Press **C** to re-center on the played tiles.
- **Opening move:** whoever is randomly chosen to go first must play the
  *maximum* number of tiles from their hand that all share a color (with
  different shapes) or all share a shape (with different colors). If
  there's a tie for the biggest such set, you'll get a popup to pick
  which set to play; you still choose where/how to lay it out on the
  board.
- **Scoring:** playing a tile scores points equal to the length of every
  line (row or column) it's part of (a lone, unconnected tile scores 0).
  Completing a line of all 6 (a **Qwirkle**) scores double for that line
  (12 instead of 6).
- **Game end:** the instant a player empties their hand and the bag has
  no tiles left to refill them, the game ends immediately and that
  player gets a **+6 bonus** added to the score of the move that emptied
  their hand.

## Project layout

| File | What it is |
|---|---|
| `tiles.py` | `Tile`, `TileBag` (the 108-tile draw pile), color/shape constants |
| `board.py` | `Board` -- placement validation and scoring, the actual rules engine |
| `player.py` | `Player` -- hand + score bookkeeping, hand sorting |
| `game.py` | `Game` -- turn order, the opening-move house rule, replenishment, end-of-game bonus |
| `bots.py` | **Edit this to build your own AI.** Bot interface + move-generation helpers + example bots |
| `shapes.py` | pygame drawing code for the six tile shapes |
| `gui.py` | The pygame table view and all UI interaction |
| `main.py` | Entry point -- pick your opponents here |

## Writing your own bot

Open `bots.py`. A bot is a class with one method:

```python
class MyCustomBot(Bot):
    name = "MyCustomBot"

    def choose_move(self, board, hand, info):
        # board: board.Board (read-only) -- use board.validate_move(move)
        #        to check anything before returning it
        # hand:  list[Tile] -- your current tiles
        # info:  dict with is_first_move, opening_options, bag_count,
        #        scores, hand_sizes, my_name
        ...
        return ("place", [(x, y, tile), ...])   # or:
        return ("swap", [tile, ...])
```

`generate_legal_placements(board, hand)` in `bots.py` already does the
legwork of finding legal single- and multi-tile placements (it's capped
for speed -- see its docstring for the knobs), and `score_placement(board,
move)` tells you how many points a candidate move is worth. `GreedyBot`
and `QwirkleHunterBot` show two different heuristics built on top of
those helpers -- copy one as a starting point.

Then wire your bot in for a seat in `main.py`:

```python
OPPONENT_BOTS = {
    "Left": MyCustomBot(),
    "Across": GreedyBot(),
    "Right": RandomBot(),
}
```

## Testing the rules engine without the GUI

```python
from game import Game
from bots import GreedyBot

g = Game(["You", "Left", "Across", "Right"],
         bots={"Left": GreedyBot(), "Across": GreedyBot(), "Right": GreedyBot()})

# on your turn:
g.current_player            # whose turn it is
g.is_first_move_of_game()   # True only for the very first move of the game
g.opening_options_for_current_player()  # (options, max_size) for that rule
g.play_place([(0, 0, some_tile), ...])  # returns a TurnResult
g.play_swap([some_tile])
```
