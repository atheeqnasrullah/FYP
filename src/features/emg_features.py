import numpy as np

FEATURES = ["RMS", "MAV", "VAR", "STD", "PEAK", "WL", "ZC", "SSC"]

def extract(window, signal_type="raw"):
    w = np.asarray(window, dtype=float).reshape(-1)
    if w.size < 2:
        raise ValueError("Feature extraction requires at least two samples")
    d = np.diff(w)
    threshold = 0.01 * np.std(w)
    if signal_type not in ("raw", "envelope"):
        raise ValueError("signal_type must be 'raw' or 'envelope'")
    zero_crossings = int(np.sum((w[:-1] * w[1:] < 0) & (np.abs(d) > threshold))) if signal_type == "raw" else 0
    return {"RMS": float(np.sqrt(np.mean(w ** 2))), "MAV": float(np.mean(np.abs(w))),
            "VAR": float(np.var(w)), "STD": float(np.std(w)), "PEAK": float(np.max(np.abs(w))),
            "WL": float(np.sum(np.abs(d))),
            "ZC": zero_crossings,
            "SSC": int(np.sum((d[:-1] * d[1:] < 0) & ((np.abs(d[:-1]) > threshold) | (np.abs(d[1:]) > threshold))))}
