"""
bots.py
========
This is the file you edit to build your own Qwirkle AI opponents.

Every bot is a class with one required method:

    choose_move(self, board, hand, info) -> ("place", move) | ("swap", tiles)

    board : board.Board       - read-only view of the current board. Do not
                                 mutate it. Use board.validate_move(move) to
                                 check any placement you're considering.
    hand  : list[tiles.Tile]  - this bot's current 6 (or fewer) tiles.
    info  : dict              - extra context:
        info["is_first_move"]      bool  - True only on the very first turn
                                            of the whole game
        info["opening_options"]    list[list[Tile]] or None
                                    - if is_first_move, the legal maximal
                                      matching sets you're allowed to open
                                      with (house rule). Pick one of these
                                      EXACTLY (same multiset of tiles) if
                                      is_first_move is True.
        info["bag_count"]          int   - tiles left in the bag
        info["scores"]             dict  name -> current score
        info["hand_sizes"]         dict  name -> tiles left in each hand
        info["my_name"]            str   - this bot's own player name

    Return value:
        ("place", [(x, y, tile), ...])   - a legal placement (one straight
                                            line, connected to the board,
                                            per Qwirkle rules)
        ("swap",  [tile, ...])           - discard these tiles, draw
                                            replacements, forfeit the turn
                                            (not legal on the opening move)

    The game engine re-validates whatever you return and will treat an
    illegal move as a forfeited turn, so it's in your interest to only
    return moves you've checked with board.validate_move(...).

Two helpers are provided so you don't have to write move-generation
yourself:

    generate_legal_placements(board, hand)  -> list of legal moves
    best_opening_choice(options)            -> picks an opening set

Look at RandomBot and GreedyBot below for two complete, working examples.
Scroll to the bottom for a blank template to fill in your own heuristic.
"""

import random
from itertools import permutations


# ----------------------------------------------------------------------
# Move generation helpers -- shared by all bots, so you don't have to
# reimplement "what placements are even legal" every time.
# ----------------------------------------------------------------------

def generate_legal_placements(board, hand, max_run=4, max_anchors=50):
    """
    Search for legal placements (single- and multi-tile) using the current
    board and hand. Not exhaustive on very crowded boards (it caps how many
    anchor squares and how long a run it tries, for speed) but it finds the
    large majority of legal moves, including all single-tile moves.

    Returns a list of moves, where each move is [(x, y, tile), ...].

    max_run: largest number of tiles it will try to lay down in one line
             (raise this for a stronger, slower bot).
    max_anchors: cap on how many candidate anchor squares to explore
                 (raise this on a sparse board for more options, at a
                 speed cost on a crowded one).
    """
    if board.is_empty():
        return []  # opening move is handled separately -- see best_opening_choice

    moves = []
    seen = set()

    def record(move):
        key = frozenset(((x, y), t.color, t.shape) for x, y, t in move)
        if key not in seen:
            seen.add(key)
            moves.append(move)

    unique_hand = list({t: t for t in hand}.values())  # dedupe identical tiles

    anchors = list(board.legal_anchor_squares())
    if len(anchors) > max_anchors:
        anchors = anchors[:max_anchors]

    for anchor in anchors:
        # single-tile placements
        for t in unique_hand:
            ok, _ = board.validate_move([(anchor[0], anchor[1], t)])
            if ok:
                record([(anchor[0], anchor[1], t)])

        # multi-tile runs starting at this anchor, in each direction
        for step in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            run_len = min(max_run, len(unique_hand))
            for size in range(2, run_len + 1):
                for combo in permutations(unique_hand, size):
                    candidate = []
                    ok_positions = True
                    for i, t in enumerate(combo):
                        p = (anchor[0] + step[0] * i, anchor[1] + step[1] * i)
                        if board.occupied(p):
                            ok_positions = False
                            break
                        candidate.append((p[0], p[1], t))
                    if not ok_positions:
                        continue
                    ok, _ = board.validate_move(candidate)
                    if ok:
                        record(candidate)

    return moves


def score_placement(board, move):
    """Convenience: validate + score a candidate move in one call.
    Returns (score, qwirkle_count) or (None, None) if illegal."""
    ok, lines = board.validate_move(move)
    if not ok:
        return None, None
    score = board.score_move(lines)
    qwirkles = sum(1 for line in lines if len(line) == 6)
    return score, qwirkles


def best_opening_choice(options, strategy="random"):
    """Pick which tied maximal opening set to play. `options` comes from
    info["opening_options"]. Strategies: 'random' or 'first'."""
    if strategy == "first":
        return options[0]
    return random.choice(options)


# ----------------------------------------------------------------------
# Bot interface
# ----------------------------------------------------------------------

class Bot:
    name = "Bot"

    def choose_move(self, board, hand, info):
        raise NotImplementedError


# ----------------------------------------------------------------------
# Example 1: RandomBot -- plays any legal move at random, swaps if it
# can't find one. Good baseline / sanity check opponent.
# ----------------------------------------------------------------------

class RandomBot(Bot):
    name = "RandomBot"

    def choose_move(self, board, hand, info):
        if info["is_first_move"]:
            chosen = best_opening_choice(info["opening_options"], strategy="random")
            move = [(i, 0, t) for i, t in enumerate(chosen)]
            return ("place", move)

        moves = generate_legal_placements(board, hand)
        if moves:
            return ("place", random.choice(moves))

        # nothing legal found -- swap a random handful of tiles
        n = random.randint(1, len(hand))
        return ("swap", random.sample(hand, n))


# ----------------------------------------------------------------------
# Example 2: GreedyBot -- among every legal move it can find, plays the
# one worth the most points this turn (ties broken randomly). This is a
# genuinely decent Qwirkle opponent despite being "just" greedy, because
# in Qwirkle immediate score correlates strongly with good positioning.
# ----------------------------------------------------------------------

class GreedyBot(Bot):
    name = "GreedyBot"

    def choose_move(self, board, hand, info):
        if info["is_first_move"]:
            chosen = best_opening_choice(info["opening_options"], strategy="random")
            move = [(i, 0, t) for i, t in enumerate(chosen)]
            return ("place", move)

        moves = generate_legal_placements(board, hand)
        if not moves:
            n = random.randint(1, min(3, len(hand)))
            return ("swap", random.sample(hand, n))

        best_move, best_score = None, -1
        for move in moves:
            score, _ = score_placement(board, move)
            if score is None:
                continue
            if score > best_score:
                best_move, best_score = move, score
        return ("place", best_move)


# ----------------------------------------------------------------------
# Example 3: QwirkleHunterBot -- greedy, but breaks ties in favor of
# moves that complete a Qwirkle (a full line of 6), and secondarily
# prefers moves that use more tiles (empties its hand faster, useful
# near the end of the bag). Shows how to layer a richer heuristic on
# top of the same move list GreedyBot uses.
# ----------------------------------------------------------------------

class QwirkleHunterBot(Bot):
    name = "QwirkleHunterBot"

    def choose_move(self, board, hand, info):
        if info["is_first_move"]:
            chosen = best_opening_choice(info["opening_options"], strategy="random")
            move = [(i, 0, t) for i, t in enumerate(chosen)]
            return ("place", move)

        moves = generate_legal_placements(board, hand)
        if not moves:
            n = random.randint(1, min(3, len(hand)))
            return ("swap", random.sample(hand, n))

        def key(move):
            score, qwirkles = score_placement(board, move)
            if score is None:
                return (-1, -1, -1)
            return (qwirkles, score, len(move))

        best_move = max(moves, key=key)
        return ("place", best_move)


# ----------------------------------------------------------------------
# Write your own bot here. `board` is read-only; use
# board.validate_move(move) to check anything before returning it.
# See generate_legal_placements() and score_placement() above -- you're
# welcome to call them, or write your own smarter search.
# ----------------------------------------------------------------------

class MyCustomBot(Bot):
    name = "MyCustomBot"

    def choose_move(self, board, hand, info):
        if info["is_first_move"]:
            # info["opening_options"] is a list of tied maximal tile sets --
            # you must play one of them exactly, as the opening move.
            chosen = best_opening_choice(info["opening_options"])
            move = [(i, 0, t) for i, t in enumerate(chosen)]
            return ("place", move)

        moves = generate_legal_placements(board, hand)
        if not moves:
            return ("swap", hand[:1])

        # TODO: replace this with your own heuristic. A few ideas:
        #  - prefer moves that set up (but don't complete) long lines for
        #    yourself next turn
        #  - avoid leaving juicy multi-color/shape intersections open for
        #    opponents
        #  - weight by hand composition (e.g. dump colors you're holding
        #    too many of)
        best_move, best_score = None, -1
        for move in moves:
            score, _ = score_placement(board, move)
            if score is not None and score > best_score:
                best_move, best_score = move, score
        return ("place", best_move)
