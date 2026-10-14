import random

import pygame

from src.games.game_engine import BaseGame
from src.realtime.pipeline import latest, lock


class CarDriving(BaseGame):
    name = "Car_Driving"
    HORIZON = 95
    CAR_Y = 475
    LANES = 3
    how_to_play = (
        "Move your hand LEFT or RIGHT to change lane.",
        "Steer the way the sign at the top asks.",
        "Avoid the other cars: change lane before you reach them.",
        "Close your hand to brake.",
    )

    def prompt_text(self):
        return f"Steer {self.target.upper()}" if self.target in ("Left", "Right") else super().prompt_text()

    def controls_hint(self):
        if getattr(self, "control_mode", "keyboard") in ("vision", "live"):
            return "Hand left/right to steer   Close hand to brake   |   Enter pause   |   M sound   |   Esc finish"
        return "Left/Right arrows steer   C brake   |   Enter pause   |   M sound   |   Esc finish"

    def road_half_width(self, y):
        progress = max(0.0, min(1.0, (y - self.HORIZON) / (self.H - self.HORIZON)))
        return 100 + progress * 365

    def lane_x(self, lane, y):
        return self.W / 2 + (lane - 1) * self.road_half_width(y) * (2 / 3)

    def draw_road(self, offset):
        # Sky and rolling hills behind the road.
        pygame.draw.rect(self.screen, (96, 181, 218), (0, 0, self.W, self.HORIZON))
        pygame.draw.circle(self.screen, (255, 225, 142), (self.W-105, 58), 30)
        pygame.draw.polygon(self.screen, (103, 157, 133), [(0, self.HORIZON+4), (0, 82), (105, 48), (205, 91), (312, 57), (445, 99), (575, 52), (700, 93), (812, 54), (self.W, 82), (self.W, self.HORIZON+4)])
        pygame.draw.polygon(self.screen, (70, 135, 100), [(0, self.HORIZON+8), (0, 116), (145, 79), (268, 122), (392, 82), (525, 120), (675, 76), (810, 123), (self.W, 93), (self.W, self.HORIZON+8)])
        pygame.draw.rect(self.screen, (61, 139, 83), (0, self.HORIZON, self.W, self.H - self.HORIZON))
        top_half, bottom_half = self.road_half_width(self.HORIZON), self.road_half_width(self.H)
        center = self.W // 2
        # Wide paved shoulder, edge line, then asphalt road.
        pygame.draw.polygon(self.screen, (183, 174, 145), [(int(center-top_half-10), self.HORIZON), (int(center+top_half+10), self.HORIZON), (int(center+bottom_half+20), self.H), (int(center-bottom_half-20), self.H)])
        pygame.draw.polygon(self.screen, (43, 48, 57), [(int(center-top_half), self.HORIZON), (int(center+top_half), self.HORIZON), (int(center+bottom_half), self.H), (int(center-bottom_half), self.H)])
        pygame.draw.polygon(self.screen, (246, 226, 157), [(int(center-top_half), self.HORIZON), (int(center-top_half+4), self.HORIZON), (int(center-bottom_half+7), self.H), (int(center-bottom_half), self.H)])
        pygame.draw.polygon(self.screen, (246, 226, 157), [(int(center+top_half-4), self.HORIZON), (int(center+top_half), self.HORIZON), (int(center+bottom_half), self.H), (int(center+bottom_half-7), self.H)])

        road_height = self.H - self.HORIZON
        # Perspective lane dashes move toward the player as the car advances.
        dash_cycle = 76
        phase = (offset * 2.2) % dash_cycle
        for boundary in (-1, 1):
            y = self.HORIZON + phase - dash_cycle
            while y < self.H:
                y1, y2 = max(self.HORIZON, y), min(self.H, y + 34)
                if y2 > y1:
                    x1 = center + boundary * self.road_half_width(y1) / 3
                    x2 = center + boundary * self.road_half_width(y2) / 3
                    width1 = max(2, int(1 + (y1-self.HORIZON) / road_height * 6))
                    width2 = max(2, int(1 + (y2-self.HORIZON) / road_height * 6))
                    pygame.draw.polygon(self.screen, (239, 239, 226), [(int(x1-width1), int(y1)), (int(x1+width1), int(y1)), (int(x2+width2), int(y2)), (int(x2-width2), int(y2))])
                y += dash_cycle

        # Small roadside trees provide depth and a visible sense of motion.
        tree_phase = int(offset * 1.5) % 105
        for side in (-1, 1):
            for i in range(7):
                y = self.HORIZON + ((i * 105 + tree_phase) % (self.H - self.HORIZON))
                depth = (y - self.HORIZON) / max(1, self.H - self.HORIZON)
                road_edge = self.road_half_width(y)
                x = int(center + side * (road_edge + 35 + depth * 45))
                size = int(8 + depth * 18)
                trunk_h = max(5, int(size * 1.45))
                pygame.draw.rect(self.screen, (91, 67, 48), (x-size//7, int(y)-trunk_h//3, max(2,size//3), trunk_h))
                pygame.draw.circle(self.screen, (27, 91, 63), (x, int(y)-size), size)
                pygame.draw.circle(self.screen, (42, 119, 73), (x-size//3, int(y)-size-size//5), max(2,size//2))

    def draw_other_car(self, lane, y, color):
        scale = max(.28, min(1.0, (y-self.HORIZON)/(self.CAR_Y-self.HORIZON)))
        width, height = int(48*scale), int(72*scale)
        x = int(self.lane_x(lane, y))
        rect = pygame.Rect(x-width//2, int(y)-height//2, width, height)
        pygame.draw.ellipse(self.screen, (25, 25, 28), (rect.x-4, rect.bottom-height//5, width+8, height//2))
        pygame.draw.rect(self.screen, (25, 27, 31), (rect.x-3, rect.y+height//4, width+6, height//2), border_radius=max(2,int(5*scale)))
        pygame.draw.rect(self.screen, color, rect, border_radius=max(2,int(9*scale)))
        pygame.draw.polygon(self.screen, (135, 199, 215), [(int(rect.x+width*.2),int(rect.y+height*.3)),(int(rect.x+width*.8),int(rect.y+height*.3)),(int(rect.x+width*.68),int(rect.y+height*.58)),(int(rect.x+width*.32),int(rect.y+height*.58))])
        pygame.draw.rect(self.screen, (255, 236, 171), (int(rect.x+width*.12),int(rect.y+height*.12),max(2,int(width*.17)),max(2,int(height*.07))))
        pygame.draw.rect(self.screen, (255, 236, 171), (int(rect.right-width*.29),int(rect.y+height*.12),max(2,int(width*.17)),max(2,int(height*.07))))

    def draw_player_car(self, x, braking):
        y=self.CAR_Y
        pygame.draw.ellipse(self.screen,(18,22,28),(x-53,y+30,106,25))
        # Tires and body shell.
        for tx in (x-41, x+27):
            pygame.draw.rect(self.screen,(20,22,27),(tx,y-12,15,65),border_radius=6)
            pygame.draw.line(self.screen,(104,111,119),(tx+4,y+2),(tx+4,y+36),2)
        body=(201,48,57) if not braking else (230,75,46)
        pygame.draw.polygon(self.screen,(117,28,39),[(x-37,y+39),(x-47,y+4),(x-34,y-31),(x-19,y-51),(x+19,y-51),(x+34,y-31),(x+47,y+4),(x+37,y+39)])
        pygame.draw.polygon(self.screen,body,[(x-32,y+35),(x-41,y+3),(x-29,y-28),(x-16,y-46),(x+16,y-46),(x+29,y-28),(x+41,y+3),(x+32,y+35)])
        pygame.draw.polygon(self.screen,(117,185,204),[(x-25,y-24),(x-12,y-41),(x+12,y-41),(x+25,y-24),(x+21,y-5),(x-21,y-5)])
        pygame.draw.line(self.screen,(211,237,239),(x-11,y-39),(x-17,y-8),2)
        pygame.draw.line(self.screen,(244,157,147),(x-31,y+8),(x-27,y+26),4)
        pygame.draw.line(self.screen,(244,157,147),(x+31,y+8),(x+27,y+26),4)
        pygame.draw.rect(self.screen,(118,32,41),(x-17,y+25,34,8),border_radius=3)
        pygame.draw.line(self.screen,(255,194,116),(x-17,y+32),(x+17,y+32),2)
        if braking:
            pygame.draw.circle(self.screen,(255,45,32),(x-30,y+18),6)
            pygame.draw.circle(self.screen,(255,45,32),(x+30,y+18),6)

    def next_target(self, lane):
        if lane <= 0:
            return "Right"
        if lane >= self.LANES-1:
            return "Left"
        return random.choice(("Left", "Right"))

    def run(self):
        clock=pygame.time.Clock()
        lane=1
        car_x=float(self.lane_x(lane,self.CAR_Y))
        speed=0.0
        max_speed=6.0
        road_offset=0.0
        distance=0.0
        obstacles=[]
        last_spawn=0
        last_steer=None
        steer_cooldown_ms=420
        last_steer_time=-steer_cooldown_ms
        braking=False
        target=self.next_target(lane)
        self.target_set(target)
        emg_peak=1.0
        self.emg_rms=0.0
        collision_until=0
        rendered_frames=0
        self.begin()

        while self.running:
            self.read_input()
            self.wait_for_required_emg()
            if not self.running: break
            with lock:
                visual=latest.get("vis")
                emg_features=latest.get("emg_features")
                emg_level=latest.get("emg_level")
            if getattr(self,"control_mode","keyboard") in ("vision","live"):
                gesture=visual[0] if visual is not None else None
                self.cmd=gesture or "Rest"
            else:
                gesture=self.cmd
            direction=gesture if gesture in ("Left","Right") else None
            braking=gesture=="Hand_Close"
            self.emg_rms=float((emg_features or {}).get("RMS",emg_level or 0.0))
            self.emg_mav=float((emg_features or {}).get("MAV",0.0))
            emg_peak=max(emg_peak,self.emg_rms,1.0)

            # Difficulty sets top speed and how often other cars appear.
            max_speed=self.difficulty.value(4.0,8.0)
            spawn_ms=self.difficulty.value(2100,950)
            if braking:
                speed=0.0
            elif pygame.time.get_ticks() >= collision_until:
                speed=min(max_speed,speed+.025)

            now=pygame.time.get_ticks()
            if direction and direction != last_steer and now-last_steer_time>=steer_cooldown_ms:
                lane=max(0,min(self.LANES-1,lane+(-1 if direction=="Left" else 1)))
                last_steer_time=now
                self.target_set(target)
                self.log(direction)
                if direction==target:
                    target=self.next_target(lane)
                    self.target_set(target)
                else:
                    self.target_set(target)
            last_steer=direction

            if speed>1.0 and now-last_spawn>spawn_ms:
                obstacles.append([random.randrange(self.LANES),float(self.HORIZON+30),random.choice(((75,157,205),(221,165,58),(154,112,187)))])
                last_spawn=now
            road_offset=(road_offset+speed)%62
            distance+=speed/30
            for obstacle in obstacles:
                obstacle[1]+=speed*1.65
            obstacles=[o for o in obstacles if o[1]<self.H+90]

            collision=next((o for o in obstacles if o[0]==lane and self.CAR_Y-27 <= o[1] <= self.CAR_Y+20),None)
            if collision:
                obstacles.remove(collision)
                collision_until=now+900
                speed=0.0
                self.score=max(0,self.score-5)
                self.miss("Crash! Change lane earlier")

            debug_frame=rendered_frames==0
            if debug_frame: print("Car Driving first frame: background",flush=True)
            self.draw_camera_background((35,48,60),overlay_alpha=165)
            if debug_frame: print("Car Driving first frame: road",flush=True)
            self.draw_road(road_offset)
            for obstacle_lane,obstacle_y,color in obstacles:
                self.draw_other_car(obstacle_lane,obstacle_y,color)
            target_x=self.lane_x(lane,self.CAR_Y)
            car_x+=(target_x-car_x)*.22
            if debug_frame: print("Car Driving first frame: car and HUD",flush=True)
            self.draw_player_car(round(car_x),braking)
            self.hud()
            lines=[f"Speed {speed*12:.0f} km/h   Distance {distance:.1f} m"]
            if emg_level is None:
                if getattr(self,"control_mode","keyboard")=="live": lines.append(("EMG activity sensor unavailable",(255,210,130)))
                y=self.info(lines)
            else:
                percent=min(100,int(self.emg_rms/emg_peak*100))
                lines.append((f"EMG RMS {self.emg_rms:.1f}   MAV {self.emg_mav:.1f}   Activity {percent}% of session peak",(210,245,225)))
                y=self.info(lines)
                pygame.draw.rect(self.screen,(36,42,48),(16,y+2,180,12),border_radius=5)
                pygame.draw.rect(self.screen,(57,208,142),(16,y+2,int(180*percent/100),12),border_radius=5)
            if braking:
                self.text("BRAKING",(round(car_x),self.CAR_Y-85),(255,95,75),34,center=True)
            elif now<collision_until:
                self.text("Obstacle hit - steer to another lane",(self.W//2,150),(255,225,125),28,center=True)
            pygame.display.flip()
            if rendered_frames == 0:
                pixels=pygame.surfarray.array3d(self.screen)
                print(f"Car Driving first frame rendered: mean_rgb={pixels.mean(axis=(0,1)).round(1).tolist()}",flush=True)
            rendered_frames+=1
            clock.tick(30)
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:
                self.running=False

        self.save_session()
