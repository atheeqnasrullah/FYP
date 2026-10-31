# MOMENT-1 fine-tuning run `small_loso_db1_pretrain_20261031-205339`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `loso`. Git commit: `77a2626caa`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S02 | 32.9% | 0.301 |
| lora | S02 | 32.2% | 0.251 |
| lora | SP02 (stroke patient) | 51.2% | 0.473 |
| lora | SP03 (stroke patient) | 70.4% | 0.661 |
| linear_probe | S03 | 24.6% | 0.196 |
| lora | S03 | 28.9% | 0.246 |
| lora | SP02 (stroke patient) | 56.1% | 0.529 |
| lora | SP03 (stroke patient) | 70.1% | 0.666 |
| linear_probe | S04 | 44.4% | 0.377 |
| lora | S04 | 46.5% | 0.391 |
| lora | SP02 (stroke patient) | 50.2% | 0.492 |
| lora | SP03 (stroke patient) | 67.4% | 0.629 |
| linear_probe | S05 | 47.2% | 0.478 |
| lora | S05 | 46.8% | 0.471 |
| lora | SP02 (stroke patient) | 55.1% | 0.526 |
| lora | SP03 (stroke patient) | 73.1% | 0.700 |
| linear_probe | S06 | 67.4% | 0.670 |
| lora | S06 | 67.8% | 0.671 |
| lora | SP02 (stroke patient) | 50.8% | 0.491 |
| lora | SP03 (stroke patient) | 68.1% | 0.644 |
| linear_probe | S07 | 57.5% | 0.569 |
| lora | S07 | 59.5% | 0.580 |
| lora | SP02 (stroke patient) | 52.8% | 0.513 |
| lora | SP03 (stroke patient) | 73.8% | 0.706 |
| linear_probe | S08 | 44.5% | 0.421 |
| lora | S08 | 48.8% | 0.485 |
| lora | SP02 (stroke patient) | 53.8% | 0.517 |
| lora | SP03 (stroke patient) | 61.8% | 0.586 |
| linear_probe | S09 | 46.2% | 0.451 |
| lora | S09 | 49.2% | 0.486 |
| lora | SP02 (stroke patient) | 53.5% | 0.508 |
| lora | SP03 (stroke patient) | 62.8% | 0.602 |
| linear_probe | S10 | 76.7% | 0.751 |
| lora | S10 | 82.1% | 0.819 |
| lora | SP02 (stroke patient) | 50.8% | 0.492 |
| lora | SP03 (stroke patient) | 63.8% | 0.610 |
| linear_probe | S11 | 73.4% | 0.711 |
| lora | S11 | 84.7% | 0.845 |
| lora | SP02 (stroke patient) | 48.2% | 0.456 |
| lora | SP03 (stroke patient) | 70.8% | 0.660 |
| linear_probe | S12 | 76.1% | 0.757 |
| lora | S12 | 88.0% | 0.869 |
| lora | SP02 (stroke patient) | 45.8% | 0.425 |
| lora | SP03 (stroke patient) | 70.1% | 0.649 |
| linear_probe | S13 | 82.4% | 0.785 |
| lora | S13 | 93.7% | 0.936 |
| lora | SP02 (stroke patient) | 45.8% | 0.427 |
| lora | SP03 (stroke patient) | 70.4% | 0.661 |
| linear_probe | S14 | 82.4% | 0.822 |
| lora | S14 | 83.4% | 0.829 |
| lora | SP02 (stroke patient) | 52.2% | 0.501 |
| lora | SP03 (stroke patient) | 76.4% | 0.716 |
| linear_probe | S15 | 84.4% | 0.844 |
| lora | S15 | 79.4% | 0.784 |
| lora | SP02 (stroke patient) | 48.8% | 0.464 |
| lora | SP03 (stroke patient) | 60.8% | 0.531 |
| linear_probe | S16 | 78.4% | 0.766 |
| lora | S16 | 87.7% | 0.880 |
| lora | SP02 (stroke patient) | 50.8% | 0.488 |
| lora | SP03 (stroke patient) | 66.8% | 0.628 |
| linear_probe | S17 | 84.4% | 0.835 |
| lora | S17 | 89.4% | 0.892 |
| lora | SP02 (stroke patient) | 48.8% | 0.471 |
| lora | SP03 (stroke patient) | 59.1% | 0.519 |
| linear_probe | S18 | 83.7% | 0.810 |
| lora | S18 | 87.0% | 0.868 |
| lora | SP02 (stroke patient) | 46.8% | 0.439 |
| lora | SP03 (stroke patient) | 70.1% | 0.662 |
| linear_probe | S19 | 75.1% | 0.729 |
| lora | S19 | 84.4% | 0.845 |
| lora | SP02 (stroke patient) | 48.5% | 0.466 |
| lora | SP03 (stroke patient) | 74.4% | 0.708 |
| linear_probe | S20 | 81.4% | 0.811 |
| lora | S20 | 90.7% | 0.907 |
| lora | SP02 (stroke patient) | 50.5% | 0.487 |
| lora | SP03 (stroke patient) | 62.1% | 0.592 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_loso_db1_pretrain_20261031-205339/folds/S20 <csv files>`
