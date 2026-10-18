# Testing and evaluation

## Automated tests

`python -m pytest -q` runs 39 tests in about 45 s. On 2026-10-18, 33 pass and 6 fail; all 6 failures come from the deleted `Datasets/` folder, not from the games, API or web code.

| Test file | Tests | Covers | Status |
|---|---|---|---|
| `test_signal_processing.py` | 4 | Feature values, envelope vs raw filtering, windowing | Pass |
| `test_fusion.py` | 3 | Confidence gate, majority smoothing, EMG features attached | Pass |
| `test_backend.py` | 4 | Patient validation, session upload, progress, CSV export, open/attempt/close flow, errors | Pass |
| `test_session_sync.py` | 2 | Offline queue keeps only failed uploads | Pass |
| `test_dashboard.py` | 1 | Streamlit dashboard runs without an API | Pass |
| `test_game_logic.py` | 4 | Difficulty presets, auto level up and down, level remembered per patient, results summary | Pass |
| `test_games_headless.py` | 12 | All four games with scripted input on a hidden display: scoring, time limit, hand-position lanes, hand joystick, pick and drop by hand, latency logging | Pass |
| `test_datasets_and_models.py` | 8 | Dataset loading and feature building (5), split gap, normalisation, runtime labels | 5 fail: `Datasets/` missing |
| `test_emg_replay.py` | 1 | Replay feeds the live pipeline | Fails: replay reads `Datasets/` |

The tests set `SDL_VIDEODRIVER=dummy`, a temporary database (`REHAB_DB`) and a temporary difficulty file (`REHAB_GAME_STATE`), and skip the start and results screens (`REHAB_SKIP_SCREENS`), so they never touch real data.

**Not automated yet:** a live webcam session, the ESP32 serial path, the React web app (no front-end tests), webcam gesture accuracy, latency against the 300 ms target, and the usability (SUS) study.

## Current dataset: activity per movement

From the 2026-10-18 profile of `Dataset/` (see [datasets.md](datasets.md)): Hand_Close gives the highest mean envelope in healthy volunteers (547 ADC units) and Rest the lowest (12.4). Classifier results on this dataset do not exist yet, because the loaders still target the removed folder.

## Previous results (removed `Datasets/` folder)

These were computed on 2026-10-14 from the old `Datasets/` folder (11 healthy volunteers, 7 wrist and hand gestures, 1 kHz). That data has been deleted, so the numbers cannot be reproduced from the current repository and must be re-run on `Dataset/` before they go in a report.

Accuracy, 7 classes (chance 14.3%), 4,578 windows of 200 ms:

| Features | Model | Leave-one-subject-out | Within-subject (70/30 in time) | Train healthy, test synthetic patients |
|---|---|---|---|---|
| Rectified raw | LDA | 26.6% | 30.7% | 14.3% |
| Rectified raw | SVM | **28.8%** | 35.9% | 14.3% |
| Rectified raw | RF | 21.8% | 38.1% | 14.3% |
| Per-subject z-score | LDA | **29.7%** | 32.9% | 17.0% |
| Per-subject z-score | SVM | 27.3% | 38.8% | 17.9% |
| Per-subject z-score | RF | 24.1% | **41.2%** | 16.6% |
| Filtered envelope | SVM | 29.4% | 33.0% | not run |

What they showed:

- Rest was easy (SVM recalled it 81% of the time across subjects); each active gesture only 10-42%.
- One EMG channel cannot separate seven gestures across people: about twice chance at best. This supports the design where the camera controls the games.
- 92% of subject-gesture pairs had higher mean RMS than that person's Rest, so RMS/MAV works as an activity indicator.

## How to reproduce (after migrating the loader to `Dataset/`)

```bash
python -m src.features.build_dataset --source <source>
python -m src.models.train_emg --features data/features/emg_features_<source>.csv
python -m src.models.train_emg --features data/features/emg_features_<source>.csv --subject-norm
python -m src.evaluation.emg_activity_report
```

Outputs go to `results/tables/`, `results/figures/` and `results/splits.json`.

## Latency (camera frame to game)

Measured automatically in webcam modes: each fused command carries its camera frame's capture time, and the game logs the delay when it consumes the command (`data/logs/latency_<game>_<time>.csv`). Not measured yet; to measure:

```bash
python main.py vision --game car          # play for about a minute, then Esc
python -m src.evaluation.latency_report   # median, p95, % under 300 ms -> results/tables/latency_summary.csv
```

## Evaluation still to do

| Area | Method | Target |
|---|---|---|
| Webcam gesture accuracy | Annotate recorded sessions; per-label precision and recall | Report honestly |
| Latency | Latency report above | Median under 300 ms |
| EMG activity | Activity report on `Dataset/` | Signal range, variability, missing data |
| Usability | SUS questionnaire with 5+ volunteers | SUS above 68 |
| Rehabilitation tracking | Score and accuracy across sessions in RehabHub | Visible trend |
