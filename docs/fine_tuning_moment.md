# Fine-tuning stage: MOMENT-1 (pending approval)

**Status:** model chosen and script written, nothing installed, downloaded or trained. Two things must happen first: the project owner approves, and the data loader is moved from the deleted `Datasets/` folder to `Dataset/`.

## Why MOMENT-1

[MOMENT](https://huggingface.co/AutonLab/MOMENT-1-small) is a family of open time-series foundation models from Carnegie Mellon's Auton Lab ([paper](https://arxiv.org/abs/2402.03885)).

| Criterion | MOMENT-1 (chosen) | [TinyMyo](https://huggingface.co/MatteoFasulo/TinyMyo) (EMG-specific) |
|---|---|---|
| Licence | MIT: fine-tuned weights can be shared | CC BY-ND 4.0: modified weights, including LoRA adapters, may not be shared |
| Input | Any channel count, 512 time steps: fits single-channel EMG | Designed for multi-channel raw sEMG |
| Classification | Built-in head (`task_name="classification"`) | Task heads in a separate repository |
| Hardware | Small (about 40M parameters) runs on an Apple M3 Pro (MPS) | Small (3.6M parameters) |

MOMENT-1-small is the first target; `--size base` follows if small helps.

## Data for the new dataset

At 100 Hz, one 512-sample MOMENT window covers 5.12 s of movement. With a 256-sample step, `Dataset/` gives about 1,354 healthy windows (9 subjects, 7 movements) and 154 synthetic-patient windows. Windows must not cross the time gaps in the joined S01, S02 and S04 files ([datasets.md](datasets.md)).

## Plan (`src/models/finetune_moment.py`)

1. Migrate `make_windows()` to read `Dataset/` (columns `adc_value`, `movement_label`, `subject_id`), split files at time gaps, and z-score each subject's signal.
2. Rebuild the baseline on the same data and write `results/splits.json`, so MOMENT and LDA/SVM/RF use the same held-out subjects:
    - `--split holdout`: last 3 subjects held out, the one before them used for validation;
    - `--split loso`: one fold per subject.
3. **Phase A, linear probe:** train only the classification head on the frozen encoder (up to 15 epochs, lr 1e-3, early stopping).
4. **Phase B, LoRA:** rank 8 on the encoder's q/v attention projections plus the head (up to 15 epochs, lr 2e-4).
5. Report accuracy and macro F1 next to the rebuilt baseline; save the adapter to `src/models/saved/`.

## Commands (after approval and migration)

```bash
uv pip install --python .venv/bin/python -r requirements-finetune.txt   # torch, momentfm, peft
python -m src.models.finetune_moment --check-data                        # no torch needed
python -m src.models.finetune_moment --split holdout                     # first run
python -m src.models.finetune_moment --split loso                        # final comparison
```

The first run downloads the MOMENT-1-small weights from Hugging Face. The `momentfm` keyword arguments follow the model card and are checked against the installed version before training.

## How the result is used

The fine-tuned model stays an offline research comparison. Game control remains camera-driven. A gain would support future work on EMG-assisted control, not a change to the current prototype.
