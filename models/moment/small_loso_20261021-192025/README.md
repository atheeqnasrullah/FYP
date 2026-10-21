# MOMENT-1 fine-tuning run `small_loso_20261021-192025`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `734bb78779`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 36.2% | 0.283 |
| lora | S02 | 38.5% | 0.317 |
| lora | SP01 (stroke patient) | 51.2% | 0.453 |
| linear_probe | S03 | 19.9% | 0.143 |
| lora | S03 | 26.2% | 0.238 |
| lora | SP01 (stroke patient) | 53.2% | 0.484 |
| linear_probe | S04 | 49.4% | 0.416 |
| lora | S04 | 51.4% | 0.435 |
| lora | SP01 (stroke patient) | 50.2% | 0.438 |
| linear_probe | S05 | 56.5% | 0.522 |
| lora | S05 | 54.2% | 0.514 |
| lora | SP01 (stroke patient) | 48.2% | 0.469 |
| linear_probe | S06 | 41.9% | 0.347 |
| lora | S06 | 53.8% | 0.496 |
| lora | SP01 (stroke patient) | 47.5% | 0.417 |
| linear_probe | S07 | 45.2% | 0.391 |
| lora | S07 | 46.5% | 0.418 |
| lora | SP01 (stroke patient) | 39.2% | 0.325 |
| linear_probe | S08 | 50.8% | 0.469 |
| lora | S08 | 52.2% | 0.508 |
| lora | SP01 (stroke patient) | 56.5% | 0.516 |
| linear_probe | S09 | 44.2% | 0.381 |
| lora | S09 | 44.5% | 0.413 |
| lora | SP01 (stroke patient) | 49.2% | 0.451 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_20261021-192025/folds/S09 <csv files>`
