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
    model = MOMENTPipeline.from_pretrained(MODEL_IDS[size], model_kwargs={
        "task_name": "classification", "n_channels": 1, "num_class": n_classes,
        "freeze_encoder": True, "freeze_embedder": True, "freeze_head": False, "reduction": "mean"})
    model.init()
    if not revin:
        class KeepLevel(torch.nn.Module):
            """Stands in for RevIN: inputs are already calibrated per subject."""
            def forward(self, x, mode="norm", mask=None): return x
        model.normalizer = KeepLevel()
    return model.to(device)


def add_lora(model, rank):
    from peft import LoraConfig, get_peft_model
    # peft reads model.config like a dict; MOMENT's config is a namespace without .get().
    config = getattr(model, "config", None)
    if config is not None and not hasattr(config, "get"):
        config.get = lambda key, default=None: getattr(config, key, default)
    return get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=.1, target_modules=["q", "v"],
                                            modules_to_save=["head"]))


def run_epochs(model, train, val, epochs, lr, device, patience, weights=None):
    import torch
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-4)
    loss_fn = torch.nn.CrossEntropyLoss(weight=None if weights is None else torch.tensor(weights, dtype=torch.float32, device=device))
    best, best_state, wait = -1.0, None, 0
    for epoch in range(epochs):
        model.train()
        for xb, mb, yb in train:
            opt.zero_grad(); loss = loss_fn(model(x_enc=xb.to(device), input_mask=mb.to(device)).logits, yb.to(device)); loss.backward(); opt.step()
        acc = (predict(model, val, device) == val.dataset.tensors[2].numpy()).mean()
        print(f"  epoch {epoch + 1}: val accuracy {acc:.3f}", flush=True)
        if acc > best: best, wait = acc, 0; best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            wait += 1
            if wait >= patience: break
    model.load_state_dict(best_state)
    return best


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
    with tempfile.TemporaryDirectory() as tmp:
        model.save_pretrained(tmp)  # the full run saves the adapter the same way
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
    def loader(part, m, shuffle):
        tensors = (torch.from_numpy(part["X"][m]), torch.from_numpy(part["mask"][m].astype(np.float32)), torch.from_numpy(part["y"][m]))
        return DataLoader(TensorDataset(*tensors), batch_size=args.batch_size, shuffle=shuffle)
    every_synthetic = np.ones(len(synthetic["y"]), bool)
    rows, all_true, all_pred = [], [], []
    for test in test_sets:
        test_mask = np.isin(groups, test)
        train_subjects = sorted(set(groups[~test_mask])); val_subject = train_subjects[-1]
        val_mask = groups == val_subject; train_mask = ~test_mask & ~val_mask
        print(f"Fold test={test} val={val_subject} train={[s for s in train_subjects if s != val_subject]} on {device}", flush=True); started = time.time()
        model = build_model(args.size, len(labels), device, args.revin)
        print(" Phase A: linear probe"); run_epochs(model, loader(data, train_mask, True), loader(data, val_mask, False), args.probe_epochs, 1e-3, device, args.patience, weights)
        probe = predict(model, loader(data, test_mask, False), device)
        print(" Phase B: LoRA"); model = add_lora(model, args.lora_rank).to(device)
        run_epochs(model, loader(data, train_mask, True), loader(data, val_mask, False), args.lora_epochs, 2e-4, device, args.patience, weights)
        lora = predict(model, loader(data, test_mask, False), device); true = data["y"][test_mask]
        results = [("linear_probe", "+".join(test), true, probe), ("lora", "+".join(test), true, lora)]
        if len(synthetic["y"]):
            results.append(("lora", "SYN_STROKE_01 (synthetic)", synthetic["y"], predict(model, loader(synthetic, every_synthetic, False), device)))
        for phase, tested, y_true, pred in results:
            rows.append({"model": f"MOMENT-1-{args.size}", "phase": phase, "split": args.split, "fold": "+".join(test), "test": tested,
                         "accuracy": accuracy_score(y_true, pred), "macro_f1": f1_score(y_true, pred, average="macro"), "n_test": len(y_true),
                         "minutes": round((time.time() - started) / 60, 1)})
            print(f"  {phase} on {tested}: accuracy {rows[-1]['accuracy']:.3f}")
        all_true.append(true); all_pred.append(lora)
    metrics = pd.DataFrame(rows); tag = f"moment_{args.size}_{args.split}"
    (ROOT / "results/tables").mkdir(parents=True, exist_ok=True)
    metrics.to_csv(ROOT / f"results/tables/{tag}_metrics.csv", index=False)
    print(metrics.groupby(["phase", metrics.test.str.contains("synthetic").map({True: "synthetic", False: "healthy"})])[["accuracy", "macro_f1"]].mean().round(3))
    from src.models.train_emg import save_confusion
    true, pred = np.concatenate(all_true), np.concatenate(all_pred)
    save_confusion([labels[i] for i in true], [labels[i] for i in pred], labels, f"MOMENT-1-{args.size} LoRA ({args.split})", ROOT / f"results/figures/confusion_{tag}.png")
    dest = ROOT / f"src/models/saved/{tag}"; dest.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(dest); (dest / "labels.json").write_text(json.dumps(labels))
    (dest / "training_args.json").write_text(json.dumps(vars(args), indent=2))
    print(f"Saved metrics to results/tables/{tag}_metrics.csv and the last fold's adapter to {dest}")

if __name__ == "__main__": main()
