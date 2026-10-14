# Stage 7: fine-tuning MOMENT-1 (pending approval)

**Status:** prepared, not run. Nothing is installed or downloaded until the project owner approves.

## Why MOMENT-1

[MOMENT](https://huggingface.co/AutonLab/MOMENT-1-small) is a family of open time-series foundation models from Carnegie Mellon's Auton Lab, pretrained on a large public time-series collection.

| Criterion | MOMENT-1 | TinyMyo (EMG-specific) |
|---|---|---|
| Licence | MIT: fine-tuned weights can be shared | CC BY-ND 4.0: modified weights (including LoRA) may not be shared |
| Input | Any number of channels, 512 time steps: fits single-channel EMG | Built around multi-channel raw sEMG |
| Classification head | Built in (`task_name="classification"`) | Task heads in a separate repo |
| Hardware | small (about 40M parameters) runs on an Apple M3 Pro (MPS) | Small, also fine |

MOMENT-1-small is the first target; `--size base` is the next step if small helps.

## What the script does

`src/models/finetune_moment.py`:

1. Cuts each healthy-volunteer recording (`healthy_raw`) into 512-sample windows with a 256-sample step: 1,722 windows over 11 subjects and 7 gestures.
2. Normalises per subject (z-score over that subject's whole signal), keeping relative amplitude between gestures.
3. Uses the subject splits in `results/splits.json`, written by the baseline, so both are scored on the same held-out people:
    - `--split holdout`: train on H01-H08 (H08 as validation), test on H09-H11
    - `--split loso`: 11 folds, comparable with the baseline's 28.8% leave-one-subject-out accuracy
4. **Phase A:** linear probe, training only the classification head on the frozen encoder (up to 15 epochs, lr 1e-3, early stopping).
5. **Phase B:** LoRA (rank 8) on the encoder's attention q/v projections plus the head (up to 15 epochs, lr 2e-4).
6. Writes `results/tables/moment_<size>_<split>_metrics.csv`, a confusion matrix, and the adapter to `src/models/saved/`.

## Commands (after approval)

```bash
uv pip install --python .venv/bin/python -r requirements-finetune.txt   # torch, momentfm, peft
python -m src.models.finetune_moment --check-data                        # works now, no torch
python -m src.models.finetune_moment --split holdout                     # first run
python -m src.models.finetune_moment --split loso                        # final comparison
```

The first run downloads the MOMENT-1-small weights from Hugging Face (MIT licence). The `momentfm` keyword arguments follow the model card; if the installed version differs, the script is adjusted before training.

## How the result is used

The fine-tuned model stays an offline research comparison against the LDA/SVM/RF baseline. Runtime game control remains camera-driven, as the system design requires. A gain would support future work on EMG-assisted control (for example with a second channel), not a change to the current prototype.
