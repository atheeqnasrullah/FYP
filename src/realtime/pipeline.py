import math, queue, threading, time
from collections import Counter, deque
import numpy as np
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, tf2sos
from src.utils.config import load_settings
from src.features.emg_features import extract
from src.fusion.fusion_engine import FusionEngine

command_bus=queue.Queue(maxsize=50); status_bus=queue.Queue(maxsize=10); stop=threading.Event(); lock=threading.Lock(); latest={"emg":None,"emg_level":None,"emg_features":None,"emg_sample_time":None,"emg_features_time":None,"vis":None,"frame":None,"pointer":None,"fist":False}

EMG_FRESHNESS_SECONDS=2.5

def emg_is_ready(now=None):
    """True only while valid samples and a complete recent feature window arrive."""
    now=time.monotonic() if now is None else now
    with lock:
        sample_time=latest.get("emg_sample_time")
        features_time=latest.get("emg_features_time")
        features=latest.get("emg_features")
    return bool(features) and sample_time is not None and features_time is not None and now-sample_time<=EMG_FRESHNESS_SECONDS and now-features_time<=EMG_FRESHNESS_SECONDS

def _emg():
    import serial
    cfg=load_settings()
    print("EMG activity monitoring enabled; movement labels come from the webcam.", flush=True)
    fs=cfg["fs"]; width=round(fs*cfg["window_ms"]/1000); step=round(fs*cfg["step_ms"]/1000)
    signal_type=cfg.get("signal_type","raw")
    if signal_type not in ("raw","envelope"): raise RuntimeError("signal_type must be raw or envelope in config/settings.yaml")
    if signal_type=="raw":
        sos=butter(4,[cfg["bandpass"][0]/(fs/2),min(cfg["bandpass"][1],fs*.475)/(fs/2)],btype="band",output="sos")
        bn,an=iirnotch(cfg["notch_hz"]/(fs/2),30); nsos=tf2sos(bn,an); zi=sosfilt_zi(sos)*0; nz=sosfilt_zi(nsos)*0
    port=serial.Serial(cfg["serial_port"],cfg["baud_rate"],timeout=1); buf=deque(maxlen=width); dc=2048.; count=0
    try:
        while not stop.is_set():
            parts=port.readline().decode(errors="ignore").strip().split(",")
            if len(parts)!=2: continue
            try: value=float(parts[1]); timestamp=float(parts[0])
            except ValueError: continue
            if not math.isfinite(value) or not math.isfinite(timestamp) or not 0<=value<=4095: continue
            with lock: latest["emg_sample_time"]=time.monotonic()
            if signal_type=="raw":
                dc=.999*dc+.001*value; y,zi=sosfilt(sos,[value-dc],zi=zi); y,nz=sosfilt(nsos,y,zi=nz); value=y[0]
            buf.append(value); count+=1
            if len(buf)==width and (count-width)%step==0:
                features=extract(buf,signal_type)
                with lock:
                    latest["emg_level"]=float(features["RMS"])
                    latest["emg_features"]=features
                    latest["emg_features_time"]=time.monotonic()
    finally:
        port.close()
        with lock: latest["emg"] = None; latest["emg_level"] = None; latest["emg_features"] = None; latest["emg_sample_time"] = None; latest["emg_features_time"] = None

def _vision(show_preview=True):
    import cv2
    from src.vision.hand_tracker import HandTracker,rule_classify
    cfg=load_settings(); tracker=HandTracker()
    history_size=max(1,int(cfg.get("vision_smoothing_frames",5)))
    history=deque(maxlen=history_size)
    fist_history=deque(maxlen=history_size)
    stable_gesture=None
    pointer_smooth=None
    palm_x_smooth=None
    palm_y_smooth=None
    movement_anchor=None
    movement_anchor_time=0.0
    movement_label=None
    movement_until=0.0
    next_movement_time=0.0
    pointer_alpha=float(cfg.get("pointer_smoothing_alpha",.35))
    horizontal_threshold=float(cfg.get("lr_motion_threshold",.04))
    vertical_threshold=float(cfg.get("ud_motion_threshold",.04))
    movement_hold_s=float(cfg.get("lr_motion_hold_ms",280))/1000
    movement_cooldown_s=float(cfg.get("lr_motion_cooldown_ms",220))/1000
    preferred=int(cfg["camera_index"])
    indexes=list(dict.fromkeys([preferred,0,1,2,3]))
    if __import__("sys").platform=="win32":
        backends=[cv2.CAP_DSHOW,cv2.CAP_MSMF,cv2.CAP_ANY]
    else:
        backends=[cv2.CAP_ANY]
    cap=None; opened_index=None
    for index in indexes:
        for backend in backends:
            candidate=cv2.VideoCapture(index,backend)
            if candidate.isOpened():
                cap=candidate; opened_index=index; break
            candidate.release()
        if cap is not None: break
    if cap is None:
        tracker.close()
        raise RuntimeError(f"Could not open a webcam (tried indexes {indexes}); check camera permissions, close other camera apps, and set camera_index in config/settings.yaml")
    cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
    print(f"Webcam opened at camera index {opened_index}", flush=True)
    failed_frames=0
    try:
        while not stop.is_set():
            ok,frame=cap.read()
            if not ok or frame is None:
                failed_frames+=1
                if failed_frames>=30:
                    raise RuntimeError(f"Camera index {opened_index} opened but did not provide video frames")
                time.sleep(.02); continue
            failed_frames=0
            lm=tracker.process(frame)
            features=tracker.features(lm) if lm is not None else None
            raw_gesture=rule_classify(features) if features is not None else None
            if raw_gesture is None:
                history.clear(); fist_history.clear(); stable_gesture=None; pointer_smooth=None
                palm_x_smooth=None; palm_y_smooth=None; movement_anchor=None; movement_anchor_time=0.0
                movement_label=None; movement_until=0.0; next_movement_time=0.0
                val=None; pointer=None; stable_fist=False
            else:
                history.append(raw_gesture)
                fist_history.append(bool(features["full_fist"]))
                stable_fist=sum(fist_history) >= max(1,(history_size*3+4)//5)
                counts=Counter(label for label,_ in history)
                candidate,count=counts.most_common(1)[0]
                if count >= max(1,(history_size*3+4)//5):
                    confidence=float(np.mean([score for label,score in history if label==candidate]))
                    stable_gesture=(candidate,confidence)
                val=stable_gesture or ("Rest",0.0)
                # Aim from the middle phalanx of the middle finger, halfway
                # between its PIP (10) and DIP (11) landmarks.
                point=(np.array([float(lm[10,0]),float(lm[10,1])])+
                       np.array([float(lm[11,0]),float(lm[11,1])]))/2
                pointer_smooth=point if pointer_smooth is None else pointer_alpha*point+(1-pointer_alpha)*pointer_smooth
                pointer=(float(pointer_smooth[0]),float(pointer_smooth[1]))
                palm_x=features["cx"]
                palm_x_smooth=palm_x if palm_x_smooth is None else pointer_alpha*palm_x+(1-pointer_alpha)*palm_x_smooth
                palm_y=features["cy"]
                palm_y_smooth=palm_y if palm_y_smooth is None else pointer_alpha*palm_y+(1-pointer_alpha)*palm_y_smooth
                now=time.monotonic()
                if raw_gesture[0]=="Hand_Close":
                    movement_label=None; movement_until=0.0
                    movement_anchor=(palm_x_smooth,palm_y_smooth); movement_anchor_time=now
                    next_movement_time=now
                elif movement_anchor is None:
                    movement_anchor=(palm_x_smooth,palm_y_smooth); movement_anchor_time=now
                elif now >= next_movement_time and now-movement_anchor_time >= .06:
                    delta_x=palm_x_smooth-movement_anchor[0]
                    delta_y=palm_y_smooth-movement_anchor[1]
                    if abs(delta_x)>=horizontal_threshold or abs(delta_y)>=vertical_threshold:
                        if abs(delta_x)/horizontal_threshold >= abs(delta_y)/vertical_threshold:
                            movement_label="Right" if delta_x>0 else "Left"
                        else:
                            movement_label="Down" if delta_y>0 else "Up"
                        movement_until=now+movement_hold_s
                        next_movement_time=now+movement_cooldown_s
                        movement_anchor=(palm_x_smooth,palm_y_smooth); movement_anchor_time=now
                if movement_label is not None and now < movement_until:
                    val=(movement_label,.92)
            display_frame=cv2.flip(frame,1)
            if lm is not None:
                tracker.draw_landmarks(display_frame,lm)
            with lock:
                latest["vis"]=val
                latest["frame"]=display_frame
                latest["pointer"]=pointer
                latest["fist"]=stable_fist
            if show_preview:
                preview=display_frame.copy()
                label=f"Camera active | {val[0]} ({val[1]:.2f})" if val else "Camera active | show one hand"
                cv2.putText(preview,label,(12,30),cv2.FONT_HERSHEY_SIMPLEX,.7,(30,230,80),2)
                cv2.imshow("Rehabilitation camera",preview)
                cv2.waitKey(1)
    finally:
        cap.release(); tracker.close()
        with lock:
            latest["frame"] = None
            latest["pointer"] = None
            latest["vis"] = None
            latest["fist"] = False
        if show_preview: cv2.destroyWindow("Rehabilitation camera")

def _fusion(use_emg=True):
    cfg=load_settings(); fusion=FusionEngine(cfg["smoothing_n"],cfg["min_confidence"])
    while not stop.is_set():
        with lock:
            v=latest["vis"]
            emg_features=latest["emg_features"] if use_emg else None
        cmd=fusion.fuse(vis=v,emg_features=emg_features)
        try: command_bus.put_nowait(cmd)
        except queue.Full:
            try: command_bus.get_nowait(); command_bus.put_nowait(cmd)
            except queue.Empty: pass
        time.sleep(.05)

def _guard(fn,*args):
    try: fn(*args)
    except Exception as e:
        message=f"{fn.__name__}: {e}"
        print(f"Live pipeline stopped in {message}", flush=True)
        try: status_bus.put_nowait(message)
        except queue.Full:
            try: status_bus.get_nowait(); status_bus.put_nowait(message)
            except queue.Empty: pass

def start(use_emg=True,use_vision=True,show_preview=False):
    stop.clear()
    with lock:
        latest.update(emg=None,emg_level=None,emg_features=None,emg_sample_time=None,emg_features_time=None,vis=None,frame=None,pointer=None,fist=False)
    if use_emg: threading.Thread(target=_guard,args=(_emg,),daemon=True).start()
    if use_vision: threading.Thread(target=_guard,args=(_vision,show_preview),daemon=True).start()
    threading.Thread(target=_guard,args=(_fusion,use_emg),daemon=True).start()

def shutdown(): stop.set()
