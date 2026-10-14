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

from src.games.game_engine import BaseGame
from src.realtime.pipeline import latest, lock

COLS, ROWS, TILE = 11, 7, 60
STEPS = {"Left": (-1, 0), "Right": (1, 0), "Up": (0, -1), "Down": (0, 1)}
SAND, SAND_DARK, GRASS = (236, 212, 158), (226, 198, 140), (126, 186, 104)
WOOD, WOOD_DARK, GOLD = (150, 92, 48), (104, 60, 30), (255, 206, 72)
MOVE_MS, SETTLE_MS, NEXT_ISLAND_MS = 150, 400, 2200


class TreasureHunt(BaseGame):
    name = "Treasure_Hunt"
    how_to_play = (
        "Move your hand LEFT, RIGHT, UP or DOWN to walk one square.",
        "Follow the yellow arrow to reach the nearest chest.",
        "On a chest, OPEN your hand to unlock it,",
        "then CLOSE your hand to grab the gold.",
        "Collect every chest to sail to the next island.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rng = random.Random()
        self.ox = (self.W - COLS * TILE) // 2
        self.oy = 128
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
            if self.log(cmd):
                self.chests[self.player] = "open"
                self.phase = "grab"
                self.target_set("Hand_Close")
            else:
                self.popup("Open your hand first", (255, 214, 92), 28)
        elif self.phase == "grab":
            if cmd not in ("Hand_Close", *STEPS):
                return
            if self.log(cmd):
                self.chests[self.player] = "collected"
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
            for cell in route[:-1]:
                pygame.draw.circle(self.screen, (255, 245, 200), self.cell_center(cell), 5)
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
            with lock:
                emg_features = latest.get("emg_features")
            self.emg_rms = float((emg_features or {}).get("RMS", 0.0))
            self.emg_mav = float((emg_features or {}).get("MAV", 0.0))

            cmd = self.cmd if self.cmd not in ("Rest", "No_Hand", None) else None
            moving = now - self.move_started < MOVE_MS
            if self.phase == "cleared":
                if now - self.cleared_at > NEXT_ISLAND_MS:
                    self.new_island()
                    self.set_explore_target()
            elif not moving:
                # React once per new gesture; a held gesture does not repeat.
                if cmd and cmd != last:
                    self.handle(cmd, now)
                last = cmd

            for coin in self.coins:
                coin[0] += coin[2]; coin[1] += coin[3]; coin[3] += .25; coin[4] -= clock.get_time()
            self.coins = [coin for coin in self.coins if coin[4] > 0]

            self.draw_camera_background((34, 102, 150), overlay_alpha=70)
            self.screen.blit(self.map_surface, (self.ox, self.oy))
            for cell, state in self.chests.items():
                self.draw_chest(cell, state, now)
            if self.phase == "explore":
                self.draw_hint(now)
            self.draw_explorer(now)
            if self.phase == "unlock":
                self.draw_bubble("Open your hand!", now)
            elif self.phase == "grab":
                self.draw_bubble("Now close it to grab!", now)
            for x, y, _, _, life in self.coins:
                pygame.draw.circle(self.screen, GOLD, (int(x), int(y)), 6)
                pygame.draw.circle(self.screen, (255, 245, 190), (int(x) - 2, int(y) - 2), 2)

            self.hud()
            collected = sum(1 for state in self.chests.values() if state == "collected")
            lines = [f"Island {self.islands + 1}   Chests {collected} of {len(self.chests)}"]
            if emg_features:
                lines.append((f"EMG activity: RMS {self.emg_rms:.1f} | MAV {self.emg_mav:.1f}", (210, 245, 225)))
            elif getattr(self, "control_mode", "keyboard") == "live":
                lines.append(("EMG activity sensor unavailable", (255, 210, 130)))
            self.info(lines)
            pygame.display.flip()
            clock.tick(30)
        self.save_session()
