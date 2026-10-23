# Backend API reference

One FastAPI app serves 32 endpoints: 12 in the session API (`backend/app.py`, used by the games) and 20 in the web app API (`backend/webapi.py`, used by RehabHub). It has no authentication, so it must stay on `127.0.0.1`. CORS allows only the Vite dev server (`http://localhost:5173`, `http://127.0.0.1:5173`). Interactive docs are at `/docs` while the API runs.

Start it with `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`. The database is `data/rehab.db`, or the path in the `REHAB_DB` environment variable.

## Session API (`backend/app.py`)

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/` | none | Service links |
| GET | `/health` | none | `{"status":"ok"}` |
| POST | `/patients` | `Patient` | The patient; 409 if the code exists; 422 if invalid |
| GET | `/patients` | none | List of patients |
| POST | `/sessions` | `Session` with attempts | `{"session_id","accuracy"}`; 404 if the patient does not exist |
| POST | `/sessions/start` | `{"patient_id","game_name"}` | `{"session_id","status":"open"}` |
| POST | `/sessions/{sid}/attempts` | `{"attempts":[Attempt]}` | `{"session_id","uploaded"}`; 409 if closed |
| PATCH | `/sessions/{sid}` | `{"total_score","duration_s"}` | Closes the session and computes accuracy; 409 if already closed |
| GET | `/patients/{pid}/sessions` | none | Sessions by start time |
| GET | `/patients/{pid}/progress` | none | `sessions`, `movement_accuracy`, `emg_activity_by_movement` |
| GET | `/sessions/{sid}/attempts` | none | Attempts in order |
| GET | `/patients/{pid}/export.csv` | none | CSV of sessions joined with attempts |

The built web app is also served at `/ui` when `webapp/dist` exists.

## Web app API (`backend/webapi.py`)

| Method | Path | Parameters / body | Returns |
|---|---|---|---|
| GET | `/overview` | none | Totals (patients, sessions, attempts, average accuracy, minutes, reaction time), recent sessions, sessions by game, daily counts (30 days), accuracy by movement, pending offline sessions |
| GET | `/patients/summary` | none | Patients with session count, average accuracy, last session, best score, last 10 accuracies, trend (last 3 vs previous 3), last game |
| GET | `/patients/{pid}` | none | One patient; 404 if missing |
| PUT | `/patients/{pid}` | `{"age","affected_side","stroke_date","notes"}` | Updated patient |
| DELETE | `/patients/{pid}` | none | Deletes the patient, their sessions and attempts |
| GET | `/sessions` | `patient_id`, `game_name`, `limit` (1-5000, default 500) | Sessions with attempt counts, newest first |
| GET | `/sessions/{sid}` | none | One session |
| DELETE | `/sessions/{sid}` | none | Deletes the session and its attempts |
| POST | `/sessions/sync-pending` | none | Imports `data/logs/pending_sessions.jsonl`; `{"imported","failed"}` |
| GET | `/games` | none | Game catalogue (id, name, modes, description, what it trains) and input modes |
| GET | `/games/status` | none | `{"running","pid","last"}` |
| POST | `/games/launch` | `{"game","mode","patient_id","difficulty","duration_s","effort"}`; `effort` is `auto` or 0-100, used in `live` and `replay` modes | Starts `main.py`; 400 on bad input, 409 if a game runs |
| POST | `/games/stop` | none | Terminates the running game (kills it after 5 s) |
| GET | `/games/log` | `lines` (1-1000, default 80) | Last lines of `data/logs/dashboard_game.log` |
| GET | `/datasets` | none | CSV files under `Dataset/` and `data/raw/emg/` with rows, columns, size, category (normal, patient, recorded) |
| GET | `/datasets/signal` | `file`, `points` (50-10000) | Peak-preserving down-sampled signal per column, labels |
| GET | `/datasets/features` | `file`, `window`, `step` | RMS, MAV, VAR, STD, peak, WL per movement; windowed RMS series |
| GET | `/datasets/compare` | none | Mean RMS/MAV per movement for each dataset category |
| GET | `/settings` | none | Parsed settings, labels and raw YAML |
| PUT | `/settings` | `{"raw": "<yaml>"}` | Validates and writes `config/settings.yaml`; 400 on invalid YAML |

For `Dataset/` files (one signal column plus `movement_label`), features and comparisons are grouped by movement.

## Models

- **Patient:** `patient_id` (regex `^P[A-Za-z0-9_-]{1,20}$`), `age` 0-120, `affected_side`, `stroke_date`, `notes` (all optional except the ID).
- **Attempt:** `target_movement`, `detected_movement`, `correct`, `reaction_time_ms` (>= 0); optional `ts`, `vision_label`, `emg_rms`, `emg_mav`, `confidence`, `input_source` (for example `Camera + EMG sensor`), `emg_activity_pct` (effort 0-100), `effort_required_pct` and `effort_ok` (grip actions in Webcam + EMG mode only; otherwise null). The four optional input fields are stored, returned by `/sessions/{sid}/attempts` and included in the CSV export.
- **Session:** `patient_id`, `game_name`, `total_score`, `duration_s` (>= 0), `attempts`.
- **Launch:** `game` (balloon, car, treasure, shape), `mode` (vision, live, replay, keyboard, sim; replay runs live mode with `--emg-source replay`), `patient_id`, `difficulty` (auto, easy, medium, hard), `duration_s` (0-3600, default 180).

## Session upload from games

`BaseGame.save_session` calls `src/utils/session_sync.upload_session`, which creates the patient if needed and posts the session. On failure the payload is appended to `data/logs/pending_sessions.jsonl`. The queue is uploaded after the next successful save, by the web app (`POST /sessions/sync-pending`) or by the Streamlit sidebar button.
