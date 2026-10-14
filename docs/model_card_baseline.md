# Model card: offline EMG gesture baseline

| Item | Value |
|---|---|
| File | `src/models/saved/emg_model.joblib` (not committed) |
| Content | `{"model": sklearn Pipeline, "features": [...], "labels": [...], "trained_on", "subject_norm"}` |
| Model | StandardScaler + SVM (RBF, C=10), chosen by best leave-one-subject-out accuracy among LDA, SVM, RF |
| Input | 8 features of one 200 ms window of single-channel EMG: RMS, MAV, VAR, STD, PEAK, WL, ZC, SSC |
| Output | One of 7 labels: Hand_Close, Hand_Open, Pronation, Rest, Supination, Wrist_Extension, Wrist_Flexion |
| Training data | 11 healthy volunteers, `Datasets/Noraml People data/raw_signals`, 4,578 windows (654 per class) |
| Intended use | Offline research comparison only. **Not used to control games** and not a clinical tool |

## Performance (chance 14.3%)

| Evaluation | Accuracy | Macro F1 |
|---|---|---|
| Leave-one-subject-out | 28.8% | 0.253 |
| Within-subject (first 70% of each recording train, last 30% test, 2-window gap) | 35.9% | 0.326 |
| Train healthy, test simulated patients (synthetic) | 14.3% | 0.036 |

Full table for all models and variants: `docs/testing_and_evaluation.md`.

## Limitations

- Single channel, about 6 s per gesture per person: too little information to tell wrist and hand gestures apart reliably.
- No per-user calibration in the saved model; per-subject z-scoring (`--subject-norm`) raises LDA cross-subject accuracy to 29.7% but needs that subject's unlabelled data.
- Amplitude units differ between sources (mV-scaled ADC vs synthetic mV); the model does not transfer to the simulated patients.
- The simulated patients are synthetic and appear derived from volunteers 1-3.

## Ethics

Trained on coded healthy-volunteer data. Do not use its output for clinical decisions.
