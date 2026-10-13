# Data collection protocol template

This is a planning aid, not ethics approval or clinical advice. Obtain institutional ethics approval before recruiting or recording participants. Restrict the initial protocol to consenting healthy adult volunteers unless separate approvals cover other groups.

## Before recording

- Assign a coded participant ID (for example `S01`); do not place names, contact details, or faces in dataset filenames.
- Explain the prototype, recording, storage, risks, voluntary participation, and withdrawal process; obtain written consent.
- Check that the EMG hardware is battery powered and isolated from mains while attached to a participant. Stop immediately if discomfort or skin irritation occurs.
- Clean the skin and place electrodes according to the sensor manufacturer's instructions. Record channel placement and any setup changes without identifying the person.
- Confirm the serial signal is neither flat nor saturated and the camera view contains only the hand where practical.

## Trial protocol

For EMG-only recording without a webcam, run `python -m src.acquisition.emg_logger S01 3 --labels Rest Hand_Open Hand_Close Left Right Up Down --separate-files --ordered` (replace the coded participant/session values as needed). The terminal prompts for each trial label; perform that movement for the 4-second recording. The logger stores raw EMG samples with the manually selected label in one CSV per label and refuses to overwrite existing separate files. For synchronized camera labels instead, use `python -m src.acquisition.fused_logger S01 3 --seconds 120`; keep the hand visible, and the camera assigns a label to each sensor sample. Raw webcam video is not saved.

Offer breaks and stop if fatigued. Repeat in a separately coded session where approved. Check that the CSV contains samples across the expected camera labels and that the EMG value is not flat or saturated. Build window-level RMS, MAV and related EMG features with `python -m src.features.build_dataset`. These features describe the recorded electrical activity; they are not clinical muscle-strength measurements. The EMG classifier training command is for offline research comparisons only and does not control runtime game movements.

## Storage and reporting

Keep raw data access limited to the approved project team, store it in the approved location, and follow the institution's retention/deletion policy. Report the actual number of participants, trials, exclusions, and evaluation split. Do not claim clinical efficacy from this prototype.
