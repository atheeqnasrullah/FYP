# Model card: offline EMG movement baseline

| Item | Value |
|---|---|
| File | `src/models/saved/emg_model.joblib` (not committed) |
| Content | `{"model": sklearn Pipeline, "features": [...], "labels": [...], "trained_on", "subject_norm"}` |
| Model | StandardScaler + SVM (RBF, C=10), chosen by best leave-one-subject-out accuracy among LDA, SVM and random forest |
| Input | 8 features of one 200 ms window (20 samples at 100 Hz) of the MD0437 envelope: RMS, MAV, VAR, STD, PEAK, WL, ZC, SSC |
| Output | One of 7 labels: Rest, Hand_Open, Hand_Close, Left, Right, Up, Down |
| Training data | `Dataset/Healthy_person`, 9 volunteers, 36,873 windows; trained 2026-10-18 |
| Intended use | Offline research comparison only. **Not used to control games** and not a clinical tool |

## Performance (chance 14.3%)

| Evaluation | Accuracy | Macro F1 |
|---|---|---|
| Leave-one-subject-out | 36.7% | 0.321 |
| Within-subject (first 70% of each recording train, last 30% test, 2-window gap) | 37.5% | 0.331 |
| Train healthy, test synthetic stroke patient `SYN_STROKE_01` (earlier file, now replaced by `SP01`) | 25.4% | 0.201 |

Recall across subjects: Rest 81%, Hand_Close 65%, Hand_Open 46%, Left 21%, Down 18%, Up 15%, Right 7%.

## Limitations

- Single channel: it separates activity levels (Rest, Hand_Open, Hand_Close) but not directions, which are near chance.
- Hand_Open is confused with Rest 43% of the time; both are low-activity.
- S01 lacks Rest and S04 lacks Down, so their folds miss a class; S01's recordings contain about 2,400 dropped-sample gaps.
- The patient result used generated data; it says nothing about real patients.

## Reproduce

```bash
python -m src.features.build_dataset --source public
python -m src.models.train_emg --features data/features/emg_features_public.csv
```

## Ethics

Trained on coded healthy-volunteer data. Do not use its output for clinical decisions.
