"""
gui.py
Top-down pygame table view for Qwirkle:

            [ Across's hand, face down ]
    [Left's                              [Right's
     hand,        [   BOARD   ]           hand,
     face down]                           face down]
            [ YOUR hand, face up ]
            [ Sort by Color/Shape ]
            [ Confirm / Clear / Swap ]

Seat / turn order is always You -> Left -> Across -> Right -> You ...

Run this file directly (`python main.py`) rather than importing it for
a quick game; see main.py for how a Game + bots are wired in.
"""

import sys
import time
import pygame

from tiles import COLOR_RGB
from shapes import draw_shape
from board import Board
from game import Game

# ---------------------------------------------------------------- layout --

BG_COLOR = (30, 34, 40)
BOARD_BG = (42, 47, 56)
PANEL_COLOR = (24, 27, 32)
TEXT_COLOR = (230, 230, 235)
DIM_TEXT = (150, 155, 165)
FACE_DOWN_COLOR = (18, 20, 24)
SELECT_COLOR = (255, 215, 0)
PENDING_COLOR = (120, 200, 255)
ERROR_COLOR = (240, 90, 90)
GOOD_COLOR = (120, 220, 140)
VALID_SQUARE_COLOR = (90, 220, 120, 100)
BUTTON_COLOR = (55, 61, 72)
BUTTON_HOVER = (75, 82, 96)
BUTTON_ACTIVE = (60, 110, 150)
BUTTON_BORDER = (100, 108, 122)

DEFAULT_CELL_SIZE = 46
MIN_CELL_SIZE = 14
BOARD_PADDING_CELLS = 2   # empty margin (in cells) kept around played tiles
ZOOM_LERP = 0.08
TILE_MARGIN = 4
SHAPE_EDGE_MARGIN = 3     # px gap kept between a shape's edge and its tile's edge
SHAPE_BASE_SIZE = (DEFAULT_CELL_SIZE - TILE_MARGIN) * 0.32  # shapes hold this size as the board zooms out

HAND_TILE_SIZE = 56
HAND_GAP = 8

# The window fills the whole screen: screen size and every rect derived
# from it (board, hand row, buttons, side panels) are computed at
# runtime in QwirkleGUI._compute_layout() from the actual display
# resolution, not hardcoded here.


class Button:
    def __init__(self, rect, label, callback, enabled_fn=None, active_fn=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.enabled_fn = enabled_fn or (lambda: True)
        self.active_fn = active_fn or (lambda: False)

    def enabled(self):
        return self.enabled_fn()

    def draw(self, surf, font, mouse_pos):
        enabled = self.enabled()
        active = self.active_fn()
        hovered = enabled and self.rect.collidepoint(mouse_pos)
        if not enabled:
            color = (40, 43, 49)
        elif active:
            color = BUTTON_ACTIVE
        elif hovered:
            color = BUTTON_HOVER
        else:
            color = BUTTON_COLOR
        pygame.draw.rect(surf, color, self.rect, border_radius=6)
        border = SELECT_COLOR if active else BUTTON_BORDER
        pygame.draw.rect(surf, border, self.rect, 2 if active else 1, border_radius=6)
        text_color = TEXT_COLOR if enabled else DIM_TEXT
        txt = font.render(self.label, True, text_color)
        surf.blit(txt, txt.get_rect(center=self.rect.center))

    def handle_click(self, pos):
        if self.enabled() and self.rect.collidepoint(pos):
            self.callback()
            return True
        return False


class QwirkleGUI:
    def __init__(self, game: Game, human_name="You"):
        pygame.init()
        pygame.display.set_caption("Qwirkle")
        display_info = pygame.display.Info()
        self.screen = pygame.display.set_mode((display_info.current_w, display_info.current_h))
        self.clock = pygame.time.Clock()
        self._compute_layout()

        self.font = pygame.font.SysFont("arial", 18)
        self.font_small = pygame.font.SysFont("arial", 14)
        self.font_big = pygame.font.SysFont("arial", 26, bold=True)
        self.font_med = pygame.font.SysFont("arial", 20, bold=True)

        self.game = game
        self.human_name = human_name
        self.human = next(p for p in game.players if p.name == human_name)

        # camera: world coords centered in self.board_rect; both are animated
        # automatically each frame (see _update_camera) -- no manual pan.
        self.cam_x, self.cam_y = 0.0, 0.0
        self.cell_size = float(DEFAULT_CELL_SIZE)

        # turn-local human state
        self.selected_hand_idx = None      # index into human.hand "armed" for placing
        self.pending = []                  # list of (x, y, tile, hand_index_used)
        self.valid_squares = set()         # legal board squares for the armed tile
        self.swap_mode = False
        self.swap_selected = set()         # indices into human.hand marked to swap
        self.active_sort = None            # None | 'color' | 'shape' -- stays applied

        self.opening_choice = None         # chosen tile set (list[Tile]) during a tied opening
        self.opening_options = None

        self.message = ""
        self.message_color = TEXT_COLOR
        self.message_until = 0

        self.log = []  # recent turn history strings, newest last

        # Ready to move shortly -- if the randomly-chosen first player is a
        # bot, this must be a real timestamp (not None) or the bot turn
        # never fires.
        self.next_bot_move_time = time.time() + 1.0
        self.game_over_shown = False

        self._build_buttons()
        self._refresh_opening_state()

    # ------------------------------------------------------------ setup --

    def _compute_layout(self):
        """Derives every screen-position rect from the actual window size,
        so the game fills whatever display it's run on."""
        self.screen_w, self.screen_h = self.screen.get_size()

        board_w = int(self.screen_w * 0.54)
        board_h = int(self.screen_h * 0.56)
        board_x = (self.screen_w - board_w) // 2
        board_y = int(self.screen_h * 0.17)
        self.board_rect = pygame.Rect(board_x, board_y, board_w, board_h)

        self.hand_y = self.board_rect.bottom + 14
        self.sort_y = self.hand_y + HAND_TILE_SIZE + 10
        self.action_y = self.sort_y + 32 + 12

        self.left_panel = pygame.Rect(20, self.screen_h - 220, 260, 200)
        self.right_panel = pygame.Rect(self.screen_w - 280, self.screen_h - 220, 260, 200)

    def _build_buttons(self):
        sort_w, sort_gap = 150, 20
        total = sort_w * 2 + sort_gap
        sx = self.board_rect.centerx - total // 2
        self.btn_sort_color = Button((sx, self.sort_y, sort_w, 32), "Sort by Color",
                                      self._sort_color, active_fn=lambda: self.active_sort == "color")
        self.btn_sort_shape = Button((sx + sort_w + sort_gap, self.sort_y, sort_w, 32), "Sort by Shape",
                                      self._sort_shape, active_fn=lambda: self.active_sort == "shape")

        act_w, act_gap = 150, 10
        act_total = act_w * 4 + act_gap * 3
        ax = self.board_rect.centerx - act_total // 2
        self.btn_confirm = Button((ax, self.action_y, act_w, 34), "Confirm Move",
                                   self._confirm_move, self._can_confirm_place)
        self.btn_clear = Button((ax + (act_w + act_gap), self.action_y, act_w, 34), "Clear Placement",
                                 self._clear_pending, lambda: len(self.pending) > 0)
        self.btn_swap_toggle = Button((ax + 2 * (act_w + act_gap), self.action_y, act_w, 34), "Swap Tiles...",
                                       self._toggle_swap_mode,
                                       lambda: not self.game.is_first_move_of_game(),
                                       active_fn=lambda: self.swap_mode)
        self.btn_confirm_swap = Button((ax + 3 * (act_w + act_gap), self.action_y, act_w, 34), "Confirm Swap",
                                        self._confirm_swap,
                                        lambda: self.swap_mode and len(self.swap_selected) > 0)

        self.buttons = [self.btn_sort_color, self.btn_sort_shape, self.btn_confirm,
                         self.btn_clear, self.btn_swap_toggle, self.btn_confirm_swap]

    def _refresh_opening_state(self):
        if self.game.is_first_move_of_game() and self.game.current_player is self.human:
            options, _ = self.game.opening_options_for_current_player()
            self.opening_options = options
            self.opening_choice = options[0] if len(options) == 1 else None
        else:
            self.opening_options = None
            self.opening_choice = None

    # ------------------------------------------------------------ coords --

    def world_to_screen(self, wx, wy):
        sx = self.board_rect.centerx + (wx - self.cam_x) * self.cell_size
        sy = self.board_rect.centery + (wy - self.cam_y) * self.cell_size
        return sx, sy

    def screen_to_world_cell(self, sx, sy):
        wx = (sx - self.board_rect.centerx) / self.cell_size + self.cam_x
        wy = (sy - self.board_rect.centery) / self.cell_size + self.cam_y
        return int(round(wx)), int(round(wy))

    def _visible_world_bounds(self):
        x0, y0 = self.screen_to_world_cell(self.board_rect.left, self.board_rect.top)
        x1, y1 = self.screen_to_world_cell(self.board_rect.right, self.board_rect.bottom)
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

    def _update_camera(self):
        """Called every frame: keeps the board centered and smoothly zooms
        out just enough that all played tiles stay comfortably in view."""
        b = self.game.board.bounds()
        if b is None:
            target_cx, target_cy, target_cell = 0.0, 0.0, DEFAULT_CELL_SIZE
        else:
            min_x, min_y, max_x, max_y = b
            w_cells = (max_x - min_x + 1) + BOARD_PADDING_CELLS * 2
            h_cells = (max_y - min_y + 1) + BOARD_PADDING_CELLS * 2
            fit_w = self.board_rect.width / max(1, w_cells)
            fit_h = self.board_rect.height / max(1, h_cells)
            target_cell = max(MIN_CELL_SIZE, min(DEFAULT_CELL_SIZE, fit_w, fit_h))
            target_cx = (min_x + max_x) / 2
            target_cy = (min_y + max_y) / 2

        self.cell_size += (target_cell - self.cell_size) * ZOOM_LERP
        self.cam_x += (target_cx - self.cam_x) * ZOOM_LERP
        self.cam_y += (target_cy - self.cam_y) * ZOOM_LERP

    # ------------------------------------------------------------ actions --

    def _sort_color(self):
        self._clear_pending()
        self.active_sort = "color"
        self.human.sort_by_color()

    def _sort_shape(self):
        self._clear_pending()
        self.active_sort = "shape"
        self.human.sort_by_shape()

    def _apply_active_sort(self):
        if self.active_sort == "color":
            self.human.sort_by_color()
        elif self.active_sort == "shape":
            self.human.sort_by_shape()

    def _toggle_swap_mode(self):
        self.swap_mode = not self.swap_mode
        self.swap_selected = set()
        self._clear_pending()

    def _can_confirm_place(self):
        if self.swap_mode or not self.pending:
            return False
        if self.game.is_first_move_of_game():
            if self.opening_options and len(self.opening_options) > 1 and self.opening_choice is None:
                return False
            needed = len(self.opening_choice) if self.opening_choice else 0
            return len(self.pending) == needed
        return True

    def _confirm_move(self):
        move = [(x, y, t) for (x, y, t, _) in self.pending]
        res = self.game.play_place(move)
        if not res.ok:
            self._set_message(res.reason, ERROR_COLOR)
            return
        msg = f"You scored {res.score}"
        if res.qwirkles:
            msg += f" (Qwirkle x{res.qwirkles}!)"
        self._set_message(msg, GOOD_COLOR)
        self.log.append(f"You: +{res.score}" + (" QWIRKLE!" if res.qwirkles else ""))
        self.pending = []
        self._apply_active_sort()
        self._refresh_opening_state()
        self._after_turn(res)

    def _confirm_swap(self):
        tiles = [self.human.hand[i] for i in sorted(self.swap_selected)]
        res = self.game.play_swap(tiles)
        if not res.ok:
            self._set_message(res.reason, ERROR_COLOR)
            return
        self._set_message(f"Swapped {len(tiles)} tile(s).", GOOD_COLOR)
        self.log.append(f"You: swapped {len(tiles)} tile(s)")
        self.swap_mode = False
        self.swap_selected = set()
        self._apply_active_sort()
        self._after_turn(res)

    def _clear_pending(self):
        self.pending = []
        self.selected_hand_idx = None
        self.valid_squares = set()

    def _set_message(self, text, color, seconds=4):
        self.message = text
        self.message_color = color
        self.message_until = time.time() + seconds

    def _after_turn(self, res):
        if res.game_over:
            self.game_over_shown = True
            return
        # schedule bot turns to run with a human-readable delay
        self.next_bot_move_time = time.time() + 1.3

    # -------------------------------------------------------- bot driving --

    def _build_info(self):
        g = self.game
        is_first = g.is_first_move_of_game()
        opening = None
        if is_first:
            opts, _ = g.opening_options_for_current_player()
            opening = opts
        return {
            "is_first_move": is_first,
            "opening_options": opening,
            "bag_count": len(g.bag),
            "scores": {p.name: p.score for p in g.players},
            "hand_sizes": {p.name: len(p.hand) for p in g.players},
            "my_name": g.current_player.name,
        }

    def _maybe_run_bot_turn(self):
        g = self.game
        if g.game_over or g.current_player.name == self.human_name:
            return
        if time.time() < self.next_bot_move_time:
            return

        player = g.current_player
        bot = player.bot
        info = self._build_info()
        try:
            action, payload = bot.choose_move(g.board, list(player.hand), info)
        except Exception:
            action, payload = "swap", (player.hand[:1] if not g.is_first_move_of_game() else None)

        if action == "place" and payload:
            res = g.play_place(payload)
        elif action == "swap" and payload:
            res = g.play_swap(payload)
        else:
            res = None

        if res is None or not res.ok:
            # bot returned something illegal / gave up -- fall back safely.
            # (Opening turns always have a valid forced move, so this
            # fallback only ever applies after the game's first move.)
            if not g.is_first_move_of_game() and player.hand:
                res = g.play_swap([player.hand[0]])
            if res is None or not res.ok:
                self.next_bot_move_time = time.time() + 1.0
                return

        tag = f"{player.name}: "
        if res.score or res.bonus_awarded:
            tag += f"+{res.score}"
            if res.qwirkles:
                tag += " QWIRKLE!"
        else:
            tag += "swapped tiles"
        self.log.append(tag)
        self.log = self.log[-8:]

        self._refresh_opening_state()

        if res.game_over:
            self.game_over_shown = True
        else:
            self.next_bot_move_time = time.time() + 1.5

    # --------------------------------------------------------- hand click --

    def _hand_rects(self):
        """Screen rects for each of the human's hand tiles (left to right)."""
        n = len(self.human.hand)
        total_w = n * HAND_TILE_SIZE + (n - 1) * HAND_GAP
        start_x = self.board_rect.centerx - total_w // 2
        rects = []
        for i in range(n):
            x = start_x + i * (HAND_TILE_SIZE + HAND_GAP)
            rects.append(pygame.Rect(x, self.hand_y, HAND_TILE_SIZE, HAND_TILE_SIZE))
        return rects

    def _used_hand_indices(self):
        return {idx for (_, _, _, idx) in self.pending}

    def _compute_valid_squares(self):
        """Every empty square where the currently-armed hand tile could
        legally be placed, given whatever's already pending this turn."""
        self.valid_squares = set()
        if self.swap_mode or self.selected_hand_idx is None:
            return
        if self.selected_hand_idx in self._used_hand_indices():
            return

        tile = self.human.hand[self.selected_hand_idx]
        board = self.game.board
        pending_move = [(x, y, t) for (x, y, t, _) in self.pending]
        occupied = set(board.cells.keys()) | {(x, y) for (x, y, _) in pending_move}

        candidates = set()
        if pending_move:
            xs = {x for x, y, _ in pending_move}
            ys = {y for x, y, _ in pending_move}
            if len(pending_move) == 1:
                x0, y0 = pending_move[0][0], pending_move[0][1]
                for d in range(-6, 7):
                    candidates.add((x0 + d, y0))
                    candidates.add((x0, y0 + d))
            elif len(xs) == 1:
                x0 = next(iter(xs))
                ymin, ymax = min(ys), max(ys)
                for y in range(ymin - 6, ymax + 7):
                    candidates.add((x0, y))
            elif len(ys) == 1:
                y0 = next(iter(ys))
                xmin, xmax = min(xs), max(xs)
                for x in range(xmin - 6, xmax + 7):
                    candidates.add((x, y0))
        elif board.cells:
            candidates = set(board.legal_anchor_squares())
        else:
            x0, y0, x1, y1 = self._visible_world_bounds()
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    candidates.add((x, y))

        candidates -= occupied
        for (x, y) in candidates:
            ok, _ = board.validate_move(pending_move + [(x, y, tile)])
            if ok:
                self.valid_squares.add((x, y))

    def _on_hand_click(self, i):
        if self.swap_mode:
            if i in self.swap_selected:
                self.swap_selected.discard(i)
            else:
                self.swap_selected.add(i)
            return
        if i in self._used_hand_indices():
            return  # already placed this turn; click the board tile to undo instead
        tile = self.human.hand[i]
        if self.game.is_first_move_of_game() and self.opening_choice is not None:
            allowed_sigs = [(t.color, t.shape) for t in self.opening_choice]
            used_sigs = [(self.human.hand[j].color, self.human.hand[j].shape)
                         for j in self._used_hand_indices()]
            remaining_allowed = list(allowed_sigs)
            for s in used_sigs:
                if s in remaining_allowed:
                    remaining_allowed.remove(s)
            if (tile.color, tile.shape) not in remaining_allowed:
                self._set_message("That tile isn't part of your chosen opening set.", ERROR_COLOR, 3)
                return
        self.selected_hand_idx = None if self.selected_hand_idx == i else i
        self._compute_valid_squares()

    def _on_board_click(self, wx, wy):
        if self.swap_mode:
            return
        if self.game.board.occupied((wx, wy)):
            return
        # is there a pending tile already here? pick it back up
        for p in list(self.pending):
            if (p[0], p[1]) == (wx, wy):
                self.pending.remove(p)
                self._compute_valid_squares()
                return
        if self.selected_hand_idx is None:
            return
        if (wx, wy) not in self.valid_squares:
            return  # not a legal spot for the armed tile -- ignore the click
        tile = self.human.hand[self.selected_hand_idx]
        self.pending.append((wx, wy, tile, self.selected_hand_idx))
        self.selected_hand_idx = None
        self._compute_valid_squares()

    # ------------------------------------------------------------- events --

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        is_human_turn = (self.game.current_player.name == self.human_name
                          and not self.game.game_over)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.handle_click(event.pos):
                    return
            if is_human_turn:
                for i, r in enumerate(self._hand_rects()):
                    if r.collidepoint(event.pos):
                        self._on_hand_click(i)
                        return
                if self.board_rect.collidepoint(event.pos):
                    wx, wy = self.screen_to_world_cell(*event.pos)
                    self._on_board_click(wx, wy)
                    return

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and is_human_turn:
                self._clear_pending()
                self.swap_mode = False
                self.swap_selected = set()

    # ---------------------------------------------------------- opening ui --

    def _draw_opening_selector(self):
        if not (self.opening_options and len(self.opening_options) > 1
                and self.opening_choice is None
                and self.game.current_player.name == self.human_name):
            return
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        title = self.font_big.render("Tie for opening move — choose which set to play:", True, TEXT_COLOR)
        self.screen.blit(title, title.get_rect(center=(self.screen_w // 2, 220)))

        card_w, card_h, gap = 220, 100, 30
        n = len(self.opening_options)
        total_w = n * card_w + (n - 1) * gap
        start_x = self.screen_w // 2 - total_w // 2
        y = 280
        self._opening_cards = []
        for i, opt in enumerate(self.opening_options):
            rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
            pygame.draw.rect(self.screen, PANEL_COLOR, rect, border_radius=8)
            pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 2, border_radius=8)
            tsize = 28
            tx = rect.left + 30
            for t in opt:
                draw_shape(self.screen, t.shape, (tx, rect.centery), tsize * 0.6, COLOR_RGB[t.color])
                tx += 45
            label = self.font_small.render(f"{len(opt)} tiles", True, DIM_TEXT)
            self.screen.blit(label, (rect.left + 10, rect.bottom - 22))
            self._opening_cards.append((rect, opt))

    def _handle_opening_click(self, pos):
        if not hasattr(self, "_opening_cards"):
            return False
        for rect, opt in self._opening_cards:
            if rect.collidepoint(pos):
                self.opening_choice = opt
                return True
        return False

    # ---------------------------------------------------------------- draw --

    def draw_tile(self, rect, tile, face_up=True, highlight=None, shape_size=None):
        pygame.draw.rect(self.screen, (250, 248, 240) if face_up else FACE_DOWN_COLOR,
                          rect, border_radius=6)
        pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 1, border_radius=6)
        if face_up:
            size = shape_size if shape_size is not None else rect.width * 0.32
            draw_shape(self.screen, tile.shape, rect.center, size,
                       COLOR_RGB[tile.color])
        if highlight:
            pygame.draw.rect(self.screen, highlight, rect, 3, border_radius=6)

    def _draw_valid_squares(self):
        if not self.valid_squares:
            return
        if not self.game.board.cells and not self.pending:
            # Very first tile of the whole game -- any empty square is
            # legal, so highlighting would just paint the entire visible
            # board green. Leave it blank; placement still works anywhere.
            return
        size = max(2, self.cell_size - 2)
        hi_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        hi_surf.fill(VALID_SQUARE_COLOR)
        for (x, y) in self.valid_squares:
            sx, sy = self.world_to_screen(x, y)
            if self.board_rect.collidepoint(sx, sy):
                rect = hi_surf.get_rect(center=(sx, sy))
                self.screen.blit(hi_surf, rect)

    def draw_board(self):
        pygame.draw.rect(self.screen, BOARD_BG, self.board_rect)

        clip = self.screen.get_clip()
        self.screen.set_clip(self.board_rect)

        self._draw_valid_squares()

        tsize = max(1, self.cell_size - TILE_MARGIN)
        # Shapes stay roughly a constant on-screen size as the board zooms
        # out with more tiles -- they only shrink once the tile itself
        # becomes too small to hold them, and never draw past the tile's
        # edge (SHAPE_EDGE_MARGIN keeps a sliver of tile visible around it).
        max_shape_size = max(1.0, tsize / 2 - SHAPE_EDGE_MARGIN)
        board_shape_size = min(SHAPE_BASE_SIZE, max_shape_size)

        for (x, y), tile in self.game.board.cells.items():
            sx, sy = self.world_to_screen(x, y)
            if self.board_rect.collidepoint(sx, sy):
                rect = pygame.Rect(0, 0, tsize, tsize)
                rect.center = (sx, sy)
                self.draw_tile(rect, tile, face_up=True, shape_size=board_shape_size)

        for (x, y, tile, _) in self.pending:
            sx, sy = self.world_to_screen(x, y)
            rect = pygame.Rect(0, 0, tsize, tsize)
            rect.center = (sx, sy)
            self.draw_tile(rect, tile, face_up=True, highlight=PENDING_COLOR,
                            shape_size=board_shape_size)

        self.screen.set_clip(clip)
        pygame.draw.rect(self.screen, BUTTON_BORDER, self.board_rect, 2)

    def draw_human_hand(self):
        rects = self._hand_rects()
        used = self._used_hand_indices()
        for i, (r, tile) in enumerate(zip(rects, self.human.hand)):
            if i in used:
                ghost = pygame.Rect(r)
                pygame.draw.rect(self.screen, (35, 38, 44), ghost, border_radius=6)
                pygame.draw.rect(self.screen, BUTTON_BORDER, ghost, 1, border_radius=6)
                continue
            highlight = None
            if self.swap_mode and i in self.swap_selected:
                highlight = ERROR_COLOR
            elif self.selected_hand_idx == i:
                highlight = SELECT_COLOR
            elif (self.game.is_first_move_of_game() and self.opening_choice is not None
                  and self.game.current_player.name == self.human_name):
                sigs = [(t.color, t.shape) for t in self.opening_choice]
                if (tile.color, tile.shape) in sigs:
                    highlight = (90, 160, 90)
            self.draw_tile(r, tile, face_up=True, highlight=highlight)

    def draw_face_down_row(self, center_x, center_y, count, horizontal=True):
        """Draws `count` face-down tiles centered on (center_x, center_y),
        laid out horizontally or vertically. Returns the tile rects, in
        order, so callers can position labels relative to them."""
        size, gap = HAND_TILE_SIZE, HAND_GAP
        total = count * size + max(0, count - 1) * gap
        rects = []
        if horizontal:
            start_x = center_x - total // 2
            y = center_y - size // 2
            for i in range(count):
                rect = pygame.Rect(start_x + i * (size + gap), y, size, size)
                self.draw_tile(rect, None, face_up=False)
                rects.append(rect)
        else:
            start_y = center_y - total // 2
            x = center_x - size // 2
            for i in range(count):
                rect = pygame.Rect(x, start_y + i * (size + gap), size, size)
                self.draw_tile(rect, None, face_up=False)
                rects.append(rect)
        return rects

    def draw_opponents(self):
        left_p = self.game.players[1]
        across_p = self.game.players[2]
        right_p = self.game.players[3]

        across_rects = self.draw_face_down_row(self.board_rect.centerx, 70, len(across_p.hand), horizontal=True)
        left_rects = self.draw_face_down_row(90, self.board_rect.centery, len(left_p.hand), horizontal=False)
        right_rects = self.draw_face_down_row(self.screen_w - 90, self.board_rect.centery, len(right_p.hand), horizontal=False)

        if across_rects:
            top_y = min(r.top for r in across_rects) - 18
            self._label(across_p, (self.board_rect.centerx, top_y), center=True)
        if left_rects:
            pos = (left_rects[0].right + 26, self.board_rect.centery)
            self._label(left_p, pos, center=True, rotate=-90)  # 90 degrees clockwise
        if right_rects:
            pos = (right_rects[0].left - 26, self.board_rect.centery)
            self._label(right_p, pos, center=True, rotate=90)  # 90 degrees counter-clockwise

    def _label(self, player, pos, center=False, rotate=0):
        turn = self.game.current_player is player
        color = SELECT_COLOR if turn else TEXT_COLOR
        text = f"{player.name} ({player.score})" + (" <-" if turn else "")
        surf = self.font.render(text, True, color)
        if rotate:
            surf = pygame.transform.rotate(surf, rotate)
        rect = surf.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        self.screen.blit(surf, rect)

    def draw_scoreboard(self):
        panel = self.left_panel
        pygame.draw.rect(self.screen, PANEL_COLOR, panel, border_radius=8)
        pygame.draw.rect(self.screen, BUTTON_BORDER, panel, 1, border_radius=8)
        title = self.font_med.render("Standings", True, TEXT_COLOR)
        self.screen.blit(title, (panel.left + 12, panel.top + 10))
        for i, p in enumerate(self.game.standings()):
            y = panel.top + 44 + i * 26
            turn = self.game.current_player is p
            color = SELECT_COLOR if turn else TEXT_COLOR
            txt = self.font.render(f"{p.name}: {p.score}", True, color)
            self.screen.blit(txt, (panel.left + 16, y))
        bag_txt = self.font_small.render(f"Bag: {len(self.game.bag)} tiles left", True, DIM_TEXT)
        self.screen.blit(bag_txt, (panel.left + 12, panel.bottom - 26))

    def draw_log(self):
        panel = self.right_panel
        pygame.draw.rect(self.screen, PANEL_COLOR, panel, border_radius=8)
        pygame.draw.rect(self.screen, BUTTON_BORDER, panel, 1, border_radius=8)
        title = self.font_med.render("Log", True, TEXT_COLOR)
        self.screen.blit(title, (panel.left + 12, panel.top + 10))
        for i, line in enumerate(self.log[-6:]):
            txt = self.font_small.render(line, True, DIM_TEXT)
            self.screen.blit(txt, (panel.left + 12, panel.top + 44 + i * 22))

    def draw_message(self):
        if self.message and time.time() < self.message_until:
            txt = self.font_med.render(self.message, True, self.message_color)
            rect = txt.get_rect(center=(self.board_rect.centerx, self.board_rect.top - 30))
            self.screen.blit(txt, rect)

    def draw_game_over(self):
        if not self.game.game_over:
            return
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))
        title = self.font_big.render("Game Over", True, TEXT_COLOR)
        self.screen.blit(title, title.get_rect(center=(self.screen_w // 2, 300)))
        standings = self.game.standings()
        for i, p in enumerate(standings):
            tag = "  WINNER" if i == 0 and (len(standings) < 2 or standings[1].score != p.score) else ""
            txt = self.font_med.render(f"{i+1}. {p.name} - {p.score} pts{tag}", True, TEXT_COLOR)
            self.screen.blit(txt, txt.get_rect(center=(self.screen_w // 2, 360 + i * 34)))

    def draw(self):
        self.screen.fill(BG_COLOR)
        self.draw_board()
        self.draw_opponents()
        self.draw_human_hand()
        for b in self.buttons:
            b.draw(self.screen, self.font, pygame.mouse.get_pos())
        self.draw_scoreboard()
        self.draw_log()
        self.draw_message()
        self._draw_opening_selector()
        self.draw_game_over()
        pygame.display.flip()

    # ---------------------------------------------------------------- loop --

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                if (self.opening_options and len(self.opening_options) > 1
                        and self.opening_choice is None
                        and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                    if self._handle_opening_click(event.pos):
                        continue
                self.handle_event(event)

            self._maybe_run_bot_turn()
            self._update_camera()
            self.draw()
            self.clock.tick(60)

        pygame.quit()