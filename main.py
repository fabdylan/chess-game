import asyncio
import math
import struct
import wave
from pathlib import Path
from dataclasses import dataclass, field

import pygame


WIDTH, HEIGHT = 1040, 720
BOARD_SIZE = 680
SQ = BOARD_SIZE // 8
BOARD_LEFT = 28
BOARD_TOP = 20
SIDEBAR_LEFT = BOARD_LEFT + BOARD_SIZE + 24
FPS = 60
ASSET_DIR = Path(__file__).parent / 'assets' / 'pieces'
SOUND_DIR = Path(__file__).parent / 'assets' / 'sounds'
START_TIME_SECONDS = 10 * 60

LIGHT = (245, 249, 255)
DARK = (52, 126, 197)
SELECT = (246, 205, 74)
MOVE_DOT = (45, 45, 45, 95)
LAST_MOVE = (244, 246, 128, 115)
CHECK = (224, 62, 62)
PANEL = (38, 41, 48)
PANEL_2 = (50, 54, 63)
TEXT = (244, 246, 248)
MUTED = (165, 172, 184)
ACCENT = (68, 160, 255)
CAPTURE = (213, 77, 77, 95)

UNICODE_PIECES = {
    "K": "â™”",
    "Q": "â™•",
    "R": "â™–",
    "B": "â™—",
    "N": "â™˜",
    "P": "â™™",
    "k": "â™š",
    "q": "â™›",
    "r": "â™œ",
    "b": "â™",
    "n": "â™ž",
    "p": "â™Ÿ",
}

PIECE_NAMES = {
    "K": "Rey",
    "Q": "Reina",
    "R": "Torre",
    "B": "Alfil",
    "N": "Caballo",
    "P": "Peon",
}


@dataclass
class Move:
    start: tuple[int, int]
    end: tuple[int, int]
    piece: str
    captured: str | None = None
    promotion: str | None = None
    castle: bool = False
    en_passant: bool = False


@dataclass
class Animation:
    piece: str
    start_px: tuple[int, int]
    end_px: tuple[int, int]
    elapsed: float = 0
    duration: float = 0.18


@dataclass
class Game:
    board: list[list[str | None]] = field(default_factory=list)
    turn: str = "w"
    selected: tuple[int, int] | None = None
    legal_targets: list[Move] = field(default_factory=list)
    history: list[Move] = field(default_factory=list)
    last_move: Move | None = None
    en_passant_target: tuple[int, int] | None = None
    castling: dict[str, bool] = field(default_factory=dict)
    flipped: bool = False
    animation: Animation | None = None
    status: str = "Juegan blancas"
    pending_sound: str | None = None
    clocks: dict[str, float] = field(default_factory=dict)
    low_time_warning: dict[str, bool] = field(default_factory=dict)

    def reset(self):
        self.board = [
            list("rnbqkbnr"),
            list("pppppppp"),
            [None] * 8,
            [None] * 8,
            [None] * 8,
            [None] * 8,
            list("PPPPPPPP"),
            list("RNBQKBNR"),
        ]
        self.turn = "w"
        self.selected = None
        self.legal_targets = []
        self.history = []
        self.last_move = None
        self.en_passant_target = None
        self.castling = {"K": True, "Q": True, "k": True, "q": True}
        self.animation = None
        self.status = "Juegan blancas"
        self.pending_sound = None
        self.clocks = {"w": START_TIME_SECONDS, "b": START_TIME_SECONDS}
        self.low_time_warning = {"w": False, "b": False}

    def color_of(self, piece):
        if not piece:
            return None
        return "w" if piece.isupper() else "b"

    def opposite(self, color):
        return "b" if color == "w" else "w"

    def in_bounds(self, r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def screen_to_square(self, pos):
        x, y = pos
        if not (BOARD_LEFT <= x < BOARD_LEFT + BOARD_SIZE and BOARD_TOP <= y < BOARD_TOP + BOARD_SIZE):
            return None
        c = (x - BOARD_LEFT) // SQ
        r = (y - BOARD_TOP) // SQ
        if self.flipped:
            r, c = 7 - r, 7 - c
        return (r, c)

    def square_to_screen(self, square):
        r, c = square
        if self.flipped:
            r, c = 7 - r, 7 - c
        return BOARD_LEFT + c * SQ, BOARD_TOP + r * SQ

    def handle_click(self, pos):
        if self.game_over():
            return
        square = self.screen_to_square(pos)
        if square is None:
            self.selected = None
            self.legal_targets = []
            return
        had_selection = self.selected is not None
        r, c = square
        piece = self.board[r][c]
        chosen = next((m for m in self.legal_targets if m.end == square), None)
        if chosen:
            self.push_move(chosen)
            return
        if piece and self.color_of(piece) == self.turn:
            self.selected = square
            self.legal_targets = self.legal_moves_from(square)
        else:
            self.selected = None
            self.legal_targets = []
            if had_selection or piece:
                self.pending_sound = "illegal"

    def legal_moves_from(self, square):
        return [m for m in self.all_legal_moves(self.turn) if m.start == square]

    def all_legal_moves(self, color):
        moves = []
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece and self.color_of(piece) == color:
                    for move in self.pseudo_moves((r, c), include_castles=True):
                        if not self.leaves_king_in_check(move, color):
                            moves.append(move)
        return moves

    def pseudo_moves(self, square, include_castles=False):
        r, c = square
        piece = self.board[r][c]
        if not piece:
            return []
        color = self.color_of(piece)
        enemy = self.opposite(color)
        moves = []
        kind = piece.upper()
        if kind == "P":
            direction = -1 if color == "w" else 1
            start_row = 6 if color == "w" else 1
            promo_row = 0 if color == "w" else 7
            nr = r + direction
            if self.in_bounds(nr, c) and self.board[nr][c] is None:
                moves.append(Move(square, (nr, c), piece, promotion=("Q" if color == "w" else "q") if nr == promo_row else None))
                nr2 = r + direction * 2
                if r == start_row and self.board[nr2][c] is None:
                    moves.append(Move(square, (nr2, c), piece))
            for dc in (-1, 1):
                nc = c + dc
                if not self.in_bounds(nr, nc):
                    continue
                target = self.board[nr][nc]
                if target and self.color_of(target) == enemy:
                    moves.append(Move(square, (nr, nc), piece, captured=target, promotion=("Q" if color == "w" else "q") if nr == promo_row else None))
                if self.en_passant_target == (nr, nc):
                    moves.append(Move(square, (nr, nc), piece, captured="p" if color == "w" else "P", en_passant=True))
        elif kind == "N":
            for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)):
                self.add_step(moves, square, r + dr, c + dc, piece)
        elif kind in ("B", "R", "Q"):
            dirs = []
            if kind in ("B", "Q"):
                dirs += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            if kind in ("R", "Q"):
                dirs += [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for dr, dc in dirs:
                self.add_slide(moves, square, dr, dc, piece)
        elif kind == "K":
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr or dc:
                        self.add_step(moves, square, r + dr, c + dc, piece)
            if include_castles and not self.is_in_check(color):
                self.add_castles(moves, square, piece)
        return moves

    def add_step(self, moves, start, r, c, piece):
        if not self.in_bounds(r, c):
            return
        target = self.board[r][c]
        if target is None or self.color_of(target) != self.color_of(piece):
            moves.append(Move(start, (r, c), piece, captured=target))

    def add_slide(self, moves, start, dr, dc, piece):
        r, c = start
        r += dr
        c += dc
        while self.in_bounds(r, c):
            target = self.board[r][c]
            if target is None:
                moves.append(Move(start, (r, c), piece))
            else:
                if self.color_of(target) != self.color_of(piece):
                    moves.append(Move(start, (r, c), piece, captured=target))
                break
            r += dr
            c += dc

    def add_castles(self, moves, square, piece):
        color = self.color_of(piece)
        row = 7 if color == "w" else 0
        king_key, queen_key = ("K", "Q") if color == "w" else ("k", "q")
        if square != (row, 4):
            return
        if self.castling.get(king_key) and self.board[row][5] is None and self.board[row][6] is None:
            if not self.square_attacked((row, 5), self.opposite(color)) and not self.square_attacked((row, 6), self.opposite(color)):
                moves.append(Move(square, (row, 6), piece, castle=True))
        if self.castling.get(queen_key) and self.board[row][1] is None and self.board[row][2] is None and self.board[row][3] is None:
            if not self.square_attacked((row, 3), self.opposite(color)) and not self.square_attacked((row, 2), self.opposite(color)):
                moves.append(Move(square, (row, 2), piece, castle=True))

    def leaves_king_in_check(self, move, color):
        snapshot = self.snapshot()
        self.apply_move(move, animate=False)
        checked = self.is_in_check(color)
        self.restore(snapshot)
        return checked

    def snapshot(self):
        return ([row[:] for row in self.board], self.en_passant_target, self.castling.copy(), self.last_move)

    def restore(self, snapshot):
        self.board, self.en_passant_target, self.castling, self.last_move = snapshot

    def king_square(self, color):
        king = "K" if color == "w" else "k"
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == king:
                    return (r, c)
        return None

    def is_in_check(self, color):
        king = self.king_square(color)
        return bool(king and self.square_attacked(king, self.opposite(color)))

    def square_attacked(self, square, by_color):
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece and self.color_of(piece) == by_color:
                    if self.attacks_square((r, c), square):
                        return True
        return False

    def attacks_square(self, start, target):
        r, c = start
        tr, tc = target
        piece = self.board[r][c]
        color = self.color_of(piece)
        kind = piece.upper()
        if kind == "P":
            direction = -1 if color == "w" else 1
            return (tr, tc) in ((r + direction, c - 1), (r + direction, c + 1))
        if kind == "N":
            return (abs(tr - r), abs(tc - c)) in ((1, 2), (2, 1))
        if kind == "K":
            return max(abs(tr - r), abs(tc - c)) == 1
        if kind in ("B", "R", "Q"):
            dr = tr - r
            dc = tc - c
            step_r = 0 if dr == 0 else int(math.copysign(1, dr))
            step_c = 0 if dc == 0 else int(math.copysign(1, dc))
            diagonal = abs(dr) == abs(dc)
            straight = dr == 0 or dc == 0
            if kind == "B" and not diagonal:
                return False
            if kind == "R" and not straight:
                return False
            if kind == "Q" and not (diagonal or straight):
                return False
            cr, cc = r + step_r, c + step_c
            while (cr, cc) != (tr, tc):
                if self.board[cr][cc] is not None:
                    return False
                cr += step_r
                cc += step_c
            return True
        return False

    def push_move(self, move):
        moving_color = self.turn
        start_px = self.square_center(move.start)
        end_px = self.square_center(move.end)
        self.animation = Animation(move.piece, start_px, end_px)
        self.apply_move(move, animate=True)
        self.history.append(move)
        self.last_move = move
        self.turn = self.opposite(self.turn)
        self.selected = None
        self.legal_targets = []
        self.refresh_status()
        if "Jaque mate" in self.status or "Tablas" in self.status:
            self.pending_sound = "game-end"
        elif "Jaque" in self.status:
            self.pending_sound = "move-check"
        elif move.promotion:
            self.pending_sound = "promote"
        elif move.castle:
            self.pending_sound = "castle"
        elif move.captured:
            self.pending_sound = "capture"
        else:
            self.pending_sound = "move-self" if moving_color == "w" else "move-opponent"

    def square_center(self, square):
        x, y = self.square_to_screen(square)
        return x + SQ // 2, y + SQ // 2

    def apply_move(self, move, animate=False):
        sr, sc = move.start
        er, ec = move.end
        piece = self.board[sr][sc]
        self.board[sr][sc] = None
        if move.en_passant:
            self.board[sr][ec] = None
        if move.castle:
            if ec == 6:
                self.board[er][5] = self.board[er][7]
                self.board[er][7] = None
            else:
                self.board[er][3] = self.board[er][0]
                self.board[er][0] = None
        self.board[er][ec] = move.promotion or piece
        self.update_castling_rights(move)
        self.en_passant_target = None
        if piece and piece.upper() == "P" and abs(er - sr) == 2:
            self.en_passant_target = ((sr + er) // 2, sc)
        if not animate:
            self.last_move = move

    def update_castling_rights(self, move):
        sr, sc = move.start
        er, ec = move.end
        if move.piece == "K":
            self.castling["K"] = self.castling["Q"] = False
        elif move.piece == "k":
            self.castling["k"] = self.castling["q"] = False
        elif move.piece == "R" and (sr, sc) == (7, 0):
            self.castling["Q"] = False
        elif move.piece == "R" and (sr, sc) == (7, 7):
            self.castling["K"] = False
        elif move.piece == "r" and (sr, sc) == (0, 0):
            self.castling["q"] = False
        elif move.piece == "r" and (sr, sc) == (0, 7):
            self.castling["k"] = False
        if move.captured == "R" and (er, ec) == (7, 0):
            self.castling["Q"] = False
        elif move.captured == "R" and (er, ec) == (7, 7):
            self.castling["K"] = False
        elif move.captured == "r" and (er, ec) == (0, 0):
            self.castling["q"] = False
        elif move.captured == "r" and (er, ec) == (0, 7):
            self.castling["k"] = False

    def refresh_status(self):
        color_name = "blancas" if self.turn == "w" else "negras"
        moves = self.all_legal_moves(self.turn)
        if self.is_in_check(self.turn) and not moves:
            winner = "negras" if self.turn == "w" else "blancas"
            self.status = f"Jaque mate: ganan {winner}"
        elif not moves:
            self.status = "Tablas por ahogado"
        elif self.is_in_check(self.turn):
            self.status = f"Jaque a {color_name}"
        else:
            self.status = f"Juegan {color_name}"

    def update_clock(self, dt):
        if self.game_over():
            return
        previous = self.clocks[self.turn]
        self.clocks[self.turn] = max(0, self.clocks[self.turn] - dt)
        if self.clocks[self.turn] <= 0:
            winner = "negras" if self.turn == "w" else "blancas"
            self.status = f"Tiempo agotado: ganan {winner}"
            self.selected = None
            self.legal_targets = []
            self.pending_sound = "game-end"
        elif previous > 10 >= self.clocks[self.turn] and not self.low_time_warning[self.turn]:
            self.low_time_warning[self.turn] = True
            self.pending_sound = "tenseconds"

    def clock_text(self, color):
        remaining = max(0, int(math.ceil(self.clocks.get(color, START_TIME_SECONDS))))
        minutes = remaining // 60
        seconds = remaining % 60
        return f"{minutes:02}:{seconds:02}"

    def game_over(self):
        return "Jaque mate" in self.status or "Tablas" in self.status or "Tiempo agotado" in self.status

    def move_label(self, move):
        start = self.alg(move.start)
        end = self.alg(move.end)
        name = PIECE_NAMES[move.piece.upper()]
        capture = "x" if move.captured else "-"
        suffix = "=Q" if move.promotion else ""
        if move.castle:
            return "O-O" if move.end[1] == 6 else "O-O-O"
        return f"{name} {start}{capture}{end}{suffix}"

    def alg(self, square):
        r, c = square
        return f"{chr(97 + c)}{8 - r}"


def draw_rounded_rect(surface, rect, color, radius=10, width=0):
    pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)


def draw_text(surface, font, text, pos, color=TEXT, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    rect.center = pos if center else rect.center
    if not center:
        rect.topleft = pos
    surface.blit(img, rect)
def write_wood_hit(path, hits, volume=0.75, sample_rate=44100):
    SOUND_DIR.mkdir(parents=True, exist_ok=True)
    samples = []
    for frequency, duration, weight in hits:
        count = int(sample_rate * duration)
        for i in range(count):
            t = i / sample_rate
            envelope = math.exp(-34 * t)
            body = (
                math.sin(2 * math.pi * frequency * t)
                + 0.45 * math.sin(2 * math.pi * frequency * 1.72 * t)
                + 0.22 * math.sin(2 * math.pi * frequency * 2.61 * t)
            )
            tap_noise = math.sin(i * 12.9898 + frequency) * 43758.5453
            tap_noise = (tap_noise - math.floor(tap_noise)) * 2 - 1
            attack = max(0, 1 - i / 320) * tap_noise * 0.32
            value = (body * 0.68 + attack) * envelope * weight
            samples.append(int(32767 * volume * value))
        pause = int(sample_rate * 0.018)
        samples.extend([0] * pause)
    with wave.open(str(path), "w") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def ensure_sound_files():
    sounds = {
        "select": [(520, 0.045, 0.55)],
        "move": [(285, 0.07, 0.95), (430, 0.045, 0.35)],
        "capture": [(205, 0.085, 1.0), (310, 0.065, 0.65)],
        "check": [(330, 0.06, 0.95), (560, 0.055, 0.75)],
        "game_over": [(260, 0.09, 1.0), (210, 0.1, 0.85), (165, 0.13, 0.7)],
    }
    for name, hits in sounds.items():
        path = SOUND_DIR / f"{name}.wav"
        write_wood_hit(path, hits)


def load_sounds():
    loaded = {}
    has_audio = any(SOUND_DIR.glob("*.ogg")) or any(SOUND_DIR.glob("*.mp3")) or any(SOUND_DIR.glob("*.wav"))
    if not has_audio:
        ensure_sound_files()
    for pattern in ("*.wav", "*.mp3", "*.ogg"):
        for path in SOUND_DIR.glob(pattern):
            try:
                loaded[path.stem] = pygame.mixer.Sound(str(path))
                loaded[path.stem].set_volume(0.65 if path.suffix.lower() in (".mp3", ".ogg") else 0.45)
            except pygame.error:
                print(f"No se pudo cargar el sonido: {path.name}")
    return loaded


def play_sound(sounds, name):
    sound = sounds.get(name)
    if sound:
        sound.play()


def draw_startup_message(screen, message):
    screen.fill((25, 27, 32))
    font = pygame.font.SysFont("Arial", 26, bold=True)
    small = pygame.font.SysFont("Arial", 18)
    draw_text(screen, font, "Chess Royale", (36, 34), TEXT)
    draw_text(screen, small, message, (36, 78), MUTED)
    pygame.display.flip()


async def show_startup_error(screen, error):
    font = pygame.font.SysFont("Arial", 24, bold=True)
    small = pygame.font.SysFont("Arial", 17)
    lines = [str(error)[i:i + 72] for i in range(0, len(str(error)), 72)] or ["Error desconocido"]
    while True:
        screen.fill((25, 27, 32))
        draw_text(screen, font, "No se pudo iniciar Chess Royale", (36, 34), (255, 195, 96))
        y = 82
        for line in lines[:12]:
            draw_text(screen, small, line, (36, y), TEXT)
            y += 26
        draw_text(screen, small, "Manda captura de este mensaje y lo arreglo.", (36, y + 18), MUTED)
        pygame.display.flip()
        await asyncio.sleep(0)


def draw_board(screen, game, fonts):
    for vr in range(8):
        for vc in range(8):
            br, bc = (7 - vr, 7 - vc) if game.flipped else (vr, vc)
            x = BOARD_LEFT + vc * SQ
            y = BOARD_TOP + vr * SQ
            color = LIGHT if (br + bc) % 2 == 0 else DARK
            pygame.draw.rect(screen, color, (x, y, SQ, SQ))
    overlay = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
    if game.last_move:
        overlay.fill(LAST_MOVE)
        for sq in (game.last_move.start, game.last_move.end):
            x, y = game.square_to_screen(sq)
            screen.blit(overlay, (x, y))
    if game.selected:
        x, y = game.square_to_screen(game.selected)
        pygame.draw.rect(screen, SELECT, (x + 3, y + 3, SQ - 6, SQ - 6), 4, border_radius=8)
    king = game.king_square(game.turn)
    if king and game.is_in_check(game.turn):
        x, y = game.square_to_screen(king)
        check_layer = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
        check_layer.fill((*CHECK, 120))
        screen.blit(check_layer, (x, y))
    draw_legal_moves(screen, game)
    draw_coordinates(screen, game, fonts["small"])


def draw_legal_moves(screen, game):
    for move in game.legal_targets:
        x, y = game.square_to_screen(move.end)
        cx, cy = x + SQ // 2, y + SQ // 2
        layer = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
        if move.captured:
            pygame.draw.circle(layer, CAPTURE, (SQ // 2, SQ // 2), SQ // 2 - 8, width=7)
        else:
            pygame.draw.circle(layer, MOVE_DOT, (SQ // 2, SQ // 2), 12)
        screen.blit(layer, (x, y))


def draw_coordinates(screen, game, font):
    for i in range(8):
        file_char = chr(97 + (7 - i if game.flipped else i))
        rank_char = str(i + 1 if game.flipped else 8 - i)
        draw_text(screen, font, file_char, (BOARD_LEFT + i * SQ + SQ - 17, BOARD_TOP + BOARD_SIZE - 22), (66, 84, 52))
        draw_text(screen, font, rank_char, (BOARD_LEFT + 8, BOARD_TOP + i * SQ + 7), (66, 84, 52))


def load_piece_images():
    images = {}
    missing = []
    for color in ("w", "b"):
        for kind in ("K", "Q", "R", "B", "N", "P"):
            key = color + kind
            path = ASSET_DIR / f"{key}.png"
            if not path.exists():
                missing.append(path.name)
                continue
            image = pygame.image.load(str(path)).convert_alpha()
            images[key] = pygame.transform.smoothscale(image, (SQ - 14, SQ - 14))
    if missing:
        raise FileNotFoundError("Faltan imagenes en assets/pieces: " + ", ".join(missing))
    return images


def draw_pieces(screen, game, fonts, piece_images):
    hidden_square = None
    if game.animation:
        hidden_square = game.last_move.end
    for r in range(8):
        for c in range(8):
            if (r, c) == hidden_square:
                continue
            piece = game.board[r][c]
            if piece:
                draw_piece(screen, piece, game.square_center((r, c)), piece_images)
    if game.animation:
        anim = game.animation
        t = min(1, anim.elapsed / anim.duration)
        eased = 1 - pow(1 - t, 3)
        x = anim.start_px[0] + (anim.end_px[0] - anim.start_px[0]) * eased
        y = anim.start_px[1] + (anim.end_px[1] - anim.start_px[1]) * eased
        draw_piece(screen, anim.piece, (int(x), int(y)), piece_images)
        if t >= 1:
            game.animation = None


def draw_piece(screen, piece, center, piece_images):
    color = "w" if piece.isupper() else "b"
    key = color + piece.upper()
    image = piece_images[key]
    shadow = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 70))
    shadow.blit(image, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    shadow_rect = shadow.get_rect(center=(center[0] + 3, center[1] + 4))
    rect = image.get_rect(center=center)
    screen.blit(shadow, shadow_rect)
    screen.blit(image, rect)


def draw_captured_piece_icons(screen, pieces, pos, piece_images):
    x, y = pos
    for piece in pieces[:10]:
        color = "w" if piece.isupper() else "b"
        key = color + piece.upper()
        icon = pygame.transform.smoothscale(piece_images[key], (22, 22))
        screen.blit(icon, (x, y))
        x += 20


def draw_sidebar(screen, game, fonts, piece_images):
    draw_rounded_rect(screen, (SIDEBAR_LEFT, BOARD_TOP, 260, BOARD_SIZE), PANEL, 12)
    draw_text(screen, fonts["title"], "Chess Royale", (SIDEBAR_LEFT + 22, BOARD_TOP + 24))
    draw_text(screen, fonts["body"], game.status, (SIDEBAR_LEFT + 22, BOARD_TOP + 72), ACCENT if not game.game_over() else (255, 195, 96))
    turn = "Blancas" if game.turn == "w" else "Negras"
    draw_text(screen, fonts["small"], f"Turno: {turn}", (SIDEBAR_LEFT + 22, BOARD_TOP + 106), MUTED)
    draw_clock_box(screen, game, fonts, "w", "Blancas", (SIDEBAR_LEFT + 22, BOARD_TOP + 132, 100, 56))
    draw_clock_box(screen, game, fonts, "b", "Negras", (SIDEBAR_LEFT + 136, BOARD_TOP + 132, 100, 56))
    draw_button(screen, fonts["body"], (SIDEBAR_LEFT + 22, BOARD_TOP + 204, 100, 36), "Reiniciar")
    draw_button(screen, fonts["body"], (SIDEBAR_LEFT + 134, BOARD_TOP + 204, 102, 36), "Girar")
    draw_text(screen, fonts["body"], "Historial", (SIDEBAR_LEFT + 22, BOARD_TOP + 268))
    list_rect = (SIDEBAR_LEFT + 18, BOARD_TOP + 300, 224, 284)
    draw_rounded_rect(screen, list_rect, PANEL_2, 8)
    recent = game.history[-12:]
    y = BOARD_TOP + 314
    start_number = max(1, len(game.history) - len(recent) + 1)
    for index, move in enumerate(recent, start=start_number):
        color = TEXT if index == len(game.history) else MUTED
        draw_text(screen, fonts["small"], f"{index}. {game.move_label(move)}", (SIDEBAR_LEFT + 30, y), color)
        y += 26
    draw_text(screen, fonts["small"], "R reinicia  |  F gira  |  Esc cancela", (SIDEBAR_LEFT + 22, BOARD_TOP + 620), MUTED)
    captured_white, captured_black = captured_pieces(game)
    draw_text(screen, fonts["small"], "Capturas blancas", (SIDEBAR_LEFT + 22, BOARD_TOP + 652), MUTED)
    draw_captured_piece_icons(screen, captured_white, (SIDEBAR_LEFT + 22, BOARD_TOP + 672), piece_images)
    draw_text(screen, fonts["small"], "Capturas negras", (SIDEBAR_LEFT + 22, BOARD_TOP + 698), MUTED)
    draw_captured_piece_icons(screen, captured_black, (SIDEBAR_LEFT + 22, BOARD_TOP + 716), piece_images)


def draw_clock_box(screen, game, fonts, color, label, rect):
    active = game.turn == color and not game.game_over()
    box_color = (72, 99, 132) if active else PANEL_2
    text_color = TEXT if active else MUTED
    draw_rounded_rect(screen, rect, box_color, 8)
    draw_text(screen, fonts["small"], label, (rect[0] + 10, rect[1] + 7), text_color)
    draw_text(screen, fonts["clock"], game.clock_text(color), (rect[0] + rect[2] // 2, rect[1] + 36), TEXT, center=True)


def draw_button(screen, font, rect, label):
    draw_rounded_rect(screen, rect, (69, 76, 88), 8)
    draw_text(screen, font, label, (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2 - 1), TEXT, center=True)


def captured_pieces(game):
    white = []
    black = []
    for move in game.history:
        if move.captured:
            if move.captured.isupper():
                black.append(move.captured)
            else:
                white.append(move.captured)
    return white, black


def sidebar_action(pos):
    x, y = pos
    restart = pygame.Rect(SIDEBAR_LEFT + 22, BOARD_TOP + 204, 100, 36)
    flip = pygame.Rect(SIDEBAR_LEFT + 134, BOARD_TOP + 204, 102, 36)
    if restart.collidepoint(x, y):
        return "restart"
    if flip.collidepoint(x, y):
        return "flip"
    return None


def make_fonts():
    piece_font = pygame.font.SysFont(["Segoe UI Symbol", "Arial Unicode MS", "DejaVu Sans"], 64)
    return {
        "title": pygame.font.SysFont("Segoe UI", 30, bold=True),
        "body": pygame.font.SysFont("Segoe UI", 18),
        "small": pygame.font.SysFont("Segoe UI", 15),
        "clock": pygame.font.SysFont("Segoe UI", 25, bold=True),
        "piece": piece_font,
        "mini_piece": pygame.font.SysFont(["Segoe UI Symbol", "Arial Unicode MS", "DejaVu Sans"], 22),
    }


async def main():
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass
    pygame.display.set_caption("Chess Royale")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    draw_startup_message(screen, "Cargando piezas y sonidos...")
    clock = pygame.time.Clock()
    try:
        fonts = make_fonts()
        piece_images = load_piece_images()
        sounds = load_sounds() if pygame.mixer.get_init() else {}
    except Exception as error:
        await show_startup_error(screen, error)
        return
    game = Game()
    game.reset()
    running = True
    while running:
        dt = clock.tick(FPS) / 1000
        if game.animation:
            game.animation.elapsed += dt
        game.update_clock(dt)
        if game.pending_sound:
            play_sound(sounds, game.pending_sound)
            game.pending_sound = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game.selected = None
                    game.legal_targets = []
                elif event.key == pygame.K_r:
                    game.reset()
                    play_sound(sounds, "game-start")
                elif event.key == pygame.K_f:
                    game.flipped = not game.flipped
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = sidebar_action(event.pos)
                if action == "restart":
                    game.reset()
                    play_sound(sounds, "game-start")
                elif action == "flip":
                    game.flipped = not game.flipped
                else:
                    game.handle_click(event.pos)
                    play_sound(sounds, game.pending_sound)
                    game.pending_sound = None
        screen.fill((25, 27, 32))
        draw_board(screen, game, fonts)
        draw_pieces(screen, game, fonts, piece_images)
        draw_sidebar(screen, game, fonts, piece_images)
        pygame.display.flip()
        await asyncio.sleep(0)
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())





