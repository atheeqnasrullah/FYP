"""Stand-in for the ESP32 serial stream: replay a Datasets/ recording at 1 kHz.

Lets Webcam + EMG mode run without the sensor. Samples go through the same
windowing and extract() path as live serial data, so games see the same
feature dictionaries. Set EMG_REPLAY_SOURCE / EMG_REPLAY_SUBJECT to choose the
recording (defaults: healthy_raw, H01); gestures play in a loop.
"""
import os, time
from collections import deque
import numpy as np
from src.utils.config import load_settings
from src.features.emg_features import extract

REPLAY_BATCH_MS = 10


def replay_signal(source=None, subject=None):
    from src.data.public_datasets import load_source
    source = source or os.environ.get("EMG_REPLAY_SOURCE", "healthy_raw")
    data = load_source(source)
    subject = subject or os.environ.get("EMG_REPLAY_SUBJECT") or data.subject_id.iloc[0]
    part = data[data.subject_id == subject]
    if part.empty: raise ValueError(f"No replay data for subject {subject} in {source}")
    return part.emg_value.to_numpy(float), part.signal_type.iloc[0], f"{source}/{subject}"


def replay_emg(source=None, subject=None):
    from src.realtime.pipeline import stop, lock, latest, publish_emg_features
    cfg = load_settings(); fs = cfg["fs"]
    width = round(fs * cfg["window_ms"] / 1000); step = round(fs * cfg["step_ms"] / 1000)
    signal, signal_type, name = replay_signal(source, subject)
    print(f"EMG replay from {name} ({len(signal) / fs:.1f} s loop); movement labels come from the webcam.", flush=True)
    buf = deque(maxlen=width); index = count = 0; batch = max(1, fs * REPLAY_BATCH_MS // 1000)
    next_time = time.monotonic()
    try:
        while not stop.is_set():
            for _ in range(batch):
                buf.append(signal[index]); index = (index + 1) % len(signal); count += 1
                if len(buf) == width and (count - width) % step == 0:
                    publish_emg_features(extract(np.asarray(buf), signal_type))
            with lock: latest["emg_sample_time"] = time.monotonic()
            next_time += batch / fs
            time.sleep(max(0.0, next_time - time.monotonic()))
    finally:
        with lock:
            latest.update(emg=None, emg_level=None, emg_features=None, emg_sample_time=None, emg_features_time=None)
