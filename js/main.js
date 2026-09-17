// main.js
// Entry point. Edit OPPONENT_BOTS below to change who you're playing
// against -- see bots.js to build your own.

import { Game } from "./game.js";
import { QwirkleGUI } from "./gui.js";
import { RandomBot, GreedyBot, QwirkleHunterBot } from "./bots.js";

// Seat order is fixed: You (bottom) -> Left -> Across (top) -> Right ->
// You ... This also determines turn order.
const PLAYER_NAMES = ["You", "Left", "Across", "Right"];

const OPPONENT_BOTS = {
  Left: new GreedyBot(),
  Across: new QwirkleHunterBot(),
  Right: new RandomBot(),
};

const SEED = null; // set a number here for a reproducible shuffle/first-player, or leave null

function main() {
  const canvas = document.getElementById("game");
  const game = new Game(PLAYER_NAMES, { bots: OPPONENT_BOTS, seed: SEED });
  const gui = new QwirkleGUI(canvas, game, "You");
  gui.start();
}

main();
