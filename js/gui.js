// gui.js
// Top-down canvas table view for Qwirkle:
//
//             [ Across's hand, face down ]
//     [Left's                              [Right's
//      hand,        [   BOARD   ]           hand,
//      face down]                           face down]
//             [ YOUR hand, face up ]
//             [ Sort by Color/Shape ]
//             [ Confirm / Clear / Swap ]
//
// Seat / turn order is always You -> Left -> Across -> Right -> You ...
// Port of gui.py (pygame -> Canvas 2D + DOM events).

import { COLOR_RGB } from "./tiles.js";
import { drawShape, roundRectPath } from "./shapes.js";
import { Game } from "./game.js";

// ---------------------------------------------------------------- layout --

const BG_COLOR = "rgb(30, 34, 40)";
const BOARD_BG = "rgb(42, 47, 56)";
const PANEL_COLOR = "rgb(24, 27, 32)";
const TEXT_COLOR = "rgb(230, 230, 235)";
const DIM_TEXT = "rgb(150, 155, 165)";
const FACE_DOWN_COLOR = "rgb(18, 20, 24)";
const SELECT_COLOR = "rgb(255, 215, 0)";
const PENDING_COLOR = "rgb(120, 200, 255)";
const ERROR_COLOR = "rgb(240, 90, 90)";
const GOOD_COLOR = "rgb(120, 220, 140)";
const VALID_SQUARE_COLOR = "rgba(90, 220, 120, 0.39)";
const BUTTON_COLOR = "rgb(55, 61, 72)";
const BUTTON_HOVER = "rgb(75, 82, 96)";
const BUTTON_ACTIVE = "rgb(60, 110, 150)";
const BUTTON_BORDER = "rgb(100, 108, 122)";
const BUTTON_DISABLED = "rgb(40, 43, 49)";
const TILE_FACE_COLOR = "rgb(250, 248, 240)";
const GHOST_COLOR = "rgb(35, 38, 44)";

const DEFAULT_CELL_SIZE = 46;
const MIN_CELL_SIZE = 14;
const BOARD_PADDING_CELLS = 2; // empty margin (in cells) kept around played tiles
const ZOOM_LERP = 0.08;
const TILE_MARGIN = 4;
const SHAPE_EDGE_MARGIN = 3; // px gap kept between a shape's edge and its tile's edge
const SHAPE_BASE_SIZE = (DEFAULT_CELL_SIZE - TILE_MARGIN) * 0.32; // shapes hold this size as the board zooms out

const HAND_TILE_SIZE = 56;
const HAND_GAP = 8;

// ------------------------------------------------------------------ Rect --

class Rect {
  constructor(x, y, w, h) {
    this.x = x;
    this.y = y;
    this.w = w;
    this.h = h;
  }
  get left() { return this.x; }
  get top() { return this.y; }
  get right() { return this.x + this.w; }
  get bottom() { return this.y + this.h; }
  get centerx() { return this.x + this.w / 2; }
  get centery() { return this.y + this.h / 2; }
  containsPoint(px, py) {
    return px >= this.x && px <= this.right && py >= this.y && py <= this.bottom;
  }
}

// ---------------------------------------------------------------- Button --

class Button {
  constructor(rect, label, callback, enabledFn = null, activeFn = null) {
    this.rect = rect;
    this.label = label;
    this.callback = callback;
    this.enabledFn = enabledFn || (() => true);
    this.activeFn = activeFn || (() => false);
  }

  enabled() {
    return this.enabledFn();
  }

  draw(ctx, mouseX, mouseY, fontSize = 15) {
    const enabled = this.enabled();
    const active = this.activeFn();
    const hovered = enabled && this.rect.containsPoint(mouseX, mouseY);
    let color;
    if (!enabled) color = BUTTON_DISABLED;
    else if (active) color = BUTTON_ACTIVE;
    else if (hovered) color = BUTTON_HOVER;
    else color = BUTTON_COLOR;

    roundRectPath(ctx, this.rect.x, this.rect.y, this.rect.w, this.rect.h, 6);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = active ? SELECT_COLOR : BUTTON_BORDER;
    ctx.lineWidth = active ? 2 : 1;
    ctx.stroke();

    ctx.fillStyle = enabled ? TEXT_COLOR : DIM_TEXT;
    ctx.font = `${fontSize}px Arial, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(this.label, this.rect.centerx, this.rect.centery);
  }

  handleClick(x, y) {
    if (this.enabled() && this.rect.containsPoint(x, y)) {
      this.callback();
      return true;
    }
    return false;
  }
}

// ------------------------------------------------------------------- GUI --

export class QwirkleGUI {
  constructor(canvas, game, humanName = "You") {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.game = game;
    this.humanName = humanName;
    this.human = game.players.find((p) => p.name === humanName);

    // camera: world coords centered in this.boardRect; both are animated
    // automatically every frame (see _updateCamera) -- no manual pan.
    this.camX = 0.0;
    this.camY = 0.0;
    this.cellSize = DEFAULT_CELL_SIZE;

    // turn-local human state
    this.selectedHandIdx = null; // index into human.hand "armed" for placing
    this.pending = []; // [{x, y, tile, handIndex}]
    this.validSquares = new Set(); // "x,y" strings -- legal squares for the armed tile
    this.swapMode = false;
    this.swapSelected = new Set(); // indices into human.hand marked to swap
    this.activeSort = null; // null | 'color' | 'shape' -- stays applied

    this.openingChoice = null; // chosen tile array during a tied opening
    this.openingOptions = null;
    this._openingCards = [];

    this.message = "";
    this.messageColor = TEXT_COLOR;
    this.messageUntil = 0;

    this.log = []; // recent turn history strings, newest last

    this.mouseX = -1;
    this.mouseY = -1;

    // The game doesn't actually begin (no bot turns, no input) until the
    // player clicks Start on the title screen.
    this.gameStarted = false;

    // Ready to move shortly after Start is clicked -- if the
    // randomly-chosen first player is a bot, this must be a real
    // timestamp (not null) or the bot turn never fires.
    this.nextBotMoveTime = performance.now() + 1000;
    this.gameOverShown = false;

    this._resizeCanvas();
    this._computeLayout();
    this._buildButtons();
    this._refreshOpeningState();

    this._bindEvents();
    this._loop = this._loop.bind(this);
  }

  start() {
    requestAnimationFrame(this._loop);
  }

  // ------------------------------------------------------------ setup --

  _resizeCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.canvas.style.width = `${w}px`;
    this.canvas.style.height = `${h}px`;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  // Derives every screen-position rect from the actual window size, so
  // the game fills whatever viewport it's run in.
  _computeLayout() {
    this.screenW = window.innerWidth;
    this.screenH = window.innerHeight;

    const boardW = Math.round(this.screenW * 0.54);
    const boardH = Math.round(this.screenH * 0.56);
    const boardX = (this.screenW - boardW) / 2;
    const boardY = Math.round(this.screenH * 0.17);
    this.boardRect = new Rect(boardX, boardY, boardW, boardH);

    this.handY = this.boardRect.bottom + 14;
    this.sortY = this.handY + HAND_TILE_SIZE + 10;
    this.actionY = this.sortY + 32 + 12;

    this.leftPanel = new Rect(20, this.screenH - 220, 260, 200);
    this.rightPanel = new Rect(this.screenW - 280, this.screenH - 220, 260, 200);
  }

  _buildButtons() {
    const sortW = 150, sortGap = 20;
    const sortTotal = sortW * 2 + sortGap;
    const sx = this.boardRect.centerx - sortTotal / 2;
    this.btnSortColor = new Button(
      new Rect(sx, this.sortY, sortW, 32), "Sort by Color",
      () => this._sortColor(), null, () => this.activeSort === "color"
    );
    this.btnSortShape = new Button(
      new Rect(sx + sortW + sortGap, this.sortY, sortW, 32), "Sort by Shape",
      () => this._sortShape(), null, () => this.activeSort === "shape"
    );

    const actW = 150, actGap = 10;
    const actTotal = actW * 4 + actGap * 3;
    const ax = this.boardRect.centerx - actTotal / 2;
    this.btnConfirm = new Button(
      new Rect(ax, this.actionY, actW, 34), "Confirm Move",
      () => this._confirmMove(), () => this._canConfirmPlace()
    );
    this.btnClear = new Button(
      new Rect(ax + (actW + actGap), this.actionY, actW, 34), "Clear Placement",
      () => this._clearPending(), () => this.pending.length > 0
    );
    this.btnSwapToggle = new Button(
      new Rect(ax + 2 * (actW + actGap), this.actionY, actW, 34), "Swap Tiles...",
      () => this._toggleSwapMode(), () => !this.game.isFirstMoveOfGame(),
      () => this.swapMode
    );
    this.btnConfirmSwap = new Button(
      new Rect(ax + 3 * (actW + actGap), this.actionY, actW, 34), "Confirm Swap",
      () => this._confirmSwap(), () => this.swapMode && this.swapSelected.size > 0
    );

    this.buttons = [this.btnSortColor, this.btnSortShape, this.btnConfirm,
      this.btnClear, this.btnSwapToggle, this.btnConfirmSwap];

    // Drawn separately, on top of the game-over overlay (see drawGameOver).
    const goW = 200, goH = 46, goGap = 20;
    const goTotal = goW * 2 + goGap;
    const goX = this.screenW / 2 - goTotal / 2;
    const goY = 520;
    this.btnPlayAgain = new Button(
      new Rect(goX, goY, goW, goH), "Play Again",
      () => this._restartGame(), () => this.game.gameOver
    );

    // Title-screen Start button -- centered, below where "Qwirkle!" is drawn.
    const startW = 220, startH = 60;
    this.btnStart = new Button(
      new Rect(this.screenW / 2 - startW / 2, this.screenH / 2 + 20, startW, startH),
      "Start",
      () => this._startGame()
    );
  }

  _refreshOpeningState() {
    if (this.game.isFirstMoveOfGame() && this.game.currentPlayer === this.human) {
      const { options } = this.game.openingOptionsForCurrentPlayer();
      this.openingOptions = options;
      this.openingChoice = options.length === 1 ? options[0] : null;
    } else {
      this.openingOptions = null;
      this.openingChoice = null;
    }
  }

  // ------------------------------------------------------------ coords --

  worldToScreen(wx, wy) {
    const sx = this.boardRect.centerx + (wx - this.camX) * this.cellSize;
    const sy = this.boardRect.centery + (wy - this.camY) * this.cellSize;
    return [sx, sy];
  }

  screenToWorldCell(sx, sy) {
    const wx = (sx - this.boardRect.centerx) / this.cellSize + this.camX;
    const wy = (sy - this.boardRect.centery) / this.cellSize + this.camY;
    return [Math.round(wx), Math.round(wy)];
  }

  _visibleWorldBounds() {
    const [x0, y0] = this.screenToWorldCell(this.boardRect.left, this.boardRect.top);
    const [x1, y1] = this.screenToWorldCell(this.boardRect.right, this.boardRect.bottom);
    return [Math.min(x0, x1), Math.min(y0, y1), Math.max(x0, x1), Math.max(y0, y1)];
  }

  // Called every frame: keeps the board centered and smoothly zooms out
  // just enough that all played tiles stay comfortably in view.
  _updateCamera() {
    const b = this.game.board.bounds();
    let targetCx, targetCy, targetCell;
    if (b === null) {
      targetCx = 0.0; targetCy = 0.0; targetCell = DEFAULT_CELL_SIZE;
    } else {
      const [minX, minY, maxX, maxY] = b;
      const wCells = (maxX - minX + 1) + BOARD_PADDING_CELLS * 2;
      const hCells = (maxY - minY + 1) + BOARD_PADDING_CELLS * 2;
      const fitW = this.boardRect.w / Math.max(1, wCells);
      const fitH = this.boardRect.h / Math.max(1, hCells);
      targetCell = Math.max(MIN_CELL_SIZE, Math.min(DEFAULT_CELL_SIZE, fitW, fitH));
      targetCx = (minX + maxX) / 2;
      targetCy = (minY + maxY) / 2;
    }
    this.cellSize += (targetCell - this.cellSize) * ZOOM_LERP;
    this.camX += (targetCx - this.camX) * ZOOM_LERP;
    this.camY += (targetCy - this.camY) * ZOOM_LERP;
  }

  // ------------------------------------------------------------ actions --

  _sortColor() {
    this._clearPending();
    this.activeSort = "color";
    this.human.sortByColor();
  }

  _sortShape() {
    this._clearPending();
    this.activeSort = "shape";
    this.human.sortByShape();
  }

  _applyActiveSort() {
    if (this.activeSort === "color") this.human.sortByColor();
    else if (this.activeSort === "shape") this.human.sortByShape();
  }

  _toggleSwapMode() {
    this.swapMode = !this.swapMode;
    this.swapSelected = new Set();
    this._clearPending();
  }

  _canConfirmPlace() {
    if (this.swapMode || this.pending.length === 0) return false;
    if (this.game.isFirstMoveOfGame()) {
      if (this.openingOptions && this.openingOptions.length > 1 && this.openingChoice === null) {
        return false;
      }
      const needed = this.openingChoice ? this.openingChoice.length : 0;
      return this.pending.length === needed;
    }
    return true;
  }

  _confirmMove() {
    const move = this.pending.map((p) => [p.x, p.y, p.tile]);
    const res = this.game.playPlace(move);
    if (!res.ok) {
      this._setMessage(res.reason, ERROR_COLOR);
      return;
    }
    let msg = `You scored ${res.score}`;
    if (res.qwirkles) msg += ` (Qwirkle x${res.qwirkles}!)`;
    this._setMessage(msg, GOOD_COLOR);
    this.log.push(`You: +${res.score}` + (res.qwirkles ? " QWIRKLE!" : ""));
    this.pending = [];
    this._applyActiveSort();
    this._refreshOpeningState();
    this._afterTurn(res);
  }

  _confirmSwap() {
    const tiles = Array.from(this.swapSelected).sort((a, b) => a - b).map((i) => this.human.hand[i]);
    const res = this.game.playSwap(tiles);
    if (!res.ok) {
      this._setMessage(res.reason, ERROR_COLOR);
      return;
    }
    this._setMessage(`Swapped ${tiles.length} tile(s).`, GOOD_COLOR);
    this.log.push(`You: swapped ${tiles.length} tile(s)`);
    this.swapMode = false;
    this.swapSelected = new Set();
    this._applyActiveSort();
    this._afterTurn(res);
  }

  _clearPending() {
    this.pending = [];
    this.selectedHandIdx = null;
    this.validSquares = new Set();
  }

  _setMessage(text, color, seconds = 4) {
    this.message = text;
    this.messageColor = color;
    this.messageUntil = performance.now() + seconds * 1000;
  }

  _afterTurn(res) {
    if (res.gameOver) {
      this.gameOverShown = true;
      return;
    }
    // schedule bot turns to run with a human-readable delay
    this.nextBotMoveTime = performance.now() + 1300;
  }

  _startGame() {
    this.gameStarted = true;
    // give it a fresh short delay in case the player sat on the title
    // screen for a while (otherwise a bot going first would fire instantly)
    this.nextBotMoveTime = performance.now() + 1000;
  }

  _restartGame() {
    const names = this.game.players.map((p) => p.name);
    const botsMap = {};
    for (const p of this.game.players) if (p.isBot) botsMap[p.name] = p.bot;

    this.game = new Game(names, { bots: botsMap, seed: null });
    this.human = this.game.players.find((p) => p.name === this.humanName);

    this.selectedHandIdx = null;
    this.pending = [];
    this.validSquares = new Set();
    this.swapMode = false;
    this.swapSelected = new Set();
    this._applyActiveSort();

    this.openingChoice = null;
    this.openingOptions = null;
    this._openingCards = [];

    this.message = "";
    this.messageUntil = 0;
    this.log = [];

    this.camX = 0.0;
    this.camY = 0.0;
    this.cellSize = DEFAULT_CELL_SIZE;

    this.nextBotMoveTime = performance.now() + 1000;
    this.gameOverShown = false;

    this._refreshOpeningState();
  }

  // -------------------------------------------------------- bot driving --

  _buildInfo() {
    const g = this.game;
    const isFirst = g.isFirstMoveOfGame();
    let opening = null;
    if (isFirst) opening = g.openingOptionsForCurrentPlayer().options;
    return {
      isFirstMove: isFirst,
      openingOptions: opening,
      bagCount: g.bag.length,
      scores: Object.fromEntries(g.players.map((p) => [p.name, p.score])),
      handSizes: Object.fromEntries(g.players.map((p) => [p.name, p.hand.length])),
      myName: g.currentPlayer.name,
    };
  }

  _maybeRunBotTurn() {
    if (!this.gameStarted) return;
    const g = this.game;
    if (g.gameOver || g.currentPlayer.name === this.humanName) return;
    if (performance.now() < this.nextBotMoveTime) return;

    const player = g.currentPlayer;
    const bot = player.bot;
    const info = this._buildInfo();
    let action, payload;
    try {
      [action, payload] = bot.chooseMove(g.board, [...player.hand], info);
    } catch (e) {
      action = "swap";
      payload = g.isFirstMoveOfGame() ? null : player.hand.slice(0, 1);
    }

    let res = null;
    if (action === "place" && payload) res = g.playPlace(payload);
    else if (action === "swap" && payload) res = g.playSwap(payload);

    if (res === null || !res.ok) {
      // bot returned something illegal / gave up -- fall back safely.
      // (Opening turns always have a valid forced move, so this fallback
      // only ever applies after the game's first move.)
      if (!g.isFirstMoveOfGame() && player.hand.length) {
        res = g.playSwap([player.hand[0]]);
      }
      if (res === null || !res.ok) {
        this.nextBotMoveTime = performance.now() + 1000;
        return;
      }
    }

    let tag = `${player.name}: `;
    if (res.score || res.bonusAwarded) {
      tag += `+${res.score}`;
      if (res.qwirkles) tag += " QWIRKLE!";
    } else {
      tag += "swapped tiles";
    }
    this.log.push(tag);
    this.log = this.log.slice(-8);

    this._refreshOpeningState();

    if (res.gameOver) {
      this.gameOverShown = true;
    } else {
      this.nextBotMoveTime = performance.now() + 1500;
    }
  }

  // --------------------------------------------------------- hand click --

  // Screen rects for each of the human's hand tiles (left to right).
  _handRects() {
    const n = this.human.hand.length;
    const totalW = n * HAND_TILE_SIZE + (n - 1) * HAND_GAP;
    const startX = this.boardRect.centerx - totalW / 2;
    const rects = [];
    for (let i = 0; i < n; i++) {
      rects.push(new Rect(startX + i * (HAND_TILE_SIZE + HAND_GAP), this.handY, HAND_TILE_SIZE, HAND_TILE_SIZE));
    }
    return rects;
  }

  _usedHandIndices() {
    return new Set(this.pending.map((p) => p.handIndex));
  }

  // Every empty square where the currently-armed hand tile could legally
  // be placed, given whatever's already pending this turn.
  _computeValidSquares() {
    this.validSquares = new Set();
    if (this.swapMode || this.selectedHandIdx === null) return;
    if (this._usedHandIndices().has(this.selectedHandIdx)) return;

    const tile = this.human.hand[this.selectedHandIdx];
    const board = this.game.board;
    const pendingMove = this.pending.map((p) => [p.x, p.y, p.tile]);
    const occupied = new Set(board.cells.keys());
    for (const [x, y] of pendingMove) occupied.add(`${x},${y}`);

    const candidates = new Set();
    if (pendingMove.length) {
      const xs = new Set(pendingMove.map(([x]) => x));
      const ys = new Set(pendingMove.map(([, y]) => y));
      if (pendingMove.length === 1) {
        const [x0, y0] = pendingMove[0];
        for (let d = -6; d <= 6; d++) {
          candidates.add(`${x0 + d},${y0}`);
          candidates.add(`${x0},${y0 + d}`);
        }
      } else if (xs.size === 1) {
        const x0 = [...xs][0];
        const ymin = Math.min(...ys), ymax = Math.max(...ys);
        for (let y = ymin - 6; y <= ymax + 6; y++) candidates.add(`${x0},${y}`);
      } else if (ys.size === 1) {
        const y0 = [...ys][0];
        const xmin = Math.min(...xs), xmax = Math.max(...xs);
        for (let x = xmin - 6; x <= xmax + 6; x++) candidates.add(`${x},${y0}`);
      }
    } else if (board.cells.size) {
      for (const [ax, ay] of board.legalAnchorSquares()) candidates.add(`${ax},${ay}`);
    } else {
      const [x0, y0, x1, y1] = this._visibleWorldBounds();
      for (let x = x0; x <= x1; x++) {
        for (let y = y0; y <= y1; y++) candidates.add(`${x},${y}`);
      }
    }

    for (const key of occupied) candidates.delete(key);

    for (const key of candidates) {
      const [x, y] = key.split(",").map(Number);
      if (board.validateMove([...pendingMove, [x, y, tile]]).ok) {
        this.validSquares.add(key);
      }
    }
  }

  _onHandClick(i) {
    if (this.swapMode) {
      if (this.swapSelected.has(i)) this.swapSelected.delete(i);
      else this.swapSelected.add(i);
      return;
    }
    if (this._usedHandIndices().has(i)) return; // already placed this turn; click the board tile to undo instead
    const tile = this.human.hand[i];
    if (this.game.isFirstMoveOfGame() && this.openingChoice !== null) {
      const allowedSigs = this.openingChoice.map((t) => t.sig());
      const usedSigs = [...this._usedHandIndices()].map((j) => this.human.hand[j].sig());
      const remainingAllowed = [...allowedSigs];
      for (const s of usedSigs) {
        const idx = remainingAllowed.indexOf(s);
        if (idx !== -1) remainingAllowed.splice(idx, 1);
      }
      if (!remainingAllowed.includes(tile.sig())) {
        this._setMessage("That tile isn't part of your chosen opening set.", ERROR_COLOR, 3);
        return;
      }
    }
    this.selectedHandIdx = this.selectedHandIdx === i ? null : i;
    this._computeValidSquares();
  }

  _onBoardClick(wx, wy) {
    if (this.swapMode) return;
    if (this.game.board.occupied(wx, wy)) return;

    // is there a pending tile already here? pick it back up
    const existingIdx = this.pending.findIndex((p) => p.x === wx && p.y === wy);
    if (existingIdx !== -1) {
      this.pending.splice(existingIdx, 1);
      this._computeValidSquares();
      return;
    }

    if (this.selectedHandIdx === null) return;
    if (!this.validSquares.has(`${wx},${wy}`)) return; // not a legal spot for the armed tile -- ignore the click

    const tile = this.human.hand[this.selectedHandIdx];
    this.pending.push({ x: wx, y: wy, tile, handIndex: this.selectedHandIdx });
    this.selectedHandIdx = null;
    this._computeValidSquares();
  }

  // ------------------------------------------------------------- events --

  _bindEvents() {
    this.canvas.addEventListener("click", (e) => this._onClick(e));
    this.canvas.addEventListener("mousemove", (e) => {
      this.mouseX = e.offsetX;
      this.mouseY = e.offsetY;
    });
    window.addEventListener("keydown", (e) => this._onKeyDown(e));
    window.addEventListener("resize", () => {
      this._resizeCanvas();
      this._computeLayout();
      this._buildButtons();
    });
  }

  _isHumanTurn() {
    return this.gameStarted && this.game.currentPlayer.name === this.humanName && !this.game.gameOver;
  }

  _onClick(e) {
    const x = e.offsetX, y = e.offsetY;

    if (!this.gameStarted) {
      this.btnStart.handleClick(x, y);
      return;
    }

    if (this.openingOptions && this.openingOptions.length > 1 && this.openingChoice === null
        && this.game.currentPlayer.name === this.humanName) {
      if (this._handleOpeningClick(x, y)) return;
    }

    if (this.game.gameOver) {
      this.btnPlayAgain.handleClick(x, y);
      return;
    }

    for (const b of this.buttons) {
      if (b.handleClick(x, y)) return;
    }

    if (this._isHumanTurn()) {
      const rects = this._handRects();
      for (let i = 0; i < rects.length; i++) {
        if (rects[i].containsPoint(x, y)) {
          this._onHandClick(i);
          return;
        }
      }
      if (this.boardRect.containsPoint(x, y)) {
        const [wx, wy] = this.screenToWorldCell(x, y);
        this._onBoardClick(wx, wy);
      }
    }
  }

  _onKeyDown(e) {
    if (!this.gameStarted) return;
    if (e.key === "Escape" && this._isHumanTurn()) {
      this._clearPending();
      this.swapMode = false;
      this.swapSelected = new Set();
    }
  }

  // ---------------------------------------------------------- opening ui --

  _drawOpeningSelector() {
    if (!(this.openingOptions && this.openingOptions.length > 1
          && this.openingChoice === null
          && this.game.currentPlayer.name === this.humanName)) {
      this._openingCards = [];
      return;
    }
    const ctx = this.ctx;
    ctx.fillStyle = "rgba(0, 0, 0, 0.63)";
    ctx.fillRect(0, 0, this.screenW, this.screenH);

    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "bold 24px Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Tie for opening move — choose which set to play:", this.screenW / 2, 220);

    const cardW = 220, cardH = 100, gap = 30;
    const n = this.openingOptions.length;
    const totalW = n * cardW + (n - 1) * gap;
    const startX = this.screenW / 2 - totalW / 2;
    const y = 280;
    this._openingCards = [];
    this.openingOptions.forEach((opt, i) => {
      const rect = new Rect(startX + i * (cardW + gap), y, cardW, cardH);
      roundRectPath(ctx, rect.x, rect.y, rect.w, rect.h, 8);
      ctx.fillStyle = PANEL_COLOR;
      ctx.fill();
      ctx.strokeStyle = BUTTON_BORDER;
      ctx.lineWidth = 2;
      ctx.stroke();

      let tx = rect.left + 30;
      for (const t of opt) {
        drawShape(ctx, t.shape, tx, rect.centery, 28 * 0.6, COLOR_RGB[t.color]);
        tx += 45;
      }
      ctx.fillStyle = DIM_TEXT;
      ctx.font = "13px Arial, sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(`${opt.length} tiles`, rect.left + 10, rect.bottom - 12);

      this._openingCards.push({ rect, opt });
    });
  }

  _handleOpeningClick(x, y) {
    for (const { rect, opt } of this._openingCards) {
      if (rect.containsPoint(x, y)) {
        this.openingChoice = opt;
        return true;
      }
    }
    return false;
  }

  // ---------------------------------------------------------------- draw --

  drawTile(rect, tile, { faceUp = true, highlight = null, shapeSize = null } = {}) {
    const ctx = this.ctx;
    roundRectPath(ctx, rect.x, rect.y, rect.w, rect.h, 6);
    ctx.fillStyle = faceUp ? TILE_FACE_COLOR : FACE_DOWN_COLOR;
    ctx.fill();
    ctx.strokeStyle = BUTTON_BORDER;
    ctx.lineWidth = 1;
    ctx.stroke();
    if (faceUp && tile) {
      const size = shapeSize !== null ? shapeSize : rect.w * 0.32;
      drawShape(ctx, tile.shape, rect.centerx, rect.centery, size, COLOR_RGB[tile.color]);
    }
    if (highlight) {
      roundRectPath(ctx, rect.x, rect.y, rect.w, rect.h, 6);
      ctx.strokeStyle = highlight;
      ctx.lineWidth = 3;
      ctx.stroke();
    }
  }

  _drawValidSquares() {
    if (this.validSquares.size === 0) return;
    if (this.game.board.cells.size === 0 && this.pending.length === 0) {
      // Very first tile of the whole game -- any empty square is legal,
      // so highlighting would just paint the entire visible board green.
      // Leave it blank; placement still works anywhere.
      return;
    }
    const ctx = this.ctx;
    const size = Math.max(2, this.cellSize - 2);
    ctx.fillStyle = VALID_SQUARE_COLOR;
    for (const key of this.validSquares) {
      const [x, y] = key.split(",").map(Number);
      const [sx, sy] = this.worldToScreen(x, y);
      if (this.boardRect.containsPoint(sx, sy)) {
        ctx.fillRect(sx - size / 2, sy - size / 2, size, size);
      }
    }
  }

  drawBoard() {
    const ctx = this.ctx;
    ctx.fillStyle = BOARD_BG;
    ctx.fillRect(this.boardRect.x, this.boardRect.y, this.boardRect.w, this.boardRect.h);

    ctx.save();
    ctx.beginPath();
    ctx.rect(this.boardRect.x, this.boardRect.y, this.boardRect.w, this.boardRect.h);
    ctx.clip();

    this._drawValidSquares();

    const tsize = Math.max(1, this.cellSize - TILE_MARGIN);
    // Shapes stay roughly a constant on-screen size as the board zooms
    // out with more tiles -- they only shrink once the tile itself
    // becomes too small to hold them, and never draw past the tile's
    // edge (SHAPE_EDGE_MARGIN keeps a sliver of tile visible around it).
    const maxShapeSize = Math.max(1.0, tsize / 2 - SHAPE_EDGE_MARGIN);
    const boardShapeSize = Math.min(SHAPE_BASE_SIZE, maxShapeSize);

    for (const [key, tile] of this.game.board.cells) {
      const [x, y] = key.split(",").map(Number);
      const [sx, sy] = this.worldToScreen(x, y);
      if (this.boardRect.containsPoint(sx, sy)) {
        const rect = new Rect(sx - tsize / 2, sy - tsize / 2, tsize, tsize);
        this.drawTile(rect, tile, { faceUp: true, shapeSize: boardShapeSize });
      }
    }

    for (const p of this.pending) {
      const [sx, sy] = this.worldToScreen(p.x, p.y);
      const rect = new Rect(sx - tsize / 2, sy - tsize / 2, tsize, tsize);
      this.drawTile(rect, p.tile, { faceUp: true, highlight: PENDING_COLOR, shapeSize: boardShapeSize });
    }

    ctx.restore();
    ctx.strokeStyle = BUTTON_BORDER;
    ctx.lineWidth = 2;
    ctx.strokeRect(this.boardRect.x, this.boardRect.y, this.boardRect.w, this.boardRect.h);
  }

  drawHumanHand() {
    const rects = this._handRects();
    const used = this._usedHandIndices();
    this.human.hand.forEach((tile, i) => {
      const r = rects[i];
      if (used.has(i)) {
        roundRectPath(this.ctx, r.x, r.y, r.w, r.h, 6);
        this.ctx.fillStyle = GHOST_COLOR;
        this.ctx.fill();
        this.ctx.strokeStyle = BUTTON_BORDER;
        this.ctx.lineWidth = 1;
        this.ctx.stroke();
        return;
      }
      let highlight = null;
      if (this.swapMode && this.swapSelected.has(i)) {
        highlight = ERROR_COLOR;
      } else if (this.selectedHandIdx === i) {
        highlight = SELECT_COLOR;
      } else if (this.game.isFirstMoveOfGame() && this.openingChoice !== null
                 && this.game.currentPlayer.name === this.humanName) {
        const sigs = this.openingChoice.map((t) => t.sig());
        if (sigs.includes(tile.sig())) highlight = "rgb(90, 160, 90)";
      }
      this.drawTile(r, tile, { faceUp: true, highlight });
    });
  }

  // Draws `count` face-down tiles centered on (centerX, centerY), laid
  // out horizontally or vertically. Returns the tile rects, in order, so
  // callers can position labels relative to them.
  drawFaceDownRow(centerX, centerY, count, horizontal = true) {
    const size = HAND_TILE_SIZE, gap = HAND_GAP;
    const total = count * size + Math.max(0, count - 1) * gap;
    const rects = [];
    if (horizontal) {
      const startX = centerX - total / 2;
      const y = centerY - size / 2;
      for (let i = 0; i < count; i++) {
        const rect = new Rect(startX + i * (size + gap), y, size, size);
        this.drawTile(rect, null, { faceUp: false });
        rects.push(rect);
      }
    } else {
      const startY = centerY - total / 2;
      const x = centerX - size / 2;
      for (let i = 0; i < count; i++) {
        const rect = new Rect(x, startY + i * (size + gap), size, size);
        this.drawTile(rect, null, { faceUp: false });
        rects.push(rect);
      }
    }
    return rects;
  }

  drawOpponents() {
    const leftP = this.game.players[1];
    const acrossP = this.game.players[2];
    const rightP = this.game.players[3];

    const acrossRects = this.drawFaceDownRow(this.boardRect.centerx, 70, acrossP.hand.length, true);
    const leftRects = this.drawFaceDownRow(90, this.boardRect.centery, leftP.hand.length, false);
    const rightRects = this.drawFaceDownRow(this.screenW - 90, this.boardRect.centery, rightP.hand.length, false);

    if (acrossRects.length) {
      const topY = Math.min(...acrossRects.map((r) => r.top)) - 18;
      this._label(acrossP, this.boardRect.centerx, topY, 0);
    }
    if (leftRects.length) {
      this._label(leftP, leftRects[0].right + 26, this.boardRect.centery, 90); // 90 degrees clockwise
    }
    if (rightRects.length) {
      this._label(rightP, rightRects[0].left - 26, this.boardRect.centery, -90); // 90 degrees counter-clockwise
    }
  }

  // rotateDeg: canvas rotation is clockwise for positive degrees.
  _label(player, x, y, rotateDeg = 0) {
    const turn = this.game.currentPlayer === player;
    const color = turn ? SELECT_COLOR : TEXT_COLOR;
    const text = `${player.name} (${player.score})` + (turn ? " <-" : "");
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(x, y);
    if (rotateDeg) ctx.rotate((rotateDeg * Math.PI) / 180);
    ctx.fillStyle = color;
    ctx.font = "18px Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 0, 0);
    ctx.restore();
  }

  drawScoreboard() {
    const ctx = this.ctx;
    const panel = this.leftPanel;
    roundRectPath(ctx, panel.x, panel.y, panel.w, panel.h, 8);
    ctx.fillStyle = PANEL_COLOR;
    ctx.fill();
    ctx.strokeStyle = BUTTON_BORDER;
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "bold 18px Arial, sans-serif";
    ctx.fillText("Standings", panel.left + 12, panel.top + 26);

    ctx.font = "16px Arial, sans-serif";
    this.game.standings().forEach((p, i) => {
      const y = panel.top + 44 + i * 26 + 12;
      const turn = this.game.currentPlayer === p;
      ctx.fillStyle = turn ? SELECT_COLOR : TEXT_COLOR;
      ctx.fillText(`${p.name}: ${p.score}`, panel.left + 16, y);
    });

    ctx.fillStyle = DIM_TEXT;
    ctx.font = "13px Arial, sans-serif";
    ctx.fillText(`Bag: ${this.game.bag.length} tiles left`, panel.left + 12, panel.bottom - 12);
  }

  drawLog() {
    const ctx = this.ctx;
    const panel = this.rightPanel;
    roundRectPath(ctx, panel.x, panel.y, panel.w, panel.h, 8);
    ctx.fillStyle = PANEL_COLOR;
    ctx.fill();
    ctx.strokeStyle = BUTTON_BORDER;
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "bold 18px Arial, sans-serif";
    ctx.fillText("Log", panel.left + 12, panel.top + 26);

    ctx.fillStyle = DIM_TEXT;
    ctx.font = "13px Arial, sans-serif";
    this.log.slice(-6).forEach((line, i) => {
      ctx.fillText(line, panel.left + 12, panel.top + 44 + i * 22 + 10);
    });
  }

  drawMessage() {
    if (this.message && performance.now() < this.messageUntil) {
      const ctx = this.ctx;
      ctx.fillStyle = this.messageColor;
      ctx.font = "bold 20px Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(this.message, this.boardRect.centerx, this.boardRect.top - 30);
    }
  }

  drawGameOver() {
    if (!this.game.gameOver) return;
    const ctx = this.ctx;
    ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
    ctx.fillRect(0, 0, this.screenW, this.screenH);

    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "bold 26px Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Game Over", this.screenW / 2, 300);

    const standings = this.game.standings();
    ctx.font = "bold 20px Arial, sans-serif";
    standings.forEach((p, i) => {
      const isWinner = i === 0 && (standings.length < 2 || standings[1].score !== p.score);
      const tag = isWinner ? "  WINNER" : "";
      ctx.fillText(`${i + 1}. ${p.name} - ${p.score} pts${tag}`, this.screenW / 2, 360 + i * 34);
    });

    this.btnPlayAgain.draw(ctx, this.mouseX, this.mouseY, 17);
  }

  _drawStartScreen() {
    const ctx = this.ctx;

    // The normal board scene, blurred, as a backdrop. The board is a
    // freshly-dealt real game (empty board, real hands) so this isn't a
    // fake mockup -- it's exactly what the player is about to see.
    ctx.save();
    ctx.filter = "blur(6px)";
    this.drawBoard();
    this.drawOpponents();
    this.drawHumanHand();
    this.drawScoreboard();
    this.drawLog();
    ctx.restore();

    ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
    ctx.fillRect(0, 0, this.screenW, this.screenH);

    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "bold 72px Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Qwirkle!", this.screenW / 2, this.screenH / 2 - 60);

    this.btnStart.draw(ctx, this.mouseX, this.mouseY, 22);
  }

  draw() {
    const ctx = this.ctx;
    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, this.screenW, this.screenH);

    if (!this.gameStarted) {
      this._drawStartScreen();
      return;
    }

    this.drawBoard();
    this.drawOpponents();
    this.drawHumanHand();
    for (const b of this.buttons) b.draw(ctx, this.mouseX, this.mouseY);
    this.drawScoreboard();
    this.drawLog();
    this.drawMessage();
    this._drawOpeningSelector();
    this.drawGameOver();
  }

  // ---------------------------------------------------------------- loop --

  _loop() {
    this._maybeRunBotTurn();
    this._updateCamera();
    this.draw();
    requestAnimationFrame(this._loop);
  }
}
