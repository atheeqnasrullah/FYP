import time
from collections import Counter, deque


class FusionEngine:
    """Use vision for movement commands and attach EMG activity measurements."""

    def __init__(self, smoothing_n=5, min_conf=.6):
        self.buf = deque(maxlen=max(1, smoothing_n))
        self.min_conf = min_conf

    def fuse(self, emg=None, vis=None, emg_features=None):
        # EMG is a continuous activity signal in this project, not a movement
        # classifier. Never let an EMG class suppress a camera-detected action.
        label, confidence = vis if vis else ("Rest", 0.0)
        if confidence < self.min_conf:
            label = "Rest"
        self.buf.append(label)
        stable_label = Counter(self.buf).most_common(1)[0][0]
        features = emg_features or {}
        return {
            "command": stable_label,
            "confidence": confidence,
            "source": "vision+emg" if features else "vision",
            "timestamp_ms": int(time.time() * 1000),
            "emg_rms": float(features.get("RMS", 0.0)),
            "emg_mav": float(features.get("MAV", 0.0)),
            "emg_features": features,
        }
