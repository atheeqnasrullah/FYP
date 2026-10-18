"""Offline EMG gesture classifiers (research only; games never use this model).

Evaluations:
  loso            leave-one-subject-out: the honest cross-subject score
  within_subject  per trial, first 70% of windows train / last 30% test, with a
                  gap so overlapping windows never straddle the split
  cross_cohort    train on healthy volunteers, test on the synthetic stroke patient
"""
import argparse, json
import joblib, numpy as np, pandas as pd
from sklearn.model_selection import LeaveOneGroupOut, GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from src.utils.config import ROOT
from src.features.emg_features import FEATURES

TRAIN_FRACTION = 0.7
GAP_WINDOWS = 2  # 200 ms windows at a 100 ms step overlap their neighbour


def models():
    return {"LDA": make_pipeline(StandardScaler(), LinearDiscriminantAnalysis()),
            "SVM": make_pipeline(StandardScaler(), SVC(C=10, random_state=42)),
            "RF": make_pipeline(StandardScaler(), RandomForestClassifier(n_estimators=200, random_state=42))}


def subject_normalise(df):
    """Unsupervised per-subject calibration: z-score each feature within a subject."""
    out = df.copy()
    grouped = out.groupby("subject_id")[FEATURES]
    out[FEATURES] = (out[FEATURES] - grouped.transform("mean")) / grouped.transform("std").replace(0, 1)
    return out


def within_subject_split(df):
    position = df.groupby("trial_id").window_id.transform(lambda w: w.rank(method="first") / len(w))
    train = position <= TRAIN_FRACTION
    last_train = df[train].groupby("trial_id").window_id.max()
    test = (~train) & (df.window_id > df.trial_id.map(last_train) + GAP_WINDOWS)
    return train.to_numpy(), test.to_numpy()


def score(y, pred):
    return {"accuracy": accuracy_score(y, pred), "macro_f1": f1_score(y, pred, average="macro", zero_division=0)}


def save_confusion(y, pred, labels, title, dest):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cm = confusion_matrix(y, pred, labels=labels, normalize="true")
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right"); ax.set_yticks(range(len(labels)), labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center", color="white" if cm[i, j] > .5 else "black", fontsize=8)
    ax.set_xlabel("Predicted"); ax.set_ylabel("True"); ax.set_title(title); fig.colorbar(im, ax=ax, fraction=.046)
    fig.tight_layout(); dest.parent.mkdir(parents=True, exist_ok=True); fig.savefig(dest, dpi=150); plt.close(fig)


def write_splits(df, dest):
    subjects = sorted(df.subject_id.astype(str).unique())
    holdout = subjects[-3:] if len(subjects) > 3 else subjects[-1:]
    splits = {"subjects": subjects, "loso": [{"test": [s]} for s in subjects],
              "holdout": {"train": [s for s in subjects if s not in holdout], "test": holdout},
              "within_subject": {"train_fraction": TRAIN_FRACTION, "gap_windows": GAP_WINDOWS}}
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(json.dumps(splits, indent=2))
    return splits


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train and evaluate offline EMG classifiers")
    parser.add_argument("--features", default=str(ROOT / "data/features/emg_features.csv"))
    parser.add_argument("--cohort", default="healthy", help="cohort used for training (ignored when the file has no cohort column)")
    parser.add_argument("--subject-norm", action="store_true", help="z-score features per subject (unsupervised calibration)")
    parser.add_argument("--tag", default=None, help="name used for result files (default: features file stem)")
    args = parser.parse_args(argv)
    path = ROOT / args.features if not str(args.features).startswith("/") else args.features
    path = __import__("pathlib").Path(path)
    if not path.exists(): raise SystemExit("Build features first with python -m src.features.build_dataset")
    data = pd.read_csv(path).dropna(subset=FEATURES + ["label", "subject_id", "trial_id"])
    if "cohort" not in data: data["cohort"] = "recorded"
    if args.subject_norm: data = subject_normalise(data)
    df = data[data.cohort == args.cohort] if args.cohort in set(data.cohort) else data
    if df.trial_id.nunique() < 2: raise SystemExit("Need at least two trials for grouped evaluation")
    tag = args.tag or path.stem.replace("emg_features", "baseline").strip("_") + ("_subjnorm" if args.subject_norm else "")
    tables, figures = ROOT / "results/tables", ROOT / "results/figures"
    labels = sorted(df.label.unique()); y, X = df.label.to_numpy(), df[FEATURES]
    groups = df.subject_id.astype(str)
    cross_subject = groups.nunique() > 1
    cv = LeaveOneGroupOut() if cross_subject else GroupKFold(min(5, df.trial_id.nunique()))
    fold_groups = groups if cross_subject else df.trial_id
    if cross_subject: write_splits(df, ROOT / "results/splits.json")
    train_mask, test_mask = within_subject_split(df)
    patients = data[(data.cohort != args.cohort) & (data.cohort != "recorded")] if args.cohort in set(data.cohort) else data.iloc[0:0]
    rows, best = [], None
    for name, model in models().items():
        pred = cross_val_predict(model, X, y, groups=fold_groups, cv=cv)
        m = score(y, pred); evaluation = "loso" if cross_subject else "trial_kfold"
        rows.append({"model": name, "evaluation": evaluation, **m, "n_test": len(y)})
        print(f"{name}: {evaluation} accuracy={m['accuracy']:.3f} macro_f1={m['macro_f1']:.3f}")
        print(classification_report(y, pred, zero_division=0))
        save_confusion(y, pred, labels, f"{name} {evaluation} ({tag})", figures / f"confusion_{tag}_{name}_{evaluation}.png")
        if best is None or m["accuracy"] > best[0]: best = (m["accuracy"], name, model)
        if test_mask.any():
            fitted = models()[name].fit(X[train_mask], y[train_mask]); p = fitted.predict(X[test_mask])
            rows.append({"model": name, "evaluation": "within_subject", **score(y[test_mask], p), "n_test": int(test_mask.sum())})
        if not patients.empty:
            fitted = models()[name].fit(X, y); p = fitted.predict(patients[FEATURES])
            rows.append({"model": name, "evaluation": "cross_cohort_stroke_synthetic", **score(patients.label, p), "n_test": len(patients)})
    metrics = pd.DataFrame(rows); tables.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(tables / f"{tag}_metrics.csv", index=False)
    print(metrics.pivot_table(index="model", columns="evaluation", values="accuracy").round(3))
    best[2].fit(X, y)
    dest = ROOT / "src/models/saved/emg_model.joblib"; dest.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": best[2], "features": FEATURES, "labels": labels, "trained_on": str(path.name), "subject_norm": args.subject_norm}, dest)
    print(f"Saved {best[1]} model to {dest}; metrics in {tables / f'{tag}_metrics.csv'}")
    return metrics

if __name__ == "__main__": main()
