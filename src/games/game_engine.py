import json, math, os, queue, time, sys
from pathlib import Path
import pygame
from src.utils.config import ROOT, load_settings
from src.utils.session_sync import PENDING, upload_session, sync_pending_sessions
from src.realtime.pipeline import latest, lock, status_bus, emg_is_ready
from src.games.audio import SoundBoard
from src.games.difficulty import Difficulty
from src.games.levels import LEVEL_COUNT, NAMES, default_level, difficulty_level, goal, goal_text, level_status, opens_text, playable, record_result
from src.games.effort import calibrate, effort_pct, load_calibration, parse_required, required_effort, save_calibration
from src.games.summary import encouragement, friendly, stars, summarize

KEYMAP={pygame.K_LEFT:"Left",pygame.K_RIGHT:"Right",pygame.K_UP:"Up",pygame.K_DOWN:"Down",pygame.K_o:"Hand_Open",pygame.K_c:"Hand_Close",pygame.K_s:"Supination",pygame.K_p:"Pronation",pygame.K_SPACE:"Rest"}
PAUSE_KEYS=(pygame.K_RETURN,pygame.K_KP_ENTER)

SOURCE_NAMES={"keyboard":"Keyboard","sim":"Simulator","vision":"Camera"}


def activity_level(pct):
    """Words for a relative muscle-activity percentage."""
    return "Low" if pct<35 else "Medium" if pct<70 else "High"

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
        # Input feedback: which input drove each action, how confident, and how much muscle activity.
        self.cards=[]; self._emg_peak=0.0; self.emg_source="serial"
        # Grip effort threshold (Webcam + EMG mode): calibrated per patient, see src/games/effort.py.
        self.effort_setting=parse_required(cfg.get("game_effort_required","auto"))
        self.calibrate_each_session=bool(cfg.get("game_emg_calibration",True))
        self.calibration=None; self._grip=self._new_grip()
        # Levels 1-7 (src/games/levels.py): "choose" shows the level panel, "free" is free play, or a level number.
        self.levels_enabled=bool(cfg.get("game_levels",True)); self.level_days=max(0,int(cfg.get("level_days_between",1) or 0))
        self.level_request="choose"; self.level=None; self.level_goal=0; self.level_unit=""; self.goal_reached_at=None; self.level_result=None

    # ------------------------------------------------------------ session flow
    def begin(self):
        """Start screen and countdown, then reset the clock so only play time counts."""
        self.difficulty=Difficulty(self.difficulty_mode,self.patient,self.name)
        self.sfx=SoundBoard(self.sound_enabled)
        choice=self.level_request
        if choice=="choose": choice=self.level_select_screen() if self.show_screens and self.levels_enabled else "free"
        if not self.running: return False
        self.set_level(choice)
        if self.show_screens: self.intro_screen()
        if self.running: self.setup_effort()
        if self.show_screens and self.running: self.countdown()
        self.started=time.monotonic()
        if self.target is not None: self.target_t=self.started
        return self.running
    def set_level(self,choice):
        """Play level 1-7 (fixed difficulty and a goal) or, for "free", free play at the chosen difficulty."""
        if not isinstance(choice,int): return
        self.level=choice; self.level_goal,self.level_unit=goal(self.name,choice)
        self.difficulty=Difficulty(patient=self.patient,game=self.name,level=difficulty_level(choice))
    def level_count(self):
        """Progress toward the level goal; games with another goal (stars, chests) override this."""
        return sum(1 for a in self.attempts if a.get("correct"))
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
        # A level ends shortly after its goal is reached, so the last success can still be seen.
        if self.level and self.running:
            if self.goal_reached_at is None and self.level_count()>=self.level_goal:
                self.goal_reached_at=time.monotonic(); self.popup(f"Level {self.level} complete!",GOOD,size=52); self.sound("level_up")
            elif self.goal_reached_at is not None and time.monotonic()-self.goal_reached_at>=1.6:
                self.running=False
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

    # ------------------------------------------------------------ input feedback
    def input_source(self):
        """Where the movement commands come from, in words for the patient and therapist."""
        mode=getattr(self,"control_mode","keyboard")
        if mode=="live": return "Camera + EMG replay" if getattr(self,"emg_source","serial")=="replay" else "Camera + EMG sensor"
        return SOURCE_NAMES.get(mode,str(mode))
    def emg_activity(self):
        """Muscle effort now, 0-100 (None without EMG).

        With a calibration it is the share of the patient's range from rest to strongest squeeze;
        without one, the share of the strongest reading this session. The MD0437 gives an activity
        envelope, not a calibrated force, so this is relative effort, not a strength measurement."""
        rms=float(self.emg_rms or 0)
        if rms<=0: return None
        if self.calibration: return effort_pct(rms,self.calibration["rest_rms"],self.calibration["max_rms"])
        self._emg_peak=max(self._emg_peak,rms)
        return 100*rms/self._emg_peak
    def input_snapshot(self):
        pct=self.emg_activity()
        return {"source":self.input_source(),"gesture":friendly(self.cmd) if self.cmd else "Rest",
                "confidence":float(self.confidence or 0),"activity":pct,"rms":float(self.emg_rms or 0)}
    def action_card(self,title,pos=None,ok=True,activity=None,need=None):
        """Card at the place of an action showing what triggered it (gesture, input, confidence, effort)."""
        snap=self.input_snapshot()
        if activity is not None: snap["activity"]=activity
        self.cards.append({**snap,"title":title,"ok":ok,"pos":pos,"born":time.monotonic(),"need":need})
        self.cards=self.cards[-3:]

    # ------------------------------------------------------------ grip effort threshold
    def effort_gated(self):
        """Grip actions need a minimum effort only in Webcam + EMG mode; other modes have no EMG."""
        return getattr(self,"control_mode","keyboard")=="live" and self.required_effort()>0
    def required_effort(self):
        return required_effort(self.effort_setting,self.difficulty)
    def effort_ok(self):
        if not self.effort_gated(): return True
        pct=self.emg_activity()
        return pct is not None and pct>=self.required_effort()
    @staticmethod
    def _new_grip(): return {"active":False,"ready":False,"fired":False,"best":0.0,"pos":None}
    def grip(self,closed,ready=True,pos=None):
        """Follow one fist against the effort threshold.

        Returns "fire" once, when a fist that can act (ready) first reaches the required effort,
        and "weak" once, when such a fist opens without reaching it; otherwise None. Outside
        Webcam + EMG mode effort is not measured, so a ready fist fires at once."""
        g=self._grip
        if not closed:
            weak=g["active"] and g["ready"] and not g["fired"]
            self.weak_grip={"best":g["best"],"pos":g["pos"]} if weak else None
            self._grip=self._new_grip()
            return "weak" if weak else None
        g["active"]=True; g["pos"]=pos
        if ready:
            g["ready"]=True; g["best"]=max(g["best"],self.emg_activity() or 0.0)
            if not g["fired"] and self.effort_ok():
                g["fired"]=True; return "fire"
        return None
    def log_weak_grip(self,pos=None):
        """Record a fist that never reached the required effort as a failed attempt."""
        weak=getattr(self,"weak_grip",None) or {"best":0.0,"pos":None}
        best=weak["best"]; need=self.required_effort()
        # The hand has opened by now; record the fist that was attempted.
        cmd=self.cmd; self.cmd="Hand_Close"
        self.log("Weak_Grip",pos=pos or weak["pos"],title=f"Squeeze harder: {best:.0f}% of {need:.0f}%",card=True,effort=best,grip=True)
        self.cmd=cmd

    def setup_effort(self):
        """Webcam + EMG mode: measure the patient's rest and strongest squeeze so effort is relative to them."""
        if getattr(self,"control_mode","keyboard")!="live": return
        if getattr(self,"emg_source","serial")=="replay":
            # A recording cannot follow instructions, so its own Rest and Hand_Close parts stand in.
            try:
                from src.realtime.emg_replay import replay_calibration
                rest,peak=replay_calibration()
                self.calibration={"rest_rms":rest,"max_rms":peak,"source":"replay"}
            except Exception as exc:
                print(f"EMG replay calibration failed ({exc}); effort is relative to the session's strongest reading.",flush=True)
            return
        saved=load_calibration(self.patient)
        if self.show_screens and self.calibrate_each_session:
            result=self.calibration_screen(saved)
            if result: saved=save_calibration(self.patient,*result,"sensor")
        self.calibration=saved
        if saved is None: print("No EMG calibration for this patient; effort is relative to the session's strongest reading.",flush=True)
    def calibration_screen(self,saved):
        """Two short steps, relax then squeeze. Returns (rest_rms, max_rms), or None if skipped or no squeeze was seen."""
        clock=pygame.time.Clock()
        steps=(("rest","Relax your hand","Rest your arm on the table and let your hand go loose."),
               ("squeeze","Now squeeze!","Make a fist as hard as you comfortably can, and hold it."))
        for attempt in range(2):
            values={"rest":[],"squeeze":[]}
            for number,(key,title,detail) in enumerate(steps,1):
                shown=time.monotonic(); seconds=3.0
                while self.running and time.monotonic()-shown<seconds:
                    for e in pygame.event.get():
                        if e.type==pygame.QUIT or (e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE): self.running=False
                        elif e.type==pygame.KEYDOWN and e.key==pygame.K_s and saved: return None
                    self.wait_for_required_emg()
                    with lock: features=latest.get("emg_features")
                    rms=float((features or {}).get("RMS",0.0)); age=time.monotonic()-shown
                    if age>0.8: values[key].append(rms)   # skip the moment the hand is still changing
                    self.draw_camera_background((18,30,52),overlay_alpha=190)
                    card=pygame.Rect(110,70,self.W-220,self.H-140); self.panel(card,220)
                    self.text(f"Muscle check   |   step {number} of 2",(self.W//2,card.y+36),MUTED,26,center=True)
                    self.text(title,(self.W//2,card.y+100),GOOD if key=="squeeze" else GOLD,62,center=True)
                    self.text(detail,(self.W//2,card.y+156),INK,27,center=True)
                    pygame.draw.rect(self.screen,(60,72,92),(self.W//2-180,card.y+200,360,14),border_radius=7)
                    pygame.draw.rect(self.screen,GOLD,(self.W//2-180,card.y+200,int(360*min(1,age/seconds)),14),border_radius=7)
                    self.text(f"{max(0,seconds-age):.0f} s",(self.W//2+196,card.y+198),MUTED,24)
                    self.text(f"EMG RMS {rms:.0f}",(self.W//2,card.y+246),MUTED,24,center=True)
                    self.text("This sets how strong a grip each game needs, for this patient.",(self.W//2,card.bottom-70),MUTED,22,center=True)
                    self.text(f"S: use the saved check from {saved['date'][:10]}   |   Esc: cancel" if saved else "Esc: cancel",(self.W//2,card.bottom-40),MUTED,22,center=True)
                    pygame.display.flip(); clock.tick(30)
                if not self.running: return None
            result=calibrate(values["rest"],values["squeeze"])
            need=self.required_effort()
            lines=([f"Rest {result[0]:.0f}   |   strongest squeeze {result[1]:.0f} (EMG RMS)",
                    f"A grip counts at {need:.0f}% of your strongest squeeze." if need>0 else "No minimum grip in this session."]
                   if result else ["The squeeze was not stronger than rest.","Check the electrodes, then squeeze again."+("" if attempt==0 else " Using the saved check.")])
            shown=time.monotonic()
            while self.running and time.monotonic()-shown<2.5:
                for e in pygame.event.get():
                    if e.type==pygame.QUIT or (e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE): self.running=False
                self.draw_camera_background((18,30,52),overlay_alpha=190)
                self.panel(pygame.Rect(110,70,self.W-220,self.H-140),220)
                self.text("Muscle check done" if result else "Let's try that again",(self.W//2,self.H//2-60),GOOD if result else GOLD,52,center=True)
                for i,line in enumerate(lines): self.text(line,(self.W//2,self.H//2+i*36),INK,27,center=True)
                pygame.display.flip(); clock.tick(30)
            if result or not self.running: return result
        return None

    # ------------------------------------------------------------ scoring and feedback
    def target_set(self,label): self.target=label; self.target_t=time.monotonic()
    def log(self,detected,pos=None,title=None,card=False,effort=None,grip=False):
        """Record one attempt. card=True also shows an action card at pos (screen x, y).

        grip=True marks a grip action, which records the required effort and whether it was met;
        effort overrides the current effort reading (a weak grip logs its strongest moment)."""
        if self.target is None: return False
        snap=self.input_snapshot()
        if effort is not None: snap["activity"]=effort
        need=self.required_effort() if grip and self.effort_gated() else None
        correct=detected==self.target; vision_label=self.cmd if getattr(self,"control_mode","keyboard") in ("vision","live") else None; self.attempts.append({"ts":time.strftime("%Y-%m-%dT%H:%M:%S"),"target_movement":self.target,"detected_movement":detected,"vision_label":vision_label,"correct":correct,"reaction_time_ms":int((time.monotonic()-self.target_t)*1000),"emg_rms":float(self.emg_rms),"emg_mav":float(self.emg_mav),"confidence":float(self.confidence),
            "input_source":snap["source"],"emg_activity_pct":None if snap["activity"] is None else round(snap["activity"],1),
            "effort_required_pct":None if need is None else round(need,1),"effort_ok":None if need is None or snap["activity"] is None else snap["activity"]>=need})
        if card: self.action_card(title or (friendly(detected) if correct else f"Not this one: {friendly(detected)}"),pos,correct,snap["activity"],need)
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
        level=self.difficulty.label() if not self.level else f"Level {self.level}: {min(self.level_count(),self.level_goal)} of {self.level_goal} {self.level_unit}"
        self.text(level,(self.W-16-self.get_font(22).size(level)[0],38),GOOD if self.goal_reached_at else MUTED,22)
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

    def present(self):
        """Draw the input strip and action cards on top of everything, then show the frame."""
        self.draw_input_strip()
        self.draw_grip_meter()
        self.draw_action_cards()
        pygame.display.flip()

    def draw_activity_bar(self,x,y,width,pct,alpha=255,need=None):
        """Effort bar; with need, a white tick marks the required effort and the bar turns green above it."""
        level=activity_level(pct)
        colour=(GOOD if pct>=need else GOLD) if need is not None else {"Low":MUTED,"Medium":GOLD,"High":GOOD}[level]
        bar=pygame.Surface((width,14),pygame.SRCALPHA)
        pygame.draw.rect(bar,(55,66,86,alpha),(0,2,width,10),border_radius=5)
        pygame.draw.rect(bar,(*colour,alpha),(0,2,max(4,int(width*min(pct,100)/100)),10),border_radius=5)
        if need is not None:
            tick=int(width*min(need,100)/100); pygame.draw.rect(bar,(*INK,alpha),(max(0,tick-1),0,3,14))
        self.screen.blit(bar,(x,y-2))
        return level,colour
    def draw_input_strip(self):
        """Live input status under the top bar: source, detected gesture + confidence, muscle activity."""
        snap=self.input_snapshot(); w,h=380,46
        x,y=self.W-w-10,64+(28 if self.runtime_message else 0)
        self.panel((x,y,w,h),210,radius=10)
        self.text(snap["source"],(x+10,y+6),MUTED,18,shadow=False)
        gesture=snap["gesture"]; conf=snap["confidence"]
        conf_text=f"{conf*100:.0f}%" if conf>0 and getattr(self,"control_mode","keyboard") in ("vision","live") else ""
        right=x+w-10
        if conf_text:
            cw=self.get_font(20).size(conf_text)[0]
            self.text(conf_text,(right-cw,y+5),GOOD if conf>=0.8 else GOLD if conf>=0.6 else BAD,20,shadow=False); right-=cw+8
        gw=self.get_font(22).size(gesture)[0]
        self.text(gesture,(right-gw,y+3),INK,22,shadow=False)
        if snap["activity"] is None:
            if getattr(self,"control_mode","keyboard")=="live":
                self.text("Muscle activity: EMG sensor not sending data",(x+10,y+27),BAD,17,shadow=False)
            else:
                self.text("Muscle activity: no EMG sensor in this mode",(x+10,y+27),MUTED,17,shadow=False)
        elif self.effort_gated():
            need=self.required_effort()
            self.text("Grip effort",(x+10,y+27),MUTED,17,shadow=False)
            _,colour=self.draw_activity_bar(x+118,y+31,130,snap["activity"],need=need)
            self.text(f"{snap['activity']:.0f}% / need {need:.0f}%",(x+256,y+27),colour,18,shadow=False)
        else:
            self.text("Muscle activity",(x+10,y+27),MUTED,17,shadow=False)
            level,colour=self.draw_activity_bar(x+118,y+31,130,snap["activity"])
            self.text(f"{snap['activity']:.0f}% {level}",(x+256,y+27),colour,18,shadow=False)
            rms=f"RMS {snap['rms']:.0f}"
            self.text(rms,(x+w-10-self.get_font(16).size(rms)[0],y+28),MUTED,16,shadow=False)
    def draw_action_cards(self):
        """Cards that appear where an action happened (for example a balloon popping) and fade out."""
        now=time.monotonic(); alive=[]; life=2.2
        for c in self.cards:
            age=now-c["born"]
            if age>life: continue
            alive.append(c)
            alpha=int(255*min(1,(life-age)/0.6))
            w,h=270,72
            px,py=c["pos"] or (self.W//2,self.H//2)
            rise=age*12
            # Above the action point when there is room under the top bar, otherwise below it.
            y=py-h-40-rise if py-h-40>=118 else py+40-rise
            x=int(min(max(px-w//2,10),self.W-w-10)); y=int(min(max(y,118),self.H-h-40))
            card=pygame.Surface((w,h),pygame.SRCALPHA)
            pygame.draw.rect(card,(*PANEL,int(230*alpha/255)),card.get_rect(),border_radius=12)
            pygame.draw.rect(card,(*(GOOD if c["ok"] else BAD),alpha),card.get_rect(),width=3,border_radius=12)
            self.screen.blit(card,(x,y))
            self.text(c["title"],(x+12,y+7),GOOD if c["ok"] else BAD,24,shadow=False,alpha=alpha)
            how=f"{c['gesture']}  |  {c['source']}"
            if c["confidence"]>0 and c["source"].startswith("Camera"): how+=f" {c['confidence']*100:.0f}%"
            self.text(how,(x+12,y+31),INK,18,shadow=False,alpha=alpha)
            if c["activity"] is None:
                self.text("Muscle activity: no EMG sensor",(x+12,y+51),MUTED,17,shadow=False,alpha=alpha)
            elif c.get("need") is not None:
                self.text("Grip effort",(x+12,y+51),MUTED,17,shadow=False,alpha=alpha)
                _,colour=self.draw_activity_bar(x+112,y+55,90,c["activity"],alpha,need=c["need"])
                self.text(f"{c['activity']:.0f}% / {c['need']:.0f}%",(x+208,y+51),colour,17,shadow=False,alpha=alpha)
            else:
                self.text("Muscle activity",(x+12,y+51),MUTED,17,shadow=False,alpha=alpha)
                level,colour=self.draw_activity_bar(x+112,y+55,90,c["activity"],alpha)
                self.text(f"{c['activity']:.0f}% {level}",(x+208,y+51),colour,17,shadow=False,alpha=alpha)
        self.cards=alive
    def draw_grip_meter(self):
        """While a fist is held but not yet strong enough, a small meter under the hand says so."""
        g=self._grip
        if not (g["active"] and g["ready"] and not g["fired"] and g["pos"] and self.effort_gated()): return
        pct=self.emg_activity() or 0.0; need=self.required_effort()
        x,y=int(g["pos"][0]),int(g["pos"][1])
        # Under the hand, or above it when the hand is near the bottom of the screen.
        y=y+58 if y+58+40<=self.H-36 else y-58-40
        x=min(max(x-80,10),self.W-170); y=max(y,118)
        self.panel((x,y,160,40),215,radius=9)
        self.text("Squeeze harder",(x+80,y+11),GOLD,21,center=True,shadow=False)
        self.draw_activity_bar(x+10,y+25,140,pct,need=need)

    # ------------------------------------------------------------ start, countdown, results
    def instructions(self):
        return list(self.how_to_play)
    def intro_screen(self):
        clock=pygame.time.Clock(); opened_since=None; shown=time.monotonic(); auto_start=25; armed=False
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
                # The hand must leave the open pose once first, so the hold that picked a level does not also start.
                if visual and visual[0]=="Hand_Open" and armed:
                    opened_since=opened_since or time.monotonic(); hold=time.monotonic()-opened_since
                    if hold>=1.2: start=True
                else: opened_since=None; armed=armed or not (visual and visual[0]=="Hand_Open")
            waited=time.monotonic()-shown
            if start or waited>=auto_start: break
            self.draw_camera_background((18,30,52),overlay_alpha=190)
            card=pygame.Rect(90,50,self.W-180,self.H-100)
            self.panel(card,215)
            self.text(self.name.replace("_"," "),(self.W//2,card.y+44),GOLD,58,center=True)
            self.text(f"Patient {self.patient}   |   {f'Level {self.level}: {NAMES[self.level-1]}' if self.level else 'Free play, '+self.difficulty.label()}   |   "+(f"{int(self.session_seconds//60)}:{int(self.session_seconds%60):02d} min session" if self.session_seconds>0 else "No time limit"),(self.W//2,card.y+88),MUTED,26,center=True)
            if self.level: self.text(f"Goal: {goal_text(self.name,self.level)}",(card.x+40,card.y+122),GOLD,32)
            else: self.text("How to play",(card.x+40,card.y+122),INK,32)
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
        if self.level:
            count=self.level_count(); passed=count>=self.level_goal
            self.level_result={"count":count,"passed":passed,"stars":stars(summarize(self.attempts)) if passed else 0}
            try: record_result(self.patient,self.name,self.level,count,passed,self.level_result["stars"])
            except OSError as exc: print(f"Level progress not saved: {exc}",flush=True)
        payload={"patient_id":self.patient,"game_name":self.name,"total_score":self.score,"duration_s":int(time.monotonic()-self.started),"attempts":self.attempts,
                 "level":self.level,"level_passed":None if not self.level else self.level_result["passed"]}
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
        message=encouragement(summary)
        if self.level:
            title,message=self.level_message()
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
            self.text(message,(self.W//2,card.y+142),GOOD if self.level and self.level_result["passed"] else INK,28,center=True)
            minutes,seconds=divmod(payload["duration_s"],60)
            stats=[("Score",str(self.score)+("  New best!" if new_best else "")),("Accuracy",f"{summary['accuracy']*100:.0f}%" if summary["attempts"] else "-"),
                   ("Good movements",f"{summary['correct']} of {summary['attempts']}"),("Best streak",str(summary["best_streak"])),
                   ("Avg reaction",f"{summary['avg_reaction_ms']/1000:.1f} s" if summary["avg_reaction_ms"] else "-"),("Time played",f"{minutes}:{seconds:02d}"),
                   ("Level",f"{self.level}: {NAMES[self.level-1]}" if self.level else f"{self.difficulty.start_level:.1f} -> {self.difficulty.level:.1f}" if self.difficulty.mode=="auto" else self.difficulty.label())]
            if best is not None and not new_best: stats.append(("Previous best",str(best)))
            effort=[a["emg_activity_pct"] for a in self.attempts if a.get("correct") and a.get("emg_activity_pct") is not None]
            if effort: stats.append(("Avg muscle activity",f"{sum(effort)/len(effort):.0f}% ({activity_level(sum(effort)/len(effort))})"))
            grips=[a for a in self.attempts if a.get("effort_ok") is not None]
            if grips: stats.append(("Strong grips",f"{sum(a['effort_ok'] for a in grips)} of {len(grips)} (need {grips[-1]['effort_required_pct']:.0f}%)"))
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
    def level_message(self):
        """Results title and line for a level: passed or not, and when the next level opens."""
        n=self.level; r=self.level_result
        if not r["passed"]:
            again=f" to open level {n+1}" if n<LEVEL_COUNT else ""
            return (f"Level {n}: {r['count']} of {self.level_goal}",f"{r['count']} of {self.level_goal} {self.level_unit}. Try level {n} again{again}!")
        if n==LEVEL_COUNT: return (f"Level {n} complete!",f"All {LEVEL_COUNT} levels done. Amazing work!")
        nxt=level_status(self.patient,self.name,days_between=self.level_days)[n]
        if nxt["state"]=="waiting": return (f"Level {n} complete!",f"Level {n+1} opens {opens_text(nxt['opens_on'])}. See you then!")
        return (f"Level {n} complete!",f"Level {n+1} is open: play it next!")

    # ------------------------------------------------------------ level panel
    def level_select_screen(self):
        """Panel of the seven levels plus free play. Returns a level number, "free", or None if cancelled.

        Arrows, number keys or the mouse pick a card and Enter/Space or a click starts it; with the camera,
        move the hand over a card and hold it open. Locked cards say what opens them."""
        rows=level_status(self.patient,self.name,days_between=self.level_days)
        options=[*rows,{"level":"free","name":"Free play","state":"free"}]
        sel=default_level(rows)-1
        clock=pygame.time.Clock(); shown=time.monotonic(); auto_pick=45; hold_since=None; note=None; armed=False
        camera=getattr(self,"control_mode","keyboard") in ("vision","live")
        cw,ch,gap=190,150,16; x0=(self.W-(4*cw+3*gap))//2; y0=150
        rects=[pygame.Rect(x0+(i%4)*(cw+gap),y0+(i//4)*(ch+gap),cw,ch) for i in range(len(options))]
        def choose(i):
            nonlocal note
            row=options[i]
            if row["state"]=="free": return "free"
            if playable(row): return row["level"]
            note=(f"Level {row['level']} opens {opens_text(row['opens_on'])}" if row["state"]=="waiting"
                  else f"Pass level {row['level']-1} first to open level {row['level']}",time.monotonic())
            self.sound("miss"); return None
        while self.running:
            picked=None
            for e in pygame.event.get():
                if e.type==pygame.QUIT or (e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE): self.running=False
                elif e.type==pygame.KEYDOWN:
                    if e.key==pygame.K_LEFT: sel=(sel-1)%len(options)
                    elif e.key==pygame.K_RIGHT: sel=(sel+1)%len(options)
                    elif e.key in (pygame.K_UP,pygame.K_DOWN): sel=(sel+4)%len(options)
                    elif pygame.K_1<=e.key<=pygame.K_7: sel=e.key-pygame.K_1
                    elif e.key==pygame.K_f: sel=len(options)-1
                    elif e.key in (pygame.K_SPACE,*PAUSE_KEYS): picked=choose(sel)
                elif e.type==pygame.MOUSEMOTION or e.type==pygame.MOUSEBUTTONDOWN:
                    hit=next((i for i,r in enumerate(rects) if r.collidepoint(e.pos)),None)
                    if hit is not None:
                        sel=hit
                        if e.type==pygame.MOUSEBUTTONDOWN: picked=choose(hit)
            hold=0.0
            if camera:
                self.check_camera()
                if not self.running: break
                with lock: pointer=latest.get("pointer"); visual=latest.get("vis")
                if pointer is not None:
                    hit=next((i for i,r in enumerate(rects) if r.collidepoint(int(pointer[0]*self.W),int(pointer[1]*self.H))),None)
                    if hit is not None and hit!=sel: sel=hit; hold_since=None
                if visual and visual[0]=="Hand_Open" and armed:
                    hold_since=hold_since or time.monotonic(); hold=time.monotonic()-hold_since
                    if hold>=1.5: picked=choose(sel); hold_since=None; armed=False
                else: hold_since=None; armed=armed or not (visual and visual[0]=="Hand_Open")
            waited=time.monotonic()-shown
            if picked is None and waited>=auto_pick: picked=default_level(rows)
            if picked is not None: self.sound("tick"); return picked
            self.draw_level_panel(options,rects,sel,hold/1.5,note,int(auto_pick-waited),camera)
            pygame.display.flip(); clock.tick(30)
        return None
    def draw_level_panel(self,options,rects,sel,hold,note,auto_left,camera):
        self.draw_camera_background((18,30,52),overlay_alpha=200)
        self.panel((20,16,self.W-40,self.H-32),215)
        rows=options[:-1]; done=sum(r["state"]=="passed" for r in rows)
        self.text(f"{self.name.replace('_',' ')}: choose a level",(self.W//2,52),GOLD,48,center=True)
        pace=("Pass a level to open the next one" if self.level_days==0 else "Pass a level and the next one opens tomorrow" if self.level_days==1
              else f"Pass a level and the next one opens {self.level_days} days later")
        self.text(f"Patient {self.patient}   |   {done} of {LEVEL_COUNT} levels done   |   {pace}",(self.W//2,96),MUTED,23,center=True)
        for i,(row,rect) in enumerate(zip(options,rects)):
            state=row["state"]; open_=state in ("passed","open","free")
            self.panel(rect,235 if open_ else 150,(30,44,70) if open_ else (22,28,40),radius=14)
            accent={"passed":GOOD,"open":GOLD,"free":(140,190,255)}.get(state,(110,118,136))
            if i==sel: pygame.draw.rect(self.screen,GOLD,rect.inflate(6,6),4,border_radius=16)
            ink=INK if open_ else (128,136,152)
            if state=="free":
                self.text("Free",(rect.x+16,rect.y+12),accent,52)
                self.text("Free play",(rect.x+16,rect.y+66),ink,27)
                self.text("No goal",(rect.x+16,rect.y+96),MUTED,20)
                self.text(self.difficulty.label(),(rect.x+16,rect.y+120),MUTED,20)
            else:
                self.text(str(row["level"]),(rect.x+16,rect.y+6),accent,64)
                badge={"passed":"Done","open":"Play","waiting":"Soon","locked":"Locked"}[state]
                bw=self.get_font(21).size(badge)[0]+16
                self.panel((rect.right-bw-10,rect.y+12,bw,24),255,accent if open_ else (60,66,80),radius=12)
                self.text(badge,(rect.right-bw//2-10,rect.y+24),PANEL if open_ else MUTED,21,center=True,shadow=False)
                if not open_: self.padlock((rect.right-30,rect.y+62))
                self.text(row["name"],(rect.x+16,rect.y+66),ink,27)
                self.text(row["goal"],(rect.x+16,rect.y+96),MUTED if open_ else (110,118,136),20)
                if state=="passed":
                    for k in range(3): self.star((rect.x+26+k*30,rect.y+130),11,k<row["stars"])
                elif state=="waiting":
                    self.text(f"Opens {opens_text(row['opens_on'])}",(rect.x+16,rect.y+120),GOLD,20)
                elif state=="locked":
                    self.text(f"Pass level {row['level']-1} first",(rect.x+16,rect.y+120),(110,118,136),20)
                elif row.get("best"):
                    self.text(f"Best so far: {row['best']}",(rect.x+16,rect.y+120),MUTED,20)
            if i==sel and hold>0:
                pygame.draw.rect(self.screen,GOOD,(rect.x+8,rect.bottom-10,int((rect.w-16)*min(1,hold)),6),border_radius=3)
        y=rects[-1].bottom+26
        if note and time.monotonic()-note[1]<2.5: self.text(note[0],(self.W//2,y),BAD,28,center=True)
        elif camera: self.text("Move your hand over a level, then hold your hand open to start",(self.W//2,y),GOOD,27,center=True)
        else: self.text("Arrows, 1-7 or the mouse to choose   |   Enter or click to start",(self.W//2,y),INK,26,center=True)
        self.text(f"Starts level {default_level(options[:-1])} by itself in {max(0,auto_left)} s   |   Esc to cancel",(self.W//2,y+34),MUTED,22,center=True)
    def padlock(self,center):
        x,y=center; colour=(130,138,156)
        pygame.draw.arc(self.screen,colour,(x-9,y-18,18,22),0,math.pi,3)
        pygame.draw.rect(self.screen,colour,(x-12,y-7,24,18),border_radius=4)
        pygame.draw.circle(self.screen,(22,28,40),(x,y+2),3)

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
