# Stroke Rehabilitation Prototype

A local research prototype for EMG and webcam driven upper limb rehabilitation games with session monitoring. It is not a certified medical device. Use coded participant IDs and obtain ethics approval and informed consent before collecting data. Do not attach mains powered equipment to a person.

## Quick start

Python 3.10–3.11 is required (3.11 recommended). Create a virtual environment, install `requirements.txt` (and `requirements-dev.txt` for tests), then run `python main.py keyboard`. Without the ESP32, `python main.py live --emg-source replay` uses a recorded healthy-volunteer EMG signal so Webcam + EMG mode still works. Full setup: [docs/user_guide.md](docs/user_guide.md). Use arrow keys, O/C, S/P and Space. Choose a game with `--game balloon|car|treasure|shape`. Run the API with `uvicorn backend.app:app --reload` and the dashboard with `streamlit run dashboard/dashboard.py`.

`python main.py sim` feeds simulated commands; `python main.py vision` uses the webcam without EMG; `python main.py live` combines the webcam with the configured serial device. The webcam supplies movement labels to the games. The MD0437 signal supplies EMG activity features such as RMS and MAV; an EMG gesture model is not needed for game control. In combined mode, the fusion command carries the camera movement label and the current EMG activity measurements. Webcam video is rendered behind the game objects. Hardware capture and feature analysis are described below. Configuration is in `config/settings.yaml`.

The webcam path supports both legacy MediaPipe Solutions and the current Tasks API. On the Tasks API it downloads Google's hand landmarker model to `data/models/` on first run if the model is not already present. Keep `opencv-contrib-python` at the pinned 4.11 version in `requirements.txt`; OpenCV 5 builds tested here could not open camera indices.

Camera gesture detection combines finger-joint angles with palm-normalized fingertip reach, stabilizes labels across frames, and recognizes Left/Right/Up/Down from palm movement over time. The game pointer follows the middle section of the middle finger. Tune `lr_motion_threshold`, `ud_motion_threshold`, `lr_motion_hold_ms`, `lr_motion_cooldown_ms`, `vision_smoothing_frames`, and `pointer_smoothing_alpha` in `config/settings.yaml`. Camera gestures control all games in Webcam Only and Webcam + EMG modes. Combined mode also shows and records EMG activity features; runtime does not use an EMG classifier to decide movement labels.

**Car Driving** offers Webcam Only and Webcam + EMG Sensor modes: left/right hand movement steers between lanes, Hand_Close brakes, and the combined mode shows live EMG RMS/MAV features plus a relative activity meter. These are electrical signal activity indicators, not clinical muscle-strength scores.

The dashboard has a launcher for four games. Select a game and patient code, then click **Start selected game**. The Pygame window opens on the computer running Streamlit; it does not render inside the browser. In webcam modes, the camera video appears as the background inside the game window, behind the game objects. Progress includes score/accuracy and available average EMG RMS/MAV by detected movement. Press Esc to finish and save the session, or use **Stop running game** in the dashboard.

**Hand Gesture Shape Matching** uses the camera pointer and camera Hand_Close/Hand_Open labels to pick up and drop shapes. Webcam + EMG also displays RMS/MAV activity measurements. If the camera is off, use the mouse or Space key.

## Data and model workflow

To collect **EMG only, without a webcam**, run `python -m src.acquisition.emg_logger S01 3 --labels Rest Hand_Open Hand_Close Left Right Up Down --separate-files --ordered`. The terminal prompts you before each 4-second trial; perform the named movement, and the logger records raw sensor samples with the label you selected. This creates one file per label, such as `data/raw/emg/S01_session3_Rest.csv`. It refuses to overwrite these files, so choose a new session number for another recording. Close Arduino Serial Monitor first and configure the ESP32 COM port and 921600 baud in `config/settings.yaml`.

To collect synchronized EMG and camera-derived movement labels instead, run `python -m src.acquisition.fused_logger S01 1 --seconds 120`. This saves timestamped sensor samples and the current webcam label to `data/raw/emg/`; the preview video is not saved. Build per-window RMS, MAV and other EMG features with `python -m src.features.build_dataset`. `python -m src.models.train_emg` is available for offline experiments comparing EMG features with camera labels; its model is not used to control the games. Keep raw data and model artifacts out of version control.

The single-channel MD0437 is used to measure electrical signal activity, while computer vision identifies the performed movement. RMS, MAV and related values are activity indicators, not clinical muscle-strength measurements. Combined mode requires a connected serial sensor for EMG measurements, while camera-based game control works without a trained model.

For the MD0437 sensor, `SIG` is a filtered and rectified muscle-activity envelope, not raw EMG. `config/settings.yaml` sets `signal_type: envelope`; offline feature building and live monitoring preserve this envelope and skip raw-EMG bandpass/notch filters. The webcam supplies labels such as Hand_Open, Hand_Close, Left, Right, Up and Down. Check the exact board's power requirements and keep SIG within the ESP32 ADC input range before wiring.

## Datasets, results and tests

`Datasets/` holds 11 healthy volunteers (raw and filtered) and 3 **synthetic** simulated patients, 7 gestures each. Build features with `python -m src.features.build_dataset --source public`, train the offline baselines with `python -m src.models.train_emg --features data/features/emg_features_public.csv`, and write activity/data-quality reports with `python -m src.evaluation.emg_activity_report`. The best single-channel baseline reaches 28.8% leave-one-subject-out accuracy on 7 gestures (chance 14.3%), which supports camera-driven control. Run `python -m pytest -q` for the 28 automated tests. Details: [docs/datasets.md](docs/datasets.md), [docs/testing_and_evaluation.md](docs/testing_and_evaluation.md), [docs/model_card_baseline.md](docs/model_card_baseline.md).

Stage 7 (MOMENT-1 fine-tuning) is prepared but waits for approval: [docs/fine_tuning_moment.md](docs/fine_tuning_moment.md).

## API

FastAPI docs are at `/docs`; reference: [docs/api_reference.md](docs/api_reference.md). Sessions saved while the API is down are queued in `data/logs/pending_sessions.jsonl` and uploaded on the next save or from the dashboard sidebar. Endpoints support patients, sessions, attempts, history, progress, and CSV exports. Local SQLite is stored in `data/rehab.db`. There is no authentication in this local prototype; do not expose it to a network or store identifying health data.

## Project map

`src/` signal processing, acquisition, datasets, ML, evaluation, vision, fusion, games and runtime; `tests/` pytest suite; `backend/` local API; `dashboard/` clinician dashboard; `firmware/` ESP32 sketch; `config/` settings; `docs/` user and developer guides, datasets, API, evaluation, model card, fine-tuning plan, protocols and ethics templates. Developer notes: [docs/developer_guide.md](docs/developer_guide.md).
