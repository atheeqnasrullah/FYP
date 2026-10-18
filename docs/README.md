# Stroke Rehabilitation System: documentation

Documentation for the Gamified Upper Limb Stroke Rehabilitation System (SLTC Final Year Project), checked against the code on branch `main` on 2026-10-18. Where older documents (`Stroke_Rehab_System_Documentation.pdf`, `EMG_Project_Documentation.md`, the root `architecture.md` and `implement.md`) disagree with this folder, this folder is correct; [corrections.md](corrections.md) lists every difference.

The system is a research prototype, not a certified medical device.

## Start here

| Document | Read it to |
|---|---|
| [overview.md](overview.md) | Understand the project, team, goals, scope and what is built vs planned |
| [architecture.md](architecture.md) | See how the parts fit: components, processes, threads, data contracts, database, repository, stack, design decisions |
| [user_guide.md](user_guide.md) | Install, configure, start and use the system |

## Parts of the system

| Document | Covers |
|---|---|
| [hardware.md](hardware.md) | MD0437 sensor, ESP32, electrodes, power, firmware, serial ports |
| [signal_processing_and_vision.md](signal_processing_and_vision.md) | EMG filtering, windows and features; MediaPipe gesture rules; fusion |
| [games.md](games.md) | The four games, scoring, session flow, adaptive difficulty |
| [web_app.md](web_app.md) | RehabHub pages, running and code layout |
| [api_reference.md](api_reference.md) | All 32 API endpoints and data models |
| [datasets.md](datasets.md) | The `Dataset/` folder: format, quality, activity per movement |

## Development, evaluation and research

| Document | Covers |
|---|---|
| [developer_guide.md](developer_guide.md) | Design rules, module map, adding games and endpoints, environment variables |
| [testing_and_evaluation.md](testing_and_evaluation.md) | The 47 tests, classifier and activity results, latency, evaluation still to do |
| [model_comparison.md](model_comparison.md) | Every model compared on the same splits: LDA, SVM, random forest, MOMENT before and after fine-tuning, with and without public data |
| [model_card_baseline.md](model_card_baseline.md) | The offline LDA/SVM/RF baseline |
| [fine_tuning_moment.md](fine_tuning_moment.md) | MOMENT-1 fine-tuning: preprocessing, environment, results, how to use the saved models |
| [known_issues.md](known_issues.md) | Open issues, issues fixed, and the prototype's limitations |
| [corrections.md](corrections.md) | Mistakes in the older project documents |
| [glossary.md](glossary.md) | Terms used across the documents |

## Research governance

| Document | Covers |
|---|---|
| [data_collection_protocol.md](data_collection_protocol.md) | How to record participants |
| [ethics_checklist.md](ethics_checklist.md) | Ethics and safety checks before and during recording |

## Status at a glance (2026-10-18)

- **Working:** webcam control of four games, adaptive difficulty, session storage, RehabHub web app, Streamlit dashboard, offline session queue, EMG replay from `Dataset/`. All 47 tests pass.
- **Results:** best offline EMG classifier (SVM) 36.7% leave-one-subject-out on 7 movements (chance 14.3%).
- **Models:** best EMG classifier is frozen MOMENT-1 features + random forest, 48.1% leave-one-subject-out on 7 movements (chance 14.3%); fine-tuned MOMENT 43.2% (44.4% when pre-trained on public UCI data). Public data gave no reliable gain ([model_comparison.md](model_comparison.md)). Fine-tuned models in `models/moment/`.
- **Not built:** login, patient-therapist communication, wireless EMG, battery pack.
- **Not measured:** latency, webcam gesture accuracy, usability.
