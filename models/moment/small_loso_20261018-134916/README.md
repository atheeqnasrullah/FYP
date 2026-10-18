# MOMENT-1 fine-tuning run `small_loso_20261018-134916`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `ac507bc71a`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 36.2% | 0.283 |
| lora | S02 | 35.9% | 0.283 |
| lora | SYN_STROKE_01 (synthetic) | 42.9% | 0.342 |
| linear_probe | S03 | 19.9% | 0.143 |
| lora | S03 | 21.3% | 0.149 |
| lora | SYN_STROKE_01 (synthetic) | 41.2% | 0.328 |
| linear_probe | S04 | 49.4% | 0.416 |
| lora | S04 | 50.6% | 0.426 |
| lora | SYN_STROKE_01 (synthetic) | 43.5% | 0.394 |
| linear_probe | S05 | 56.5% | 0.522 |
| lora | S05 | 55.5% | 0.509 |
| lora | SYN_STROKE_01 (synthetic) | 46.8% | 0.411 |
| linear_probe | S06 | 41.9% | 0.347 |
| lora | S06 | 43.5% | 0.372 |
| lora | SYN_STROKE_01 (synthetic) | 45.5% | 0.382 |
| linear_probe | S07 | 45.2% | 0.391 |
| lora | S07 | 43.5% | 0.370 |
| lora | SYN_STROKE_01 (synthetic) | 42.9% | 0.345 |
| linear_probe | S08 | 50.8% | 0.469 |
| lora | S08 | 50.8% | 0.458 |
| lora | SYN_STROKE_01 (synthetic) | 43.2% | 0.386 |
| linear_probe | S09 | 44.2% | 0.381 |
| lora | S09 | 44.5% | 0.386 |
| lora | SYN_STROKE_01 (synthetic) | 41.5% | 0.360 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_20261018-134916/folds/S09 <csv files>`
