"""Stand-in for the ESP32 serial stream: replay a Dataset/ recording in real time.

Lets Webcam + EMG mode run without the sensor. Samples go through the same
windowing and extract() path as live serial data, so games see the same
feature dictionaries. Samples play at the recording's own rate (100 Hz for
Dataset/), and windows use that rate. Set EMG_REPLAY_SOURCE / EMG_REPLAY_SUBJECT
to choose the recording (defaults: healthy, S02); movements play in a loop.
"""
import os, time
from collections import deque
import numpy as np
from src.utils.config import load_settings
from src.features.emg_features import extract

REPLAY_BATCH_MS = 10


def replay_part(source=None, subject=None):
    from src.data.public_datasets import load_source
    source = source or os.environ.get("EMG_REPLAY_SOURCE", "healthy")
    data = load_source(source)
    # S02 has all seven movements as clean 60 s recordings (S01 lacks Rest).
    default = "S02" if "S02" in set(data.subject_id) else data.subject_id.iloc[0]
    subject = subject or os.environ.get("EMG_REPLAY_SUBJECT") or default
    part = data[data.subject_id == subject]
    if part.empty: raise ValueError(f"No replay data for subject {subject} in {source}")
    return part, f"{source}/{subject}"


def replay_signal(source=None, subject=None):
    part, name = replay_part(source, subject)
    return part.emg_value.to_numpy(float), part.signal_type.iloc[0], name, int(part.fs.iloc[0])


def replay_calibration(source=None, subject=None):
    """(rest, strongest) RMS of the replayed recording: median of its Rest windows, 90th percentile of its Hand_Close windows.

    Stands in for the relax-then-squeeze check, which a recording cannot follow."""
    from src.games.effort import calibrate
    cfg = load_settings()
    part, _ = replay_part(source, subject)
    fs = int(part.fs.iloc[0]); width = round(fs * cfg["window_ms"] / 1000); step = round(fs * cfg["step_ms"] / 1000)
    def rms(label):
        values = []
        for _, trial in part[part.label == label].groupby("trial_id"):
            x = trial.emg_value.to_numpy(float); x = x[np.isfinite(x)]
            values += [extract(x[i:i + width], part.signal_type.iloc[0])["RMS"] for i in range(0, len(x) - width + 1, step)]
        return values
    result = calibrate(rms("Rest") or rms("Hand_Open"), rms("Hand_Close"))
    if result is None: raise ValueError("the recording's Hand_Close is not stronger than its Rest")
    return result


def replay_emg(source=None, subject=None):
    from src.realtime.pipeline import stop, lock, latest, publish_emg_features
    cfg = load_settings()
    signal, signal_type, name, fs = replay_signal(source, subject)
    width = round(fs * cfg["window_ms"] / 1000); step = round(fs * cfg["step_ms"] / 1000)
    print(f"EMG replay from {name} at {fs} Hz ({len(signal) / fs:.1f} s loop); movement labels come from the webcam.", flush=True)
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
