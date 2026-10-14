import time
from src.realtime import pipeline


def test_replay_makes_emg_ready_and_fusion_carries_features():
    pipeline.start(use_emg=True, use_vision=False, emg_source="replay")
    try:
        deadline = time.monotonic() + 5
        while not pipeline.emg_is_ready() and time.monotonic() < deadline:
            time.sleep(.05)
        assert pipeline.emg_is_ready()
        with pipeline.lock:
            features = dict(pipeline.latest["emg_features"])
        assert features["RMS"] > 0
        cmd = None
        while cmd is None or not cmd["emg_features"]:
            cmd = pipeline.command_bus.get(timeout=2)
        assert cmd["source"] == "vision+emg" and cmd["command"] == "Rest" and cmd["vision_ts_ms"] is None
    finally:
        pipeline.shutdown(); time.sleep(.2)
