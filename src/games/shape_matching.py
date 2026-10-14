"""Shape Matching: a wooden shape-sorter. Pick up a shape and drop it in its hole.

Webcam modes point with the hand and grasp with a fist (open the hand to drop);
without a hand pointer the mouse and left-click or Space work the same way.
"""
import math
import random
from functools import lru_cache

import pygame

from src.games.balloon_pop import draw_hand
from src.games.game_engine import BaseGame, GOLD, GOOD, INK, MUTED
from src.realtime.pipeline import latest, lock


SHAPES = ("Circle", "Square", "Triangle", "Trapezium", "Rhombus", "Parallelogram")
COLORS = {
    "Circle": (240, 84, 132),
    "Square": (72, 182, 110),
    "Triangle": (250, 196, 58),
    "Trapezium": (242, 128, 54),
    "Rhombus": (150, 102, 216),
    "Parallelogram": (48, 164, 214),
}
WOOD, WOOD_DARK, WOOD_LIGHT = (196, 146, 92), (150, 104, 60), (222, 180, 128)
HOLE = (74, 50, 32)


def shape_points(name, x, y, size):
    """Polygon for a shape centred on (x, y); None for the circle."""
    if name == "Circle":
        return None
    if name == "Square":
        return [(x - size, y - size), (x + size, y - size), (x + size, y + size), (x - size, y + size)]
    if name == "Triangle":
        return [(x, y - size), (x + size * 1.1, y + size * .9), (x - size * 1.1, y + size * .9)]
    if name == "Trapezium":
        return [(x - size * .6, y - size * .8), (x + size * .6, y - size * .8), (x + size * 1.1, y + size * .8), (x - size * 1.1, y + size * .8)]
    if name == "Rhombus":
        return [(x, y - size * 1.1), (x + size, y), (x, y + size * 1.1), (x - size, y)]
    return [(x - size * .65, y - size * .75), (x + size * 1.15, y - size * .75), (x + size * .65, y + size * .75), (x - size * 1.15, y + size * .75)]


def draw_shape(surface, name, center, size, color, width=0):
    x, y = map(int, center)
    points = shape_points(name, x, y, size)
    if points is None:
        pygame.draw.circle(surface, color, (x, y), size, width)
    else:
        pygame.draw.polygon(surface, color, points, width)


def _shade(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


@lru_cache(maxsize=64)
def tile_sprite(name, color, size):
    """Glossy toy block: darker side, lighter face and a highlight, drawn at 2x then smoothed."""
    k = 2
    pad = 14
    dim = (size * 2 + pad * 2) * k
    surf = pygame.Surface((dim, dim), pygame.SRCALPHA)
    c = dim // 2
    s = size * k
    draw_shape(surf, name, (c, c + 5 * k), s, _shade(color, .62))
    draw_shape(surf, name, (c, c), s, color)
    draw_shape(surf, name, (c - 2 * k, c - 3 * k), int(s * .78), _shade(color, 1.18))
    draw_shape(surf, name, (c, c), s, _shade(color, .5), 2 * k)
    pygame.draw.ellipse(surf, (255, 255, 255, 110), (c - s * .55, c - s * .7, s * .55, s * .3))
    return pygame.transform.smoothscale(surf, (dim // k, dim // k))


@lru_cache(maxsize=64)
def hole_sprite(name, size):
    """A shape-shaped hole cut into the wooden board."""
    k = 2
    pad = 14
    dim = (size * 2 + pad * 2) * k
    surf = pygame.Surface((dim, dim), pygame.SRCALPHA)
    c = dim // 2
    s = (size + 4) * k
    draw_shape(surf, name, (c, c + 2 * k), s, WOOD_LIGHT)
    draw_shape(surf, name, (c, c), s, HOLE)
    draw_shape(surf, name, (c + 2 * k, c + 3 * k), int(s * .9), (54, 36, 22))
    return pygame.transform.smoothscale(surf, (dim // k, dim // k))


@lru_cache(maxsize=4)
def backdrop(width, height):
    """Soft playroom wall with a wooden board and a shelf for the loose shapes."""
    surf = pygame.Surface((width, height))
    for y in range(height):
        t = y / height
        surf.fill((int(206 + 30 * t), int(226 + 10 * t), int(240 - 10 * t)), (0, y, width, 1))
    for x in range(-40, width, 80):
        for y in range(70, height, 80):
            pygame.draw.circle(surf, (255, 255, 255), (x + (y // 80 % 2) * 40, y), 4)
    return surf


def draw_wood(surface, rect, base, grain_seed):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, _shade(base, .7), rect.move(0, 6), border_radius=18)
    pygame.draw.rect(surface, base, rect, border_radius=18)
    rng = random.Random(grain_seed)
    for _ in range(9):
        y = rng.randint(rect.y + 10, rect.bottom - 10)
        pygame.draw.arc(surface, _shade(base, .9), (rect.x + rng.randint(0, 200), y - 8, rng.randint(200, 500), 16), 0, math.pi, 2)
    pygame.draw.rect(surface, _shade(base, 1.12), rect, 3, border_radius=18)


class ShapeMatching(BaseGame):
    name = "Shape_Matching"
    SIZE = 34
    BOARD = pygame.Rect(70, 122, 760, 284)
    SHELF = pygame.Rect(70, 430, 760, 112)

    def instructions(self):
        if getattr(self, "control_mode", "keyboard") in ("vision", "live"):
            return [
                "Move your hand over a shape on the shelf.",
                "Make a fist to pick it up.",
                "Carry it to the hole with the same shape.",
                "Open your hand to drop it in.",
                "Fill every hole to finish the round.",
            ]
        return [
            "Point at a shape on the shelf with the mouse.",
            "Hold the left button (or Space) to pick it up.",
            "Carry it to the hole with the same shape.",
            "Let go to drop it in. Fill every hole to finish the round.",
        ]

    def controls_hint(self):
        if getattr(self, "control_mode", "keyboard") in ("vision", "live"):
            return "Fist to pick up   Open hand to drop   |   Enter pause   |   M sound   |   Esc finish"
        return "Mouse to point   Hold left-click or Space to carry   |   Enter pause   |   M sound   |   Esc finish"

    def prompt_text(self):
        return getattr(self, "prompt", "Pick up a shape")

    def reach_gain(self):
        """Easier levels amplify hand movement so the board edges need less reach."""
        return self.difficulty.value(1.5, 1.0)

    def new_round(self, round_no):
        """Pick shapes for this round; more shapes and a tighter drop zone as the level rises."""
        count = max(3, min(len(SHAPES), round(self.difficulty.value(3, 6))))
        names = random.sample(SHAPES, count)
        columns = min(3, count)
        rows = math.ceil(count / columns)
        row_ys = [self.BOARD.centery] if rows == 1 else [self.BOARD.y + 82, self.BOARD.bottom - 92]
        slots = [(self.BOARD.x + self.BOARD.w * (c + 1) // (columns + 1), row_ys[r]) for r in range(rows) for c in range(columns)]
        random.shuffle(slots)
        targets = {name: slots[i] for i, name in enumerate(names)}
        homes = {name: (self.SHELF.x + self.SHELF.w * (i + 1) // (count + 1), self.SHELF.centery - 4) for i, name in enumerate(names)}
        return names, targets, homes

    def run(self):
        clock = pygame.time.Clock()
        size = self.SIZE
        self.begin()
        round_no = 1
        names, targets, homes = self.new_round(round_no)
        positions = {name: list(homes[name]) for name in names}
        returning = {}           # shape -> time it started floating back to the shelf
        snapping = {}            # shape -> time it started settling into its hole
        shake = {}               # hole name -> time a wrong drop was made on it
        sparkles = []
        matched = set()
        active_shape = None
        was_grabbing = False
        round_done_at = None
        hand = [self.W / 2, self.H / 2]
        self.prompt = "Pick up a shape"
        self.target_set("Pick up a shape")
        while self.running:
            self.read_input()
            self.wait_for_required_emg()
            if not self.running:
                break
            now = pygame.time.get_ticks()
            with lock:
                hand_pointer = latest.get("pointer")
                visual = latest.get("vis")
                emg_features = latest.get("emg_features")
                frame_available = latest.get("frame") is not None

            camera_mode = getattr(self, "control_mode", "keyboard") in ("vision", "live")
            hardware_controls = camera_mode and hand_pointer is not None
            if hand_pointer is not None:
                gain = self.reach_gain()
                px = int((.5 + (hand_pointer[0] - .5) * gain) * self.W)
                py = int((.5 + (hand_pointer[1] - .5) * gain) * self.H)
            else:
                px, py = pygame.mouse.get_pos()
            px = max(10, min(self.W - 10, px)); py = max(70, min(self.H - 40, py))
            hand[0] += (px - hand[0]) * .6; hand[1] += (py - hand[1]) * .6
            px, py = int(hand[0]), int(hand[1])

            camera_gesture = visual[0] if visual else "Rest"
            manual_grab = bool(pygame.mouse.get_pressed()[0] or pygame.key.get_pressed()[pygame.K_SPACE])
            grabbing = camera_gesture == "Hand_Close" if hardware_controls else manual_grab
            self.emg_rms = float((emg_features or {}).get("RMS", 0.0))
            self.emg_mav = float((emg_features or {}).get("MAV", 0.0))
            snap = self.difficulty.value(80, 42)
            grab_radius = self.difficulty.value(size + 42, size + 22)

            # Next round starts a moment after the last shape is placed.
            if round_done_at is not None and now - round_done_at > 2200:
                round_no += 1
                names, targets, homes = self.new_round(round_no)
                positions = {name: list(homes[name]) for name in names}
                matched = set(); active_shape = None; round_done_at = None
                returning.clear(); snapping.clear(); shake.clear()
                self.target_set("Pick up a shape")

            available = [n for n in names if n not in matched and n not in returning and n != active_shape]
            hovered = None
            if active_shape is None and round_done_at is None and available:
                nearest = min(available, key=lambda n: math.dist((px, py), positions[n]))
                if math.dist((px, py), positions[nearest]) <= grab_radius:
                    hovered = nearest

            # Vision controls pointer and grasp; EMG remains an activity measurement.
            if round_done_at is None and grabbing and not was_grabbing and active_shape is None and hovered:
                active_shape = hovered
                self.target_set(hovered)
                self.sound("tick")

            if active_shape is not None and grabbing:
                positions[active_shape] = [px, py]

            over_hole = None
            if active_shape is not None:
                over_hole = min(names, key=lambda n: math.dist((px, py), targets[n]))
                if math.dist((px, py), targets[over_hole]) > snap or over_hole in matched:
                    over_hole = None

            if was_grabbing and not grabbing and active_shape is not None:
                shape = active_shape
                if over_hole == shape:
                    matched.add(shape)
                    snapping[shape] = now
                    self.log(shape)
                    tx, ty = targets[shape]
                    for _ in range(16):
                        a = random.uniform(0, math.tau); v = random.uniform(1.5, 4.5)
                        sparkles.append([tx, ty, math.cos(a) * v, math.sin(a) * v, 600, COLORS[shape]])
                    if len(matched) == len(names):
                        self.score += 20
                        self.popup(f"Round {round_no} complete! +20", GOOD, 42)
                        self.sound("chest")
                        round_done_at = now
                        self.target_set("Well done!")
                    else:
                        self.target_set("Pick up a shape")
                elif over_hole is not None:
                    self.log(f"Wrong hole ({over_hole})")
                    shake[over_hole] = now
                    self.popup(f"That hole is for the {over_hole.lower()}", (255, 170, 150), 30)
                    returning[shape] = (now, tuple(positions[shape]))
                    self.target_set("Pick up a shape")
                else:
                    # Dropped away from any hole: float back to the shelf without counting a mistake.
                    returning[shape] = (now, tuple(positions[shape]))
                    self.popup("Dropped: pick it up again", MUTED, 28)
                    self.target_set("Pick up a shape")
                active_shape = None

            was_grabbing = grabbing

            for shape, (started, start_pos) in list(returning.items()):
                t = min(1.0, (now - started) / 450)
                ease = 1 - (1 - t) ** 3
                positions[shape] = [start_pos[0] + (homes[shape][0] - start_pos[0]) * ease, start_pos[1] + (homes[shape][1] - start_pos[1]) * ease]
                if t >= 1:
                    del returning[shape]
            for shape, started in snapping.items():
                t = min(1.0, (now - started) / 220)
                positions[shape] = [positions[shape][0] + (targets[shape][0] - positions[shape][0]) * t, positions[shape][1] + (targets[shape][1] - positions[shape][1]) * t]
            for p in sparkles:
                p[0] += p[2]; p[1] += p[3]; p[3] += .12; p[4] -= clock.get_time()
            sparkles = [p for p in sparkles if p[4] > 0]

            # Prompt follows what the patient is doing.
            close_word = "Make a fist" if hardware_controls else "Hold the button"
            open_word = "Open your hand" if hardware_controls else "Let go"
            if round_done_at is not None:
                self.prompt = "Round complete!"
            elif active_shape is not None:
                self.prompt = f"{open_word} to drop it" if over_hole == active_shape else f"Take the {active_shape.lower()} to its hole"
            elif hovered:
                self.prompt = f"{close_word} to pick up the {hovered.lower()}"
            else:
                self.prompt = "Move to a shape on the shelf"

            # ---------------- draw
            if frame_available:
                self.draw_camera_background((27, 35, 53), overlay_alpha=60)
                wash = backdrop(self.W, self.H).copy(); wash.set_alpha(150)
                self.screen.blit(wash, (0, 0))
            else:
                self.screen.blit(backdrop(self.W, self.H), (0, 0))
            draw_wood(self.screen, self.BOARD, WOOD, 3)
            draw_wood(self.screen, self.SHELF, WOOD_LIGHT, 5)
            self.text("Shelf", (self.SHELF.x + 18, self.SHELF.y + 8), _shade(WOOD_LIGHT, .55), 22, shadow=False)

            show_names = self.difficulty.level <= 3.5
            for name in names:
                tx, ty = targets[name]
                dx = 0
                if name in shake and now - shake[name] < 420:
                    dx = int(math.sin((now - shake[name]) / 25) * 6)
                hole = hole_sprite(name, size)
                self.screen.blit(hole, (tx - hole.get_width() // 2 + dx, ty - hole.get_height() // 2))
                if name == active_shape:
                    pulse = int(4 + 3 * math.sin(now / 140))
                    ring = (120, 255, 170) if over_hole == name else (255, 236, 150)
                    pygame.draw.circle(self.screen, ring, (tx, ty), size + 22 + pulse, 4)
                elif name in shake and now - shake[name] < 420:
                    pygame.draw.circle(self.screen, (255, 110, 90), (tx + dx, ty), size + 22, 4)
                if show_names and name not in matched:
                    self.text(name, (tx, ty + size + 26), (255, 244, 225), 22, center=True)

            # Guide line from the carried shape to its hole on easier levels.
            if active_shape is not None and self.difficulty.level <= 2.5:
                sx, sy = positions[active_shape]; tx, ty = targets[active_shape]
                dist = math.dist((sx, sy), (tx, ty))
                for k in range(int(dist // 22)):
                    f = (k * 22 + (now / 20) % 22) / max(1, dist)
                    pygame.draw.circle(self.screen, (255, 250, 220), (int(sx + (tx - sx) * f), int(sy + (ty - sy) * f)), 3)

            order = [n for n in names if n != active_shape] + ([active_shape] if active_shape else [])
            for name in order:
                x, y = positions[name]
                sprite = tile_sprite(name, COLORS[name], size)
                if name == active_shape:
                    shadow = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
                    draw_shape(shadow, name, (shadow.get_width() // 2, shadow.get_height() // 2), size, (0, 0, 0, 70))
                    self.screen.blit(shadow, (x - sprite.get_width() // 2 + 10, y - sprite.get_height() // 2 + 16))
                    sprite = pygame.transform.smoothscale(sprite, (int(sprite.get_width() * 1.12), int(sprite.get_height() * 1.12)))
                elif name == hovered:
                    glow = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
                    pygame.draw.circle(glow, (255, 255, 220, int(90 + 40 * math.sin(now / 130))), (size * 2, size * 2), size + 16)
                    self.screen.blit(glow, (x - size * 2, y - size * 2))
                self.screen.blit(sprite, (int(x - sprite.get_width() / 2), int(y - sprite.get_height() / 2)))
                if name in matched:
                    pygame.draw.circle(self.screen, GOOD, (int(x + size), int(y - size)), 11)
                    pygame.draw.lines(self.screen, (20, 80, 40), False, [(x + size - 5, y - size), (x + size - 1, y - size + 4), (x + size + 5, y - size - 4)], 3)
            for sx, sy, _, _, life, color in sparkles:
                pygame.draw.circle(self.screen, color, (int(sx), int(sy)), 4)
                pygame.draw.circle(self.screen, (255, 255, 255), (int(sx) - 1, int(sy) - 1), 1)

            # Hand cursor with the current grasp state.
            draw_hand(self.screen, px, py, grabbing, (255, 120, 96) if grabbing else (255, 226, 110), scale=1.2)
            if hovered and not grabbing:
                label = "Fist to pick up" if hardware_controls else "Hold to pick up"
            elif active_shape is not None and over_hole == active_shape:
                label = "Open to drop" if hardware_controls else "Let go to drop"
            else:
                label = None
            if label:
                font = self.get_font(24); width = font.size(label)[0] + 18
                bubble = pygame.Rect(px - width // 2, py + 40, width, 28)
                bubble.clamp_ip(pygame.Rect(0, 64, self.W, self.H - 96))
                pygame.draw.rect(self.screen, (255, 252, 240), bubble, border_radius=9)
                pygame.draw.rect(self.screen, (60, 140, 90), bubble, 2, border_radius=9)
                self.text(label, bubble.center, (30, 60, 40), 24, center=True, shadow=False)

            if round_done_at is not None:
                t = min(1.0, (now - round_done_at) / 300)
                banner = pygame.Rect(0, 0, int(460 * (.6 + .4 * t)), 110)
                banner.center = (self.W // 2, self.BOARD.centery)
                self.panel(banner, 230)
                self.text(f"Round {round_no} complete!", (banner.centerx, banner.y + 38), GOLD, 44, center=True)
                self.text("Next round coming up...", (banner.centerx, banner.y + 78), INK, 26, center=True)

            self.hud()
            lines = [f"Round {round_no}   Placed {len(matched)} of {len(names)}"]
            if hardware_controls and emg_features:
                lines.append((f"EMG RMS {self.emg_rms:.1f} | MAV {self.emg_mav:.1f}", (40, 90, 60)))
            elif getattr(self, "control_mode", "keyboard") == "live":
                lines.append(("EMG activity unavailable; camera control remains active.", (200, 120, 20)))
            if camera_mode and hand_pointer is None:
                lines.append(("Show your hand to the camera (the mouse also works)", (200, 120, 20)))
            self.info(lines, (40, 52, 70), shadow=False)

            pygame.display.flip()
            clock.tick(30)
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:
                self.running = False

        self.save_session()
