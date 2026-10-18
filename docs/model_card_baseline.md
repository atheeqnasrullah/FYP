# Model card: offline EMG gesture baseline

> **Status:** trained on 2026-10-14 on the old `Datasets/` folder, which was deleted on 2026-10-16. Retrain on `Dataset/` once the loader is migrated ([known_issues.md](known_issues.md)).

| Item | Value |
|---|---|
| File | `src/models/saved/emg_model.joblib` (not committed) |
| Content | `{"model": sklearn Pipeline, "features": [...], "labels": [...], "trained_on", "subject_norm"}` |
| Model | StandardScaler + SVM (RBF, C=10), chosen by best leave-one-subject-out accuracy among LDA, SVM and RF |
| Input | 8 features of one 200 ms window of single-channel EMG: RMS, MAV, VAR, STD, PEAK, WL, ZC, SSC |
| Output | One of 7 labels: Hand_Close, Hand_Open, Pronation, Rest, Supination, Wrist_Extension, Wrist_Flexion |
| Training data | 11 healthy volunteers (old `Datasets/`), 4,578 windows (654 per class) |
| Intended use | Offline research comparison only. **Not used to control games** and not a clinical tool |

Note that the new `Dataset/` uses a different label set (Rest, Hand_Open, Hand_Close, Left, Right, Up, Down) and a 100 Hz sample rate, so a retrained model will not be comparable label for label.

## Performance (chance 14.3%)

| Evaluation | Accuracy | Macro F1 |
|---|---|---|
| Leave-one-subject-out | 28.8% | 0.253 |
| Within-subject (first 70% of each recording train, last 30% test, 2-window gap) | 35.9% | 0.326 |
| Train healthy, test synthetic patients | 14.3% | 0.036 |

## Limitations

- Single channel and about 6 s per gesture per person: too little information to tell wrist and hand gestures apart.
- No per-user calibration in the saved model; per-subject z-scoring (`--subject-norm`) raised LDA cross-subject accuracy to 29.7% but needs that subject's unlabelled data.
- Did not transfer to the synthetic patients (different amplitude scale).

## Ethics

Trained on coded healthy-volunteer data. Do not use its output for clinical decisions.
