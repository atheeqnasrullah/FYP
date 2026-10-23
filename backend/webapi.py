"""Extra endpoints used by the React web application (webapp/).

Covers overview statistics, patient/session management, launching the
Pygame games, browsing the EMG datasets and editing config/settings.yaml.
All endpoints are local-only, like the rest of this prototype API.
"""
from contextlib import closing
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import json, re, subprocess, sys

import numpy as np
import pandas as pd
import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.utils.config import ROOT

router = APIRouter()

PATIENT_RE = re.compile(r"^P[A-Za-z0-9_-]{1,20}$")


def _connect():
    # Imported lazily to avoid a circular import with backend.app.
    from backend.app import connect
    return connect()


# ---------------------------------------------------------------- overview
@router.get("/overview")
def overview():
    with closing(_connect()) as c:
        one = lambda q, *a: c.execute(q, a).fetchone()[0]
        return {
            "patients": one("SELECT COUNT(*) FROM patients"),
            "sessions": one("SELECT COUNT(*) FROM sessions"),
            "attempts": one("SELECT COUNT(*) FROM attempts"),
            "avg_accuracy": one("SELECT COALESCE(AVG(accuracy),0) FROM sessions"),
            "total_minutes": one("SELECT COALESCE(SUM(duration_s),0) FROM sessions") / 60,
            "avg_reaction_ms": one("SELECT AVG(reaction_time_ms) FROM attempts"),
            "recent_sessions": [dict(r) for r in c.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT 8")],
            "sessions_by_game": [dict(r) for r in c.execute(
                "SELECT game_name, COUNT(*) sessions, AVG(accuracy) accuracy, AVG(total_score) avg_score FROM sessions GROUP BY game_name ORDER BY sessions DESC")],
            "daily": [dict(r) for r in c.execute(
                "SELECT substr(started_at,1,10) day, COUNT(*) sessions, AVG(accuracy) accuracy FROM sessions GROUP BY day ORDER BY day DESC LIMIT 30")][::-1],
            "movement_accuracy": [dict(r) for r in c.execute(
                "SELECT target_movement, AVG(correct) accuracy, COUNT(*) attempts FROM attempts GROUP BY target_movement ORDER BY target_movement")],
            "pending_sessions": len(_pending_lines()),
        }


# ---------------------------------------------------------------- patients
class PatientUpdate(BaseModel):
    age: int | None = Field(default=None, ge=0, le=120)
    affected_side: str | None = None
    stroke_date: str | None = None
    notes: str | None = None


@router.get("/patients/summary")
def patient_summary():
    """Patients with totals plus a short accuracy history for trend lines and attention flags."""
    with closing(_connect()) as c:
        rows = [dict(r) for r in c.execute(
            """SELECT p.*, COUNT(s.session_id) sessions, AVG(s.accuracy) avg_accuracy,
               MAX(s.started_at) last_session, MAX(s.total_score) best_score
               FROM patients p LEFT JOIN sessions s USING(patient_id)
               GROUP BY p.patient_id ORDER BY p.patient_id""")]
        history = {}
        for r in c.execute("SELECT patient_id, accuracy, game_name FROM sessions ORDER BY started_at"):
            history.setdefault(r["patient_id"], []).append((r["accuracy"], r["game_name"]))
    for row in rows:
        accs = [a for a, _ in history.get(row["patient_id"], [])]
        row["recent_accuracy"] = [round(a, 4) for a in accs[-10:]]
        recent, previous = accs[-3:], accs[-6:-3]
        row["trend"] = (sum(recent) / len(recent) - sum(previous) / len(previous)) if recent and previous else None
        games = [g for _, g in history.get(row["patient_id"], [])]
        row["last_game"] = games[-1] if games else None
    return rows


@router.get("/patients/{pid}")
def get_patient(pid: str):
    with closing(_connect()) as c:
        row = c.execute("SELECT * FROM patients WHERE patient_id=?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "Patient not found")
    return dict(row)


@router.put("/patients/{pid}")
def update_patient(pid: str, p: PatientUpdate):
    with closing(_connect()) as c:
        cur = c.execute("UPDATE patients SET age=?,affected_side=?,stroke_date=?,notes=? WHERE patient_id=?",
                        (p.age, p.affected_side, p.stroke_date, p.notes, pid))
        c.commit()
    if not cur.rowcount:
        raise HTTPException(404, "Patient not found")
    return {"patient_id": pid, **p.model_dump()}


@router.delete("/patients/{pid}")
def delete_patient(pid: str):
    with closing(_connect()) as c:
        c.execute("DELETE FROM sessions WHERE patient_id=?", (pid,))
        cur = c.execute("DELETE FROM patients WHERE patient_id=?", (pid,))
        c.commit()
    if not cur.rowcount:
        raise HTTPException(404, "Patient not found")
    return {"deleted": pid}


# ---------------------------------------------------------------- sessions
@router.get("/sessions")
def list_sessions(patient_id: str | None = None, game_name: str | None = None, limit: int = Query(500, ge=1, le=5000)):
    q, args = "SELECT s.*, (SELECT COUNT(*) FROM attempts a WHERE a.session_id=s.session_id) attempts FROM sessions s WHERE 1=1", []
    if patient_id:
        q += " AND s.patient_id=?"; args.append(patient_id)
    if game_name:
        q += " AND s.game_name=?"; args.append(game_name)
    q += " ORDER BY s.started_at DESC LIMIT ?"; args.append(limit)
    with closing(_connect()) as c:
        return [dict(r) for r in c.execute(q, args)]


@router.get("/sessions/{sid}")
def get_session(sid: int):
    with closing(_connect()) as c:
        row = c.execute("SELECT * FROM sessions WHERE session_id=?", (sid,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return dict(row)


@router.delete("/sessions/{sid}")
def delete_session(sid: int):
    with closing(_connect()) as c:
        cur = c.execute("DELETE FROM sessions WHERE session_id=?", (sid,))
        c.commit()
    if not cur.rowcount:
        raise HTTPException(404, "Session not found")
    return {"deleted": sid}


PENDING = ROOT / "data/logs/pending_sessions.jsonl"


def _pending_lines():
    if not PENDING.exists():
        return []
    return [l for l in PENDING.read_text(encoding="utf-8").splitlines() if l.strip()]


@router.post("/sessions/sync-pending")
def sync_pending():
    """Import sessions that games saved offline while the API was unreachable."""
    from backend.app import Session, Patient, create_session, create_patient
    imported, failed = 0, []
    for line in _pending_lines():
        try:
            s = Session(**json.loads(line))
            if not PATIENT_RE.match(s.patient_id):
                raise ValueError("invalid patient code")
            try:
                create_patient(Patient(patient_id=s.patient_id))
            except HTTPException:
                pass  # already exists
            create_session(s); imported += 1
        except Exception:
            failed.append(line)
    if PENDING.exists():
        PENDING.write_text("".join(l + "\n" for l in failed), encoding="utf-8")
    return {"imported": imported, "failed": len(failed)}


# ---------------------------------------------------------------- game launcher
GAMES = [
    {"id": "balloon", "name": "Balloon Pop", "modes": ["vision", "live", "replay", "keyboard", "sim"],
     "description": "Reach to a balloon and make a full fist to pop it, then open the hand again.",
     "trains": ["Reaching", "Hand close", "Hand open"]},
    {"id": "car", "name": "Car Driving", "modes": ["vision", "live", "replay", "keyboard", "sim"],
     "description": "Hold the hand left, middle or right to pick a lane and catch stars; a fist brakes.",
     "trains": ["Side-to-side reach", "Holding a position", "Hand close"]},
    {"id": "treasure", "name": "Treasure Hunt", "modes": ["vision", "live", "replay", "keyboard", "sim"],
     "description": "Push the hand like a joystick to walk the island, then open and close it at each chest.",
     "trains": ["Left / right / up / down", "Hand open", "Hand close"]},
    {"id": "shape", "name": "Hand Gesture Shape Matching", "modes": ["vision", "live", "replay", "keyboard", "sim"],
     "description": "Grasp a shape with a fist, carry it to the matching hole and release it.",
     "trains": ["Grasp and release", "Reaching", "Precision"]},
]
MODES = {"vision": "Webcam only", "live": "Webcam + EMG sensor", "replay": "Webcam + EMG replay (no sensor)",
         "keyboard": "Keyboard controls", "sim": "Simulator"}
LOG = ROOT / "data/logs/dashboard_game.log"
_running: dict = {"proc": None, "info": None}


DIFFICULTIES = ("auto", "easy", "medium", "hard")


class Launch(BaseModel):
    game: str
    mode: str
    patient_id: str
    difficulty: str = "auto"
    duration_s: int = Field(default=180, ge=0, le=3600)
    effort: str = "auto"   # grip effort needed in Webcam + EMG modes: auto or 0-100 (% of the patient's strongest squeeze)


def _status():
    proc = _running["proc"]
    if proc is not None and proc.poll() is not None:
        _running["info"] = {**_running["info"], "exit_code": proc.returncode}
        _running["proc"] = None
        proc = None
    return {"running": proc is not None, "pid": proc.pid if proc else None, "last": _running["info"]}


@router.get("/games")
def games():
    return {"games": GAMES, "modes": MODES}


@router.get("/games/status")
def game_status():
    return _status()


@router.post("/games/launch")
def launch(req: Launch):
    game = next((g for g in GAMES if g["id"] == req.game), None)
    if not game:
        raise HTTPException(400, "Unknown game")
    if req.mode not in game["modes"]:
        raise HTTPException(400, f"Mode '{req.mode}' is not available for {game['name']}")
    if not PATIENT_RE.match(req.patient_id.strip()):
        raise HTTPException(400, "Patient code must start with P and contain only letters, numbers, _ or - (up to 21 characters).")
    if req.difficulty not in DIFFICULTIES:
        raise HTTPException(400, "Difficulty must be auto, easy, medium or hard")
    from src.games.effort import parse_required
    try:
        effort = parse_required(req.effort)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if _status()["running"]:
        raise HTTPException(409, "A game is already running. Stop it before starting another.")
    # Close any live sensor/camera preview in the web app so the game can open the devices.
    from backend.hardware import release_all
    release_all()
    # "replay" is live mode with EMG played from Dataset/ instead of the ESP32.
    command = [sys.executable, "-u", str(ROOT / "main.py"), "live" if req.mode == "replay" else req.mode, "--game", req.game,
               "--patient", req.patient_id.strip(), "--difficulty", req.difficulty, "--duration", str(req.duration_s)]
    if req.mode == "replay":
        command += ["--emg-source", "replay"]
    if req.mode in ("live", "replay"):
        command += ["--effort", "auto" if effort == "auto" else f"{effort:g}"]
    options = {"cwd": str(ROOT), "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with LOG.open("w", encoding="utf-8") as log:
            log.write(f"Web app launch command: {subprocess.list2cmdline(command)}\n"); log.flush()
            proc = subprocess.Popen(command, stdout=log, stderr=log, **options)
    except OSError as exc:
        raise HTTPException(500, f"Could not start the game: {exc}")
    _running["proc"] = proc
    _running["info"] = {"game": req.game, "game_name": game["name"], "mode": req.mode, "patient_id": req.patient_id.strip(),
                        "difficulty": req.difficulty, "duration_s": req.duration_s, "effort": req.effort, "started_at": datetime.now(timezone.utc).isoformat(), "exit_code": None}
    return _status()


@router.post("/games/stop")
def stop():
    proc = _running["proc"]
    if proc is None or proc.poll() is not None:
        return {**_status(), "message": "No game is currently running."}
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    return {**_status(), "message": "Game stopped."}


@router.get("/games/log")
def game_log(lines: int = Query(80, ge=1, le=1000)):
    if not LOG.exists():
        return {"lines": []}
    return {"lines": LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]}


# ---------------------------------------------------------------- datasets
DATASET_DIRS = [("Dataset", "Reference datasets"), ("data/raw/emg", "Recorded sessions")]
SKIP_COLS = {"timestamp_ms", "subject_id", "session_id", "trial_id", "vision_confidence", "pointer_x", "pointer_y"}
LABEL_COLS = ("label", "movement_label")


def _label_col(df: pd.DataFrame):
    return next((c for c in LABEL_COLS if c in df.columns), None)


def _resolve(file: str) -> Path:
    path = (ROOT / file).resolve()
    allowed = [(ROOT / d).resolve() for d, _ in DATASET_DIRS]
    if path.suffix.lower() != ".csv" or not any(path.is_relative_to(a) for a in allowed) or not path.is_file():
        raise HTTPException(404, "Dataset file not found")
    return path


def _category(rel: str) -> str:
    low = rel.lower()
    if "patiant" in low or "patient" in low or "stroke" in low:
        return "patient"
    if "healthy" in low or "volunteer" in low or "normal" in low or "noraml" in low:
        return "filtered" if "filtered" in low else "normal"
    return "recorded"


@lru_cache(maxsize=64)
def _load(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed") and str(c) != ""]]
    return df


def _frame(file: str):
    p = _resolve(file)
    return _load(str(p), p.stat().st_mtime)


def _signal_columns(df: pd.DataFrame):
    return [c for c in df.columns if str(c).lower() not in SKIP_COLS and pd.api.types.is_numeric_dtype(df[c])]


def _natural(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


@router.get("/datasets")
def list_datasets():
    out = []
    for d, group in DATASET_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.csv"), key=lambda x: _natural(str(x))):
            rel = p.relative_to(ROOT).as_posix()
            with p.open(encoding="utf-8", errors="replace") as f:
                header = f.readline().strip().split(",")
                rows = sum(1 for _ in f)
            out.append({"file": rel, "name": p.stem, "group": group, "folder": p.parent.relative_to(ROOT).as_posix(),
                        "category": _category(rel), "rows": rows, "columns": [h for h in header if h], "size_kb": round(p.stat().st_size / 1024, 1)})
    return out


def _decimate(values: np.ndarray, n: int) -> np.ndarray:
    """Downsample keeping the largest-magnitude sample in each bucket so peaks survive."""
    if len(values) <= n:
        return values
    edges = np.linspace(0, len(values), n + 1).astype(int)
    out = np.empty(n)
    for i in range(n):
        seg = values[edges[i]:edges[i + 1]]
        out[i] = seg[np.argmax(np.abs(seg))] if len(seg) else np.nan
    return out


@router.get("/datasets/signal")
def dataset_signal(file: str, points: int = Query(1200, ge=50, le=10000)):
    df = _frame(file)
    cols = _signal_columns(df)
    if df.empty or not cols:
        return {"file": file, "rows": len(df), "columns": cols, "index": [], "series": {}, "labels": None}
    n = min(points, len(df))
    edges = np.linspace(0, len(df), n + 1).astype(int)[:-1]
    series = {c: [None if np.isnan(v) else round(float(v), 6) for v in _decimate(df[c].to_numpy(dtype=float), n)] for c in cols}
    label_col = _label_col(df)
    labels = df[label_col].astype(str).to_numpy()[edges].tolist() if label_col else None
    ts = next((c for c in df.columns if str(c).lower() == "timestamp_ms"), None)
    index = (df[ts].to_numpy()[edges] if ts else edges).tolist()
    return {"file": file, "rows": len(df), "columns": cols, "index": index, "series": series, "labels": labels}


def _features(x: np.ndarray) -> dict:
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return {}
    d = np.diff(x)
    return {"RMS": float(np.sqrt(np.mean(x ** 2))), "MAV": float(np.mean(np.abs(x))), "VAR": float(np.var(x)),
            "STD": float(np.std(x)), "PEAK": float(np.max(np.abs(x))), "WL": float(np.sum(np.abs(d)) / len(x)),
            "samples": int(len(x))}


def _windowed_rms(x: np.ndarray, window: int, step: int, limit: int = 600):
    x = np.nan_to_num(x)
    if len(x) < window:
        return []
    starts = range(0, len(x) - window + 1, step)
    rms = [float(np.sqrt(np.mean(x[s:s + window] ** 2))) for s in starts]
    if len(rms) > limit:
        idx = np.linspace(0, len(rms) - 1, limit).astype(int)
        rms = [rms[i] for i in idx]
    return [round(v, 6) for v in rms]


@router.get("/datasets/features")
def dataset_features(file: str, window: int = Query(200, ge=10, le=5000), step: int = Query(100, ge=1, le=5000)):
    df = _frame(file)
    cols = _signal_columns(df)
    result = {"file": file, "window": window, "step": step, "features": [], "rms_series": {}}
    if df.empty:
        return result
    label_col = _label_col(df)
    if label_col and len(cols) == 1:
        # Long format recordings: one emg column labelled by movement.
        col = cols[0]
        for label, g in df.groupby(label_col):
            result["features"].append({"movement": str(label), **_features(g[col].to_numpy(dtype=float))})
        result["rms_series"][col] = _windowed_rms(df[col].to_numpy(dtype=float), window, step)
    else:
        for col in cols:
            x = df[col].to_numpy(dtype=float)
            result["features"].append({"movement": col, **_features(x)})
            result["rms_series"][col] = _windowed_rms(x, window, step)
    return result


@router.get("/datasets/compare")
def dataset_compare():
    """Mean RMS/MAV per movement for each dataset category (normal raw, normal filtered, patient)."""
    files = [f for f in list_datasets() if f["category"] != "recorded" and f["rows"] > 1]
    acc: dict = {}
    for f in files:
        df = _frame(f["file"])
        cols, label_col = _signal_columns(df), _label_col(df)
        if label_col and len(cols) == 1:
            # Long format (Dataset/): one signal column, movement in the label column.
            parts = [(str(label), g[cols[0]]) for label, g in df.groupby(label_col)]
        else:
            parts = [(col, df[col]) for col in cols]
        for movement, values in parts:
            feats = _features(values.to_numpy(dtype=float))
            if not feats:
                continue
            bucket = acc.setdefault(f["category"], {}).setdefault(movement, {"RMS": [], "MAV": []})
            bucket["RMS"].append(feats["RMS"]); bucket["MAV"].append(feats["MAV"])
    out = {}
    for cat, movements in acc.items():
        out[cat] = [{"movement": m, "RMS": float(np.mean(v["RMS"])), "MAV": float(np.mean(v["MAV"])),
                     "RMS_std": float(np.std(v["RMS"])), "files": len(v["RMS"])} for m, v in movements.items()]
    return {"categories": out, "files": {c: sum(1 for f in files if f["category"] == c) for c in out}}


# ---------------------------------------------------------------- settings
SETTINGS = ROOT / "config/settings.yaml"
LABELS = ROOT / "config/labels.yaml"


@router.get("/settings")
def get_settings():
    return {"settings": yaml.safe_load(SETTINGS.read_text(encoding="utf-8")) or {},
            "labels": (yaml.safe_load(LABELS.read_text(encoding="utf-8")) or {}).get("labels", []) if LABELS.exists() else [],
            "raw": SETTINGS.read_text(encoding="utf-8")}


class SettingsUpdate(BaseModel):
    raw: str


@router.put("/settings")
def put_settings(body: SettingsUpdate):
    try:
        parsed = yaml.safe_load(body.raw)
    except yaml.YAMLError as exc:
        raise HTTPException(400, f"Invalid YAML: {exc}")
    if not isinstance(parsed, dict):
        raise HTTPException(400, "Settings must be a YAML mapping")
    SETTINGS.write_text(body.raw if body.raw.endswith("\n") else body.raw + "\n", encoding="utf-8")
    return get_settings()
