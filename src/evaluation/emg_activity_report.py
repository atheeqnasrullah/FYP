"""EMG activity analysis and data-quality report for the Datasets/ recordings.

RMS/MAV describe recorded electrical activity, not clinical muscle strength.
Simulated patient data is synthetic and is reported separately.
"""
import argparse
import numpy as np, pandas as pd
from src.utils.config import ROOT
from src.data.public_datasets import SOURCES, files, load_wide, GESTURES


def quality_table():
    rows = []
    for source in SOURCES:
        for path in files(source):
            wide = load_wide(path)
            for label in GESTURES:
                x = wide[label].to_numpy(float); finite = x[np.isfinite(x)]
                peak = finite.max() if finite.size else np.nan
                rows.append({"source": source, "file": path.name, "label": label, "samples": len(x),
                             "duration_s": len(x) / 1000, "missing": int((~np.isfinite(x)).sum()),
                             "min": finite.min(), "max": peak, "mean": finite.mean(), "std": finite.std(),
                             "at_max_pct": 100 * float(np.mean(finite == peak)),
                             "flat_pct": 100 * float(np.mean(np.diff(finite) == 0))})
    return pd.DataFrame(rows)


def plot_activity(features, dest):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cohorts = list(features.cohort.unique())
    fig, axes = plt.subplots(1, len(cohorts), figsize=(6 * len(cohorts), 4.5), squeeze=False)
    for ax, cohort in zip(axes[0], cohorts):
        part = features[features.cohort == cohort]
        data = [part[part.label == g].RMS.to_numpy() for g in GESTURES]
        ax.boxplot(data, showfliers=False); ax.set_xticks(range(1, len(GESTURES) + 1), GESTURES, rotation=40, ha="right")
        unit = "mV (synthetic)" if cohort == "simulated_patient" else "mV"
        ax.set_ylabel(f"Window RMS, {unit}"); ax.set_title(f"EMG RMS by gesture: {cohort}")
    fig.tight_layout(); fig.savefig(dest, dpi=150); plt.close(fig)


def plot_subject_heatmap(features, dest):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    part = features[features.cohort == "healthy"]
    table = part.pivot_table(index="subject_id", columns="label", values="RMS", aggfunc="mean")[GESTURES]
    relative = table.div(table["Rest"], axis=0)
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(relative.to_numpy(), cmap="viridis")
    ax.set_xticks(range(len(GESTURES)), GESTURES, rotation=40, ha="right"); ax.set_yticks(range(len(relative)), relative.index)
    ax.set_title("Healthy volunteers: mean RMS relative to own Rest"); fig.colorbar(im, ax=ax, label="x Rest RMS")
    fig.tight_layout(); fig.savefig(dest, dpi=150); plt.close(fig)
    return relative


def main(argv=None):
    parser = argparse.ArgumentParser(description="EMG activity and data-quality report")
    parser.add_argument("--features", default=str(ROOT / "data/features/emg_features_public.csv"))
    args = parser.parse_args(argv)
    tables, figures = ROOT / "results/tables", ROOT / "results/figures"
    tables.mkdir(parents=True, exist_ok=True); figures.mkdir(parents=True, exist_ok=True)
    quality = quality_table(); quality.to_csv(tables / "data_quality.csv", index=False)
    summary = quality.groupby("source").agg(files=("file", "nunique"), recordings=("label", "size"),
                                            mean_duration_s=("duration_s", "mean"), missing=("missing", "sum"),
                                            max_at_max_pct=("at_max_pct", "max"))
    print(summary.round(2))
    features = pd.read_csv(args.features)
    activity = features.groupby(["cohort", "label"])[["RMS", "MAV"]].agg(["mean", "std"]).round(4)
    activity.to_csv(tables / "emg_activity_by_gesture.csv"); print(activity)
    plot_activity(features, figures / "emg_rms_by_gesture.png")
    relative = plot_subject_heatmap(features, figures / "emg_rms_relative_to_rest.png")
    relative.round(3).to_csv(tables / "emg_rms_relative_to_rest.csv")
    print(f"Saved tables to {tables} and figures to {figures}")

if __name__ == "__main__": main()
