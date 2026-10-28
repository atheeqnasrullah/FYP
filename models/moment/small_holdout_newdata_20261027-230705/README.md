# MOMENT-1 fine-tuning run `small_holdout_newdata_20261027-230705`

Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small) at revision `411e288267f82cce86296dbe4d6c8bc533cc162f`, without per-window RevIN. Split: `holdout`. Git commit: `7a38377d12`.

| Phase | Test | Accuracy | Macro F1 |
|---|---|---|---|
| linear_probe | S18+S19+S20 | 74.9% | 0.709 |
| lora | S18+S19+S20 | 82.2% | 0.816 |
| lora | SP02 (stroke patient) | 48.5% | 0.466 |
| lora | SP03 (stroke patient) | 64.8% | 0.598 |

Files: `run.json` (settings, environment, summary), `metrics.csv`, `epochs.csv`, `confusion.png`, `train_log.txt`,
`preprocessing.json`, and `folds/<test subjects>/` (LoRA adapter + classification head, `fold.json`).

Use it: `python -m src.models.moment_predict --adapter models/moment/small_holdout_newdata_20261027-230705/folds/S18+S19+S20 <csv files>`
