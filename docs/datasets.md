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

- **Sample rate:** 100 Hz, not the 1 kHz of the firmware and `config/settings.yaml`. The dataset tools use 100 Hz automatically.
- **Missing values:** none.
- **Zeros:** 59.8% of healthy samples and 20.9% of patient samples are exactly 0, the envelope's resting floor.
- **Saturation:** 0.57% of healthy samples sit at 4095, mostly during Hand_Close (up to 8.4% in `S02_Hand_Close.csv`); the synthetic patient never saturates.
- **Dropped samples:** S01 has about 2,400 short gaps of 20-560 ms (a lossy recording link); the other subjects have at most 7.
- **Joined recordings:** most files are one 60 s recording (6,000 samples). Exceptions:
    - S01 files run 1,652-7,789 samples, and `S01_Down.csv` has a timestamp that jumps back 32 s.
    - S04 Hand_Close, Hand_Open and Up have 12,000 samples spread over up to 882 s.
    - `S02_Down.csv` has a 27 s gap.

  The loader splits these files at the gaps, so no window spans two recordings.

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

## Code

`src/data/public_datasets.py` loads `Dataset/` into the repository's long format (`timestamp_ms, subject_id, session_id, trial_id, emg_value, label, cohort, source, signal_type, fs, file`):

- Sources: `healthy` (S01-S09) and `stroke_synthetic`; `public` in the feature builder means both.
- Each file is split into segments at gaps over 1 s or backwards timestamps, giving 73 segments (66 healthy, 7 patient); each segment is one trial, so windows never cross a gap.
- Every row carries `fs` = 100, which the feature builder, replay and fine-tuning use for window sizes.

```bash
python -m src.data.public_datasets                          # summary of both sources
python -m src.features.build_dataset --source public        # 41,066 windows of 200 ms
python -m src.evaluation.emg_activity_report                # quality and activity tables, figures
```

The web app's EMG Datasets page, EMG replay (`--emg-source replay`) and MOMENT-1 fine-tuning all read this folder.

For fine-tuning, `python -m src.data.prepare_finetune` turns this folder into model-ready windows in `data/processed/moment/`; see [fine_tuning_moment.md](fine_tuning_moment.md#data-preprocessing).

## Your own recordings

Follow [data_collection_protocol.md](data_collection_protocol.md):

- EMG only: `python -m src.acquisition.emg_logger S10 1 --separate-files --ordered` (4 s trials, 15 per label, prompts in the terminal).
- EMG + camera labels: `python -m src.acquisition.fused_logger S10 1 --seconds 120`.

Both write to `data/raw/emg/` with columns `timestamp_ms, subject_id, session_id, trial_id, emg_value, label` (the fused logger adds `vision_confidence, pointer_x, pointer_y`). Build features with `python -m src.features.build_dataset`.

## Privacy

Files use coded IDs only. Keep raw data out of public repositories unless consent and ethics approval allow it.
