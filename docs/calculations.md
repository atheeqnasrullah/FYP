# Calculations: from sensor to results

Every calculation the system performs, in the order data flows through it: EMG acquisition, signal processing, features, effort, camera gestures, fusion, games, session records, the web app, and the offline machine-learning research. Each section gives the formula, a worked example with the project's own numbers, and the file where it is implemented.

Contents

1. [EMG acquisition](#1-emg-acquisition)
2. [Signal conditioning](#2-signal-conditioning)
3. [Windowing](#3-windowing)
4. [EMG features](#4-emg-features)
5. [Grip effort: calibration and percentage](#5-grip-effort-calibration-and-percentage)
6. [Computer vision: hand features and gesture rules](#6-computer-vision-hand-features-and-gesture-rules)
7. [Smoothing, pointer and directions](#7-smoothing-pointer-and-directions)
8. [Fusion](#8-fusion)
9. [Games: difficulty, levels, scoring and results](#9-games-difficulty-levels-scoring-and-results)
10. [Backend and dashboard statistics](#10-backend-and-dashboard-statistics)
11. [Web app: EMG Datasets page](#11-web-app-emg-datasets-page)
12. [Offline machine learning](#12-offline-machine-learning)
13. [Evaluation metrics](#13-evaluation-metrics)
14. [Reports: data quality, activity and latency](#14-reports-data-quality-activity-and-latency)
15. [Quick reference](#15-quick-reference)

---

## 1. EMG acquisition

**What:** the ESP32 turns the MD0437 envelope voltage into a number.

| Quantity | Value | Calculation |
|---|---|---|
| ADC resolution | 12 bit | 2^12 = 4096 levels, so `adc_value` is 0 to 4095 |
| Firmware sample rate | 1 kHz | one reading every 1000 µs (`micros()` timer) |
| Dataset sample rate | 100 Hz | one row every 10 ms in `Dataset/` |
| Samples per 60 s recording | 6,000 | 60 s × 100 Hz |

**Validation (live):** a serial line is used only if it has exactly two numbers, both finite, and `0 ≤ adc_value ≤ 4095`. If no valid sample arrives for 2.5 s, Webcam + EMG games pause.

Where: `firmware/emg_acquisition/emg_acquisition.ino`, `src/realtime/pipeline.py` (`_emg`).

---

## 2. Signal conditioning

The MD0437 already amplifies, rectifies and smooths the EMG, so with `signal_type: envelope` (the project's setting) the signal **passes through unchanged**. Filtering would remove the activity level the project relies on.

The raw-EMG path exists for other sensors (`signal_type: raw`) and is not used with the MD0437:

| Step | Formula / setting | Purpose |
|---|---|---|
| Remove DC offset (offline) | x ← x − mean(x) | centre the signal on 0 |
| Remove DC offset (live) | dc ← 0.999·dc + 0.001·x, then x − dc | slow running mean (time constant ≈ 1000 samples = 1 s at 1 kHz) |
| Band-pass | 4th-order Butterworth, 20–450 Hz; cut-offs divided by the Nyquist frequency fs/2 | keep muscle frequencies, drop motion artefacts and high-frequency noise |
| Notch | IIR notch at 50 Hz, quality factor Q = 30 (bandwidth ≈ 50/30 ≈ 1.7 Hz) | remove Sri Lankan mains hum |

Offline filtering uses `filtfilt` (forward and backward, so no phase delay); live filtering uses causal second-order sections (`sosfilt`).

Where: `src/preprocessing/filters.py`, `src/realtime/pipeline.py`.

---

## 3. Windowing

The signal is cut into overlapping windows; each window becomes one set of features.

```
width  = round(fs × window_ms / 1000)
stride = round(fs × step_ms / 1000)
windows start at 0, stride, 2·stride, …  while start + width ≤ N
number of windows = floor((N − width) / stride) + 1
```

| Use | fs | Window | Step | Samples per window | Overlap |
|---|---|---|---|---|---|
| Live (firmware) | 1000 Hz | 200 ms | 100 ms | 200 | 50% |
| Offline, `Dataset/` | 100 Hz | 200 ms | 100 ms | 20 | 50% |
| MOMENT-1 | 100 Hz | 5.12 s | 1.28 s | 512 | 75% |

**Worked example:** a 60 s recording at 100 Hz has N = 6,000 samples. With 200 ms windows: (6000 − 20)/10 + 1 = **599 windows**. With MOMENT windows: floor((6000 − 512)/128) + 1 = 42 + 1 = **43 windows**, which is exactly the 43 windows per movement per stroke patient reported in `docs/fine_tuning_moment.md`.

Where: `src/preprocessing/windowing.py`, `src/data/prepare_finetune.py`.

---

## 4. EMG features

Eight features are computed from each window w = (w₁ … w_N). Let dᵢ = wᵢ₊₁ − wᵢ (sample-to-sample change) and threshold = 0.01 × STD(w).

| Feature | Formula | Meaning |
|---|---|---|
| RMS | √( (1/N) Σ wᵢ² ) | overall activity level |
| MAV | (1/N) Σ \|wᵢ\| | average absolute activity |
| VAR | (1/N) Σ (wᵢ − w̄)² | spread around the mean |
| STD | √VAR | spread, in ADC units |
| PEAK | max \|wᵢ\| | largest reading |
| WL | Σ \|dᵢ\| | waveform length: how much the signal moves |
| ZC | count of i where wᵢ·wᵢ₊₁ < 0 and \|dᵢ\| > threshold | zero crossings; **always 0 for the envelope** (it never goes below 0) |
| SSC | count of i where dᵢ·dᵢ₊₁ < 0 and (\|dᵢ\| or \|dᵢ₊₁\|) > threshold | slope sign changes: peaks and valleys |

**Worked example:** w = [0, 10, 20].

- RMS = √((0 + 100 + 400)/3) = √166.7 = **12.91**
- MAV = (0 + 10 + 20)/3 = **10**
- mean = 10, so VAR = ((−10)² + 0² + 10²)/3 = **66.67**, STD = **8.16**
- PEAK = **20**
- d = [10, 10], so WL = **20**, and SSC = **0** (the slope never changes sign)

These measure **electrical activity, not muscle strength**.

Where used: live game feedback (RMS drives the effort bar), the offline 200 ms and 5.12 s classifiers, the web app, the activity report. Code: `src/features/emg_features.py`.

---

## 5. Grip effort: calibration and percentage

Because the envelope is in ADC units, effort is measured against **each patient's own range**.

**Calibration (relax-then-squeeze check at the start of a Webcam + EMG session):**

```
rest      = median(RMS readings while relaxed)
strongest = 90th percentile(RMS readings while squeezing)
valid only if  strongest − rest ≥ 0.05 × strongest      (at least 5% above rest)
```

The median ignores occasional spikes at rest; the 90th percentile captures a strong squeeze without trusting the single highest value. With EMG replay, the recording's own Rest and Hand_Close sections stand in for the check.

**Effort percentage (every EMG window):**

```
effort % = (RMS − rest) / (strongest − rest) × 100,   clipped to 0–100
```

**Worked example:** rest = 120, strongest = 980, current RMS = 550 → (550 − 120)/(980 − 120) × 100 = 430/860 × 100 = **50.0%**.

**Without a calibration**, the game shows activity relative to the strongest reading so far: activity % = 100 × RMS / (session peak RMS).

**Activity words:** below 35% = Low, 35–70% = Medium, 70% and above = High.

**Effort needed (auto mode)** rises with difficulty from 25% to 60%, using the interpolation in [section 9.1](#91-difficulty-interpolation):

```
needed % = 25 + (60 − 25) × t
```

| Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Effort needed | 25.0% | 30.8% | 36.7% | 42.5% | 48.3% | 54.2% | 60.0% |

**Grip gate:** a fist (pop, brake, grab, pick up) counts only when effort % ≥ needed %. A fist that opens without reaching it is logged as `Weak_Grip`, with the best effort reached ("Squeeze harder: 31% of 43%").

Where: `src/games/effort.py`, `src/games/game_engine.py` (`emg_activity`, `grip`, `setup_effort`).

---

## 6. Computer vision: hand features and gesture rules

MediaPipe returns 21 landmarks per hand, each (x, y, z) with x and y as fractions of the frame (0–1). Landmark 0 is the wrist, 4 the thumb tip, 5/9/13/17 the finger bases (MCP), 6/10/14/18 the middle joints (PIP), 8/12/16/20 the fingertips.

### 6.1 Hand features

| Feature | Formula | Why |
|---|---|---|
| Palm size | ‖L0 − L9‖ (wrist to middle-finger base) | scale reference, so rules work at any camera distance |
| Finger curl angle | angle at the PIP joint between MCP and tip: θ = arccos( (a·b) / (‖a‖‖b‖) ), with a = MCP − PIP, b = tip − PIP | 180° = straight finger, smaller = bent |
| Reach | ‖tip − L0‖ / ‖MCP − L0‖ | how far the fingertip is from the wrist, relative to the finger base |
| Extended finger | curl ≥ 145° **and** reach ≥ 1.12 | both measures must agree |
| Fingers closed | every finger curl < 135° and reach < 1.20 | |
| Thumb to palm | min distance from thumb tip (L4) to L5, L9 or L13, divided by palm size | |
| Full fist | fingers closed **and** thumb to palm < 0.72 | strict fist used by the grip actions |
| Pinch ratio | ‖L4 − L8‖ / palm size (thumb tip to index tip) | |
| Palm centre | cx = mean x of L0, L5, L9, L13, L17; cy = mean y of all 21 | used for directions |

### 6.2 Gesture rules and confidence

Checked in this order (`rule_classify`):

| Condition | Label | Confidence |
|---|---|---|
| Pinch ratio < 0.34 | Hand_Close | 0.92 |
| 3 or more extended fingers (n) | Hand_Open | min(0.96, 0.78 + 0.06 × (n − 3)) |
| 1 or fewer extended, mean curl < 135° and mean reach < 1.48 | Hand_Close | min(0.94, 0.76 + max(0, 125 − mean curl)/100) |
| Anything else | Rest | 0.65 |

**Worked examples:** 4 extended fingers → 0.78 + 0.06 = **0.84**. A fist with mean curl 95° → 0.76 + 30/100 = 1.06, capped at **0.94**.

Where: `src/vision/hand_tracker.py`.

---

## 7. Smoothing, pointer and directions

### 7.1 Label smoothing (3 of 5 frames)

The last 5 raw labels are kept. A label becomes the stable label when it appears at least

```
needed = (5 × 3 + 4) // 5 = 3 times   (a 60% majority, rounded up)
```

Its confidence is the mean confidence of those frames. The full-fist flag is smoothed the same way.

### 7.2 Pointer (aiming)

The aim point is halfway between the middle finger's PIP (L10) and DIP (L11) joints, smoothed with an exponential moving average:

```
pointer_new = α × point + (1 − α) × pointer_old,   α = 0.35
```

A smaller α is steadier but slower. The palm centre is smoothed the same way.

### 7.3 Directions (Left, Right, Up, Down)

The palm centre is compared with an anchor point:

```
Δx = cx − anchor_x,   Δy = cy − anchor_y
a move happens when |Δx| ≥ 0.025 or |Δy| ≥ 0.04   (2.5% / 4% of the frame)
horizontal if |Δx| / 0.025 ≥ |Δy| / 0.04, else vertical
Right if Δx > 0, Left if Δx < 0;  Down if Δy > 0, Up if Δy < 0   (image y grows downwards)
```

Dividing by each threshold makes the two axes comparable. The direction is held for 350 ms, the next one cannot start for 280 ms (cooldown), the anchor moves to the new position, and a closed hand resets the anchor.

**Worked example:** Δx = 0.03, Δy = −0.02 → 0.03/0.025 = 1.2 vs 0.02/0.04 = 0.5, so horizontal; Δx > 0 → **Right**.

### 7.4 Reach gain (games)

At easier levels hand movement is amplified around the screen centre, so less reach is needed:

```
screen_x = (0.5 + (pointer_x − 0.5) × gain) × width
gain = 1.6 → 1.0 (Balloon Pop), 1.5 → 1.0 (Shape Matching), easiest → hardest
```

Example: hand at x = 0.8 with gain 1.6 → 0.5 + 0.3 × 1.6 = 0.98, almost at the right edge.

Where: `src/realtime/pipeline.py` (`_vision`), `src/games/balloon_pop.py`, `src/games/shape_matching.py`.

---

## 8. Fusion

Every 50 ms (20 times a second):

1. Take the latest camera label; if its confidence < 0.6, use **Rest**.
2. Add it to the last 5 labels and take the **most common** one (majority vote).
3. Attach the latest EMG window (RMS, MAV, all features) and the camera frame's time.
4. Put the command on the command bus (50 slots; when full, the oldest is dropped).

EMG never changes the label; it only adds effort information.

Where: `src/fusion/fusion_engine.py`, `src/realtime/pipeline.py` (`_fusion`).

---

## 9. Games: difficulty, levels, scoring and results

### 9.1 Difficulty interpolation

Difficulty runs from 1.0 (easiest) to 5.0 (hardest). Every game parameter is a straight-line blend between its easiest and hardest value:

```
t = (difficulty − 1) / (5 − 1)               (0 at easiest, 1 at hardest)
value = easy + (hard − easy) × t
```

### 9.2 Levels 1–7

```
difficulty(level) = 1 + (level − 1) × 4 / 6
```

| Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Difficulty | 1.00 | 1.67 | 2.33 | 3.00 | 3.67 | 4.33 | 5.00 |
| t | 0 | 0.17 | 0.33 | 0.50 | 0.67 | 0.83 | 1 |

**Worked example, Balloon Pop level 4 (t = 0.5):**

| Parameter | Easy → hard | Level 4 |
|---|---|---|
| New balloon every | 1700 → 800 ms | 1700 + (800 − 1700) × 0.5 = **1250 ms** |
| Rise speed | 1.2 → 2.8 | **2.0** |
| Radius | 54 → 38 px | **46 px** |
| Hit margin (pop allowed when hand-to-balloon distance ≤ radius + margin) | 30 → 12 px | **21 px** |
| Reach gain | 1.6 → 1.0 | **1.3** |
| Effort needed | 25 → 60% | **42.5%** |

Other games use the same formula:

| Game | Parameter | Easiest → hardest |
|---|---|---|
| Car Driving | lane-zone half-width | 0.10 → 0.19 of the view |
| Car Driving | top speed | 3.5 → 7.5 |
| Car Driving | traffic every | 2300 → 1000 ms |
| Treasure Hunt | joystick radius | 0.08 → 0.16 of the view |
| Treasure Hunt | chests / obstacles | 2 → 5 / 6 → 16 (rounded) |
| Shape Matching | shapes per round | 3 → 6 (rounded) |
| Shape Matching | snap distance | 80 → 42 px |
| Shape Matching | grab radius | size + 42 → size + 22 px |

**Level goals** (Balloon Pop): 6, 8, 10, 12, 14, 16, 18 balloons; other games in `src/games/levels.py`.

**Unlocking:** level n opens on (date level n − 1 was first passed) + `level_days_between` days (default 1). Level 1 is always open.

### 9.3 Adaptive difficulty (free play, auto mode)

```
keep the last 6 attempts; act only after at least 4 attempts since the last change
success rate = correct / attempts kept
rate ≥ 0.8 → difficulty + 0.5      rate ≤ 0.4 → difficulty − 0.5      otherwise unchanged
always kept within 1.0–5.0; presets: easy 1.5, medium 3.0, hard 4.5
```

Example: 5 of the last 6 correct → 0.83 ≥ 0.8 → raise from 3.0 to **3.5**. The level reached is saved per patient and game.

### 9.4 Scoring

```
correct movement:   +10, plus +5 while the streak is 3 or more
wrong movement:     streak resets to 0
```

| Game bonus | Points |
|---|---|
| Golden balloon (every 7th balloon, `spawned % 7 == 0`) | +20 |
| Car: star caught | +15 |
| Car: crash | −5 (score never below 0) |
| Treasure: chest / island cleared | +25 / +50 |
| Shape: round complete | +20 |

Example: five correct in a row → 10 + 10 + 15 + 15 + 15 = **65 points**.

### 9.5 Session results

```
accuracy       = correct attempts / all attempts
best streak    = longest run of consecutive correct attempts
reaction time  = time the attempt happened − time the target was shown   (ms)
avg reaction   = mean reaction time of correct attempts
stars          = 3 if accuracy ≥ 80%, 2 if ≥ 50%, 1 otherwise (0 with no attempts)
strong grips   = grip attempts with effort % ≥ needed %
```

Example: 9 correct of 12 → 75% → **2 stars**.

Where: `src/games/difficulty.py`, `src/games/levels.py`, `src/games/summary.py`, `src/games/game_engine.py`, and each game file.

---

## 10. Backend and dashboard statistics

| Statistic | Calculation | Shown in |
|---|---|---|
| Session accuracy | correct / attempts (SQL: `AVG(correct)`) | Sessions, Patients |
| Average accuracy | mean of session accuracies | Dashboard, Patients |
| Therapy time | Σ session durations / 60 (minutes) | Dashboard |
| Average reaction | mean reaction time of all attempts | Dashboard |
| Accuracy by movement | `AVG(correct)` per target movement | Dashboard, Patient detail |
| Daily accuracy | mean session accuracy per day, last 30 days | "Accuracy over time" chart |
| EMG by movement | mean RMS and MAV per camera label (zeros ignored) | Patient detail |
| Trend | mean of the last 3 session accuracies − mean of the 3 before | trend arrow |

**Needs attention** (first rule that applies):

1. No sessions yet.
2. Trend ≤ −0.10 (accuracy down 10 points or more over the last 3 sessions).
3. No session for 7 or more days.
4. At least 3 sessions and average accuracy below 50%.

Example: last three sessions 60%, 55%, 50% (mean 55%), previous three 70%, 65%, 68% (mean 67.7%) → trend = −12.7 points → flagged.

Where: `backend/app.py`, `backend/webapi.py`, `webapp/src/pages/Dashboard.tsx`.

---

## 11. Web app: EMG Datasets page

- **Features** for a whole file: RMS, MAV, VAR, STD and PEAK as in [section 4](#4-emg-features), but **WL is divided by the number of samples** (WL per sample), so files of different lengths compare fairly.
- **Windowed RMS envelope:** RMS of each window (default 200 samples), thinned to at most 600 points for the chart.
- **Peak-preserving downsampling** for the signal plot: the file is split into equal buckets and each bucket keeps its largest-magnitude sample, so spikes stay visible (5,317 samples shown as 1,200 points).
- **Compare groups:** mean RMS and MAV per movement for healthy and patient data, optionally relative to Rest (%).

Where: `backend/webapi.py` (`_decimate`, `_windowed_rms`, the features endpoint), `webapp/src/pages/Datasets.tsx`.

---

## 12. Offline machine learning

Research only; the games never use these models.

### 12.1 Segmenting the recordings

A file is split into segments wherever the time between rows is over 1,000 ms or goes backwards, so no window spans two recordings. Each segment is one trial.

### 12.2 Classical models (LDA, SVM, random forest)

1. 200 ms windows (20 samples) every 100 ms → the 8 features of [section 4](#4-emg-features).
2. **Standardisation** inside each model: z = (x − mean) / std, using the training data only.
3. Optional per-subject normalisation: each feature z-scored using that person's own mean and spread.

| Model | Settings | How it decides |
|---|---|---|
| LDA | default | linear boundaries, assuming each class is Gaussian with a shared covariance |
| SVM | RBF kernel, C = 10 | curved boundaries; kernel K(a, b) = exp(−γ‖a − b‖²); C trades margin width against training errors |
| Random forest | 200 trees | each tree votes; the majority wins |

The same three models are also trained on the 8 features of 5.12 s windows and on MOMENT-1 embeddings.

### 12.3 MOMENT-1 preprocessing

| Step | Calculation | Why |
|---|---|---|
| Resample | linear interpolation onto an exact 10 ms grid; filled samples are flagged | lost samples (mainly S01) |
| Log | z = log(1 + adc) | the envelope is mostly zeros with rare large values (0–4095); log puts Rest and Hand_Close on one scale |
| Calibrate | z = (z − subject mean) / subject std, using all of that person's samples | per-person calibration without labels; keeps activity differences between movements |
| Clip | z limited to −6…+6 | rare extremes cannot dominate |
| Window | 512 samples every 128 (75% overlap); shorter segments of at least 256 are left-padded with zeros and masked | MOMENT needs exactly 512 inputs |
| Exclude | a person with more than 25% interpolated samples (S01: 39%), and any window above 25% | do not train on invented signal |

Example: adc = 0 → log1p = 0; adc = 4095 → log1p = 8.32. If a subject's mean is 2.85 and std 2.0, then adc 4095 → (8.32 − 2.85)/2.0 = **2.74**.

**Why not MOMENT's own RevIN:** RevIN rescales every window to mean 0 and spread 1, which erases the activity level that separates Rest, Hand_Open and Hand_Close. It is kept only as a comparison (`--revin`).

**Class weights** (optional): weight = (all windows) / (number of classes × windows of that class); equal classes give 1.0.

### 12.4 MOMENT-1 models

| Method | Calculation | Trained parameters |
|---|---|---|
| Frozen embeddings | the encoder turns each window into a 512-number vector (mean over its patches); LDA/SVM/RF are trained on those vectors | only the classical model |
| Linear probe | encoder frozen; a linear head (logits = W·embedding + b) is trained | 3,591 (512 × 7 + 7) |
| LoRA | low-rank update on attention q and v: W' = W + (α / r)·B·A, rank r = 8, α = 16, dropout 0.1 | 118,279 (adapters + head) |

**Training:**

```
loss  = cross-entropy = −log( softmax(logits)[true class] ), optionally class-weighted
optimiser: AdamW, weight decay 1e-4, batch 32
linear probe: learning rate 1e-3, up to 15 epochs
LoRA:         learning rate 2e-4, up to 15 epochs
early stopping: stop after 4 epochs without better validation accuracy
prediction = argmax(logits);  random seed 42
```

The linear-probe check shows the arithmetic: 512 inputs × 7 classes + 7 biases = 3,591 parameters.

Where: `src/data/public_datasets.py`, `src/features/build_dataset.py`, `src/models/train_emg.py`, `src/data/prepare_finetune.py`, `src/models/finetune_moment.py`, `src/evaluation/compare_models.py`.

---

## 13. Evaluation metrics

### 13.1 Splits

| Split | Calculation |
|---|---|
| Leave-one-subject-out (LOSO) | 19 folds; in each, 1 person is tested, 1 more is MOMENT's validation person, 17 train. The reported score is the **mean over the 19 folds** |
| Holdout | train S02–S16, validate S17, test S18–S20 (the last three subjects) |
| Within-subject | first 70% of each trial's windows train, the rest test, skipping 2 windows at the boundary so overlapping windows never fall on both sides |

### 13.2 Metrics

```
accuracy  = correct predictions / all predictions
precision_c = TP_c / (TP_c + FP_c)      recall_c = TP_c / (TP_c + FN_c)
F1_c      = 2 × precision_c × recall_c / (precision_c + recall_c)
macro F1  = mean of F1_c over the 7 movements (each movement counts equally)
chance    = 1 / 7 = 14.3%   (7 balanced classes)
```

**Confusion matrix (row-normalised):** cell (i, j) = windows of true movement i predicted as j, divided by all windows of movement i. Each row sums to 1, and the diagonal is the per-movement recall. Example: the LoRA Up row has 0.37 on the diagonal, so 37% of Up windows were recognised.

**Group means:** S02–S09 and S10–S20 are averages of the per-volunteer LOSO accuracies (for example frozen MOMENT + RF: 47.9% and 89.6%).

**Patient score:** each LOSO fold model predicts both patients' windows; the reported value is the mean over the 19 models.

Where: `src/models/train_emg.py`, `src/models/finetune_moment.py`, `src/evaluation/compare_models.py`.

---

## 14. Reports: data quality, activity and latency

| Report | Calculation |
|---|---|
| Zero % | 100 × (samples equal to 0) / (all samples) |
| Saturation % | 100 × (samples ≥ 4095) / (all samples) |
| Recording span | (last timestamp − first timestamp) / 1000 s |
| Activity by movement | mean and standard deviation of RMS and MAV per cohort and movement |
| Relative to rest | each person's mean RMS per movement ÷ their own Rest RMS, shown on a log10 scale |
| Latency (per command) | time the game used the command − capture time of the camera frame |
| Latency summary | median, mean, 95th percentile, maximum, and % of commands under the 300 ms target, per game and mode |

Where: `src/evaluation/emg_activity_report.py`, `src/evaluation/latency_report.py`.

---

## 15. Quick reference

| Calculation | Formula | Where used |
|---|---|---|
| Samples per window | fs × window_ms / 1000 | all EMG processing |
| RMS | √(mean w²) | effort, features, web app |
| Effort % | (RMS − rest)/(strongest − rest) × 100 | grip gate, effort bar |
| Effort needed | 25 + 35 × t | auto grip threshold |
| Difficulty of level | 1 + (level − 1) × 4/6 | levels 1–7 |
| Game parameter | easy + (hard − easy) × t | all four games |
| Finger angle | arccos(a·b / (‖a‖‖b‖)) | gesture rules |
| Pointer smoothing | 0.35 × new + 0.65 × old | aiming |
| Stable label | 3 of the last 5 frames | camera labels |
| Fusion | confidence < 0.6 → Rest; majority of last 5 | every 50 ms |
| Score | +10, +5 on a streak of 3 or more | games |
| Accuracy | correct / attempts | results, dashboard |
| Stars | ≥ 80% = 3, ≥ 50% = 2, else 1 | results screen |
| Adaptive step | ≥ 80% → +0.5, ≤ 40% → −0.5 | free play |
| Trend | mean(last 3) − mean(previous 3) | attention flags |
| MOMENT input | clip((log1p(adc) − μ_subject)/σ_subject, ±6) | fine-tuning |
| LoRA update | W + (α/r)·B·A, r = 8, α = 16 | fine-tuning |
| Macro F1 | mean of per-class F1 | model comparison |
| Chance | 1/7 = 14.3% | all accuracy results |
