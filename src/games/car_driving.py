"""Car Driving: steer between three lanes to catch stars and avoid traffic.

Webcam modes steer by hand *position*: the camera view is split into left,
middle and right zones and the car drives in the lane matching the zone the
hand is held in. (Swipe detection made the car jump back when the hand
returned to the centre.) The zones sit closer together on easier levels, so
less arm movement is needed. Keyboard and simulator modes step one lane per
Left/Right command. A fist (or C) brakes.
"""
import math
import random
from functools import lru_cache

import pygame

from src.games.game_engine import BaseGame, GOLD, INK, MUTED
from src.realtime.pipeline import latest, lock

LANE_NAMES = ("left", "middle", "right")
CAR_COLORS = ((52, 120, 214), (236, 174, 52), (142, 96, 196), (64, 170, 122), (222, 222, 230), (90, 98, 112))


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def _shade(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


@lru_cache(maxsize=8)
def player_sprite(braking):
    """Rear view of a red sports car, drawn at 2x and smoothed down for clean edges."""
    s = 2
    w, h = 132 * s, 96 * s
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    body, dark, light = (206, 38, 52), (128, 20, 32), (240, 92, 98)
    # Tyres.
    for x in (8, 104):
        pygame.draw.rect(surf, (22, 24, 28), (x * s, 58 * s, 20 * s, 34 * s), border_radius=6 * s)
        pygame.draw.rect(surf, (70, 74, 82), (x * s + 4 * s, 64 * s, 12 * s, 6 * s), border_radius=2 * s)
    # Lower body and bumper.
    pygame.draw.rect(surf, dark, (6 * s, 50 * s, 120 * s, 36 * s), border_radius=14 * s)
    pygame.draw.rect(surf, body, (8 * s, 40 * s, 116 * s, 40 * s), border_radius=16 * s)
    # Cabin and rear window with a reflection.
    pygame.draw.polygon(surf, body, [(26 * s, 42 * s), (38 * s, 12 * s), (94 * s, 12 * s), (106 * s, 42 * s)])
    pygame.draw.polygon(surf, (36, 44, 60), [(33 * s, 40 * s), (43 * s, 17 * s), (89 * s, 17 * s), (99 * s, 40 * s)])
    pygame.draw.polygon(surf, (88, 104, 132), [(46 * s, 19 * s), (58 * s, 19 * s), (48 * s, 38 * s), (38 * s, 38 * s)])
    pygame.draw.line(surf, light, (30 * s, 43 * s), (102 * s, 43 * s), 2 * s)
    # Spoiler.
    pygame.draw.rect(surf, dark, (14 * s, 34 * s, 104 * s, 7 * s), border_radius=3 * s)
    pygame.draw.rect(surf, (40, 40, 46), (30 * s, 40 * s, 5 * s, 8 * s))
    pygame.draw.rect(surf, (40, 40, 46), (97 * s, 40 * s, 5 * s, 8 * s))
    # Tail lights, brighter with a glow when braking.
    lamp = (255, 60, 50) if braking else (170, 30, 36)
    for x in (14, 94):
        if braking:
            glow = pygame.Surface((44 * s, 30 * s), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (255, 60, 40, 90), glow.get_rect())
            surf.blit(glow, ((x - 8) * s, 44 * s))
        pygame.draw.rect(surf, lamp, (x * s, 50 * s, 24 * s, 9 * s), border_radius=4 * s)
        pygame.draw.rect(surf, (255, 190, 170), (x * s + 3 * s, 52 * s, 8 * s, 3 * s), border_radius=1 * s)
    # Number plate and exhausts.
    pygame.draw.rect(surf, (240, 240, 232), (50 * s, 62 * s, 32 * s, 11 * s), border_radius=2 * s)
    font = pygame.font.Font(None, 11 * s)
    plate = font.render("REHAB", True, (40, 40, 60))
    surf.blit(plate, (66 * s - plate.get_width() // 2, 63 * s))
    for x in (34, 90):
        pygame.draw.ellipse(surf, (60, 60, 66), (x * s, 76 * s, 9 * s, 6 * s))
        pygame.draw.ellipse(surf, (20, 20, 22), (x * s + 2 * s, 77 * s, 5 * s, 4 * s))
    return pygame.transform.smoothscale(surf, (w // s, h // s))


@lru_cache(maxsize=128)
def traffic_sprite(kind, color, width):
    """Rear view of another vehicle (car, van or truck) at the given pixel width."""
    base_w = 120
    tall = {"car": 78, "van": 104, "truck": 128}[kind]
    surf = pygame.Surface((base_w, tall + 14), pygame.SRCALPHA)
    dark = _shade(color, .62)
    pygame.draw.ellipse(surf, (0, 0, 0, 70), (4, tall - 2, base_w - 8, 16))
    for x in (8, base_w - 26):
        pygame.draw.rect(surf, (24, 24, 28), (x, tall - 26, 18, 26), border_radius=5)
    if kind == "car":
        pygame.draw.rect(surf, dark, (6, 34, base_w - 12, 38), border_radius=12)
        pygame.draw.rect(surf, color, (8, 28, base_w - 16, 38), border_radius=14)
        pygame.draw.polygon(surf, color, [(24, 32), (34, 6), (base_w - 34, 6), (base_w - 24, 32)])
        pygame.draw.polygon(surf, (44, 52, 68), [(30, 30), (38, 11), (base_w - 38, 11), (base_w - 30, 30)])
        lamp_y = 40
    elif kind == "van":
        pygame.draw.rect(surf, dark, (6, 10, base_w - 12, tall - 16), border_radius=10)
        pygame.draw.rect(surf, color, (8, 6, base_w - 16, tall - 20), border_radius=12)
        pygame.draw.rect(surf, (44, 52, 68), (22, 14, base_w - 44, 30), border_radius=6)
        pygame.draw.line(surf, dark, (base_w // 2, 46), (base_w // 2, tall - 18), 2)
        lamp_y = tall - 40
    else:
        pygame.draw.rect(surf, (210, 214, 220), (4, 0, base_w - 8, tall - 30), border_radius=6)
        for k in range(1, 4):
            pygame.draw.line(surf, (176, 182, 190), (4 + k * (base_w - 8) // 4, 4), (4 + k * (base_w - 8) // 4, tall - 34), 2)
        pygame.draw.rect(surf, color, (6, tall - 34, base_w - 12, 14), border_radius=4)
        lamp_y = tall - 32
    for x in (12, base_w - 34):
        pygame.draw.rect(surf, (200, 40, 40), (x, lamp_y, 22, 8), border_radius=3)
    pygame.draw.rect(surf, (236, 236, 228), (base_w // 2 - 14, lamp_y + (14 if kind == "car" else 2), 28, 9), border_radius=2)
    height = round(surf.get_height() * width / base_w)
    return pygame.transform.smoothscale(surf, (max(4, width), max(4, height)))


@lru_cache(maxsize=64)
def star_sprite(radius):
    size = radius * 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    for r, a in ((radius * 1.9, 40), (radius * 1.4, 70)):
        pygame.draw.circle(surf, (255, 220, 90, a), (c, c), int(r))
    pts = [(c + math.cos(-math.pi / 2 + i * math.pi / 5) * (radius if i % 2 == 0 else radius * .45),
            c + math.sin(-math.pi / 2 + i * math.pi / 5) * (radius if i % 2 == 0 else radius * .45)) for i in range(10)]
    pygame.draw.polygon(surf, (255, 206, 60), pts)
    pygame.draw.polygon(surf, (255, 246, 200), pts, max(1, radius // 8))
    return surf


class CarDriving(BaseGame):
    name = "Car_Driving"
    HORIZON = 150
    CAR_Y = 430
    LANES = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lane = 1
        self.target_lane = None
        self.stars = []

    def instructions(self):
        if getattr(self, "control_mode", "keyboard") in ("vision", "live"):
            return [
                "Hold your hand on the LEFT, MIDDLE or RIGHT of the camera to pick a lane.",
                "Drive into the GREEN lane to catch the gold star.",
                "The bar at the bottom shows where your hand is.",
                "Keep away from other cars. Make a fist to brake.",
            ]
        return [
            "Press LEFT or RIGHT to move one lane.",
            "Drive into the GREEN lane to catch the gold star.",
            "Keep away from other cars.",
            "Hold C to brake.",
        ]

    def controls_hint(self):
        if getattr(self, "control_mode", "keyboard") in ("vision", "live"):
            return "Hand position steers   Fist brakes   |   Enter pause   |   M sound   |   Esc finish"
        return "Left/Right arrows change lane   C brake   |   Enter pause   |   M sound   |   Esc finish"

    def prompt_text(self):
        if self.target_lane is None:
            return ""
        if self.lane == self.target_lane:
            return "Hold steady: catch the star"
        return f"Steer {self.target.upper()} to the green lane" if self.target in ("Left", "Right") else ""

    # ------------------------------------------------------------ geometry
    def road_half_width(self, y):
        p = max(0.0, min(1.0, (y - self.HORIZON) / (self.H - self.HORIZON)))
        return 34 + p * 430

    def lane_x(self, lane, y):
        return self.W / 2 + (lane - 1) * self.road_half_width(y) * (2 / 3)

    def depth(self, y):
        return max(0.0, min(1.0, (y - self.HORIZON) / (self.CAR_Y - self.HORIZON)))

    # ------------------------------------------------------------ steering
    def zone_edges(self):
        """Hand x positions (0..1, mirrored camera view) that separate the three lanes."""
        half = self.difficulty.value(0.10, 0.19)
        return 0.5 - half, 0.5 + half

    def zone_lane(self, x, current):
        """Lane for a hand x position, with a small dead band so the car doesn't flicker."""
        left, right = self.zone_edges()
        margin = 0.025
        if x < left - (margin if current != 0 else -margin):
            return 0
        if x > right + (margin if current != 2 else -margin):
            return 2
        if left + margin < x < right - margin:
            return 1
        return current

    def new_target(self):
        choices = [lane for lane in range(self.LANES) if lane != self.lane]
        self.target_lane = random.choice(choices)
        self.stars.append({"lane": self.target_lane, "y": float(self.HORIZON + 6), "spin": 0.0})
        self.target_set("Left" if self.target_lane < self.lane else "Right")

    def change_lane(self, new_lane):
        if new_lane == self.lane:
            return
        moved = "Left" if new_lane < self.lane else "Right"
        if self.lane != self.target_lane:
            right_way = moved == self.target
            self.log(moved, pos=(self.lane_x(new_lane, self.CAR_Y), self.CAR_Y),
                     title=f"Steered {moved.lower()}" if right_way else f"Wrong way: {moved.lower()}", card=True)
        self.lane = new_lane
        if self.lane != self.target_lane:
            self.target_set("Left" if self.target_lane < self.lane else "Right")

    # ------------------------------------------------------------ drawing
    def build_scenery(self):
        sky = pygame.Surface((self.W, self.HORIZON + 4))
        for y in range(self.HORIZON + 4):
            sky.fill(_lerp((52, 112, 196), (176, 220, 240), y / (self.HORIZON + 4)), (0, y, self.W, 1))
        for r, a in ((70, 30), (48, 60), (32, 255)):
            glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 236, 160, a), (r, r), r)
            sky.blit(glow, (self.W - 150 - r, 96 - r))
        far = [(0, self.HORIZON), (0, 118)] + [(x, 118 - (34 if (x // 90) % 2 else 6) + (x * 7) % 11) for x in range(45, self.W, 90)] + [(self.W, 112), (self.W, self.HORIZON)]
        pygame.draw.polygon(sky, (120, 150, 178), far)
        near = [(0, self.HORIZON), (0, 134)] + [(x, 136 - (20 if (x // 120) % 2 else 2)) for x in range(60, self.W, 120)] + [(self.W, 130), (self.W, self.HORIZON)]
        pygame.draw.polygon(sky, (86, 140, 112), near)
        return sky

    def draw_road(self, travelled, now):
        self.screen.blit(self.scenery, (0, 0))
        for cloud_x, cloud_y, size in self.clouds:
            x = int((cloud_x + now * 0.004) % (self.W + 160)) - 80
            for dx, dy, r in ((0, 0, size), (size, -size // 3, int(size * 1.2)), (size * 2, 0, size)):
                pygame.draw.circle(self.screen, (246, 250, 255), (x + dx, cloud_y + dy), r)
        cx = self.W // 2
        # Grass, curbs and asphalt drawn in thin horizontal bands; alternating
        # stripes moving towards the driver give a strong sense of speed.
        step = 3
        for y in range(self.HORIZON, self.H, step):
            p = (y - self.HORIZON) / (self.H - self.HORIZON)
            z = 1.0 / (p + 0.04)
            band = int(z * 3 - travelled * 0.9) % 2
            half = self.road_half_width(y)
            curb = 6 + p * 26
            self.screen.fill((84, 168, 92) if band else (74, 152, 82), (0, y, self.W, step))
            self.screen.fill((230, 230, 226) if band else (206, 52, 52), (int(cx - half - curb), y, int(2 * (half + curb)), step))
            self.screen.fill(_lerp((70, 74, 84), (52, 56, 64), p), (int(cx - half), y, int(2 * half), step))
            if band:
                for boundary in (-1, 1):
                    lx = cx + boundary * half / 3
                    lw = max(1, int(1 + p * 5))
                    self.screen.fill((240, 240, 230), (int(lx - lw), y, lw * 2, step))
        # Target lane: a green glow with chevrons sliding up the lane.
        if self.target_lane is not None:
            overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            top, bottom = self.HORIZON + 6, self.H
            t, b = self.road_half_width(top), self.road_half_width(bottom)
            lt, lb = self.target_lane - 1.5, self.target_lane - 0.5
            poly = [(cx + lt * t * 2 / 3, top), (cx + lb * t * 2 / 3, top), (cx + lb * b * 2 / 3, bottom), (cx + lt * b * 2 / 3, bottom)]
            alpha = 85 + int(25 * math.sin(now / 200))
            pygame.draw.polygon(overlay, (90, 235, 140, alpha), poly)
            for k in range(5):
                y = self.H - ((now * 0.12 + k * 90) % 450)
                if y < self.HORIZON + 20:
                    continue
                x = self.lane_x(self.target_lane, y)
                size = 6 + 18 * self.depth(y)
                pygame.draw.lines(overlay, (220, 255, 230, 170), False, [(x - size, y + size * .6), (x, y), (x + size, y + size * .6)], max(2, int(size / 4)))
            self.screen.blit(overlay, (0, 0))
        # Roadside trees and lamp posts.
        for side in (-1, 1):
            for i in range(6):
                p = ((i / 6) + travelled * 0.012) % 1.0
                p = p * p
                y = self.HORIZON + p * (self.H - self.HORIZON)
                half = self.road_half_width(y)
                x = int(cx + side * (half + 40 + p * 140))
                size = int(6 + p * 30)
                if i % 2:
                    pygame.draw.rect(self.screen, (96, 70, 48), (x - size // 6, int(y) - size, max(2, size // 3), size))
                    pygame.draw.circle(self.screen, (34, 104, 64), (x, int(y) - size - size // 2), size)
                    pygame.draw.circle(self.screen, (52, 132, 80), (x - size // 3, int(y - size - size / 1.4)), max(2, size // 2))
                else:
                    pygame.draw.line(self.screen, (120, 126, 136), (x, int(y)), (x, int(y) - size * 2), max(1, size // 8))
                    pygame.draw.line(self.screen, (120, 126, 136), (x, int(y) - size * 2), (x - side * size // 2, int(y) - size * 2), max(1, size // 8))
                    pygame.draw.circle(self.screen, (255, 238, 170), (x - side * size // 2, int(y) - size * 2 + 2), max(2, size // 6))

    def draw_steering_bar(self, hand_x, camera):
        bar = pygame.Rect(self.W // 2 - 270, self.H - 84, 540, 40)
        self.panel(bar.inflate(16, 30).move(0, -6), 190)
        left, right = self.zone_edges() if camera else (1 / 3, 2 / 3)
        edges = [0.0, left, right, 1.0]
        for lane in range(self.LANES):
            x0 = bar.x + int(edges[lane] * bar.w)
            x1 = bar.x + int(edges[lane + 1] * bar.w)
            rect = pygame.Rect(x0 + 2, bar.y, x1 - x0 - 4, bar.h)
            color = (40, 150, 90) if lane == self.target_lane else (54, 64, 82)
            pygame.draw.rect(self.screen, color, rect, border_radius=10)
            if lane == self.lane:
                pygame.draw.rect(self.screen, INK, rect, 3, border_radius=10)
            label = "GO HERE" if lane == self.target_lane and lane != self.lane else LANE_NAMES[lane].upper()
            self.text(label, rect.center, INK if lane == self.target_lane else MUTED, 22, center=True)
        if camera:
            if hand_x is None:
                self.text("Show your hand to the camera", (bar.centerx, bar.y - 16), GOLD, 24, center=True)
            else:
                mx = bar.x + int(max(0.0, min(1.0, hand_x)) * bar.w)
                pygame.draw.circle(self.screen, (0, 0, 0), (mx + 2, bar.centery + 2), 13)
                pygame.draw.circle(self.screen, GOLD, (mx, bar.centery), 13)
                pygame.draw.circle(self.screen, (120, 80, 10), (mx, bar.centery), 13, 3)
                self.text("Your hand", (mx, bar.y - 16), GOLD, 22, center=True)
        else:
            self.text("Use the LEFT and RIGHT arrow keys", (bar.centerx, bar.y - 16), MUTED, 22, center=True)

    def draw_speedometer(self, speed, max_speed):
        cx, cy, r = self.W - 78, self.H - 70, 50
        self.panel((cx - r - 12, cy - r - 12, 2 * r + 24, r + 52), 190)
        for k in range(11):
            a = math.pi + k * math.pi / 10
            pygame.draw.line(self.screen, MUTED, (cx + math.cos(a) * (r - 8), cy + math.sin(a) * (r - 8)), (cx + math.cos(a) * r, cy + math.sin(a) * r), 2)
        share = min(1.0, speed / max(0.1, 8.0))
        a = math.pi + share * math.pi
        pygame.draw.line(self.screen, (255, 96, 80), (cx, cy), (cx + math.cos(a) * (r - 6), cy + math.sin(a) * (r - 6)), 4)
        pygame.draw.circle(self.screen, INK, (cx, cy), 5)
        self.text(f"{speed * 15:.0f}", (cx, cy + 18), INK, 30, center=True)
        self.text("km/h", (cx, cy + 36), MUTED, 18, center=True)

    # ------------------------------------------------------------ main loop
    def run(self):
        clock = pygame.time.Clock()
        self.scenery = self.build_scenery()
        self.clouds = [(random.randint(0, self.W), random.randint(88, 112), random.randint(8, 13)) for _ in range(4)]
        self.lane = 1
        self.target_lane = None
        self.stars = []
        car_x = float(self.lane_x(self.lane, self.CAR_Y))
        speed = 0.0
        travelled = 0.0
        distance = 0.0
        obstacles = []
        last_spawn = 0
        last_cmd = None
        collision_until = 0
        caught = 0
        self.begin()
        self.new_target()

        while self.running:
            self.read_input()
            self.wait_for_required_emg()
            if not self.running:
                break
            now = pygame.time.get_ticks()
            camera = getattr(self, "control_mode", "keyboard") in ("vision", "live")
            with lock:
                visual = latest.get("vis")
                pointer = latest.get("pointer")
                fist = bool(latest.get("fist", False))
                emg_features = latest.get("emg_features")
                emg_level = latest.get("emg_level")
            hand_x = pointer[0] if (camera and pointer is not None) else None
            if camera:
                gesture = visual[0] if visual is not None else "Rest"
                closed = fist or gesture == "Hand_Close"
                self.cmd = "Hand_Close" if closed else gesture
                if hand_x is not None and not closed:
                    self.change_lane(self.zone_lane(hand_x, self.lane))
            else:
                closed = self.cmd == "Hand_Close"
                if self.cmd in ("Left", "Right") and self.cmd != last_cmd:
                    self.change_lane(max(0, min(self.LANES - 1, self.lane + (-1 if self.cmd == "Left" else 1))))
                last_cmd = self.cmd
            self.emg_rms = float((emg_features or {}).get("RMS", emg_level or 0.0))
            self.emg_mav = float((emg_features or {}).get("MAV", 0.0))
            # The brakes only bite while the grip is at the required effort (Webcam + EMG mode).
            # Braking is not a scored attempt (targets are lanes), so it gets a card, not a log entry.
            braking = closed and self.effort_ok()
            car_pos = (self.lane_x(self.lane, self.CAR_Y), self.CAR_Y)
            # The grip meter sits above the car, clear of the lane panel.
            grip = self.grip(closed, pos=(car_pos[0], self.CAR_Y - 140))
            if grip == "fire" and self.effort_gated():
                self.action_card("Braking", car_pos, True, need=self.required_effort())
            elif grip == "weak":
                cmd, self.cmd = self.cmd, "Hand_Close"   # the card names the fist, though the hand has opened
                self.action_card(f"Brake too weak: {self.weak_grip['best']:.0f}% of {self.required_effort():.0f}%", car_pos, False,
                                 self.weak_grip["best"], self.required_effort())
                self.cmd = cmd

            # Difficulty sets top speed and how often other vehicles appear.
            max_speed = self.difficulty.value(3.5, 7.5)
            spawn_ms = self.difficulty.value(2300, 1000)
            if braking:
                speed = max(0.0, speed - 0.25)
            elif now >= collision_until:
                speed = min(max_speed, speed + 0.04)

            if speed > 1.0 and now - last_spawn > spawn_ms:
                lanes = [lane for lane in range(self.LANES) if lane != self.target_lane]
                obstacles.append({"lane": random.choice(lanes), "y": float(self.HORIZON + 4),
                                  "kind": random.choice(("car", "car", "van", "truck")), "color": random.choice(CAR_COLORS)})
                last_spawn = now
            travelled += speed / 30
            distance += speed / 30
            for item in obstacles:
                item["y"] += speed * (0.35 + 1.9 * self.depth(item["y"]))
            obstacles = [o for o in obstacles if o["y"] < self.H + 60]

            for star in self.stars:
                star["y"] += speed * (0.35 + 1.9 * self.depth(star["y"])) if speed > 0.2 else 0.3
                star["spin"] += 0.08
            for star in list(self.stars):
                if self.CAR_Y - 30 <= star["y"] <= self.CAR_Y + 25 and star["lane"] == self.lane:
                    self.stars.remove(star)
                    caught += 1
                    self.score += 15
                    self.sound("chest")
                    self.popup("Star caught! +15", GOLD, 38)
                    self.new_target()
                elif star["y"] > self.CAR_Y + 25:
                    self.stars.remove(star)
                    self.miss("Missed the star")
                    self.new_target()

            collision = next((o for o in obstacles if o["lane"] == self.lane and self.CAR_Y - 34 <= o["y"] <= self.CAR_Y + 20), None)
            if collision:
                obstacles.remove(collision)
                collision_until = now + 900
                speed = 0.0
                self.score = max(0, self.score - 5)
                self.miss("Crash! Watch the traffic")

            # ---------------- draw
            self.draw_road(travelled, now)
            drawables = [(o["y"], "car", o) for o in obstacles] + [(s["y"], "star", s) for s in self.stars]
            for y, kind, item in sorted(drawables, key=lambda d: d[0]):
                d = self.depth(y)
                x = self.lane_x(item["lane"], y)
                if kind == "car":
                    width = max(8, int(118 * (0.18 + 0.82 * d)) // 2 * 2)
                    sprite = traffic_sprite(item["kind"], item["color"], width)
                    self.screen.blit(sprite, (int(x - sprite.get_width() / 2), int(y - sprite.get_height() + 8 * d)))
                else:
                    radius = max(4, int(4 + 18 * d))
                    sprite = star_sprite(radius)
                    bob = math.sin(item["spin"] * 2) * 3 * d
                    self.screen.blit(sprite, (int(x - sprite.get_width() / 2), int(y - sprite.get_height() / 2 - 10 * d + bob)))
            target_x = self.lane_x(self.lane, self.CAR_Y)
            car_x += (target_x - car_x) * 0.2
            sprite = player_sprite(braking)
            tilt = max(-8.0, min(8.0, (target_x - car_x) * -0.06))
            if abs(tilt) > 0.3:
                sprite = pygame.transform.rotozoom(sprite, tilt, 1.0)
            shadow = pygame.Surface((140, 26), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
            self.screen.blit(shadow, (int(car_x - 70), self.CAR_Y + 34))
            self.screen.blit(sprite, (int(car_x - sprite.get_width() / 2), int(self.CAR_Y - sprite.get_height() / 2 + 6)))
            if now < collision_until and (now // 120) % 2:
                self.text("Crash!", (int(car_x), self.CAR_Y - 70), (255, 120, 100), 40, center=True)
            elif braking:
                self.text("BRAKING", (int(car_x), self.CAR_Y - 70), (255, 110, 90), 34, center=True)

            self.hud()
            # Muscle activity is shown by the engine's input strip (BaseGame.draw_input_strip).
            self.info([f"Stars caught {caught}   Distance {distance * 0.05:.2f} km"])
            self.draw_steering_bar(hand_x, camera)
            self.draw_speedometer(speed, max_speed)
            self.present()
            clock.tick(30)
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:
                self.running = False

        self.save_session()
