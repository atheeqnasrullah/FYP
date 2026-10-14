from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import csv, io, os, sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from src.utils.config import ROOT

app=FastAPI(title="Rehabilitation Session API",version="1.0")
DB=Path(os.environ.get("REHAB_DB",ROOT/"data/rehab.db"))

@app.get("/")
def home():
    return {
        "message": "Rehabilitation Session API is running.",
        "dashboard": "http://127.0.0.1:8501",
        "web_app": "/ui",
        "api_docs": "/docs",
        "health": "/health",
    }

def connect():
    DB.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

with closing(connect()) as c:
    c.executescript("""CREATE TABLE IF NOT EXISTS patients(patient_id TEXT PRIMARY KEY, age INTEGER, affected_side TEXT, stroke_date TEXT, notes TEXT);
    CREATE TABLE IF NOT EXISTS sessions(session_id INTEGER PRIMARY KEY AUTOINCREMENT,patient_id TEXT NOT NULL REFERENCES patients(patient_id),game_name TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT,total_score INTEGER NOT NULL,duration_s INTEGER NOT NULL,accuracy REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS attempts(attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,session_id INTEGER NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,ts TEXT,target_movement TEXT,detected_movement TEXT,correct INTEGER,reaction_time_ms INTEGER,emg_rms REAL,emg_mav REAL NOT NULL DEFAULT 0.0,vision_label TEXT,confidence REAL);
    CREATE INDEX IF NOT EXISTS idx_sessions_patient ON sessions(patient_id,started_at); CREATE INDEX IF NOT EXISTS idx_attempts_session ON attempts(session_id);""")
    attempt_columns={row[1] for row in c.execute("PRAGMA table_info(attempts)")}
    if "emg_mav" not in attempt_columns:
        c.execute("ALTER TABLE attempts ADD COLUMN emg_mav REAL NOT NULL DEFAULT 0.0")
    if "vision_label" not in attempt_columns:
        c.execute("ALTER TABLE attempts ADD COLUMN vision_label TEXT")
    c.commit()

class Patient(BaseModel): patient_id:str=Field(pattern=r"^P[A-Za-z0-9_-]{1,20}$"); age:int|None=Field(default=None,ge=0,le=120); affected_side:str|None=None; stroke_date:str|None=None; notes:str|None=None
class Attempt(BaseModel): ts:str|None=None; target_movement:str; detected_movement:str; vision_label:str|None=None; correct:bool; reaction_time_ms:int=Field(ge=0); emg_rms:float=0.; emg_mav:float=0.; confidence:float=0.
class SessionStart(BaseModel): patient_id:str; game_name:str
class AttemptBatch(BaseModel): attempts:list[Attempt]=Field(default_factory=list)
class SessionClose(BaseModel): total_score:int; duration_s:int=Field(ge=0)
class Session(BaseModel): patient_id:str; game_name:str; total_score:int; duration_s:int=Field(ge=0); attempts:list[Attempt]=Field(default_factory=list)

@app.get("/health")
def health(): return {"status":"ok"}

@app.post("/patients")
def create_patient(p:Patient):
    with closing(connect()) as c:
        try: c.execute("INSERT INTO patients VALUES(?,?,?,?,?)",tuple(p.model_dump().values())); c.commit()
        except sqlite3.IntegrityError: raise HTTPException(409,"Patient code already exists")
    return p.model_dump()

@app.get("/patients")
def list_patients():
    with closing(connect()) as c: return [dict(r) for r in c.execute("SELECT patient_id,age,affected_side,stroke_date,notes FROM patients ORDER BY patient_id")]

@app.post("/sessions")
def create_session(s:Session):
    with closing(connect()) as c:
        if not c.execute("SELECT 1 FROM patients WHERE patient_id=?",(s.patient_id,)).fetchone(): raise HTTPException(404,"Create patient before uploading a session")
        acc=sum(a.correct for a in s.attempts)/len(s.attempts) if s.attempts else 0.
        now=datetime.now(timezone.utc).isoformat()
        cur=c.execute("INSERT INTO sessions(patient_id,game_name,started_at,ended_at,total_score,duration_s,accuracy) VALUES(?,?,?,?,?,?,?)",(s.patient_id,s.game_name,now,now,s.total_score,s.duration_s,acc)); sid=cur.lastrowid
        c.executemany("INSERT INTO attempts(session_id,ts,target_movement,detected_movement,vision_label,correct,reaction_time_ms,emg_rms,emg_mav,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",[(sid,a.ts or datetime.now(timezone.utc).isoformat(),a.target_movement,a.detected_movement,a.vision_label,int(a.correct),a.reaction_time_ms,a.emg_rms,a.emg_mav,a.confidence) for a in s.attempts]); c.commit()
    return {"session_id":sid,"accuracy":acc}

@app.post("/sessions/start")
def start_session(s:SessionStart):
    with closing(connect()) as c:
        if not c.execute("SELECT 1 FROM patients WHERE patient_id=?",(s.patient_id,)).fetchone(): raise HTTPException(404,"Patient not found")
        cur=c.execute("INSERT INTO sessions(patient_id,game_name,started_at,total_score,duration_s,accuracy) VALUES(?,?,?,?,?,?)",(s.patient_id,s.game_name,datetime.now(timezone.utc).isoformat(),0,0,0.))
        c.commit(); return {"session_id":cur.lastrowid,"status":"open"}

@app.post("/sessions/{sid}/attempts")
def upload_attempts(sid:int,batch:AttemptBatch):
    with closing(connect()) as c:
        session=c.execute("SELECT ended_at FROM sessions WHERE session_id=?",(sid,)).fetchone()
        if not session: raise HTTPException(404,"Session not found")
        if session["ended_at"] is not None: raise HTTPException(409,"Session is already closed")
        c.executemany("INSERT INTO attempts(session_id,ts,target_movement,detected_movement,vision_label,correct,reaction_time_ms,emg_rms,emg_mav,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",[(sid,a.ts or datetime.now(timezone.utc).isoformat(),a.target_movement,a.detected_movement,a.vision_label,int(a.correct),a.reaction_time_ms,a.emg_rms,a.emg_mav,a.confidence) for a in batch.attempts])
        c.commit(); return {"session_id":sid,"uploaded":len(batch.attempts)}

@app.patch("/sessions/{sid}")
def close_session(sid:int,s:SessionClose):
    with closing(connect()) as c:
        row=c.execute("SELECT ended_at FROM sessions WHERE session_id=?",(sid,)).fetchone()
        if not row: raise HTTPException(404,"Session not found")
        if row["ended_at"] is not None: raise HTTPException(409,"Session is already closed")
        c.execute("UPDATE sessions SET ended_at=?,total_score=?,duration_s=?,accuracy=COALESCE((SELECT AVG(correct) FROM attempts WHERE session_id=?),0) WHERE session_id=?",(datetime.now(timezone.utc).isoformat(),s.total_score,s.duration_s,sid,sid)); c.commit()
        return {"session_id":sid,"status":"closed"}

@app.get("/patients/{pid}/sessions")
def sessions(pid:str):
    with closing(connect()) as c: return [dict(r) for r in c.execute("SELECT * FROM sessions WHERE patient_id=? ORDER BY started_at",(pid,))]

@app.get("/patients/{pid}/progress")
def progress(pid:str):
    with closing(connect()) as c:
        if not c.execute("SELECT 1 FROM patients WHERE patient_id=?",(pid,)).fetchone(): raise HTTPException(404,"Patient not found")
        return {
            "sessions":[dict(r) for r in c.execute("SELECT * FROM sessions WHERE patient_id=? ORDER BY started_at",(pid,))],
            "movement_accuracy":[dict(r) for r in c.execute("SELECT a.target_movement,AVG(a.correct) accuracy,COUNT(*) attempts FROM attempts a JOIN sessions s USING(session_id) WHERE s.patient_id=? GROUP BY a.target_movement",(pid,))],
            "emg_activity_by_movement":[dict(r) for r in c.execute("SELECT a.vision_label movement,AVG(NULLIF(a.emg_rms,0)) mean_rms,AVG(NULLIF(a.emg_mav,0)) mean_mav,COUNT(*) attempts FROM attempts a JOIN sessions s USING(session_id) WHERE s.patient_id=? AND a.vision_label IS NOT NULL AND (a.emg_rms>0 OR a.emg_mav>0) GROUP BY a.vision_label ORDER BY a.vision_label",(pid,))],
        }

@app.get("/sessions/{sid}/attempts")
def attempts(sid:int):
    with closing(connect()) as c: return [dict(r) for r in c.execute("SELECT * FROM attempts WHERE session_id=? ORDER BY attempt_id",(sid,))]

@app.get("/patients/{pid}/export.csv")
def export(pid:str):
    with closing(connect()) as c: rows=c.execute("SELECT s.session_id,s.started_at,s.game_name,s.total_score,s.duration_s,s.accuracy,a.ts,a.target_movement,a.detected_movement,a.vision_label,a.correct,a.reaction_time_ms,a.emg_rms,a.emg_mav,a.confidence FROM sessions s LEFT JOIN attempts a USING(session_id) WHERE s.patient_id=? ORDER BY s.started_at",(pid,)).fetchall()
    if not rows: raise HTTPException(404,"No sessions found")
    buff=io.StringIO(); writer=csv.DictWriter(buff,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(map(dict,rows)); buff.seek(0)
    return StreamingResponse(iter([buff.getvalue()]),media_type="text/csv",headers={"Content-Disposition":f"attachment; filename={pid}_sessions.csv"})

# React web application support (webapp/): extra endpoints, CORS for the Vite
# dev server, and the production build served at /ui when it has been built.
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.webapi import router as web_router

app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["*"],allow_headers=["*"])
app.include_router(web_router)
WEBAPP_DIST=ROOT/"webapp/dist"
if WEBAPP_DIST.is_dir(): app.mount("/ui",StaticFiles(directory=WEBAPP_DIST,html=True),name="webapp")
