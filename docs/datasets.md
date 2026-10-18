# Datasets

`Dataset/` (added 2026-10-16) holds MD0437 envelope recordings from 9 healthy volunteers and one synthetic stroke patient, already labelled with the same 7 movements the games use. It replaces the older `Datasets/` folder (11 volunteers in wide format, 3 synthetic patients), which was deleted the same day.

## Contents

| Group | Folder | Subjects | Files | Samples | Notes |
|---|---|---|---|---|---|
| Healthy volunteers | `Dataset/Healthy_person/S01`-`S09` | 9 | 61 | 369,435 | One file per movement; S01 has no Rest file, S04 has no Down file |
| Synthetic stroke patient | `Dataset/stroke_patient` | 1 (`SYN_STROKE_01`) | 7 | 42,000 | Generated data, not a real patient; 60 s per movement |

## Format

One CSV per subject and movement, for example `Dataset/Healthy_person/S05/S05_Hand_Close.csv`:

```csv
timestamp_ms,adc_value,subject_id,movement_label
565470,553,S04,Up
565480,20,S04,Up
```

- `adc_value`: raw 12-bit ESP32 ADC reading (0-4095) of the MD0437 envelope.
- `movement_label`: Rest, Hand_Open, Hand_Close, Left, Right, Up or Down (the runtime labels in `config/labels.yaml`).
- Sampling: 100 Hz (10 ms steps).

## Quality checks

All 68 files were read on 2026-10-18:

- **Sample rate:** 100 Hz, not the 1 kHz of the firmware and `config/settings.yaml`. Set `fs: 100` before windowing this data.
- **Missing values:** none.
- **Zeros:** 59.8% of healthy samples and 20.9% of patient samples are exactly 0, the envelope's resting floor.
- **Saturation:** 0.57% of healthy samples sit at 4095, mostly during Hand_Close; the synthetic patient never saturates.
- **Joined recordings:** most files are one 60 s recording (6,000 samples). Exceptions:
    - S01 files run 1,652-7,789 samples with time gaps, and `S01_Down.csv` has a timestamp that jumps back 32 s.
    - S04 Hand_Close, Hand_Open and Up have 12,000 samples spread over up to 882 s.
    - `S02_Down.csv` has a 27 s gap.

  Split these files at the gaps before windowing, so no window spans two recordings.

## Mean activity per movement

Mean `adc_value` over all samples (envelope units, not strength):

| Movement | Healthy (9 volunteers) | Synthetic stroke patient |
|---|---|---|
| Hand_Close | 547.0 | 328.6 |
| Up | 237.6 | 264.5 |
| Down | 233.7 | 115.4 |
| Right | 209.8 | 192.1 |
| Left | 162.1 | 92.9 |
| Hand_Open | 39.2 | 46.8 |
| Rest | 12.4 | 21.1 |

Hand_Close produces by far the most activity, and Rest the least, in both groups. The synthetic patient is lower on most movements, but it is generated data and supports no clinical claim.

## Code status

The following still point at the deleted `Datasets/` folder, so none of them can read `Dataset/` yet:

- `src/data/public_datasets.py` (loader) and `python -m src.features.build_dataset --source ...`
- `src/realtime/emg_replay.py` (`python main.py live --emg-source replay`)
- `src/models/finetune_moment.py`
- `backend/webapi.py` dataset explorer (`DATASET_DIRS`)
- `tests/test_datasets_and_models.py` and `tests/test_emg_replay.py` (6 failing tests)

See [known_issues.md](known_issues.md).

## Your own recordings

Follow [data_collection_protocol.md](data_collection_protocol.md):

- EMG only: `python -m src.acquisition.emg_logger S10 1 --separate-files --ordered` (4 s trials, 15 per label, prompts in the terminal).
- EMG + camera labels: `python -m src.acquisition.fused_logger S10 1 --seconds 120`.

Both write to `data/raw/emg/` with columns `timestamp_ms, subject_id, session_id, trial_id, emg_value, label` (the fused logger adds `vision_confidence, pointer_x, pointer_y`). Build features with `python -m src.features.build_dataset`.

## Privacy

Files use coded IDs only. Keep raw data out of public repositories unless consent and ethics approval allow it.
