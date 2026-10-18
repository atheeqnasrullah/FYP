"""Does public EMG data improve accuracy on our volunteers?

Runs in .venv-finetune. Every method is trained with and without public
windows (src.data.public_emg, shared labels only: Rest, Hand_Open,
Hand_Close) and always tested on our own volunteers, using the subject folds
of a saved LOSO run. Public windows never enter validation or test sets.

Methods: SVM / random forest on 8 features of the 5.12 s windows, and SVM /
random forest on frozen MOMENT-1 features; plus fine-tuned MOMENT runs read
from models/moment/ (baseline and public-data runs).

  python -m src.evaluation.public_data_gain --loso-run models/moment/<baseline loso run> \\
      --public data/processed/public/uci_gestures_windows.npz \\
      --finetuned models/moment/<run> [models/moment/<run> ...]

Writes results/tables/public_data_gain.csv and docs/figures/public_data_gain.png.
"""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score
from src.utils.config import ROOT
from src.features.emg_features import FEATURES, extract
from src.models.train_emg import models as classical_models
from src.models.finetune_moment import DATA, load_windows, load_public, build_model
from src.evaluation.compare_models import read_folds, embeddings

LENGTH_FEATURES = {"WL", "ZC", "SSC"}  # sums or counts that grow with window length


def window_features(X, mask):
    """8 features per window; length-dependent ones scaled to a full 512-sample window (padded public windows)."""
    out = []
    for x, m in zip(X, mask):
        valid = x[0][m.astype(bool)]
        f = extract(valid, "envelope")
        out.append([f[k] * (512 / len(valid) if k in LENGTH_FEATURES else 1) for k in FEATURES])
    return np.array(out, float)


def run(features, extra_features, data, extra, folds, labels, name, rows, recalls):
    for model_name in ("SVM", "RF"):
        for with_public in (False, True):
            preds, trues = [], []
            for f in folds:
                train, test = np.isin(data["subject"], f["train"]), np.isin(data["subject"], f["test"])
                X, y = features[train], data["y"][train]
                if with_public: X, y = np.concatenate([X, extra_features]), np.concatenate([y, extra["y"]])
                model = classical_models()[model_name].fit(X, y)
                p = model.predict(features[test]); preds.append(p); trues.append(data["y"][test])
                rows.append({"method": f"{model_name}, {name}", "public_data": with_public, "fold": "+".join(f["test"]),
                             "accuracy": accuracy_score(data["y"][test], p), "macro_f1": f1_score(data["y"][test], p, average="macro", labels=range(len(labels)), zero_division=0)})
            t, p = np.concatenate(trues), np.concatenate(preds)
            recalls.append({"method": f"{model_name}, {name}", "public_data": with_public,
                            **dict(zip(labels, recall_score(t, p, labels=range(len(labels)), average=None, zero_division=0).round(4)))})
            mean = np.mean([r["accuracy"] for r in rows if r["method"] == f"{model_name}, {name}" and r["public_data"] == with_public])
            print(f"  {model_name}, {name}, public data {with_public}: LOSO accuracy {mean:.3f}", flush=True)


def finetuned_rows(run_dirs, rows):
    for run_dir in run_dirs:
        run_dir = ROOT / run_dir if not Path(run_dir).is_absolute() else Path(run_dir)
        info = json.loads((run_dir / "run.json").read_text()); args = info["args"]
        public = bool(args.get("extra_data") or args.get("pretrain_data"))
        how = " + ".join(x for x, on in (("pre-trained on public", args.get("pretrain_data")), ("public windows added", args.get("extra_data"))) if on) or "own data only"
        metrics = pd.read_csv(run_dir / "metrics.csv")
        for r in metrics[(metrics.phase == "lora") & ~metrics.test.str.contains("synthetic")].itertuples():
            rows.append({"method": "MOMENT LoRA fine-tuned", "public_data": public, "variant": how, "run": info["run_id"],
                         "fold": r.fold, "accuracy": r.accuracy, "macro_f1": r.macro_f1})


def plot(table, dest):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    summary = table.groupby(["method", "variant"], sort=False).accuracy.mean().reset_index()
    labels = [f"{m}\n({v})" for m, v in zip(summary.method, summary.variant)]
    colours = ["#1f6fb5" if v != "own data only" else "#9aa5b1" for v in summary.variant]
    fig, ax = plt.subplots(figsize=(9, 0.5 * len(summary) + 1.3))
    y = np.arange(len(summary))[::-1]
    ax.barh(y, summary.accuracy * 100, color=colours)
    for yv, acc in zip(y, summary.accuracy): ax.text(acc * 100 + 0.4, yv, f"{acc:.1%}", va="center", fontsize=9)
    ax.set_yticks(y, labels, fontsize=8); ax.set_xlim(0, max(60, summary.accuracy.max() * 100 + 8))
    ax.axvline(100 / 7, color="#c0392b", linestyle="--", linewidth=1)
    ax.set_xlabel("Leave-one-subject-out accuracy on our 8 volunteers (%)")
    ax.set_title("Effect of adding public UCI EMG data\n(grey: own data only, blue: with public data)", fontsize=11)
    fig.tight_layout(); dest.parent.mkdir(parents=True, exist_ok=True); fig.savefig(dest, dpi=150); plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure the effect of public EMG data on our volunteers")
    parser.add_argument("--loso-run", required=True, help="saved LOSO run whose folds are used")
    parser.add_argument("--public", required=True, help="windows.npz from src.data.public_emg")
    parser.add_argument("--finetuned", nargs="*", default=[], help="fine-tuned run folders to include")
    args = parser.parse_args(argv)
    import torch
    torch.manual_seed(42); np.random.seed(42)
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    data, _, labels = load_windows(DATA)
    extra, shared = load_public(args.public, labels)
    folds = read_folds(ROOT / args.loso_run)
    print(f"{len(extra['y'])} public windows with shared labels {shared}; {len(folds)} folds", flush=True)
    rows, recalls = [], []
    run(window_features(data["X"], data["mask"]), window_features(extra["X"], extra["mask"]), data, extra, folds, labels, "5.12 s window features", rows, recalls)
    model = build_model("small", len(labels), device, revin=False); model.eval()
    run(embeddings(model, data["X"], data["mask"], device), embeddings(model, extra["X"], extra["mask"], device), data, extra, folds, labels, "frozen MOMENT features", rows, recalls)
    for r in rows: r.setdefault("variant", "public windows added" if r["public_data"] else "own data only")
    finetuned_rows(args.finetuned, rows)
    table = pd.DataFrame(rows)
    tables = ROOT / "results/tables"; tables.mkdir(parents=True, exist_ok=True)
    table.to_csv(tables / "public_data_gain.csv", index=False)
    pd.DataFrame(recalls).to_csv(tables / "public_data_gain_recall.csv", index=False)
    summary = table.groupby(["method", "variant"], sort=False)[["accuracy", "macro_f1"]].mean().round(4)
    print(summary.to_string())
    plot(table, ROOT / "docs/figures/public_data_gain.png")
    print("Saved results/tables/public_data_gain*.csv and docs/figures/public_data_gain.png")

if __name__ == "__main__": main()
