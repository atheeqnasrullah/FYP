import numpy as np
from scipy.signal import butter, filtfilt, iirnotch

def bandpass(x, fs=1000, low=20, high=450, order=4):
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) < 32:
        raise ValueError("Expected at least 32 samples in a one-dimensional signal")
    nyquist = fs / 2
    high = min(high, nyquist * 0.95)
    if low >= high:
        raise ValueError("Invalid bandpass for configured sample rate")
    b, a = butter(order, [low / nyquist, high / nyquist], btype="band")
    return filtfilt(b, a, x)

def notch(x, fs=1000, f0=50, q=30):
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) < 32:
        raise ValueError("Expected at least 32 samples in a one-dimensional signal")
    if not 0 < f0 < fs / 2:
        return x.copy()
    b, a = iirnotch(f0 / (fs / 2), q)
    return filtfilt(b, a, x)

def clean(x, fs=1000, low=20, high=450, notch_hz=50, signal_type="raw"):
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) < 32:
        raise ValueError("Expected at least 32 samples in a one-dimensional signal")
    if signal_type == "envelope":
        # The MD0437 has already filtered, rectified and smoothed the EMG.
        # Preserve its activation level; a 20-450 Hz raw-EMG bandpass would remove it.
        return x.copy()
    if signal_type != "raw":
        raise ValueError("signal_type must be 'raw' or 'envelope'")
    nyquist = fs / 2
    x = x - np.mean(x)
    x = bandpass(x, fs, low, high)
    if 0 < notch_hz < nyquist:
        x = notch(x, fs, notch_hz)
    return x
