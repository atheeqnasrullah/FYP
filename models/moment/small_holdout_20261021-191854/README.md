# MOMENT-1 fine-tuning run `small_holdout_20261021-191854`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `holdout`. Git commit: `734bb78779`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S07+S08+S09 | 45.5% | 0.401 |
| lora | S07+S08+S09 | 48.7% | 0.453 |
| lora | SP01 (stroke patient) | 34.9% | 0.282 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_holdout_20261021-191854/folds/S07+S08+S09 <csv files>`
