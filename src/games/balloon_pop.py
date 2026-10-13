import math
import random
from functools import lru_cache

import numpy as np
import pygame
from src.games.game_engine import BaseGame


@lru_cache(maxsize=48)
def _balloon_sprite(color, radius):
    """Build a small cached, softly shaded balloon sprite."""
    rx = round(radius * .82)
    width, height = 2 * rx + 16, 2 * radius + 22
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    yy, xx = np.mgrid[-radius:radius + 1, -rx:rx + 1]
    nx, ny = xx / max(rx, 1), yy / max(radius, 1)
    rho2 = nx * nx + ny * ny
    inside = rho2 <= 1
    nz = np.sqrt(np.clip(1 - rho2, 0, 1))

    # Soft light from the upper-left gives the oval a rounded, glossy volume.
    light = np.array([-0.48, -0.58, 0.66], dtype=float)
    light /= np.linalg.norm(light)
    diffuse = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
    half = light + np.array([0., 0., 1.])
    half /= np.linalg.norm(half)
    specular = np.clip(nx * half[0] + ny * half[1] + nz * half[2], 0, 1) ** 28
    rim = np.clip((1 - np.sqrt(rho2)) * 7, 0, 1)
    intensity = .22 + .76 * diffuse

    base = np.asarray(color, dtype=float)
    rgb = base[None, None, :] * intensity[:, :, None]
    rgb += 245 * specular[:, :, None] * np.array([1., .94, .9])[None, None, :]
    rgb *= (.72 + .28 * rim)[:, :, None]
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    alpha = np.where(inside, np.clip((1 - np.sqrt(rho2)) * 22 + .5, 0, 1) * 255, 0).astype(np.uint8)

    left, top = 8, 5
    surface_rgb = pygame.surfarray.pixels3d(surface)
    surface_alpha = pygame.surfarray.pixels_alpha(surface)
    surface_rgb[left:left + 2 * rx + 1, top:top + 2 * radius + 1] = np.transpose(rgb, (1, 0, 2))
    surface_alpha[left:left + 2 * rx + 1, top:top + 2 * radius + 1] = alpha.T
    del surface_rgb, surface_alpha

    center_x = left + rx
    bottom_y = top + 2 * radius
    knot = tuple(max(0, min(255, int(c * .58))) for c in color)
    pygame.draw.polygon(surface, knot, [(center_x - 5, bottom_y - 1), (center_x + 5, bottom_y - 1), (center_x, bottom_y + 8)])
    pygame.draw.polygon(surface, (*color, 255), [(center_x - 4, bottom_y), (center_x + 4, bottom_y), (center_x, bottom_y + 6)])
    pygame.draw.ellipse(surface, (255, 255, 255, 105), (int(left + rx * .2), int(top + radius * .22), int(rx * .42), int(radius * .5)))
    pygame.draw.ellipse(surface, (255, 255, 255, 180), (int(left + rx * .32), int(top + radius * .3), max(2, int(rx * .14)), max(3, int(radius * .16))))
    pygame.draw.ellipse(surface, (*knot, 210), (left, top, 2 * rx, 2 * radius), 1)
    return surface


@lru_cache(maxsize=16)
def _balloon_shadow(radius):
    rx = round(radius * .82)
    shadow = pygame.Surface((2 * rx + 10, 2 * radius + 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 75), (5, 3, 2 * rx, 2 * radius))
    return shadow


def draw_balloon(surface, x, y, color, radius, tick):
    rx = round(radius * .82)
    sprite = _balloon_sprite(tuple(color), radius)
    left, top = 8, 5
    balloon_top = y - radius
    surface.blit(_balloon_shadow(radius), (x - rx, balloon_top + 3))
    surface.blit(sprite, (x - rx - left, balloon_top - top))
    knot_y = y + radius + 8
    sway = math.sin(tick * .004 + x) * 5
    points = [(x, knot_y), (x + sway, knot_y + 8), (x - sway * .35, knot_y + 17), (x + sway * .6, knot_y + 26)]
    pygame.draw.lines(surface, (235, 229, 215), False, points, 2)


class BalloonPop(BaseGame):
    name="Balloon_Pop"

    @staticmethod
    def make_pop_sound():
        """Create a short synthesized pop; return None when audio is unavailable."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            sample_rate = 22050
            t = np.arange(int(sample_rate * .17), dtype=np.float32) / sample_rate
            rng = np.random.default_rng()
            envelope = np.exp(-t * 25)
            wave = (rng.normal(0, .48, len(t)) + .75 * np.sin(2 * np.pi * 105 * t)) * envelope
            samples = np.asarray(np.clip(wave, -1, 1) * 32767, dtype=np.int16)
            return pygame.mixer.Sound(buffer=samples.tobytes())
        except (pygame.error, OSError):
            return None

    def run(self):
        clock=pygame.time.Clock(); x=self.W//2; player_y=130; balloons=[]; fragments=[]; bursts=[]; last_spawn=0; last_action=0; was_closed=False; self.target_set("Hand_Close")
        palette=((235,70,95),(70,165,245),(255,190,55),(165,105,230),(70,205,155))
        pop_sound=self.make_pop_sound()
        while self.running:
            self.read_input()
            if not self.running: break
            mode=getattr(self,"control_mode","keyboard")
            pointer=None; emg_level=None; emg_features=None; full_fist=False
            sensor_ready=False
            if mode in ("vision","live"):
                from src.realtime.pipeline import latest, lock, emg_is_ready
                with lock:
                    visual=latest.get("vis")
                    pointer=latest.get("pointer")
                    emg_level=latest.get("emg_level")
                    emg_features=latest.get("emg_features")
                    full_fist=bool(latest.get("fist",False))
                sensor_ready=emg_is_ready()
                # The balloon action is intentionally stricter than the generic
                # Hand_Close label: require a stable, complete five-finger fist.
                gesture="Hand_Close" if full_fist else "Rest"
                self.cmd=gesture
            else:
                gesture=self.cmd
            self.emg_rms=float((emg_features or {}).get("RMS",emg_level or 0.0))
            self.emg_mav=float((emg_features or {}).get("MAV",0.0))
            if pointer is not None:
                x=max(20,min(self.W-20,int(pointer[0]*self.W)))
                player_y=max(75,min(self.H-65,int(pointer[1]*self.H)))
            else:
                if self.cmd=="Left":x-=7
                if self.cmd=="Right":x+=7
                x=max(20,min(self.W-20,x))
            now=pygame.time.get_ticks()
            if now-last_spawn>1100:
                balloons.append({"x":random.randint(72,self.W-72),"y":self.H+52,"color":random.choice(palette),"radius":random.randint(40,48),"speed":random.uniform(1.7,2.5),"state":"floating","hit_at":0})
                last_spawn=now
            for balloon in balloons:
                if balloon["state"]=="floating":
                    balloon["y"]-=balloon["speed"]
            balloons=[b for b in balloons if b["state"]!="floating" or b["y"]>-55]
            # In Webcam + EMG mode, keep the game and camera controls active
            # while the sensor is disconnected, but require a fresh complete
            # EMG feature window before a fist can trigger a balloon pop.
            closed=full_fist and (mode!="live" or sensor_ready)
            if closed and not was_closed and now-last_action>250:
                hit=next((b for b in balloons if b["state"]=="floating" and math.hypot(b["x"]-x,b["y"]-player_y)<b["radius"]+16),None)
                if hit:
                    hit["state"]="expanding"; hit["hit_at"]=now
                    self.log("Hand_Close"); self.target_set("Hand_Close"); last_action=now
                    bursts.append({"x":hit["x"],"y":hit["y"],"color":hit["color"],"created":now,"duration":430})
                    if pop_sound is not None: pop_sound.play()
            was_closed=closed

            for balloon in list(balloons):
                if balloon["state"]=="expanding" and now-balloon["hit_at"]>=180:
                    balloons.remove(balloon)
                    for _ in range(14):
                        angle=random.uniform(0,math.tau); velocity=random.uniform(2.0,6.0)
                        fragments.append({"x":float(balloon["x"]),"y":float(balloon["y"]),"vx":math.cos(angle)*velocity,"vy":math.sin(angle)*velocity-1.5,"color":balloon["color"],"size":random.randint(4,9),"life":520})
            for piece in fragments:
                piece["x"]+=piece["vx"]; piece["y"]+=piece["vy"]; piece["vy"]+=.14; piece["life"]-=clock.get_time()
            fragments=[piece for piece in fragments if piece["life"]>0]
            bursts=[burst for burst in bursts if now-burst["created"]<burst["duration"]]

            self.draw_camera_background((19,30,59))
            for balloon in balloons:
                radius=balloon["radius"]
                if balloon["state"]=="expanding":
                    progress=min(1.0,(now-balloon["hit_at"])/180)
                    radius=round(radius*(1+.65*progress))
                draw_balloon(self.screen,balloon["x"],round(balloon["y"]),balloon["color"],radius,now)
            for burst in bursts:
                progress=(now-burst["created"])/burst["duration"]
                ring_radius=12+int(progress*62)
                pygame.draw.circle(self.screen,(*burst["color"],max(0,220-int(progress*220))),(int(burst["x"]),int(burst["y"])),ring_radius,3)
            for piece in fragments:
                pygame.draw.circle(self.screen,piece["color"],(int(piece["x"]),int(piece["y"])),piece["size"])
            cursor_color=(255,224,70) if not closed else (255,110,90)
            pygame.draw.circle(self.screen,cursor_color,(x,player_y),17,3 if pointer is not None else 0)
            self.hud()
            if mode=="live" and not sensor_ready:
                self.text("Aim with your hand; balloon pop is disabled until fresh EMG data arrives",(15,48),(255,220,110),22)
            else:
                self.text("Close all five fingers into a fist on a balloon to pop | Move index finger to aim",(15,48),(245,245,235),22)
            if emg_level is not None:
                self.text(f"EMG activity features: RMS {self.emg_rms:.1f} | MAV {self.emg_mav:.1f}",(15,76),(210,245,225),21)
            elif mode=="live":
                self.text("EMG activity: sensor unavailable",(15,76),(255,210,130),21)
            pygame.display.flip();clock.tick(30)
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:self.running=False
        self.save_session()
