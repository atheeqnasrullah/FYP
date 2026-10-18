# MOMENT-1 fine-tuning run `small_loso_uci_pretrain_extra_20261018-144800`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `ac507bc71a`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 24.9% | 0.198 |
| lora | S02 | 30.6% | 0.246 |
| lora | SYN_STROKE_01 (synthetic) | 43.9% | 0.387 |
| linear_probe | S03 | 14.0% | 0.094 |
| lora | S03 | 13.6% | 0.101 |
| lora | SYN_STROKE_01 (synthetic) | 42.9% | 0.376 |
| linear_probe | S04 | 47.8% | 0.397 |
| lora | S04 | 49.6% | 0.408 |
| lora | SYN_STROKE_01 (synthetic) | 45.2% | 0.409 |
| linear_probe | S05 | 57.1% | 0.532 |
| lora | S05 | 57.5% | 0.543 |
| lora | SYN_STROKE_01 (synthetic) | 45.8% | 0.408 |
| linear_probe | S06 | 42.2% | 0.342 |
| lora | S06 | 42.5% | 0.366 |
| lora | SYN_STROKE_01 (synthetic) | 41.2% | 0.334 |
| linear_probe | S07 | 41.5% | 0.345 |
| lora | S07 | 42.5% | 0.364 |
| lora | SYN_STROKE_01 (synthetic) | 41.5% | 0.335 |
| linear_probe | S08 | 48.5% | 0.429 |
| lora | S08 | 48.8% | 0.432 |
| lora | SYN_STROKE_01 (synthetic) | 41.5% | 0.351 |
| linear_probe | S09 | 43.5% | 0.393 |
| lora | S09 | 43.5% | 0.388 |
| lora | SYN_STROKE_01 (synthetic) | 40.5% | 0.366 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_uci_pretrain_extra_20261018-144800/folds/S09 <csv files>`
