# Backend API reference

FastAPI app in `backend/app.py`; interactive docs at `/docs`. Data is stored in SQLite at `data/rehab.db` (override with the `REHAB_DB` environment variable). There is no authentication: run it on localhost only and store coded IDs only.

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/` | none | Service links |
| GET | `/health` | none | `{"status":"ok"}` |
| POST | `/patients` | `Patient` | The patient; 409 if the code exists; 422 if the code is invalid |
| GET | `/patients` | none | List of patients |
| POST | `/sessions` | `Session` (with attempts) | `{"session_id", "accuracy"}`; 404 if the patient does not exist |
| POST | `/sessions/start` | `{"patient_id","game_name"}` | `{"session_id","status":"open"}` |
| POST | `/sessions/{sid}/attempts` | `{"attempts":[Attempt]}` | `{"session_id","uploaded"}`; 409 if closed |
| PATCH | `/sessions/{sid}` | `{"total_score","duration_s"}` | Closes the session and computes accuracy; 409 if already closed |
| GET | `/patients/{pid}/sessions` | none | Sessions by start time |
| GET | `/patients/{pid}/progress` | none | `sessions`, `movement_accuracy`, `emg_activity_by_movement` |
| GET | `/sessions/{sid}/attempts` | none | Attempts in order |
| GET | `/patients/{pid}/export.csv` | none | CSV of sessions joined with attempts |

## Models

- **Patient:** `patient_id` (regex `^P[A-Za-z0-9_-]{1,20}$`), `age` 0-120, `affected_side`, `stroke_date`, `notes` (all optional except the ID).
- **Attempt:** `target_movement`, `detected_movement`, `correct`, `reaction_time_ms` (>= 0), optional `ts`, `vision_label`, `emg_rms`, `emg_mav`, `confidence`.
- **Session:** `patient_id`, `game_name`, `total_score`, `duration_s` (>= 0), `attempts`.

## Database tables

`patients(patient_id PK, age, affected_side, stroke_date, notes)`
`sessions(session_id PK, patient_id FK, game_name, started_at, ended_at, total_score, duration_s, accuracy)`
`attempts(attempt_id PK, session_id FK cascade, ts, target_movement, detected_movement, correct, reaction_time_ms, emg_rms, emg_mav, vision_label, confidence)`

## Session upload from games

`BaseGame.save_session` calls `src/utils/session_sync.upload_session` (creates the patient if needed, then posts the session). On failure the payload is appended to `data/logs/pending_sessions.jsonl`; `sync_pending_sessions` uploads the queue after the next successful save or from the dashboard sidebar button.
