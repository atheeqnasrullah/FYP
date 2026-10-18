"""Use a saved MOMENT-1 fine-tuned model on EMG recordings of one person.

Runs in .venv-finetune. The pinned base model downloads from Hugging Face on
first use; the fine-tuned adapter comes from the repository (models/moment/).

  python -m src.models.moment_predict --adapter models/moment/<run>/folds/<fold> \\
      Dataset/Healthy_person/S07/*.csv

Input CSVs need timestamp_ms and adc_value (100 Hz MD0437 envelope, as in
Dataset/). Pass all recordings of ONE person together: they are calibrated with
that person's own mean and spread, exactly as in training (no labels used).
If a movement_label column is present, accuracy is reported too.
Writes a per-window CSV next to --out (default results/moment_predictions.csv).
"""
import argparse, glob
from pathlib import Path
import numpy as np, pandas as pd
from src.utils.config import ROOT
from src.data.prepare_finetune import segments_from_frame, calibration, windows_from


def prepare(paths, step, max_interp):
    records = []
    for path in paths:
        df = pd.read_csv(path)
        missing = {"timestamp_ms", "adc_value"} - set(df.columns)
        if missing: raise SystemExit(f"{path} lacks columns {sorted(missing)}")
        label = str(df.movement_label.iloc[0]) if "movement_label" in df else ""
        for r in segments_from_frame(df, "person", label, "input"):
            r["file"] = Path(path).name; records.append(r)
    stats = calibration(records)["person"]
    X, mask, rows = [], [], []
    for r in records:
        wins, _ = windows_from(r, stats, step, 256, max_interp)
        for w in wins:
            X.append(w.pop("X")); mask.append(w.pop("mask"))
            rows.append({"file": r["file"], "label": r["label"], **w})
    if not rows: raise SystemExit("No usable windows: recordings need at least 2.56 s of continuous signal.")
    return np.stack(X)[:, None, :], np.stack(mask).astype(np.float32), pd.DataFrame(rows), stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="Predict movements with a fine-tuned MOMENT-1 adapter")
    parser.add_argument("--adapter", required=True, help="a fold folder, e.g. models/moment/<run>/folds/S07+S08+S09")
    parser.add_argument("files", nargs="+", help="CSV recordings of one person (globs allowed)")
    parser.add_argument("--step", type=int, default=128)
    parser.add_argument("--max-interp", type=float, default=0.25)
    parser.add_argument("--out", default=str(ROOT / "results/moment_predictions.csv"))
    args = parser.parse_args(argv)
    paths = sorted({p for pattern in args.files for p in glob.glob(pattern)} or set(args.files))
    X, mask, rows, stats = prepare(paths, args.step, args.max_interp)
    import torch
    from src.models.finetune_moment import load_finetuned
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    model, labels, info = load_finetuned(args.adapter, device)
    preds, probs = [], []
    with torch.no_grad():
        for i in range(0, len(X), 64):
            logits = model(x_enc=torch.from_numpy(X[i:i + 64]).to(device), input_mask=torch.from_numpy(mask[i:i + 64]).to(device)).logits
            p = torch.softmax(logits, 1).cpu().numpy(); probs.append(p); preds.append(p.argmax(1))
    probs = np.concatenate(probs); preds = np.concatenate(preds)
    rows["predicted"] = [labels[i] for i in preds]; rows["confidence"] = probs.max(1).round(4)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True); rows.to_csv(out, index=False)
    print(f"Model {info['run_id']} ({info['base_model']}), {len(rows)} windows from {len(paths)} file(s); calibration mean {stats['mean']:.3f}, std {stats['std']:.3f}")
    summary = rows.groupby("file").agg(label=("label", "first"), windows=("predicted", "size"),
                                       most_common=("predicted", lambda s: s.value_counts().index[0]),
                                       share=("predicted", lambda s: s.value_counts(normalize=True).iloc[0]))
    print(summary.to_string())
    labelled = rows[rows.label != ""]
    if len(labelled): print(f"Window accuracy against movement_label: {(labelled.label == labelled.predicted).mean():.1%}")
    print(f"Per-window predictions: {out}")

if __name__ == "__main__": main()
