import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# Games: skip the start/results screens (they wait for a key press) and keep the
# adaptive difficulty levels written by tests out of data/logs.
os.environ.setdefault("REHAB_SKIP_SCREENS", "1")
import tempfile
_state = tempfile.mkdtemp(prefix="rehab_test_")
os.environ.setdefault("REHAB_GAME_STATE", os.path.join(_state, "game_levels.json"))
os.environ.setdefault("REHAB_EMG_CALIBRATION", os.path.join(_state, "emg_calibration.json"))
