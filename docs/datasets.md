# Datasets

Three sources of EMG data are used. Only the healthy volunteers are real recordings of people; the patient files are synthetic.

| Source key | Location | Subjects | Signal | Pipeline path |
|---|---|---|---|---|
| `healthy_raw` | `Datasets/Noraml People data/raw_signals/volunteer_N.csv` | 11 (H01-H11) | Rectified EMG scaled to mV (10-bit ADC, 4.887 mV steps, 0-3,226 mV) | Envelope: no bandpass |
| `healthy_filtered` | `Datasets/Noraml People data/filtered_signals/volunteer_filtered_N.csv` | 11 (same people) | Smoothed activity envelope | Envelope |
| `simulated_patient` | `Datasets/Patiant data/simulated_patient_raw_emg_N.csv` | 3 (SP01-SP03) | Synthetic bipolar EMG in mV, labelled `SYNTHETIC_SIMULATED_PATIENT_RAW_EMG_mV` | Raw: 20-450 Hz bandpass + 50 Hz notch |
| `recorded` | `data/raw/emg/*.csv` | Own recordings | MD0437 envelope from the ESP32 | From `config/settings.yaml` (`envelope`) |

## Format

Each Datasets/ CSV has one column per gesture: `HandOpen, HandClose, Wrist Flexion, Wrist Extension, Supination, Pronation, Rest`. A column is one continuous recording at 1 kHz, 5.5-6.5 s long (5,467-6,520 samples). `src/data/public_datasets.py` turns them into the repository's long format:

`timestamp_ms, subject_id, session_id, trial_id, emg_value, label, cohort, source, signal_type`

Gesture names map to `Hand_Open, Hand_Close, Wrist_Flexion, Wrist_Extension, Supination, Pronation, Rest`. These are **wrist/forearm gesture labels for offline EMG research**. The games use the camera's labels (`Rest, Hand_Open, Hand_Close, Left, Right, Up, Down`, from `config/labels.yaml`); the two sets are deliberately not merged.

## Data quality

`python -m src.evaluation.emg_activity_report` writes `results/tables/data_quality.csv`. Findings:

- 175 recordings (11 x 7 x 2 healthy + 3 x 7 patient), no missing values.
- At most 0.1% of samples in any recording sit at its maximum, so there is no clipping.
- The volunteer "raw" files are already rectified (never negative). A raw-EMG bandpass removes their activity level, so they take the envelope path. Baseline cross-subject accuracy rose from 26.7% to 28.8% (SVM) with this choice.
- The three simulated patients have exactly the lengths of volunteers 1-3, so they are assumed to be derived from them. They are never mixed into healthy training, and results on them are reported separately as synthetic.

## Own recordings

Record with the protocol in `docs/data_collection_protocol.md`:

- EMG only: `python -m src.acquisition.emg_logger S01 1 --separate-files --ordered`
- EMG + camera labels: `python -m src.acquisition.fused_logger S01 1 --seconds 120`

The `S01_*` files currently in `data/raw/emg/` contain only headers (no samples yet).

## Building feature tables

```bash
python -m src.features.build_dataset --source healthy_raw        # data/features/emg_features_healthy_raw.csv
python -m src.features.build_dataset --source healthy_filtered
python -m src.features.build_dataset --source public             # healthy_raw + simulated_patient
python -m src.features.build_dataset                             # own recordings -> emg_features.csv
```

Windows are 200 ms with a 100 ms step. Features: RMS, MAV, VAR, STD, PEAK, WL, ZC (raw signals only), SSC. The public table has 5,810 windows: 4,578 healthy (654 per gesture) and 1,232 simulated patient.

## Privacy

Participant files use coded IDs only. Keep raw data out of public repositories unless the consent and ethics approval allow it. `.gitignore` excludes `data/raw/`, feature CSVs, logs, the database and saved models.
