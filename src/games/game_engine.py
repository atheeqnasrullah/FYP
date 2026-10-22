import json, math, os, queue, time, sys
from pathlib import Path
import pygame
from src.utils.config import ROOT, load_settings
from src.utils.session_sync import PENDING, upload_session, sync_pending_sessions
from src.realtime.pipeline import latest, lock, status_bus, emg_is_ready
from src.games.audio import SoundBoard
from src.games.difficulty import Difficulty
from src.games.summary import encouragement, friendly, stars, summarize

KEYMAP={pygame.K_LEFT:"Left",pygame.K_RIGHT:"Right",pygame.K_UP:"Up",pygame.K_DOWN:"Down",pygame.K_o:"Hand_Open",pygame.K_c:"Hand_Close",pygame.K_s:"Supination",pygame.K_p:"Pronation",pygame.K_SPACE:"Rest"}
PAUSE_KEYS=(pygame.K_RETURN,pygame.K_KP_ENTER)

# High-contrast palette shared by the HUD and the start/results screens.
INK=(245,247,250); MUTED=(186,198,214); GOLD=(255,214,92); GOOD=(110,231,160); BAD=(255,128,112); PANEL=(10,18,32)

class BaseGame:
    name="Base"
    # Shown on the start screen; games override with their own steps.
    how_to_play=("Follow the movement shown at the top of the screen.",)
    def __init__(self,bus,patient_id="P01",w=900,h=600):
        # Display and fonts only: the mixer is started later by SoundBoard, and only
        # when sound is enabled, because it can block on Windows with no audio device.
        pygame.display.init(); pygame.font.init()
        self.screen=pygame.display.set_mode((w,h),pygame.SHOWN); pygame.display.set_caption(self.name.replace("_"," ")); self.W=w; self.H=h
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.ShowWindow.argtypes = (wintypes.HWND, wintypes.INT)
                user32.BringWindowToTop.argtypes = (wintypes.HWND,)
                user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
                user32.SetWindowPos.argtypes = (
                    wintypes.HWND, wintypes.HWND, wintypes.INT, wintypes.INT,
                    wintypes.INT, wintypes.INT, wintypes.UINT,
                )
                user32.SetWindowPos.restype = wintypes.BOOL
                user32.IsWindowVisible.argtypes = (wintypes.HWND,)
                user32.IsWindowVisible.restype = wintypes.BOOL
                kernel32.GetConsoleWindow.restype = wintypes.HWND
                hwnd = pygame.display.get_wm_info().get("window")
                console_hwnd = kernel32.GetConsoleWindow()
                if console_hwnd:
                    user32.ShowWindow(console_hwnd, 6)  # SW_MINIMIZE
                if hwnd:
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    # Place the game inside the primary screen and above the dashboard/browser.
                    ctypes.set_last_error(0)
                    positioned = user32.SetWindowPos(
                        hwnd, wintypes.HWND(-1), 40, 40, w, h, 0x0040
                    )  # HWND_TOPMOST | SWP_SHOWWINDOW
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    print(
                        "Pygame window activation: "
                        f"positioned={bool(positioned)}, "
                        f"visible={bool(user32.IsWindowVisible(hwnd))}, "
                        f"winerror={ctypes.get_last_error()}",
                        flush=True,
                    )
            except Exception as exc:
                print(f"Pygame window activation warning: {exc}", flush=True)
        self.font=pygame.font.Font(None,30); self.bus=bus; self.patient=patient_id; self.score=0; self.attempts=[]; self.running=True; self.cmd="Rest"; self.started=time.monotonic(); self.target=None; self.target_t=None; self.confidence=0.; self.emg_rms=0.; self.emg_mav=0.
        self.runtime_message=None; self.latencies=[]; self.aborted=False
        cfg=load_settings()
        self.session_seconds=float(cfg.get("game_session_seconds",180) or 0)
        self.difficulty_mode=str(cfg.get("game_difficulty","auto"))
        self.sound_enabled=bool(cfg.get("game_sound",True))
        self.show_screens=bool(cfg.get("game_show_screens",True)) and not os.environ.get("REHAB_SKIP_SCREENS")
        self.difficulty=Difficulty(self.difficulty_mode,patient_id,self.name)
        self.sfx=None; self.popups=[]; self.streak=0; self.best_streak=0; self.time_up=False; self._last_tick_second=None
        self._fonts={}

    # ------------------------------------------------------------ session flow
    def begin(self):
        """Start screen and countdown, then reset the clock so only play time counts."""
        self.difficulty=Difficulty(self.difficulty_mode,self.patient,self.name)
        self.sfx=SoundBoard(self.sound_enabled)
        if self.show_screens:
            self.intro_screen()
            if self.running: self.countdown()
        self.started=time.monotonic()
        if self.target is not None: self.target_t=self.started
        return self.running
    def remaining(self):
        if self.session_seconds<=0: return None
        return max(0.0,self.session_seconds-(time.monotonic()-self.started))
    def sound(self,name):
        if self.sfx is not None: self.sfx.play(name)

    def read_input(self):
        for e in pygame.event.get():
            if e.type==pygame.QUIT: self.running=False
            elif e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: self.running=False
            elif e.type==pygame.KEYDOWN and e.key in PAUSE_KEYS: self.pause()
            elif e.type==pygame.KEYDOWN and e.key==pygame.K_m and self.sfx is not None:
                self.popup("Sound off" if self.sfx.toggle_mute() else "Sound on",MUTED)
            elif e.type==pygame.KEYDOWN and e.key in KEYMAP: self.cmd=KEYMAP[e.key]; self.confidence=1.
            elif e.type==pygame.KEYUP and e.key in KEYMAP: self.cmd="Rest"; self.confidence=0.
        item=None
        try:
            while True:
                item=self.bus.get_nowait(); self.cmd=item.get("command","Rest"); self.confidence=item.get("confidence",0.)
        except queue.Empty: pass
        if item is not None and item.get("vision_ts_ms") is not None:
            self.latencies.append((self.cmd,time.time()*1000-item["vision_ts_ms"]))
        self.check_camera()
        left=self.remaining()
        if left is not None:
            second=math.ceil(left)
            if 0<second<=3 and second!=self._last_tick_second: self.sound("tick")
            self._last_tick_second=second
            if left<=0 and self.running:
                self.time_up=True; self.running=False
    def pause(self):
        """Freeze the game until Enter is pressed again; paused time is not counted."""
        snapshot=self.screen.copy(); paused_at=time.monotonic(); clock=pygame.time.Clock(); waiting=True
        while waiting and self.running:
            for e in pygame.event.get():
                if e.type==pygame.QUIT or (e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE): self.running=False
                elif e.type==pygame.KEYDOWN and e.key in PAUSE_KEYS: waiting=False
            self.screen.blit(snapshot,(0,0)); self.shade(170)
            self.text("Paused",(self.W//2,self.H//2-40),INK,64,center=True)
            self.text("Press Enter to continue   |   Esc to finish the session",(self.W//2,self.H//2+18),MUTED,28,center=True)
            pygame.display.flip(); clock.tick(15)
        gap=time.monotonic()-paused_at
        self.started+=gap
        if self.target_t is not None: self.target_t+=gap
        self.cmd="Rest"

    def check_camera(self):
        """Read pipeline status; if the webcam thread died in a webcam mode, explain it and end the game."""
        try:
            while True: self.runtime_message=status_bus.get_nowait()
        except queue.Empty: pass
        if self.running and getattr(self,"control_mode","keyboard") in ("vision","live") and str(self.runtime_message or "").startswith("_vision"):
            self.camera_error_screen()

    def camera_error_screen(self):
        """Without a camera the patient cannot play, so show why and close without saving a session."""
        detail=str(self.runtime_message).split(": ",1)[-1]
        clock=pygame.time.Clock(); shown=time.monotonic(); close_after=60
        lines=["Close Zoom, Teams, the Camera app or any browser tab using the camera,",
               "and allow camera access in Windows Settings > Privacy > Camera.",
               "If the API was started from an AI assistant or IDE sandbox, start it",
               "again from a normal terminal: python -m uvicorn backend.app:app"]
        while time.monotonic()-shown<close_after:
            if any(e.type==pygame.QUIT or e.type==pygame.KEYDOWN for e in pygame.event.get()): break
            self.screen.fill(PANEL)
            self.text("The webcam could not be opened",(self.W//2,110),BAD,46,center=True)
            self.text(detail[:90],(self.W//2,170),MUTED,22,center=True)
            for i,line in enumerate(lines): self.text(line,(self.W//2,240+i*34),INK,26,center=True)
            self.text(f"Press any key to close   |   closes in {int(close_after-(time.monotonic()-shown))} s",(self.W//2,self.H-70),MUTED,24,center=True)
            pygame.display.flip(); clock.tick(15)
        self.aborted=True; self.running=False

    def wait_for_required_emg(self):
        """Freeze gameplay in Webcam + EMG mode until fresh valid sensor data returns."""
        if getattr(self,"control_mode","keyboard")!="live" or emg_is_ready():
            return
        clock=pygame.time.Clock(); waited_from=time.monotonic()
        while self.running and not emg_is_ready():
            for event in pygame.event.get():
                if event.type==pygame.QUIT or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE):
                    self.running=False
            if not self.running:
                break
            self.draw_camera_background((24,32,48),overlay_alpha=145)
            self.text("Waiting for valid EMG sensor data",(self.W//2,self.H//2-30),GOLD,36,center=True)
            self.text("Check ESP32 connection, COM port, baud rate and CSV output.",(self.W//2,self.H//2+10),INK,25,center=True)
            if self.runtime_message:
                self.text(str(self.runtime_message)[:100],(self.W//2,self.H//2+44),BAD,22,center=True)
            pygame.display.flip(); clock.tick(15)
        # Waiting for the sensor does not use up session time.
        gap=time.monotonic()-waited_from
        self.started+=gap
        if self.target_t is not None: self.target_t+=gap

    # ------------------------------------------------------------ scoring and feedback
    def target_set(self,label): self.target=label; self.target_t=time.monotonic()
    def log(self,detected):
        if self.target is None: return False
        correct=detected==self.target; vision_label=self.cmd if getattr(self,"control_mode","keyboard") in ("vision","live") else None; self.attempts.append({"ts":time.strftime("%Y-%m-%dT%H:%M:%S"),"target_movement":self.target,"detected_movement":detected,"vision_label":vision_label,"correct":correct,"reaction_time_ms":int((time.monotonic()-self.target_t)*1000),"emg_rms":float(self.emg_rms),"emg_mav":float(self.emg_mav),"confidence":float(self.confidence)})
        if correct:
            self.streak+=1; self.best_streak=max(self.best_streak,self.streak)
            self.score+=10+(5 if self.streak>=3 else 0)
            self.sound("success")
            if self.streak in (3,5) or (self.streak>=10 and self.streak%5==0):
                self.popup(f"{self.streak} in a row! Great!",GOLD,size=40)
        else:
            self.streak=0; self.sound("miss")
        self.adapt(correct)
        return correct
    def miss(self,message=None):
        """A failure that is not a movement attempt (e.g. hitting an obstacle)."""
        self.streak=0; self.sound("miss")
        if message: self.popup(message,BAD)
        self.adapt(False)
    def adapt(self,success):
        change=self.difficulty.record(success)
        if change>0: self.popup("Level up! A little faster now",GOOD,size=38); self.sound("level_up")
        elif change<0: self.popup("Let's slow it down a little",MUTED,size=34); self.sound("level_down")
    def popup(self,message,color=INK,size=34,pos=None):
        x,y=pos if pos else (self.W//2,self.H//2-110)
        self.popups.append({"text":message,"color":color,"size":size,"x":x,"y":y,"born":time.monotonic()})
        self.popups=self.popups[-4:]

    # ------------------------------------------------------------ drawing helpers
    def get_font(self,size):
        font=self._fonts.get(size)
        if font is None: font=self._fonts[size]=pygame.font.Font(None,size)
        return font
    def text(self,msg,pos,color=INK,size=None,center=False,shadow=True,alpha=255):
        font=self.get_font(size or 28); surface=font.render(str(msg),True,color)
        x,y=pos
        if center: x-=surface.get_width()//2; y-=surface.get_height()//2
        if shadow:
            back=font.render(str(msg),True,(0,0,0))
            if alpha<255: back.set_alpha(alpha)
            self.screen.blit(back,(x+2,y+2))
        if alpha<255: surface.set_alpha(alpha)
        self.screen.blit(surface,(x,y))
        return surface.get_width()
    def shade(self,alpha):
        overlay=pygame.Surface((self.W,self.H),pygame.SRCALPHA); overlay.fill((0,0,0,alpha)); self.screen.blit(overlay,(0,0))
    def panel(self,rect,alpha=200,color=PANEL,radius=14):
        rect=pygame.Rect(rect); surface=pygame.Surface(rect.size,pygame.SRCALPHA)
        pygame.draw.rect(surface,(*color,alpha),surface.get_rect(),border_radius=radius)
        self.screen.blit(surface,rect.topleft)
    def draw_camera_background(self,fallback=(24,32,48),overlay_alpha=100):
        with lock:
            frame=latest["frame"]
            frame=None if frame is None else frame.copy()
        if frame is None:
            self.screen.fill(fallback)
            return
        import cv2
        import numpy as np
        frame=cv2.resize(frame,(self.W,self.H),interpolation=cv2.INTER_AREA)
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        camera_surface=pygame.surfarray.make_surface(np.transpose(rgb,(1,0,2)))
        self.screen.blit(camera_surface,(0,0))
        shade=pygame.Surface((self.W,self.H),pygame.SRCALPHA)
        shade.fill((0,0,0,overlay_alpha))
        self.screen.blit(shade,(0,0))

    def prompt_text(self):
        """What the patient should do now, shown large at the top of the screen."""
        return friendly(self.target) if self.target else ""
    def controls_hint(self):
        if getattr(self,"control_mode","keyboard") in ("vision","live"):
            return "Move your hand to play   |   Enter pause   |   M sound   |   Esc finish"
        return "Arrows move   O open   C close   |   Enter pause   |   M sound   |   Esc finish"
    def info(self,lines,color=INK,shadow=True):
        """Game-specific status lines, stacked below the top bar."""
        y=74+(28 if self.runtime_message else 0)
        for line in lines:
            if line is None: continue
            text,col=(line if isinstance(line,tuple) else (line,color))
            self.text(text,(16,y),col,24,shadow=shadow); y+=26
        return y
    def hud(self):
        self.panel((0,0,self.W,62),175,radius=0)
        self.text(self.name.replace("_"," "),(16,8),MUTED,24)
        self.text(f"Score {self.score}",(16,30),INK,32)
        prompt=self.prompt_text()
        if prompt:
            font=self.get_font(40); width=font.size(prompt)[0]+40
            self.panel((self.W//2-width//2,7,width,48),235,(48,40,8),radius=12)
            self.text(prompt,(self.W//2,31),GOLD,40,center=True)
        left=self.remaining()
        if left is not None:
            minutes,seconds=divmod(int(math.ceil(left)),60)
            self.text(f"{minutes}:{seconds:02d}",(self.W-16-self.get_font(40).size(f"{minutes}:{seconds:02d}")[0],5),BAD if left<=10 else INK,40)
        level=self.difficulty.label()
        self.text(level,(self.W-16-self.get_font(22).size(level)[0],38),MUTED,22)
        if self.runtime_message:
            message=str(self.runtime_message)
            if len(message)>95: message=message[:92]+"..."
            self.text(f"Input warning: {message}",(16,70),(255,190,90),22)
        self.panel((0,self.H-32,self.W,32),150,radius=0)
        self.text(self.controls_hint(),(self.W//2,self.H-16),MUTED,22,center=True)
        now=time.monotonic(); alive=[]
        for p in self.popups:
            age=now-p["born"]
            if age>1.6: continue
            alive.append(p)
            alpha=int(255*min(1,(1.6-age)/0.5))
            self.text(p["text"],(p["x"],p["y"]-age*30),p["color"],p["size"],center=True,alpha=alpha)
        self.popups=alive

    # ------------------------------------------------------------ start, countdown, results
    def instructions(self):
        return list(self.how_to_play)
    def intro_screen(self):
        clock=pygame.time.Clock(); opened_since=None; shown=time.monotonic(); auto_start=25
        camera=getattr(self,"control_mode","keyboard") in ("vision","live")
        while self.running:
            start=False
            for e in pygame.event.get():
                if e.type==pygame.QUIT or (e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE): self.running=False
                elif (e.type==pygame.KEYDOWN and e.key in (pygame.K_SPACE,*PAUSE_KEYS)) or e.type==pygame.MOUSEBUTTONDOWN: start=True
            hold=0.0
            if camera:
                self.check_camera()
                if not self.running: break
                with lock: visual=latest.get("vis")
                if visual and visual[0]=="Hand_Open":
                    opened_since=opened_since or time.monotonic(); hold=time.monotonic()-opened_since
                    if hold>=1.2: start=True
                else: opened_since=None
            waited=time.monotonic()-shown
            if start or waited>=auto_start: break
            self.draw_camera_background((18,30,52),overlay_alpha=190)
            card=pygame.Rect(90,50,self.W-180,self.H-100)
            self.panel(card,215)
            self.text(self.name.replace("_"," "),(self.W//2,card.y+44),GOLD,58,center=True)
            self.text(f"Patient {self.patient}   |   {self.difficulty.label()}   |   "+(f"{int(self.session_seconds//60)}:{int(self.session_seconds%60):02d} min session" if self.session_seconds>0 else "No time limit"),(self.W//2,card.y+88),MUTED,26,center=True)
            self.text("How to play",(card.x+40,card.y+122),INK,32)
            y=card.y+160
            for i,line in enumerate(self.instructions(),1):
                self.text(f"{i}.  {line}",(card.x+44,y),INK,27); y+=34
            y=card.bottom-118
            if camera:
                self.text("Open your hand and hold it to start",(self.W//2,y),GOOD,34,center=True)
                pygame.draw.rect(self.screen,(60,72,92),(self.W//2-150,y+24,300,12),border_radius=6)
                pygame.draw.rect(self.screen,GOOD,(self.W//2-150,y+24,int(300*min(1,hold/1.2)),12),border_radius=6)
            self.text("or press Space to start",(self.W//2,y+60),MUTED,28,center=True)
            self.text(f"Starts automatically in {int(auto_start-waited)} s   |   Esc to cancel",(self.W//2,y+90),MUTED,22,center=True)
            pygame.display.flip(); clock.tick(30)
    def countdown(self):
        clock=pygame.time.Clock()
        for label in ("3","2","1","Go!"):
            self.sound("go" if label=="Go!" else "tick"); shown=time.monotonic()
            while self.running and time.monotonic()-shown<0.75:
                for e in pygame.event.get():
                    if e.type==pygame.QUIT or (e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE): self.running=False
                progress=(time.monotonic()-shown)/0.75
                self.draw_camera_background((18,30,52),overlay_alpha=150)
                self.text("Get ready",(self.W//2,self.H//2-120),MUTED,36,center=True)
                self.text(label,(self.W//2,self.H//2),GOLD if label!="Go!" else GOOD,int(150+60*progress),center=True,alpha=int(255*(1-progress*0.6)))
                pygame.display.flip(); clock.tick(30)
            if not self.running: return

    def previous_best(self,base):
        try:
            import requests
            rows=requests.get(f"{base}/patients/{self.patient}/sessions",timeout=1.5).json()
            scores=[r["total_score"] for r in rows if r.get("game_name")==self.name]
            return max(scores) if scores else None
        except Exception:
            return None
    def save_session(self):
        if self.aborted:
            print("Session not saved: the webcam could not be opened.",flush=True)
            pygame.quit(); return
        payload={"patient_id":self.patient,"game_name":self.name,"total_score":self.score,"duration_s":int(time.monotonic()-self.started),"attempts":self.attempts}
        cfg=load_settings()
        self.save_latency_log()
        self.difficulty.save()
        base=cfg["backend_url"]; best=None
        if self.show_screens:
            self.draw_camera_background((18,30,52),overlay_alpha=190)
            self.text("Saving session...",(self.W//2,self.H//2),INK,40,center=True); pygame.display.flip()
            best=self.previous_best(base)
        try:
            upload_session(base,payload)
            sync_pending_sessions(base)
            saved="Saved to the patient record"
        except Exception:
            PENDING.parent.mkdir(parents=True,exist_ok=True)
            with PENDING.open("a",encoding="utf-8") as f:f.write(json.dumps(payload)+"\n")
            saved="API not reachable: saved on this computer, it will sync later"
        if self.show_screens and self.attempts is not None:
            self.results_screen(payload,best,saved)
        pygame.quit()
    def results_screen(self,payload,best,saved):
        summary=summarize(self.attempts); count=stars(summary); clock=pygame.time.Clock()
        shown=time.monotonic(); close_after=45; self.sound("finish")
        title="Time's up!" if self.time_up else "Session complete"
        new_best=best is not None and self.score>best
        while True:
            done=False
            for e in pygame.event.get():
                if e.type==pygame.QUIT or (e.type==pygame.KEYDOWN and e.key in (pygame.K_ESCAPE,pygame.K_SPACE,*PAUSE_KEYS)) or e.type==pygame.MOUSEBUTTONDOWN: done=True
            waited=time.monotonic()-shown
            if done or waited>=close_after: break
            self.draw_camera_background((18,30,52),overlay_alpha=200)
            card=pygame.Rect(60,30,self.W-120,self.H-60); self.panel(card,225)
            self.text(title,(self.W//2,card.y+40),GOLD,56,center=True)
            for i in range(3):
                self.star((self.W//2-70+i*70,card.y+100),26,i<count)
            self.text(encouragement(summary),(self.W//2,card.y+142),INK,28,center=True)
            minutes,seconds=divmod(payload["duration_s"],60)
            stats=[("Score",str(self.score)+("  New best!" if new_best else "")),("Accuracy",f"{summary['accuracy']*100:.0f}%" if summary["attempts"] else "-"),
                   ("Good movements",f"{summary['correct']} of {summary['attempts']}"),("Best streak",str(summary["best_streak"])),
                   ("Avg reaction",f"{summary['avg_reaction_ms']/1000:.1f} s" if summary["avg_reaction_ms"] else "-"),("Time played",f"{minutes}:{seconds:02d}"),
                   ("Level",f"{self.difficulty.start_level:.1f} -> {self.difficulty.level:.1f}" if self.difficulty.mode=="auto" else self.difficulty.label())]
            if best is not None and not new_best: stats.append(("Previous best",str(best)))
            x0,y0=card.x+40,card.y+178
            for i,(label,value) in enumerate(stats):
                col,row=i%2,i//2; x=x0+col*260; y=y0+row*48
                self.text(label,(x,y),MUTED,22); self.text(value,(x,y+18),GOOD if "best" in value else INK,30)
            mx,my=card.x+490,card.y+178
            self.text("By movement",(mx,my),MUTED,22); my+=26
            for movement,m in list(summary["movements"].items())[:7]:
                share=m["correct"]/m["total"] if m["total"] else 0
                self.text(friendly(movement)[:16],(mx,my),INK,22)
                pygame.draw.rect(self.screen,(55,66,86),(mx+130,my+3,100,12),border_radius=6)
                pygame.draw.rect(self.screen,GOOD if share>=0.75 else GOLD if share>=0.5 else BAD,(mx+130,my+3,int(100*share),12),border_radius=6)
                self.text(f"{m['correct']}/{m['total']}",(mx+238,my),MUTED,20); my+=24
            self.text(saved,(self.W//2,card.bottom-62),GOOD if saved.startswith("Saved to") else GOLD,24,center=True)
            self.text(f"Press Space to close   |   closes in {int(close_after-waited)} s",(self.W//2,card.bottom-30),MUTED,22,center=True)
            pygame.display.flip(); clock.tick(30)
    def star(self,center,radius,filled):
        cx,cy=center
        points=[(cx+math.cos(-math.pi/2+i*math.pi/5)*(radius if i%2==0 else radius*0.45),cy+math.sin(-math.pi/2+i*math.pi/5)*(radius if i%2==0 else radius*0.45)) for i in range(10)]
        pygame.draw.polygon(self.screen,GOLD if filled else (70,80,98),points)
        pygame.draw.polygon(self.screen,(255,240,180) if filled else (100,110,128),points,2)

    def save_latency_log(self):
        """Write camera-frame-to-game latency samples for src.evaluation.latency_report."""
        if not self.latencies: return
        folder=ROOT/"data/logs"; folder.mkdir(parents=True,exist_ok=True)
        path=folder/f"latency_{self.name}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        with path.open("w",encoding="utf-8") as f:
            f.write("game,mode,command,latency_ms\n")
            for command,latency in self.latencies: f.write(f"{self.name},{getattr(self,'control_mode','keyboard')},{command},{latency:.1f}\n")
