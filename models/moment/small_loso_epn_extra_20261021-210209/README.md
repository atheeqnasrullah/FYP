# MOMENT-1 fine-tuning run `small_loso_epn_extra_20261021-210209`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `734bb78779`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 37.2% | 0.283 |
| lora | S02 | 36.9% | 0.301 |
| lora | SP01 (stroke patient) | 49.8% | 0.464 |
| linear_probe | S03 | 22.6% | 0.175 |
| lora | S03 | 23.6% | 0.217 |
| lora | SP01 (stroke patient) | 46.2% | 0.416 |
| linear_probe | S04 | 47.8% | 0.383 |
| lora | S04 | 56.6% | 0.463 |
| lora | SP01 (stroke patient) | 49.5% | 0.452 |
| linear_probe | S05 | 53.2% | 0.533 |
| lora | S05 | 56.8% | 0.578 |
| lora | SP01 (stroke patient) | 56.1% | 0.539 |
| linear_probe | S06 | 43.9% | 0.380 |
| lora | S06 | 50.5% | 0.451 |
| lora | SP01 (stroke patient) | 41.5% | 0.348 |
| linear_probe | S07 | 42.2% | 0.348 |
| lora | S07 | 44.2% | 0.427 |
| lora | SP01 (stroke patient) | 39.2% | 0.344 |
| linear_probe | S08 | 46.5% | 0.441 |
| lora | S08 | 49.5% | 0.482 |
| lora | SP01 (stroke patient) | 44.9% | 0.412 |
| linear_probe | S09 | 45.5% | 0.411 |
| lora | S09 | 45.2% | 0.444 |
| lora | SP01 (stroke patient) | 50.5% | 0.462 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_epn_extra_20261021-210209/folds/S09 <csv files>`
