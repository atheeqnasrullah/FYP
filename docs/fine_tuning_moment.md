# Fine-tuning stage: MOMENT-1

**Status (2026-10-28): done on all current data.** MOMENT-1-small was fine-tuned again from the pinned base model on all 19 usable volunteers (S02-S20), with freshly built windows; nothing from earlier runs was reused. LoRA reaches 68.2% leave-one-subject-out (82.2% on the S18-S20 holdout), 2.6 points above training the head alone, and 57.5% on the two stroke patients. It does not overtake frozen MOMENT features + random forest (72.1%); full comparison in [model_comparison.md](model_comparison.md). The earlier 8-volunteer runs (45.9% LOSO) are kept for reference.

> **Correction (2026-10-21).** Runs before this date did not fine-tune the encoder: MOMENT enables gradient checkpointing by default, and with a frozen encoder that blocks every gradient to the LoRA adapters, so only the head trained. `build_model` now passes `enable_gradient_checkpointing: False`, the smoke test fails if the adapters do not move after one step, and all runs were repeated. The invalid runs were removed from `models/moment/`.

## Why MOMENT-1

[MOMENT](https://huggingface.co/AutonLab/MOMENT-1-small) is a family of open time-series foundation models from Carnegie Mellon's Auton Lab ([paper](https://arxiv.org/abs/2402.03885)).

| Criterion | MOMENT-1 (chosen) | [TinyMyo](https://huggingface.co/MatteoFasulo/TinyMyo) (EMG-specific) |
|---|---|---|
| Licence | MIT: fine-tuned weights can be shared | CC BY-ND 4.0: modified weights, including LoRA adapters, may not be shared |
| Input | Any channel count, 512 time steps: fits single-channel EMG | Designed for multi-channel raw sEMG |
| Classification | Built-in head (`task_name="classification"`) | Task heads in a separate repository |
| Hardware | Small: 35.3M parameters, runs on an Apple M3 Pro (MPS) | Small (3.6M parameters) |

## Data preprocessing

`python -m src.data.prepare_finetune` (runs in the main `.venv` in under a second) turns `Dataset/` into `data/processed/moment/`:

| Step | What happens | Why |
|---|---|---|
| 1. Segment | Split each file at gaps over 1 s or backwards timestamps | Some files join several recordings; a window must not span two |
| 2. Resample | Put each segment on an exact 10 ms grid; fill dropped samples by linear interpolation and flag them | MOMENT expects evenly spaced samples |
| 3. Exclude | Leave out any subject with more than 25% interpolated samples: **S01 (39%)** | S01 lost 26-50% of samples in every file and has no Rest file; training on filled-in data would be training on invented signal |
| 4. Transform | `log1p(adc)` | The envelope is zero-heavy and long-tailed (0 to 4095); the log keeps Rest (about 38) and Hand_Close (about 885) on one usable scale |
| 5. Calibrate | z-score with each subject's own mean and spread (no labels used), clip to +/-6 | Removes person-to-person gain differences, like a per-patient calibration, while keeping the activity difference between movements |
| 6. Window | 512 samples (5.12 s) every 128 samples (75% overlap), inside one segment; shorter segments of at least 256 samples are left-padded and masked | MOMENT's fixed input length; overlap gives more training windows |
| 7. Filter | Drop single windows with more than 25% interpolated samples | Quality control |

**Why per-subject calibration instead of MOMENT's own normalisation:** MOMENT's `classify()` normally applies RevIN, which rescales every window to zero mean and unit spread. That would erase each window's activity level, the very thing that separates Rest, Hand_Open and Hand_Close (the baseline recalls them at 81%, 46% and 65%, while directions are near chance). The training script therefore replaces RevIN with a pass-through and relies on step 5. `--revin` turns MOMENT's normalisation back on for comparison.

**Output:**

| File | Contents |
|---|---|
| `windows.npz` | `X` [n, 1, 512] float32, `mask` [n, 512], `y`, `labels`, `subject`, `cohort`, `label`, `segment`, `start_ms`, `interp_frac`, `saturated_frac` (no pickled objects) |
| `manifest.csv` | One row per window with the same fields |
| `metadata.json` | Parameters, label order, counts per subject and movement, calibration statistics, class weights, excluded subjects |

**Result (2026-10-28):** 6,407 windows from 150 segments, none padded or dropped. The earlier 2,795-window set is kept in `data/processed/moment_old_20261018/`.

| Subject | Rest | Hand_Open | Hand_Close | Left | Right | Up | Down |
|---|---|---|---|---|---|---|---|
| S02, S03, S05-S20 (each) | 43 | 43 | 43 | 43 | 43 | 43 | 43 |
| S04 | 43 | 86 | 86 | 43 | 43 | 86 | 0 |
| SP02, SP03 (stroke patients, test only, each) | 43 | 43 | 43 | 43 | 43 | 43 | 43 |

That is 5,805 healthy windows for training and testing, and 602 stroke-patient windows used only as an extra test; each patient is scored on their own. Classes are nearly balanced; `--class-weights` applies class weights to the loss.

Options: `--step` (default 128), `--min-samples` (256), `--max-interp` (0.25), `--out`.

## Subject splits

Splits come from `results/splits.json`, written by the baseline with S01 excluded, so MOMENT and LDA/SVM/RF are scored on the same people.

| Split | Train | Validation (early stopping) | Test |
|---|---|---|---|
| `holdout` | S02-S16 | S17 | S18, S19, S20: 903 windows, 129 per movement |
| `loso` | All but two subjects | The last remaining training subject | One subject per fold, 19 folds |

The 8-volunteer splits used before 2026-10-28 are kept in `results/splits_old_20261021.json`.

**Baseline to beat (same 19 subjects, S01 excluded, `results/tables/baseline_finetune_subjects_metrics.csv`):**

| Model | Leave-one-subject-out | Within-subject | Stroke patients `SP02` + `SP03` |
|---|---|---|---|
| LDA | 40.8% | 41.2% | 23.3% |
| SVM | **43.8%** (macro F1 0.419) | **44.7%** | 30.7% |
| Random forest | 41.6% | 42.1% | **31.6%** |

The baseline classifies 200 ms windows from 8 features; MOMENT sees 5.12 s of raw envelope per decision, so it has more context. Report both window lengths when comparing.

## Separate environment

`momentfm` 0.1.4 pins NumPy 1.25.2 and transformers 4.33.3. Installing it into the main `.venv` would downgrade NumPy and break pandas 3, SciPy 1.17 and scikit-learn 1.9, so fine-tuning uses its own environment, `.venv-finetune` (ignored by git):

```bash
uv venv --python 3.11 .venv-finetune
uv pip install --python .venv-finetune/bin/python -r requirements-finetune.txt
```

Installed and tested: torch 2.14.1 (MPS available), momentfm 0.1.4, peft 0.13.2, transformers 4.33.3, NumPy 1.25.2, pandas 2.1.4, scikit-learn 1.3.2.

## Training plan

1. **Phase A, linear probe:** frozen encoder, train only the classification head (3,591 parameters); up to 15 epochs, learning rate 1e-3, early stopping after 4 epochs without validation improvement.
2. **Phase B, LoRA:** rank-8 adapters on the encoder's attention q and v projections plus the head (118,279 trainable parameters); up to 15 epochs, learning rate 2e-4, same early stopping. Gradient checkpointing is switched off so gradients reach the adapters.
3. Evaluate both phases on the held-out subjects, and the LoRA model also on the stroke patient.
4. Save everything about the run in one committed folder, `models/moment/<run>/` (next section).

## Outputs and sharing

Every run creates `models/moment/<size>_<split>_<YYYYmmdd-HHMMSS>/`, which is tracked by git, and adds a row to `models/moment/runs.csv`:

| File | Contents |
|---|---|
| `folds/<test subjects>/adapter_model.safetensors` | The fine-tuned weights: LoRA adapters and the trained classification head (0.48 MB per fold) |
| `folds/<test subjects>/adapter_config.json`, `fold.json` | LoRA settings; train, validation and test subjects |
| `run.json` | Base model and pinned revision, labels, all arguments, environment versions, git commit, results summary |
| `preprocessing.json` | The preprocessing used (calibration statistics, window settings, excluded subjects) |
| `metrics.csv`, `epochs.csv` | Accuracy and macro F1 per fold and phase; validation accuracy per epoch |
| `confusion.png`, `train_log.txt`, `README.md` | Confusion matrix, full console log, readable summary |

Folds are saved as they finish, so an interrupted run keeps its completed folds.

The 150 MB base model is not committed (GitHub's limit is 100 MB per file). It is pinned to Hugging Face revision `411e288267f82cce86296dbe4d6c8bc533cc162f` and downloaded once on each laptop, so pinned base + committed adapter rebuilds exactly the same model everywhere.

**On another laptop:**

```bash
git pull
uv venv --python 3.11 .venv-finetune
uv pip install --python .venv-finetune/bin/python -r requirements-finetune.txt
.venv-finetune/bin/python -m src.models.moment_predict --adapter models/moment/<run>/folds/<fold> "Dataset/Healthy_person/S07/*.csv"
```

`moment_predict` applies the same preprocessing to the given recordings (all from one person, calibrated with that person's own level), writes per-window predictions to `results/moment_predictions.csv`, prints the most common prediction per file, and reports accuracy when a `movement_label` column exists. In Python: `load_finetuned(adapter_dir)` in `src/models/finetune_moment.py`.

Verified before training: a model saved in this layout and reloaded gives identical outputs (maximum difference 0.0), and `moment_predict` reproduces the training calibration for S07 (mean 2.853).

## Results (2026-10-28, 19 volunteers)

MOMENT-1-small, no RevIN, trained from the pinned base on the rebuilt windows, same splits as the classical models; times on an M3 Pro GPU. Chance is 14.3%.

| Run folder | Split | Head only (Phase A) | LoRA (Phase B) | `SP02` | `SP03` | Time |
|---|---|---|---|---|---|---|
| `small_holdout_newdata_20261027-230705` | holdout (test S18-S20) | 74.9% | **82.2%** | 48.5% | 64.8% | 4 min |
| `small_loso_newdata_20261027-231047` | loso, 19 folds | 65.7% | **68.2%** | 51.6% | 63.5% | 6.5 h (about 1.5 h awake; the laptop slept during folds S07-S09) |

LoRA LOSO accuracy is 44.4% on the original volunteers S02-S09 and 85.6% on the new S10-S20; per-volunteer values are in [model_comparison.md](model_comparison.md#per-volunteer-loso-accuracy). LoRA per movement (LOSO recall): Rest 85%, Hand_Open 85%, Hand_Close 80%, Left 66%, Right 49%, Up 37%, Down 74%.

What the results show:

- **LoRA fine-tuning works:** +2.6 points over the head alone (LOSO) and +7.3 on the holdout.
- **More volunteers helped a lot:** 68.2% LOSO against 45.9% with 8 volunteers, mostly because the new volunteers are easier; on S02-S09 it is 44.4%, about the same as before.
- **It is still not the best model:** frozen MOMENT features + random forest reach 72.1% LOSO, and an SVM on 5.12 s window features 71.7%.

For a single model to use, take the holdout adapter (`small_holdout_newdata_20261027-230705/folds/S18+S19+S20`, trained on 15 volunteers) or any LOSO fold (17 volunteers).

## Results (2026-10-21, 8 volunteers)

All runs: MOMENT-1-small, no RevIN, 8 volunteers, same splits as the classical models; times on an M3 Pro GPU. Chance is 14.3%.

| Run folder | Split | Training data | Head only (Phase A) | LoRA (Phase B) | Stroke patient `SP01` | Time |
|---|---|---|---|---|---|---|
| `small_holdout_20261021-191854` | holdout | Own data | 45.5% | **48.7%** | 34.9% | 2 min |
| `small_loso_20261021-192025` | loso, 8 folds | Own data | 43.0% | **45.9%** | 49.4% | 12 min |
| `small_loso_uci_pretrain_20261021-201317` | loso, 8 folds | Pre-trained on UCI (6,288 windows), then own data | 43.0% | 45.0% | 53.9% | 49 min |
| `small_loso_epn_pretrain_20261021-193241` | loso, 8 folds | Pre-trained on EMG-EPN-612 (60,000 windows, 5 epochs), then own data | 40.3% | 44.6% | **55.4%** | 41 min |
| `small_loso_epn_extra_20261021-210209` | loso, 8 folds | Own data + 3,000 EMG-EPN-612 windows (Rest, Hand_Open, Hand_Close) | 42.4% | 45.4% | 47.2% | 30 min |

LoRA per movement (LOSO recall, own data): Rest 65%, Hand_Open 82%, Hand_Close 74%, Left 31%, Right 21%, Up 17%, Down 26%. Hand_Open is recognised better than by any other method; directions stay near chance.

What the results show:

- **LoRA fine-tuning works:** +2.9 points over the head alone (LOSO) and +3.2 on the holdout.
- **It is not the best model:** frozen MOMENT features + random forest reach 48.1% LOSO, and an SVM on 5.12 s window features 47.3%.
- **Public data did not help our volunteers:** every public-data run is 0.5-1.3 points below own-data fine-tuning. Pre-training learned the public data (EMG-EPN-612: 53.7% on held-out public people) but transferred poorly to the MD0437 signal. It did help the stroke patient (`SP01`: 55.4% vs 49.4%).

Pre-trained runs keep the public-data adapter in `pretrain/`. The public-data runs have not been repeated on 19 volunteers.

## Commands

From `FYP/`:

```bash
.venv/bin/python -m src.data.prepare_finetune                              # 1. preprocess
.venv-finetune/bin/python -m src.models.finetune_moment --check-data       # 2. windows and folds
.venv-finetune/bin/python -m src.models.finetune_moment --smoke            # 3. one step per phase, saves nothing
.venv-finetune/bin/python -m src.models.finetune_moment --split holdout    # 4. first real run
.venv-finetune/bin/python -m src.models.finetune_moment --split loso       # 5. final comparison (19 folds)
.venv-finetune/bin/python -m src.models.moment_predict --adapter models/moment/<run>/folds/<fold> <csv files>   # 6. use it
```

Other options: `--size base`, `--probe-epochs`, `--lora-epochs`, `--lora-rank`, `--batch-size`, `--patience`, `--class-weights`, `--revin`, `--data`, `--extra-data` and `--max-extra` (public windows added to training, capped and label-balanced), `--pretrain-data`, `--max-pretrain` and `--pretrain-epochs` (pre-train LoRA on public data), `--tag` (name in the run folder).

## Smoke test result (2026-10-21)

```text
2494 healthy windows of 512 samples, 7 classes, 8 subjects, 1 fold(s); 301 stroke-patient windows for extra testing
linear probe: logits (32, 7), loss 1.938, trainable 3,591 of 35,340,999 parameters on mps
LoRA: logits (32, 7), loss 1.941, trainable 118,279 of 35,459,278 parameters on mps
LoRA adapters after one step: |B| = 4.91e+00
save and reload: max logit difference 0.00e+00
Smoke test passed: ready to fine-tune.
```

The smoke test checks three things: one training step per phase, that the LoRA adapters actually change (LoRA B starts at zero and must move; this check would have caught the gradient-checkpointing bug), and that a model saved in the run layout reloads with identical outputs. It also handles one incompatibility: peft 0.13 reads the model config like a dictionary, and MOMENT's config has no `.get()`, so `add_lora()` adds one.

With real LoRA training a step takes 0.108 s per batch of 32 (0.043 s for the head alone), using about 1.3 GB of GPU memory.

## How the result is used

The fine-tuned model stays an offline research comparison. Game control remains camera-driven. A gain would support future work on EMG-assisted control, not a change to the current prototype.
