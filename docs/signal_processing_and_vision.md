# Signal processing, vision and fusion

EMG is cut into 200 ms windows every 100 ms and each window yields eight activity features; the camera produces a movement label for every frame; the fusion engine pairs the two every 50 ms. The same feature code runs offline and live.

## EMG processing

1. **Filter** (`src/preprocessing/filters.py`, `clean()`):
    - `signal_type: envelope` (MD0437, the default): the signal passes through unchanged.
    - `signal_type: raw`: mean removed, 4th-order Butterworth bandpass 20-450 Hz (zero-phase offline, causal second-order sections live) and a 50 Hz notch (Sri Lanka mains frequency).
2. **Window** (`src/preprocessing/windowing.py`, `make_windows()`): `window_ms` 200 and `step_ms` 100, converted to samples with `fs`. At 1 kHz that is 200 samples with a 100-sample step; at 100 Hz (`Dataset/`) it is 20 and 10.
3. **Extract** (`src/features/emg_features.py`, `extract()`):

| Feature | Meaning |
|---|---|
| RMS | Root mean square: overall activity level |
| MAV | Mean absolute value |
| VAR, STD | Variance and standard deviation |
| PEAK | Largest absolute sample |
| WL | Waveform length: sum of absolute sample-to-sample changes |
| ZC | Zero crossings above a noise threshold (raw signals only; 0 for envelopes) |
| SSC | Slope sign changes above the threshold |

These describe electrical activity, not muscle strength.

**Offline feature tables:** `python -m src.features.build_dataset` reads your recordings in `data/raw/emg/` (using `fs` from the settings) and writes `data/features/emg_features.csv`. `--source healthy|stroke_synthetic|public` reads `Dataset/` at its own 100 Hz and writes `data/features/emg_features_<source>.csv` (41,066 windows for `public`).

## Vision

`src/vision/hand_tracker.py` wraps MediaPipe (the Tasks API hand landmarker in MediaPipe 1.1; the older Solutions API is used when present). The model file downloads to `data/models/hand_landmarker.task` on first use.

**Hand features** computed from the 21 landmarks:

- finger curl angles at each finger's middle joint;
- fingertip reach divided by palm size, so rules work at any camera distance;
- thumb-index pinch ratio;
- a strict `full_fist` flag (all fingers closed and the thumb near the palm);
- palm centre, palm orientation and wrist angle.

**Gesture rules** (`rule_classify`):

| Condition | Label | Confidence |
|---|---|---|
| Pinch ratio below 0.34 | Hand_Close | 0.92 |
| 3 or more extended fingers | Hand_Open | 0.78-0.96 |
| 1 or fewer extended fingers, curled and short reach | Hand_Close | 0.76-0.94 |
| Anything else | Rest | 0.65 |

**Smoothing:** a label is kept only when at least 3 of the last 5 frames agree (`vision_smoothing_frames: 5`).

**Directions:** Left, Right, Up and Down come from palm-centre movement relative to an anchor point: thresholds `lr_motion_threshold` 0.025 and `ud_motion_threshold` 0.04 of the frame. The direction is held for `lr_motion_hold_ms` (350 ms) with a `lr_motion_cooldown_ms` (280 ms) cooldown, and a closed hand resets the anchor.

**Pointer:** the midpoint of the middle finger's PIP and DIP joints, smoothed with `pointer_smoothing_alpha` 0.35. Balloon Pop, Car Driving, Treasure Hunt and Shape Matching read the pointer directly for aiming, lane choice and the joystick.

## Fusion

`src/fusion/fusion_engine.py`, run by `pipeline._fusion` every 50 ms:

1. Take the latest camera label; below `min_confidence` (0.6) it becomes Rest.
2. Majority vote over the last `smoothing_n` (5) labels.
3. Attach the latest EMG feature window (`emg_rms`, `emg_mav`, `emg_features`) and the camera frame's capture time (`vision_ts_ms`).
4. Put the command on the command bus (50 slots; the oldest is dropped when full).

EMG never overrides or suppresses a camera label. Its only effect on play is that Webcam + EMG mode waits until fresh EMG data arrives.

## EMG sources

| Source | Code | When |
|---|---|---|
| ESP32 serial | `pipeline._emg` | `python main.py live` |
| Dataset replay | `src/realtime/emg_replay.py` | `python main.py live --emg-source replay`: plays `Dataset/` (default S02) in real time at 100 Hz |
| None | | `vision`, `keyboard` and `sim` modes |
