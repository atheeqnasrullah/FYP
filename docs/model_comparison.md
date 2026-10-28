# Model comparison: classical models, MOMENT-1 before and after fine-tuning, and public data

On 19 volunteers (S02-S20) and the same subject splits for every method, the best EMG movement classifier is still a **random forest on frozen (not fine-tuned) MOMENT-1 features: 72.1%** leave-one-subject-out accuracy over 7 movements (chance 14.3%). An SVM on hand-crafted features of the same 5.12 s windows is close behind (71.7%), and MOMENT-1 fine-tuned with LoRA reaches 68.2%. On the two stroke patients (never trained on), frozen MOMENT features with MOMENT's own normalisation (RevIN) do best (68.7%), and LoRA reaches 57.5%.

Results as of 2026-10-28, from `src/evaluation/compare_models.py`. The 5.12 s windows were rebuilt from all of `Dataset/` and MOMENT was fine-tuned again from the pinned base model; no earlier windows, adapters or runs were reused. Every fine-tuned model was reloaded from its saved files in `models/moment/` and reproduced its training score exactly.

> **Why the numbers rose so much since 2026-10-21 (8 volunteers, best 48.1%).** Eleven new volunteers (S10-S20) were added. They are much easier to classify than the original eight: every method scores 80-94% on them and 44-49% on S02-S09 (table below). Their recordings are consistent with each other (for example, Down is about 400 ADC on almost every one of them), while S02-S09 vary widely; no recording is a copy of another (checked: no pair of recordings correlates above 0.8). Report the results per group, not only the overall mean.

![Leave-one-subject-out accuracy of every model](figures/model_comparison.png)

## Setup

| Item | Value |
|---|---|
| Data | `Dataset/Healthy_person`, 19 volunteers (S02-S20; S01 excluded for 39% lost samples), 7 movements: Rest, Hand_Open, Hand_Close, Left, Right, Up, Down. S04 has no Down recording |
| Extra test | Stroke patients `SP02` and `SP03` (the `stroke_patient/SP01/` files are labelled `SP03` inside, see [datasets.md](datasets.md)); never trained on, 301 windows each |
| Leave-one-subject-out (LOSO) | 19 folds; each tests one volunteer. Train on 17, the 18th is MOMENT's early-stopping subject (classical models skip it) |
| Holdout | Train S02-S16, validation S17 (MOMENT only), test S18+S19+S20 (903 windows, 129 per movement) |
| Splits | Read from the saved runs (`models/moment/*_newdata_*/folds/*/fold.json`), so every method sees exactly the same people |
| Metrics | Accuracy (classes are balanced) and macro F1; chance = 1/7 = 14.3% |

## Methods

| Group | Method | Input | What is trained |
|---|---|---|---|
| Classical, 200 ms | LDA, SVM (RBF, C=10), random forest (200 trees) | 8 features (RMS, MAV, VAR, STD, PEAK, WL, ZC, SSC) of 200 ms raw-envelope windows; 80,887 healthy windows | Whole classifier |
| Classical, 5.12 s | Same three | Same 8 features of the 5.12 s preprocessed windows MOMENT sees (log1p, per-subject z-score); 5,805 healthy windows | Whole classifier |
| MOMENT before fine-tuning | Untrained head | MOMENT-1-small as downloaded, random classification head | Nothing |
| MOMENT before fine-tuning | Frozen features + LDA / SVM / RF | 512-number MOMENT embedding of each 5.12 s window; no MOMENT weight changed. Two variants: our per-subject calibration, or MOMENT's own per-window normalisation (RevIN) | Only the classical classifier |
| MOMENT after fine-tuning | Linear probe (Phase A) | 5.12 s windows | MOMENT's classification head (3,591 parameters) |
| MOMENT after fine-tuning | LoRA (Phase B) | 5.12 s windows | LoRA adapters on attention q, v + head (118,279 parameters) |

## Results: leave-one-subject-out (19 volunteers)

| Group | Method | Accuracy | Macro F1 | Both stroke patients |
|---|---|---|---|---|
| Classical, 200 ms | LDA | 40.7% | 0.397 | 23.6% |
| Classical, 200 ms | SVM | 43.8% | 0.418 | 29.2% |
| Classical, 200 ms | Random forest | 41.4% | 0.399 | 30.7% |
| Classical, 5.12 s | LDA | 67.7% | 0.664 | 43.4% |
| Classical, 5.12 s | SVM | 71.7% | 0.698 | 42.1% |
| Classical, 5.12 s | Random forest | 70.8% | 0.698 | 35.0% |
| MOMENT before fine-tuning | Untrained head | 16.0% | 0.070 | - |
| MOMENT before fine-tuning | Frozen + LDA (calibrated) | 65.8% | 0.649 | 52.4% |
| MOMENT before fine-tuning | Frozen + SVM (calibrated) | 69.8% | 0.684 | 49.2% |
| MOMENT before fine-tuning | **Frozen + random forest (calibrated)** | **72.1%** | **0.710** | 55.4% |
| MOMENT before fine-tuning | Frozen + LDA (RevIN) | 53.8% | 0.523 | 64.7% |
| MOMENT before fine-tuning | Frozen + SVM (RevIN) | 57.9% | 0.561 | 67.2% |
| MOMENT before fine-tuning | Frozen + random forest (RevIN) | 58.3% | 0.563 | **68.7%** |
| MOMENT after fine-tuning | Linear probe | 65.7% | 0.636 | - |
| MOMENT after fine-tuning | LoRA | 68.2% | 0.670 | 57.5% |

Patient values are the mean of the 19 fold models, over both patients' windows.

## Results: holdout (test S18, S19, S20)

| Group | Method | Accuracy | Macro F1 | Both stroke patients |
|---|---|---|---|---|
| Classical, 200 ms | LDA / SVM / random forest | 42.9% / 48.3% / 46.1% | 0.433 / 0.475 / 0.457 | 23.3% / 24.0% / 30.5% |
| Classical, 5.12 s | LDA / **SVM** / random forest | 86.9% / **89.8%** / 89.5% | 0.868 / **0.897** / 0.893 | 43.4% / 42.2% / 35.2% |
| MOMENT before fine-tuning | Untrained head | 16.6% | 0.075 | - |
| MOMENT before fine-tuning | Frozen + LDA / SVM / random forest (calibrated) | 78.2% / 87.2% / 88.8% | 0.776 / 0.868 / 0.884 | 52.5% / 48.2% / 53.5% |
| MOMENT before fine-tuning | Frozen + LDA / SVM / random forest (RevIN) | 61.2% / 70.7% / 69.8% | 0.617 / 0.702 / 0.691 | 61.6% / 63.0% / **65.3%** |
| MOMENT after fine-tuning | Linear probe / LoRA | 74.9% / 82.2% | 0.709 / 0.816 | - / 56.6% |

The holdout tests three of the new, easier volunteers only, so it overstates accuracy; LOSO (all 19) is the more reliable ranking.

## Results: stroke patients (fine-tuned MOMENT)

| Patient | LoRA, mean of 19 LOSO models | LoRA, holdout model |
|---|---|---|
| `SP02` | 51.6% (macro F1 0.505) | 48.5% |
| `SP03` | 63.5% (macro F1 0.584) | 64.8% |

The models were trained on healthy volunteers only. The patient recordings come from two people, and their clinical details are not documented, so these numbers show transfer to a different signal, not clinical performance. The 200 ms models stay close to chance on the patients; 5.12 s windows with calibrated or RevIN-normalised MOMENT features transfer best.

## Per movement (LOSO recall)

| Method | Rest | Hand_Open | Hand_Close | Left | Right | Up | Down |
|---|---|---|---|---|---|---|---|
| SVM, 200 ms | 79% | 50% | 66% | 25% | 26% | 18% | 41% |
| SVM, 5.12 s | 90% | 81% | **86%** | **73%** | **63%** | 37% | 71% |
| Frozen MOMENT + random forest | 89% | **88%** | 82% | 66% | 62% | **40%** | **75%** |
| MOMENT LoRA | 85% | 85% | 80% | 66% | 49% | 37% | 74% |

## Per volunteer (LOSO accuracy)

| Volunteer | SVM, 200 ms | SVM, 5.12 s | Frozen MOMENT + RF | MOMENT linear probe | MOMENT LoRA |
|---|---|---|---|---|---|
| S02 | 18.7% | 38.5% | 27.9% | 29.6% | 27.2% |
| S03 | 15.6% | 24.6% | 33.2% | 26.2% | 24.9% |
| S04 | 34.8% | 44.2% | 47.0% | 47.3% | 46.8% |
| S05 | 44.4% | 47.5% | 50.2% | 50.2% | 46.5% |
| S06 | 45.4% | 70.1% | 69.4% | 61.8% | 62.1% |
| S07 | 41.1% | 65.1% | 60.5% | 61.8% | 53.8% |
| S08 | 41.6% | 48.5% | 47.8% | 46.5% | 47.5% |
| S09 | 41.3% | 51.2% | 47.5% | 48.8% | 46.2% |
| S10 | 51.1% | 88.4% | 89.4% | 76.7% | 84.1% |
| S11 | 47.0% | 86.4% | 85.0% | 81.1% | 82.7% |
| S12 | 51.1% | 86.4% | 91.4% | 77.7% | 87.4% |
| S13 | 52.3% | 88.0% | 93.7% | 80.7% | 93.7% |
| S14 | 51.0% | 89.0% | 92.0% | 80.1% | 86.4% |
| S15 | 50.0% | 90.7% | 89.4% | 79.1% | 76.7% |
| S16 | 50.2% | 81.4% | 84.1% | 79.7% | 76.1% |
| S17 | 48.0% | 93.0% | 93.0% | 75.7% | 91.7% |
| S18 | 50.9% | 86.0% | 85.7% | 88.4% | 90.7% |
| S19 | 47.4% | 96.3% | 91.0% | 73.8% | 84.7% |
| S20 | 50.1% | 87.4% | 91.4% | 82.4% | 87.0% |
| **Mean S02-S09** | 35.4% | **48.7%** | 47.9% | 46.5% | 44.4% |
| **Mean S10-S20** | 49.9% | 88.5% | **89.6%** | 79.6% | 85.6% |
| **Mean, all 19** | 43.8% | 71.7% | **72.1%** | 65.7% | 68.2% |

## Findings

1. **More volunteers helped every method.** LOSO accuracy rose from 48.1% to 72.1% (best method) and from 45.9% to 68.2% (LoRA). Most of the rise comes from the new volunteers being easier; on the original S02-S09 the best methods stay at 48-49%, about where they were with 8 volunteers.
2. **Window length still matters most.** Moving the SVM from 200 ms to 5.12 s windows raises LOSO accuracy from 43.8% to 71.7% (+27.9 points).
3. **Frozen MOMENT features remain the best healthy-volunteer model** (72.1% with a random forest), with the 5.12 s SVM 0.4 points behind; that gap is well within the spread between volunteers.
4. **LoRA fine-tuning helps MOMENT but does not overtake frozen features.** LoRA adds 2.6 points over the linear probe (68.2% vs 65.7% LOSO; 82.2% vs 74.9% holdout) and is the best MOMENT variant on the new volunteers (85.6%), yet stays 3.9 points below frozen features + random forest overall and is weaker on S02-S09.
5. **For the patients, RevIN helps.** Per-subject calibration is best for healthy volunteers (72.1% vs 58.3%), but MOMENT's per-window normalisation transfers better to the patients (68.7% vs 55.4%), whose signal level differs from the volunteers'. This reverses the 8-volunteer finding for patients and is worth testing on more patients.
6. **The untouched model is at chance** (16.0%): MOMENT must be adapted, at least with a trained classifier on its features.
7. **Directions are now partly learnable.** With 19 volunteers, Left, Right and Down reach 49-75% recall on 5.12 s windows; Up stays weakest (37-40%). Rest, Hand_Open and Hand_Close remain the most reliable (80-90%).
8. **Volunteers differ a lot.** S02 and S03 stay near 25-38% for every method, while S13, S17 and S19 exceed 90%. Differences of a few points between the top methods should not be over-interpreted.

## Earlier result: 8 volunteers (2026-10-21)

Before S10-S20 were added, the same comparison on S02-S09 (8 LOSO folds; holdout test S07-S09) gave:

| Method | LOSO | Holdout | Stroke patient `SP01` (LOSO models) |
|---|---|---|---|
| SVM, 200 ms | 37.2% | 40.5% | 14.8% |
| SVM, 5.12 s | 47.3% | 50.2% | 43.4% |
| Frozen MOMENT + random forest (calibrated) | **48.1%** | 49.3% | **67.5%** |
| Frozen MOMENT + random forest (RevIN) | 35.3% | 29.2% | 51.0% |
| MOMENT linear probe | 43.0% | 45.5% | - |
| MOMENT LoRA | 45.9% | 48.7% | 49.4% |

Those runs (`models/moment/small_*_20261021-*`) are kept for reference; their patient `SP01` recordings have since been replaced by the `SP02`/`SP03` files.

> **Correction (2026-10-21).** Fine-tuning results published before 2026-10-21 were wrong. MOMENT enables gradient checkpointing by default; with its encoder frozen, this blocked every gradient to the LoRA adapters, so only the classification head ever trained. The fix (`enable_gradient_checkpointing: False` in `build_model`) is in place, and the smoke test fails if the adapters do not change.

## Public data (UCI and EMG-EPN-612)

Two public datasets were converted to MD0437-like windows (see [datasets.md](datasets.md#public-data)) and used in three ways, always testing on our own volunteers with the same 8 LOSO folds. This experiment was run on the 8-volunteer data (2026-10-21) and has not been repeated on 19 volunteers:

- **Public windows added:** public windows whose labels match ours (Rest, Hand_Close, Hand_Open) join every training fold (UCI: all 2,120; EMG-EPN-612: a label-balanced sample of 3,000 of 68,850).
- **Pre-trained on public:** MOMENT's LoRA adapters first learn all public gestures (UCI: 6,288 windows, 7 gestures; EMG-EPN-612: a label-balanced 60,000 of 137,700 windows, 6 gestures), then are fine-tuned on our data with a new head.
- **Features after public pre-training:** the pre-trained encoder is frozen and an SVM or random forest is trained on its features.

Held-out accuracy of the pre-training itself (public people not trained on): UCI 36.2% over 7 gestures, EMG-EPN-612 53.7% over 6 gestures.

| Method | Own data only | + UCI | + EMG-EPN-612 |
|---|---|---|---|
| SVM, 5.12 s window features (public windows added) | **47.3%** | 43.2% | 44.3% |
| Random forest, 5.12 s window features (public windows added) | 40.3% | 43.4% | 44.4% |
| SVM, frozen MOMENT features (public windows added) | 46.4% | 47.2% | 47.2% |
| Random forest, frozen MOMENT features (public windows added) | **48.1%** | 47.8% | 47.5% |
| SVM, features of the public-pre-trained encoder | 46.4% | 44.1% | 45.9% |
| SVM, public-pre-trained encoder + public windows added | 46.4% | 45.2% | 47.9% |
| Random forest, features of the public-pre-trained encoder | 48.1% | 45.2% | 45.3% |
| Random forest, public-pre-trained encoder + public windows added | 48.1% | 45.7% | 46.2% |
| MOMENT LoRA, pre-trained on public | 45.9% | 45.0% | 44.6% |
| MOMENT LoRA, public windows added | 45.9% | not re-run | 45.4% |

![Effect of EMG-EPN-612](figures/epn612_data_gain.png)

Fine-tuned MOMENT per volunteer (LOSO accuracy):

| Volunteer | Own data only | Pre-trained on UCI | Pre-trained on EMG-EPN-612 | EMG-EPN-612 windows added |
|---|---|---|---|---|
| S02 | 38.5% | 30.9% | 36.2% | 36.9% |
| S03 | 26.2% | 24.6% | 26.9% | 23.6% |
| S04 | 51.4% | 46.0% | 43.4% | 56.6% |
| S05 | 54.2% | 53.2% | 49.5% | 56.8% |
| S06 | 53.8% | 53.2% | 52.5% | 50.5% |
| S07 | 46.5% | 50.5% | 49.2% | 44.2% |
| S08 | 52.2% | 53.8% | 48.2% | 49.5% |
| S09 | 44.5% | 48.2% | 51.2% | 45.2% |
| **Mean** | **45.9%** | 45.0% | 44.6% | 45.4% |
| Stroke patient `SP01` (mean of 8 models) | 49.4% | 53.9% | **55.4%** | 47.2% |

Why the public data did not help our volunteers:

1. **Different sensor.** Both datasets come from a raw 8-channel Myo armband; the conversion to an MD0437-like envelope is an approximation, and we do not know which armband channel matches our electrode site.
2. **Different recordings.** Public gestures are short (UCI about 1.8 s; EMG-EPN-612 about 1 s of gesture inside a 5 s recording), while our volunteers hold each movement for 60 s.
3. **Only 3 shared movements.** Directions (Left/Right/Up/Down) have no public equivalent, and adding Rest/Hand_Open/Hand_Close windows tilts training toward those classes.
4. **Pre-training learns the public data well but transfers poorly.** EMG-EPN-612 pre-training reached 53.7% on its own held-out people, yet the adapted encoder made our volunteers slightly worse (44.6% vs 45.9%). It did help the stroke patient (55.4% vs 49.4%), whose signal is also unlike our healthy volunteers'.

**Conclusion:** public armband data is not a substitute for recordings from our own sensor. The most reliable ways to raise accuracy are more volunteers recorded with the MD0437 setup, the missing S01 and S04 recordings, and, for direction movements, a second EMG channel.

## What this means for the application

- Keep the camera in charge of movement labels; EMG can help with hand open/close, activity feedback and, increasingly, direction as more volunteers are recorded.
- For an EMG classifier on healthy users, use 5.12 s windows with per-subject calibration, and frozen MOMENT features + random forest (or an SVM on window features, or LoRA-fine-tuned MOMENT). For patients, test the RevIN variant as well.
- Next improvements: more volunteers like S02-S09 (the harder group) and more stroke patients, the missing S01 and S04 recordings, a second EMG channel for directions, and a short per-patient calibration recording.

## Reproduce

```bash
.venv/bin/python -m src.features.build_dataset --source public          # 200 ms features
.venv/bin/python -m src.models.train_emg --features data/features/emg_features_public.csv   # baselines + results/splits.json
.venv/bin/python -m src.data.prepare_finetune                            # 5.12 s windows (6,407)
.venv-finetune/bin/python -m src.models.finetune_moment --split holdout --tag newdata   # about 4 min
.venv-finetune/bin/python -m src.models.finetune_moment --split loso --tag newdata      # 19 folds, about 5 min each
.venv-finetune/bin/python -m src.evaluation.compare_models \
    --holdout-run models/moment/small_holdout_newdata_20261027-230705 \
    --loso-run models/moment/small_loso_newdata_20261027-231047         # about 1 hour
```

Public-data runs (8 volunteers, 2026-10-21; to repeat them exactly, restore `results/splits_old_20261021.json` as `results/splits.json` and pass `--data data/processed/moment_old_20261018/windows.npz`):

```bash
.venv/bin/python -m src.data.download_public uci_gestures epn612         # 17 MB + 5.5 GB
.venv/bin/python -m src.data.public_emg uci_gestures
.venv/bin/python -m src.data.public_emg epn612                           # 137,700 windows, about 3 min
U=data/processed/public/uci_gestures_windows.npz; E=data/processed/public/epn612_windows.npz
.venv-finetune/bin/python -m src.models.finetune_moment --split loso --pretrain-data $U --tag uci_pretrain
.venv-finetune/bin/python -m src.models.finetune_moment --split loso --pretrain-data $E --max-pretrain 60000 --pretrain-epochs 5 --tag epn_pretrain
.venv-finetune/bin/python -m src.models.finetune_moment --split loso --extra-data $E --max-extra 3000 --tag epn_extra
.venv-finetune/bin/python -m src.evaluation.public_data_gain --name epn612 --loso-run models/moment/small_loso_20261021-192025 \
    --public $E --max-extra 3000 --encoder models/moment/small_loso_epn_pretrain_20261021-193241/pretrain \
    --finetuned models/moment/small_loso_20261021-192025 models/moment/small_loso_epn_pretrain_20261021-193241 models/moment/small_loso_epn_extra_20261021-210209
.venv-finetune/bin/python -m src.evaluation.public_data_gain --name public --loso-run models/moment/small_loso_20261021-192025 \
    --public $U --encoder models/moment/small_loso_uci_pretrain_20261021-201317/pretrain \
    --finetuned models/moment/small_loso_20261021-192025 models/moment/small_loso_uci_pretrain_20261021-201317
```

Outputs: `results/tables/model_comparison*.csv`, `public_data_gain*.csv` (UCI), `epn612_data_gain*.csv`, and `docs/figures/model_comparison.png`, `public_data_gain.png`, `epn612_data_gain.png`.
