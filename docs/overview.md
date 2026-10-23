# Overview

The system turns hand movements seen by a webcam into controls for four rehabilitation games, measures forearm muscle activity with a single-channel EMG sensor, and records every session so a physiotherapist can follow progress in a web app. It is a Final Year Project research prototype that runs on one PC, and it is **not a certified medical device**.

## Project details

| Item | Detail |
|---|---|
| Project title | Gamified Upper Limb Stroke Rehabilitation System with Communication Features |
| Institution | Sri Lanka Technology Campus (SLTC), Department of Information and Communications Engineering |
| Supervisor | Ms. Dulashi Pabasara |
| Co-supervisor | Mr. Vihanga Herath |
| Students | M.N.M. Atheeq (22ug2-0237), A.F.M. Imzaan (22ug2-0072) |
| Repository | github.com/atheeqnasrullah/FYP, branch `main` |

## Goals

| Goal | How the system meets it |
|---|---|
| G1 Detect movement | MediaPipe hand landmarks give 7 labels: Rest, Hand_Open, Hand_Close, Left, Right, Up, Down |
| G2 Measure muscle activity | The MD0437 EMG envelope gives RMS, MAV and six more features per 200 ms window |
| G3 Engage the patient | Four Pygame games with start screens, a timer, rewards and adaptive difficulty |
| G4 Monitor progress | Sessions go to a local FastAPI + SQLite service and appear in the RehabHub web app |
| G5 Stay testable without hardware | Keyboard, simulator and EMG replay inputs; 57 automated tests |

**In scope:** single-channel EMG acquisition, webcam movement detection, four PC games, adaptive difficulty, local API and database, web app and Streamlit dashboard, offline EMG analysis and classifier research, healthy-volunteer data.

**Out of scope:** clinical trials with stroke patients, mobile app, cloud hosting, user accounts, medical certification. The camera, not an EMG classifier, decides game movements.

## Implementation status

The core loop (camera control, four games, session records, monitoring) is built. Login, therapist messaging, wireless EMG and automatic per-patient EMG thresholds from the original concept (`EMG_Project_Documentation.md`) are not.

| Concept feature | Status | What exists now |
|---|---|---|
| MD0437 EMG sensor + ESP32 acquisition | Built | 1 kHz firmware, USB serial at 921600 baud, live feature extraction |
| Webcam hand detection (open, close, left, right, up, down) | Built | MediaPipe landmarks, gesture rules and palm-motion directions |
| EMG strength + camera position combined to control games | Built (changed) | The camera decides every action; in Webcam + EMG mode a grip action (pop, brake, grab, pick up) also needs a per-patient effort threshold from a relax-then-squeeze check. EMG never chooses the movement |
| Balloon Pop | Built | Aim with the hand, full fist pops; golden bonus balloons |
| Car game | Built | Hand position picks one of three lanes; fist brakes; catch stars, avoid traffic |
| Shape placement | Built | Wooden shape sorter: fist to grab, open hand to drop in the matching hole |
| Treasure Hunt (not in the concept) | Built | Island grid walked with a hand joystick; open then close at each chest |
| Games built in Unity | Changed | Built in Python with Pygame, launched from the web app |
| Three difficulty levels per game | Built | Continuous levels 1.0-5.0, easy/medium/hard presets and an automatic mode |
| Rewards | Built | Points, streak bonus, star rating, previous best, level-up messages |
| Web app in React.js + Node.js | Changed | React 19 + TypeScript front end (RehabHub); the back end is Python FastAPI, not Node.js |
| Physiotherapist monitoring dashboard | Partial | Overview, patient progress, sessions and CSV export; no daily-exercise reminders or report generation |
| ML gesture classifier (LDA) | Partial | Offline LDA/SVM/RF research only; never used in the games |
| Automatic per-patient threshold before playing | Changed | Replaced by adaptive difficulty from the patient's accuracy, remembered per patient and game |
| ML model separating healthy from patient signals | Partial | Web app compares healthy vs patient RMS/MAV per movement; no trained classifier |
| Patient login | Not built | No accounts or authentication; coded patient IDs only |
| Patient-therapist voice and text communication | Not built | Not started |
| Wireless link (WiFi UDP) | Not built | USB serial only |
| Rechargeable battery pack (TP4056 + MT3608) | Not built | No schematic or firmware for it in the repository |

The project title promises "communication features"; patient-therapist messaging is the largest gap between the title and the build.
