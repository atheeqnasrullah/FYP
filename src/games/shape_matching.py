import math
import random

import pygame

from src.games.game_engine import BaseGame
from src.realtime.pipeline import latest, lock


SHAPES = ("Circle", "Square", "Triangle", "Trapezium", "Rhombus", "Parallelogram")
COLORS = {
    "Circle": (247, 91, 139),
    "Square": (93, 190, 124),
    "Triangle": (250, 205, 75),
    "Trapezium": (242, 139, 70),
    "Rhombus": (160, 112, 220),
    "Parallelogram": (65, 175, 205),
}


def draw_shape(surface, name, center, size, color, width=0):
    x, y = map(int, center)
    if name == "Circle":
        pygame.draw.circle(surface, color, (x, y), size, width)
    elif name == "Square":
        pygame.draw.rect(surface, color, (x - size, y - size, size * 2, size * 2), width)
    elif name == "Triangle":
        points = [(x, y - size), (x - size, y + size), (x + size, y + size)]
        pygame.draw.polygon(surface, color, points, width)
    elif name == "Trapezium":
        points = [(x - size, y - size), (x + size, y - size), (x + size // 2, y + size), (x - size // 2, y + size)]
        pygame.draw.polygon(surface, color, points, width)
    elif name == "Rhombus":
        points = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
        pygame.draw.polygon(surface, color, points, width)
    else:
        points = [(x - size + 12, y - size), (x + size + 12, y - size), (x + size - 12, y + size), (x - size - 12, y + size)]
        pygame.draw.polygon(surface, color, points, width)


class ShapeMatching(BaseGame):
    name = "Shape_Matching"
    how_to_play = (
        "Move your hand so the pointer is over a coloured shape.",
        "Close your hand to pick it up.",
        "Carry it to the outline with the same shape.",
        "Open your hand to drop it. Finish the round to get new shapes.",
    )
    SIZE = 34

    def controls_hint(self):
        if getattr(self, "control_mode", "keyboard") in ("vision", "live"):
            return "Close hand to pick up   Open hand to drop   |   Enter pause   |   M sound   |   Esc finish"
        return "Mouse to point   Hold left-click or Space to drag   |   Enter pause   |   M sound   |   Esc finish"

    def new_round(self, round_no):
        """Pick shapes for this round; more shapes and a tighter drop zone as the level rises."""
        count = max(3, min(len(SHAPES), round(self.difficulty.value(3, 6))))
        names = random.sample(SHAPES, count)
        columns = min(3, count)
        rows = math.ceil(count / columns)
        slots = [(self.W * (c + 1) // (columns + 1), 190 + r * 140) for r in range(rows) for c in range(columns)]
        random.shuffle(slots)
        targets = {name: slots[i] for i, name in enumerate(names)}
        homes = {name: (self.W * (i + 1) // (count + 1), 505) for i, name in enumerate(names)}
        return names, targets, homes

    def run(self):
        clock = pygame.time.Clock()
        size = self.SIZE
        self.begin()
        round_no = 1
        names, targets, homes = self.new_round(round_no)
        positions = {name: list(homes[name]) for name in names}
        matched = set()
        active_shape = None
        was_grabbing = False
        round_done_at = None
        self.target_set("Pick up a shape")
        while self.running:
            self.read_input()
            self.wait_for_required_emg()
            if not self.running: break
            with lock:
                hand_pointer = latest.get("pointer")
                visual = latest.get("vis")
                emg_features = latest.get("emg_features")

            camera_mode = getattr(self, "control_mode", "keyboard") in ("vision", "live")
            hardware_controls = camera_mode and hand_pointer is not None
            if hand_pointer is not None:
                px, py = int(hand_pointer[0] * self.W), int(hand_pointer[1] * self.H)
            else:
                px, py = pygame.mouse.get_pos()

            camera_gesture = visual[0] if visual else "Rest"
            manual_grab = bool(pygame.mouse.get_pressed()[0] or pygame.key.get_pressed()[pygame.K_SPACE])
            grabbing = camera_gesture == "Hand_Close" if hardware_controls else manual_grab
            self.emg_rms = float((emg_features or {}).get("RMS", 0.0))
            self.emg_mav = float((emg_features or {}).get("MAV", 0.0))
            snap = self.difficulty.value(80, 42)

            # Next round starts a moment after the last shape is placed.
            if round_done_at is not None and pygame.time.get_ticks() - round_done_at > 1800:
                round_no += 1
                names, targets, homes = self.new_round(round_no)
                positions = {name: list(homes[name]) for name in names}
                matched = set(); active_shape = None; round_done_at = None
                self.target_set("Pick up a shape")

            # Vision controls pointer and grasp; EMG remains an activity measurement.
            if round_done_at is None and grabbing and not was_grabbing and active_shape is None:
                available = [name for name in names if name not in matched]
                if available:
                    nearest = min(available, key=lambda name: math.dist((px, py), positions[name]))
                    if math.dist((px, py), positions[nearest]) <= size + 28:
                        active_shape = nearest
                        self.target_set(nearest)

            if active_shape is not None and grabbing:
                positions[active_shape] = [px, py]

            if was_grabbing and not grabbing and active_shape is not None:
                shape = active_shape
                if math.dist(positions[shape], targets[shape]) <= snap:
                    positions[shape] = list(targets[shape])
                    matched.add(shape)
                    self.log(shape)
                    if len(matched) == len(names):
                        self.score += 20
                        self.popup(f"Round {round_no} complete! +20", (110, 231, 160), 40)
                        self.sound("chest")
                        round_done_at = pygame.time.get_ticks()
                        self.target_set("Well done!")
                    else:
                        self.target_set("Pick up a shape")
                else:
                    positions[shape] = list(homes[shape])
                    self.log("Incorrect drop")
                    self.target_set("Pick up a shape")
                active_shape = None

            was_grabbing = grabbing

            self.draw_camera_background((27, 35, 53), overlay_alpha=28)

            for name in names:
                glow = active_shape == name
                pygame.draw.circle(self.screen, (255, 214, 92) if glow else (225, 230, 240), targets[name], size + 14, 3 if glow else 2)
                draw_shape(self.screen, name, targets[name], size, (225, 230, 240), 3)
            for name in names:
                draw_shape(self.screen, name, positions[name], size, (95, 235, 155) if name in matched else COLORS[name])

            pygame.draw.circle(self.screen, (255, 255, 255), (px, py), 12, 3)
            pygame.draw.circle(self.screen, (255, 120, 90) if grabbing else (60, 220, 255), (px, py), 5)

            self.hud()
            lines = [f"Round {round_no}   Placed {len(matched)} of {len(names)}"]
            if hardware_controls and emg_features:
                lines.append((f"Camera gesture: {camera_gesture} | EMG RMS {self.emg_rms:.1f} | MAV {self.emg_mav:.1f}", (210, 245, 225)))
            elif getattr(self, "control_mode", "keyboard") == "live":
                lines.append(("EMG activity unavailable; camera control remains active.", (255, 220, 130)))
            elif not hardware_controls:
                lines.append(("Point with your hand or the mouse; hold left-click or Space to drag.", (255, 220, 130)))
            self.info(lines)

            pygame.display.flip()
            clock.tick(30)
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:
                self.running = False

        self.save_session()
