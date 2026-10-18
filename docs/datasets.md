# Datasets

`Dataset/` (added 2026-10-16) holds MD0437 envelope recordings from 9 healthy volunteers and one stroke patient, already labelled with the same 7 movements the games use. It replaces the older `Datasets/` folder (11 volunteers in wide format, 3 synthetic patients), which was deleted the same day.

## Contents

| Group | Folder | Subjects | Files | Samples | Notes |
|---|---|---|---|---|---|
| Healthy volunteers | `Dataset/Healthy_person/S01`-`S09` | 9 | 61 | 369,435 | One file per movement; S01 has no Rest file, S04 has no Down file |
| Stroke patient | `Dataset/stroke_patient` | 1 (`SP01`) | 7 | 42,000 | 60 s per movement; used only as an extra test, never for training |

**Patient file change (2026-10-18, 14:58):** the earlier patient `SYN_STROKE_01`, which was generated (synthetic) data, was replaced by `SP01`. Whether `SP01` is a real recording or also generated is not stated in the repository; confirm it before making any claim about stroke patients. `SP01` looks different from the healthy recordings: its values never exceed 200 and never reach 0, and its activity is much lower (table below).

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
- **Zeros:** 59.8% of healthy samples are exactly 0, the envelope's resting floor; `SP01` has none.
- **Saturation:** 0.57% of healthy samples sit at 4095, mostly during Hand_Close (up to 8.4% in `S02_Hand_Close.csv`); `SP01` never exceeds 200.
- **Dropped samples:** S01 has about 2,400 short gaps of 20-560 ms (a lossy recording link); the other subjects have at most 7.
- **Joined recordings:** most files are one 60 s recording (6,000 samples). Exceptions:
    - S01 files run 1,652-7,789 samples, and `S01_Down.csv` has a timestamp that jumps back 32 s.
    - S04 Hand_Close, Hand_Open and Up have 12,000 samples spread over up to 882 s.
    - `S02_Down.csv` has a 27 s gap.

  The loader splits these files at the gaps, so no window spans two recordings.

## Mean activity per movement

Mean `adc_value` over all samples (envelope units, not strength):

| Movement | Healthy (9 volunteers) | Stroke patient `SP01` |
|---|---|---|
| Hand_Close | 547.0 | 67.2 |
| Up | 237.6 | 31.3 |
| Down | 233.7 | 47.2 |
| Right | 209.8 | 29.8 |
| Left | 162.1 | 21.2 |
| Hand_Open | 39.2 | 15.9 |
| Rest | 12.4 | 8.3 |

Hand_Close produces by far the most activity, and Rest the least, in both groups. `SP01`'s values are 5-8 times lower than the healthy volunteers' on every movement, with the same order of movements.

## Code

`src/data/public_datasets.py` loads `Dataset/` into the repository's long format (`timestamp_ms, subject_id, session_id, trial_id, emg_value, label, cohort, source, signal_type, fs, file`):

- Sources: `healthy` (S01-S09) and `stroke_patient`; `public` in the feature builder means both.
- Each file is split into segments at gaps over 1 s or backwards timestamps, giving 73 segments (66 healthy, 7 patient); each segment is one trial, so windows never cross a gap.
- Every row carries `fs` = 100, which the feature builder, replay and fine-tuning use for window sizes.

```bash
python -m src.data.public_datasets                          # summary of both sources
python -m src.features.build_dataset --source public        # 41,066 windows of 200 ms
python -m src.evaluation.emg_activity_report                # quality and activity tables, figures
```

The web app's EMG Datasets page, EMG replay (`--emg-source replay`) and MOMENT-1 fine-tuning all read this folder.

For fine-tuning, `python -m src.data.prepare_finetune` turns this folder into model-ready windows in `data/processed/moment/`; see [fine_tuning_moment.md](fine_tuning_moment.md#data-preprocessing).

## Public data (UCI EMG Data for Gestures)

To test whether outside data improves accuracy, one public dataset was downloaded and converted. It is not committed (see `.gitignore`); anyone can fetch it with the script.

| Item | Value |
|---|---|
| Dataset | [UCI EMG Data for Gestures](https://archive.ics.uci.edu/dataset/481/emg+data+for+gestures) (Lobov et al., *Sensors* 2018), CC BY 4.0 |
| Download | `python -m src.data.download_public` into `Dataset/public/uci_gestures/` (17 MB) |
| Content | 36 healthy people, 8-channel Myo armband, about 1 kHz, 2 series x 6-7 gestures of about 1.8 s |
| Labels | Rest, fist (= Hand_Close), extended palm (= Hand_Open, only a few people), wrist flexion, wrist extension, radial deviation, ulnar deviation |
| Conversion | `python -m src.data.public_emg uci_gestures`: each armband channel is rectified, smoothed (100 ms moving RMS), resampled to 100 Hz and scaled to our ADC range, then windowed like `Dataset/` (log1p, calibration, 512-sample windows, short gestures padded and masked) |
| Output | `data/processed/public/uci_gestures_windows.npz`: 6,288 windows (36 people x 8 channels); 2,120 share our labels (Rest 1,008, Hand_Close 1,048, Hand_Open 64) |

The wrist movements keep their own names, because it is not known how they relate to our Left/Right/Up/Down. A second dataset, EMG-EPN-612 (612 people, 5.5 GB), was considered but its download was stopped; the script can still fetch it (`python -m src.data.download_public epn612`), but nothing uses it.

How much the public data helped is in [model_comparison.md](model_comparison.md#public-data-uci).

## Your own recordings

Follow [data_collection_protocol.md](data_collection_protocol.md):

- EMG only: `python -m src.acquisition.emg_logger S10 1 --separate-files --ordered` (4 s trials, 15 per label, prompts in the terminal).
- EMG + camera labels: `python -m src.acquisition.fused_logger S10 1 --seconds 120`.

Both write to `data/raw/emg/` with columns `timestamp_ms, subject_id, session_id, trial_id, emg_value, label` (the fused logger adds `vision_confidence, pointer_x, pointer_y`). Build features with `python -m src.features.build_dataset`.

## Privacy

Files use coded IDs only. Keep raw data out of public repositories unless consent and ethics approval allow it.
