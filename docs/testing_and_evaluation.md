# Testing and evaluation

## Automated tests

`python -m pytest -q` runs 47 tests in about 30 s, and all pass (2026-10-18, Python 3.11, main environment).

| Test file | Tests | Covers |
|---|---|---|
| `test_signal_processing.py` | 4 | Feature values, envelope vs raw filtering, windowing |
| `test_fusion.py` | 3 | Confidence gate, majority smoothing, EMG features attached |
| `test_backend.py` | 5 | Patient validation, session upload, progress, CSV export, open/attempt/close flow, errors, replay mode in the web launcher |
| `test_session_sync.py` | 2 | Offline queue keeps only failed uploads |
| `test_dashboard.py` | 1 | Streamlit dashboard runs without an API |
| `test_game_logic.py` | 4 | Difficulty presets, auto level up and down, level remembered per patient, results summary |
| `test_games_headless.py` | 12 | All four games with scripted input on a hidden display: scoring, time limit, hand-position lanes, hand joystick, pick and drop by hand, latency logging |
| `test_datasets_and_models.py` | 9 | `Dataset/` loading (both groups), labels match the games, synthetic patient kept separate, segment splitting, 100 Hz feature windows, split gap, normalisation |
| `test_emg_replay.py` | 1 | Replay of `Dataset/` feeds the live pipeline |
| `test_prepare_finetune.py` | 3 | Fine-tuning preprocessing: 10 ms resampling, padding and masking, saved windows, S01 exclusion |
| `test_public_emg.py` | 3 | Public-data envelope conversion, shared labels, safe archive extraction |

The tests set `SDL_VIDEODRIVER=dummy`, a temporary database (`REHAB_DB`) and a temporary difficulty file (`REHAB_GAME_STATE`), and skip the start and results screens (`REHAB_SKIP_SCREENS`), so they never touch real data.

Fine-tuning has its own check, run in the fine-tuning environment: `python -m src.models.finetune_moment --smoke` (see [fine_tuning_moment.md](fine_tuning_moment.md)).

**Not automated yet:** a live webcam session, the ESP32 serial path, the React web app (no front-end tests; `npm run lint` and `npm run build` pass), webcam gesture accuracy, latency against the 300 ms target, and the usability (SUS) study.

## Reproducing the results

```bash
python -m src.features.build_dataset --source public       # 41,066 windows from Dataset/
python -m src.models.train_emg --features data/features/emg_features_public.csv   # about 18 min
python -m src.evaluation.emg_activity_report
```

Outputs: `results/tables/baseline_public_metrics.csv`, `data_quality.csv`, `emg_activity_by_gesture.csv`, `emg_rms_relative_to_rest.csv`; `results/figures/confusion_baseline_public_*_loso.png`, `emg_rms_by_gesture.png`, `emg_rms_relative_to_rest.png`; `results/splits.json`.

## Results: EMG movement classification (offline)

Healthy volunteers in `Dataset/` (9 subjects, 7 movements, chance 14.3%), 36,873 windows of 200 ms (20 samples at 100 Hz), 8 features per window. Run on 2026-10-18.

| Model | Leave-one-subject-out | Within-subject (70/30 in time) | Train healthy, test synthetic patient |
|---|---|---|---|
| LDA | 33.3% | 34.9% | 26.4% |
| SVM (RBF, C=10) | **36.7%** | **37.5%** | 25.4% |
| Random forest | 33.8% | 34.1% | **37.1%** |

Macro F1 for the SVM across subjects is 0.321.

With S01 excluded (the 8 subjects used for fine-tuning; `--exclude-subjects S01`), the SVM reaches 37.4% leave-one-subject-out and 39.2% within-subject; this is the baseline for MOMENT-1 ([fine_tuning_moment.md](fine_tuning_moment.md)).

Per-movement recall of the SVM across subjects (`confusion_baseline_public_SVM_loso.png`):

| Movement | Recall |
|---|---|
| Rest | 81% |
| Hand_Close | 65% |
| Hand_Open | 46% (43% mistaken for Rest) |
| Left | 21% |
| Down | 18% |
| Up | 15% |
| Right | 7% |

What this shows:

- **Activity level is learnable, direction is not.** Rest and Hand_Close separate well because they are the quietest and loudest movements. Left, Right, Up and Down sit at or near chance: one forearm channel carries almost no information about direction.
- **The camera must keep deciding movements.** This confirms the design: EMG is shown as activity feedback, and the camera produces the labels.
- **Results are better than on the old dataset** (36.7% vs 28.8%), mainly because there are 60 s per movement instead of about 6 s, and the label set now includes easier activity contrasts.

## Results: MOMENT-1 and the full model comparison

On the same 8 volunteers, fine-tuned MOMENT-1-small reaches 43.2% leave-one-subject-out, against 37.4% for the SVM on 200 ms windows. On equal 5.12 s windows the classical models catch up: SVM 47.3%, and frozen MOMENT features with a random forest 48.1%, the best result. Public UCI data did not raise the best accuracy (pre-training MOMENT on it: 44.4%). Full tables, per movement and per volunteer: [model_comparison.md](model_comparison.md).

## Results: EMG activity per movement

Mean window RMS in ADC units (`emg_activity_by_gesture.csv`):

| Movement | Healthy (9) | Synthetic stroke patient |
|---|---|---|
| Hand_Close | 884.6 | 466.3 |
| Up | 413.8 | 384.9 |
| Down | 413.5 | 174.9 |
| Right | 387.9 | 291.7 |
| Left | 301.4 | 145.1 |
| Hand_Open | 92.0 | 83.5 |
| Rest | 38.5 | 41.5 |

Relative to each volunteer's own Rest (`emg_rms_relative_to_rest.csv`), Hand_Close ranges from 7.3x (S03) to 117x (S02). S03's Hand_Open (0.41x) and Up (0.82x) fall below its Rest; every other subject-movement pair is above Rest. S01 has no Rest file and S04 no Down file. These are activity values, not strength.

## Previous results (removed `Datasets/` folder)

Computed on 2026-10-14 from the old `Datasets/` folder (11 volunteers, wrist and forearm gestures, 1 kHz), which was deleted on 2026-10-16. The best was 28.8% leave-one-subject-out (SVM). It cannot be reproduced from the repository and should not be reported alongside the results above.

## Latency (camera frame to game)

Measured automatically in webcam modes: each fused command carries its camera frame's capture time, and the game logs the delay when it consumes the command (`data/logs/latency_<game>_<time>.csv`). Not measured yet:

```bash
python main.py vision --game car          # play for about a minute, then Esc
python -m src.evaluation.latency_report   # median, p95, % under 300 ms -> results/tables/latency_summary.csv
```

## Evaluation still to do

| Area | Method | Target |
|---|---|---|
| Webcam gesture accuracy | Annotate recorded sessions; per-label precision and recall | Report honestly |
| Latency | Latency report above | Median under 300 ms |
| Usability | SUS questionnaire with 5+ volunteers | SUS above 68 |
| Rehabilitation tracking | Score and accuracy across sessions in RehabHub | Visible trend |
