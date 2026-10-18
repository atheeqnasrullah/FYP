"""Loaders for the EMG recordings shipped in Dataset/.

Layout: one CSV per subject and movement with columns
timestamp_ms, adc_value, subject_id, movement_label, sampled at 100 Hz.
adc_value is the raw 12-bit ESP32 reading (0-4095) of the MD0437 envelope.

Sources:
  healthy           Dataset/Healthy_person/S01-S09 (9 volunteers)
  stroke_patient    Dataset/stroke_patient (one stroke patient, SP01; replaced
                    the generated patient SYN_STROKE_01 on 2026-10-18); never
                    mixed into healthy training, only used as an extra test

Some files join several recordings (gaps of 12-760 s, one timestamp that runs
backwards), so a file is split into segments at any backwards step or gap
over MAX_GAP_MS. A segment becomes one trial, so windows never span two
recordings. Shorter gaps are dropped samples (S01 has about 2,400 of
20-560 ms) and are kept inside the segment.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from src.utils.config import ROOT

DATASET_DIR = ROOT / "Dataset"
FS = 100
STEP_MS = 1000 // FS
MAX_GAP_MS = 1000  # longer steps (or backwards ones) start a new segment
GESTURES = ["Rest", "Hand_Open", "Hand_Close", "Left", "Right", "Up", "Down"]
SOURCES = {
    "healthy": {"glob": "Healthy_person/*/*.csv", "cohort": "healthy"},
    "stroke_patient": {"glob": "stroke_patient/*.csv", "cohort": "stroke_patient"},
}


def files(source):
    return sorted(DATASET_DIR.glob(SOURCES[source]["glob"]))


def read_file(path):
    df = pd.read_csv(path)
    missing = {"timestamp_ms", "adc_value", "subject_id", "movement_label"} - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing columns {sorted(missing)}")
    return df


def segment_ids(timestamps):
    """Number consecutive runs of samples whose time step is plausible (0 < step <= MAX_GAP_MS)."""
    step = np.diff(np.asarray(timestamps, dtype=float), prepend=np.nan)
    breaks = ~((step > 0) & (step <= MAX_GAP_MS))
    breaks[0] = True
    return np.cumsum(breaks) - 1


def load_source(source):
    """Long-format samples: one trial per continuous recording segment."""
    cohort = SOURCES[source]["cohort"]; frames = []
    for path in files(source):
        df = read_file(path)
        subject, label = str(df.subject_id.iloc[0]), str(df.movement_label.iloc[0])
        segment = segment_ids(df.timestamp_ms)
        frames.append(pd.DataFrame({
            "timestamp_ms": df.timestamp_ms.to_numpy(), "subject_id": subject, "session_id": 1,
            "trial_id": [f"{subject}_{label}_{s}" for s in segment],
            "emg_value": pd.to_numeric(df.adc_value, errors="coerce").to_numpy(), "label": label,
            "cohort": cohort, "source": source, "signal_type": "envelope", "fs": FS, "file": path.name}))
    if not frames:
        raise FileNotFoundError(f"No files for {source} under {DATASET_DIR}")
    return pd.concat(frames, ignore_index=True)


def load_all(sources=tuple(SOURCES)):
    return pd.concat([load_source(s) for s in sources], ignore_index=True)


if __name__ == "__main__":
    for name in SOURCES:
        data = load_source(name)
        print(f"{name}: {data.subject_id.nunique()} subjects, {data.trial_id.nunique()} segments, "
              f"{len(data)} samples, labels {sorted(data.label.unique())}")
