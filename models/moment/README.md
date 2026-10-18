# Fine-tuned MOMENT-1 models

Every fine-tuning run writes one folder here, and the folders are committed to git, so anyone who pulls the repository gets the same fine-tuned models.

## What is stored, and what is downloaded

| Part | Where | Size |
|---|---|---|
| Fine-tuned weights: LoRA adapters (encoder attention q, v) + trained classification head | `<run>/folds/<test subjects>/adapter_model.safetensors` | about 0.5 MB per fold |
| Base model `AutonLab/MOMENT-1-small` | Downloaded once from Hugging Face, pinned to revision `411e288267f82cce86296dbe4d6c8bc533cc162f` (MIT licence) | 150 MB, too large for a normal git file |

Because the base revision is pinned, every laptop rebuilds exactly the same model: pinned base + the adapter from this folder.

## Run folder layout

```text
models/moment/
├── runs.csv                         one row per run: id, date, split, accuracies
└── <size>_<split>_<YYYYmmdd-HHMMSS>/
    ├── README.md                    results table and how to use it
    ├── run.json                     settings, base model + revision, labels, environment, git commit, summary
    ├── preprocessing.json           the data preprocessing used (copy of data/processed/moment/metadata.json)
    ├── metrics.csv                  accuracy and macro F1 per fold and phase (+ stroke patient)
    ├── epochs.csv                   validation accuracy per epoch
    ├── confusion.png                confusion matrix over all test folds
    ├── train_log.txt                full console output
    └── folds/<test subjects>/       adapter_config.json, adapter_model.safetensors, fold.json (train/validation/test subjects)
```

`holdout` runs have one fold (test S07+S08+S09). `loso` runs have one fold per held-out volunteer.

## Using a fine-tuned model on another laptop

```bash
git pull
uv venv --python 3.11 .venv-finetune
uv pip install --python .venv-finetune/bin/python -r requirements-finetune.txt
.venv-finetune/bin/python -m src.models.moment_predict \
    --adapter models/moment/<run>/folds/<fold> "Dataset/Healthy_person/S07/*.csv"
```

The first call downloads the pinned base model (needs internet once). Pass all recordings of one person together: they are calibrated with that person's own signal level, as in training. In Python:

```python
from src.models.finetune_moment import load_finetuned
model, labels, info = load_finetuned("models/moment/<run>/folds/<fold>", device="cpu")
```

Full details: [docs/fine_tuning_moment.md](../../docs/fine_tuning_moment.md).
