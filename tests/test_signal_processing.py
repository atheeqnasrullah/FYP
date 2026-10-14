import numpy as np
import pytest
from src.features.emg_features import FEATURES, extract
from src.preprocessing.filters import clean
from src.preprocessing.windowing import make_windows


def test_extract_known_values():
    f = extract([1.0, -1.0, 1.0, -1.0])
    assert set(f) == set(FEATURES)
    assert f["RMS"] == pytest.approx(1.0) and f["MAV"] == pytest.approx(1.0)
    assert f["PEAK"] == 1.0 and f["WL"] == pytest.approx(6.0) and f["ZC"] == 3


def test_envelope_has_no_zero_crossings_and_rejects_bad_type():
    assert extract([1.0, 2.0, 1.0, 2.0], "envelope")["ZC"] == 0
    with pytest.raises(ValueError):
        extract([1.0, 2.0], "unknown")
    with pytest.raises(ValueError):
        extract([1.0])


def test_windows_count_and_width():
    windows = make_windows(np.arange(1000), fs=1000, window_ms=200, step_ms=100)
    assert len(windows) == 9 and all(len(w) == 200 for w in windows)


def test_clean_envelope_passthrough_and_raw_removes_dc():
    x = np.full(500, 5.0) + np.sin(np.linspace(0, 200 * np.pi, 500))
    assert np.array_equal(clean(x, signal_type="envelope"), x)
    assert abs(clean(x, signal_type="raw").mean()) < 0.05
    with pytest.raises(ValueError):
        clean(np.ones(10))
