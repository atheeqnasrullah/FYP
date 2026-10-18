# plan.md

> **Outdated (kept for reference).** This document describes an earlier plan. The current, checked documentation is in [docs/README.md](docs/README.md); [docs/corrections.md](docs/corrections.md) lists where this file differs from the built system.

# Project Plan: Gamified Upper-Limb Stroke Rehabilitation System

Companion documents: `architecture.md` (design) and `implement.md` (build steps).

---

## 1. Project Summary

| Item | Detail |
|---|---|
| Title | A Gamified Upper Limb Stroke Rehabilitation System with Remote Monitoring and Communication Features |
| Type | Final Year Project (hardware + AI/ML + software) |
| Duration | 16 weeks (adjust to your semester) |
| Deliverables | Working prototype, synchronized EMG/vision datasets, EMG activity features, 4 games, dashboard, report, presentation/viva |

## 2. Objectives

1. Acquire timestamp-aligned EMG samples and webcam-derived movement labels.
2. Extract EMG activity features such as RMS, MAV, variance, peak and waveform length.
3. Use computer vision to identify hand gestures and movement direction; combine its labels with EMG activity measurements for game feedback.
4. Build rehabilitation games (Balloon Pop, Car Driving, Treasure Hunt, Shape Matching).
5. Log sessions and show progress to a clinician through a dashboard.
6. Evaluate accuracy, latency and usability.

## 3. Scope

**In scope:** single-channel MD0437 acquisition, webcam movement detection, synchronized data fusion, EMG feature analysis, 4 PC games, local backend, dashboard, healthy-subject data collection. Offline EMG classifiers may be compared for research, but do not control games.

**Out of scope (future work):** clinical trials on stroke patients, mobile app, multi-channel armband, cloud hosting, medical certification.

## 4. Team Roles (adjust to team size)

| Role | Owner | Responsibilities |
|---|---|---|
| A: Hardware & Signals | | ESP32, EMG circuit, firmware, filtering, data logger |
| B: ML | | Features, training, evaluation, calibration |
| C: Vision & Fusion | | MediaPipe tracker, gesture logic, fusion engine |
| D: Games & Monitoring | | Game engine, 4 games, backend, dashboard |
| All | | Testing, documentation, report sections |

> For a solo project, follow the phase order and merge roles A+B, C+D.

## 5. Timeline (16 weeks)

| Week | Phase | Tasks | Milestone |
|---|---|---|---|
| 1 | Planning | Finalise requirements, literature review, repo setup, ethics application | **M0:** Proposal and repo ready |
| 2 | Hardware | Wire ESP32 + EMG, write firmware, view live signal | **M1:** Clean EMG signal on PC |
| 3 | Acquisition | EMG logger, landmark recorder, data collection protocol, pilot recording | **M2:** Pilot dataset |
| 4-5 | Data collection | Record coded sessions with timestamp-aligned camera labels and EMG samples | **M3:** Synchronized dataset |
| 6 | Preprocessing | Filters, windowing, feature extraction, dataset QA | **M4:** `emg_features.csv` |
| 7-8 | Feature analysis | Build RMS/MAV and related window features; compare activity across camera labels and sessions | **M5:** EMG activity analysis |
| 8-9 | Vision | Hand tracker, derived features, gesture classifier | **M6:** Vision model/rules working |
| 10 | Fusion | Camera-label smoothing, time-aligned EMG feature transport, simulator | **M7:** Live fused command and feedback |
| 10-12 | Games | Base engine, then Balloon Pop → Car Driving → Treasure Hunt → Shape Matching | **M8:** playable games |
| 12-13 | Backend & dashboard | API, DB, session logging, dashboard | **M9:** End-to-end monitoring |
| 14 | Integration | Full system test, latency check, bug fixing, calibration | **M10:** Working prototype |
| 15 | Evaluation | User testing, SUS survey, final results and figures | **M11:** Results ready |
| 16 | Documentation | Report, slides, demo video, viva preparation | **M12:** Final submission |

Games (Weeks 10-12) can start earlier using the keyboard/simulator input, so they are **not blocked** by the ML work.

## 6. Work Breakdown by Phase

### Phase 1: Planning
- [x] Define camera-derived movement labels and the EMG activity-measurement role
- [ ] Literature review (EMG gesture recognition, stroke rehab games, MediaPipe)
- [ ] Submit ethics approval request and prepare consent form
- [x] Create GitHub repo and folder structure

### Phase 2: Hardware
- [ ] Build EMG front end and ESP32 wiring
- [x] Firmware: 1000 Hz sampling, serial output
- [ ] Verify signal: rest is flat, contraction increases amplitude
- [ ] Document electrode placement with photos

### Phase 3: Data Collection
- [ ] Record timestamp-aligned EMG samples and live webcam-derived movement labels
- [ ] Repeat comfortable movements with rest periods and allow breaks
- [ ] Check serial samples, camera label counts, signal range and session metadata

### Phase 4: Processing and Features
- [x] Preserve the MD0437 envelope path without raw-EMG bandpass/notch filtering
- [x] Build 200 ms windows with 100 ms step
- [x] Extract RMS, MAV and other activity features
- [x] Compare EMG activity across camera-derived labels and sessions

### Phase 5: Machine Learning
- [x] Optional offline comparison of EMG features against camera-derived movement labels
- [x] Keep any EMG classifier out of runtime game control
- [x] Report activity-feature and camera-label performance separately (EMG done in `docs/testing_and_evaluation.md`; camera-label accuracy needs annotated sessions)

### Phase 6: Vision
- [x] Real-time hand tracking with MediaPipe
- [x] Rules or ML for Open/Close/Left/Right
- [ ] Palm-facing and wrist-angle features for rotation and wrist
- [ ] Record landmark dataset, validate accuracy

### Phase 7: Fusion and Real-Time
- [x] Implement fusion rules and smoothing
- [x] Real-time loop with threads
- [x] Simulator and keyboard fallback
- [ ] Measure latency (instrumented: play in webcam mode, then `python -m src.evaluation.latency_report`)

### Phase 8: Games
- [x] BaseGame (input, scoring, timer, target scheduler, logging)
- [x] Balloon Pop
- [x] Car Driving (camera steering/brake, optional EMG activity monitor)
- [x] Treasure Hunt
- [x] Shape Matching
- [ ] Difficulty levels and patient feedback visuals

### Phase 9: Monitoring
- [x] FastAPI backend and SQLite database
- [x] Session upload from games
- [x] Streamlit clinician dashboard

### Phase 10: Testing, Evaluation and Documentation
- [x] Unit tests, integration tests, end-to-end run (28 pytest tests; live webcam run still manual)
- [ ] User testing with 5+ volunteers, SUS questionnaire
- [ ] Final figures and tables (EMG figures/tables in `results/`; latency, vision and SUS pending)
- [ ] Report, slides, demo video

## 7. Data Collection Plan

| Item | Plan |
|---|---|
| Subjects | 5-10 healthy volunteers (more is better) |
| Camera labels | Hand_Open, Hand_Close, Left, Right, Up, Down, Rest; No_Hand when the hand is not visible |
| Recording | Continuous timestamp-aligned EMG and camera labels, e.g. 120 seconds per session |
| Movement periods | Comfortable repetitions with relaxed periods between them; camera labels each sample |
| Sessions | 2 sessions on different days |
| EMG features | RMS, MAV and related windowed activity measures |
| Per-subject time | Choose duration to suit the approved protocol and participant comfort |

**Checklist per subject:** consent signed → skin cleaned → electrodes placed → signal check → record → backup file → note any issues.

## 8. Evaluation Plan

| Area | Method | Target |
|---|---|---|
| EMG activity | Compare RMS/MAV and related features across camera labels and sessions | Report signal range, variability and missing samples; do not call it strength |
| Vision movement labels | Independently annotate a sample of Open/Close/Left/Right/Up/Down movements | Report per-label precision/recall and confusion |
| Fusion | End-to-end test that camera commands carry concurrent EMG features | Movement comes from vision; activity feedback comes from EMG |
| Latency | Camera label timestamp vs. game response | < 300 ms |
| Usability | SUS questionnaire, task completion | SUS > 68 |
| Rehab tracking | Score and accuracy across sessions | Trend visible on dashboard |

Treat the targets as goals. Report honest results even if they fall short, and explain why.

## 9. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Single EMG channel can't separate all classes | High | High | Add 2nd channel; assign classes by sensor; merge hard classes |
| R2 | Noisy EMG (50 Hz, motion) | Medium | High | Notch filter, battery power, skin prep, shielding |
| R3 | Ethics approval delay | Medium | High | Apply in Week 1; use team members first |
| R4 | Poor cross-subject generalisation | High | Medium | Per-user calibration, more subjects |
| R5 | Vision fails in poor lighting | Medium | Medium | Lighting guidelines, confidence threshold |
| R6 | Latency too high | Medium | Medium | Smaller windows, threads, lighter model |
| R7 | Hardware failure or lost parts | Low | High | Spare sensor and ESP32, backups |
| R8 | Integration issues late | High | High | Simulator, weekly integration builds |
| R9 | Time overrun | Medium | High | Prioritise (see MVP below), weekly review |

## 10. Minimum Viable Product (MVP) vs. Stretch Goals

**MVP (must finish):**
- Webcam-based movement control with timestamped EMG RMS/MAV feedback
- Balloon Pop fully working
- Session logging and a basic dashboard
- Honest evaluation and report

**Target:**
- Available hand gestures and Left/Right/Up/Down camera movement labels
- All 4 games
- Calibration step, difficulty levels

**Stretch:**
- 2-channel EMG, wireless link, adaptive difficulty, patient trial

If time runs short, cut from the bottom up.

## 11. Ethics and Safety Checklist

- [ ] Ethics approval before recording anyone
- [ ] Written informed consent
- [ ] Coded IDs only, no names, no stored face video
- [ ] Battery-powered EMG device, never mains-connected while on a person
- [ ] Clean skin, single-use electrodes, stop if irritation occurs
- [ ] Data stored securely with limited access
- [ ] Clear statement that the prototype is **not a certified medical device**

## 12. Communication and Management

| Practice | Detail |
|---|---|
| Weekly meeting | Review progress, blockers, next tasks |
| Supervisor update | Fortnightly with demo |
| Tracking | GitHub Projects or Trello board |
| Version control | `main` stable, feature branches, pull-request review |
| Logbook | Weekly entry: done, failed, decisions (feeds methodology chapter) |

## 13. Report Outline

1. Introduction and problem statement
2. Literature review
3. System design (from `architecture.md`)
4. Methodology: data collection, processing, ML, fusion
5. Implementation: hardware, software, games, dashboard
6. Results and discussion
7. Limitations and future work
8. Conclusion
9. References and appendices (code, consent form, protocol)

### Phase 11: Foundation-model fine-tuning (final stage, needs approval)
- [x] Select the model: MOMENT-1 (MIT licence, single-channel classification), see `docs/fine_tuning_moment.md`
- [x] Prepare `src/models/finetune_moment.py` on the same subject splits as the baseline
- [ ] Owner approval, then install `requirements-finetune.txt` and run holdout + LOSO
- [ ] Compare with the LDA/SVM/RF baseline in the results chapter

## 14. Definition of Done

The project is complete when:
- The live system detects movements and controls all (MVP: at least one) games
- Session data appears on the dashboard
- Results are documented with figures and a confusion matrix
- Code is committed with a README that lets someone else run it
- Report, slides and demo video are submitted
