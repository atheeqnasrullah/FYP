# Datasets

`Dataset/` (added 2026-10-16, extended 2026-10-22) holds MD0437 envelope recordings from 20 healthy volunteers and two stroke patients, already labelled with the same 7 movements the games use. It replaces the older `Datasets/` folder (11 volunteers in wide format, 3 synthetic patients), which was deleted the same day.

## Contents

| Group | Folder | Subjects | Files | Samples | Notes |
|---|---|---|---|---|---|
| Healthy volunteers | `Dataset/Healthy_person/S01`-`S20` | 20 | 138 | 831,435 | One file per movement; S01 has no Rest file, S04 has no Down file. S10-S20 were added on 2026-10-22 |
| Stroke patients | `Dataset/stroke_patient/SP01/`, `SP02/` | 2 (`SP03`, `SP02`) | 14 | 84,000 | 60 s per movement; used only as an extra test, never for training |

**Patient ID mismatch (2026-10-22):** the files in `stroke_patient/SP01/` are named `SP01_*.csv` but carry `subject_id` `SP03` inside, so results report them as `SP03`. They are not the earlier `SP01` recordings (different values). Confirm which ID is correct. Both patient folders differ from the volunteer recordings: timestamps start at 0 in every file, values never exceed 291 (both patients hit exactly that maximum), and activity is far lower except for Hand_Close (table below). Whether they are real or generated recordings is not stated in the repository; confirm it before making any claim about stroke patients.

**Earlier patient file change (2026-10-18, 14:58):** the earlier patient `SYN_STROKE_01`, which was generated (synthetic) data, was replaced by `SP01`. Whether `SP01` is a real recording or also generated is not stated in the repository; confirm it before making any claim about stroke patients. `SP01` looks different from the healthy recordings: its values never exceed 200 and never reach 0, and its activity is much lower (table below).

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

All 68 files were read on 2026-10-18; the 2026-10-22 additions (S10-S20, `SP02`, `SP03`) were checked on 2026-10-28 and are noted where they differ:

- **Sample rate:** 100 Hz, not the 1 kHz of the firmware and `config/settings.yaml`. The dataset tools use 100 Hz automatically.
- **Missing values:** none.
- **Zeros:** 59.8% of healthy samples are exactly 0, the envelope's resting floor (56.3% over all 20 volunteers); `SP01` had none, `SP02`/`SP03` 53.3%.
- **Saturation:** 0.57% of healthy samples sit at 4095, mostly during Hand_Close (up to 8.4% in `S02_Hand_Close.csv`); `SP01` never exceeded 200, `SP02`/`SP03` never exceed 291.
- **Dropped samples:** S01 has about 2,400 short gaps of 20-560 ms (a lossy recording link); the other subjects have at most 7, and S10-S20 have none (every step is exactly 10 ms).
- **Joined recordings:** most files are one 60 s recording (6,000 samples). Exceptions:
    - S01 files run 1,652-7,789 samples, and `S01_Down.csv` has a timestamp that jumps back 32 s.
    - S04 Hand_Close, Hand_Open and Up have 12,000 samples spread over up to 882 s.
    - `S02_Down.csv` has a 27 s gap.

  The loader splits these files at the gaps, so no window spans two recordings.

## Mean activity per movement

Mean `adc_value` over all samples (envelope units, not strength):

| Movement | Healthy (20 volunteers) | `SP02` | `SP03` | Earlier patient `SP01` |
|---|---|---|---|---|
| Hand_Close | 614.7 | 153.5 | 127.4 | 67.2 |
| Down | 335.3 | 4.5 | 12.4 | 47.2 |
| Right | 201.5 | 19.0 | 8.4 | 29.8 |
| Up | 198.6 | 8.0 | 1.9 | 31.3 |
| Left | 130.8 | 1.8 | 6.5 | 21.2 |
| Hand_Open | 40.9 | 1.7 | 1.3 | 15.9 |
| Rest | 12.9 | 0.3 | 0.2 | 8.3 |

Hand_Close produces by far the most activity, and Rest the least, in every group. The new patients are 4-5 times weaker than the volunteers on Hand_Close and 20-100 times weaker on the other movements.

**The new volunteers are more alike than the first nine.** S10-S20 show nearly the same activity pattern (for example, Down is about 400 on almost all of them), while S02-S09 vary widely (Down from 64 to 413). No recording is a copy of another (no pair correlates above 0.8). This makes S10-S20 much easier to classify (80-94% against 44-49% for S02-S09; see [model_comparison.md](model_comparison.md#per-volunteer-loso-accuracy)).

## Code

`src/data/public_datasets.py` loads `Dataset/` into the repository's long format (`timestamp_ms, subject_id, session_id, trial_id, emg_value, label, cohort, source, signal_type, fs, file`):

- Sources: `healthy` (S01-S20, `Healthy_person/**/*.csv`) and `stroke_patient` (`stroke_patient/**/*.csv`, one folder per patient); `public` in the feature builder means both.
- Each file is split into segments at gaps over 1 s or backwards timestamps, giving 157 segments (143 healthy, 14 patient); each segment is one trial, so windows never cross a gap.
- Every row carries `fs` = 100, which the feature builder, replay and fine-tuning use for window sizes.

```bash
python -m src.data.public_datasets                          # summary of both sources
python -m src.features.build_dataset --source public        # 41,066 windows of 200 ms
python -m src.evaluation.emg_activity_report                # quality and activity tables, figures
```

The web app's EMG Datasets page, EMG replay (`--emg-source replay`) and MOMENT-1 fine-tuning all read this folder.

For fine-tuning, `python -m src.data.prepare_finetune` turns this folder into model-ready windows in `data/processed/moment/`; see [fine_tuning_moment.md](fine_tuning_moment.md#data-preprocessing).

## Public data

To test whether outside data improves accuracy, two public datasets were downloaded and converted. They are not committed (see `.gitignore`); anyone can fetch them with `python -m src.data.download_public uci_gestures epn612` (large files use 8 parallel connections, resume after interruptions and are checked against the published MD5).

| Item | UCI EMG Data for Gestures | EMG-EPN-612 |
|---|---|---|
| Source | [archive.ics.uci.edu/dataset/481](https://archive.ics.uci.edu/dataset/481/emg+data+for+gestures) (Lobov et al., *Sensors* 2018) | [doi.org/10.5281/zenodo.4421500](https://doi.org/10.5281/zenodo.4421500) (v2.1, Escuela Politécnica Nacional) |
| Licence | CC BY 4.0 | CC BY 4.0 |
| Folder, size | `Dataset/public/uci_gestures/`, 17 MB | `Dataset/public/epn612/`, 5.5 GB zip, 11 GB unpacked |
| People | 36 healthy | 612 healthy (306 + 306) |
| Recording | 8-channel Myo armband, about 1 kHz; 2 series x 6-7 gestures of about 1.8 s | 8-channel Myo armband, 200 Hz; 150-300 labelled 5 s recordings per person (25 per gesture), gesture about 1 s inside |
| Labels | Rest, fist (= Hand_Close), extended palm (= Hand_Open, only a few people), wrist flexion, wrist extension, radial deviation, ulnar deviation | noGesture (= Rest), fist (= Hand_Close), open (= Hand_Open), waveIn (wrist flexion), waveOut (wrist extension), pinch |
| Conversion | `python -m src.data.public_emg uci_gestures`: all 8 channels | `python -m src.data.public_emg epn612`: one random channel per recording, full 5 s |
| Output | `data/processed/public/uci_gestures_windows.npz`: 6,288 windows; 2,120 share our labels | `data/processed/public/epn612_windows.npz`: 137,700 windows (22,950 per gesture); 68,850 share our labels |

Conversion, for both: each armband channel is rectified, smoothed (100 ms moving RMS), resampled to 100 Hz and scaled to our ADC range, then windowed like `Dataset/` (log1p, per-recording-channel calibration, 512-sample windows; short recordings padded and masked). The wrist movements keep their own names, because it is not known how they relate to our Left/Right/Up/Down.

How much the public data helped: [model_comparison.md](model_comparison.md#public-data-uci-and-emg-epn-612). In short, it did not improve accuracy on our volunteers.

## Your own recordings

Follow [data_collection_protocol.md](data_collection_protocol.md):

- EMG only: `python -m src.acquisition.emg_logger S10 1 --separate-files --ordered` (4 s trials, 15 per label, prompts in the terminal).
- EMG + camera labels: `python -m src.acquisition.fused_logger S10 1 --seconds 120`.

Both write to `data/raw/emg/` with columns `timestamp_ms, subject_id, session_id, trial_id, emg_value, label` (the fused logger adds `vision_confidence, pointer_x, pointer_y`). Build features with `python -m src.features.build_dataset`.

## Privacy

Files use coded IDs only. Keep raw data out of public repositories unless consent and ethics approval allow it.
