"""
tiles.py
Defines the Tile object and the TileBag (the draw pile of all 108 tiles).
"""

import random

COLORS = ["Red", "Orange", "Yellow", "Green", "Blue", "Purple"]
SHAPES = ["Circle", "Star", "Diamond", "Square", "Clover", "Triangle"]

# How each shape/color is drawn (used by the GUI). Kept here so both the
# GUI and any headless/debug rendering share one source of truth.
COLOR_RGB = {
    "Red": (211, 47, 47),
    "Orange": (245, 124, 0),
    "Yellow": (251, 192, 45),
    "Green": (56, 142, 60),
    "Blue": (25, 118, 210),
    "Purple": (123, 31, 162),
}


class Tile:
    """A single Qwirkle tile: one shape, one color."""

    __slots__ = ("color", "shape")

    def __init__(self, color: str, shape: str):
        if color not in COLORS:
            raise ValueError(f"Invalid color: {color}")
        if shape not in SHAPES:
            raise ValueError(f"Invalid shape: {shape}")
        self.color = color
        self.shape = shape

    def __eq__(self, other):
        return (
            isinstance(other, Tile)
            and self.color == other.color
            and self.shape == other.shape
        )

    def __hash__(self):
        return hash((self.color, self.shape))

    def __repr__(self):
        return f"{self.color} {self.shape}"

    def to_dict(self):
        return {"color": self.color, "shape": self.shape}

    @staticmethod
    def from_dict(d):
        return Tile(d["color"], d["shape"])


class TileBag:
    """The shared draw pile. Starts with 3 copies of each of the 36 unique tiles (108 total)."""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self.tiles = [
            Tile(color, shape)
            for color in COLORS
            for shape in SHAPES
            for _ in range(3)
        ]
        self._rng.shuffle(self.tiles)

    def __len__(self):
        return len(self.tiles)

    def is_empty(self):
        return len(self.tiles) == 0

    def draw(self, count: int):
        """Draw up to `count` tiles. Returns fewer if the bag runs low."""
        drawn = self.tiles[:count]
        self.tiles = self.tiles[count:]
        return drawn

    def draw_one(self):
        drawn = self.draw(1)
        return drawn[0] if drawn else None
