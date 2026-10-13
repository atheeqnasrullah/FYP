import numpy as np

def make_windows(x, fs=1000, window_ms=200, step_ms=100):
    x = np.asarray(x)
    width, stride = round(fs * window_ms / 1000), round(fs * step_ms / 1000)
    if width <= 0 or stride <= 0:
        raise ValueError("Window and step must be positive")
    return [x[i:i + width] for i in range(0, len(x) - width + 1, stride)]
