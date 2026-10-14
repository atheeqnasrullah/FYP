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


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


@lru_cache(maxsize=2)
def _sky(width, height):
    """Daytime sky with sun and rolling hills, used when no camera picture is shown."""
    sky = pygame.Surface((width, height))
    for y in range(height):
        sky.fill(_lerp((70, 140, 222), (196, 232, 250), y / height), (0, y, width, 1))
    for r, a in ((90, 28), (64, 55), (44, 255)):
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 240, 170, a), (r, r), r)
        sky.blit(glow, (width - 140 - r, 150 - r))
    far = [(0, height), (0, height - 120)] + [(x, height - 120 - 40 * math.sin(x / 140) - 18 * math.sin(x / 47)) for x in range(0, width + 20, 20)] + [(width, height)]
    pygame.draw.polygon(sky, (118, 186, 132), far)
    near = [(0, height), (0, height - 60)] + [(x, height - 64 - 26 * math.sin(x / 95 + 1.3)) for x in range(0, width + 20, 20)] + [(width, height)]
    pygame.draw.polygon(sky, (86, 160, 98), near)
    return sky


@lru_cache(maxsize=2)
def _tint(width, height):
    """Soft sky-coloured wash over the camera picture so the game keeps its look."""
    tint = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        t = y / height
        tint.fill((*_lerp((40, 90, 170), (120, 190, 230), t), 120), (0, y, width, 1))
    return tint


def draw_cloud(surface, x, y, size, alpha=235):
    cloud = pygame.Surface((size * 5, size * 3), pygame.SRCALPHA)
    for dx, dy, r in ((size * 1.2, size * 1.8, size), (size * 2.3, size * 1.3, size * 1.25), (size * 3.5, size * 1.8, size * .95), (size * 2.4, size * 2.1, size)):
        pygame.draw.circle(cloud, (255, 255, 255, alpha), (int(dx), int(dy)), int(r))
    surface.blit(cloud, (int(x), int(y)))


def draw_hand(surface, x, y, closed, color, scale=1.35):
    """Cursor shaped like the gesture: an open hand or a fist (drawn at 2x, then scaled)."""
    k = 2
    size = int(64 * scale)
    icon = pygame.Surface((64 * k, 64 * k), pygame.SRCALPHA)
    cx, cy = 32 * k, 36 * k
    outline = (40, 30, 20)
    def rect(r, col, radius):
        pygame.draw.rect(icon, col, [v * k for v in r], border_radius=radius * k)
    if closed:
        rect((cx / k - 19, cy / k - 15, 38, 32), outline, 12)
        rect((cx / k - 17, cy / k - 13, 34, 28), color, 10)
        for i in range(1, 4):
            xx = cx + (-17 + i * 8.5) * k
            pygame.draw.line(icon, _lerp(color, outline, .45), (xx, cy - 11 * k), (xx, cy - 2 * k), 2 * k)
        pygame.draw.ellipse(icon, outline, (cx - 25 * k, cy - 4 * k, 16 * k, 20 * k))
        pygame.draw.ellipse(icon, color, (cx - 23 * k, cy - 2 * k, 12 * k, 16 * k))
    else:
        for dx, length in ((-12, 18), (-4, 23), (4, 24), (12, 20)):
            r = (cx / k + dx - 4, cy / k - 8 - length, 8, length + 8)
            rect((r[0] - 2, r[1] - 2, r[2] + 4, r[3] + 4), outline, 5)
            rect(r, color, 4)
        thumb = [(cx - 12 * k, cy + 6 * k), (cx - 29 * k, cy - 8 * k), (cx - 23 * k, cy - 15 * k), (cx - 7 * k, cy - 2 * k)]
        pygame.draw.polygon(icon, color, thumb)
        pygame.draw.polygon(icon, outline, thumb, 2 * k)
        rect((cx / k - 19, cy / k - 12, 38, 32), outline, 12)
        rect((cx / k - 17, cy / k - 10, 34, 28), color, 11)
    icon = pygame.transform.smoothscale(icon, (size, size))
    surface.blit(icon, (x - size // 2, y - int(size * 36 / 64)))


def draw_dashed_ring(surface, center, radius, color, now):
    segments = 18
    offset = now / 900
    for k in range(segments):
        a0 = offset + k * math.tau / segments
        pygame.draw.arc(surface, color, (center[0] - radius, center[1] - radius, radius * 2, radius * 2), a0, a0 + math.tau / segments * .55, 2)


class BalloonPop(BaseGame):
    name="Balloon_Pop"

    how_to_play=(
        "Move your hand to aim. The balloon you can pop starts to glow.",
        "Close all five fingers into a fist to pop it.",
        "Open your hand again before the next pop.",
        "Golden balloons give a bonus.",
        "Balloons that float away count as misses.",
    )

    GOLD_EVERY = 7   # every n-th balloon is a golden bonus balloon

    def prompt_text(self):
        return {"reopen": "Open your hand again", "ready": "Make a fist now!", "aim": "Move to a balloon"}.get(getattr(self, "state", "aim"), "")

    def reach_gain(self):
        """Easier levels amplify hand movement so the screen edges need less reach."""
        return self.difficulty.value(1.6, 1.0)

    def run(self):
        clock=pygame.time.Clock(); x=self.W//2; player_y=self.H//2; balloons=[]; fragments=[]; bursts=[]; scores=[]; last_spawn=0; last_action=0; was_closed=False
        palette=((235,70,95),(70,165,245),(255,150,60),(165,105,230),(70,205,155))
        clouds=[[random.uniform(0,self.W),random.uniform(90,320),random.uniform(14,24),random.uniform(.15,.4)] for _ in range(5)]
        popped=missed=spawned=0; self.state="aim"
        self.target_set("Hand_Close")
        self.begin()
        while self.running:
            self.read_input()
            if not self.running: break
            mode=getattr(self,"control_mode","keyboard")
            pointer=None; emg_level=None; emg_features=None; full_fist=False; frame_available=False
            sensor_ready=False
            if mode in ("vision","live"):
                from src.realtime.pipeline import latest, lock, emg_is_ready
                with lock:
                    pointer=latest.get("pointer")
                    emg_level=latest.get("emg_level")
                    emg_features=latest.get("emg_features")
                    full_fist=bool(latest.get("fist",False))
                    frame_available=latest.get("frame") is not None
                sensor_ready=emg_is_ready()
                # The balloon action is intentionally stricter than the generic
                # Hand_Close label: require a stable, complete five-finger fist.
                self.cmd="Hand_Close" if full_fist else "Rest"
            else:
                full_fist=self.cmd=="Hand_Close"  # keyboard C / simulator Hand_Close
            self.emg_rms=float((emg_features or {}).get("RMS",emg_level or 0.0))
            self.emg_mav=float((emg_features or {}).get("MAV",0.0))
            if pointer is not None:
                gain=self.reach_gain()
                x=max(24,min(self.W-24,int((.5+(pointer[0]-.5)*gain)*self.W)))
                player_y=max(90,min(self.H-50,int((.5+(pointer[1]-.5)*gain)*self.H)))
            else:
                step=9
                if self.cmd=="Left":x-=step
                if self.cmd=="Right":x+=step
                if self.cmd=="Up":player_y-=step
                if self.cmd=="Down":player_y+=step
                x=max(24,min(self.W-24,x)); player_y=max(90,min(self.H-50,player_y))
            now=pygame.time.get_ticks()
            # Difficulty sets how often balloons appear, how fast they rise,
            # how big they are and how far the fist may land from them.
            spawn_ms=self.difficulty.value(1700,800)
            speed=self.difficulty.value(1.2,2.8)
            radius=round(self.difficulty.value(54,38))
            reach=self.difficulty.value(30,12)
            if now-last_spawn>spawn_ms:
                spawned+=1
                golden=spawned%self.GOLD_EVERY==0
                # Keep new balloons apart so they do not overlap.
                lane_x=random.randint(72,self.W-72)
                for _ in range(6):
                    if all(abs(lane_x-b["x"])>2*radius or b["y"]<self.H-120 for b in balloons): break
                    lane_x=random.randint(72,self.W-72)
                balloons.append({"x":lane_x,"y":self.H+52,"color":(255,200,40) if golden else random.choice(palette),"golden":golden,"radius":random.randint(radius-4,radius+4),"speed":random.uniform(speed-.3,speed+.3)*(1.15 if golden else 1),"state":"floating","hit_at":0,"phase":random.uniform(0,math.tau)})
                last_spawn=now
            for balloon in balloons:
                if balloon["state"]=="floating":
                    balloon["y"]-=balloon["speed"]
            escaped=[b for b in balloons if b["state"]=="floating" and b["y"]<=-55]
            for balloon in escaped:
                balloons.remove(balloon); missed+=1
                self.log("Missed"); self.target_set("Hand_Close")
                self.popup("Missed one",(255,170,150),28,(balloon["x"],105))

            def drift(b):
                return b["x"]+math.sin(now/700+b["phase"])*6
            floating=[b for b in balloons if b["state"]=="floating"]
            in_reach=min(floating,key=lambda b:math.hypot(drift(b)-x,b["y"]-player_y),default=None)
            if in_reach is not None and math.hypot(drift(in_reach)-x,in_reach["y"]-player_y)>in_reach["radius"]+reach:
                in_reach=None
            # In Webcam + EMG mode, keep the game and camera controls active
            # while the sensor is disconnected, but require a fresh complete
            # EMG feature window before a fist can trigger a balloon pop.
            closed=full_fist and (mode!="live" or sensor_ready)
            if closed and not was_closed and now-last_action>250 and in_reach is not None:
                hit=in_reach
                hit["state"]="expanding"; hit["hit_at"]=now; hit["x"]=drift(hit)
                self.log("Hand_Close"); self.target_set("Hand_Close"); last_action=now; popped+=1
                bonus=20 if hit["golden"] else 0
                self.score+=bonus
                scores.append({"x":hit["x"],"y":hit["y"],"text":f"+{10+bonus+(5 if self.streak>=3 else 0)}","color":(255,214,92) if hit["golden"] else (255,255,255),"born":now})
                bursts.append({"x":hit["x"],"y":hit["y"],"color":hit["color"],"created":now,"duration":430})
                self.sound("chest" if hit["golden"] else "pop")
                if hit["golden"]: self.popup("Golden balloon! +20 bonus",(255,214,92),36)
            was_closed=closed
            self.state="reopen" if closed and now-last_action<1500 and last_action else ("ready" if in_reach is not None else "aim")

            for balloon in list(balloons):
                if balloon["state"]=="expanding" and now-balloon["hit_at"]>=160:
                    balloons.remove(balloon)
                    for _ in range(18):
                        angle=random.uniform(0,math.tau); velocity=random.uniform(2.0,6.5)
                        fragments.append({"x":float(balloon["x"]),"y":float(balloon["y"]),"vx":math.cos(angle)*velocity,"vy":math.sin(angle)*velocity-1.5,"color":balloon["color"] if random.random()<.6 else random.choice(palette),"size":random.randint(3,8),"life":620,"spin":random.uniform(0,math.tau)})
            for piece in fragments:
                piece["x"]+=piece["vx"]; piece["y"]+=piece["vy"]; piece["vy"]+=.16; piece["vx"]*=.98; piece["life"]-=clock.get_time(); piece["spin"]+=.3
            fragments=[piece for piece in fragments if piece["life"]>0]
            bursts=[burst for burst in bursts if now-burst["created"]<burst["duration"]]
            scores=[t for t in scores if now-t["born"]<900]

            # ---------------- draw
            if frame_available:
                self.draw_camera_background((19,30,59),overlay_alpha=40)
                self.screen.blit(_tint(self.W,self.H),(0,0))
            else:
                self.screen.blit(_sky(self.W,self.H),(0,0))
            for cloud in clouds:
                cloud[0]=(cloud[0]+cloud[3])%(self.W+160)
                draw_cloud(self.screen,cloud[0]-160,cloud[1],cloud[2],150 if frame_available else 235)
            for balloon in balloons:
                radius=balloon["radius"]; bx=balloon["x"] if balloon["state"]!="floating" else drift(balloon)
                if balloon["state"]=="expanding":
                    progress=min(1.0,(now-balloon["hit_at"])/160)
                    radius=round(radius*(1+.6*progress))
                if balloon is in_reach:
                    glow=pygame.Surface((radius*3,radius*3),pygame.SRCALPHA)
                    pulse=int(70+40*math.sin(now/120))
                    pygame.draw.ellipse(glow,(255,255,210,pulse),(radius*.35,radius*.25,radius*2.3,radius*2.5))
                    self.screen.blit(glow,(bx-radius*1.5,balloon["y"]-radius*1.5))
                draw_balloon(self.screen,round(bx),round(balloon["y"]),balloon["color"],radius,now)
                if balloon["golden"] and balloon["state"]=="floating":
                    for k in range(3):
                        a=now/300+k*math.tau/3
                        pygame.draw.circle(self.screen,(255,250,200),(int(bx+math.cos(a)*(radius+10)),int(balloon["y"]+math.sin(a)*(radius+10))),3)
            for burst in bursts:
                progress=(now-burst["created"])/burst["duration"]
                ring_radius=12+int(progress*70)
                ring=pygame.Surface((ring_radius*2+8,ring_radius*2+8),pygame.SRCALPHA)
                pygame.draw.circle(ring,(*burst["color"],max(0,230-int(progress*230))),(ring_radius+4,ring_radius+4),ring_radius,4)
                self.screen.blit(ring,(int(burst["x"])-ring_radius-4,int(burst["y"])-ring_radius-4))
            for piece in fragments:
                w=piece["size"]; h=max(2,int(w*abs(math.cos(piece["spin"]))))
                pygame.draw.rect(self.screen,piece["color"],(int(piece["x"]-w/2),int(piece["y"]-h/2),w,h),border_radius=2)
            for t in scores:
                age=(now-t["born"])/900
                self.text(t["text"],(int(t["x"]),int(t["y"]-40-age*60)),t["color"],40,center=True,alpha=int(255*(1-age)))

            # Cursor: reach ring, hand icon and a short label telling the patient what to do.
            hand_color=(255,120,96) if closed else (255,226,110)
            draw_dashed_ring(self.screen,(x,player_y),int(reach+30),(255,255,255) if in_reach is None else (120,255,170),now)
            draw_hand(self.screen,x,player_y,closed,hand_color)
            label={"reopen":"Open your hand","ready":"Make a fist!"}.get(self.state)
            if label:
                font=self.get_font(26); width=font.size(label)[0]+20
                bubble=pygame.Rect(x-width//2,player_y+int(reach+30)+8,width,30)
                bubble.clamp_ip(pygame.Rect(0,64,self.W,self.H-96))
                pygame.draw.rect(self.screen,(255,252,240) if self.state=="ready" else (255,236,200),bubble,border_radius=10)
                pygame.draw.rect(self.screen,(60,140,90) if self.state=="ready" else (200,120,40),bubble,2,border_radius=10)
                self.text(label,bubble.center,(30,60,40) if self.state=="ready" else (110,60,20),26,center=True,shadow=False)

            self.hud()
            lines=[f"Popped {popped}   Missed {missed}"]
            if mode in ("vision","live") and pointer is None:
                lines.append(("Show your hand to the camera",(255,220,110)))
            if mode=="live" and not sensor_ready:
                lines.append(("Aim with your hand; popping is paused until fresh EMG data arrives",(255,220,110)))
            if emg_level is not None:
                lines.append((f"EMG activity: RMS {self.emg_rms:.1f} | MAV {self.emg_mav:.1f}",(210,245,225)))
            elif mode=="live":
                lines.append(("EMG activity: sensor unavailable",(255,210,130)))
            self.info(lines)
            pygame.display.flip();clock.tick(30)
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:self.running=False
        self.save_session()
