# Glossary

| Term | Meaning |
|---|---|
| ADC | Analog-to-digital converter. The ESP32's 12-bit ADC turns the sensor voltage into 0-4095 |
| Attempt | One scored action in a game: target movement, detected movement, correct or not, reaction time, EMG values |
| Auto difficulty | Free-play mode that raises the difficulty by 0.5 at 80%+ accuracy and lowers it at 40% or less, over the last 6 attempts |
| Command bus | Queue (50 slots) carrying fused commands from the fusion thread to the game |
| EMG | Electromyography: electrical activity of muscles, measured on the skin |
| Effort threshold | In Webcam + EMG mode, the share of the patient's strongest squeeze a grip must reach before a pop, brake, grab or pick-up counts (`game_effort_required`, auto 25-60%) |
| Envelope | A smoothed, rectified EMG signal showing activity level; the MD0437 outputs this instead of raw EMG |
| Fusion | Combining the camera label with the latest EMG features into one command every 50 ms |
| Landmarks | The 21 hand points MediaPipe finds in each camera frame |
| LDA, SVM, RF | Linear discriminant analysis, support vector machine, random forest: classic classifiers used for the offline baseline |
| LoRA | Low-rank adaptation: training small extra matrices instead of the whole model during fine-tuning |
| LOSO | Leave-one-subject-out: train on all people but one, test on that one, repeat for everyone |
| Game level | One of seven stages of a game (1 Warm-up to 7 Champion), each with a fixed difficulty and a goal; the next opens a day after a pass |
| Grip effort | EMG RMS as a percentage of the patient's range from rest to strongest squeeze, measured by the muscle check |
| MAV | Mean absolute value of a window: an activity measure |
| MediaPipe | Google's library for hand tracking from camera images |
| Muscle check | Calibration at the start of a Webcam + EMG session: relax 3 s (rest RMS), squeeze 3 s (strongest RMS); saved per patient |
| MOMENT-1 | Open time-series foundation model (MIT licence) chosen for the fine-tuning stage |
| Pending session | A session saved to `data/logs/pending_sessions.jsonl` because the API was down |
| RehabHub | The React web app for physiotherapists |
| Replay | Feeding a recorded EMG file into the live pipeline instead of the ESP32 |
| RMS | Root mean square of a window: the main activity measure shown in the games |
| Runtime labels | The movement names the games use: Rest, Hand_Open, Hand_Close, Left, Right, Up, Down |
| SUS | System Usability Scale: a 10-question usability questionnaire scored 0-100 |
| Window | A short slice of signal (200 ms, every 100 ms) from which features are computed |
