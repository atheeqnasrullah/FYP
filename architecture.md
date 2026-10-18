# architecture.md

> **Outdated (kept for reference).** This document describes an earlier plan. The current, checked documentation is in [docs/README.md](docs/README.md); [docs/corrections.md](docs/corrections.md) lists where this file differs from the built system.

# Gamified Upper-Limb Stroke Rehabilitation System: System Architecture

**Version:** 1.1 | **Scope:** FYP prototype (EMG + Computer Vision + 4 games + local session monitoring)

---

## 1. Purpose

This document defines **what the system is made of and how the parts talk to each other**. For the schedule see `plan.md`; for build steps and code see `implement.md`.

## 2. System Goals

| ID | Goal |
|---|---|
| G1 | Detect hand gestures and movement direction from webcam frames while measuring EMG activity |
| G2 | Pair camera-derived movement labels with timestamped EMG features and use both for game actions and feedback in four games |
| G3 | Give immediate visual feedback to the patient |
| G4 | Log every session and show progress to a clinician remotely |
| G5 | Keep every module independently testable (simulator and keyboard fallbacks) |

**Supported movements (class labels):**
`Hand_Open, Hand_Close, Rest, Left, Right, Up, Down` (camera-derived labels implemented in the runtime)

## 3. High-Level Architecture

```text
┌───────────────────────── PATIENT SIDE (PC) ─────────────────────────┐
│                                                                     │
│  EMG Sensor ─► ESP32 ─serial─► EMG Pipeline ─┐                      │
│                                              ├─► Fusion Engine ─►   │
│  Webcam ─► OpenCV + MediaPipe ─► Vision Pipe ┘        │             │
│                                                       ▼             │
│                                              Command Bus (queue)    │
│                                                       │             │
│                          ┌────────────────────────────┼──────────┐  │
│                          ▼                ▼                     ▼  │
│                    Balloon Pop       Car Driving         Treasure Hunt
│                          └────────────────┬───────────────────────┘  │
│                                           ▼                         │
│                                   Session Logger                    │
└───────────────────────────────────────────┬─────────────────────────┘
                                            │ HTTP (JSON)
                                            ▼
                               ┌─────────────────────────┐
                               │ Backend API (FastAPI)   │
                               │ + Database (SQLite)     │
                               └────────────┬────────────┘
                                            ▼
                               ┌─────────────────────────┐
                               │ Clinician Dashboard     │
                               │ (Streamlit)             │
                               └─────────────────────────┘
```

## 4. Layered View

| Layer | Components | Responsibility |
|---|---|---|
| L1 Sensing | EMG sensor, electrodes, ESP32, webcam | Capture raw signals |
| L2 Signal Processing | Filters, windowing, landmark normalisation | Clean and segment data |
| L3 Feature + ML | EMG feature extractor, vision gesture/motion rules | Produce EMG activity features and camera movement labels |
| L4 Fusion | Fusion engine | Carry the camera movement command with synchronized EMG activity measurements |
| L5 Application | Game engine and 4 games | Turn commands into rehabilitation exercises |
| L6 Data + Cloud | Session logger, API, database | Store and serve progress data |
| L7 Presentation | Patient UI (game), clinician dashboard | Feedback and monitoring |

## 5. Component Specifications

### 5.1 Hardware

| Part | Specification |
|---|---|
| Microcontroller | ESP32 DevKit, ADC1 pin (GPIO34/35/36/39). Do **not** use ADC2 pins when WiFi is on |
| EMG sensor | MD0437 single-channel analog muscle-activity envelope |
| Electrodes | Ag/AgCl surface electrodes, reference electrode on bony area (elbow) |
| Power | Battery-powered sensor side recommended (reduces mains noise and improves patient safety) |
| Sampling rate | 1000 Hz per channel, 12-bit ADC (0-4095) |
| Link to PC | USB serial at 921600 baud (WiFi/BLE as a later upgrade) |

**Electrode placement (suggested):**
- Ch1: flexor carpi radialis / flexor digitorum (inner forearm)
- Ch2: extensor carpi radialis / extensor digitorum (outer forearm)
- Reference: elbow bony prominence

> **Design note:** The single-channel MD0437 measures an electrical activity envelope. It does not assign movement labels or provide a clinical strength measurement; the webcam labels movement.

### 5.2 EMG Pipeline

```text
MD0437 envelope ADC samples -> 200 ms windows (100 ms step) -> RMS/MAV/other activity features
                            -> timestamped EMG measurements (no runtime movement classification)
```

For this single-channel sensor, RMS, MAV, VAR, STD, PEAK, WL, ZC and SSC are electrical activity features, not clinical muscle-strength measurements.

### 5.3 Vision Pipeline

```text
Frame → OpenCV (flip, RGB) → MediaPipe Hands (21 landmarks)
      → normalise (relative to wrist, scale by palm size)
      → rule-based or ML gesture classifier → (label, confidence)
```

**Derived vision features:** finger curl angles, fingertip-to-palm distances, wrist angle, palm-facing indicator, hand centre (x, y).

### 5.4 Fusion Engine

The webcam supplies movement labels and confidence. EMG supplies timestamped activity features (RMS, MAV, VAR, STD, PEAK, WL, ZC, SSC). Fusion smooths the camera label and attaches the latest EMG measurements to each command for game feedback and attempt logging. EMG activity does not gate or replace a camera-detected movement. The one-channel MD0437 is not treated as a clinical muscle-strength measurement.

### 5.5 Sensor and movement responsibilities

| Signal or label | Primary source | Role of the other sensor | Notes |
|---|---|---|---|
| Hand_Open / Hand_Close | Webcam | EMG activity features are recorded during the gesture | Landmark-based finger posture; Balloon Pop requires a full fist |
| Left / Right | Webcam | EMG activity features are recorded during movement | Palm movement along the horizontal axis |
| Up / Down | Webcam | EMG activity features are recorded during movement | Palm movement along the vertical axis |
| RMS / MAV / other features | EMG sensor + ESP32 | Current camera label is attached to samples | Electrical activity indicators, not clinical strength |
| Rest / No_Hand | Webcam status | EMG baseline/activity can be observed | No EMG classifier decides game actions |

### 5.6 Command Bus

A thread-safe `queue.Queue` carries camera-derived movement commands and associated EMG feature measurements to the active game. Keyboard and simulator modes remain available for manual operation.

```json
{
  "command": "Hand_Close",
  "confidence": 0.91,
  "source": "vision+emg",
  "timestamp_ms": 1759650000123,
  "emg_rms": 410.2,
  "emg_mav": 398.1
}
```

### 5.7 Games

All games inherit from `BaseGame` (input handling, score, timer, target scheduler and logging).

| Game | Controls | Rehab target |
|---|---|---|
| Balloon Pop | Camera pointer aims; a complete fist pops; combined mode displays RMS/MAV | Grip/release, aiming, activity feedback |
| Car Driving | Webcam Left/Right steers; Hand_Close brakes; combined mode displays RMS/MAV | Lateral reach, gesture response, activity feedback |
| Treasure Hunt | Camera Left/Right/Up/Down moves; Hand_Open selects; Hand_Close grabs; combined mode displays RMS/MAV | Multi-direction reach and coordination |
| Shape Matching | Camera pointer and Hand_Close/Hand_Open pick/drop; combined mode displays RMS/MAV | Reach, grasp/release and shape alignment |

Each game defines a target per attempt and logs camera movement plus available EMG activity features.

### 5.8 Backend

- **Framework:** FastAPI
- **Database:** SQLite (PostgreSQL if scaled)
- **Auth (basic):** API key for the patient client, login for the clinician dashboard

**Endpoints:**

| Method | Path | Purpose |
|---|---|---|
| POST | `/patients` | Create a patient |
| GET | `/patients` | List patients |
| POST | `/sessions` | Start a session |
| POST | `/sessions/{id}/attempts` | Upload attempt logs (batch) |
| PATCH | `/sessions/{id}` | Close session with summary |
| GET | `/patients/{id}/sessions` | Session history |
| GET | `/patients/{id}/progress` | Aggregated progress metrics |

### 5.9 Database Schema

```text
patients(patient_id PK, code, age, affected_side, stroke_date, notes)
sessions(session_id PK, patient_id FK, started_at, ended_at, game_name,
         total_score, duration_s, accuracy)
attempts(attempt_id PK, session_id FK, ts, target_movement, detected_movement,
         vision_label, correct, reaction_time_ms, emg_rms, emg_mav, confidence)
```

Use coded IDs (P01, P02). **Never store names.**

### 5.10 Clinician Dashboard

Dashboard progress shows session score/accuracy, per-movement accuracy, average EMG RMS/MAV by movement when available, session table and CSV export.

## 6. Data Architecture

| Dataset | File | Row = | Used for |
|---|---|---|---|
| Synchronized EMG + camera labels | `data/raw/emg/*_fused.csv` | timestamped EMG sample with current camera label | Movement-linked activity analysis |
| EMG features | `emg_features.csv` | one window | Activity analysis; optional offline research comparison |
| Hand landmarks | `hand_landmarks.csv` | one frame | Training/validating vision |
| Session log | `session_log.csv` / DB `attempts` | one attempt | Dashboard |

**Synchronized sample columns:** `timestamp_ms, subject_id, session_id, trial_id, emg_value, label, vision_confidence, pointer_x, pointer_y`. The camera label is paired with the EMG sample; the camera video is not retained.

| Public gesture datasets | `Datasets/` (11 healthy volunteers raw + filtered, 3 synthetic patients) | one gesture recording per column | Offline EMG baselines, activity analysis, EMG replay (`docs/datasets.md`) |
| Subject splits | `results/splits.json` | one fold | Shared by the baseline and MOMENT-1 fine-tuning |

**Rule:** split train/test **by subject or session**, never by random row, to avoid leakage.

## 7. Repository Structure

```text
stroke-rehab-system/
├── README.md
├── requirements.txt
├── .gitignore
├── config/            settings.yaml, labels.yaml
├── firmware/emg_acquisition/emg_acquisition.ino
├── data/              raw/{emg,vision}, processed/, features/, logs/
├── src/
│   ├── acquisition/   fused_logger.py, emg_logger.py, landmark_recorder.py
│   ├── preprocessing/ filters.py, windowing.py
│   ├── features/      emg_features.py, vision_features.py
│   ├── models/        train_emg.py, finetune_moment.py, saved/
│   ├── vision/        hand_tracker.py
│   ├── fusion/        fusion_engine.py
│   ├── data/          public_datasets.py (Datasets/ loaders)
│   ├── evaluation/    emg_activity_report.py, latency_report.py
│   ├── realtime/      pipeline.py, simulator.py, emg_replay.py
│   ├── games/         game_engine.py, balloon_pop.py, car_driving.py,
│   │                  treasure_hunt.py, shape_matching.py
│   └── utils/         config.py, session_sync.py
├── backend/           app.py
├── dashboard/         dashboard.py
├── tests/             pytest suite (28 tests)
├── docs/
└── results/           figures/, tables/
```

## 8. Technology Stack

| Area | Tools |
|---|---|
| Firmware | Arduino IDE / PlatformIO |
| Signal processing | Python 3.10+, NumPy, SciPy, pandas |
| ML | scikit-learn, joblib |
| Vision | OpenCV, MediaPipe |
| Games | Pygame |
| Backend | FastAPI, Uvicorn, SQLite, SQLAlchemy |
| Dashboard | Streamlit, Plotly |
| Tooling | Git/GitHub, pytest, black |

## 9. Non-Functional Requirements

| Requirement | Target |
|---|---|
| End-to-end latency (movement → game response) | < 300 ms |
| EMG window | 200 ms, step 100 ms |
| Vision frame rate | ≥ 20 FPS |
| Offline-first | Game runs without internet; logs sync when online |
| Safety | Battery-powered/isolated EMG front end, no mains-connected electrodes |
| Privacy | Coded patient IDs, consent forms, no names or faces stored |
| Testability | Keyboard and simulator input for every game |

## 10. Key Risks and Design Responses

| Risk | Response |
|---|---|
| Single-channel EMG cannot separate all movements | Role-based sensor split, add 2nd channel, reduce classes if needed |
| Vision weak on wrist/rotation | Use palm-facing and wrist-angle features, EMG as confirmation |
| Cross-subject accuracy drops | Per-user calibration (30-60 s) at session start |
| Stroke patients: tremor, weak signal | Adjustable thresholds, difficulty levels, longer hold times |
| 50 Hz noise, motion artefacts | Shielded leads, notch filter, battery power, good skin prep |
| Training on healthy subjects only | State clearly as a limitation; propose clinical validation as future work |

## 11. Evaluation Metrics

- **Classification:** accuracy, precision, recall, F1, confusion matrix (subject-wise split)
- **System:** latency, FPS, command stability (flicker rate)
- **Usability:** task success rate, SUS questionnaire, patient/clinician feedback
- **Rehabilitation:** score and accuracy trend across sessions

## 12. Future Extensions

Multi-channel EMG armband, BLE/WiFi wireless link, cloud deployment, more games, adaptive difficulty driven by performance, clinical trial with stroke patients.
