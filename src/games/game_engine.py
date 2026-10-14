import json, queue, time, sys
from pathlib import Path
import pygame
from src.utils.config import ROOT, load_settings
from src.utils.session_sync import PENDING, upload_session, sync_pending_sessions
from src.realtime.pipeline import latest, lock, status_bus, emg_is_ready

KEYMAP={pygame.K_LEFT:"Left",pygame.K_RIGHT:"Right",pygame.K_UP:"Up",pygame.K_DOWN:"Down",pygame.K_o:"Hand_Open",pygame.K_c:"Hand_Close",pygame.K_s:"Supination",pygame.K_p:"Pronation",pygame.K_SPACE:"Rest"}

class BaseGame:
    name="Base"
    def __init__(self,bus,patient_id="P01",w=900,h=600):
        # These games do not use audio; initializing pygame.mixer via pygame.init()
        # can block on Windows systems with no default audio device.
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
        self.runtime_message=None; self.latencies=[]
    def read_input(self):
        for e in pygame.event.get():
            if e.type==pygame.QUIT: self.running=False
            elif e.type==pygame.KEYDOWN and e.key in KEYMAP: self.cmd=KEYMAP[e.key]; self.confidence=1.
            elif e.type==pygame.KEYUP and e.key in KEYMAP: self.cmd="Rest"; self.confidence=0.
        item=None
        try:
            while True:
                item=self.bus.get_nowait(); self.cmd=item.get("command","Rest"); self.confidence=item.get("confidence",0.)
        except queue.Empty: pass
        if item is not None and item.get("vision_ts_ms") is not None:
            self.latencies.append((self.cmd,time.time()*1000-item["vision_ts_ms"]))
        try:
            while True: self.runtime_message=status_bus.get_nowait()
        except queue.Empty: pass
    def wait_for_required_emg(self):
        """Freeze gameplay in Webcam + EMG mode until fresh valid sensor data returns."""
        if getattr(self,"control_mode","keyboard")!="live" or emg_is_ready():
            return
        clock=pygame.time.Clock()
        while self.running and not emg_is_ready():
            for event in pygame.event.get():
                if event.type==pygame.QUIT or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE):
                    self.running=False
            if not self.running:
                break
            self.draw_camera_background((24,32,48),overlay_alpha=145)
            self.text("Waiting for valid EMG sensor data",(self.W//2-205,self.H//2-35),(255,220,110),34)
            self.text("Check ESP32 connection, COM port, baud rate and CSV output.",(self.W//2-275,self.H//2+8),(245,245,245),23)
            if self.runtime_message:
                self.text(str(self.runtime_message)[:100],(self.W//2-275,self.H//2+42),(255,150,120),20)
            pygame.display.flip(); clock.tick(15)
    def target_set(self,label): self.target=label; self.target_t=time.monotonic()
    def log(self,detected):
        if self.target is None: return False
        correct=detected==self.target; vision_label=self.cmd if getattr(self,"control_mode","keyboard") in ("vision","live") else None; self.attempts.append({"ts":time.strftime("%Y-%m-%dT%H:%M:%S"),"target_movement":self.target,"detected_movement":detected,"vision_label":vision_label,"correct":correct,"reaction_time_ms":int((time.monotonic()-self.target_t)*1000),"emg_rms":float(self.emg_rms),"emg_mav":float(self.emg_mav),"confidence":float(self.confidence)})
        if correct:self.score+=10
        return correct
    def text(self,msg,pos,color=(245,245,245),size=None):
        font=pygame.font.Font(None,size or 28); self.screen.blit(font.render(str(msg),True,color),pos)
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
    def hud(self):
        self.text(f"{self.name.replace('_',' ')}   Score {self.score}   Target: {self.target or '-'}   Input: {self.cmd}",(15,12))
        if self.runtime_message:
            message=self.runtime_message
            if len(message)>105: message=message[:102]+"..."
            self.text(f"Input warning: {message}",(15,48),(255,190,90),22)
        if getattr(self,"control_mode","keyboard") in ("vision","live"):
            controls="Move hand to steer/reach | open/close hand for gestures | Esc quit"
        else:
            controls="Arrows move | O open | C close | S/P rotate | Space rest | Esc quit"
        self.text(controls,(15,self.H-28),(190,200,215),22)
    def save_session(self):
        payload={"patient_id":self.patient,"game_name":self.name,"total_score":self.score,"duration_s":int(time.monotonic()-self.started),"attempts":self.attempts}
        cfg=load_settings()
        self.save_latency_log()
        try:
            base=cfg["backend_url"]
            upload_session(base,payload)
            sync_pending_sessions(base)
        except Exception:
            PENDING.parent.mkdir(parents=True,exist_ok=True)
            with PENDING.open("a",encoding="utf-8") as f:f.write(json.dumps(payload)+"\n")
        pygame.quit()
    def save_latency_log(self):
        """Write camera-frame-to-game latency samples for src.evaluation.latency_report."""
        if not self.latencies: return
        folder=ROOT/"data/logs"; folder.mkdir(parents=True,exist_ok=True)
        path=folder/f"latency_{self.name}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        with path.open("w",encoding="utf-8") as f:
            f.write("game,mode,command,latency_ms\n")
            for command,latency in self.latencies: f.write(f"{self.name},{getattr(self,'control_mode','keyboard')},{command},{latency:.1f}\n")
