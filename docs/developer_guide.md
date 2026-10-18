# Developer guide

How the code fits together, where to change things, and the rules that keep the design consistent. Read [architecture.md](architecture.md) first.

## Design rules

1. **The camera decides movements.** EMG is an activity measurement (RMS, MAV). No EMG classifier controls a game; `src/models/` is offline research only.
2. **One label vocabulary at runtime:** `config/labels.yaml`, read by `runtime_labels()` in `src/utils/config.py`. The keyboard map, simulator and games use these labels. Supination/Pronation exist only as keyboard keys for Treasure Hunt's lock.
3. **Signal type and sample rate matter.** `envelope` skips the bandpass/notch; `raw` gets 20-450 Hz bandpass and 50 Hz notch. `fs` converts window milliseconds to samples, so it must match the data (1000 for the live ESP32, 100 for `Dataset/`).
4. **Split by subject.** Evaluate EMG models leave-one-subject-out or on held-out subjects, never by random window: windows overlap by 50%.
5. **Synthetic data stays labelled.** The synthetic stroke patient is never presented as clinical evidence.
6. **Local only.** No authentication exists; never bind the API to a public interface.

## Module map

| Path | Responsibility |
|---|---|
| `main.py` | Parse mode, game, patient, difficulty, duration, EMG source; start threads; run the game |
| `src/acquisition/` | `emg_logger` (EMG-only trials), `fused_logger` (EMG + camera labels), `landmark_recorder` (hand landmarks) |
| `src/data/public_datasets.py` | Loader for `Dataset/`: long format, 100 Hz, segments split at gaps over 1 s |
| `src/data/prepare_finetune.py` | Preprocess `Dataset/` into MOMENT-1 windows in `data/processed/moment/` |
| `src/preprocessing/` | `clean()` filters, `make_windows()` |
| `src/features/` | `extract()` 8 features; `build_dataset.py` |
| `src/models/train_emg.py` | LDA/SVM/RF baselines: LOSO, within-subject, cross-cohort; metrics, confusion matrices, `results/splits.json` |
| `src/models/finetune_moment.py` | MOMENT-1 fine-tuning: `--check-data`, `--smoke`, `--split holdout|loso`; `load_finetuned()` |
| `src/models/moment_predict.py` | Run a saved fine-tuned model on one person's recordings |
| `models/moment/` | Committed fine-tuning runs (adapters, metrics, logs); see its README |
| `src/evaluation/` | `emg_activity_report.py`, `latency_report.py` |
| `src/vision/hand_tracker.py` | MediaPipe wrapper, hand features, `rule_classify` |
| `src/fusion/fusion_engine.py` | Confidence gate, majority smoothing, EMG attachment |
| `src/realtime/` | `pipeline.py` (threads, `latest`, command bus), `simulator.py`, `emg_replay.py` |
| `src/games/` | `game_engine.py` (`BaseGame`), four games, `difficulty.py`, `summary.py`, `audio.py` |
| `src/utils/` | `config.py` (settings, labels, env overrides), `session_sync.py` |
| `backend/app.py` | Session API and SQLite schema; mounts `webapi` and `/ui` |
| `backend/webapi.py` | Web app endpoints: overview, patients, sessions, game launcher, datasets, settings |
| `webapp/` | RehabHub (React + TypeScript), see [web_app.md](web_app.md) |
| `dashboard/dashboard.py` | Streamlit launcher and progress views (older) |
| `firmware/emg_acquisition/` | ESP32 sketch |

## Adding a game

1. Subclass `BaseGame` in `src/games/`, set `name` and `how_to_play`, implement `run()`.
2. Call `self.begin()` first (start screen, countdown, difficulty); each frame call `self.read_input()` and, in live mode, `self.wait_for_required_emg()`; read `self.cmd` and `latest["pointer"]`.
3. Call `self.target_set(label)` when a new target appears and `self.log(detected)` when the player acts; `self.miss()` for failures that are not movements. Use `self.difficulty.value(easy, hard)` for every tunable.
4. End with `self.save_session()`.
5. Register it in `main.py` (`--game`), `backend/webapi.py` (`GAMES`) and `dashboard/dashboard.py` (`GAMES`), add a card image in `webapp/public/games/`, and add a headless test in `tests/test_games_headless.py`.

## Adding an API endpoint

Add it to `backend/webapi.py` (web app features) or `backend/app.py` (anything games call), add a typed call in `webapp/src/api.ts` and a type in `webapp/src/types.ts`, and a test in `tests/test_backend.py`.

## Environment variables

| Variable | Effect |
|---|---|
| `EMG_SERIAL_PORT` | Overrides `serial_port` |
| `REHAB_DB` | SQLite path for the API |
| `REHAB_GAME_STATE` | Path of the per-patient difficulty file |
| `REHAB_SKIP_SCREENS` | Skip start and results screens (tests) |
| `EMG_REPLAY_SOURCE`, `EMG_REPLAY_SUBJECT` | Replay recording (default `healthy`, `S02`) |
| `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` | Headless Pygame (tests) |

## Tests

`python -m pytest -q` runs 44 tests, all passing. Fine-tuning code runs in `.venv-finetune` (`--smoke` checks it). See [testing_and_evaluation.md](testing_and_evaluation.md). Web app checks: `cd webapp && npm run lint && npm run build`.

## Git

Work on a feature branch, keep `main` runnable, and keep raw data, the database, logs and saved models out of commits (`.gitignore` already does this).
