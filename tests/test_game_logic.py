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


def test_levels_open_one_a_day_after_a_pass(tmp_path, monkeypatch):
    from datetime import date, timedelta
    from src.games import levels
    monkeypatch.setenv("REHAB_LEVEL_PROGRESS", str(tmp_path / "levels.json"))
    day = date(2026, 10, 20)
    rows = levels.level_status("P01", "Balloon_Pop", today=day)
    assert len(rows) == 7 and rows[0]["state"] == "open" and all(r["state"] == "locked" for r in rows[1:])
    assert rows[0]["goal"] == "Pop 6 balloons" and levels.default_level(rows) == 1
    levels.record_result("P01", "Balloon_Pop", 1, 4, False, 0, today=day)          # not passed: nothing opens
    assert levels.level_status("P01", "Balloon_Pop", today=day)[1]["state"] == "locked"
    levels.record_result("P01", "Balloon_Pop", 1, 6, True, 2, today=day)
    rows = levels.level_status("P01", "Balloon_Pop", today=day)
    assert rows[0]["state"] == "passed" and rows[0]["stars"] == 2 and rows[0]["best"] == 6
    assert rows[1]["state"] == "waiting" and rows[1]["opens_on"] == "2026-10-21"      # opens the next day
    assert levels.opens_text(rows[1]["opens_on"], today=day) == "tomorrow"
    assert levels.level_status("P01", "Balloon_Pop", today=day + timedelta(days=1))[1]["state"] == "open"
    assert levels.level_status("P01", "Balloon_Pop", today=day, days_between=0)[1]["state"] == "open"
    assert levels.level_status("P01", "Balloon_Pop", today=day + timedelta(days=1), days_between=7)[1]["state"] == "waiting"
    assert levels.level_status("P01", "Car_Driving", today=day)[1]["state"] == "locked"   # each game separately
    assert levels.level_status("P02", "Balloon_Pop", today=day)[0]["state"] == "open"     # each patient separately


def test_level_difficulty_and_parsing():
    import pytest
    from src.games import levels
    from src.games.difficulty import Difficulty
    assert levels.difficulty_level(1) == 1.0 and levels.difficulty_level(7) == 5.0
    fixed = Difficulty("auto", "P01", "T", level=levels.difficulty_level(4))
    assert fixed.level == 3.0 and fixed.mode == "level"
    for _ in range(12): fixed.record(True)
    assert fixed.level == 3.0                      # a level never adapts during play
    assert levels.parse_level("3") == 3 and levels.parse_level("Free") == "free" and levels.parse_level("choose") == "choose"
    with pytest.raises(ValueError): levels.parse_level("8")
