# Glossary

| Term | Meaning |
|---|---|
| ADC | Analog-to-digital converter. The ESP32's 12-bit ADC turns the sensor voltage into 0-4095 |
| Attempt | One scored action in a game: target movement, detected movement, correct or not, reaction time, EMG values |
| Auto difficulty | Mode that raises the level by 0.5 at 80%+ accuracy and lowers it at 40% or less, over the last 6 attempts |
| Command bus | Queue (50 slots) carrying fused commands from the fusion thread to the game |
| EMG | Electromyography: electrical activity of muscles, measured on the skin |
| Envelope | A smoothed, rectified EMG signal showing activity level; the MD0437 outputs this instead of raw EMG |
| Fusion | Combining the camera label with the latest EMG features into one command every 50 ms |
| Landmarks | The 21 hand points MediaPipe finds in each camera frame |
| LDA, SVM, RF | Linear discriminant analysis, support vector machine, random forest: classic classifiers used for the offline baseline |
| LoRA | Low-rank adaptation: training small extra matrices instead of the whole model during fine-tuning |
| LOSO | Leave-one-subject-out: train on all people but one, test on that one, repeat for everyone |
| MAV | Mean absolute value of a window: an activity measure |
| MediaPipe | Google's library for hand tracking from camera images |
| MOMENT-1 | Open time-series foundation model (MIT licence) chosen for the fine-tuning stage |
| Pending session | A session saved to `data/logs/pending_sessions.jsonl` because the API was down |
| RehabHub | The React web app for physiotherapists |
| Replay | Feeding a recorded EMG file into the live pipeline instead of the ESP32 |
| RMS | Root mean square of a window: the main activity measure shown in the games |
| Runtime labels | The movement names the games use: Rest, Hand_Open, Hand_Close, Left, Right, Up, Down |
| SUS | System Usability Scale: a 10-question usability questionnaire scored 0-100 |
| Window | A short slice of signal (200 ms, every 100 ms) from which features are computed |
