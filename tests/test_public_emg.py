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


def _fake_db1(folder, reps=2):
    """A tiny Exercise B file: every movement `reps` times, 300 samples each, with 200-sample pauses."""
    from scipy.io import savemat
    label = []
    for move in range(1, 18):
        for _ in range(reps): label += [move] * 300 + [0] * 200
    label = np.array(label)
    emg = np.stack([label * 0.01 + ch * 0.001 + 0.002 for ch in range(10)], axis=1)  # positive envelope, label-coded
    folder.mkdir(parents=True)
    savemat(folder / "S1_A1_E2.mat", {"emg": emg, "restimulus": label[:, None], "rerepetition": np.zeros((len(label), 1))})
    return emg, label


@pytest.mark.parametrize("mapping, up, radial", [("none", "Wrist_Extension", "Radial_Deviation"),
                                               ("direct", "Up", "Left"), ("mirrored", "Up", "Right")])
def test_db1_keeps_our_seven_movements_and_maps_directions(tmp_path, monkeypatch, mapping, up, radial):
    emg, label = _fake_db1(tmp_path / "ninapro_db1/raw/s1")
    monkeypatch.setattr(public_emg, "PUBLIC_DIR", tmp_path)
    records = public_emg.load_db1(mapping)
    by_label = {}
    for r in records: by_label.setdefault(r["label"], []).append(r)
    assert len(by_label) == 7 and {"Rest", "Hand_Open", "Hand_Close", up} <= set(by_label)
    assert all(len(v) == 2 * 10 for v in by_label.values())          # 2 repetitions x 10 electrodes, Rest thinned to match
    r = next(r for r in by_label[up] if r["channel"] == 1)
    assert np.allclose(np.diff(r["t"]), 10)                            # already 100 Hz
    assert np.allclose(r["adc"], emg[label == 14, 0][:300])            # envelope passed through, not re-rectified
    r = next(r for r in by_label[radial] if r["channel"] == 1)
    assert np.allclose(r["adc"], 15 * 0.01 + 0.002)                    # movement 15 (radial deviation) under its mapped name


def test_db1_windows_fit_moment(tmp_path, monkeypatch):
    _fake_db1(tmp_path / "ninapro_db1/raw/s1")
    monkeypatch.setattr(public_emg, "PUBLIC_DIR", tmp_path)
    monkeypatch.setattr(public_emg, "target_p95", lambda: 1000.0)
    X, mask, manifest, labels, _ = public_emg.build("ninapro_db1", mapping="direct")
    assert X.shape[1:] == (1, 512) and len(X) == len(manifest) == 7 * 2 * 10
    assert set(labels) == {"Rest", "Hand_Open", "Hand_Close", "Left", "Right", "Up", "Down"}
    assert (mask.sum(1) <= 300).all()                                  # short repetitions are left-padded and masked
