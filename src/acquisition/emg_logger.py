import argparse, csv, random, time
from contextlib import ExitStack
from pathlib import Path
import serial
from src.utils.config import ROOT, load_settings

def main():
    all_labels = ["Rest", "Hand_Open", "Hand_Close", "Left", "Right", "Up", "Down"]
    parser = argparse.ArgumentParser(description="Record EMG-only trials from the configured serial device; labels are entered manually.")
    parser.add_argument("subject")
    parser.add_argument("session", type=int)
    parser.add_argument("--labels", nargs="+", choices=all_labels, default=all_labels,
                        help="Movement labels to record; no webcam is used. Example: Rest Hand_Open Hand_Close Left Right Up Down")
    parser.add_argument("--separate-files", action="store_true",
                        help="Write one CSV per movement label instead of one combined session CSV")
    parser.add_argument("--ordered", action="store_true",
                        help="Record all repetitions label by label in the order supplied (default: shuffle trials).")
    args = parser.parse_args()
    subject, session, labels = args.subject, args.session, args.labels
    cfg = load_settings()
    trials = [(label, rep) for label in labels for rep in range(1, 16)]; random.shuffle(trials)
    if args.ordered:
        trials = [(label, rep) for label in labels for rep in range(1, 16)]
    outdir = ROOT / "data/raw/emg"; outdir.mkdir(parents=True, exist_ok=True)
    if args.separate_files:
        output_paths = {label: outdir / f"{subject}_session{session}_{label}.csv" for label in labels}
        existing = [str(path) for path in output_paths.values() if path.exists()]
        if existing:
            parser.error("Output file(s) already exist; choose a new session number to avoid overwriting: " + ", ".join(existing))
    else:
        output_paths = {}
    port = serial.Serial(cfg["serial_port"], cfg["baud_rate"], timeout=1); time.sleep(2)

    try:
        with ExitStack() as stack:
            if args.separate_files:
                writers = {}; output_files = {}
                for label, path in output_paths.items():
                    f = stack.enter_context(path.open("w", newline="", encoding="utf-8"))
                    output_files[label] = f
                    writers[label] = csv.writer(f)
                    writers[label].writerow(["timestamp_ms", "subject_id", "session_id", "trial_id", "emg_value", "label"])
                shared_writer = None
            else:
                path = outdir / f"{subject}_session{session}.csv"
                f = stack.enter_context(path.open("w", newline="", encoding="utf-8"))
                shared_writer = csv.writer(f)
                shared_writer.writerow(["timestamp_ms", "subject_id", "session_id", "trial_id", "emg_value", "label"])
                writers = {}
            for trial_id, (label, _) in enumerate(trials, 1):
                input(f"Trial {trial_id}/{len(trials)}. Prepare {label}; press Enter to record 4 s (Ctrl+C stops): ")
                # Discard samples gathered while the participant was reading the
                # prompt/resting so every row belongs to this labelled trial.
                port.reset_input_buffer()
                samples_written = 0
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    parts = port.readline().decode(errors="ignore").strip().split(",")
                    if len(parts) == 2:
                        try: timestamp, value = int(parts[0]), int(parts[1])
                        except ValueError: continue
                        writer = writers[label] if args.separate_files else shared_writer
                        writer.writerow([timestamp, subject, session, trial_id, value, label])
                        samples_written += 1
                (output_files[label] if args.separate_files else f).flush()
                if samples_written == 0:
                    print("WARNING: 0 EMG samples received. Check the ESP32 sketch, COM port, baud rate (921600), and CSV serial format.")
                else:
                    print(f"Captured {samples_written} EMG samples for {label}.")
                print("Rest for 3 seconds"); time.sleep(3)
    finally: port.close()
    if args.separate_files:
        print("Saved separate label files:")
        for path in output_paths.values(): print(path)

if __name__ == "__main__": main()
