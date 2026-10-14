# Testing and evaluation

## Automated tests

```bash
python -m pytest -q        # 28 passed in about 20 s (macOS, Python 3.11)
```

| File | Covers |
|---|---|
| `tests/test_signal_processing.py` | Feature values, envelope vs raw filtering, windowing |
| `tests/test_fusion.py` | Confidence gate, majority smoothing, EMG features attached |
| `tests/test_datasets_and_models.py` | All three dataset sources, feature build, within-subject split gap, subject normalisation, runtime labels |
| `tests/test_backend.py` | Patient validation, session upload, progress, CSV export, open/attempt/close flow, 404/409 errors (temp DB via `REHAB_DB`) |
| `tests/test_session_sync.py` | Offline queue keeps only failed uploads |
| `tests/test_emg_replay.py` | Replay makes `emg_is_ready()` true and fusion commands carry EMG features |
| `tests/test_games_headless.py` | All four games run with scripted input on SDL's dummy driver and save a session; Balloon Pop scores from the keyboard; latency is recorded from vision timestamps |
| `tests/test_dashboard.py` | Dashboard script runs without an API and shows the replay mode |

## Reproducing the results

```bash
python -m src.features.build_dataset --source public
python -m src.features.build_dataset --source healthy_filtered
python -m src.models.train_emg --features data/features/emg_features_public.csv --subject-norm
python -m src.models.train_emg --features data/features/emg_features_healthy_filtered.csv
python -m src.models.train_emg --features data/features/emg_features_public.csv   # run last: its model is saved
python -m src.evaluation.emg_activity_report
```

Outputs: `results/tables/*.csv`, `results/figures/*.png`, `results/splits.json`.

## Results: EMG gesture classification (offline, 7 classes, chance 14.3%)

Healthy volunteers, 11 subjects, 4,578 windows of 200 ms. Accuracy:

| Features | Model | Leave-one-subject-out | Within-subject (70/30 in time) | Train healthy, test simulated patients |
|---|---|---|---|---|
| Rectified raw | LDA | 26.6% | 30.7% | 14.3% |
| Rectified raw | SVM | **28.8%** | 35.9% | 14.3% |
| Rectified raw | RF | 21.8% | 38.1% | 14.3% |
| Rectified raw, per-subject z-score | LDA | **29.7%** | 32.9% | 17.0% |
| Rectified raw, per-subject z-score | SVM | 27.3% | 38.8% | 17.9% |
| Rectified raw, per-subject z-score | RF | 24.1% | **41.2%** | 16.6% |
| Filtered envelope | SVM | 29.4% | 33.0% | not run |

Findings:

- **Rest is easy, gestures are not.** SVM recalls Rest 81% of the time across subjects, but the six active gestures sit at 10-42% (confusion matrix: `results/figures/confusion_baseline_public_SVM_loso.png`).
- **One channel cannot separate seven gestures.** Cross-subject accuracy is about twice chance; per-subject data helps (up to 41%) but stays far from usable. This matches risk R1 in `plan.md` and supports the design decision that the camera, not EMG, controls the games.
- **The simulated patients do not transfer.** Their signal is in a different unit scale (about 0.01 mV vs 100+ mV), so without calibration every model predicts one class (14.3%). Per-subject z-scoring lifts it only to 17-18%.

## Results: EMG activity

`results/figures/emg_rms_relative_to_rest.png`: 92% of the 66 subject-gesture pairs have higher mean RMS than that subject's Rest (median 2.6x Rest; H03 up to 13.7x). Eight of 11 volunteers are above Rest on every gesture; H02, H06 and H11 each have one to three gestures at or below Rest (lowest 0.65x, H06 Supination). This supports using RMS/MAV as an activity indicator in the games, while not calling it strength.

## Latency (camera frame to game)

Measured automatically in webcam modes: each fused command carries the capture time of its camera frame, and the game logs the delay when it consumes the command (`data/logs/latency_<game>_<time>.csv`). Summarise with:

```bash
python main.py vision --game car        # play for about a minute, then Esc
python -m src.evaluation.latency_report # median, p95, % under 300 ms -> results/tables/latency_summary.csv
```

Not yet measured in this repository: it needs a person in front of the webcam. Expected contributors: MediaPipe inference, label smoothing (5 frames), fusion polling (50 ms) and the 30 fps game loop.

## Still to do by hand

- Webcam gesture accuracy: annotate a sample of Open/Close/Left/Right/Up/Down attempts and report precision/recall (plan section 8).
- Usability: SUS questionnaire with 5+ volunteers (target SUS > 68).
- Live EMG with the ESP32 + MD0437 once the hardware is available.
