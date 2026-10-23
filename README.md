# Gamified Upper-Limb Stroke Rehabilitation System

A Final Year Project (Sri Lanka Technology Campus) research prototype: a webcam turns hand movements into controls for four rehabilitation games, a single-channel EMG sensor (MD0437 + ESP32) measures forearm muscle activity, and every session is stored by a local API and shown to the physiotherapist in a web app (RehabHub).

> **Not a certified medical device.** Use coded participant IDs, obtain ethics approval and informed consent before recording anyone, and never attach mains-powered equipment to a person.

**Full documentation: [docs/README.md](docs/README.md)**: overview and implementation status, architecture, user and developer guides, API, datasets, model comparison, fine-tuning, known issues and corrections to older documents.

## Quick start

Requirements: Python 3.11, Node.js 18+, a webcam (optional: ESP32 + MD0437).

```bash
# 1. Install
uv venv --python 3.11 .venv && source .venv/bin/activate        # or: py -3.11 -m venv .venv
uv pip install -r requirements.txt -r requirements-dev.txt       # or: pip install ...
cd webapp && npm install && npm run build && cd ..

# 2. Run the API (it also serves the web app)
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000/ui  -> add a patient -> Game Launcher

# 3. Or start a game directly
python main.py keyboard --game balloon          # no hardware
python main.py vision --game car                # webcam
python main.py live --game shape                # webcam + EMG sensor
python main.py live --emg-source replay --game treasure   # webcam + recorded EMG
```

If port 8000 is taken, use another port and set `backend_url` in `config/settings.yaml` to match. Details: [docs/user_guide.md](docs/user_guide.md).

## What is in the system

| Part | Summary | Docs |
|---|---|---|
| Games | Balloon Pop, Car Driving, Treasure Hunt, Shape Matching; start screen, timer, rewards, adaptive difficulty (levels 1-5, remembered per patient) | [games.md](docs/games.md) |
| Vision | MediaPipe hand landmarks: Rest, Hand_Open, Hand_Close, Left, Right, Up, Down; the camera decides every game action | [signal_processing_and_vision.md](docs/signal_processing_and_vision.md) |
| EMG | MD0437 envelope at 1 kHz over USB serial; RMS/MAV activity shown and logged (not strength) | [hardware.md](docs/hardware.md) |
| Web app (RehabHub) | Dashboard, patients, sessions, game launcher, EMG dataset explorer, settings | [web_app.md](docs/web_app.md) |
| API | FastAPI + SQLite, 33 endpoints, local only (no authentication) | [api_reference.md](docs/api_reference.md) |
| Data | `Dataset/`: 9 healthy volunteers and 1 stroke patient, 7 movements, 100 Hz | [datasets.md](docs/datasets.md) |
| EMG classifiers (offline research) | LDA, SVM, random forest and MOMENT-1 (fine-tuned models in `models/moment/`) | [model_comparison.md](docs/model_comparison.md) |

## Key results (offline, 8 healthy volunteers, 7 movements, chance 14.3%)

| Method | Leave-one-subject-out accuracy |
|---|---|
| Frozen MOMENT-1 features + random forest | **48.1%** |
| SVM on 5.12 s window features | 47.3% |
| MOMENT-1-small fine-tuned (LoRA) | 45.9% (48.7% on the S07-S09 holdout) |
| SVM on 200 ms window features | 37.2% |

Rest, Hand_Open and Hand_Close are recognised well from EMG; Left, Right, Up and Down are near chance with one forearm channel, so the camera keeps control of movement. Public data (UCI, 36 people; EMG-EPN-612, 612 people) did not improve accuracy on our volunteers. See [docs/model_comparison.md](docs/model_comparison.md).

## Repository map

```text
main.py            game entry point              backend/    FastAPI (app.py, webapi.py)
src/               acquisition, preprocessing,   webapp/     RehabHub (React + TypeScript)
                   features, data, models,       dashboard/  Streamlit dashboard (older)
                   evaluation, vision, fusion,   firmware/   ESP32 sketch
                   realtime, games, utils        config/     settings.yaml, labels.yaml
Dataset/           EMG recordings                models/     fine-tuned MOMENT-1 runs
docs/              documentation                 tests/      62 pytest tests
```

`python -m pytest -q` runs the tests. Fine-tuning uses a separate environment (`.venv-finetune`, see [docs/fine_tuning_moment.md](docs/fine_tuning_moment.md)).

## Older documents

`Stroke_Rehab_System_Documentation.pdf`, `EMG_Project_Documentation.md` (original concept), `architecture.md`, `implement.md` and `plan.md` describe earlier plans. Where they differ from `docs/`, `docs/` is correct; [docs/corrections.md](docs/corrections.md) lists every difference.

## Credits

Public data: UCI "EMG Data for Gestures" (Lobov et al., *Sensors* 2018) and EMG-EPN-612 (Escuela Politécnica Nacional, Zenodo 10.5281/zenodo.4421500), both CC BY 4.0. Base model: [AutonLab/MOMENT-1-small](https://huggingface.co/AutonLab/MOMENT-1-small), MIT licence. Team: M.N.M. Atheeq, A.F.M. Imzaan; supervisors Ms. Dulashi Pabasara and Mr. Vihanga Herath.
