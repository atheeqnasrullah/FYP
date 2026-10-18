import zipfile
import numpy as np
import pytest
from src.data import public_emg
from src.data.download_public import safe_extract


def test_envelope_is_rectified_smoothed_and_100hz():
    t = np.arange(0, 2000, 1.0)                       # 2 s at 1 kHz
    x = np.sin(2 * np.pi * 50 * t / 1000) * 0.5          # zero-mean signal
    grid, env = public_emg.envelope(t, x)
    assert np.allclose(np.diff(grid), 10)                # 100 Hz
    assert env.min() >= 0
    assert abs(np.median(env) - 0.5 / np.sqrt(2)) < 0.05  # RMS of a sine


def test_uci_labels_share_three_movements_with_dataset():
    assert set(public_emg.SHARED) <= set(public_emg.UCI_LABELS.values())
    assert public_emg.UCI_LABELS[2] == "Hand_Close" and public_emg.UCI_LABELS[7] == "Hand_Open"


def test_safe_extract_refuses_paths_outside_target(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escape.txt", "x")
    with pytest.raises(RuntimeError):
        safe_extract(archive, tmp_path / "out")
