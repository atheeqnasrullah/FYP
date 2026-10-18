# Fine-tuning stage: MOMENT-1

**Status (2026-10-18): ready, not started.** The data loader reads `Dataset/`, the fine-tuning environment is installed, the MOMENT-1-small weights are downloaded, and a smoke test has run one training step of each phase on the Apple GPU. Training itself has not been run.

## Why MOMENT-1

[MOMENT](https://huggingface.co/AutonLab/MOMENT-1-small) is a family of open time-series foundation models from Carnegie Mellon's Auton Lab ([paper](https://arxiv.org/abs/2402.03885)).

| Criterion | MOMENT-1 (chosen) | [TinyMyo](https://huggingface.co/MatteoFasulo/TinyMyo) (EMG-specific) |
|---|---|---|
| Licence | MIT: fine-tuned weights can be shared | CC BY-ND 4.0: modified weights, including LoRA adapters, may not be shared |
| Input | Any channel count, 512 time steps: fits single-channel EMG | Designed for multi-channel raw sEMG |
| Classification | Built-in head (`task_name="classification"`) | Task heads in a separate repository |
| Hardware | Small: 35.3M parameters, runs on an Apple M3 Pro (MPS) | Small (3.6M parameters) |

## Separate environment

`momentfm` 0.1.4 pins NumPy 1.25.2 and transformers 4.33.3. Installing it into the main `.venv` would downgrade NumPy and break pandas 3, SciPy 1.17 and scikit-learn 1.9, so fine-tuning uses its own environment, `.venv-finetune` (ignored by git):

```bash
uv venv --python 3.11 .venv-finetune
uv pip install --python .venv-finetune/bin/python -r requirements-finetune.txt
```

Installed and tested versions: torch 2.14.1 (MPS available), momentfm 0.1.4, peft 0.13.2, transformers 4.33.3, NumPy 1.25.2, pandas 2.1.4, scikit-learn 1.3.2.

## Data

`src/models/finetune_moment.py` reads `Dataset/Healthy_person` through `src/data/public_datasets.py`:

- 512-sample windows (5.12 s at 100 Hz) with a 256-sample step, cut only inside continuous recording segments: **1,349 windows**, 9 subjects, 7 movements.
- Each subject's signal is z-scored over all of that subject's samples, which keeps the relative activity between movements.
- Subject splits come from `results/splits.json`, written by the baseline, so both are scored on the same people:

| Split | Train | Validation (early stopping) | Test |
|---|---|---|---|
| `holdout` | S01-S05 | S06 | S07, S08, S09 (462 windows) |
| `loso` | All but two subjects | The last remaining training subject | One subject per fold, 9 folds |

## Training plan

1. **Phase A, linear probe:** frozen encoder, train only the classification head (3,591 parameters); up to 15 epochs, learning rate 1e-3, early stopping after 4 epochs without improvement.
2. **Phase B, LoRA:** rank-8 adapters on the encoder's attention q and v projections plus the head (118,279 trainable parameters); up to 15 epochs, learning rate 2e-4, same early stopping.
3. Report accuracy and macro F1 per phase in `results/tables/moment_small_<split>_metrics.csv`, a confusion matrix in `results/figures/`, and save the last fold's adapter to `src/models/saved/moment_small_<split>/`.

**Baseline to beat:** SVM, 36.7% leave-one-subject-out on the same subjects ([testing_and_evaluation.md](testing_and_evaluation.md)). Note the baseline uses 200 ms windows and MOMENT 5.12 s windows, so MOMENT sees more context per decision.

## Commands

Run from `FYP/` with the fine-tuning environment:

```bash
.venv-finetune/bin/python -m src.models.finetune_moment --check-data       # windows and folds
.venv-finetune/bin/python -m src.models.finetune_moment --smoke            # one step per phase, saves nothing
.venv-finetune/bin/python -m src.models.finetune_moment --split holdout    # first real run
.venv-finetune/bin/python -m src.models.finetune_moment --split loso       # final comparison (9 folds)
```

Useful options: `--size base` (larger model), `--probe-epochs`, `--lora-epochs`, `--lora-rank`, `--batch-size`, `--patience`, `--norm subject|window|none`.

## Smoke test result (2026-10-18)

```text
1349 windows of 512 samples, 7 classes, 9 subjects, 1 fold(s)
linear probe: logits (32, 7), loss 2.109, trainable 3,591 of 35,340,999 parameters on mps
LoRA: logits (32, 7), loss 2.114, trainable 118,279 of 35,459,278 parameters on mps
Smoke test passed: ready to fine-tune.
```

The smoke test found and fixed one incompatibility: peft 0.13 reads the model config like a dictionary, and MOMENT's config has no `.get()`, so `add_lora()` adds one before wrapping the model.

## How the result is used

The fine-tuned model stays an offline research comparison. Game control remains camera-driven. A gain would support future work on EMG-assisted control, not a change to the current prototype.
