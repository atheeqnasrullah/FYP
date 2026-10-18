# User guide

How to install, start and use the rehabilitation prototype. It is a research prototype, not a certified medical device.

## 1. Install (once)

You need **Python 3.11** (3.10 also works; the macOS system Python 3.9 does not) and **Node.js 18 or newer** for the web app.

**macOS** (with [uv](https://docs.astral.sh/uv/)):

```bash
cd FYP
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
cd webapp && npm install && npm run build && cd ..
```

**Windows** (PowerShell):

```powershell
cd FYP
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
cd webapp; npm install; npm run build; cd ..
```

Keep `opencv-contrib-python` pinned at 4.11 (OpenCV 5 builds could not open cameras in testing). MediaPipe's hand model downloads to `data/models/` on first webcam use if it is missing.

## 2. Configure

Edit `config/settings.yaml`, or use the web app's Settings page.

| Key | Default | Change when |
|---|---|---|
| `serial_port` | `COM3` | The ESP32 is on another port. macOS: `/dev/cu.usbserial-*`. The `EMG_SERIAL_PORT` environment variable overrides it |
| `baud_rate` | 921600 | Firmware uses another rate |
| `fs` | 1000 | Data uses another sample rate (`Dataset/` is 100 Hz) |
| `signal_type` | `envelope` | Using a raw-EMG sensor (then `raw`) |
| `window_ms` / `step_ms` | 200 / 100 | Changing the EMG feature window |
| `camera_index` | 0 | Another camera should be used |
| `lr_motion_threshold` / `ud_motion_threshold` | 0.025 / 0.04 | Direction labels fire too easily or not at all |
| `lr_motion_hold_ms` / `lr_motion_cooldown_ms` | 350 / 280 | Directions last too long or repeat too fast |
| `vision_smoothing_frames`, `pointer_smoothing_alpha` | 5, 0.35 | Labels flicker, or the pointer is too jumpy or slow |
| `backend_url` | `http://127.0.0.1:8000` | The API runs on another port |
| `game_session_seconds` | 180 | Different session length; 0 = no limit |
| `game_difficulty` | `auto` | Fixed `easy`, `medium` or `hard` |
| `game_sound` / `game_show_screens` | true / true | Mute sound, or skip start and results screens |

## 3. Start the system

1. Activate the venv in `FYP/`.
2. Start the API: `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`.
   If port 8000 is already used (on the development Mac a Docker container uses it), run `--port 8001` and set `backend_url: "http://127.0.0.1:8001"` so games save to it.
3. Open the web app at `http://127.0.0.1:8000/ui` (or `:8001/ui`).
4. Add a patient (Patients, coded ID such as `P01`), then use **Game Launcher** to choose patient, game, input mode, difficulty and length, and start. The game window opens on this computer.

For web app development use `cd webapp && npm run dev` and `http://localhost:5173`; this mode needs the API on port 8000.

The older Streamlit dashboard still works: `streamlit run dashboard/dashboard.py`, then `http://localhost:8501`.

## 4. Input modes

| Mode | Command | Needs |
|---|---|---|
| Keyboard | `python main.py keyboard --game balloon` | Nothing |
| Simulator | `python main.py sim --game car` | Nothing; a random label every second |
| Webcam only | `python main.py vision --game treasure` | Webcam |
| Webcam + EMG sensor | `python main.py live --game shape` | Webcam, ESP32 + MD0437 |
| Webcam + EMG replay | `python main.py live --emg-source replay --game car` | Webcam; currently broken, the replay recordings were removed |

Options: `--patient P02`, `--difficulty auto|easy|medium|hard`, `--duration 120` (seconds, 0 = no limit). Games are `balloon`, `car`, `treasure` and `shape`.

**In every game:** Enter pauses, M mutes, Esc ends and saves the session.

**Keyboard controls:** arrows move, O opens the hand, C closes it, Space rests, S/P turn Treasure Hunt's lock; Shape Matching uses the mouse (hold left-click or Space to drag).

**Webcam controls:** see [games.md](games.md). In short: move the hand to aim or steer, make a full fist to grab, pop or brake, open the hand to release.

## 5. Sessions

Each session ends with a results screen (score, accuracy, best streak, reaction time, stars, previous best) and is saved to the API. If the API is not running, it is queued in `data/logs/pending_sessions.jsonl` and uploaded on the next save, with the Dashboard's import button, or with the Streamlit sidebar button.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| "Could not open a webcam" | Grant camera permission to the terminal/IDE (macOS: System Settings > Privacy & Security > Camera); close other camera apps; try another `camera_index` |
| Game stuck on "Waiting for valid EMG sensor data" | Check `serial_port` and baud rate, close Arduino Serial Monitor, check the ESP32 is printing lines |
| Web app shows errors or no data | Check the API is running and on the port the page uses; in dev mode the API must be on 8000 |
| Sessions not appearing | Check `backend_url` matches the API port; import queued sessions from the Dashboard |
| Left/Right fire too often | Raise `lr_motion_threshold` or `lr_motion_cooldown_ms` |
| Game window not visible | It opens on the PC running the API, not in the browser; check the taskbar or Dock |
| `ModuleNotFoundError: src` | Run tools as modules from `FYP/`, for example `python -m src.acquisition.emg_logger`, not `python src/...` |

More known problems: [known_issues.md](known_issues.md).
