"""Difficulty adaptation and session summaries used by the games."""
import json

from src.games.difficulty import Difficulty
from src.games.summary import stars, summarize


def test_fixed_presets_do_not_adapt():
    d = Difficulty("easy", "P01", "Game")
    for _ in range(12): d.record(True)
    assert d.level == 1.5 and d.value(0, 100) == 12.5


def test_auto_level_rises_and_falls():
    d = Difficulty("auto", "PX1", "Game")
    start = d.level
    changes = [d.record(True) for _ in range(4)]
    assert changes[-1] == 1 and d.level == start + 0.5
    changes = [d.record(False) for _ in range(4)]
    assert changes[-1] == -1 and d.level == start


def test_auto_level_is_remembered_per_patient(tmp_path, monkeypatch):
    monkeypatch.setenv("REHAB_GAME_STATE", str(tmp_path / "levels.json"))
    d = Difficulty("auto", "P07", "Balloon_Pop")
    for _ in range(8): d.record(True)
    d.save()
    assert json.loads((tmp_path / "levels.json").read_text())["P07"]["Balloon_Pop"] == d.level
    assert Difficulty("auto", "P07", "Balloon_Pop").level == d.level
    assert Difficulty("auto", "P08", "Balloon_Pop").level == 3.0


def test_summary_counts_streaks_and_movements():
    attempts = [
        {"target_movement": "Left", "correct": True, "reaction_time_ms": 800},
        {"target_movement": "Left", "correct": True, "reaction_time_ms": 1200},
        {"target_movement": "Hand_Open", "correct": False, "reaction_time_ms": 3000},
        {"target_movement": "Hand_Open", "correct": True, "reaction_time_ms": 1000},
    ]
    s = summarize(attempts)
    assert s["correct"] == 3 and s["best_streak"] == 2 and s["accuracy"] == 0.75
    assert s["avg_reaction_ms"] == 1000 and s["movements"]["Hand_Open"] == {"correct": 1, "total": 2}
    assert stars(s) == 2 and stars(summarize([])) == 0
