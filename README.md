# Qwirkle

A browser-based implementation of **Qwirkle**, built with plain HTML5 Canvas and JavaScript. The game can be played directly in a web browser and is hosted on GitHub Pages.

## 🎮 How to Play

### Objective

The goal of Qwirkle is to score the most points by creating and extending lines of tiles that share either a **color** or a **shape**.

Each tile has:

* One of **6 colors**
* One of **6 shapes**

There are 108 tiles total, with three copies of every color/shape combination.

---

## 🧩 Game Setup

At the beginning of the game:

1. Each player receives **6 tiles**.
2. The remaining tiles form the draw pile.
3. Players determine who goes first by finding the largest group of tiles in their hand that share a single characteristic:

   * The same color, **or**
   * The same shape.
4. The player with the largest group starts the game.
5. If multiple players tie, the game uses the applicable tie-breaking rule.

The opening player places their chosen tiles as the first line on the board.

---

## 🔷 Creating Lines

A valid line must follow **one** of these two patterns:

### Same Color

All tiles have the same color, but every tile has a different shape.

For example:

```text
🔴 Circle — 🔴 Square — 🔴 Star — 🔴 Diamond
```

### Same Shape

All tiles have the same shape, but every tile has a different color.

For example:

```text
🔵 Circle — 🟢 Circle — 🟡 Circle — 🔴 Circle
```

### Important Rules

* A line can contain **2–6 tiles**.
* A line can never contain duplicate color/shape combinations.
* A line can never contain more than **6 tiles**.
* Tiles are connected horizontally or vertically.
* Diagonal connections do not count.
* Every line created by a move must be valid after the move is completed.

---

## 🎯 Taking a Turn

On your turn, you have two choices:

### 1. Place Tiles

You can place one or more tiles from your hand onto the board.

When placing multiple tiles during the same turn:

* All tiles must share the same **color or shape**.
* All tiles must be placed in the same row or column.
* The tiles must create valid lines.
* At least one tile must connect to the existing board after the opening move.
* You cannot create a duplicate tile within a line.

After placing your tiles, you draw from the tile bag until you have **6 tiles** again, as long as tiles remain.

### 2. Swap Tiles

Instead of placing tiles, you can exchange some or all of your tiles for new ones from the bag.

The tiles you exchange are returned to the bag after drawing replacements.

You cannot place tiles and swap tiles during the same turn.

---

## 💯 Scoring

You earn points whenever you create or extend a line.

### Normal Scoring

A line scores **1 point for every tile in that line**, including tiles that were already on the board.

For example, extending:

```text
🔴 Circle — 🔴 Square — 🔴 Star
```

with another valid tile creates a 4-tile line and scores **4 points**.

### Multiple Lines

A single tile can be part of both a horizontal and vertical line.

When this happens, you score each line separately.

For example, if your move creates:

```text
        🟢
        🔵
🔴 — 🟡 — 🟣
        🟠
```

the newly placed tile contributes to both the horizontal and vertical lines, so both lines are scored.

---

## 🌟 Qwirkle

A **Qwirkle** occurs when you complete a line of exactly **6 tiles**.

A Qwirkle scores:

* **6 points** for the six tiles in the line
* **+6 bonus points**

### Total: 12 points

A line can only contain six tiles, so completing a six-tile line is the maximum possible length for a single line.

---

## 🏁 Ending the Game

The game continues until the tile bag is empty.

Once there are no tiles left in the bag:

* Players continue taking turns.
* Players no longer draw replacement tiles.
* The first player to play all of the tiles in their hand ends the game.
* The player who ends the game receives an additional **6-point bonus**.

The player with the highest score at the end of the game wins.

---

## 🤖 Computer Opponents

This version includes several computer-controlled opponents.

The AI implementations are located in:

```text
js/bots.js
```

Bots can evaluate the current board, available tiles, and legal moves to decide what they should play.

The project currently includes multiple bot behaviors, including random and strategy-based opponents.

You can also create your own bot by extending the `Bot` class.

Example:

```javascript
class MyCustomBot extends Bot {
    static name = "MyCustomBot";

    chooseMove(board, hand, info) {
        // Choose and return a legal move
    }
}
```

---

## 🖥️ Browser Version

This project is a direct port of an earlier Python/Pygame implementation into JavaScript.

| Original Python | Browser JavaScript |
| --------------- | ------------------ |
| `tiles.py`      | `js/tiles.js`      |
| `board.py`      | `js/board.js`      |
| `player.py`     | `js/player.js`     |
| `game.py`       | `js/game.js`       |
| `bots.py`       | `js/bots.js`       |
| `shapes.py`     | `js/shapes.js`     |
| `gui.py`        | `js/gui.js`        |
| `main.py`       | `js/main.js`       |

The browser version uses:

* HTML5 Canvas
* JavaScript ES Modules
* No external framework
* No server-side code
* No build step

---

## 🌐 Playing the Game

The game is hosted using GitHub Pages:

**[Play Qwirkle](https://lukemarshalll.github.io/qwirkle/)**

Because the game is made entirely with client-side JavaScript, it can run as a static website.

---

## 🚀 Running Locally

Because the project uses JavaScript ES modules, opening `index.html` directly with `file://` may prevent modules from loading.

Instead, run a local HTTP server from the project directory.

### Python

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

### VS Code

You can also use the **Live Server** extension.

---

## 📁 Project Structure

```text
qwirkle/
│
├── index.html
│
├── js/
│   ├── main.js
│   ├── game.js
│   ├── board.js
│   ├── tiles.js
│   ├── player.js
│   ├── bots.js
│   ├── shapes.js
│   └── gui.js
│
└── README.md
```

### File Responsibilities

**`main.js`**
Starts the game and configures the computer opponents.

**`game.js`**
Controls turns, game state, opening moves, scoring, and game completion.

**`board.js`**
Handles tile placement, move validation, lines, and scoring.

**`tiles.js`**
Defines tiles and manages the tile bag.

**`player.js`**
Handles player hands and scores.

**`bots.js`**
Contains the computer-controlled opponents and move-generation logic.

**`shapes.js`**
Draws the six Qwirkle shapes onto the Canvas.

**`gui.js`**
Handles rendering, user input, camera/zoom, and interaction with the game.

---

## 🛠️ Development

The game does not require Node.js, npm, or a build system.

The JavaScript files are loaded directly by the browser as ES modules.

The rules engine is also separated from the graphical interface, making it possible to test the game logic independently from the Canvas UI.

---

## 📜 Rules Summary

For a quick reference:

| Rule              | Description                                  |
| ----------------- | -------------------------------------------- |
| Hand size         | 6 tiles                                      |
| Tiles             | 108 total                                    |
| Colors            | 6                                            |
| Shapes            | 6                                            |
| Maximum line      | 6 tiles                                      |
| Valid line        | Same color OR same shape, without duplicates |
| Normal scoring    | 1 point per tile in each line                |
| Qwirkle           | 6-tile line                                  |
| Qwirkle bonus     | +6 points                                    |
| End-game bonus    | +6 points                                    |
| Winning condition | Highest score                                |

Have fun, and **good luck getting a Qwirkle!** 🎯
