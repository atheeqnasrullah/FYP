# Gamified Upper Limb Stroke Rehabilitation System with Communication Features

## Project Overview

This system is designed to help stroke patients rehabilitate their upper limb through gamified exercises. The system has two main components — a hardware system and a software system.

---

## 1. Hardware System

### Components Used
- **EMG Sensor (MD0437)** — reads muscle electrical signals from the forearm
- **ESP32 Microcontroller (30-pin Type-C)** — processes and transmits the signal
- **3 Electrodes** — Yellow (reference), Green and Red (muscle signal)
- **Power Supply** — +9V and -9V for EMG sensor

### How It Works
```
3 electrodes placed on forearm
        ↓
EMG sensor reads analog muscle signal
        ↓
ESP32 converts analog to digital (ADC)
        ↓
Digital signal sent to laptop via WiFi
```

### Electrode Placement

| Color | Role | Placement |
|---|---|---|
| Yellow | Reference | Elbow bone area |
| Green | Signal + | Upper forearm muscle |
| Red | Signal - | Lower forearm muscle (3-4cm below green) |

---

## 2. Software System

### 2.1 Visual Detection (MediaPipe)
The laptop camera detects hand position in real time:

```
Hand open       → RELAX detected  (fingers extended, no muscle effort)
Hand closed     → FLEX detected   (fist closed, muscle contracting)
Wrist right     → RIGHT detected
Wrist left      → LEFT detected
Wrist up        → UP detected
Wrist down      → DOWN detected
```

### 2.2 Signal + Visual Combined

```
Hardware system  →  muscle STRENGTH signal
Visual system    →  hand POSITION
        ↓
Both combined together
        ↓
Control the rehabilitation games
```

---

## 3. Games

### Game 1 — Balloon Pop

```
Goal: Pop balloons on screen

How to play:
→ Close fist with enough strength → balloon pops
→ Both hand position AND strength must be correct
→ Only correct strength at correct position pops the balloon

Levels:
Level 1 → Low strength required, short time
Level 2 → Medium strength required, medium time
Level 3 → High strength required, longer time

Reward given after completing each level
```

### Game 2 — Car Control

```
Goal: Control a car moving on a straight road

How to play:
→ Close fist        → car brakes (stops)
→ Wrist right       → car moves right
→ Wrist left        → car moves left

Levels:
Level 1 → Slow car, simple road
Level 2 → Faster car, more obstacles
Level 3 → Fast car, complex road

Reward given after completing each level
```

### Game 3 — Shape Placement

```
Goal: Place shapes in correct positions on screen

How to play:
→ Use hand movements to drag and place shapes
→ Correct position = shape locks in place

Levels:
Level 1 → Simple shapes, large targets
Level 2 → More shapes, smaller targets
Level 3 → Complex shapes, precise placement needed

Reward given after completing each level
```

---

## 4. Data Collection and ML Model

### Data Types Needed

```
1. Healthy people data   →  normal strong signals
2. Patient data          →  weaker damaged muscle signals
```

### ML Model Purpose

```
Collect both datasets
        ↓
Train ML model
        ↓
Model learns to differentiate:
   → Is this signal from a healthy person?
   → Is this signal from a stroke patient?
        ↓
Use this to set correct game thresholds
for each individual patient automatically
```

---

## 5. Web Application

### Login System

```
Patient logs in
        ↓
System automatically collects raw data first:
→ Hand open  (RELAX)
→ Hand closed (FLEX)
→ Wrist right
→ Wrist left
→ Wrist up
→ Wrist down
        ↓
System calculates personal threshold value
        ↓
Threshold automatically applied to all games
        ↓
Different threshold levels set for each game level
```

### Three Main Options After Login

#### Option 1 — Games

```
Different games for different exercises
Patient selects game and plays
Each game has 3 difficulty levels
```

#### Option 2 — Communication

```
Patient and physiotherapist can communicate:
→ Voice messages
→ Text messages
Real time communication between patient and therapist
```

#### Option 3 — Dashboard (Physiotherapist Monitor)

```
Physiotherapist can monitor:
→ Which game the patient played
→ How long they played
→ How accurately they played
→ Patient improvement over time
→ Whether patient did their exercise today
→ Progress graphs and reports
```

---

## 6. Complete System Flow

```
Patient logs in to web application
        ↓
System collects raw EMG data from patient
        ↓
Personal threshold calculated automatically
        ↓
Patient selects exercise game
        ↓
Camera detects hand position (MediaPipe)
Hardware reads muscle strength (EMG sensor)
        ↓
Both signals combined → control the game
        ↓
Patient completes levels → receives rewards
        ↓
Physiotherapist monitors progress on dashboard
        ↓
Communication between patient and physiotherapist
```

---

## 7. Summary Table

| Component | Technology | Purpose |
|---|---|---|
| EMG Sensor MD0437 | Hardware | Read muscle signal |
| ESP32 30-pin | Hardware | Process and send signal |
| MediaPipe | Python/Camera | Detect hand position |
| LDA Classifier | Machine Learning | Classify gestures |
| Unity Games | Software | Rehabilitation exercises |
| Web Application | React.js + Node.js | Login, dashboard, communication |
| WiFi UDP | Communication | Wireless data transmission |
| TP4056 + MT3608 | Power | Rechargeable battery system |

---

## 8. Key Features

- ✅ Wearable EMG sensor — lightweight, no IMU
- ✅ Real time gesture detection
- ✅ 3 rehabilitation games with 3 levels each
- ✅ Automatic threshold calibration per patient
- ✅ ML model differentiates healthy vs patient signals
- ✅ Physiotherapist monitoring dashboard
- ✅ Patient-therapist communication (voice + text)
- ✅ Reward system for patient motivation
- ✅ Wireless operation — no cables to laptop
- ✅ Rechargeable battery system

---

## 9. Team Details

| | |
|---|---|
| **Project Title** | Gamified Upper Limb Stroke Rehabilitation System with Communication Features |
| **Institution** | Sri Lanka Technology Campus (SLTC) |
| **Supervisor** | Ms. Dulashi Pabasara |
| **Co-Supervisor** | Mr. Vihanga Herath |
| **Student 1** | M.N.M. Atheeq — 22ug2-0237 |
| **Student 2** | A.F.M. Imzaan — 22ug2-0072 |
| **Department** | Information and Communications Engineering |
