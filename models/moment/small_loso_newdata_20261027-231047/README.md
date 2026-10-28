# MOMENT-1 fine-tuning run `small_loso_newdata_20261027-231047`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `7a38377d12`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 29.6% | 0.219 |
| lora | S02 | 27.2% | 0.205 |
| lora | SP02 (stroke patient) | 46.2% | 0.438 |
| lora | SP03 (stroke patient) | 59.8% | 0.521 |
| linear_probe | S03 | 26.2% | 0.171 |
| lora | S03 | 24.9% | 0.200 |
| lora | SP02 (stroke patient) | 56.8% | 0.552 |
| lora | SP03 (stroke patient) | 65.1% | 0.597 |
| linear_probe | S04 | 47.3% | 0.400 |
| lora | S04 | 46.8% | 0.387 |
| lora | SP02 (stroke patient) | 43.2% | 0.430 |
| lora | SP03 (stroke patient) | 57.8% | 0.502 |
| linear_probe | S05 | 50.2% | 0.525 |
| lora | S05 | 46.5% | 0.467 |
| lora | SP02 (stroke patient) | 57.5% | 0.553 |
| lora | SP03 (stroke patient) | 66.1% | 0.622 |
| linear_probe | S06 | 61.8% | 0.603 |
| lora | S06 | 62.1% | 0.618 |
| lora | SP02 (stroke patient) | 53.5% | 0.533 |
| lora | SP03 (stroke patient) | 58.8% | 0.539 |
| linear_probe | S07 | 61.8% | 0.600 |
| lora | S07 | 53.8% | 0.534 |
| lora | SP02 (stroke patient) | 50.5% | 0.505 |
| lora | SP03 (stroke patient) | 60.8% | 0.558 |
| linear_probe | S08 | 46.5% | 0.465 |
| lora | S08 | 47.5% | 0.472 |
| lora | SP02 (stroke patient) | 53.8% | 0.528 |
| lora | SP03 (stroke patient) | 62.1% | 0.570 |
| linear_probe | S09 | 48.8% | 0.478 |
| lora | S09 | 46.2% | 0.465 |
| lora | SP02 (stroke patient) | 54.8% | 0.539 |
| lora | SP03 (stroke patient) | 61.8% | 0.579 |
| linear_probe | S10 | 76.7% | 0.741 |
| lora | S10 | 84.1% | 0.837 |
| lora | SP02 (stroke patient) | 55.8% | 0.552 |
| lora | SP03 (stroke patient) | 62.5% | 0.584 |
| linear_probe | S11 | 81.1% | 0.791 |
| lora | S11 | 82.7% | 0.822 |
| lora | SP02 (stroke patient) | 53.5% | 0.523 |
| lora | SP03 (stroke patient) | 61.1% | 0.561 |
| linear_probe | S12 | 77.7% | 0.762 |
| lora | S12 | 87.4% | 0.852 |
| lora | SP02 (stroke patient) | 48.5% | 0.470 |
| lora | SP03 (stroke patient) | 62.5% | 0.569 |
| linear_probe | S13 | 80.7% | 0.788 |
| lora | S13 | 93.7% | 0.936 |
| lora | SP02 (stroke patient) | 49.8% | 0.500 |
| lora | SP03 (stroke patient) | 62.5% | 0.587 |
| linear_probe | S14 | 80.1% | 0.797 |
| lora | S14 | 86.4% | 0.864 |
| lora | SP02 (stroke patient) | 53.8% | 0.530 |
| lora | SP03 (stroke patient) | 69.1% | 0.647 |
| linear_probe | S15 | 79.1% | 0.784 |
| lora | S15 | 76.7% | 0.768 |
| lora | SP02 (stroke patient) | 52.2% | 0.505 |
| lora | SP03 (stroke patient) | 59.1% | 0.524 |
| linear_probe | S16 | 79.7% | 0.796 |
| lora | S16 | 76.1% | 0.774 |
| lora | SP02 (stroke patient) | 51.2% | 0.497 |
| lora | SP03 (stroke patient) | 68.8% | 0.645 |
| linear_probe | S17 | 75.7% | 0.748 |
| lora | S17 | 91.7% | 0.914 |
| lora | SP02 (stroke patient) | 51.5% | 0.504 |
| lora | SP03 (stroke patient) | 69.1% | 0.651 |
| linear_probe | S18 | 88.4% | 0.881 |
| lora | S18 | 90.7% | 0.907 |
| lora | SP02 (stroke patient) | 51.8% | 0.510 |
| lora | SP03 (stroke patient) | 67.8% | 0.635 |
| linear_probe | S19 | 73.8% | 0.721 |
| lora | S19 | 84.7% | 0.843 |
| lora | SP02 (stroke patient) | 47.8% | 0.465 |
| lora | SP03 (stroke patient) | 65.4% | 0.600 |
| linear_probe | S20 | 82.4% | 0.823 |
| lora | S20 | 87.0% | 0.870 |
| lora | SP02 (stroke patient) | 47.8% | 0.465 |
| lora | SP03 (stroke patient) | 65.4% | 0.600 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_newdata_20261027-231047/folds/S20 <csv files>`
