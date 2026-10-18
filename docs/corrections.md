# Corrections to existing documents

The older project documents describe plans that changed during the build. Where they disagree with this `docs/` folder, the code and this folder are correct (checked 2026-10-18).

## `Stroke_Rehab_System_Documentation.pdf` (v1.0, 21 pages)

The PDF combines an early `architecture.md`, `plan.md` and `implement.md`.

| What the PDF says | What is true now |
|---|---|
| 3 games: Balloon Pop, **River Crossing**, Treasure Hunt | 4 games: Balloon Pop, Car Driving, Treasure Hunt, Shape Matching. River Crossing does not exist |
| 9 movements, including Wrist_Flexion, Wrist_Extension, Supination, Pronation | 7 camera labels: Rest, Hand_Open, Hand_Close, Left, Right, Up, Down (Supination/Pronation are keyboard-only) |
| LDA/SVM/RF classifiers "convert signals to movement labels" (L3) | Classifiers are offline research only; the camera produces all movement labels |
| Fusion: EMG Rest gate, Hand_Close needs EMG activation, 150 ms hold | Fusion drops labels under 0.6 confidence, takes a 5-command majority and attaches EMG features; EMG never changes the label |
| Sensor: MyoWare 2.0, 1 or 2 channels, Ch1/Ch2 electrode sites | MD0437, one channel, 3 electrodes (reference, +, -) |
| EMG pipeline: bandpass 20-450 Hz and 50 Hz notch | MD0437 output is already an envelope; filters are skipped (`signal_type: envelope`) |
| Auth: API key for games, login for the dashboard | No authentication; local use only |
| `patients` has a `code` column; `attempts` has only `emg_rms` | No `code` column; `attempts` also stores `emg_mav` and `vision_label` |
| `POST /sessions` "starts a session" | `POST /sessions` stores a finished session; `POST /sessions/start` opens one |
| 7 endpoints | 32 endpoints ([api_reference.md](api_reference.md)) |
| Files `emg_raw.csv`, `hand_landmarks.csv`, `session_log.csv`, columns `emg_ch1, emg_ch2` | Per-session files in `data/raw/emg/` and `data/raw/vision/`; the database; one `emg_value` column |
| Repository has `river_crossing.py`, `train_vision.py`, `evaluate.py`, `vision_features.py`, `logger.py`, `helpers.py`, `database.py`, `routes/` | None of these exist ([architecture.md](architecture.md), section 6) |
| Clinician dashboard in Streamlit | RehabHub web app (React + TypeScript); Streamlit remains as an older view |
| Per-user calibration step | Not implemented; adaptive difficulty from accuracy instead |
| Data plan: 5-10 subjects x 9 movements x 15 reps | `Dataset/`: 9 volunteers x 7 movements, 60 s each, plus one synthetic patient |
| Latency = game time - EMG sample time | Latency = game time - camera frame capture time |

## `EMG_Project_Documentation.md` (concept notes)

| What the notes say | What is true now |
|---|---|
| Signal sent to the laptop over Wi-Fi (UDP) | USB serial at 921600 baud |
| EMG gives muscle **strength** | EMG gives an activity envelope (RMS/MAV); it is not strength |
| Camera and strength combined control the games | The camera controls the games; EMG is displayed and logged |
| Hand open = RELAX, hand closed = FLEX; wrist right/left/up/down | Labels Hand_Open, Hand_Close, Left, Right, Up, Down, from finger shape and whole-hand movement |
| Balloon Pop needs enough strength at the right position; levels 1-3 by strength | A full fist on the balloon pops it; levels 1.0-5.0 change speed, size and timing |
| Car moves right/left on a straight road | Three lanes chosen by hand position; catch stars, avoid traffic, fist brakes |
| 3 games, 3 levels each | 4 games, continuous levels with auto adaptation |
| Games in Unity | Games in Python (Pygame) |
| Web app in React.js + Node.js | React + TypeScript front end, Python FastAPI back end |
| Login, automatic personal threshold, voice/text communication | Not built ([overview.md](overview.md)) |
| ML model separates healthy from patient signals | Not built; the web app compares the two groups' RMS/MAV |
| Wireless operation, rechargeable battery (TP4056 + MT3608) | Not in the repository |

## `architecture.md` (repository root, v1.1)

| What it says | What is true now |
|---|---|
| Electrode placement Ch1 and Ch2 | Single channel; see [hardware.md](hardware.md) |
| Auth: API key and dashboard login | No authentication |
| Datasets: `hand_landmarks.csv`, `session_log.csv`, `Datasets/` | `data/raw/vision/*.csv`, the database, and `Dataset/` |
| Repository lists `vision_features.py`; omits `webapp/`, `backend/webapi.py`, `difficulty.py` | See [architecture.md](architecture.md), section 6 |
| `tests/` has 28 tests | 47 tests |
| 1000 Hz sampling | Live firmware 1 kHz; `Dataset/` 100 Hz |

## `implement.md` (repository root)

| What it says | What is true now |
|---|---|
| `python src/acquisition/emg_logger.py S01 1` and `python src/acquisition/landmark_recorder.py ...` | Run as modules: `python -m src.acquisition.emg_logger S01 1`; the landmark recorder also needs a fix for MediaPipe 1.1 |
| Vision rules with thresholds 0.35/0.65 and 150/100; optional `vision_model.joblib` | `rule_classify` uses finger curl, reach and pinch ratio; no vision model file exists |
| Code listings throughout (for example the vision listing labels Left when the hand centre `cx < 0.35`) | The listings predate the current code: directions now come from palm movement, and games have session screens and adaptive difficulty. Read the source, not the listings |

## `README.md` and `plan.md`

| What they say | What is true now |
|---|---|
| `Datasets/` holds 11 volunteers and 3 synthetic patients | `Dataset/` holds 9 volunteers and 1 synthetic patient |
| 28 automated tests | 47 tests, all passing |
| `--emg-source replay` plays a recorded healthy volunteer | It now replays `Dataset/` (default S02) at 100 Hz |
| Best baseline 28.8% leave-one-subject-out | That came from the deleted data; on `Dataset/` the best is 36.7% (SVM) |
