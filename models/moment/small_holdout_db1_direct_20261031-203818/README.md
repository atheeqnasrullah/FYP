# MOMENT-1 fine-tuning run `small_holdout_db1_direct_20261031-203818`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `holdout`. Git commit: `77a2626caa`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S18+S19+S20 | 75.2% | 0.748 |
| lora | S18+S19+S20 | 81.8% | 0.809 |
| lora | SP02 (stroke patient) | 46.8% | 0.430 |
| lora | SP03 (stroke patient) | 66.4% | 0.612 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_holdout_db1_direct_20261031-203818/folds/S18+S19+S20 <csv files>`
