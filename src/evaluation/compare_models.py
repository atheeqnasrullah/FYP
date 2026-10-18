"""Compare every movement classifier on exactly the same subject splits.

Runs in .venv-finetune (needs torch). Uses the train / validation / test
subjects saved in the fine-tuning runs (folds/<test>/fold.json), so every
method is scored on the same people. Classical models train on the same
training subjects (the validation subject is not used by them).

Methods
  classical_200ms   LDA, SVM, RF on 8 features of 200 ms windows of the raw
                    envelope (data/features/emg_features_public.csv)
  classical_5s      LDA, SVM, RF on 8 features of the same 5.12 s preprocessed
                    windows MOMENT sees (separates window length from model)
  moment_untrained  MOMENT-1-small out of the box with an untrained head
  moment_frozen     frozen MOMENT embeddings (no weights changed) + LDA, SVM, RF;
                    with per-subject calibration, and with MOMENT's RevIN
  moment_finetuned  the saved fine-tuned models: linear probe (from the run's
                    metrics) and LoRA (reloaded from the saved adapters)

  python -m src.evaluation.compare_models \\
      --holdout-run models/moment/<holdout run> --loso-run models/moment/<loso run>

Writes results/tables/model_comparison.csv, model_comparison_recall.csv and
docs/figures/model_comparison.png.
"""
import argparse, json, time
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score
from src.utils.config import ROOT
from src.features.emg_features import FEATURES, extract
from src.models.train_emg import models as classical_models
from src.models.finetune_moment import DATA, load_windows, build_model, load_finetuned


def read_folds(run_dir):
    return [json.loads((d / "fold.json").read_text()) | {"dir": d} for d in sorted((run_dir / "folds").iterdir()) if (d / "fold.json").exists()]


def score(evaluation, method, family, stage, fold, test, y_true, y_pred, labels, rows, recalls):
    rows.append({"evaluation": evaluation, "method": method, "family": family, "stage": stage, "fold": fold, "test": test,
                 "accuracy": accuracy_score(y_true, y_pred), "macro_f1": f1_score(y_true, y_pred, average="macro", labels=range(len(labels)), zero_division=0),
                 "n": len(y_true)})
    if test != "synthetic":
        recalls.append({"evaluation": evaluation, "method": method, "fold": fold, "y_true": np.asarray(y_true), "y_pred": np.asarray(y_pred)})


def classical_on(features_by, folds, synthetic_features, evaluation, family, labels, rows, recalls, note):
    """features_by: (X, y, subject) for healthy windows; synthetic_features: (X, y)."""
    X, y, subject = features_by
    for f in folds:
        train, test = np.isin(subject, f["train"]), np.isin(subject, f["test"])
        for name, model in classical_models().items():
            started = time.time(); model.fit(X[train], y[train])
            method = f"{name} ({note})"
            score(evaluation, method, family, "classical", "+".join(f["test"]), "healthy", y[test], model.predict(X[test]), labels, rows, recalls)
            score(evaluation, method, family, "classical", "+".join(f["test"]), "synthetic", synthetic_features[1], model.predict(synthetic_features[0]), labels, rows, recalls)
            print(f"  {evaluation} {method} test {'+'.join(f['test'])}: {rows[-2]['accuracy']:.3f} ({time.time() - started:.0f} s)", flush=True)


def window_features(X, mask):
    return np.array([list(extract(x[0][m.astype(bool)], "envelope").values()) for x, m in zip(X, mask)], dtype=float)


def embeddings(model, X, mask, device):
    import torch
    out = []
    with torch.no_grad():
        for i in range(0, len(X), 64):
            e = model.embed(x_enc=torch.from_numpy(X[i:i + 64]).to(device), input_mask=torch.from_numpy(mask[i:i + 64].astype(np.float32)).to(device), reduction="mean").embeddings
            out.append(e.cpu().numpy())
    return np.concatenate(out)


def logits_predict(model, X, mask, device):
    import torch
    out = []
    with torch.no_grad():
        for i in range(0, len(X), 64):
            out.append(model(x_enc=torch.from_numpy(X[i:i + 64]).to(device), input_mask=torch.from_numpy(mask[i:i + 64].astype(np.float32)).to(device)).logits.argmax(1).cpu().numpy())
    return np.concatenate(out)


def plot(table, dest):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    loso = table[(table.evaluation == "loso") & (table.test == "healthy")].groupby(["family", "method"], sort=False).accuracy.mean().reset_index()
    colours = {"Classical, 200 ms windows": "#9aa5b1", "Classical, 5.12 s windows": "#6b7785", "MOMENT before fine-tuning": "#9cc3e6", "MOMENT after fine-tuning": "#1f6fb5"}
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(loso) + 1.2))
    ypos = np.arange(len(loso))[::-1]
    ax.barh(ypos, loso.accuracy * 100, color=[colours.get(f, "#999") for f in loso.family])
    for yv, acc in zip(ypos, loso.accuracy): ax.text(acc * 100 + 0.5, yv, f"{acc:.1%}", va="center", fontsize=9)
    ax.axvline(100 / 7, color="#c0392b", linestyle="--", linewidth=1); ax.text(100 / 7 + 0.5, ypos[-1] - 0.7, "chance 14.3%", color="#c0392b", fontsize=8)
    ax.set_yticks(ypos, loso.method, fontsize=9); ax.set_xlabel("Leave-one-subject-out accuracy, 8 healthy volunteers (%)")
    ax.set_xlim(0, max(60, loso.accuracy.max() * 100 + 8))
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colours.values()]
    ax.legend(handles, colours.keys(), loc="upper right", fontsize=8, frameon=True, framealpha=0.95)
    ax.set_title("Every model on the same subject splits (7 movements)")
    fig.tight_layout(); dest.parent.mkdir(parents=True, exist_ok=True); fig.savefig(dest, dpi=150); plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare classical models and MOMENT-1 before and after fine-tuning")
    parser.add_argument("--holdout-run", required=True); parser.add_argument("--loso-run", required=True)
    parser.add_argument("--features", default=str(ROOT / "data/features/emg_features_public.csv"))
    parser.add_argument("--skip-200ms", action="store_true", help="skip the slow 200 ms classical models (about 15 min)")
    args = parser.parse_args(argv)
    import torch
    torch.manual_seed(42); np.random.seed(42)
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    data, synthetic, labels = load_windows(DATA)
    runs = {"holdout": Path(args.holdout_run), "loso": Path(args.loso_run)}
    folds = {k: read_folds(ROOT / v if not v.is_absolute() else v) for k, v in runs.items()}
    rows, recalls = [], []

    if not args.skip_200ms:
        feats = pd.read_csv(args.features)
        healthy, syn = feats[feats.cohort == "healthy"], feats[feats.cohort == "stroke_synthetic"]
        to_idx = lambda s: s.map(labels.index).to_numpy()
        h = (healthy[FEATURES].to_numpy(), to_idx(healthy.label), healthy.subject_id.astype(str).to_numpy())
        s = (syn[FEATURES].to_numpy(), to_idx(syn.label))
        for evaluation in ("holdout", "loso"):
            classical_on(h, folds[evaluation], s, evaluation, "Classical, 200 ms windows", labels, rows, recalls, "200 ms")

    fx, fs = window_features(data["X"], data["mask"]), window_features(synthetic["X"], synthetic["mask"])
    for evaluation in ("holdout", "loso"):
        classical_on((fx, data["y"], data["subject"]), folds[evaluation], (fs, synthetic["y"]), evaluation, "Classical, 5.12 s windows", labels, rows, recalls, "5.12 s")

    for revin, note in ((False, "calibrated"), (True, "RevIN")):
        model = build_model("small", len(labels), device, revin)
        model.eval()
        if not revin:
            for evaluation in ("holdout", "loso"):
                for f in folds[evaluation]:
                    test = np.isin(data["subject"], f["test"])
                    score(evaluation, "MOMENT untrained head", "MOMENT before fine-tuning", "before", "+".join(f["test"]), "healthy",
                          data["y"][test], logits_predict(model, data["X"][test], data["mask"][test], device), labels, rows, recalls)
        ex, es = embeddings(model, data["X"], data["mask"], device), embeddings(model, synthetic["X"], synthetic["mask"], device)
        for evaluation in ("holdout", "loso"):
            classical_on((ex, data["y"], data["subject"]), folds[evaluation], (es, synthetic["y"]), evaluation,
                         "MOMENT before fine-tuning", labels, rows, recalls, f"frozen MOMENT, {note}")

    for evaluation, run in runs.items():
        metrics = pd.read_csv((ROOT / run) / "metrics.csv")
        for r in metrics[metrics.phase == "linear_probe"].itertuples():
            rows.append({"evaluation": evaluation, "method": "MOMENT linear probe (head trained)", "family": "MOMENT after fine-tuning", "stage": "after",
                         "fold": r.fold, "test": "healthy", "accuracy": r.accuracy, "macro_f1": r.macro_f1, "n": r.n_test})
        for f in folds[evaluation]:
            model, _, _ = load_finetuned(f["dir"], device)
            test = np.isin(data["subject"], f["test"]); fold = "+".join(f["test"])
            score(evaluation, "MOMENT LoRA (fine-tuned)", "MOMENT after fine-tuning", "after", fold, "healthy",
                  data["y"][test], logits_predict(model, data["X"][test], data["mask"][test], device), labels, rows, recalls)
            score(evaluation, "MOMENT LoRA (fine-tuned)", "MOMENT after fine-tuning", "after", fold, "synthetic",
                  synthetic["y"], logits_predict(model, synthetic["X"], synthetic["mask"], device), labels, rows, recalls)
            saved = metrics[(metrics.phase == "lora") & (metrics.fold == fold) & ~metrics.test.str.contains("synthetic")].accuracy.iloc[0]
            print(f"  {evaluation} reloaded LoRA {fold}: {rows[-2]['accuracy']:.3f} (training run reported {saved:.3f})", flush=True)

    table = pd.DataFrame(rows)
    tables = ROOT / "results/tables"; tables.mkdir(parents=True, exist_ok=True)
    table.to_csv(tables / "model_comparison.csv", index=False)
    recall_rows = []
    for (evaluation, method), group in pd.DataFrame(recalls).groupby(["evaluation", "method"], sort=False):
        y_true, y_pred = np.concatenate(group.y_true.to_list()), np.concatenate(group.y_pred.to_list())
        per = recall_score(y_true, y_pred, labels=range(len(labels)), average=None, zero_division=0)
        recall_rows.append({"evaluation": evaluation, "method": method, **{l: round(float(v), 4) for l, v in zip(labels, per)}})
    pd.DataFrame(recall_rows).to_csv(tables / "model_comparison_recall.csv", index=False)
    summary = table.groupby(["evaluation", "test", "family", "method"], sort=False)[["accuracy", "macro_f1"]].mean().round(4)
    summary.to_csv(tables / "model_comparison_summary.csv")
    print(summary.to_string())
    plot(table, ROOT / "docs/figures/model_comparison.png")
    print(f"Saved results/tables/model_comparison*.csv and docs/figures/model_comparison.png")

if __name__ == "__main__": main()
