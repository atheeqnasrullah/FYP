# Web application (RehabHub)

RehabHub is the physiotherapist's single place to manage patients, launch games, review sessions and inspect EMG data. It talks only to the local API and has no login.

## Pages

| Page | What it shows and does |
|---|---|
| Dashboard | Patients, sessions, average accuracy and total therapy time; patients needing attention; accuracy over time; accuracy by movement; games played; recent sessions; an import button for sessions saved offline |
| Patients | Coded patient records with session count, average and recent accuracy, trend and last game; add and search |
| Patient detail | Clinical notes (age, affected side, stroke date, notes); progress over sessions; accuracy by movement; EMG activity by camera-detected movement; session history; CSV export; delete |
| Sessions | Every session, filterable by patient and game; click a session to see each attempt; delete a session |
| Game Launcher | Pick patient, game, input mode (webcam, webcam + EMG, keyboard, simulator), difficulty and length; start or stop the game; follow its live log |
| EMG Datasets | Browse CSV files, plot the signal, compute RMS, MAV, VAR, peak and waveform length, and compare healthy with patient data per movement |
| Settings | Light or dark theme, API address override, hardware summary, and an editor for `config/settings.yaml` that validates the YAML before saving |

The EMG Datasets page reads `Datasets/` and `data/raw/emg/` only, so the new `Dataset/` folder does not appear in it yet (see [known_issues.md](known_issues.md)).

## Running it

**Production (recommended):**

```bash
cd webapp && npm install && npm run build && cd ..
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ui. The built app calls the API on the same address, so any port works.

**Development:**

```bash
python -m uvicorn backend.app:app --reload --port 8000   # terminal 1
cd webapp && npm run dev                                  # terminal 2
```

Open http://localhost:5173. Vite forwards `/api` to port 8000 only (`webapp/vite.config.ts`), so the API must use port 8000 in this mode.

## Code

| Path | Role |
|---|---|
| `webapp/src/App.tsx` | Routes (hash router): `/`, `/patients`, `/patients/:pid`, `/sessions`, `/games`, `/datasets`, `/settings` |
| `webapp/src/api.ts` | Typed client for every endpoint; `/api` prefix in development, same origin in production |
| `webapp/src/types.ts` | Response types |
| `webapp/src/pages/` | One file per page |
| `webapp/src/components/` | Layout, charts, session modal, trend sparkline, UI primitives |
| `webapp/src/theme.tsx`, `index.css` | Light/dark theme and styles |
| `backend/webapi.py` | The endpoints this app adds to the API ([api_reference.md](api_reference.md)) |

Stack: React 19, TypeScript 5.8, Vite 6, React Router 6, Recharts 2; Node.js 18 or newer. There are no front-end tests yet.
