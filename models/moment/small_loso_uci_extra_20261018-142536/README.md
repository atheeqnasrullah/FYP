# MOMENT-1 fine-tuning run `small_loso_uci_extra_20261018-142536`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `ac507bc71a`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 12.6% | 0.116 |
| lora | S02 | 17.9% | 0.163 |
| lora | SYN_STROKE_01 (synthetic) | 44.5% | 0.377 |
| linear_probe | S03 | 15.0% | 0.099 |
| lora | S03 | 15.0% | 0.107 |
| lora | SYN_STROKE_01 (synthetic) | 44.9% | 0.393 |
| linear_probe | S04 | 47.8% | 0.407 |
| lora | S04 | 50.4% | 0.427 |
| lora | SYN_STROKE_01 (synthetic) | 43.9% | 0.402 |
| linear_probe | S05 | 50.8% | 0.432 |
| lora | S05 | 52.2% | 0.459 |
| lora | SYN_STROKE_01 (synthetic) | 40.9% | 0.337 |
| linear_probe | S06 | 41.2% | 0.346 |
| lora | S06 | 43.2% | 0.375 |
| lora | SYN_STROKE_01 (synthetic) | 46.5% | 0.396 |
| linear_probe | S07 | 41.5% | 0.318 |
| lora | S07 | 43.9% | 0.363 |
| lora | SYN_STROKE_01 (synthetic) | 40.2% | 0.316 |
| linear_probe | S08 | 45.2% | 0.384 |
| lora | S08 | 47.8% | 0.429 |
| lora | SYN_STROKE_01 (synthetic) | 40.5% | 0.347 |
| linear_probe | S09 | 43.2% | 0.347 |
| lora | S09 | 42.9% | 0.350 |
| lora | SYN_STROKE_01 (synthetic) | 38.2% | 0.317 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_uci_extra_20261018-142536/folds/S09 <csv files>`
