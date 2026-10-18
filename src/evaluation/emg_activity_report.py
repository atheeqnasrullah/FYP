"""EMG activity analysis and data-quality report for the Dataset/ recordings.

RMS/MAV describe the recorded envelope (ADC units), not clinical muscle strength.
The stroke patient data is synthetic and is reported separately.
"""
import argparse
import numpy as np, pandas as pd
from src.utils.config import ROOT
from src.data.public_datasets import SOURCES, files, read_file, segment_ids, GESTURES, STEP_MS

ADC_MAX = 4095


def quality_table():
    rows = []
    for source in SOURCES:
        for path in files(source):
            df = read_file(path); x = pd.to_numeric(df.adc_value, errors="coerce").to_numpy(float)
            step = np.diff(df.timestamp_ms.to_numpy(float))
            finite = x[np.isfinite(x)]
            rows.append({"source": source, "file": path.name, "subject_id": df.subject_id.iloc[0], "label": df.movement_label.iloc[0],
                         "samples": len(x), "segments": int(segment_ids(df.timestamp_ms).max() + 1),
                         "dropouts": int(np.sum(step > STEP_MS)), "backward_steps": int(np.sum(step <= 0)),
                         "span_s": (df.timestamp_ms.iloc[-1] - df.timestamp_ms.iloc[0]) / 1000,
                         "missing": int((~np.isfinite(x)).sum()), "min": finite.min(), "max": finite.max(),
                         "mean": finite.mean(), "zero_pct": 100 * float(np.mean(finite == 0)),
                         "saturated_pct": 100 * float(np.mean(finite >= ADC_MAX))})
    return pd.DataFrame(rows)


def plot_activity(features, dest):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cohorts = list(features.cohort.unique())
    fig, axes = plt.subplots(1, len(cohorts), figsize=(6 * len(cohorts), 4.5), squeeze=False, sharey=True)
    for ax, cohort in zip(axes[0], cohorts):
        part = features[features.cohort == cohort]
        data = [part[part.label == g].RMS.to_numpy() for g in GESTURES]
        ax.boxplot(data, showfliers=False); ax.set_xticks(range(1, len(GESTURES) + 1), GESTURES, rotation=40, ha="right")
        ax.set_ylabel("Window RMS (ADC units)"); ax.set_title(f"EMG RMS by movement: {cohort}")
    fig.tight_layout(); fig.savefig(dest, dpi=150); plt.close(fig)


def plot_subject_heatmap(features, dest):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    part = features[features.cohort == "healthy"]
    table = part.pivot_table(index="subject_id", columns="label", values="RMS", aggfunc="mean").reindex(columns=GESTURES)
    relative = table.div(table["Rest"], axis=0)
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(np.log10(relative.to_numpy(dtype=float)), cmap="viridis")
    ax.set_xticks(range(len(GESTURES)), GESTURES, rotation=40, ha="right"); ax.set_yticks(range(len(relative)), relative.index)
    ax.set_title("Healthy volunteers: mean RMS relative to own Rest (log10)"); fig.colorbar(im, ax=ax, label="log10(x Rest RMS)")
    fig.tight_layout(); fig.savefig(dest, dpi=150); plt.close(fig)
    return relative


def main(argv=None):
    parser = argparse.ArgumentParser(description="EMG activity and data-quality report")
    parser.add_argument("--features", default=str(ROOT / "data/features/emg_features_public.csv"))
    args = parser.parse_args(argv)
    tables, figures = ROOT / "results/tables", ROOT / "results/figures"
    tables.mkdir(parents=True, exist_ok=True); figures.mkdir(parents=True, exist_ok=True)
    quality = quality_table(); quality.to_csv(tables / "data_quality.csv", index=False)
    summary = quality.groupby("source").agg(files=("file", "size"), subjects=("subject_id", "nunique"), samples=("samples", "sum"),
                                            segments=("segments", "sum"), dropouts=("dropouts", "sum"), missing=("missing", "sum"),
                                            max_saturated_pct=("saturated_pct", "max"))
    print(summary.round(2))
    features = pd.read_csv(args.features)
    activity = features.groupby(["cohort", "label"])[["RMS", "MAV"]].agg(["mean", "std"]).round(2)
    activity.to_csv(tables / "emg_activity_by_gesture.csv"); print(activity)
    plot_activity(features, figures / "emg_rms_by_gesture.png")
    relative = plot_subject_heatmap(features, figures / "emg_rms_relative_to_rest.png")
    relative.round(3).to_csv(tables / "emg_rms_relative_to_rest.csv")
    print(f"Saved tables to {tables} and figures to {figures}")

if __name__ == "__main__": main()
