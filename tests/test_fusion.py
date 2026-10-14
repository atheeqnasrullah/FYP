from src.fusion.fusion_engine import FusionEngine


def test_low_confidence_becomes_rest():
    assert FusionEngine(smoothing_n=1, min_conf=.6).fuse(vis=("Left", .3))["command"] == "Rest"


def test_majority_smoothing_and_emg_attached():
    fusion = FusionEngine(smoothing_n=3, min_conf=.5)
    fusion.fuse(vis=("Left", .9)); fusion.fuse(vis=("Left", .9))
    out = fusion.fuse(vis=("Right", .9), emg_features={"RMS": 2.0, "MAV": 1.5})
    assert out["command"] == "Left"
    assert out["source"] == "vision+emg" and out["emg_rms"] == 2.0 and out["emg_mav"] == 1.5


def test_no_vision_is_rest_from_vision_only():
    out = FusionEngine().fuse()
    assert out["command"] == "Rest" and out["source"] == "vision"
