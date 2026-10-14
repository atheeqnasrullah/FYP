# Developer guide

How the code fits together, where to change things, and the rules that keep the design consistent.

## Runtime data flow

```text
ESP32 (1 kHz CSV "ms,adc") --serial--> pipeline._emg ----------.
   or Datasets/ recording --> emg_replay.replay_emg -----------+--> latest["emg_features"] (RMS, MAV, ...)
Webcam --> pipeline._vision (MediaPipe + rules + motion) --> latest["vis"], ["pointer"], ["fist"], ["vis_ts_ms"]
pipeline._fusion (every 50 ms) --> FusionEngine.fuse --> command_bus (queue, 50)
Game loop (30 fps) --> BaseGame.read_input --> game logic --> attempts --> save_session --> API / pending queue
```

All threads share `latest` under `pipeline.lock`. `pipeline.start(use_emg, use_vision, show_preview, emg_source)` starts them; `shutdown()` sets `stop`.

## Design rules

1. **The camera decides movements.** EMG is an activity measurement (RMS, MAV). No EMG classifier controls a game; offline classifiers (`src/models/`) are research only.
2. **One label vocabulary at runtime:** `config/labels.yaml` (`runtime_labels()` in `src/utils/config.py`). The keyboard map, simulator and games all use these labels. Supination/Pronation exist only as keyboard bonus keys in Treasure Hunt.
3. **Signal type matters.** `envelope` (MD0437 SIG, rectified datasets) skips the bandpass/notch; `raw` gets 20-450 Hz bandpass and 50 Hz notch. Set it per source, never globally for mixed data.
4. **Split by subject.** Evaluate EMG models leave-one-subject-out or on held-out subjects (`results/splits.json`), never by random window: windows overlap by 50%.
5. **Synthetic data stays labelled.** `cohort == "simulated_patient"` is never presented as clinical evidence.

## Module map

| Path | Responsibility |
|---|---|
| `src/acquisition/` | EMG-only logger, fused EMG + camera logger, landmark recorder |
| `src/data/public_datasets.py` | Load Datasets/ into long format |
| `src/preprocessing/` | `clean()` filters, `make_windows()` |
| `src/features/` | `extract()` 8 features; `build_dataset.py --source ...` |
| `src/models/train_emg.py` | LDA/SVM/RF baselines: LOSO, within-subject, cross-cohort; writes metrics, confusion matrices, `splits.json` |
| `src/models/finetune_moment.py` | Stage 7, MOMENT-1 fine-tuning (needs approval and `requirements-finetune.txt`) |
| `src/evaluation/` | `emg_activity_report.py` (activity + data quality), `latency_report.py` |
| `src/vision/hand_tracker.py` | MediaPipe wrapper (Solutions or Tasks API), hand features, `rule_classify` |
| `src/fusion/fusion_engine.py` | Confidence gate, majority smoothing, attach EMG features |
| `src/realtime/` | `pipeline.py` threads, `simulator.py`, `emg_replay.py` |
| `src/games/` | `BaseGame` + four games |
| `src/utils/` | `config.py` (settings, labels, env overrides), `session_sync.py` |
| `backend/app.py` | FastAPI + SQLite |
| `dashboard/dashboard.py` | Streamlit launcher and progress views |
| `firmware/emg_acquisition/` | ESP32 sketch, GPIO34, 1 kHz, 921600 baud |

## Vision logic (summary)

`HandTracker.features` computes finger curl angles, fingertip reach normalised by palm size, pinch ratio, a strict `full_fist`, palm centre and orientation. `rule_classify` returns `Hand_Close` for a pinch or a closed hand, `Hand_Open` for three or more extended fingers, else `Rest`. `_vision` smooths labels over `vision_smoothing_frames` (60% majority) and detects Left/Right/Up/Down from palm displacement against an anchor (`lr_motion_threshold`, `ud_motion_threshold`), holding a direction for `lr_motion_hold_ms` with a cooldown.

## Adding a game

1. Subclass `BaseGame` in `src/games/`, set `name`, implement `run()`.
2. Each frame: `self.read_input()`; in live mode call `self.wait_for_required_emg()`; read `self.cmd` (and `latest["pointer"]` for pointing).
3. Call `self.target_set(label)` when a new target appears and `self.log(detected)` when the player acts.
4. End with `self.save_session()`.
5. Register it in `main.py` (`--game`) and `dashboard.py` (`GAMES`), and add a headless test in `tests/test_games_headless.py`.

## Environment variables

| Variable | Effect |
|---|---|
| `EMG_SERIAL_PORT` | Overrides `serial_port` |
| `REHAB_DB` | SQLite path for the API (tests use a temp file) |
| `EMG_REPLAY_SOURCE`, `EMG_REPLAY_SUBJECT` | Replay recording (default `healthy_raw`, first subject) |
| `SDL_VIDEODRIVER=dummy` | Headless Pygame (tests) |

## Tests

`python -m pytest -q` runs 28 tests in about 20 s: signal processing, fusion, datasets and evaluation helpers, API, session sync, EMG replay through the pipeline, all four games headless, and the dashboard script. See `docs/testing_and_evaluation.md`.
