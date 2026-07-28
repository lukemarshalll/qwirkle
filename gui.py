"""
gui.py
Top-down pygame table view for Qwirkle:

            [ Across's hand, face down ]
    [Left's                              [Right's
     hand,        [   BOARD   ]           hand,
     face down]                           face down]
            [ YOUR hand, face up + Sort buttons ]

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

SCREEN_W, SCREEN_H = 1440, 900
BG_COLOR = (30, 34, 40)
BOARD_BG = (42, 47, 56)
GRID_LINE = (56, 62, 72)
PANEL_COLOR = (24, 27, 32)
TEXT_COLOR = (230, 230, 235)
DIM_TEXT = (150, 155, 165)
FACE_DOWN_COLOR = (18, 20, 24)
SELECT_COLOR = (255, 215, 0)
PENDING_COLOR = (120, 200, 255)
ERROR_COLOR = (240, 90, 90)
GOOD_COLOR = (120, 220, 140)
BUTTON_COLOR = (55, 61, 72)
BUTTON_HOVER = (75, 82, 96)
BUTTON_BORDER = (100, 108, 122)

CELL_SIZE = 46
TILE_MARGIN = 4

HAND_TILE_SIZE = 56
HAND_GAP = 8

BOARD_RECT = pygame.Rect(330, 150, 780, 560)


class Button:
    def __init__(self, rect, label, callback, enabled_fn=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.enabled_fn = enabled_fn or (lambda: True)

    def enabled(self):
        return self.enabled_fn()

    def draw(self, surf, font, mouse_pos):
        enabled = self.enabled()
        hovered = enabled and self.rect.collidepoint(mouse_pos)
        color = BUTTON_HOVER if hovered else BUTTON_COLOR
        if not enabled:
            color = (40, 43, 49)
        pygame.draw.rect(surf, color, self.rect, border_radius=6)
        pygame.draw.rect(surf, BUTTON_BORDER, self.rect, 1, border_radius=6)
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
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("arial", 18)
        self.font_small = pygame.font.SysFont("arial", 14)
        self.font_big = pygame.font.SysFont("arial", 26, bold=True)
        self.font_med = pygame.font.SysFont("arial", 20, bold=True)

        self.game = game
        self.human_name = human_name
        self.human = next(p for p in game.players if p.name == human_name)

        # camera: world coords currently centered in BOARD_RECT
        self.cam_x, self.cam_y = 0.0, 0.0
        self.dragging_cam = False
        self.drag_start = None
        self.cam_start = None

        # turn-local human state
        self.selected_hand_idx = None      # index into human.hand "armed" for placing
        self.pending = []                  # list of (x, y, tile, hand_index_used)
        self.swap_mode = False
        self.swap_selected = set()         # indices into human.hand marked to swap

        self.opening_choice = None         # chosen tile set (list[Tile]) during a tied opening
        self.opening_options = None

        self.message = ""
        self.message_color = TEXT_COLOR
        self.message_until = 0

        self.log = []  # recent turn history strings, newest last

        self.next_bot_move_time = None
        self.game_over_shown = False

        self._build_buttons()
        self._refresh_opening_state()

    # ------------------------------------------------------------ setup --

    def _build_buttons(self):
        by = BOARD_RECT.bottom + 90
        self.btn_sort_color = Button((BOARD_RECT.centerx - 160, by, 150, 32),
                                      "Sort by Color", self._sort_color)
        self.btn_sort_shape = Button((BOARD_RECT.centerx + 10, by, 150, 32),
                                      "Sort by Shape", self._sort_shape)

        panel_x = BOARD_RECT.right + 40
        self.btn_confirm = Button((panel_x, 300, 170, 38), "Confirm Move",
                                   self._confirm_move, self._can_confirm_place)
        self.btn_clear = Button((panel_x, 346, 170, 38), "Clear Placement",
                                 self._clear_pending, lambda: len(self.pending) > 0)
        self.btn_swap_toggle = Button((panel_x, 410, 170, 38), "Swap Tiles...",
                                       self._toggle_swap_mode,
                                       lambda: not self.game.is_first_move_of_game())
        self.btn_confirm_swap = Button((panel_x, 456, 170, 38), "Confirm Swap",
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
        sx = BOARD_RECT.centerx + (wx - self.cam_x) * CELL_SIZE
        sy = BOARD_RECT.centery + (wy - self.cam_y) * CELL_SIZE
        return sx, sy

    def screen_to_world_cell(self, sx, sy):
        wx = (sx - BOARD_RECT.centerx) / CELL_SIZE + self.cam_x
        wy = (sy - BOARD_RECT.centery) / CELL_SIZE + self.cam_y
        return int(round(wx)), int(round(wy))

    def _center_camera_on_board(self):
        b = self.game.board.bounds()
        if b is None:
            self.cam_x, self.cam_y = 0.0, 0.0
        else:
            min_x, min_y, max_x, max_y = b
            self.cam_x = (min_x + max_x) / 2
            self.cam_y = (min_y + max_y) / 2

    # ------------------------------------------------------------ actions --

    def _sort_color(self):
        self._clear_pending()
        self.human.sort_by_color()

    def _sort_shape(self):
        self._clear_pending()
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
        self._center_camera_on_board()
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
        self._after_turn(res)

    def _clear_pending(self):
        self.pending = []
        self.selected_hand_idx = None

    def _set_message(self, text, color, seconds=4):
        self.message = text
        self.message_color = color
        self.message_until = time.time() + seconds

    def _after_turn(self, res):
        if res.game_over:
            self.game_over_shown = True
            return
        # schedule bot turns to run with a short human-readable delay
        self.next_bot_move_time = time.time() + 0.5

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
        if self.next_bot_move_time is None or time.time() < self.next_bot_move_time:
            return

        player = g.current_player
        bot = player.bot
        info = self._build_info()
        try:
            action, payload = bot.choose_move(g.board, list(player.hand), info)
        except Exception as e:
            action, payload = "swap", player.hand[:1] if not g.is_first_move_of_game() else None

        if action == "place" and payload:
            res = g.play_place(payload)
        elif action == "swap" and payload:
            res = g.play_swap(payload)
        else:
            res = None

        if res is None or not res.ok:
            # bot returned something illegal / gave up -- fall back safely
            if not g.is_first_move_of_game() and player.hand:
                res = g.play_swap([player.hand[0]])
            if res is None or not res.ok:
                # truly stuck (shouldn't normally happen) -- skip via smallest swap
                self.next_bot_move_time = time.time() + 0.5
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

        self._center_camera_on_board()
        self._refresh_opening_state()

        if res.game_over:
            self.game_over_shown = True
            self.next_bot_move_time = None
        else:
            self.next_bot_move_time = time.time() + 0.7

    # --------------------------------------------------------- hand click --

    def _hand_rects(self):
        """Screen rects for each of the human's hand tiles (left to right)."""
        n = len(self.human.hand)
        total_w = n * HAND_TILE_SIZE + (n - 1) * HAND_GAP
        start_x = BOARD_RECT.centerx - total_w // 2
        y = BOARD_RECT.bottom + 20
        rects = []
        for i in range(n):
            x = start_x + i * (HAND_TILE_SIZE + HAND_GAP)
            rects.append(pygame.Rect(x, y, HAND_TILE_SIZE, HAND_TILE_SIZE))
        return rects

    def _used_hand_indices(self):
        return {idx for (_, _, _, idx) in self.pending}

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

    def _on_board_click(self, wx, wy):
        if self.swap_mode:
            return
        if self.game.board.occupied((wx, wy)):
            return
        # is there a pending tile already here? pick it back up
        for p in list(self.pending):
            if (p[0], p[1]) == (wx, wy):
                self.pending.remove(p)
                return
        if self.selected_hand_idx is None:
            return
        tile = self.human.hand[self.selected_hand_idx]
        self.pending.append((wx, wy, tile, self.selected_hand_idx))
        self.selected_hand_idx = None

    # ------------------------------------------------------------- events --

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        is_human_turn = (self.game.current_player.name == self.human_name
                          and not self.game.game_over)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for b in self.buttons:
                    if b.handle_click(event.pos):
                        return
                if is_human_turn:
                    for i, r in enumerate(self._hand_rects()):
                        if r.collidepoint(event.pos):
                            self._on_hand_click(i)
                            return
                    if BOARD_RECT.collidepoint(event.pos):
                        wx, wy = self.screen_to_world_cell(*event.pos)
                        self._on_board_click(wx, wy)
                        return
                if BOARD_RECT.collidepoint(event.pos):
                    self.dragging_cam = True
                    self.drag_start = event.pos
                    self.cam_start = (self.cam_x, self.cam_y)
            elif event.button in (2, 3):
                self.dragging_cam = True
                self.drag_start = event.pos
                self.cam_start = (self.cam_x, self.cam_y)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button in (1, 2, 3):
                self.dragging_cam = False

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging_cam and self.drag_start:
                dx = event.pos[0] - self.drag_start[0]
                dy = event.pos[1] - self.drag_start[1]
                self.cam_x = self.cam_start[0] - dx / CELL_SIZE
                self.cam_y = self.cam_start[1] - dy / CELL_SIZE

        elif event.type == pygame.KEYDOWN:
            step = 1.0
            if event.key == pygame.K_LEFT:
                self.cam_x -= step
            elif event.key == pygame.K_RIGHT:
                self.cam_x += step
            elif event.key == pygame.K_UP:
                self.cam_y -= step
            elif event.key == pygame.K_DOWN:
                self.cam_y += step
            elif event.key == pygame.K_c:
                self._center_camera_on_board()
            elif event.key == pygame.K_ESCAPE and is_human_turn:
                self._clear_pending()
                self.swap_mode = False
                self.swap_selected = set()

    # ---------------------------------------------------------- opening ui --

    def _draw_opening_selector(self):
        if not (self.opening_options and len(self.opening_options) > 1
                and self.opening_choice is None
                and self.game.current_player.name == self.human_name):
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        title = self.font_big.render("Tie for opening move — choose which set to play:", True, TEXT_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 220)))

        card_w, card_h, gap = 220, 100, 30
        n = len(self.opening_options)
        total_w = n * card_w + (n - 1) * gap
        start_x = SCREEN_W // 2 - total_w // 2
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

    def draw_tile(self, rect, tile, face_up=True, highlight=None):
        pygame.draw.rect(self.screen, (250, 248, 240) if face_up else FACE_DOWN_COLOR,
                          rect, border_radius=6)
        pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 1, border_radius=6)
        if face_up:
            draw_shape(self.screen, tile.shape, rect.center, rect.width * 0.32,
                       COLOR_RGB[tile.color])
        if highlight:
            pygame.draw.rect(self.screen, highlight, rect, 3, border_radius=6)

    def draw_board(self):
        pygame.draw.rect(self.screen, BOARD_BG, BOARD_RECT)
        # grid
        cols = BOARD_RECT.width // CELL_SIZE + 2
        rows = BOARD_RECT.height // CELL_SIZE + 2
        offset_x = (BOARD_RECT.centerx - self.cam_x * CELL_SIZE) % CELL_SIZE
        offset_y = (BOARD_RECT.centery - self.cam_y * CELL_SIZE) % CELL_SIZE
        for c in range(-1, cols):
            x = BOARD_RECT.left + offset_x + c * CELL_SIZE
            pygame.draw.line(self.screen, GRID_LINE, (x, BOARD_RECT.top), (x, BOARD_RECT.bottom))
        for r in range(-1, rows):
            y = BOARD_RECT.top + offset_y + r * CELL_SIZE
            pygame.draw.line(self.screen, GRID_LINE, (BOARD_RECT.left, y), (BOARD_RECT.right, y))

        clip = self.screen.get_clip()
        self.screen.set_clip(BOARD_RECT)

        for (x, y), tile in self.game.board.cells.items():
            sx, sy = self.world_to_screen(x, y)
            if BOARD_RECT.collidepoint(sx, sy):
                rect = pygame.Rect(0, 0, CELL_SIZE - TILE_MARGIN, CELL_SIZE - TILE_MARGIN)
                rect.center = (sx, sy)
                self.draw_tile(rect, tile, face_up=True)

        for (x, y, tile, _) in self.pending:
            sx, sy = self.world_to_screen(x, y)
            rect = pygame.Rect(0, 0, CELL_SIZE - TILE_MARGIN, CELL_SIZE - TILE_MARGIN)
            rect.center = (sx, sy)
            self.draw_tile(rect, tile, face_up=True, highlight=PENDING_COLOR)

        self.screen.set_clip(clip)
        pygame.draw.rect(self.screen, BUTTON_BORDER, BOARD_RECT, 2)

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

    def draw_face_down_row(self, center_x, top_y, count, horizontal=True):
        size = HAND_TILE_SIZE
        gap = HAND_GAP
        total = count * size + (count - 1) * gap
        if horizontal:
            start = center_x - total // 2
            for i in range(count):
                rect = pygame.Rect(start + i * (size + gap), top_y, size, size)
                self.draw_tile(rect, None, face_up=False)
        else:
            start = top_y - total // 2
            for i in range(count):
                rect = pygame.Rect(center_x, start + i * (size + gap), size, size)
                self.draw_tile(rect, None, face_up=False)

    def draw_opponents(self):
        left_p = self.game.players[1]
        across_p = self.game.players[2]
        right_p = self.game.players[3]

        # Across (top)
        self.draw_face_down_row(BOARD_RECT.centerx, 30, len(across_p.hand), horizontal=True)
        # Left
        self.draw_face_down_row(60, BOARD_RECT.centery - 3 * (HAND_TILE_SIZE + HAND_GAP) // 2,
                                 len(left_p.hand), horizontal=False)
        # Right
        self.draw_face_down_row(SCREEN_W - 60 - HAND_TILE_SIZE,
                                 BOARD_RECT.centery - 3 * (HAND_TILE_SIZE + HAND_GAP) // 2,
                                 len(right_p.hand), horizontal=False)

        self._label(across_p, (BOARD_RECT.centerx, 8), center=True)
        self._label(left_p, (60 + HAND_TILE_SIZE // 2, BOARD_RECT.centery - 130), center=True)
        self._label(right_p, (SCREEN_W - 60 - HAND_TILE_SIZE // 2, BOARD_RECT.centery - 130), center=True)

    def _label(self, player, pos, center=False):
        turn = self.game.current_player is player
        color = SELECT_COLOR if turn else TEXT_COLOR
        text = f"{player.name}  ({player.score} pts)" + ("  <- turn" if turn else "")
        surf = self.font.render(text, True, color)
        rect = surf.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        self.screen.blit(surf, rect)

    def draw_scoreboard(self):
        panel = pygame.Rect(20, 20, 280, 200)
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
        panel = pygame.Rect(20, 240, 280, 200)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel, border_radius=8)
        pygame.draw.rect(self.screen, BUTTON_BORDER, panel, 1, border_radius=8)
        title = self.font_med.render("Log", True, TEXT_COLOR)
        self.screen.blit(title, (panel.left + 12, panel.top + 10))
        for i, line in enumerate(self.log[-6:]):
            txt = self.font_small.render(line, True, DIM_TEXT)
            self.screen.blit(txt, (panel.left + 12, panel.top + 44 + i * 22))

    def draw_side_panel(self):
        panel_x = BOARD_RECT.right + 40
        title = self.font_med.render("Actions", True, TEXT_COLOR)
        self.screen.blit(title, (panel_x, 260))
        for b in (self.btn_confirm, self.btn_clear, self.btn_swap_toggle, self.btn_confirm_swap):
            b.draw(self.screen, self.font, pygame.mouse.get_pos())
        hint_y = 510
        hints = [
            "Click a tile in your hand,",
            "then click the board to place it.",
            "Click a placed (blue) tile to undo it.",
            "All tiles in a turn must form",
            "one straight line touching the board.",
            "",
            "Right/middle-drag or arrow keys",
            "to pan the board. Press C to re-center.",
        ]
        for i, h in enumerate(hints):
            txt = self.font_small.render(h, True, DIM_TEXT)
            self.screen.blit(txt, (panel_x, hint_y + i * 18))

    def draw_message(self):
        if self.message and time.time() < self.message_until:
            txt = self.font_med.render(self.message, True, self.message_color)
            rect = txt.get_rect(center=(BOARD_RECT.centerx, BOARD_RECT.top - 30))
            self.screen.blit(txt, rect)

    def draw_game_over(self):
        if not self.game.game_over:
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))
        title = self.font_big.render("Game Over", True, TEXT_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 300)))
        standings = self.game.standings()
        for i, p in enumerate(standings):
            tag = "  WINNER" if i == 0 and (len(standings) < 2 or standings[1].score != p.score) else ""
            txt = self.font_med.render(f"{i+1}. {p.name} - {p.score} pts{tag}", True, TEXT_COLOR)
            self.screen.blit(txt, txt.get_rect(center=(SCREEN_W // 2, 360 + i * 34)))

    def draw(self):
        self.screen.fill(BG_COLOR)
        self.draw_board()
        self.draw_opponents()
        self.draw_human_hand()
        self.btn_sort_color.draw(self.screen, self.font, pygame.mouse.get_pos())
        self.btn_sort_shape.draw(self.screen, self.font, pygame.mouse.get_pos())
        self.draw_side_panel()
        self.draw_scoreboard()
        self.draw_log()
        self.draw_message()
        self._draw_opening_selector()
        self.draw_game_over()
        pygame.display.flip()

    # ---------------------------------------------------------------- loop --

    def run(self):
        self._center_camera_on_board()
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
            self.draw()
            self.clock.tick(60)

        pygame.quit()
