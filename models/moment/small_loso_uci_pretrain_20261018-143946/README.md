# MOMENT-1 fine-tuning run `small_loso_uci_pretrain_20261018-143946`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `ac507bc71a`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 36.5% | 0.269 |
| lora | S02 | 35.5% | 0.272 |
| lora | SYN_STROKE_01 (synthetic) | 43.2% | 0.351 |
| linear_probe | S03 | 33.6% | 0.314 |
| lora | S03 | 32.9% | 0.312 |
| lora | SYN_STROKE_01 (synthetic) | 48.5% | 0.431 |
| linear_probe | S04 | 48.6% | 0.387 |
| lora | S04 | 53.0% | 0.441 |
| lora | SYN_STROKE_01 (synthetic) | 40.9% | 0.348 |
| linear_probe | S05 | 54.2% | 0.483 |
| lora | S05 | 50.8% | 0.437 |
| lora | SYN_STROKE_01 (synthetic) | 37.9% | 0.296 |
| linear_probe | S06 | 46.5% | 0.396 |
| lora | S06 | 43.2% | 0.363 |
| lora | SYN_STROKE_01 (synthetic) | 41.2% | 0.310 |
| linear_probe | S07 | 45.5% | 0.376 |
| lora | S07 | 44.2% | 0.363 |
| lora | SYN_STROKE_01 (synthetic) | 39.5% | 0.286 |
| linear_probe | S08 | 49.5% | 0.461 |
| lora | S08 | 51.2% | 0.471 |
| lora | SYN_STROKE_01 (synthetic) | 43.2% | 0.395 |
| linear_probe | S09 | 42.9% | 0.366 |
| lora | S09 | 44.5% | 0.389 |
| lora | SYN_STROKE_01 (synthetic) | 43.2% | 0.379 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_uci_pretrain_20261018-143946/folds/S09 <csv files>`
