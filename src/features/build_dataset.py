from pathlib import Path
import pandas as pd
from src.utils.config import ROOT, load_settings
from src.preprocessing.filters import clean
from src.preprocessing.windowing import make_windows
from src.features.emg_features import extract

def main():
    cfg = load_settings(); rows = []
    for path in (ROOT / "data/raw/emg").glob("*.csv"):
        df = pd.read_csv(path)
        required = {"subject_id", "session_id", "trial_id", "emg_value", "label"}
        if not required.issubset(df.columns):
            print(f"Skipping {path}: missing {sorted(required - set(df.columns))}"); continue
        for (subject, session, trial, label), group in df.groupby(["subject_id", "session_id", "trial_id", "label"]):
            raw = pd.to_numeric(group.emg_value, errors="coerce").dropna().to_numpy()
            minimum = round(cfg["fs"] * cfg["window_ms"] / 1000)
            if len(raw) < minimum: continue
            try: filtered = clean(raw, cfg["fs"], *cfg["bandpass"], cfg["notch_hz"], cfg.get("signal_type", "raw"))
            except ValueError as e: print(f"Skipping {path} trial {trial}: {e}"); continue
            for i, window in enumerate(make_windows(filtered, cfg["fs"], cfg["window_ms"], cfg["step_ms"])):
                rows.append({"subject_id": subject, "session_id": session, "trial_id": trial,
                             "window_id": i, **extract(window, cfg.get("signal_type", "raw")), "label": label})
    out = pd.DataFrame(rows)
    if out.empty: raise SystemExit("No usable samples. Record EMG data first.")
    dest = ROOT / "data/features/emg_features.csv"; dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest, index=False); print(f"Saved {len(out)} windows to {dest}"); print(out.label.value_counts())

if __name__ == "__main__": main()
