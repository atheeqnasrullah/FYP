"""Preprocess Dataset/ into model-ready windows for MOMENT-1 fine-tuning.

Steps, per subject and movement file:
  1. Segment   split at gaps over 1 s or backwards timestamps (public_datasets)
  2. Resample  put each segment on an exact 10 ms grid; dropped samples
               (S01 has about 2,400 gaps) are filled by linear interpolation
               and flagged
  3. Transform log1p(adc): the envelope is zero-heavy and long-tailed
               (0 to 4095), so the log keeps Rest and Hand_Close on one scale
  4. Calibrate z-score with the subject's own mean and spread (label-free,
               like a per-patient calibration), then clip to +/-CLIP. This
               keeps relative activity between movements, which per-window
               normalisation (MOMENT's RevIN) would erase
  5. Window    512 samples (5.12 s at 100 Hz) every --step samples, inside a
               segment only; segments shorter than a window but at least
               --min-samples long are left-padded and masked
  6. Filter    exclude a whole subject whose recordings are more than
               --max-interp interpolated (S01 lost 26-50% of samples in
               every file and has no Rest file), then drop single windows
               above the same limit

Output in data/processed/moment/ (not committed):
  windows.npz    X [n, 1, 512] float32, mask [n, 512] uint8, y [n] int,
                 subject, cohort, label, segment, start_ms, interp_frac,
                 saturated_frac
  manifest.csv   one row per window
  metadata.json  parameters, label order, counts, calibration statistics,
                 class weights, dropped-window counts

  python -m src.data.prepare_finetune
"""
import argparse, json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from src.utils.config import ROOT
from src.data.public_datasets import FS, STEP_MS, GESTURES, SOURCES, files, read_file, segment_ids

OUT_DIR = ROOT / "data/processed/moment"
SEQ_LEN = 512
CLIP = 6.0
ADC_MAX = 4095


def resample_segment(t, x):
    """Values on an exact STEP_MS grid from the first to the last timestamp, plus an interpolated flag."""
    grid = np.arange(t[0], t[-1] + 1, STEP_MS, dtype=float)
    values = np.interp(grid, t, x)
    observed = np.isin(grid, t)
    return grid, values, ~observed


def segments_from_frame(df, subject, label, cohort):
    """Continuous segments of one recording (columns timestamp_ms, adc_value), resampled to the 10 ms grid."""
    t = df.timestamp_ms.to_numpy(float); x = pd.to_numeric(df.adc_value, errors="coerce").to_numpy(float)
    seg = segment_ids(t); records = []
    for s in np.unique(seg):
        keep = (seg == s) & np.isfinite(x)
        if keep.sum() < 2: continue
        grid, values, interp = resample_segment(t[keep], x[keep])
        records.append({"subject": subject, "cohort": cohort, "label": label,
                        "segment": f"{subject}_{label}_{s}", "t": grid, "adc": values, "interp": interp})
    return records


def load_segments(source):
    """One record per continuous segment: resampled raw ADC values and flags."""
    records = []
    for path in files(source):
        df = read_file(path)
        records += segments_from_frame(df, str(df.subject_id.iloc[0]), str(df.movement_label.iloc[0]), SOURCES[source]["cohort"])
    return records


def calibration(records):
    """Per-subject mean and standard deviation of log1p(adc) over all of that subject's samples."""
    stats = {}
    for subject in sorted({r["subject"] for r in records}):
        z = np.concatenate([np.log1p(r["adc"]) for r in records if r["subject"] == subject])
        stats[subject] = {"mean": float(z.mean()), "std": float(z.std() or 1.0), "samples": int(z.size)}
    return stats


def windows_from(record, stats, step, min_samples, max_interp):
    z = (np.log1p(record["adc"]) - stats["mean"]) / stats["std"]
    z = np.clip(z, -CLIP, CLIP).astype(np.float32)
    n = len(z); out, dropped = [], 0
    if n >= SEQ_LEN:
        spans = [(s, s + SEQ_LEN) for s in range(0, n - SEQ_LEN + 1, step)]
    elif n >= min_samples:
        spans = [(0, n)]  # one left-padded, masked window
    else:
        return out, 0
    for a, b in spans:
        interp = record["interp"][a:b]
        if interp.mean() > max_interp:
            dropped += 1; continue
        x = np.zeros(SEQ_LEN, np.float32); mask = np.zeros(SEQ_LEN, np.uint8)
        x[SEQ_LEN - (b - a):] = z[a:b]; mask[SEQ_LEN - (b - a):] = 1
        out.append({"X": x, "mask": mask, "start_ms": float(record["t"][a]), "length": b - a,
                    "interp_frac": float(interp.mean()), "saturated_frac": float(np.mean(record["adc"][a:b] >= ADC_MAX))})
    return out, dropped


def interpolated_share(records):
    by_subject = {}
    for r in records:
        a, b = by_subject.get(r["subject"], (0, 0))
        by_subject[r["subject"]] = (a + int(r["interp"].sum()), b + len(r["interp"]))
    return {k: a / b for k, (a, b) in by_subject.items()}


def build(step=128, min_samples=256, max_interp=0.25):
    rows, arrays, dropped, segments = [], {"X": [], "mask": []}, {}, 0
    stats_all, excluded = {}, {}
    for source in SOURCES:
        records = load_segments(source)
        for subject, share in interpolated_share(records).items():
            if share > max_interp:
                excluded[subject] = f"{share:.0%} of samples interpolated (limit {max_interp:.0%})"
        records = [r for r in records if r["subject"] not in excluded]
        segments += len(records)
        stats = calibration(records); stats_all.update(stats)
        for r in records:
            wins, lost = windows_from(r, stats[r["subject"]], step, min_samples, max_interp)
            dropped[r["subject"]] = dropped.get(r["subject"], 0) + lost
            for w in wins:
                arrays["X"].append(w.pop("X")); arrays["mask"].append(w.pop("mask"))
                rows.append({"subject": r["subject"], "cohort": r["cohort"], "label": r["label"], "segment": r["segment"], **w})
    manifest = pd.DataFrame(rows)
    X = np.stack(arrays["X"])[:, None, :]; mask = np.stack(arrays["mask"])
    return X, mask, manifest, stats_all, dropped, segments, excluded


def class_weights(labels):
    counts = labels.value_counts()
    weights = len(labels) / (len(counts) * counts)
    return {label: round(float(weights.get(label, 0.0)), 4) for label in GESTURES}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preprocess Dataset/ into MOMENT-1 fine-tuning windows")
    parser.add_argument("--step", type=int, default=128, help="samples between window starts (128 = 1.28 s, 75%% overlap)")
    parser.add_argument("--min-samples", type=int, default=256, help="shorter segments are skipped; shorter than 512 are padded and masked")
    parser.add_argument("--max-interp", type=float, default=0.25, help="drop windows with a larger fraction of interpolated samples")
    parser.add_argument("--out", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    X, mask, manifest, stats, dropped, segments, excluded = build(args.step, args.min_samples, args.max_interp)
    labels = list(GESTURES); y = manifest.label.map(labels.index).to_numpy(np.int64)
    out = __import__("pathlib").Path(args.out); out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "windows.npz", X=X, mask=mask, y=y, labels=np.array(labels),
                        # Plain unicode arrays (not object), so the file loads with allow_pickle=False.
                        subject=manifest.subject.to_numpy(str), cohort=manifest.cohort.to_numpy(str), label=manifest.label.to_numpy(str),
                        segment=manifest.segment.to_numpy(str), start_ms=manifest.start_ms.to_numpy(float),
                        interp_frac=manifest.interp_frac.to_numpy(np.float32), saturated_frac=manifest.saturated_frac.to_numpy(np.float32))
    manifest.to_csv(out / "manifest.csv", index_label="window")
    healthy = manifest[manifest.cohort == "healthy"]
    meta = {
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Dataset/", "fs_hz": FS, "seq_len": SEQ_LEN, "window_s": SEQ_LEN / FS, "step": args.step,
        "min_samples": args.min_samples, "max_interp": args.max_interp, "transform": "log1p(adc), per-subject z-score, clip",
        "clip": CLIP, "labels": labels, "segments": segments, "windows": int(len(manifest)),
        "padded_windows": int((manifest.length < SEQ_LEN).sum()),
        "windows_by_cohort": manifest.cohort.value_counts().to_dict(),
        "windows_by_subject_label": manifest.pivot_table(index="subject", columns="label", values="start_ms", aggfunc="size", fill_value=0).astype(int).to_dict(orient="index"),
        "excluded_subjects": excluded,
        "dropped_windows_by_subject": {k: v for k, v in dropped.items() if v},
        "calibration": stats, "class_weights_healthy": class_weights(healthy.label),
        "note": "stroke_synthetic is generated data; train on cohort == healthy only",
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2))
    print(f"Saved {len(manifest)} windows ({meta['padded_windows']} padded) from {segments} segments to {out}")
    print(manifest.pivot_table(index="subject", columns="label", values="start_ms", aggfunc="size", fill_value=0).reindex(columns=labels, fill_value=0))
    if excluded: print("Excluded subjects:", excluded)
    if meta["dropped_windows_by_subject"]: print("Dropped windows (too much interpolation):", meta["dropped_windows_by_subject"])

if __name__ == "__main__": main()
