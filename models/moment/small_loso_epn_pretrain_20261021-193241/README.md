# MOMENT-1 fine-tuning run `small_loso_epn_pretrain_20261021-193241`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `734bb78779`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 35.2% | 0.293 |
| lora | S02 | 36.2% | 0.273 |
| lora | SP01 (stroke patient) | 60.8% | 0.591 |
| linear_probe | S03 | 22.3% | 0.154 |
| lora | S03 | 26.9% | 0.261 |
| lora | SP01 (stroke patient) | 53.2% | 0.489 |
| linear_probe | S04 | 48.3% | 0.369 |
| lora | S04 | 43.4% | 0.381 |
| lora | SP01 (stroke patient) | 57.8% | 0.509 |
| linear_probe | S05 | 50.5% | 0.441 |
| lora | S05 | 49.5% | 0.487 |
| lora | SP01 (stroke patient) | 49.5% | 0.490 |
| linear_probe | S06 | 44.9% | 0.387 |
| lora | S06 | 52.5% | 0.484 |
| lora | SP01 (stroke patient) | 54.5% | 0.540 |
| linear_probe | S07 | 31.6% | 0.200 |
| lora | S07 | 49.2% | 0.467 |
| lora | SP01 (stroke patient) | 46.8% | 0.441 |
| linear_probe | S08 | 48.5% | 0.426 |
| lora | S08 | 48.2% | 0.472 |
| lora | SP01 (stroke patient) | 61.5% | 0.608 |
| linear_probe | S09 | 41.2% | 0.363 |
| lora | S09 | 51.2% | 0.504 |
| lora | SP01 (stroke patient) | 58.8% | 0.572 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_epn_pretrain_20261021-193241/folds/S09 <csv files>`
