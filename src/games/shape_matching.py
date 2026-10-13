import math
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

    def run(self):
        clock = pygame.time.Clock()
        size = 34
        targets = {
            name: (150 + (i % 3) * 300, 175 + (i // 3) * 130)
            for i, name in enumerate(SHAPES)
        }
        homes = {name: (75 + i * 150, 520) for i, name in enumerate(SHAPES)}
        positions = {name: list(homes[name]) for name in SHAPES}
        matched = set()
        active_shape = None
        was_grabbing = False
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

            # Vision controls pointer and grasp; EMG remains an activity measurement.
            if grabbing and not was_grabbing and active_shape is None:
                available = [name for name in SHAPES if name not in matched]
                if available:
                    nearest = min(available, key=lambda name: math.dist((px, py), positions[name]))
                    if math.dist((px, py), positions[nearest]) <= size + 28:
                        active_shape = nearest
                        self.target_set(nearest)

            if active_shape is not None and grabbing:
                positions[active_shape] = [px, py]

            if was_grabbing and not grabbing and active_shape is not None:
                shape = active_shape
                if math.dist(positions[shape], targets[shape]) <= 62:
                    positions[shape] = list(targets[shape])
                    matched.add(shape)
                    self.log(shape)
                    self.target_set("All matched" if len(matched) == len(SHAPES) else "Pick up a shape")
                else:
                    positions[shape] = list(homes[shape])
                    self.log("Incorrect drop")
                    self.target_set("Pick up a shape")
                active_shape = None

            was_grabbing = grabbing

            self.draw_camera_background((27, 35, 53), overlay_alpha=28)

            for name in SHAPES:
                pygame.draw.circle(self.screen, (225, 230, 240), targets[name], size + 12, 2)
                draw_shape(self.screen, name, targets[name], size, (225, 230, 240), 3)
                draw_shape(self.screen, name, positions[name], size, (95, 235, 155) if name in matched else COLORS[name])

            pygame.draw.circle(self.screen, (255, 255, 255), (px, py), 10, 2)
            pygame.draw.circle(self.screen, (60, 220, 255), (px, py), 4)

            self.hud()
            self.text(f"Matched: {len(matched)}/{len(SHAPES)}", (self.W - 175, 48), (245, 245, 245), 22)
            if hardware_controls and emg_features:
                self.text(f"Camera gesture: {camera_gesture} | EMG RMS {self.emg_rms:.1f} | MAV {self.emg_mav:.1f}", (15, 80), (245, 245, 245), 22)
            elif getattr(self, "control_mode", "keyboard") == "live":
                self.text("EMG activity unavailable; camera control remains active.", (15, 80), (255, 220, 130), 22)
            elif not hardware_controls:
                self.text("Fallback: point with hand or mouse; hold left-click or Space to pick/drag, release to drop.", (15, 80), (255, 220, 130), 22)
            else:
                self.text(f"Camera gesture: {camera_gesture} | Close hand to pick, open to drop", (15, 80), (245, 245, 245), 22)
            if len(matched) == len(SHAPES):
                self.text("All shapes matched!", (self.W // 2 - 105, self.H // 2 - 15), (110, 255, 165), 38)

            pygame.display.flip()
            clock.tick(30)
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:
                self.running = False

        self.save_session()
