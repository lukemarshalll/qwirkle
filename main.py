"""
main.py
Run this to play: `python main.py`

Requires pygame (`pip install pygame`) -- everything else in this project
(tiles.py, board.py, player.py, game.py, bots.py) is pure Python with no
dependencies, so you can also import and test the game logic headlessly.

Edit OPPONENT_BOTS below to change who you're playing against -- see
bots.py to build your own.
"""

from game import Game
from gui import QwirkleGUI
from bots import RandomBot, GreedyBot, QwirkleHunterBot

# Seat order is fixed: You (bottom) -> Left -> Across (top) -> Right -> You ...
# This also determines turn order.
PLAYER_NAMES = ["You", "Left", "Across", "Right"]

OPPONENT_BOTS = {
    "Left": GreedyBot(),
    "Across": QwirkleHunterBot(),
    "Right": RandomBot(),
}

SEED = None  # set an int here for a reproducible shuffle/first-player, or leave None


def main():
    game = Game(PLAYER_NAMES, bots=OPPONENT_BOTS, seed=SEED)
    gui = QwirkleGUI(game, human_name="You")
    gui.run()


if __name__ == "__main__":
    main()
