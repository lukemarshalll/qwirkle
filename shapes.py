"""
shapes.py
Draws the six Qwirkle shapes (Circle, Star, Diamond, Square, Clover, X)
onto a pygame surface. Kept separate from gui.py so the art is easy to
tweak without wading through layout code.
"""

import math
import pygame

WHITE = (255, 255, 255)
BLACK = (20, 20, 20)


def _star_points(center, outer_r, inner_r, points=5, rotation=-90):
    cx, cy = center
    pts = []
    step = math.pi / points
    angle = math.radians(rotation)
    for i in range(points * 2):
        r = outer_r if i % 2 == 0 else inner_r
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        angle += step
    return pts


def draw_shape(surface, shape, center, size, color, outline=BLACK, outline_w=2):
    """
    shape: one of Circle, Star, Diamond, Square, Clover, X
    center: (x, y) pixel center
    size: roughly the shape's radius/half-width in pixels
    """
    cx, cy = center

    if shape == "Circle":
        pygame.draw.circle(surface, color, (int(cx), int(cy)), int(size))
        pygame.draw.circle(surface, outline, (int(cx), int(cy)), int(size), outline_w)

    elif shape == "Square":
        rect = pygame.Rect(0, 0, size * 1.6, size * 1.6)
        rect.center = (cx, cy)
        pygame.draw.rect(surface, color, rect, border_radius=3)
        pygame.draw.rect(surface, outline, rect, outline_w, border_radius=3)

    elif shape == "Diamond":
        pts = [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)]
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, outline, pts, outline_w)

    elif shape == "Star":
        pts = _star_points((cx, cy), size, size * 0.42, points=5)
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, outline, pts, outline_w)

    elif shape == "X":
        w = max(3, int(size * 0.42))
        _thick_line(surface, color, (cx - size, cy - size), (cx + size, cy + size), w, outline, outline_w)
        _thick_line(surface, color, (cx - size, cy + size), (cx + size, cy - size), w, outline, outline_w)

    elif shape == "Clover":
        # A 3-leaf clover: three overlapping circular "leaves" arranged in a
        # triangle around the center, plus a small stem.
        leaf_r = size * 0.55
        offset = size * 0.55
        angles = [-90, 30, 150]  # degrees, evenly spaced (3 leaves)
        for a in angles:
            rad = math.radians(a)
            lx = cx + offset * math.cos(rad)
            ly = cy + offset * math.sin(rad)
            pygame.draw.circle(surface, color, (int(lx), int(ly)), int(leaf_r))
        for a in angles:
            rad = math.radians(a)
            lx = cx + offset * math.cos(rad)
            ly = cy + offset * math.sin(rad)
            pygame.draw.circle(surface, outline, (int(lx), int(ly)), int(leaf_r), outline_w)

    else:
        raise ValueError(f"Unknown shape: {shape}")


def _thick_line(surface, color, p1, p2, width, outline, outline_w):
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1
    nx, ny = -dy / length * (width / 2), dx / length * (width / 2)
    pts = [
        (x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
        (x2 - nx, y2 - ny), (x1 - nx, y1 - ny),
    ]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, outline, pts, max(1, outline_w - 1))
