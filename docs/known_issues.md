# Known issues and limitations

Checked against the code and data on 2026-10-18 (branch `main`). Issues are things that are broken or inconsistent today; limitations are what the prototype cannot do by design.

## Open issues

| # | Issue | Effect | Fix |
|---|---|---|---|
| 1 | `Dataset/` is sampled at 100 Hz; the live firmware and `config/settings.yaml` (`fs: 1000`) use 1 kHz | Dataset tools now use the dataset's own rate, but a model trained on `Dataset/` windows (20 samples) does not match live windows (200 samples) | Confirm which logger recorded `Dataset/`; record at one rate, or resample before comparing |
| 2 | Two volunteers are missing a movement (S01 Rest, S04 Down); S01 has about 2,400 dropped-sample gaps of 20-560 ms | Unbalanced classes; leave-one-subject-out folds for S01 and S04 lack a class | Record the missing files; re-record S01 if possible |
| 3 | `src/acquisition/landmark_recorder.py` calls `mp.solutions`, which MediaPipe 1.1 (installed) no longer has; its usage text says `python src/...` | The landmark recorder crashes; the script-style command fails with `ModuleNotFoundError` | Use `HandTracker` (supports the Tasks API) and run as `python -m src.acquisition.landmark_recorder` |
| 4 | `webapp/vite.config.ts` forwards `/api` to port 8000 only | Web app development mode fails when the API must use another port (on the development Mac Docker holds 8000) | Use the production build at `/ui`, or read the port from an environment variable |
| 5 | `momentfm` 0.1.4 pins old NumPy and transformers | Fine-tuning needs its own environment (`.venv-finetune`) | Documented in [fine_tuning_moment.md](fine_tuning_moment.md); revisit if a newer momentfm drops the pins |
| 6 | Latency, webcam gesture accuracy and usability have not been measured | No evidence yet for the 300 ms and SUS > 68 targets | See [testing_and_evaluation.md](testing_and_evaluation.md) |
| 7 | No front-end tests for RehabHub | Web regressions are found by hand | Add component tests (for example Vitest) |
| 8 | `npm run lint` reports 4 `react-refresh/only-export-components` warnings | Only affects hot reload in development | Move shared helpers out of component files |

## Fixed on 2026-10-18

| Issue | Fix |
|---|---|
| Code still read the deleted `Datasets/` folder (replay, feature builder, fine-tuning, web dataset explorer, 6 failing tests) | `src/data/public_datasets.py` now reads `Dataset/`; replay, `build_dataset --source healthy|stroke_synthetic|public`, `finetune_moment` and `backend/webapi.py` use it; all 41 tests pass |
| Joined recordings in some files (time gaps, a backwards timestamp in `S01_Down.csv`) | The loader splits files into segments at gaps over 1 s or backwards steps; windows never cross a segment |
| Window sizes assumed 1 kHz for dataset files | Dataset rows carry `fs` = 100, used by the feature builder, replay and fine-tuning |
| Web Game Launcher had no EMG replay mode | "Webcam + EMG replay (no sensor)" added to every game |
| Classifier results came from the deleted data | Baselines re-run on `Dataset/` (SVM 36.7% leave-one-subject-out) |

## Limitations

- **Single EMG channel:** it separates activity levels (Rest, Hand_Open, Hand_Close) but not directions (Left/Right/Up/Down near chance), so EMG never controls the games.
- **EMG is not strength:** RMS/MAV are envelope values in ADC units, not calibrated force.
- **No real patients:** the only patient data is synthetic; no clinical claim can be made.
- **No accounts or communication:** no login, no patient-therapist messaging, no reminders or report generation.
- **Local only:** the API has no authentication; the Settings page can rewrite `config/settings.yaml` for anyone who can reach the API. Keep it on `127.0.0.1`.
- **One game at a time** from the web app, on the same computer as the API.
- **Wired only:** USB serial; no Wi-Fi link or battery pack in the repository.
- **Fixed rules for vision:** gesture thresholds were tuned by hand and are not validated against annotated data.
