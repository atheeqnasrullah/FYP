"""Treasure Hunt: walk an explorer across an island grid and open treasure chests.

Each step uses a directional movement (Left/Right/Up/Down) and each chest needs
an open-hand then a close-hand gesture, so a session practises all six camera
movements. The prompt always names the next useful movement, which is logged as
the target for that attempt.
"""
import math
import random
from collections import deque

import pygame

from src.games.balloon_pop import draw_hand
from src.games.game_engine import BaseGame, GOOD, INK, MUTED
from src.realtime.pipeline import latest, lock

COLS, ROWS, TILE = 9, 7, 60
STEPS = {"Left": (-1, 0), "Right": (1, 0), "Up": (0, -1), "Down": (0, 1)}
SAND, SAND_DARK, GRASS = (236, 212, 158), (226, 198, 140), (126, 186, 104)
WOOD, WOOD_DARK, GOLD = (150, 92, 48), (104, 60, 30), (255, 206, 72)
MOVE_MS, SETTLE_MS, NEXT_ISLAND_MS = 150, 400, 2200


class TreasureHunt(BaseGame):
    name = "Treasure_Hunt"
    def instructions(self):
        if getattr(self, "control_mode", "keyboard") in ("vision", "live"):
            return [
                "Your hand is a joystick. Push it LEFT, RIGHT, UP or DOWN",
                "to walk one square, then bring it back to the centre.",
                "Follow the yellow arrow to the nearest chest.",
                "On a chest: OPEN your hand, then make a FIST to grab the gold.",
                "Collect every chest to sail to the next island.",
            ]
        return [
            "Press an arrow key to walk one square.",
            "Follow the yellow arrow to the nearest chest.",
            "On a chest: press O to open it, then C to grab the gold.",
            "Collect every chest to sail to the next island.",
        ]

    def controls_hint(self):
        if getattr(self, "control_mode", "keyboard") in ("vision", "live"):
            return "Push hand to walk, back to centre   Open / fist at a chest   |   Enter pause   |   M sound   |   Esc finish"
        return "Arrows walk   O open   C grab   |   Enter pause   |   M sound   |   Esc finish"

    def joystick_radius(self):
        """How far (fraction of the camera view) the hand must move from the centre for a step."""
        return self.difficulty.value(0.08, 0.16)

    def joystick(self, pointer):
        """Direction for a hand position, firing once per push; the hand must come back to the centre."""
        if pointer is None:
            self.hand_vector = None
            return None
        # The camera picture is 4:3, so vertical offsets are scaled to match horizontal ones.
        dx, dy = pointer[0] - .5, (pointer[1] - .5) * .75
        self.hand_vector = (dx, dy)
        reach = self.joystick_radius()
        dist = math.hypot(dx, dy)
        if dist < reach * .55:
            self.armed = True
            return None
        if not self.armed or dist < reach:
            return None
        self.armed = False
        if abs(dx) >= abs(dy):
            return "Right" if dx > 0 else "Left"
        return "Down" if dy > 0 else "Up"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rng = random.Random()
        self.ox = 34
        self.oy = 128
        self.pad = pygame.Rect(self.ox + COLS * TILE + 24, 112, self.W - (self.ox + COLS * TILE + 24) - 14, 440)
        self.armed = True        # hand must return to the centre between steps
        self.hand_vector = None  # hand offset from the camera centre, for the control panel
        self.footprints = []
        self.phase = "explore"

    # ------------------------------------------------------------ island generation
    def free_cells(self, blocked):
        return [(c, r) for c in range(COLS) for r in range(ROWS) if (c, r) not in blocked]

    def path(self, start, goals, blocked):
        """Shortest path (list of cells, excluding start) to the nearest goal, or None."""
        queue, came = deque([start]), {start: None}
        while queue:
            cell = queue.popleft()
            if cell in goals:
                route = []
                while cell != start:
                    route.append(cell)
                    cell = came[cell]
                return route[::-1]
            for dc, dr in STEPS.values():
                nxt = (cell[0] + dc, cell[1] + dr)
                if 0 <= nxt[0] < COLS and 0 <= nxt[1] < ROWS and nxt not in blocked and nxt not in came:
                    came[nxt] = cell
                    queue.append(nxt)
        return None

    def level_count(self):
        return getattr(self, "chests_collected", 0)

    def new_island(self):
        """Random island whose chests are all reachable; harder levels add chests and obstacles."""
        chests_wanted = max(2, round(self.difficulty.value(2, 5)))
        obstacles_wanted = round(self.difficulty.value(6, 16))
        for _ in range(200):
            start = (self.rng.randrange(COLS), self.rng.randrange(ROWS))
            cells = [c for c in self.free_cells({start}) if abs(c[0] - start[0]) + abs(c[1] - start[1]) > 1]
            self.rng.shuffle(cells)
            obstacles = {cell: self.rng.choice(("rock", "palm", "water")) for cell in cells[:obstacles_wanted]}
            chests = cells[obstacles_wanted:obstacles_wanted + chests_wanted]
            blocked = set(obstacles)
            if all(self.path(start, {chest}, blocked) for chest in chests):
                self.player = start
                self.draw_pos = [float(start[0]), float(start[1])]
                self.obstacles = obstacles
                self.chests = {chest: "closed" for chest in chests}
                self.map_surface = self.render_map()
                return
        raise RuntimeError("Could not generate a reachable island")

    # ------------------------------------------------------------ rules
    def closed_chests(self):
        return {cell for cell, state in self.chests.items() if state != "collected"}

    def route(self):
        return self.path(self.player, self.closed_chests(), set(self.obstacles)) or []

    def suggested_move(self):
        route = self.route()
        if not route:
            return None
        step = (route[0][0] - self.player[0], route[0][1] - self.player[1])
        return next(name for name, delta in STEPS.items() if delta == step)

    def set_explore_target(self):
        self.phase = "explore"
        move = self.suggested_move()
        if move:
            self.target_set(move)

    def prompt_text(self):
        if self.phase == "unlock":
            return "Open your hand"
        if self.phase == "grab":
            return "Close your hand: grab the gold"
        if self.phase == "cleared":
            return "Island cleared!"
        return f"Move {self.target.upper()}" if self.target in STEPS else super().prompt_text()

    def handle(self, cmd, now):
        """Apply one new gesture according to the current phase."""
        if self.phase == "explore":
            if cmd not in STEPS:
                return
            self.log(cmd)
            dc, dr = STEPS[cmd]
            nxt = (self.player[0] + dc, self.player[1] + dr)
            if not (0 <= nxt[0] < COLS and 0 <= nxt[1] < ROWS) or nxt in self.obstacles:
                self.bump_until = now + 250
                self.popup("Blocked: try another way", (255, 170, 150), 28)
                self.set_explore_target()
                return
            self.footprints.append((self.player, cmd, now))
            self.footprints = self.footprints[-12:]
            self.player = nxt
            self.move_started = now
            if self.chests.get(nxt) == "closed":
                self.phase = "unlock"
                self.settle_until = now + MOVE_MS + SETTLE_MS
                self.target_set("Hand_Open")
            else:
                self.set_explore_target()
        elif self.phase == "unlock":
            if now < self.settle_until or cmd not in ("Hand_Open", "Hand_Close", *STEPS):
                return
            if cmd in STEPS:
                self.popup("Stay on the chest: open your hand", (255, 214, 92), 28)
                return
            if self.log(cmd, pos=self.cell_center(self.player), title="Chest unlocked" if cmd == self.target else None, card=True):
                self.chests[self.player] = "open"
                self.phase = "grab"
                self.target_set("Hand_Close")
            else:
                self.popup("Open your hand first", (255, 214, 92), 28)
        elif self.phase == "grab":
            if cmd not in ("Hand_Close", *STEPS):
                return
            if cmd in STEPS:
                self.popup("Make a fist to grab the gold first", (255, 214, 92), 28)
                return
            if self.log(cmd, pos=self.cell_center(self.player), title="Gold grabbed" if cmd == self.target else None, card=True, grip=True):
                self.chests[self.player] = "collected"
                self.chests_collected = getattr(self, "chests_collected", 0) + 1
                self.score += 25
                self.sound("chest")
                self.popup("+25 gold!", GOLD, 40)
                cx, cy = self.cell_center(self.player)
                for _ in range(22):
                    angle = self.rng.uniform(0, math.tau)
                    speed = self.rng.uniform(2, 6)
                    self.coins.append([cx, cy, math.cos(angle) * speed, math.sin(angle) * speed - 3, 700])
                if not self.closed_chests():
                    self.phase = "cleared"
                    self.cleared_at = now
                    self.islands += 1
                    self.score += 50
                    self.popup("Island cleared! +50", (110, 231, 160), 44)
                    self.target_set("Island cleared!")
                else:
                    self.set_explore_target()
            else:
                self.popup("Close your hand to grab the gold", (255, 214, 92), 28)

    # ------------------------------------------------------------ drawing
    def cell_center(self, cell):
        return self.ox + cell[0] * TILE + TILE // 2, self.oy + cell[1] * TILE + TILE // 2

    def render_map(self):
        surface = pygame.Surface((COLS * TILE, ROWS * TILE), pygame.SRCALPHA)
        rng = random.Random(hash(tuple(sorted(self.obstacles))))
        for c in range(COLS):
            for r in range(ROWS):
                rect = pygame.Rect(c * TILE, r * TILE, TILE, TILE)
                pygame.draw.rect(surface, SAND if (c + r) % 2 == 0 else SAND_DARK, rect)
                if rng.random() < .18:
                    pygame.draw.circle(surface, GRASS, (rect.x + rng.randint(10, 50), rect.y + rng.randint(10, 50)), rng.randint(3, 6))
        for (c, r), kind in self.obstacles.items():
            x, y = c * TILE, r * TILE
            if kind == "water":
                pygame.draw.rect(surface, (64, 150, 208), (x + 3, y + 3, TILE - 6, TILE - 6), border_radius=14)
                for k in range(2):
                    yy = y + 22 + k * 16
                    pygame.draw.arc(surface, (190, 228, 247), (x + 12, yy - 6, 18, 12), math.pi, 2 * math.pi, 2)
                    pygame.draw.arc(surface, (190, 228, 247), (x + 30, yy - 6, 18, 12), math.pi, 2 * math.pi, 2)
            elif kind == "rock":
                pygame.draw.ellipse(surface, (0, 0, 0, 50), (x + 8, y + 38, 46, 14))
                pygame.draw.polygon(surface, (120, 124, 134), [(x + 10, y + 46), (x + 18, y + 18), (x + 34, y + 10), (x + 50, y + 22), (x + 52, y + 46)])
                pygame.draw.polygon(surface, (160, 165, 176), [(x + 18, y + 22), (x + 34, y + 14), (x + 40, y + 28), (x + 22, y + 34)])
            else:
                pygame.draw.ellipse(surface, (0, 0, 0, 45), (x + 14, y + 44, 34, 10))
                pygame.draw.line(surface, (136, 96, 56), (x + 30, y + 50), (x + 34, y + 20), 6)
                for angle in (200, 250, 290, 340, 20):
                    a = math.radians(angle)
                    pygame.draw.line(surface, (46, 140, 76), (x + 34, y + 20), (x + 34 + math.cos(a) * 22, y + 20 + math.sin(a) * 14), 6)
                pygame.draw.circle(surface, (120, 78, 40), (x + 33, y + 23), 4)
        pygame.draw.rect(surface, (122, 92, 52), surface.get_rect(), 4, border_radius=6)
        return surface

    def draw_chest(self, cell, state, now):
        cx, cy = self.cell_center(cell)
        body = pygame.Rect(cx - 20, cy - 6, 40, 24)
        if state == "collected":
            pygame.draw.rect(self.screen, (120, 96, 72), body, border_radius=4)
            pygame.draw.rect(self.screen, (80, 62, 46), (cx - 20, cy - 20, 40, 10), border_radius=4)
            return
        if state == "closed" and cell != self.player:
            # A soft pulse helps patients spot the chests.
            glow = 6 + 3 * math.sin(now / 250)
            pygame.draw.circle(self.screen, (255, 230, 140), (cx, cy + 4), int(26 + glow), 2)
        pygame.draw.ellipse(self.screen, (176, 148, 100), (cx - 22, cy + 14, 44, 10))
        pygame.draw.rect(self.screen, WOOD, body, border_radius=4)
        pygame.draw.rect(self.screen, WOOD_DARK, body, 2, border_radius=4)
        pygame.draw.rect(self.screen, GOLD, (cx - 20, cy + 2, 40, 4))
        if state == "closed":
            pygame.draw.rect(self.screen, WOOD, (cx - 20, cy - 18, 40, 14), border_radius=6)
            pygame.draw.rect(self.screen, WOOD_DARK, (cx - 20, cy - 18, 40, 14), 2, border_radius=6)
            pygame.draw.rect(self.screen, GOLD, (cx - 5, cy - 8, 10, 12), border_radius=2)
            pygame.draw.circle(self.screen, WOOD_DARK, (cx, cy - 2), 2)
        else:
            pygame.draw.polygon(self.screen, WOOD, [(cx - 20, cy - 6), (cx + 20, cy - 6), (cx + 16, cy - 30), (cx - 16, cy - 30)])
            pygame.draw.polygon(self.screen, WOOD_DARK, [(cx - 20, cy - 6), (cx + 20, cy - 6), (cx + 16, cy - 30), (cx - 16, cy - 30)], 2)
            for k in range(5):
                pygame.draw.circle(self.screen, GOLD, (cx - 12 + k * 6, cy - 6 + (k % 2) * 3), 5)
            shine = int(4 + 3 * math.sin(now / 120))
            pygame.draw.circle(self.screen, (255, 250, 210), (cx + 8, cy - 10), shine)

    def draw_explorer(self, now):
        progress = min(1.0, (now - self.move_started) / MOVE_MS)
        for i in (0, 1):
            self.draw_pos[i] += (self.player[i] - self.draw_pos[i]) * (1 if progress >= 1 else .35)
        x = self.ox + self.draw_pos[0] * TILE + TILE / 2
        y = self.oy + self.draw_pos[1] * TILE + TILE / 2
        if now < self.bump_until:
            x += math.sin(now / 18) * 4
        bob = math.sin(now / 200) * 2
        x, y = int(x), int(y + bob)
        pygame.draw.ellipse(self.screen, (176, 148, 100), (x - 15, y + 18, 30, 8))
        pygame.draw.rect(self.screen, (40, 72, 120), (x - 9, y + 6, 7, 14), border_radius=3)
        pygame.draw.rect(self.screen, (40, 72, 120), (x + 2, y + 6, 7, 14), border_radius=3)
        pygame.draw.rect(self.screen, (32, 160, 150), (x - 12, y - 12, 24, 22), border_radius=7)
        pygame.draw.circle(self.screen, (243, 196, 160), (x, y - 20), 10)
        pygame.draw.ellipse(self.screen, (150, 104, 52), (x - 17, y - 28, 34, 9))
        pygame.draw.rect(self.screen, (176, 124, 64), (x - 9, y - 38, 18, 13), border_radius=4)
        pygame.draw.circle(self.screen, (40, 40, 40), (x - 4, y - 20), 2)
        pygame.draw.circle(self.screen, (40, 40, 40), (x + 4, y - 20), 2)

    def draw_hint(self, now):
        route = self.route()
        if not route:
            return
        if self.difficulty.level <= 2.5:
            # Easier levels show the whole path; harder levels only the next step.
            for i, cell in enumerate(route[:-1]):
                cx, cy = self.cell_center(cell)
                alpha_pulse = 150 + int(80 * math.sin(now / 250 - i * .6))
                dot = pygame.Surface((14, 14), pygame.SRCALPHA)
                pygame.draw.circle(dot, (255, 250, 210, alpha_pulse), (7, 7), 6)
                self.screen.blit(dot, (cx - 7, cy - 7))
        move = self.suggested_move()
        if not move:
            return
        dc, dr = STEPS[move]
        cx, cy = self.cell_center(self.player)
        pulse = 4 * math.sin(now / 160)
        tip = (cx + dc * (TILE * .78 + pulse), cy + dr * (TILE * .78 + pulse))
        side = (-dr, dc)
        base = (cx + dc * TILE * .45, cy + dr * TILE * .45)
        points = [tip, (base[0] + side[0] * 14, base[1] + side[1] * 14), (base[0] - side[0] * 14, base[1] - side[1] * 14)]
        pygame.draw.polygon(self.screen, GOLD, points)
        pygame.draw.polygon(self.screen, (120, 80, 10), points, 2)

    def draw_bubble(self, text, now):
        cx, cy = self.cell_center(self.player)
        font = self.get_font(26)
        width = font.size(text)[0] + 24
        rect = pygame.Rect(cx - width // 2, cy - 82 + int(math.sin(now / 220) * 3), width, 34)
        rect.clamp_ip(pygame.Rect(0, 64, self.W, self.H - 96))
        pygame.draw.rect(self.screen, (255, 252, 240), rect, border_radius=10)
        pygame.draw.rect(self.screen, (120, 92, 52), rect, 2, border_radius=10)
        self.text(text, rect.center, (60, 40, 20), 26, center=True, shadow=False)

    def draw_sea(self, now):
        """Animated sea with a beach and surf around the island."""
        self.screen.fill((38, 128, 186))
        for row in range(70, self.H, 26):
            shift = (now / 40 + row * 7) % 60
            for x in range(-60, self.W + 60, 60):
                pygame.draw.arc(self.screen, (92, 170, 214), (x + shift, row, 30, 12), math.pi, 2 * math.pi, 2)
        island = pygame.Rect(self.ox, self.oy, COLS * TILE, ROWS * TILE)
        foam = 4 + 2 * math.sin(now / 400)
        pygame.draw.rect(self.screen, (226, 244, 250), island.inflate(36 + foam * 2, 36 + foam * 2), border_radius=34)
        pygame.draw.rect(self.screen, (245, 226, 176), island.inflate(28, 28), border_radius=30)

    def draw_footprints(self, now):
        for cell, direction, made in self.footprints:
            age = (now - made) / 6000
            if age >= 1:
                continue
            cx, cy = self.cell_center(cell)
            dc, dr = STEPS[direction]
            color = (196, 160, 104)
            for k, side in ((0, -1), (1, 1)):
                fx = cx + dc * (k * 14 - 7) + dr * side * 5
                fy = cy + dr * (k * 14 - 7) + dc * side * 5
                pygame.draw.ellipse(self.screen, color, (fx - 4, fy - 5, 8, 10))

    def draw_pad(self, now, frame, camera):
        """Control panel: camera view with joystick zones (or arrow keys), gesture to make and chest count."""
        pad = self.pad
        self.panel(pad, 215)
        self.text("Your hand" if camera else "Controls", (pad.centerx, pad.y + 20), MUTED, 24, center=True)
        view = pygame.Rect(pad.x + 14, pad.y + 40, pad.w - 28, int((pad.w - 28) * .75))
        if camera and frame is not None:
            import cv2
            import numpy as np
            small = cv2.cvtColor(cv2.resize(frame, view.size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
            self.screen.blit(pygame.surfarray.make_surface(np.transpose(small, (1, 0, 2))), view.topleft)
        else:
            pygame.draw.rect(self.screen, (28, 40, 58), view)
        pygame.draw.rect(self.screen, (90, 110, 140), view, 2)
        cx, cy = view.center
        if self.phase in ("unlock", "grab"):
            shade = pygame.Surface(view.size, pygame.SRCALPHA); shade.fill((10, 18, 32, 150))
            self.screen.blit(shade, view.topleft)
            closed = self.phase == "grab"
            draw_hand(self.screen, cx, cy + 6, closed, (255, 120, 96) if closed else (255, 226, 110), scale=2.0)
            self.text("Make a FIST" if closed else "OPEN your hand", (cx, view.bottom - 18), INK, 28, center=True)
        elif camera:
            reach = self.joystick_radius()
            scale = view.w
            inner, outer = int(reach * .55 * scale), int(reach * scale)
            overlay = pygame.Surface(view.size, pygame.SRCALPHA)
            ox, oy = view.w // 2, view.h // 2
            target = self.target if self.phase == "explore" else None
            for name, (dc, dr) in STEPS.items():
                tip = (ox + dc * (outer + 30), oy + dr * (outer + 30))
                side = (-dr, dc)
                base = (ox + dc * (outer + 6), oy + dr * (outer + 6))
                pts = [tip, (base[0] + side[0] * 16, base[1] + side[1] * 16), (base[0] - side[0] * 16, base[1] - side[1] * 16)]
                pygame.draw.polygon(overlay, (255, 206, 72, 235) if name == target else (255, 255, 255, 90), pts)
            pygame.draw.circle(overlay, (255, 255, 255, 50), (ox, oy), outer)
            pygame.draw.circle(overlay, (255, 255, 255, 160), (ox, oy), outer, 2)
            pygame.draw.circle(overlay, (110, 231, 160, 90) if self.armed else (255, 255, 255, 40), (ox, oy), inner)
            self.screen.blit(overlay, view.topleft)
            if self.hand_vector is not None:
                hx = max(view.x + 8, min(view.right - 8, int(cx + self.hand_vector[0] * scale)))
                hy = max(view.y + 8, min(view.bottom - 8, int(cy + self.hand_vector[1] * scale)))
                pygame.draw.circle(self.screen, (0, 0, 0), (hx + 2, hy + 2), 10)
                pygame.draw.circle(self.screen, (255, 206, 72), (hx, hy), 10)
                pygame.draw.circle(self.screen, (120, 80, 10), (hx, hy), 10, 3)
                status = "Push towards the arrow" if self.armed else "Back to the centre"
            else:
                status = "Show your hand to the camera"
            self.text(status, (cx, view.bottom + 18), GOOD if self.armed and self.hand_vector else (255, 214, 92), 24, center=True)
        else:
            keys = {"Up": (0, -1), "Left": (-1, 0), "Down": (0, 0), "Right": (1, 0)}
            for name, (kx, ky) in keys.items():
                key = pygame.Rect(0, 0, 54, 46); key.center = (cx + kx * 60, cy + 26 + ky * 52)
                active = self.phase == "explore" and name == self.target
                pygame.draw.rect(self.screen, (255, 206, 72) if active else (70, 84, 108), key, border_radius=10)
                pygame.draw.rect(self.screen, (30, 36, 50), key, 2, border_radius=10)
                dc, dr = STEPS[name]
                pts = [(key.centerx + dc * 12, key.centery + dr * 12), (key.centerx - dr * 10 - dc * 6, key.centery + dc * 10 - dr * 6), (key.centerx + dr * 10 - dc * 6, key.centery - dc * 10 - dr * 6)]
                pygame.draw.polygon(self.screen, (40, 30, 10) if active else INK, pts)
        # Chest counter.
        y = pad.bottom - 96
        self.text(f"Island {self.islands + 1}", (pad.centerx, y), INK, 28, center=True)
        total = len(self.chests)
        width = total * 34
        for i, state in enumerate(sorted(self.chests.values(), key=lambda st: st != "collected")):
            x = pad.centerx - width // 2 + i * 34 + 17
            box = pygame.Rect(x - 13, y + 26, 26, 18)
            pygame.draw.rect(self.screen, (150, 92, 48) if state == "collected" else (70, 76, 92), box, border_radius=4)
            pygame.draw.rect(self.screen, GOLD if state == "collected" else (110, 118, 136), (box.x, box.y + 7, box.w, 4))
        collected = sum(1 for st in self.chests.values() if st == "collected")
        self.text(f"{collected} of {total} chests", (pad.centerx, y + 66), MUTED, 22, center=True)

    # ------------------------------------------------------------ main loop
    def run(self):
        clock = pygame.time.Clock()
        self.begin()
        self.islands = 0
        self.coins = []
        self.move_started = self.bump_until = self.settle_until = self.cleared_at = 0
        self.new_island()
        self.set_explore_target()
        last = None
        while self.running:
            self.read_input()
            self.wait_for_required_emg()
            if not self.running:
                break
            now = pygame.time.get_ticks()
            camera = getattr(self, "control_mode", "keyboard") in ("vision", "live")
            with lock:
                emg_features = latest.get("emg_features")
                pointer = latest.get("pointer")
                visual = latest.get("vis")
                fist = bool(latest.get("fist", False))
                frame = latest.get("frame")
                frame = None if frame is None else frame.copy()
            self.emg_rms = float((emg_features or {}).get("RMS", 0.0))
            self.emg_mav = float((emg_features or {}).get("MAV", 0.0))

            moving = now - self.move_started < MOVE_MS
            if camera:
                # Hand position is a joystick for walking; open hand / fist work the chests.
                step = self.joystick(pointer) if self.phase == "explore" and not moving else None
                gesture = "Hand_Close" if fist else ("Hand_Open" if visual and visual[0] == "Hand_Open" else None)
                if self.phase != "explore":
                    self.joystick(pointer)
                self.cmd = step or gesture or "Rest"
                # Grabbing the gold needs a grip at the required effort (Webcam + EMG mode).
                grip = self.grip(gesture == "Hand_Close", ready=self.phase == "grab", pos=self.cell_center(self.player))
                if grip == "weak" and self.phase == "grab":
                    self.log_weak_grip(); self.target_set("Hand_Close")
                if gesture == "Hand_Close" and self.phase == "grab" and grip != "fire":
                    gesture = None
                cmd = step or (gesture if self.phase in ("unlock", "grab") else None)
            else:
                cmd = self.cmd if self.cmd not in ("Rest", "No_Hand", None) else None
            if self.phase == "cleared":
                if now - self.cleared_at > NEXT_ISLAND_MS:
                    self.new_island()
                    self.footprints = []
                    self.set_explore_target()
            elif not moving:
                if camera and cmd in STEPS:
                    self.handle(cmd, now)
                    last = None
                # React once per new gesture; a held gesture does not repeat.
                elif cmd and cmd != last:
                    self.handle(cmd, now)
                    last = cmd
                elif not cmd:
                    last = None

            for coin in self.coins:
                coin[0] += coin[2]; coin[1] += coin[3]; coin[3] += .25; coin[4] -= clock.get_time()
            self.coins = [coin for coin in self.coins if coin[4] > 0]

            self.draw_sea(now)
            self.screen.blit(self.map_surface, (self.ox, self.oy))
            self.draw_footprints(now)
            for cell, state in self.chests.items():
                self.draw_chest(cell, state, now)
            if self.phase == "explore":
                self.draw_hint(now)
            self.draw_explorer(now)
            if self.phase == "unlock":
                self.draw_bubble("Open your hand!", now)
            elif self.phase == "grab":
                self.draw_bubble("Now make a fist to grab!", now)
            for x, y, _, _, life in self.coins:
                pygame.draw.circle(self.screen, GOLD, (int(x), int(y)), 6)
                pygame.draw.circle(self.screen, (255, 245, 190), (int(x) - 2, int(y) - 2), 2)
            if self.phase == "cleared":
                banner = pygame.Rect(0, 0, 440, 110)
                banner.center = (self.ox + COLS * TILE // 2, self.oy + ROWS * TILE // 2)
                self.panel(banner, 230)
                self.text("Island cleared!", (banner.centerx, banner.y + 38), GOLD, 46, center=True)
                self.text("Sailing to the next island...", (banner.centerx, banner.y + 80), INK, 26, center=True)
            self.draw_pad(now, frame, camera)

            self.hud()
            self.present()
            clock.tick(30)
        self.save_session()
