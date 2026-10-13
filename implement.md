# implement.md

# Implementation Guide: Gamified Upper-Limb Stroke Rehabilitation System

Current runtime roles: computer vision labels hand gestures and movement direction; the MD0437/ESP32 stream supplies timestamped EMG activity features (RMS, MAV, etc.). Game commands are camera-derived, and combined mode attaches EMG activity for feedback/logging. The legacy EMG classification snippets in this scaffold are optional offline experiments only; their model does not control the games. For the implemented workflow see `architecture.md`, `README.md`, and `python -m src.acquisition.fused_logger`.

---

## Step 0: Environment Setup

```bash
git init stroke-rehab-system && cd stroke-rehab-system
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

mkdir -p config firmware/emg_acquisition data/{raw/emg,raw/vision,processed,features,logs} \
  src/{acquisition,preprocessing,features,models/saved,vision,fusion,realtime,games/assets,utils} \
  backend/routes dashboard notebooks tests docs results/{figures,tables}
touch src/__init__.py
```

**requirements.txt**
```text
numpy
scipy
pandas
scikit-learn
joblib
pyserial
opencv-python
mediapipe
pygame
fastapi
uvicorn
sqlalchemy
streamlit
plotly
requests
pyyaml
pytest
matplotlib
```
```bash
pip install -r requirements.txt
```

**.gitignore**
```text
venv/
__pycache__/
data/raw/
data/processed/
src/models/saved/
*.db
```

**config/labels.yaml**
```yaml
labels: [No_Hand, Rest, Hand_Open, Hand_Close, Left, Right, Up, Down]
```

**config/settings.yaml**
```yaml
serial_port: "COM3"        # Linux/Mac: /dev/ttyUSB0
baud_rate: 921600
fs: 1000                   # EMG sampling rate (Hz)
n_channels: 1
window_ms: 200
step_ms: 100
bandpass: [20, 450]
notch_hz: 50
smoothing_n: 5
min_confidence: 0.6
backend_url: "http://127.0.0.1:8000"
```

---

## Step 1: ESP32 Firmware

**Goal:** stream EMG at 1000 Hz over serial.

`firmware/emg_acquisition/emg_acquisition.ino`
```cpp
// ESP32 EMG acquisition: 1000 Hz, 1 channel (add a 2nd pin if needed)
const int EMG_PIN = 34;                 // ADC1 pin
const unsigned long PERIOD_US = 1000;   // 1000 Hz
unsigned long nextT;

void setup() {
  Serial.begin(921600);
  analogReadResolution(12);             // 0..4095
  analogSetPinAttenuation(EMG_PIN, ADC_11db);
  nextT = micros();
}

void loop() {
  unsigned long now = micros();
  if ((long)(now - nextT) >= 0) {
    nextT += PERIOD_US;
    int v = analogRead(EMG_PIN);
    Serial.print(millis());
    Serial.print(',');
    Serial.println(v);
  }
}
```

**Check:** Arduino Serial Plotter shows a flat line at rest and larger spikes when you squeeze your fist.

---

## Step 2: Data Acquisition Tools

### 2.1 EMG logger with on-screen prompts

`src/acquisition/emg_logger.py`
```python
import serial, time, csv, random, yaml, os, sys

cfg = yaml.safe_load(open("config/settings.yaml"))
labels = yaml.safe_load(open("config/labels.yaml"))["labels"]

subject = sys.argv[1]            # e.g. S01
session = int(sys.argv[2])       # e.g. 1
REPS, HOLD, REST = 15, 4, 3      # reps per class, seconds

ser = serial.Serial(cfg["serial_port"], cfg["baud_rate"], timeout=1)
os.makedirs("data/raw/emg", exist_ok=True)
out = f"data/raw/emg/{subject}_session{session}.csv"

trials = [(l, r) for l in labels for r in range(1, REPS + 1)]
random.shuffle(trials)

def record(label, trial_id, seconds, writer):
    ser.reset_input_buffer()
    end = time.time() + seconds
    while time.time() < end:
        line = ser.readline().decode(errors="ignore").strip()
        parts = line.split(",")
        if len(parts) == 2 and parts[1].isdigit():
            writer.writerow([parts[0], subject, session, trial_id, parts[1], label])

with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp_ms", "subject_id", "session_id", "trial_id", "emg_value", "label"])
    for i, (label, rep) in enumerate(trials, 1):
        print(f"\n[{i}/{len(trials)}] Get ready: {label}")
        time.sleep(2)
        print(f">>> DO: {label}")
        record(label, i, HOLD, w)
        print("... relax")
        record("Rest", i, REST, w)       # rest between reps adds Rest data
print("Saved", out)
```
Run: `python src/acquisition/emg_logger.py S01 1`

### 2.2 Landmark recorder

`src/acquisition/landmark_recorder.py`
```python
import cv2, csv, sys, time
import mediapipe as mp

subject, session, label = sys.argv[1], int(sys.argv[2]), sys.argv[3]
hands = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.6)
cap = cv2.VideoCapture(0)
out = f"data/raw/vision/{subject}_session{session}_{label}.csv"

header = ["frame_id", "timestamp_ms", "subject_id", "session_id"] + \
         [f"{a}{i}" for i in range(21) for a in "xyz"] + ["label"]

with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(header)
    fid, t0 = 0, time.time()
    print("Press SPACE to start/stop recording, Q to quit")
    rec = False
    while True:
        ok, frame = cap.read()
        if not ok: break
        frame = cv2.flip(frame, 1)
        res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if rec and res.multi_hand_landmarks:
            lm = res.multi_hand_landmarks[0].landmark
            row = [fid, int((time.time() - t0) * 1000), subject, session]
            for p in lm: row += [p.x, p.y, p.z]
            w.writerow(row + [label]); fid += 1
        cv2.putText(frame, f"{label} REC={rec}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("recorder", frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord(" "): rec = not rec
        if k == ord("q"): break
cap.release(); cv2.destroyAllWindows()
```
Run once per gesture: `python src/acquisition/landmark_recorder.py S01 1 Hand_Open`

**Check:** CSVs exist in `data/raw/`; class counts are roughly balanced.

---

## Step 3: Preprocessing

`src/preprocessing/filters.py`
```python
import numpy as np
from scipy.signal import butter, filtfilt, iirnotch

def bandpass(x, fs=1000, low=20, high=450, order=4):
    b, a = butter(order, [low/(fs/2), high/(fs/2)], btype="band")
    return filtfilt(b, a, x)

def notch(x, fs=1000, f0=50, q=30):
    b, a = iirnotch(f0/(fs/2), q)
    return filtfilt(b, a, x)

def clean(x, fs=1000):
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x)            # remove DC offset
    return notch(bandpass(x, fs), fs)
```

`src/preprocessing/windowing.py`
```python
import numpy as np

def make_windows(x, fs=1000, window_ms=200, step_ms=100):
    w, s = int(fs*window_ms/1000), int(fs*step_ms/1000)
    return [x[i:i+w] for i in range(0, len(x) - w + 1, s)]
```

**Note:** `filtfilt` is zero-phase and ideal for offline training. For real-time use, filter with `lfilter` and keep filter state (see Step 8).

---

## Step 4: Feature Extraction

`src/features/emg_features.py`
```python
import numpy as np

def extract(w):
    w = np.asarray(w, dtype=float)
    d = np.diff(w)
    thr = 0.01 * np.std(w) if np.std(w) > 0 else 0
    return {
        "RMS":  np.sqrt(np.mean(w**2)),
        "MAV":  np.mean(np.abs(w)),
        "VAR":  np.var(w),
        "STD":  np.std(w),
        "PEAK": np.max(np.abs(w)),
        "WL":   np.sum(np.abs(d)),
        "ZC":   int(np.sum((w[:-1]*w[1:] < 0) & (np.abs(w[:-1]-w[1:]) > thr))),
        "SSC":  int(np.sum((d[:-1]*d[1:] < 0) &
                           ((np.abs(d[:-1]) > thr) | (np.abs(d[1:]) > thr)))),
    }
```

**Build the feature CSV:** `src/features/build_dataset.py`
```python
import glob, pandas as pd, yaml
from src.preprocessing.filters import clean
from src.preprocessing.windowing import make_windows
from src.features.emg_features import extract

cfg = yaml.safe_load(open("config/settings.yaml"))
rows = []
for path in glob.glob("data/raw/emg/*.csv"):
    df = pd.read_csv(path)
    for (subj, sess, trial), g in df.groupby(["subject_id", "session_id", "trial_id"]):
        # a trial may contain active + rest segments; process each label separately
        for label, seg in g.groupby("label", sort=False):
            if len(seg) < cfg["fs"] * cfg["window_ms"] / 1000: continue
            x = clean(seg["emg_value"].values, cfg["fs"])
            for k, w in enumerate(make_windows(x, cfg["fs"], cfg["window_ms"], cfg["step_ms"])):
                feats = extract(w)
                rows.append({"subject_id": subj, "session_id": sess, "trial_id": trial,
                             "window_id": k, **feats, "label": label})

out = pd.DataFrame(rows)
out.to_csv("data/features/emg_features.csv", index=False)
print(out.shape); print(out["label"].value_counts())
```
Run: `python -m src.features.build_dataset`

**Check:** `Rest` has clearly lower `RMS` than active classes. Class counts shown; fix imbalance if large.

---

## Step 5: Train and Evaluate ML Models

`src/models/train_emg.py`
```python
import pandas as pd, numpy as np, joblib
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import matplotlib.pyplot as plt
import seaborn as sns   # pip install seaborn

df = pd.read_csv("data/features/emg_features.csv")
FEATS = ["RMS", "MAV", "VAR", "STD", "PEAK", "WL", "ZC", "SSC"]
X, y, groups = df[FEATS].values, df["label"].values, df["subject_id"].values

models = {
    "LDA": make_pipeline(StandardScaler(), LinearDiscriminantAnalysis()),
    "SVM": make_pipeline(StandardScaler(), SVC(kernel="rbf", C=10, probability=True)),
    "RF":  make_pipeline(StandardScaler(),
                         RandomForestClassifier(n_estimators=200, random_state=42)),
}

best_name, best_acc = None, 0
for name, m in models.items():
    pred = cross_val_predict(m, X, y, groups=groups, cv=LeaveOneGroupOut())  # subject-wise
    acc = accuracy_score(y, pred)
    print(f"\n=== {name}: accuracy {acc:.3f} ===")
    print(classification_report(y, pred))
    cm = confusion_matrix(y, pred, labels=sorted(set(y)))
    sns.heatmap(cm, annot=True, fmt="d", xticklabels=sorted(set(y)), yticklabels=sorted(set(y)))
    plt.title(name); plt.tight_layout()
    plt.savefig(f"results/figures/cm_{name}.png"); plt.clf()
    if acc > best_acc: best_name, best_acc = name, acc

print("Best:", best_name, best_acc)
final = models[best_name].fit(X, y)
joblib.dump(final, "src/models/saved/emg_model.joblib")
```

**Notes**
- If you have only one subject or session, use `GroupKFold` over `trial_id` instead (still no random row splits).
- If some classes (e.g. Flexion vs. Extension) confuse each other, report it honestly and consider the 2-channel upgrade or merging classes.

**Check:** confusion matrices saved in `results/figures/`; `emg_model.joblib` created.

---

## Step 6: Vision Module

`src/vision/hand_tracker.py`
```python
import cv2, numpy as np
import mediapipe as mp

mpH = mp.solutions.hands

def _angle(a, b, c):
    ba, bc = a - b, c - b
    cosv = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return np.degrees(np.arccos(np.clip(cosv, -1, 1)))

class HandTracker:
    def __init__(self):
        self.h = mpH.Hands(max_num_hands=1, min_detection_confidence=0.6,
                           min_tracking_confidence=0.6)

    def process(self, frame_bgr):
        frame = cv2.flip(frame_bgr, 1)
        res = self.h.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not res.multi_hand_landmarks:
            return None
        lm = np.array([[p.x, p.y, p.z] for p in res.multi_hand_landmarks[0].landmark])
        return lm

    @staticmethod
    def features(lm):
        palm = np.linalg.norm(lm[0] - lm[9]) + 1e-9          # scale reference
        tips, pips, mcps = [8, 12, 16, 20], [6, 10, 14, 18], [5, 9, 13, 17]
        curl = [_angle(lm[m], lm[p], lm[t]) for t, p, m in zip(tips, pips, mcps)]
        dist = [np.linalg.norm(lm[t] - lm[0]) / palm for t in tips]
        cx, cy = lm[:, 0].mean(), lm[:, 1].mean()
        # palm normal z-component: sign hints supination vs pronation
        v1, v2 = lm[5] - lm[0], lm[17] - lm[0]
        palm_normal_z = np.cross(v1, v2)[2]
        wrist_angle = np.degrees(np.arctan2(lm[9][1] - lm[0][1], lm[9][0] - lm[0][0]))
        return {"curl": curl, "dist": dist, "cx": cx, "cy": cy,
                "palm_nz": palm_normal_z, "wrist_angle": wrist_angle}

def rule_classify(f):
    """Simple rule-based gesture classifier. Replace/augment with ML later."""
    mean_curl = np.mean(f["curl"])
    if f["cx"] < 0.35: return "Left", 0.8
    if f["cx"] > 0.65: return "Right", 0.8
    if mean_curl > 150: return "Hand_Open", 0.85      # straight fingers
    if mean_curl < 100: return "Hand_Close", 0.85     # curled fingers
    return "Rest", 0.5
```
**Tuning:** the thresholds (0.35/0.65, 150/100) must be calibrated on your own recordings. Print the features while you perform each gesture and pick thresholds from the data. For better accuracy, train a classifier (e.g. Random Forest) on `hand_landmarks.csv` features and save it as `vision_model.joblib`.

**Check:** a live window shows the correct label for open, close, left and right with a stable hand.

---

## Step 7: Fusion Engine

The implemented `src/fusion/fusion_engine.py` uses the webcam movement label as the game command. It smooths the camera label and carries the latest EMG feature values alongside it. EMG activity does not gate, override, or classify movement commands. This lets the game respond to camera-detected Left/Right/Up/Down/Hand_Open/Hand_Close while showing and logging RMS/MAV when the sensor is connected.

Runtime implementation: `src/realtime/pipeline.py`. The EMG thread reads `timestamp_ms,adc_value`, creates windowed EMG features, and updates shared activity state. The vision thread updates camera labels, hand pointer and camera frame. Fusion publishes the camera command and current EMG feature measurements.

## Step 8: Real-Time Pipeline and Command Bus

`main.py vision` starts camera-only control. `main.py live` starts the webcam and the configured serial sensor; it does not require a trained EMG gesture model. In combined mode the command bus carries a camera movement label and the current EMG RMS/MAV values for feedback and session logging. If the EMG sensor is unavailable, camera controls still work and the game reports the missing activity stream.

## Step 9: Games

The current games use the camera as their movement source in Webcam Only and Webcam + EMG modes. Combined mode also shows/logs EMG activity features.

- **Balloon Pop:** the camera pointer aims; a stable complete fist pops the balloon. EMG RMS/MAV are displayed in combined mode.
- **Car Driving:** Left/Right steer and Hand_Close brakes. The game displays EMG RMS/MAV and relative activity when connected.
- **Treasure Hunt:** Left/Right/Up/Down move; Hand_Open selects and Hand_Close collects. EMG activity features accompany attempts.
- **Shape Matching:** the camera pointer and Hand_Close/Hand_Open control pickup/drop. Mouse/Space remain fallbacks when camera control is unavailable.

The combined sensor values are electrical activity indicators and are not clinical muscle-strength scores.

## Step 10: Backend and Database

`backend/app.py`
```python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import sqlite3, datetime

app = FastAPI(title="Rehab Monitoring API")
DB = "rehab.db"

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

with db() as c:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS sessions(
      session_id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, game_name TEXT,
      started_at TEXT, total_score INTEGER, duration_s INTEGER, accuracy REAL);
    CREATE TABLE IF NOT EXISTS attempts(
      attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, ts TEXT,
      target_movement TEXT, detected_movement TEXT, correct INTEGER,
      reaction_time_ms INTEGER, emg_rms REAL);
    """)

class Attempt(BaseModel):
    ts: str; target_movement: str; detected_movement: str
    correct: int; reaction_time_ms: int; emg_rms: float = 0.0

class SessionIn(BaseModel):
    patient_id: str; game_name: str; total_score: int; duration_s: int
    attempts: List[Attempt]

@app.post("/sessions")
def create_session(s: SessionIn):
    acc = sum(a.correct for a in s.attempts) / len(s.attempts) if s.attempts else 0
    with db() as c:
        cur = c.execute("INSERT INTO sessions(patient_id,game_name,started_at,total_score,"
                        "duration_s,accuracy) VALUES(?,?,?,?,?,?)",
                        (s.patient_id, s.game_name, datetime.datetime.now().isoformat(),
                         s.total_score, s.duration_s, acc))
        sid = cur.lastrowid
        c.executemany("INSERT INTO attempts(session_id,ts,target_movement,detected_movement,"
                      "correct,reaction_time_ms,emg_rms) VALUES(?,?,?,?,?,?,?)",
                      [(sid, a.ts, a.target_movement, a.detected_movement, a.correct,
                        a.reaction_time_ms, a.emg_rms) for a in s.attempts])
    return {"session_id": sid, "accuracy": acc}

@app.get("/patients/{pid}/sessions")
def sessions(pid: str):
    return [dict(r) for r in db().execute(
        "SELECT * FROM sessions WHERE patient_id=? ORDER BY started_at", (pid,))]

@app.get("/sessions/{sid}/attempts")
def attempts(sid: int):
    return [dict(r) for r in db().execute("SELECT * FROM attempts WHERE session_id=?", (sid,))]
```
Run: `uvicorn backend.app:app --reload` → API docs at `http://127.0.0.1:8000/docs`

---

## Step 11: Clinician Dashboard

`dashboard/dashboard.py`
```python
import streamlit as st, pandas as pd, requests, plotly.express as px

API = "http://127.0.0.1:8000"
st.set_page_config(page_title="Rehab Dashboard", layout="wide")
st.title("Clinician Dashboard: Stroke Rehabilitation")

pid = st.sidebar.text_input("Patient ID", "P01")
sessions = requests.get(f"{API}/patients/{pid}/sessions").json()

if not sessions:
    st.info("No sessions yet.")
else:
    df = pd.DataFrame(sessions)
    c1, c2, c3 = st.columns(3)
    c1.metric("Sessions", len(df))
    c2.metric("Latest score", int(df["total_score"].iloc[-1]))
    c3.metric("Latest accuracy", f"{df['accuracy'].iloc[-1]*100:.0f}%")

    st.plotly_chart(px.line(df, x="started_at", y="total_score", markers=True,
                            title="Score over time"), use_container_width=True)
    st.plotly_chart(px.line(df, x="started_at", y="accuracy", markers=True,
                            title="Accuracy over time"), use_container_width=True)

    sid = st.selectbox("Session", df["session_id"])
    att = pd.DataFrame(requests.get(f"{API}/sessions/{sid}/attempts").json())
    if not att.empty:
        per = att.groupby("target_movement")["correct"].mean().reset_index()
        st.plotly_chart(px.bar(per, x="target_movement", y="correct",
                               title="Accuracy per movement"), use_container_width=True)
        st.dataframe(att)
    st.download_button("Export sessions CSV", df.to_csv(index=False), "sessions.csv")
```
Run: `streamlit run dashboard/dashboard.py`

---

## Step 12: EMG activity baseline (optional)

Record a relaxed period and comfortable movement periods to compare RMS/MAV activity within a session. Keep sensor placement and gain consistent. These electrical measurements are for relative signal monitoring and analysis; they do not measure clinical muscle strength or control camera movement labels.

---

## Step 13: Testing

`tests/test_features.py`
```python
import numpy as np
from src.features.emg_features import extract

def test_rms_of_constant():
    f = extract(np.ones(200) * 5)
    assert abs(f["RMS"] - 5) < 1e-6

def test_rest_lower_than_active():
    rng = np.random.default_rng(0)
    assert extract(rng.normal(0, 1, 200))["RMS"] < extract(rng.normal(0, 10, 200))["RMS"]
```

`tests/test_fusion.py`
```python
from src.fusion.fusion_engine import FusionEngine

def test_camera_command_carries_emg_features():
    fe = FusionEngine(smoothing_n=1)
    assert fe.fuse(vis=("Hand_Close", 0.9), emg_features={"RMS": 320, "MAV": 290})["command"] == "Hand_Close"

def test_direction_from_vision():
    fe = FusionEngine(smoothing_n=1)
    assert fe.fuse(vis=("Left", 0.9), emg_features={"RMS": 320, "MAV": 290})["command"] == "Left"
```
Run: `pytest -q`

**Integration test checklist**
- [ ] Simulator → game → backend → dashboard works end-to-end
- [ ] Camera labels drive gestures and Left/Right/Up/Down in Webcam Only mode
- [ ] Webcam + EMG keeps camera commands active and displays/logs RMS/MAV
- [ ] Fusion output is stable (no rapid flicker)
- [ ] Latency measured and recorded (< 300 ms target)
- [ ] Game keeps running if the backend is offline (pending log saved)

---

## Step 14: Latency Measurement

Stamp each EMG window with `time.time()` when its last sample arrives, and log the time at which the game reacts to the resulting command. `latency = t_game − t_sample`. Report mean and 95th percentile over 100+ commands.

---

## Step 15: Run Order Summary

```powershell
# Record synchronized EMG samples with webcam-derived movement labels
python -m src.acquisition.fused_logger S01 1 --seconds 120

# Build per-window RMS, MAV and related activity features
python -m src.features.build_dataset

# Optional offline experiment only; this model is not used for game control
python -m src.models.train_emg

# Start API and dashboard
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
streamlit run dashboard/dashboard.py

# Camera labels control the game; the live mode also reads EMG activity
python main.py vision --game balloon
python main.py live --game balloon
```

The fused collector saves raw webcam video nowhere; it writes timestamped EMG samples with the current vision label to `data/raw/emg/*_fused.csv`. Close the Arduino Serial Monitor before starting it so the logger can own the COM port.

## Step 16: Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Flat or saturated EMG | Poor electrode contact, wrong gain | Clean skin, check wiring, adjust sensor gain |
| Strong 50 Hz hum | Mains interference | Battery power, shorter leads, notch filter |
| ADC readings jump when WiFi on | ADC2 pin used | Use ADC1 pins (32-39) |
| Serial lines corrupted | Baud too high or buffer overrun | Lower baud, send in binary, check cable |
| Accuracy high in training, low live | Random split leakage, no calibration | Subject-wise split, add calibration |
| Commands flicker | No smoothing or low confidence | Majority vote, minimum hold time, raise threshold |
| MediaPipe misses hand | Lighting, background, distance | Good lighting, plain background, hand fully in frame |
| Latency too high | Heavy model, large window, slow loop | Smaller window, lighter model, separate threads |

---

## Step 17: Git Workflow

```bash
git checkout -b feature/emg-features
git add . && git commit -m "Add EMG feature extraction"
git push origin feature/emg-features      # open a pull request into main
```
Commit small and often. Never commit `data/raw/` or trained models.

---

## Final Checklist

- [ ] Hardware streams clean EMG
- [ ] Dataset recorded, balanced, quality-checked
- [ ] Models trained with subject-wise evaluation, figures saved
- [ ] Vision tracker stable
- [ ] Fusion engine tested
- [ ] 4 games playable (keyboard, simulator, Webcam Only and Webcam + EMG)
- [ ] Backend and dashboard working end to end
- [ ] Tests pass, latency measured
- [ ] README, report, slides, demo video complete
