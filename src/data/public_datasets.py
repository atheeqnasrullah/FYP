"""Loaders for the gesture datasets shipped in Datasets/.

Each CSV holds one column per gesture (about 5.5-6.5 s at 1 kHz). Rows are
converted to the long format used by data/raw/emg recordings:
subject_id, session_id, trial_id, emg_value, label, plus cohort and source.

Sources:
  healthy_raw       rectified EMG scaled to mV (10-bit ADC, 4.887 mV steps).
                    Already rectified (never negative), so it takes the envelope
                    path: a 20-450 Hz bandpass would strip its activity level.
  healthy_filtered  smoothed activity envelope of the same recordings
  simulated_patient synthetic bipolar EMG in mV; NOT real patient data.
                    Its lengths match volunteers 1-3, so it is treated as
                    derived from them and never mixed into healthy training.
"""
from pathlib import Path
import pandas as pd
from src.utils.config import ROOT

DATASET_DIR = ROOT / "Datasets"
COLUMN_LABELS = {"HandOpen": "Hand_Open", "HandClose": "Hand_Close", "Wrist Flexion": "Wrist_Flexion",
                 "Wrist Extension": "Wrist_Extension", "Supination": "Supination", "Pronation": "Pronation", "Rest": "Rest"}
GESTURES = list(COLUMN_LABELS.values())
SOURCES = {
    "healthy_raw": {"glob": "Noraml People data/raw_signals/volunteer_*.csv", "prefix": "H", "cohort": "healthy", "signal_type": "envelope"},
    "healthy_filtered": {"glob": "Noraml People data/filtered_signals/volunteer_filtered_*.csv", "prefix": "H", "cohort": "healthy", "signal_type": "envelope"},
    "simulated_patient": {"glob": "Patiant data/simulated_patient_raw_emg_*.csv", "prefix": "SP", "cohort": "simulated_patient", "signal_type": "raw"},
}
FS = 1000


def _subject_number(path):
    return int(Path(path).stem.rsplit("_", 1)[-1])


def files(source):
    spec = SOURCES[source]
    return sorted(DATASET_DIR.glob(spec["glob"]), key=_subject_number)


def load_wide(path):
    """Return a DataFrame with one canonical-label column per gesture."""
    df = pd.read_csv(path)
    missing = set(COLUMN_LABELS) - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing gesture columns {sorted(missing)}")
    return df[list(COLUMN_LABELS)].rename(columns=COLUMN_LABELS).apply(pd.to_numeric, errors="coerce")


def load_source(source):
    """Long-format samples for one source, one trial per gesture recording."""
    spec = SOURCES[source]; frames = []
    for path in files(source):
        subject = f"{spec['prefix']}{_subject_number(path):02d}"
        wide = load_wide(path)
        for label in GESTURES:
            values = wide[label].dropna().to_numpy()
            frames.append(pd.DataFrame({
                "timestamp_ms": range(len(values)), "subject_id": subject, "session_id": 1,
                "trial_id": f"{subject}_{label}", "emg_value": values, "label": label,
                "cohort": spec["cohort"], "source": source, "signal_type": spec["signal_type"]}))
    if not frames:
        raise FileNotFoundError(f"No files for {source} under {DATASET_DIR}")
    return pd.concat(frames, ignore_index=True)


def load_all(sources=("healthy_raw", "simulated_patient")):
    return pd.concat([load_source(s) for s in sources], ignore_index=True)


if __name__ == "__main__":
    for name in SOURCES:
        data = load_source(name)
        print(f"{name}: {data.subject_id.nunique()} subjects, {len(data)} samples, labels {sorted(data.label.unique())}")
