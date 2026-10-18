"""Fine-tune MOMENT-1 (AutonLab, MIT licence) as an offline EMG movement classifier.

Research only: games keep using camera labels. Runs in .venv-finetune
(requirements-finetune.txt) and downloads weights from Hugging Face on first use.

  python -m src.data.prepare_finetune                         # preprocess Dataset/ (main .venv is fine)
  python -m src.models.finetune_moment --check-data          # windows and folds; no torch needed
  python -m src.models.finetune_moment --smoke               # install check: one batch, no training
  python -m src.models.finetune_moment --split holdout       # quick run
  python -m src.models.finetune_moment --split loso          # comparable with baseline LOSO

Data: data/processed/moment/windows.npz from src.data.prepare_finetune:
512-sample windows (5.12 s at 100 Hz) of log1p(ADC), z-scored per subject.
Healthy volunteers train and test; the synthetic stroke patient is only an
extra test set.

MOMENT normally rescales every window to zero mean and unit spread (RevIN).
That would erase the activity level that separates Rest, Hand_Open and
Hand_Close, so RevIN is replaced by the per-subject calibration done in
preprocessing unless --revin is given.

Phase A trains only the classification head on the frozen encoder (linear probe).
Phase B adds LoRA adapters to the encoder attention (q, v) and trains them with
the head. Splits come from results/splits.json, written by src.models.train_emg,
so MOMENT and the LDA/SVM/RF baseline are scored on the same held-out subjects.
"""
import argparse, json, time
import numpy as np, pandas as pd
from src.utils.config import ROOT

SEQ_LEN = 512          # MOMENT-1 input length
DATA = ROOT / "data/processed/moment/windows.npz"
MODEL_IDS = {"small": "AutonLab/MOMENT-1-small", "base": "AutonLab/MOMENT-1-base", "large": "AutonLab/MOMENT-1-large"}
# Exact Hugging Face commit of each base model, so every laptop fine-tunes and
# loads the same weights. The 150 MB base is downloaded once (MIT licence);
# only the small fine-tuned adapters are committed to git.
MODEL_REVISIONS = {"small": "411e288267f82cce86296dbe4d6c8bc533cc162f"}
RUNS_DIR = ROOT / "models/moment"


def load_windows(path=DATA):
    """Preprocessed windows split into the healthy training pool and the synthetic test set."""
    path = __import__("pathlib").Path(path)
    if not path.exists(): raise SystemExit(f"{path} not found. Run python -m src.data.prepare_finetune first.")
    d = np.load(path, allow_pickle=False)
    labels = [str(v) for v in d["labels"]]
    pool = {k: d[k] for k in ("X", "mask", "y", "subject", "cohort")}
    healthy = pool["cohort"] == "healthy"
    split = lambda m: {k: v[m] for k, v in pool.items()}
    return split(healthy), split(~healthy), labels


def class_weights(path=DATA):
    meta = json.loads(path.with_name("metadata.json").read_text())
    return [meta["class_weights_healthy"][label] for label in meta["labels"]]


def folds(split, subjects):
    path = ROOT / "results/splits.json"
    if not path.exists(): raise SystemExit("Run python -m src.models.train_emg --features data/features/emg_features_public.csv first (writes results/splits.json)")
    splits = json.loads(path.read_text())
    if split == "holdout": return [splits["holdout"]["test"]]
    return [f["test"] for f in splits["loso"] if f["test"][0] in subjects]


def build_model(size, n_classes, device, revin=False):
    import torch
    from momentfm import MOMENTPipeline
    model = MOMENTPipeline.from_pretrained(MODEL_IDS[size], revision=MODEL_REVISIONS.get(size), model_kwargs={
        "task_name": "classification", "n_channels": 1, "num_class": n_classes,
        "freeze_encoder": True, "freeze_embedder": True, "freeze_head": False, "reduction": "mean"})
    model.init()
    if not revin:
        class KeepLevel(torch.nn.Module):
            """Stands in for RevIN: inputs are already calibrated per subject."""
            def forward(self, x, mode="norm", mask=None): return x
        model.normalizer = KeepLevel()
    return model.to(device)


def _dict_like_config(model):
    # peft reads model.config like a dict; MOMENT's config is a namespace without .get().
    config = getattr(model, "config", None)
    if config is not None and not hasattr(config, "get"):
        config.get = lambda key, default=None: getattr(config, key, default)


def add_lora(model, rank):
    from peft import LoraConfig, get_peft_model
    _dict_like_config(model)
    return get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=.1, target_modules=["q", "v"],
                                            modules_to_save=["head"]))


def load_finetuned(adapter_dir, device="cpu"):
    """Rebuild a saved fine-tuned model: pinned base + saved LoRA adapter and head.

    Returns (model, labels, run_info). adapter_dir is a fold folder inside a run,
    for example models/moment/<run>/folds/S07+S08+S09.
    """
    from peft import PeftModel
    adapter_dir = __import__("pathlib").Path(adapter_dir)
    run_dir = adapter_dir.parent.parent
    info = json.loads((run_dir / "run.json").read_text())
    model = build_model(info["size"], len(info["labels"]), device, info["revin"])
    _dict_like_config(model)
    model = PeftModel.from_pretrained(model, adapter_dir).to(device)
    model.eval()
    return model, info["labels"], info


def run_epochs(model, train, val, epochs, lr, device, patience, weights=None):
    import torch
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-4)
    loss_fn = torch.nn.CrossEntropyLoss(weight=None if weights is None else torch.tensor(weights, dtype=torch.float32, device=device))
    best, best_state, wait, history = -1.0, None, 0, []
    for epoch in range(epochs):
        model.train()
        for xb, mb, yb in train:
            opt.zero_grad(); loss = loss_fn(model(x_enc=xb.to(device), input_mask=mb.to(device)).logits, yb.to(device)); loss.backward(); opt.step()
        acc = (predict(model, val, device) == val.dataset.tensors[2].numpy()).mean()
        print(f"  epoch {epoch + 1}: val accuracy {acc:.3f}", flush=True)
        history.append({"epoch": epoch + 1, "val_accuracy": float(acc), "train_loss_last_batch": float(loss.item())})
        if acc > best: best, wait = acc, 0; best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            wait += 1
            if wait >= patience: break
    model.load_state_dict(best_state)
    return best, history


def smoke_test(args, data, n_classes, device):
    """Check the install end to end on one batch: model download, forward, backward, LoRA."""
    import torch
    pick = np.random.default_rng(0).choice(len(data["y"]), args.batch_size, replace=False)
    xb = torch.from_numpy(data["X"][pick]).to(device); yb = torch.from_numpy(data["y"][pick]).to(device)
    mb = torch.from_numpy(data["mask"][pick].astype(np.float32)).to(device)
    model = build_model(args.size, n_classes, device, args.revin)
    for phase in ("linear probe", "LoRA"):
        if phase == "LoRA": model = add_lora(model, args.lora_rank).to(device)
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=1e-4); opt.zero_grad()
        logits = model(x_enc=xb, input_mask=mb).logits
        loss = torch.nn.functional.cross_entropy(logits, yb); loss.backward(); opt.step()
        trainable = sum(p.numel() for p in params); total = sum(p.numel() for p in model.parameters())
        print(f"{phase}: logits {tuple(logits.shape)}, loss {loss.item():.3f}, trainable {trainable:,} of {total:,} parameters on {device}")
    import tempfile
    model.eval()
    with torch.no_grad(): expected = model(x_enc=xb, input_mask=mb).logits.cpu()
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = __import__("pathlib").Path(tmp)
        (run_dir / "run.json").write_text(json.dumps({"size": args.size, "revin": args.revin, "labels": [str(i) for i in range(n_classes)]}))
        model.save_pretrained(run_dir / "folds" / "smoke")  # same layout as a real run
        reloaded, _, _ = load_finetuned(run_dir / "folds" / "smoke", device)
        with torch.no_grad(): got = reloaded(x_enc=xb, input_mask=mb).logits.cpu()
    diff = float((expected - got).abs().max())
    print(f"save and reload: max logit difference {diff:.2e}")
    if diff > 1e-4: raise SystemExit("Reloaded model differs from the saved one")
    print("Smoke test passed: ready to fine-tune.")


def predict(model, loader, device):
    import torch
    model.eval(); out = []
    with torch.no_grad():
        for xb, mb, _ in loader: out.append(model(x_enc=xb.to(device), input_mask=mb.to(device)).logits.argmax(1).cpu().numpy())
    return np.concatenate(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fine-tune MOMENT-1 on the EMG gesture dataset (offline research model)")
    parser.add_argument("--size", choices=list(MODEL_IDS), default="small")
    parser.add_argument("--split", choices=["holdout", "loso"], default="holdout")
    parser.add_argument("--data", default=str(DATA), help="windows.npz from src.data.prepare_finetune")
    parser.add_argument("--revin", action="store_true", help="keep MOMENT's per-window normalisation (erases activity level)")
    parser.add_argument("--class-weights", action="store_true", help="weight the loss by inverse class frequency (metadata.json)")
    parser.add_argument("--probe-epochs", type=int, default=15)
    parser.add_argument("--lora-epochs", type=int, default=15)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--check-data", action="store_true", help="build windows and folds only; no torch")
    parser.add_argument("--smoke", action="store_true", help="load the model, run one training step per phase on one batch, save nothing")
    args = parser.parse_args(argv)
    data, synthetic, labels = load_windows(args.data)
    groups = data["subject"]
    test_sets = folds(args.split, set(groups))
    print(f"{len(data['y'])} healthy windows of {SEQ_LEN} samples, {len(labels)} classes, {len(set(groups))} subjects, "
          f"{len(test_sets)} fold(s); {len(synthetic['y'])} synthetic-patient windows for extra testing")
    if args.check_data:
        for test in test_sets:
            m = np.isin(groups, test); counts = np.bincount(data["y"][m], minlength=len(labels))
            print(f"  test {test}: {m.sum()} windows; per class " + ", ".join(f"{l} {c}" for l, c in zip(labels, counts)))
        return
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.metrics import accuracy_score, f1_score
    torch.manual_seed(42); np.random.seed(42)
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    if args.smoke:
        smoke_test(args, data, len(labels), device)
        return
    weights = class_weights(__import__("pathlib").Path(args.data)) if args.class_weights else None
    run_dir, log = start_run(args, labels, test_sets, device)
    def loader(part, m, shuffle):
        tensors = (torch.from_numpy(part["X"][m]), torch.from_numpy(part["mask"][m].astype(np.float32)), torch.from_numpy(part["y"][m]))
        return DataLoader(TensorDataset(*tensors), batch_size=args.batch_size, shuffle=shuffle)
    every_synthetic = np.ones(len(synthetic["y"]), bool)
    rows, epochs, all_true, all_pred = [], [], [], []
    for test in test_sets:
        fold = "+".join(test)
        test_mask = np.isin(groups, test)
        train_subjects = sorted(set(groups[~test_mask])); val_subject = train_subjects[-1]
        val_mask = groups == val_subject; train_mask = ~test_mask & ~val_mask
        print(f"Fold test={test} val={val_subject} train={[s for s in train_subjects if s != val_subject]} on {device}", flush=True); started = time.time()
        torch.manual_seed(42)
        model = build_model(args.size, len(labels), device, args.revin)
        print(" Phase A: linear probe")
        _, history = run_epochs(model, loader(data, train_mask, True), loader(data, val_mask, False), args.probe_epochs, 1e-3, device, args.patience, weights)
        epochs += [{"fold": fold, "phase": "linear_probe", **h} for h in history]
        probe = predict(model, loader(data, test_mask, False), device)
        print(" Phase B: LoRA"); model = add_lora(model, args.lora_rank).to(device)
        _, history = run_epochs(model, loader(data, train_mask, True), loader(data, val_mask, False), args.lora_epochs, 2e-4, device, args.patience, weights)
        epochs += [{"fold": fold, "phase": "lora", **h} for h in history]
        lora = predict(model, loader(data, test_mask, False), device); true = data["y"][test_mask]
        results = [("linear_probe", fold, true, probe), ("lora", fold, true, lora)]
        if len(synthetic["y"]):
            results.append(("lora", "SYN_STROKE_01 (synthetic)", synthetic["y"], predict(model, loader(synthetic, every_synthetic, False), device)))
        for phase, tested, y_true, pred in results:
            rows.append({"model": f"MOMENT-1-{args.size}", "phase": phase, "split": args.split, "fold": fold, "test": tested,
                         "accuracy": accuracy_score(y_true, pred), "macro_f1": f1_score(y_true, pred, average="macro"), "n_test": len(y_true),
                         "minutes": round((time.time() - started) / 60, 1)})
            print(f"  {phase} on {tested}: accuracy {rows[-1]['accuracy']:.3f}")
        all_true.append(true); all_pred.append(lora)
        # Save each fold as it finishes, so an interrupted LOSO run keeps what it has.
        fold_dir = run_dir / "folds" / fold
        model.save_pretrained(fold_dir)
        (fold_dir / "fold.json").write_text(json.dumps({"test": list(test), "validation": val_subject,
            "train": [s for s in train_subjects if s != val_subject], "labels": labels}, indent=2))
        pd.DataFrame(rows).to_csv(run_dir / "metrics.csv", index=False); pd.DataFrame(epochs).to_csv(run_dir / "epochs.csv", index=False)
    metrics = pd.DataFrame(rows)
    summary = metrics.groupby(["phase", metrics.test.str.contains("synthetic").map({True: "synthetic", False: "healthy"})])[["accuracy", "macro_f1"]].mean().round(4)
    print(summary)
    from src.models.train_emg import save_confusion
    true, pred = np.concatenate(all_true), np.concatenate(all_pred)
    save_confusion([labels[i] for i in true], [labels[i] for i in pred], labels, f"MOMENT-1-{args.size} LoRA ({args.split})", run_dir / "confusion.png")
    finish_run(run_dir, metrics, summary)
    log.close()
    print(f"Saved run to {run_dir.relative_to(ROOT)}")


class _Tee:
    """Copy console output into the run's train_log.txt."""
    def __init__(self, path):
        import sys
        self.file = open(path, "w", encoding="utf-8"); self.stdout = sys.stdout; sys.stdout = self
    def write(self, text): self.stdout.write(text); self.file.write(text)
    def flush(self): self.stdout.flush(); self.file.flush()
    def close(self):
        import sys
        sys.stdout = self.stdout; self.file.close()


def _environment(device):
    import platform, subprocess, torch, momentfm, peft, transformers
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    from importlib.metadata import version
    return {"python": platform.python_version(), "platform": platform.platform(), "device": device,
            "torch": torch.__version__, "momentfm": version("momentfm"), "peft": peft.__version__, "transformers": transformers.__version__,
            "numpy": np.__version__, "git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain"))}


def start_run(args, labels, test_sets, device):
    """Create models/moment/<run_id>/ with run.json and a console log; returns (run_dir, tee)."""
    from datetime import datetime
    run_id = f"{args.size}_{args.split}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = RUNS_DIR / run_id; (run_dir / "folds").mkdir(parents=True)
    data_path = __import__("pathlib").Path(args.data)
    meta_path = data_path.with_name("metadata.json")
    if meta_path.exists(): (run_dir / "preprocessing.json").write_text(meta_path.read_text())
    info = {"run_id": run_id, "status": "running", "created": datetime.now().astimezone().isoformat(timespec="seconds"),
            "size": args.size, "base_model": MODEL_IDS[args.size], "base_revision": MODEL_REVISIONS.get(args.size),
            "revin": args.revin, "labels": labels, "split": args.split, "folds": ["+".join(t) for t in test_sets],
            "seq_len": SEQ_LEN, "args": {k: v for k, v in vars(args).items() if k not in ("check_data", "smoke")},
            "environment": _environment(device)}
    (run_dir / "run.json").write_text(json.dumps(info, indent=2))
    return run_dir, _Tee(run_dir / "train_log.txt")


def finish_run(run_dir, metrics, summary):
    info = json.loads((run_dir / "run.json").read_text())
    healthy = metrics[~metrics.test.str.contains("synthetic")]
    info["status"] = "completed"
    info["results"] = {phase: {"accuracy": round(float(g.accuracy.mean()), 4), "macro_f1": round(float(g.macro_f1.mean()), 4)}
                       for phase, g in healthy.groupby("phase")}
    synthetic = metrics[metrics.test.str.contains("synthetic")]
    if len(synthetic): info["results"]["lora_synthetic_patient"] = {"accuracy": round(float(synthetic.accuracy.mean()), 4)}
    (run_dir / "run.json").write_text(json.dumps(info, indent=2))
    lines = [f"# MOMENT-1 fine-tuning run `{info['run_id']}`", "",
             f"Base model: [{info['base_model']}](https://huggingface.co/{info['base_model']}) at revision `{info['base_revision']}`, "
             f"{'with' if info['revin'] else 'without'} per-window RevIN. Split: `{info['split']}`. Git commit: `{info['environment']['git_commit'][:10]}`.", "",
             "| Phase | Test | Accuracy | Macro F1 |", "|---|---|---|---|"]
    lines += [f"| {r.phase} | {r.test} | {r.accuracy:.1%} | {r.macro_f1:.3f} |" for r in metrics.itertuples()]
    lines += ["", "Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,",
              "`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).", "",
              "Use it: `python -m src.models.moment_predict --adapter " + f"models/moment/{info['run_id']}/folds/{info['folds'][-1]} <csv files>`"]
    (run_dir / "README.md").write_text("\n".join(lines) + "\n")
    index = RUNS_DIR / "runs.csv"
    row = pd.DataFrame([{"run_id": info["run_id"], "created": info["created"], "size": info["size"], "split": info["split"],
                         "revin": info["revin"], "folds": len(info["folds"]),
                         **{f"{k}_accuracy": v["accuracy"] for k, v in info["results"].items()}}])
    row.to_csv(index, mode="a", header=not index.exists(), index=False)


if __name__ == "__main__": main()
