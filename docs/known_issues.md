# Known issues and limitations

Checked against the code and data on 2026-10-18 (branch `main`). Issues are things that are broken or inconsistent today; limitations are what the prototype cannot do by design.

## Open issues

| # | Issue | Effect | Fix |
|---|---|---|---|
| 1 | `Dataset/` is sampled at 100 Hz; the live firmware and `config/settings.yaml` (`fs: 1000`) use 1 kHz | Dataset tools now use the dataset's own rate, but a model trained on `Dataset/` windows (20 samples) does not match live windows (200 samples) | Confirm which logger recorded `Dataset/`; record at one rate, or resample before comparing |
| 2 | Two volunteers are missing a movement (S01 Rest, S04 Down); S01 lost 26-50% of its samples in every file (about 2,400 gaps of 20-560 ms) | S01 is excluded from fine-tuning (39% interpolated); S04's fold has no Down windows | Re-record S01 and S04 Down |
| 3 | `src/acquisition/landmark_recorder.py` calls `mp.solutions`, which MediaPipe 1.1 (installed) no longer has; its usage text says `python src/...` | The landmark recorder crashes; the script-style command fails with `ModuleNotFoundError` | Use `HandTracker` (supports the Tasks API) and run as `python -m src.acquisition.landmark_recorder` |
| 4 | `webapp/vite.config.ts` forwards `/api` to port 8000 only | Web app development mode fails when the API must use another port (on the development Mac Docker holds 8000) | Use the production build at `/ui`, or read the port from an environment variable |
| 5 | `momentfm` 0.1.4 pins old NumPy and transformers | Fine-tuning needs its own environment (`.venv-finetune`) | Documented in [fine_tuning_moment.md](fine_tuning_moment.md); revisit if a newer momentfm drops the pins |
| 6 | Latency, webcam gesture accuracy and usability have not been measured | No evidence yet for the 300 ms and SUS > 68 targets | See [testing_and_evaluation.md](testing_and_evaluation.md) |
| 7 | No front-end tests for RehabHub | Web regressions are found by hand | Add component tests (for example Vitest) |
| 8 | `npm run lint` reports 4 `react-refresh/only-export-components` warnings | Only affects hot reload in development | Move shared helpers out of component files |
| 9 | The patient data changed twice (generated `SYN_STROKE_01`, then `SP01` on 2026-10-18, then two patients on 2026-10-22); its origin (real or generated) is not documented, and the files in `stroke_patient/SP01/` say `SP03` inside | Patient results (now `SP02` and `SP03`) cannot be called clinical, and one ID may be wrong | Confirm the patients' origin and the correct ID for the `SP01/` folder |
| 10 | The grip effort threshold (auto 25-60% of the strongest squeeze) is a starting guess; it has not been tried with patients | The default may be too hard or too easy for some patients | Check it in the usability study; the therapist can set a fixed value or turn it off per session |
| 11 | The level goals (for example 6 to 18 balloons) and the one-level-a-day pace are first choices, not tested with patients | Some levels may be too easy or too hard to pass in 3 minutes | Tune `GOALS` in `src/games/levels.py` after the usability study; the therapist can change `level_days_between` and the session length |
| 12 | The new volunteers S10-S20 are far easier to classify (80-94%) than S02-S09 (44-49%), and their recordings are very alike | Overall accuracy (72.1% best) depends on the mix of volunteers; the S18-S20 holdout (82-90%) overstates it | Report results per group; record more volunteers under the same protocol as S02-S09, and note how S10-S20 were recorded |

## Fixed (2026-10-18 to 2026-10-21)

| Issue | Fix |
|---|---|
| Code still read the deleted `Datasets/` folder (replay, feature builder, fine-tuning, web dataset explorer, 6 failing tests) | `src/data/public_datasets.py` now reads `Dataset/`; replay, `build_dataset --source healthy|stroke_patient|public`, `finetune_moment` and `backend/webapi.py` use it; the dataset tests pass again |
| Joined recordings in some files (time gaps, a backwards timestamp in `S01_Down.csv`) | The loader splits files into segments at gaps over 1 s or backwards steps; windows never cross a segment |
| Window sizes assumed 1 kHz for dataset files | Dataset rows carry `fs` = 100, used by the feature builder, replay and fine-tuning |
| Web Game Launcher had no EMG replay mode | "Webcam + EMG replay (no sensor)" added to every game |
| Classifier results came from the deleted data | Baselines re-run on `Dataset/` (SVM 36.7% leave-one-subject-out) |
| LoRA adapters never trained (2026-10-21): MOMENT's default gradient checkpointing blocked all gradients to them, so earlier "fine-tuned" results were head-only | `enable_gradient_checkpointing: False` in `build_model`; the smoke test fails if the adapters do not change; all fine-tuning runs repeated |

## Limitations

- **Single EMG channel:** it separates activity levels (Rest, Hand_Open, Hand_Close) best; directions are less reliable (Left/Right/Down 49-75% and Up about 40% recall on 5.12 s windows, near chance on 200 ms windows), so EMG never controls the games.
- **EMG is not strength:** RMS/MAV are envelope values in ADC units, not calibrated force. The grip threshold is relative to each patient's own squeeze, not a force in newtons, and the squeeze depends on electrode placement on the day.
- **No confirmed patient data:** two patient recordings (`SP02`, `SP03`, origin to be confirmed; they replaced earlier patient files); no clinical claim can be made.
- **No accounts or communication:** no login, no patient-therapist messaging, no reminders or report generation.
- **Local only:** the API has no authentication; the Settings page can rewrite `config/settings.yaml` for anyone who can reach the API. Keep it on `127.0.0.1`.
- **One game at a time** from the web app, on the same computer as the API.
- **Wired only:** USB serial; no Wi-Fi link or battery pack in the repository.
- **Fixed rules for vision:** gesture thresholds were tuned by hand and are not validated against annotated data.
