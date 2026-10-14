import os
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]

def load_settings():
    with (ROOT / "config/settings.yaml").open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Per-machine override, e.g. EMG_SERIAL_PORT=/dev/cu.usbserial-0001 on macOS.
    if os.environ.get("EMG_SERIAL_PORT"):
        cfg["serial_port"] = os.environ["EMG_SERIAL_PORT"]
    return cfg

def runtime_labels():
    """Movement labels the camera can produce (config/labels.yaml without No_Hand)."""
    with (ROOT / "config/labels.yaml").open(encoding="utf-8") as f:
        return [label for label in yaml.safe_load(f)["labels"] if label != "No_Hand"]
