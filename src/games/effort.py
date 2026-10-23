"""Grip-effort threshold for Webcam + EMG sessions.

The MD0437 gives an activity envelope in ADC units, not a force, so effort is
measured against the patient's own range. A short calibration records their
rest level and their strongest comfortable squeeze, and

    effort % = (RMS - rest) / (strongest - rest) * 100

A grip action (pop a balloon, brake, grab gold, pick up a shape) only counts
when effort reaches the required level. The required level is the therapist's
setting (game_effort_required / --effort) or, in auto, follows the difficulty
level, so it rises as the patient succeeds and falls after weak attempts.
"""
import json
import os
import time

import numpy as np

from src.utils.config import ROOT

AUTO_RANGE = (25, 60)   # required effort % at the easiest and hardest level
MIN_SPAN = 0.05         # strongest squeeze must be at least 5% above rest to count as a calibration


def calibration_path():
    return os.environ.get("REHAB_EMG_CALIBRATION") or str(ROOT / "data/logs/emg_calibration.json")


def _load_all():
    try:
        with open(calibration_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_calibration(patient):
    """The patient's saved calibration ({rest_rms, max_rms, ...}) or None."""
    saved = _load_all().get(patient)
    if isinstance(saved, dict) and valid(saved.get("rest_rms"), saved.get("max_rms")):
        return saved
    return None


def save_calibration(patient, rest, peak, source):
    data = _load_all()
    data[patient] = {"rest_rms": round(float(rest), 3), "max_rms": round(float(peak), 3), "source": source,
                     "date": time.strftime("%Y-%m-%dT%H:%M:%S")}
    path = calibration_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data[patient]


def valid(rest, peak):
    try:
        rest, peak = float(rest), float(peak)
    except (TypeError, ValueError):
        return False
    return peak > 0 and peak - rest >= MIN_SPAN * peak


def calibrate(rest_values, squeeze_values):
    """(rest, strongest) from RMS readings taken while relaxed and while squeezing, or None if no squeeze was seen."""
    rest_values = [float(v) for v in rest_values if v and v > 0]
    squeeze_values = [float(v) for v in squeeze_values if v and v > 0]
    if not rest_values or not squeeze_values:
        return None
    rest, peak = float(np.median(rest_values)), float(np.percentile(squeeze_values, 90))
    return (rest, peak) if valid(rest, peak) else None


def effort_pct(rms, rest, peak):
    """Effort as a percentage of the calibrated range, clipped to 0-100."""
    span = peak - rest
    if span <= 0:
        return 0.0
    return float(min(100.0, max(0.0, 100.0 * (rms - rest) / span)))


def parse_required(setting):
    """'auto' (or None) or a fixed percentage 0-100; 0 turns the threshold off."""
    if setting is None or str(setting).strip().lower() == "auto":
        return "auto"
    try:
        value = float(str(setting).strip().rstrip("%"))
    except ValueError:
        raise ValueError(f"Required effort must be 'auto' or a number from 0 to 100, not {setting!r}")
    if not 0 <= value <= 100:
        raise ValueError(f"Required effort must be from 0 to 100, not {value:g}")
    return value


def required_effort(setting, difficulty):
    value = parse_required(setting)
    return difficulty.value(*AUTO_RANGE) if value == "auto" else value
