"""Convert public multi-channel EMG datasets into MD0437-like training windows.

Public datasets (src.data.download_public) record raw EMG with an 8-channel
Myo armband; our sensor gives one rectified, smoothed envelope at 100 Hz in
ESP32 ADC units. Each armband channel is converted separately, as if it were
one MD0437 placed at that spot (we do not know which channel matches our
electrode site, so all 8 are kept):

  1. rectify      |x|
  2. smooth       moving RMS over SMOOTH_MS (envelope, like the MD0437)
  3. resample     onto the 10 ms grid (100 Hz)
  4. gain         scale so the channel's 95th percentile matches our healthy
                  volunteers' typical 95th percentile (ADC units)
  5. windows      the same log1p + per-recording-channel z-score + 512-sample
                  windows as src.data.prepare_finetune (short gestures are
                  left-padded and masked)

Labels keep the public names. Three match ours exactly (Rest, Hand_Close =
fist, Hand_Open = extended palm / open); wrist movements keep their own names
because we do not know how they relate to our Left/Right/Up/Down.

Datasets:
  uci_gestures  36 people, all 8 channels kept (about 6,300 windows)
  epn612        EMG-EPN-612: 612 people, 150-300 labelled recordings of 5 s at 200 Hz;
                one random channel per recording by default (--channels), and
                either the marked gesture part or the full 5 s (--epn-segment)

  python -m src.data.public_emg uci_gestures
  python -m src.data.public_emg epn612 [--channels 1] [--max-users N] [--epn-segment full|gesture]
"""
import argparse, json, glob
from pathlib import Path
import numpy as np, pandas as pd
from src.utils.config import ROOT
from src.data.public_datasets import load_source, STEP_MS
from src.data.prepare_finetune import windows_from, SEQ_LEN

PUBLIC_DIR = ROOT / "Dataset/public"
OUT_DIR = ROOT / "data/processed/public"
SMOOTH_MS = 100
MIN_SAMPLES = 150  # 1.5 s: UCI gestures last about 1.8 s
SHARED = ["Rest", "Hand_Open", "Hand_Close"]
UCI_LABELS = {1: "Rest", 2: "Hand_Close", 3: "Wrist_Flexion", 4: "Wrist_Extension",
              5: "Radial_Deviation", 6: "Ulnar_Deviation", 7: "Hand_Open"}


def target_p95():
    """Typical 95th percentile of our healthy volunteers' ADC envelope (median over subjects)."""
    data = load_source("healthy")
    return float(data.groupby("subject_id").emg_value.quantile(.95).median())


def envelope(t_ms, x):
    """Rectified moving-RMS envelope on a 1 ms grid, then sampled every 10 ms."""
    fine = np.arange(t_ms[0], t_ms[-1] + 1, 1.0)
    rect = np.interp(fine, t_ms, np.abs(x))
    k = np.ones(SMOOTH_MS) / SMOOTH_MS
    rms = np.sqrt(np.convolve(rect ** 2, k, mode="same"))
    grid = np.arange(fine[0], fine[-1] + 1, STEP_MS)
    return grid, np.interp(grid, fine, rms)


def load_uci():
    """One record per gesture repetition and channel: envelope on the 10 ms grid."""
    files = sorted(glob.glob(str(PUBLIC_DIR / "uci_gestures/raw/*/*/*.txt")))
    if not files: raise SystemExit("Run python -m src.data.download_public uci_gestures first")
    records = []
    for path in files:
        subject = f"UCI{Path(path).parent.name}"; series = Path(path).name.split("_")[0]
        d = pd.read_csv(path, sep="\t").dropna()  # a few files end with incomplete rows
        runs = (d["class"] != d["class"].shift()).cumsum()
        for run_id, run in d.groupby(runs):
            cls = int(run["class"].iloc[0])
            if cls not in UCI_LABELS or len(run) < 2: continue
            t = run.time.to_numpy(float)
            for ch in range(1, 9):
                grid, env = envelope(t, run[f"channel{ch}"].to_numpy(float))
                records.append({"subject": subject, "channel": ch, "cohort": "public_uci", "label": UCI_LABELS[cls],
                                "segment": f"{subject}_s{series}_r{run_id}_ch{ch}", "t": grid, "adc": env,
                                "interp": np.zeros(len(env), bool)})
    return records


EPN_LABELS = {"noGesture": "Rest", "fist": "Hand_Close", "open": "Hand_Open",
              "waveIn": "Wrist_Flexion", "waveOut": "Wrist_Extension", "pinch": "Pinch"}
EPN_FS = 200


def load_epn(channels=1, max_users=None, segment="full", seed=0):
    """EMG-EPN-612 user JSON files (trainingJSON/ and testingJSON/), labelled samples only."""
    paths = sorted(glob.glob(str(PUBLIC_DIR / "epn612/raw/**/user*/user*.json"), recursive=True))
    if not paths: raise SystemExit("Run python -m src.data.download_public epn612 first")
    if max_users: paths = paths[:max_users]
    rng = np.random.default_rng(seed); records = []
    for i, path in enumerate(paths):
        group = "test" if "testing" in path.lower() else "train"
        user = f"EPN{group}_{Path(path).stem}"
        with open(path, encoding="utf-8") as f: data = json.load(f)
        # trainingJSON users have labels in both sample sets; testingJSON users only in trainingSamples.
        samples = [(f"{part}_{key}", sample) for part in ("trainingSamples", "testingSamples") for key, sample in data.get(part, {}).items()]
        for key, sample in samples:
            label = EPN_LABELS.get(sample.get("gestureName"))
            if label is None or "emg" not in sample: continue
            names = list(sample["emg"].keys())
            x = np.array([sample["emg"][c] for c in names], dtype=float)
            gt = sample.get("groundTruthIndex")
            if segment == "gesture" and label != "Rest" and isinstance(gt, list) and len(gt) == 2:
                x = x[:, max(0, int(gt[0]) - 1):int(gt[1])]
            if x.shape[1] < 2: continue
            t = np.arange(x.shape[1]) * (1000 / EPN_FS)
            for ch in sorted(rng.choice(len(names), min(channels, len(names)), replace=False)):
                grid, env = envelope(t, x[ch])
                records.append({"subject": user, "channel": int(ch) + 1, "cohort": "public_epn", "label": label,
                                "segment": f"{user}_{key}_ch{ch + 1}", "t": grid, "adc": env, "interp": np.zeros(len(env), bool)})
        if (i + 1) % 50 == 0: print(f"  {i + 1}/{len(paths)} users, {len(records)} recordings", flush=True)
    return records


LOADERS = {"uci_gestures": load_uci, "epn612": load_epn}


def build(name, **loader_args):
    records = LOADERS[name](**loader_args)
    target = target_p95()
    # Gain and calibration per recording channel (subject + channel), label-free like ours.
    groups = {}
    for r in records: groups.setdefault((r["subject"], r["channel"]), []).append(r)
    stats = {}
    for (subject, ch), group in groups.items():
        p95 = np.quantile(np.concatenate([r["adc"] for r in group]), .95) or 1.0
        for r in group: r["adc"] = r["adc"] * (target / p95); r["calib"] = f"{subject}_ch{ch}"
        z = np.log1p(np.concatenate([r["adc"] for r in group]))
        stats[f"{subject}_ch{ch}"] = {"mean": float(z.mean()), "std": float(z.std() or 1.0)}
    X, mask, rows = [], [], []
    for r in records:
        wins, _ = windows_from(r, stats[r["calib"]], 128, MIN_SAMPLES, 0.25)
        for w in wins:
            X.append(w.pop("X")); mask.append(w.pop("mask"))
            rows.append({"subject": r["subject"], "channel": r["channel"], "cohort": r["cohort"], "label": r["label"], "segment": r["segment"], **w})
    manifest = pd.DataFrame(rows)
    labels = sorted(manifest.label.unique(), key=lambda l: (l not in SHARED, SHARED.index(l) if l in SHARED else 0, l))
    return np.stack(X)[:, None, :], np.stack(mask), manifest, labels, target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert a public EMG dataset into MD0437-like windows")
    parser.add_argument("name", choices=list(LOADERS))
    parser.add_argument("--channels", type=int, default=1, help="epn612: armband channels kept per recording")
    parser.add_argument("--max-users", type=int, help="epn612: only the first N user files")
    parser.add_argument("--epn-segment", choices=["full", "gesture"], default="full", help="epn612: whole 5 s recording, or only the marked gesture")
    args = parser.parse_args(argv)
    extra = {"channels": args.channels, "max_users": args.max_users, "segment": args.epn_segment} if args.name == "epn612" else {}
    X, mask, manifest, labels, target = build(args.name, **extra)
    y = manifest.label.map(labels.index).to_numpy(np.int64)
    OUT_DIR.mkdir(parents=True, exist_ok=True); out = OUT_DIR / f"{args.name}_windows.npz"
    np.savez_compressed(out, X=X, mask=mask, y=y, labels=np.array(labels), subject=manifest.subject.to_numpy(str),
                        channel=manifest.channel.to_numpy(np.int64), cohort=manifest.cohort.to_numpy(str), label=manifest.label.to_numpy(str))
    meta = {"source": args.name, "windows": len(manifest), "labels": labels, "shared_with_dataset": SHARED,
            "subjects": int(manifest.subject.nunique()), "channels_per_recording": extra.get("channels", 8),
            "options": extra, "smooth_ms": SMOOTH_MS,
            "target_p95_adc": round(target, 1), "mean_valid_samples": round(float(mask.sum(1).mean()), 1), "seq_len": SEQ_LEN,
            "windows_by_label": manifest.label.value_counts().to_dict()}
    out.with_name(f"{args.name}_metadata.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))

if __name__ == "__main__": main()
