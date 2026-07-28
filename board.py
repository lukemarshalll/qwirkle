"""
board.py
The Qwirkle board: an unbounded grid of (x, y) -> Tile.

A "move" is a list of (x, y, tile) triples representing everything a
player places down on a single turn. This module validates moves against
the real Qwirkle placement rules and computes the resulting score.
"""

from collections import defaultdict
from tiles import Tile


class InvalidMove(Exception):
    """Raised (as a reason string, not actually thrown during normal play)
    to explain why a candidate move is illegal."""
    pass


class Board:
    def __init__(self):
        self.cells = {}  # (x, y) -> Tile

    def is_empty(self):
        return len(self.cells) == 0

    def get(self, pos):
        return self.cells.get(pos)

    def occupied(self, pos):
        return pos in self.cells

    # ---------- line helpers ----------

    @staticmethod
    def _line_cells(temp_cells, pos, direction):
        """Return the contiguous run of occupied cells through `pos` in
        `direction` ('h' = varying x, same y; 'v' = varying y, same x),
        as a sorted list of (pos, tile)."""
        x, y = pos
        step = (1, 0) if direction == "h" else (0, 1)
        cells = [pos]

        cx, cy = x - step[0], y - step[1]
        while (cx, cy) in temp_cells:
            cells.insert(0, (cx, cy))
            cx -= step[0]
            cy -= step[1]

        cx, cy = x + step[0], y + step[1]
        while (cx, cy) in temp_cells:
            cells.append((cx, cy))
            cx += step[0]
            cy += step[1]

        return [(p, temp_cells[p]) for p in cells]

    @staticmethod
    def _line_valid(line):
        """A line (list of (pos, tile)) is valid if every tile shares a
        color (with all-distinct shapes) or shares a shape (with all
        distinct colors), has no duplicate tile, and is at most 6 long."""
        tiles = [t for _, t in line]
        if len(tiles) > 6:
            return False
        sigs = {(t.color, t.shape) for t in tiles}
        if len(sigs) != len(tiles):
            return False  # duplicate tile in the line
        colors = {t.color for t in tiles}
        shapes = {t.shape for t in tiles}
        return len(colors) == 1 or len(shapes) == 1

    # ---------- validation ----------

    def validate_move(self, move):
        """
        move: list of (x, y, tile)
        Returns (ok: bool, reason_or_lines):
            if ok -> (True, lines) where lines is the list of resulting
                     lines (each a list of (pos, tile)) touched by this move
            if not ok -> (False, "human readable reason")
        """
        if not move:
            return False, "No tiles placed."

        positions = [(x, y) for x, y, _ in move]
        if len(set(positions)) != len(positions):
            return False, "Can't place two tiles on the same square."

        for pos in positions:
            if self.occupied(pos):
                return False, f"Square {pos} is already occupied."

        tile_map = {(x, y): t for x, y, t in move}
        temp_cells = dict(self.cells)
        temp_cells.update(tile_map)

        if len(move) > 1:
            xs = {x for x, y in positions}
            ys = {y for x, y in positions}
            if len(xs) == 1:
                main_dir = "v"
            elif len(ys) == 1:
                main_dir = "h"
            else:
                return False, "All tiles in a turn must be placed in a single straight line."
        else:
            main_dir = None

        lines = []

        if main_dir:
            main_line = self._line_cells(temp_cells, positions[0], main_dir)
            main_line_positions = {p for p, _ in main_line}
            for p in positions:
                if p not in main_line_positions:
                    return False, "Tiles must form one contiguous line (no gaps)."
            if not self._line_valid(main_line):
                return False, "The main line has a color/shape conflict or duplicate."
            lines.append(main_line)

            perp_dir = "h" if main_dir == "v" else "v"
            for p in positions:
                pline = self._line_cells(temp_cells, p, perp_dir)
                if len(pline) > 1:
                    if not self._line_valid(pline):
                        return False, f"Cross line through {p} has a color/shape conflict or duplicate."
                    lines.append(pline)
        else:
            pos = positions[0]
            for d in ("h", "v"):
                line = self._line_cells(temp_cells, pos, d)
                if len(line) > 1:
                    if not self._line_valid(line):
                        return False, "Placement conflicts with an existing line."
                    lines.append(line)

        if not self.is_empty():
            touches_existing = any(
                any(p in self.cells for p, _ in line) for line in lines
            )
            if not touches_existing:
                return False, "Your tiles must connect to tiles already on the board."

        return True, lines

    def score_move(self, lines):
        """Given the validated `lines` from validate_move, compute the score."""
        total = 0
        for line in lines:
            n = len(line)
            if n < 2:
                continue
            total += n
            if n == 6:
                total += 6  # Qwirkle bonus
        return total

    def apply_move(self, move):
        for x, y, t in move:
            self.cells[(x, y)] = t

    # ---------- convenience for bots/GUI ----------

    def legal_anchor_squares(self):
        """All empty squares adjacent to at least one occupied square --
        useful for bots scanning for candidate placements."""
        if self.is_empty():
            return {(0, 0)}
        anchors = set()
        for (x, y) in self.cells:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, y + dy)
                if p not in self.cells:
                    anchors.add(p)
        return anchors

    def bounds(self):
        """(min_x, min_y, max_x, max_y) of played tiles, or None if empty."""
        if self.is_empty():
            return None
        xs = [x for x, y in self.cells]
        ys = [y for x, y in self.cells]
        return min(xs), min(ys), max(xs), max(ys)
