# User guide

How to install, start and use the rehabilitation prototype. It is a research prototype, not a certified medical device.

## 1. Install (once)

Python 3.10 or 3.11 is required (the backend uses `int | None` syntax). 3.11 is recommended because the optional fine-tuning stage needs it.

**macOS** (with [uv](https://docs.astral.sh/uv/)):

```bash
cd FYP
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
```

**Windows** (PowerShell):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

Keep `opencv-contrib-python` pinned at 4.11 (OpenCV 5 builds could not open cameras in testing). On first webcam use, MediaPipe's hand model downloads to `data/models/` if it is not there.

## 2. Configure

Edit `config/settings.yaml`:

| Setting | Default | Change when |
|---|---|---|
| `serial_port` | `COM3` | The ESP32 is on another port. macOS: `/dev/cu.usbserial-*` or `/dev/cu.SLAB_USBtoUART`. You can also set the `EMG_SERIAL_PORT` environment variable instead of editing the file |
| `baud_rate` | 921600 | Firmware uses a different rate |
| `camera_index` | 0 | Another camera should be used |
| `backend_url` | `http://127.0.0.1:8000` | The API runs on another port (see below) |
| `lr_motion_threshold`, `ud_motion_threshold` | 0.025, 0.04 | Left/Right or Up/Down trigger too easily or not at all |

## 3. Start the system

Open three terminals in `FYP/` with the venv active.

1. **API:** `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`
   If port 8000 is already used (for example by Docker), use `--port 8001` and set `backend_url: "http://127.0.0.1:8001"` in `config/settings.yaml` and the dashboard's sidebar API URL.
2. **Dashboard:** `streamlit run dashboard/dashboard.py` and open http://localhost:8501.
3. **Games:** start from the dashboard ("Start selected game"), or from the terminal as below.

## 4. Input modes

| Mode | Command | Needs |
|---|---|---|
| Keyboard | `python main.py keyboard --game balloon` | Nothing |
| Simulator | `python main.py sim --game car` | Nothing (random labels every second) |
| Webcam only | `python main.py vision --game car` | Webcam |
| Webcam + EMG sensor | `python main.py live --game car` | Webcam + ESP32 with MD0437 |
| Webcam + EMG replay | `python main.py live --emg-source replay --game car` | Webcam; EMG comes from a recorded healthy volunteer |

Add `--patient P02` to save the session under another coded patient ID (must start with `P`). For replay, `EMG_REPLAY_SUBJECT=H03` picks another volunteer and `EMG_REPLAY_SOURCE=healthy_filtered` uses the smoothed recordings.

**Keyboard controls:** arrows = Left/Right/Up/Down, O = Hand_Open, C = Hand_Close, S/P = Supination/Pronation (Treasure Hunt lock), Space = Rest, Esc = finish and save.

**Webcam controls:** move the open hand left/right/up/down to produce direction labels; close the hand (or pinch thumb and index) for Hand_Close; open all fingers for Hand_Open. The pointer follows the middle finger.

## 5. The games

| Game | Goal | Webcam action | Keyboard action |
|---|---|---|---|
| Balloon Pop | Pop rising balloons | Aim with the hand, make a full five-finger fist on a balloon | Arrows move the cursor, C pops |
| Car Driving | Steer into the target lane, avoid cars | Move the hand left/right; close the hand to brake | Left/Right arrows; C brakes |
| Treasure Hunt | Collect treasures | Move the hand to walk; open the hand to select the nearest treasure, close to collect | Arrows walk; O selects; C collects; S/P turn the lock (must be 0/4) |
| Shape Matching | Drag shapes onto their outlines | Point, close the hand to pick up, open to drop | Mouse; hold left-click or Space to drag |

In Webcam + EMG modes the game waits for fresh EMG data before play, then shows RMS/MAV activity values. These values describe electrical activity, not muscle strength.

## 6. Sessions and the dashboard

Pressing Esc saves the session (score, duration, every attempt with target, detected movement, reaction time, EMG RMS/MAV). If the API is not running, the session is queued in `data/logs/pending_sessions.jsonl`. The queue is uploaded automatically the next time a game saves while the API is up, or with **Upload offline sessions** in the dashboard sidebar.

The dashboard's Progress section shows score and accuracy by session, accuracy per movement, EMG activity per camera-detected movement, a session table and a CSV export.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| "Could not open a webcam" | Grant camera permission to the terminal/IDE (macOS: System Settings → Privacy & Security → Camera); close other camera apps; try another `camera_index` |
| Game stuck on "Waiting for valid EMG sensor data" | Check the serial port and baud rate, close Arduino Serial Monitor, or use `--emg-source replay` |
| Dashboard says it cannot reach the API | Start uvicorn; check the API URL in the sidebar; check nothing else uses the port |
| Left/Right fire too often | Raise `lr_motion_threshold` or `lr_motion_cooldown_ms` |
| Game window not visible (Windows) | It opens on the PC running Streamlit, not in the browser; check the taskbar |
