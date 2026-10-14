import argparse
from pathlib import Path
import pandas as pd
from src.utils.config import ROOT, load_settings
from src.preprocessing.filters import clean
from src.preprocessing.windowing import make_windows
from src.features.emg_features import extract

PUBLIC_SOURCES = {"healthy_raw": ["healthy_raw"], "healthy_filtered": ["healthy_filtered"],
                  "simulated_patient": ["simulated_patient"], "public": ["healthy_raw", "simulated_patient"]}


def recorded_frames():
    """Own recordings in data/raw/emg; signal_type comes from config/settings.yaml."""
    for path in sorted((ROOT / "data/raw/emg").glob("*.csv")):
        df = pd.read_csv(path)
        required = {"subject_id", "session_id", "trial_id", "emg_value", "label"}
        if not required.issubset(df.columns):
            print(f"Skipping {path}: missing {sorted(required - set(df.columns))}"); continue
        if df.empty: continue
        yield path.name, df.assign(cohort="recorded", source="recorded")


def public_frames(name):
    from src.data.public_datasets import load_source
    for source in PUBLIC_SOURCES[name]:
        yield source, load_source(source)


def windows_from(df, cfg, default_signal_type, label_name):
    rows = []; minimum = round(cfg["fs"] * cfg["window_ms"] / 1000)
    for (subject, session, trial, label), group in df.groupby(["subject_id", "session_id", "trial_id", "label"]):
        raw = pd.to_numeric(group.emg_value, errors="coerce").dropna().to_numpy()
        if len(raw) < minimum: continue
        signal_type = group.signal_type.iloc[0] if "signal_type" in group else default_signal_type
        try: filtered = clean(raw, cfg["fs"], *cfg["bandpass"], cfg["notch_hz"], signal_type)
        except ValueError as e: print(f"Skipping {label_name} trial {trial}: {e}"); continue
        for i, window in enumerate(make_windows(filtered, cfg["fs"], cfg["window_ms"], cfg["step_ms"])):
            rows.append({"subject_id": subject, "session_id": session, "trial_id": trial, "window_id": i,
                         "cohort": group.cohort.iloc[0], "source": group.source.iloc[0],
                         **extract(window, signal_type), "label": label})
    return rows


def build(source="recorded", cfg=None):
    cfg = cfg or load_settings(); rows = []
    frames = recorded_frames() if source == "recorded" else public_frames(source)
    for name, df in frames:
        rows += windows_from(df, cfg, cfg.get("signal_type", "raw"), name)
    return pd.DataFrame(rows)


def output_path(source):
    return ROOT / "data/features" / ("emg_features.csv" if source == "recorded" else f"emg_features_{source}.csv")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build windowed EMG feature tables")
    parser.add_argument("--source", choices=["recorded", *PUBLIC_SOURCES], default="recorded",
                        help="recorded = data/raw/emg; others read Datasets/ (simulated_patient is synthetic)")
    args = parser.parse_args(argv)
    out = build(args.source)
    if out.empty: raise SystemExit("No usable samples. Record EMG data first or choose a Datasets/ source.")
    dest = output_path(args.source); dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest, index=False); print(f"Saved {len(out)} windows to {dest}"); print(out.groupby(["cohort", "label"]).size())

if __name__ == "__main__": main()
