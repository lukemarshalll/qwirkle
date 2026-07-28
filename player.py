"""
player.py
A player's hand + score bookkeeping. Works the same whether the player
is the human or a bot -- the difference is only in who decides the move.
"""

HAND_SIZE = 6


class Player:
    def __init__(self, name, is_bot=False, bot=None):
        self.name = name
        self.is_bot = is_bot
        self.bot = bot  # instance of a class from bots.py, or None for human
        self.hand = []
        self.score = 0

    def refill(self, bag):
        need = HAND_SIZE - len(self.hand)
        if need > 0:
            self.hand.extend(bag.draw(need))

    def remove_tiles(self, tiles):
        """Remove the given tiles (a list of Tile) from hand."""
        for t in tiles:
            for i, h in enumerate(self.hand):
                if h == t:
                    del self.hand[i]
                    break
            else:
                raise ValueError(f"Tile {t} not in {self.name}'s hand")

    def has_tiles(self, tiles):
        pool = list(self.hand)
        for t in tiles:
            for i, h in enumerate(pool):
                if h == t:
                    del pool[i]
                    break
            else:
                return False
        return True

    def sort_by_color(self):
        color_order = {c: i for i, c in enumerate(
            ["Red", "Orange", "Yellow", "Green", "Blue", "Purple"])}
        self.hand.sort(key=lambda t: (color_order[t.color], t.shape))

    def sort_by_shape(self):
        shape_order = {s: i for i, s in enumerate(
            ["Circle", "Star", "Diamond", "Square", "Clover", "X"])}
        self.hand.sort(key=lambda t: (shape_order[t.shape], t.color))
