"""Synchronously record ESP32 EMG samples with camera-derived movement labels."""
import argparse
import csv
import queue
import time
from collections import Counter

import serial

from src.realtime.pipeline import latest, lock, shutdown, start, status_bus
from src.utils.config import ROOT, load_settings


def main():
    parser = argparse.ArgumentParser(
        description="Record EMG samples synchronized with webcam movement labels."
    )
    parser.add_argument("subject", help="Coded participant ID, e.g. S01")
    parser.add_argument("session", type=int)
    parser.add_argument("--seconds", type=int, default=120, help="Recording duration (default: 120 seconds)")
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error("--seconds must be at least 1")

    cfg = load_settings()
    output_dir = ROOT / "data/raw/emg"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.subject}_session{args.session}_fused.csv"
    port = serial.Serial(cfg["serial_port"], cfg["baud_rate"], timeout=1)
    counts = Counter()
    rows_written = 0
    previous_label = None
    trial_id = 0
    started = False

    try:
        port.reset_input_buffer()
        while True:
            try:
                status_bus.get_nowait()
            except queue.Empty:
                break
        start(use_emg=False, use_vision=True, show_preview=False)
        started = True
        print("Recording EMG with camera-derived labels. Show one hand clearly to the webcam.")
        print("Detected labels include Hand_Open, Hand_Close, Left, Right, Up and Down.")
        print("No visible hand is recorded as No_Hand. Press Ctrl+C to stop early.")

        with output_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow([
                "timestamp_ms", "subject_id", "session_id", "trial_id",
                "emg_value", "label", "vision_confidence", "pointer_x", "pointer_y",
            ])
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                try:
                    message = status_bus.get_nowait()
                except queue.Empty:
                    message = None
                if message:
                    raise RuntimeError(f"Webcam pipeline stopped: {message}")

                parts = port.readline().decode(errors="ignore").strip().split(",")
                if len(parts) != 2:
                    continue
                try:
                    timestamp_ms, value = int(parts[0]), int(parts[1])
                except ValueError:
                    continue

                with lock:
                    visual = latest.get("vis")
                    pointer = latest.get("pointer")
                label, confidence = visual if visual else ("No_Hand", 0.0)
                if label != previous_label:
                    trial_id += 1
                    previous_label = label
                    print(f"Camera label: {label} ({confidence:.2f})")
                x, y = pointer if pointer else ("", "")
                writer.writerow([
                    timestamp_ms, args.subject, args.session, trial_id,
                    value, label, f"{confidence:.3f}", x, y,
                ])
                rows_written += 1
                counts[label] += 1
                if rows_written % 100 == 0:
                    output.flush()
            output.flush()
    except KeyboardInterrupt:
        print("Recording stopped by user.")
    finally:
        port.close()
        if started:
            shutdown()

    print(f"Saved {rows_written} synchronized samples to {output_path}")
    print(f"Samples by camera label: {dict(counts)}")
    if rows_written == 0:
        print("WARNING: No EMG rows were received. Check ESP32 firmware, COM port, and baud rate.")


if __name__ == "__main__":
    main()
