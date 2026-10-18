"""Fine-tune MOMENT-1 (AutonLab, MIT licence) as an offline EMG gesture classifier.

Research only: games keep using camera labels. Requires requirements-finetune.txt
(torch, momentfm, peft) and downloads weights from Hugging Face on first use.

  python -m src.models.finetune_moment --check-data          # no torch needed
  python -m src.models.finetune_moment --smoke               # install check: one batch, no training
  python -m src.models.finetune_moment --split holdout       # quick run
  python -m src.models.finetune_moment --split loso          # comparable with baseline LOSO

Data: Dataset/ healthy volunteers at 100 Hz, so one 512-sample window covers
5.12 s. Windows are cut inside continuous recording segments only.

Phase A trains only the classification head on the frozen encoder (linear probe).
Phase B adds LoRA adapters to the encoder attention (q, v) and trains them with
the head. Splits come from results/splits.json, written by src.models.train_emg,
so MOMENT and the LDA/SVM/RF baseline are scored on the same held-out subjects.
"""
import argparse, json, time
import numpy as np, pandas as pd
from src.utils.config import ROOT

SEQ_LEN = 512          # MOMENT-1 input length
STEP = 256
MODEL_IDS = {"small": "AutonLab/MOMENT-1-small", "base": "AutonLab/MOMENT-1-base", "large": "AutonLab/MOMENT-1-large"}


def make_windows(source="healthy", norm="subject"):
    """Return X [n, 1, 512], labels, subject ids. norm=subject keeps relative amplitude within a subject."""
    from src.data.public_datasets import load_source
    data = load_source(source)
    X, y, groups = [], [], []
    for subject, part in data.groupby("subject_id"):
        scale = part.emg_value.std() or 1.0; centre = part.emg_value.mean()
        for (trial, label), rec in part.groupby(["trial_id", "label"]):
            x = rec.emg_value.to_numpy(float)
            if norm == "subject": x = (x - centre) / scale
            for start in range(0, len(x) - SEQ_LEN + 1, STEP):
                w = x[start:start + SEQ_LEN]
                if norm == "window": w = (w - w.mean()) / (w.std() or 1.0)
                X.append(w); y.append(label); groups.append(subject)
    return np.asarray(X, np.float32)[:, None, :], np.asarray(y), np.asarray(groups)


def folds(split, subjects):
    path = ROOT / "results/splits.json"
    if not path.exists(): raise SystemExit("Run python -m src.models.train_emg --features data/features/emg_features_public.csv first (writes results/splits.json)")
    splits = json.loads(path.read_text())
    if split == "holdout": return [splits["holdout"]["test"]]
    return [f["test"] for f in splits["loso"] if f["test"][0] in subjects]


def build_model(size, n_classes, device):
    from momentfm import MOMENTPipeline
    model = MOMENTPipeline.from_pretrained(MODEL_IDS[size], model_kwargs={
        "task_name": "classification", "n_channels": 1, "num_class": n_classes,
        "freeze_encoder": True, "freeze_embedder": True, "freeze_head": False, "reduction": "mean"})
    model.init()
    return model.to(device)


def add_lora(model, rank):
    from peft import LoraConfig, get_peft_model
    # peft reads model.config like a dict; MOMENT's config is a namespace without .get().
    config = getattr(model, "config", None)
    if config is not None and not hasattr(config, "get"):
        config.get = lambda key, default=None: getattr(config, key, default)
    return get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=.1, target_modules=["q", "v"],
                                            modules_to_save=["head"]))


def run_epochs(model, train, val, epochs, lr, device, patience):
    import torch
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-4); loss_fn = torch.nn.CrossEntropyLoss()
    best, best_state, wait = -1.0, None, 0
    for epoch in range(epochs):
        model.train()
        for xb, yb in train:
            opt.zero_grad(); loss = loss_fn(model(x_enc=xb.to(device)).logits, yb.to(device)); loss.backward(); opt.step()
        acc = (predict(model, val, device) == val.dataset.tensors[1].numpy()).mean()
        print(f"  epoch {epoch + 1}: val accuracy {acc:.3f}", flush=True)
        if acc > best: best, wait = acc, 0; best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            wait += 1
            if wait >= patience: break
    model.load_state_dict(best_state)
    return best


def smoke_test(args, X, y_idx, n_classes, device):
    """Check the install end to end on one batch: model download, forward, backward, LoRA."""
    import torch
    xb, yb = torch.from_numpy(X[:args.batch_size]).to(device), torch.from_numpy(y_idx[:args.batch_size]).to(device)
    model = build_model(args.size, n_classes, device)
    for phase in ("linear probe", "LoRA"):
        if phase == "LoRA": model = add_lora(model, args.lora_rank).to(device)
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=1e-4); opt.zero_grad()
        logits = model(x_enc=xb).logits
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
        for xb, _ in loader: out.append(model(x_enc=xb.to(device)).logits.argmax(1).cpu().numpy())
    return np.concatenate(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fine-tune MOMENT-1 on the EMG gesture dataset (offline research model)")
    parser.add_argument("--size", choices=list(MODEL_IDS), default="small")
    parser.add_argument("--split", choices=["holdout", "loso"], default="holdout")
    parser.add_argument("--source", default="healthy")
    parser.add_argument("--norm", choices=["subject", "window", "none"], default="subject")
    parser.add_argument("--probe-epochs", type=int, default=15)
    parser.add_argument("--lora-epochs", type=int, default=15)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--check-data", action="store_true", help="build windows and folds only; no torch")
    parser.add_argument("--smoke", action="store_true", help="load the model, run one training step per phase on one batch, save nothing")
    args = parser.parse_args(argv)
    X, y, groups = make_windows(args.source, args.norm)
    labels = sorted(set(y)); y_idx = np.array([labels.index(v) for v in y])
    test_sets = folds(args.split, set(groups))
    print(f"{len(X)} windows of {SEQ_LEN} samples, {len(labels)} classes, {len(set(groups))} subjects, {len(test_sets)} fold(s)")
    if args.check_data:
        for test in test_sets: print(f"  test {test}: {np.isin(groups, test).sum()} windows")
        return
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.metrics import accuracy_score, f1_score
    torch.manual_seed(42); np.random.seed(42)
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    if args.smoke:
        smoke_test(args, X, y_idx, len(labels), device)
        return
    loader = lambda m, shuffle: DataLoader(TensorDataset(torch.from_numpy(X[m]), torch.from_numpy(y_idx[m])), batch_size=args.batch_size, shuffle=shuffle)
    rows, all_true, all_pred = [], [], []
    for test in test_sets:
        test_mask = np.isin(groups, test)
        train_subjects = sorted(set(groups[~test_mask])); val_subject = train_subjects[-1]
        val_mask = groups == val_subject; train_mask = ~test_mask & ~val_mask
        print(f"Fold test={test} val={val_subject} on {device}", flush=True); started = time.time()
        model = build_model(args.size, len(labels), device)
        print(" Phase A: linear probe"); run_epochs(model, loader(train_mask, True), loader(val_mask, False), args.probe_epochs, 1e-3, device, args.patience)
        probe = predict(model, loader(test_mask, False), device)
        print(" Phase B: LoRA"); model = add_lora(model, args.lora_rank).to(device)
        run_epochs(model, loader(train_mask, True), loader(val_mask, False), args.lora_epochs, 2e-4, device, args.patience)
        lora = predict(model, loader(test_mask, False), device); true = y_idx[test_mask]
        for phase, pred in (("linear_probe", probe), ("lora", lora)):
            rows.append({"model": f"MOMENT-1-{args.size}", "phase": phase, "split": args.split, "test": "+".join(test),
                         "accuracy": accuracy_score(true, pred), "macro_f1": f1_score(true, pred, average="macro"), "n_test": len(true),
                         "minutes": round((time.time() - started) / 60, 1)})
            print(f"  {phase}: accuracy {rows[-1]['accuracy']:.3f}")
        all_true.append(true); all_pred.append(lora)
    metrics = pd.DataFrame(rows); tag = f"moment_{args.size}_{args.split}"
    metrics.to_csv(ROOT / f"results/tables/{tag}_metrics.csv", index=False)
    print(metrics.groupby("phase")[["accuracy", "macro_f1"]].mean().round(3))
    from src.models.train_emg import save_confusion
    true, pred = np.concatenate(all_true), np.concatenate(all_pred)
    save_confusion([labels[i] for i in true], [labels[i] for i in pred], labels, f"MOMENT-1-{args.size} LoRA ({args.split})", ROOT / f"results/figures/confusion_{tag}.png")
    dest = ROOT / f"src/models/saved/{tag}"; dest.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(dest); (dest / "labels.json").write_text(json.dumps(labels))
    print(f"Saved metrics to results/tables/{tag}_metrics.csv and the last fold's adapter to {dest}")

if __name__ == "__main__": main()
