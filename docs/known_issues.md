# Known issues and limitations

Checked against the code and data on 2026-10-18 (branch `main`). Issues are things that are broken or inconsistent today; limitations are what the prototype cannot do by design.

## Issues

| # | Issue | Effect | Fix |
|---|---|---|---|
| 1 | The old `Datasets/` folder was deleted on 2026-10-16, but `src/data/public_datasets.py`, `src/realtime/emg_replay.py`, `build_dataset --source ...`, `src/models/finetune_moment.py` and `backend/webapi.py` (`DATASET_DIRS`) still read it | EMG replay mode crashes; dataset feature building and fine-tuning cannot run; the web app's EMG Datasets page does not list `Dataset/`; 6 tests fail | Rewrite the loader for `Dataset/` (`timestamp_ms, adc_value, subject_id, movement_label`), point replay, feature builder, fine-tuning and `DATASET_DIRS` at it, update the tests |
| 2 | `Dataset/` is sampled at 100 Hz; firmware and `config/settings.yaml` (`fs: 1000`) assume 1 kHz | A 200 ms window would be read as 200 samples (2 s) instead of 20 | Set `fs` per data source; confirm which logger recorded `Dataset/` |
| 3 | Some `Dataset/` files join several recordings (S01, S02_Down, S04 Hand_Close/Hand_Open/Up); `S01_Down.csv` has a timestamp that runs backwards | Windows can span two recordings | Split at time gaps of more than 10 ms when loading |
| 4 | Two volunteers are missing a movement (S01 Rest, S04 Down) | Unbalanced classes; leave-one-subject-out folds lack a class | Record the missing files, or report per-class counts |
| 5 | `src/acquisition/landmark_recorder.py` calls `mp.solutions`, which MediaPipe 1.1 (installed) no longer has; its usage text says `python src/...` | The landmark recorder crashes; the script-style command fails with `ModuleNotFoundError` | Use `HandTracker` (supports the Tasks API) and run as `python -m src.acquisition.landmark_recorder` |
| 6 | `webapp/vite.config.ts` forwards `/api` to port 8000 only | Web app development mode fails when the API must use another port (on the development Mac Docker holds 8000) | Use the production build at `/ui`, or read the port from an environment variable |
| 7 | The web Game Launcher offers no EMG replay mode (the Streamlit dashboard does) | Webcam + EMG cannot be demonstrated from RehabHub without the sensor | Add a `replay` mode to `GAMES` in `backend/webapi.py` once issue 1 is fixed |
| 8 | Previous classifier results and `results/splits.json` come from the deleted data | They cannot be reproduced from the repository | Re-run the baselines on `Dataset/` |
| 9 | Latency, webcam gesture accuracy and usability have not been measured | No evidence yet for the 300 ms and SUS > 68 targets | See [testing_and_evaluation.md](testing_and_evaluation.md) |
| 10 | No front-end tests for RehabHub | Web regressions are found by hand | Add component tests (for example Vitest) |

## Limitations

- **Single EMG channel:** measures activity well but cannot tell gestures apart reliably, so EMG never controls the games.
- **EMG is not strength:** RMS/MAV are envelope values in ADC units, not calibrated force.
- **No real patients:** the only patient data is synthetic; no clinical claim can be made.
- **No accounts or communication:** no login, no patient-therapist messaging, no reminders or report generation.
- **Local only:** the API has no authentication; the Settings page can rewrite `config/settings.yaml` for anyone who can reach the API. Keep it on `127.0.0.1`.
- **One game at a time** from the web app, on the same computer as the API.
- **Wired only:** USB serial; no Wi-Fi link or battery pack in the repository.
- **Fixed rules for vision:** gesture thresholds were tuned by hand and are not validated against annotated data.
