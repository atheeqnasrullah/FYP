"""Difficulty levels shared by all games.

A level runs from 1.0 (easiest) to 5.0 (hardest). Fixed presets keep the level
constant; "auto" adapts it from the patient's recent accuracy and remembers the
last level per patient and game, so the next session starts where this one ended.
"""
import json
import os
from collections import deque

from src.utils.config import ROOT

PRESETS = {"easy": 1.5, "medium": 3.0, "hard": 4.5}
MODES = ("auto", *PRESETS)
MIN_LEVEL, MAX_LEVEL, STEP = 1.0, 5.0, 0.5
WINDOW = 6          # attempts considered when adapting
MIN_BETWEEN = 4     # attempts that must pass between two level changes
RAISE_AT, LOWER_AT = 0.8, 0.4


def state_path():
    return os.environ.get("REHAB_GAME_STATE") or str(ROOT / "data/logs/game_levels.json")


def _load_state():
    try:
        with open(state_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class Difficulty:
    def __init__(self, mode="auto", patient="P01", game="Game", level=None):
        """level fixes the difficulty for a game level (see levels.py); it never adapts or saves."""
        self.mode = "level" if level is not None else mode if mode in MODES else "auto"
        self.patient, self.game = patient, game
        if self.mode == "level":
            pass
        elif self.mode == "auto":
            saved = _load_state().get(patient, {}).get(game)
            level = saved if isinstance(saved, (int, float)) else PRESETS["medium"]
        else:
            level = PRESETS[self.mode]
        self.level = self.start_level = float(min(MAX_LEVEL, max(MIN_LEVEL, level)))
        self.recent = deque(maxlen=WINDOW)
        self.since_change = 0

    @property
    def t(self):
        """Level mapped to 0..1 for interpolating game parameters."""
        return (self.level - MIN_LEVEL) / (MAX_LEVEL - MIN_LEVEL)

    def value(self, easy, hard):
        """Interpolate a game parameter between its easiest and hardest value."""
        return easy + (hard - easy) * self.t

    def record(self, success):
        """Record one outcome. Returns +1/-1 when the level changed, else 0."""
        self.recent.append(bool(success))
        self.since_change += 1
        if self.mode != "auto" or len(self.recent) < MIN_BETWEEN or self.since_change < MIN_BETWEEN:
            return 0
        rate = sum(self.recent) / len(self.recent)
        change = 1 if rate >= RAISE_AT and self.level < MAX_LEVEL else -1 if rate <= LOWER_AT and self.level > MIN_LEVEL else 0
        if change:
            self.level = min(MAX_LEVEL, max(MIN_LEVEL, self.level + change * STEP))
            self.recent.clear()
            self.since_change = 0
        return change

    def label(self):
        names = ((2.0, "Easy"), (3.5, "Medium"), (MAX_LEVEL, "Hard"))
        name = next(n for limit, n in names if self.level <= limit)
        return f"{name} {self.level:.1f}" + (" (auto)" if self.mode == "auto" else "")

    def save(self):
        if self.mode != "auto":
            return
        data = _load_state()
        data.setdefault(self.patient, {})[self.game] = self.level
        try:
            os.makedirs(os.path.dirname(state_path()), exist_ok=True)
            with open(state_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass
