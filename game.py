"""
game.py
The turn-based game engine that ties Board + Player + TileBag together
and enforces the house rules described by the designer:

  - 4 players, 6-tile hands, replenish to 6 immediately after playing.
  - First player is chosen at random.
  - The first player's opening move must use the MAXIMUM number of tiles
    from their hand that share either a color (all different shapes) or a
    shape (all different colors). Ties are resolved by the player.
  - Score for a placement = sum of the length of every line (row/column)
    touched by the move (min length 2 to count), with a Qwirkle
    (a complete line of 6) worth double (i.e. +6 bonus on top of the 6).
  - The game ends the instant a player empties their hand and the bag has
    no tiles left to refill them. That player gets a +6 bonus added to
    the score of the turn that emptied their hand.
"""

import random
from collections import defaultdict

from tiles import TileBag, Tile, COLORS, SHAPES
from board import Board
from player import Player, HAND_SIZE


def find_max_matching_sets(hand):
    """
    Find the largest subset(s) of `hand` that could legally form a single
    straight line on an empty board (all same color w/ distinct shapes,
    OR all same shape w/ distinct colors).

    Returns (options, max_size) where `options` is a list of tile-lists,
    one per distinct maximal set (there's more than one entry only when
    there's a genuine tie for the largest size).
    """
    if not hand:
        return [], 0

    by_color = defaultdict(dict)  # color -> {shape: tile}
    by_shape = defaultdict(dict)  # shape -> {color: tile}
    for t in hand:
        by_color[t.color].setdefault(t.shape, t)
        by_shape[t.shape].setdefault(t.color, t)

    candidates = [list(v.values()) for v in by_color.values()]
    candidates += [list(v.values()) for v in by_shape.values()]

    max_size = max(len(c) for c in candidates)
    best = [c for c in candidates if len(c) == max_size]

    unique, seen = [], set()
    for c in best:
        sig = frozenset((t.color, t.shape) for t in c)
        if sig not in seen:
            seen.add(sig)
            unique.append(c)

    return unique, max_size


class TurnResult:
    def __init__(self, ok, reason=None, score=0, qwirkles=0, game_over=False,
                 winner=None, bonus_awarded=0):
        self.ok = ok
        self.reason = reason
        self.score = score
        self.qwirkles = qwirkles
        self.game_over = game_over
        self.winner = winner
        self.bonus_awarded = bonus_awarded

    def __repr__(self):
        if not self.ok:
            return f"TurnResult(FAILED: {self.reason})"
        return (f"TurnResult(ok, score={self.score}, qwirkles={self.qwirkles}, "
                f"game_over={self.game_over})")


class Game:
    def __init__(self, player_names, bots=None, seed=None):
        """
        player_names: list of 4 display names, in seat order
                       (e.g. [You, Left, Across, Right])
        bots: dict {name: bot_instance} for any non-human players.
              A player with no entry / name not in bots is treated as human.
        """
        assert len(player_names) == 4, "Qwirkle here is fixed to 4 players."
        bots = bots or {}
        self.rng = random.Random(seed)
        self.bag = TileBag(seed=seed)
        self.board = Board()
        self.players = [
            Player(name, is_bot=name in bots, bot=bots.get(name))
            for name in player_names
        ]
        for p in self.players:
            p.refill(self.bag)

        self.current_index = self.rng.randrange(4)
        self.first_player_index = self.current_index
        self.first_move_done = False
        self.turn_number = 0
        self.game_over = False
        self.winner = None
        self.history = []  # list of dicts describing each turn, for UI/debug

    # ---------- state accessors ----------

    @property
    def current_player(self):
        return self.players[self.current_index]

    def is_first_move_of_game(self):
        return not self.first_move_done

    def opening_options_for_current_player(self):
        """Only meaningful when is_first_move_of_game() is True."""
        return find_max_matching_sets(self.current_player.hand)

    # ---------- turn actions ----------

    def play_place(self, move):
        """
        move: list of (x, y, tile)
        Validates against Board rules AND, if this is the game's opening
        move, against the "must play your max matching set" house rule.
        """
        player = self.current_player

        placed_tiles = [t for _, _, t in move]
        if not player.has_tiles(placed_tiles):
            return TurnResult(False, reason="You don't have those tiles in hand.")

        if self.is_first_move_of_game():
            options, max_size = self.opening_options_for_current_player()
            if len(placed_tiles) != max_size:
                return TurnResult(
                    False,
                    reason=(f"Opening move must use your maximum matching set "
                            f"({max_size} tiles)."))
            played_sig = frozenset((t.color, t.shape) for t in placed_tiles)
            valid_sigs = [frozenset((t.color, t.shape) for t in opt) for opt in options]
            if played_sig not in valid_sigs:
                return TurnResult(
                    False,
                    reason="Opening tiles must all share a color or all share a shape.")
            # opening move: any straight-line arrangement of these tiles is fine,
            # board validate_move will confirm colinearity/order.

        ok, result = self.board.validate_move(move)
        if not ok:
            return TurnResult(False, reason=result)
        lines = result

        score = self.board.score_move(lines)
        qwirkles = sum(1 for line in lines if len(line) == 6)

        self.board.apply_move(move)
        player.remove_tiles(placed_tiles)
        player.refill(self.bag)

        player.score += score

        game_over = False
        winner = None
        bonus = 0
        if len(player.hand) == 0 and self.bag.is_empty():
            bonus = 6
            player.score += bonus
            game_over = True
            self.game_over = True
            winner = self._determine_winner()
            self.winner = winner

        self.first_move_done = True
        self.turn_number += 1
        result_obj = TurnResult(True, score=score, qwirkles=qwirkles,
                                 game_over=game_over, winner=winner,
                                 bonus_awarded=bonus)
        self.history.append({
            "player": player.name, "type": "place", "score": score,
            "qwirkles": qwirkles, "tiles": [str(t) for t in placed_tiles],
        })
        if not game_over:
            self._advance_turn()
        return result_obj

    def play_swap(self, tiles):
        """Discard `tiles` back into the bag and draw the same number of
        replacements. Forfeits the turn (0 points). Not allowed as the
        very first move of the game (there'd be nothing to swap for)."""
        player = self.current_player
        if self.is_first_move_of_game():
            return TurnResult(False, reason="You must make the opening move; you can't swap first.")
        if not tiles:
            return TurnResult(False, reason="Select at least one tile to swap.")
        if not player.has_tiles(tiles):
            return TurnResult(False, reason="You don't have those tiles in hand.")
        if len(tiles) > len(self.bag):
            return TurnResult(False, reason="Not enough tiles left in the bag to swap that many.")

        player.remove_tiles(tiles)
        new_tiles = self.bag.draw(len(tiles))
        player.hand.extend(new_tiles)
        self.bag.tiles.extend(tiles)
        self.rng.shuffle(self.bag.tiles)

        self.turn_number += 1
        self.history.append({"player": player.name, "type": "swap",
                              "count": len(tiles)})
        self._advance_turn()
        return TurnResult(True, score=0)

    def has_any_legal_move(self, player=None):
        """Cheap-ish check used by bots/UI to decide whether a swap is
        the only option. Not exhaustive-search-optimal, just practical."""
        player = player or self.current_player
        if self.is_first_move_of_game():
            return True  # opening move is always possible
        if self.board.is_empty():
            return True
        for anchor in self.board.legal_anchor_squares():
            for t in player.hand:
                ok, _ = self.board.validate_move([(anchor[0], anchor[1], t)])
                if ok:
                    return True
        return False

    # ---------- internal ----------

    def _advance_turn(self):
        self.current_index = (self.current_index + 1) % 4

    def _determine_winner(self):
        best = max(self.players, key=lambda p: p.score)
        ties = [p for p in self.players if p.score == best.score]
        if len(ties) > 1:
            return None  # tie -- let the caller display all tied players
        return best

    def standings(self):
        return sorted(self.players, key=lambda p: -p.score)
