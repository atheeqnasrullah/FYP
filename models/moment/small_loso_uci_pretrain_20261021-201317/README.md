# MOMENT-1 fine-tuning run `small_loso_uci_pretrain_20261021-201317`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `734bb78779`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 36.2% | 0.262 |
| lora | S02 | 30.9% | 0.256 |
| lora | SP01 (stroke patient) | 60.1% | 0.581 |
| linear_probe | S03 | 28.6% | 0.254 |
| lora | S03 | 24.6% | 0.229 |
| lora | SP01 (stroke patient) | 54.8% | 0.531 |
| linear_probe | S04 | 49.6% | 0.404 |
| lora | S04 | 46.0% | 0.391 |
| lora | SP01 (stroke patient) | 56.1% | 0.513 |
| linear_probe | S05 | 50.5% | 0.439 |
| lora | S05 | 53.2% | 0.522 |
| lora | SP01 (stroke patient) | 60.1% | 0.589 |
| linear_probe | S06 | 42.2% | 0.349 |
| lora | S06 | 53.2% | 0.486 |
| lora | SP01 (stroke patient) | 46.2% | 0.432 |
| linear_probe | S07 | 42.5% | 0.336 |
| lora | S07 | 50.5% | 0.453 |
| lora | SP01 (stroke patient) | 43.2% | 0.364 |
| linear_probe | S08 | 50.2% | 0.441 |
| lora | S08 | 53.8% | 0.510 |
| lora | SP01 (stroke patient) | 53.5% | 0.502 |
| linear_probe | S09 | 44.5% | 0.385 |
| lora | S09 | 48.2% | 0.462 |
| lora | SP01 (stroke patient) | 57.5% | 0.568 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_uci_pretrain_20261021-201317/folds/S09 <csv files>`
