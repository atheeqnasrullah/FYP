import math, random, pygame
from src.games.game_engine import BaseGame
from src.realtime.pipeline import latest, lock

class TreasureHunt(BaseGame):
    name="Treasure_Hunt"
    def run(self):
        clock=pygame.time.Clock(); x=self.W//2; y=self.H-80; treasures=[[random.randint(70,self.W-70),random.randint(130,self.H-80)] for _ in range(5)]; selected=None; rotation=0; last=None
        while self.running:
            self.read_input()
            self.wait_for_required_emg()
            if not self.running: break
            with lock:
                emg_features=latest.get("emg_features")
            self.emg_rms=float((emg_features or {}).get("RMS",0.0))
            self.emg_mav=float((emg_features or {}).get("MAV",0.0))
            if self.cmd=="Left":x-=5
            if self.cmd=="Right":x+=5
            if self.cmd=="Up":y-=5
            if self.cmd=="Down":y+=5
            x=max(25,min(self.W-25,x)); y=max(80,min(self.H-35,y))
            if self.cmd in ("Supination","Pronation") and self.cmd!=last:
                self.target_set(self.cmd);self.log(self.cmd);rotation+=1 if self.cmd=="Supination" else -1
            elif self.cmd=="Hand_Open" and self.cmd!=last:
                self.target_set("Hand_Open");self.log(self.cmd);selected=min(treasures,key=lambda t:math.dist(t,(x,y))) if treasures else None
            elif self.cmd=="Hand_Close" and self.cmd!=last and selected in treasures and rotation%4==0:
                self.target_set("Hand_Close");self.log(self.cmd);treasures.remove(selected);self.score+=20;selected=None
                if not treasures:treasures=[[random.randint(70,self.W-70),random.randint(130,self.H-80)] for _ in range(5)]
            last=self.cmd if self.cmd!="Rest" else None
            self.draw_camera_background((31,48,46))
            for t in treasures: pygame.draw.circle(self.screen,(247,193,45),t,18);pygame.draw.circle(self.screen,(255,235,130),t,7)
            pygame.draw.rect(self.screen,(90,180,185),(x-15,y-20,30,40));
            if selected:pygame.draw.circle(self.screen,(250,230,100),selected,28,3)
            self.text(f"Lock rotation {rotation%4}/4",(15,60),(210,230,220));self.hud()
            if emg_features:
                self.text(f"EMG activity features: RMS {self.emg_rms:.1f} | MAV {self.emg_mav:.1f}",(15,90),(210,245,225),22)
            elif getattr(self,"control_mode","keyboard")=="live":
                self.text("EMG activity sensor unavailable",(15,90),(255,210,130),22)
            pygame.display.flip();clock.tick(30)
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:self.running=False
        self.save_session()
