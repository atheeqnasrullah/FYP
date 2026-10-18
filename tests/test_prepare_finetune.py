import json
import numpy as np
from src.data import prepare_finetune as prep


def test_resample_fills_dropped_samples_on_10ms_grid():
    grid, values, interp = prep.resample_segment(np.array([0., 10., 40., 50.]), np.array([0., 10., 40., 50.]))
    assert grid.tolist() == [0, 10, 20, 30, 40, 50]
    assert values.tolist() == [0, 10, 20, 30, 40, 50]
    assert interp.tolist() == [False, False, True, True, False, False]


def test_short_segments_are_padded_and_masked():
    record = {"adc": np.full(300, 100.0), "interp": np.zeros(300, bool), "t": np.arange(300) * 10.0}
    wins, dropped = prep.windows_from(record, {"mean": 0.0, "std": 1.0}, 128, 256, 0.25)
    assert len(wins) == 1 and dropped == 0
    assert wins[0]["mask"].sum() == 300 and wins[0]["mask"][:212].sum() == 0 and wins[0]["X"][:212].sum() == 0


def test_build_and_save(tmp_path):
    prep.main(["--out", str(tmp_path)])
    data = np.load(tmp_path / "windows.npz", allow_pickle=False)
    meta = json.loads((tmp_path / "metadata.json").read_text())
    assert data["X"].shape[1:] == (1, 512) and data["X"].dtype == np.float32
    assert np.abs(data["X"]).max() <= prep.CLIP
    assert "S01" in meta["excluded_subjects"] and "S01" not in set(data["subject"])
    assert set(data["cohort"]) == {"healthy", "stroke_synthetic"}
    assert list(data["labels"]) == meta["labels"] and len(meta["labels"]) == 7
    assert len(data["y"]) == meta["windows"] == len(data["mask"])
