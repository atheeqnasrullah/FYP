# MOMENT-1 fine-tuning run `small_holdout_db1_pretrain_20261031-202258`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `holdout`. Git commit: `77a2626caa`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S18+S19+S20 | 77.1% | 0.765 |
| lora | S18+S19+S20 | 85.7% | 0.850 |
| lora | SP02 (stroke patient) | 47.2% | 0.440 |
| lora | SP03 (stroke patient) | 66.8% | 0.605 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_holdout_db1_pretrain_20261031-202258/folds/S18+S19+S20 <csv files>`
