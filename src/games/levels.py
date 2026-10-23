"""Seven levels per game, opened one at a time.

Each level fixes the difficulty (level 1 = easiest, level 7 = hardest) and sets a
goal, such as "Pop 10 balloons". Reaching the goal before the time runs out
passes the level. Level 1 is always open; level n opens once level n-1 has been
passed and level_days_between days have gone by (default 1: one new level a
day, so a patient can finish all seven in a week; 7 gives one level a week).
Passed and open levels can be replayed at any time.

Progress is kept per patient and game in data/logs/level_progress.json.
"""
import json
import os
from datetime import date, timedelta

from src.utils.config import ROOT

LEVEL_COUNT = 7
NAMES = ("Warm-up", "Getting going", "Steady", "Building up", "Stronger", "Challenge", "Champion")
# Goal per level: how many of the game's main achievement the patient needs.
GOALS = {
    "Balloon_Pop": ((6, 8, 10, 12, 14, 16, 18), "balloons popped", "Pop {n} balloons"),
    "Car_Driving": ((4, 5, 6, 8, 10, 12, 14), "stars caught", "Catch {n} stars"),
    "Treasure_Hunt": ((2, 3, 4, 5, 6, 7, 8), "chests collected", "Collect {n} chests"),
    "Shape_Matching": ((3, 4, 6, 8, 9, 10, 12), "shapes placed", "Place {n} shapes"),
}
GAME_IDS = {"balloon": "Balloon_Pop", "car": "Car_Driving", "treasure": "Treasure_Hunt", "shape": "Shape_Matching"}


def progress_path():
    return os.environ.get("REHAB_LEVEL_PROGRESS") or str(ROOT / "data/logs/level_progress.json")


def _load_all():
    try:
        with open(progress_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def difficulty_level(level):
    """Difficulty (1.0-5.0, see difficulty.py) for a level: 1.0, 1.67, ... 5.0."""
    return 1.0 + (level - 1) * 4.0 / (LEVEL_COUNT - 1)


def goal(game, level):
    """(count, unit) the level asks for."""
    counts, unit, _ = GOALS.get(game, ((5, 6, 7, 8, 10, 12, 14), "good movements", "Make {n} good movements"))
    return counts[level - 1], unit


def goal_text(game, level):
    counts, _, text = GOALS.get(game, ((5, 6, 7, 8, 10, 12, 14), "", "Make {n} good movements"))
    return text.format(n=counts[level - 1])


def level_status(patient, game, today=None, days_between=1):
    """One dict per level: level, name, goal, state (passed / open / waiting / locked), opens_on, stars, best."""
    today = today or date.today()
    saved = _load_all().get(patient, {}).get(game, {})
    rows, previous_passed = [], None
    for level in range(1, LEVEL_COUNT + 1):
        rec = saved.get(str(level), {})
        passed_on = date.fromisoformat(rec["first_passed"]) if rec.get("first_passed") else None
        opens_on = None
        if level > 1:
            opens_on = previous_passed + timedelta(days=max(0, int(days_between))) if previous_passed else None
        if passed_on:
            state = "passed"
        elif level == 1 or (opens_on and today >= opens_on):
            state = "open"
        elif opens_on:
            state = "waiting"
        else:
            state = "locked"
        rows.append({"level": level, "name": NAMES[level - 1], "goal": goal_text(game, level), "goal_count": goal(game, level)[0],
                     "state": state, "opens_on": opens_on.isoformat() if opens_on and state == "waiting" else None,
                     "stars": int(rec.get("stars", 0)), "best": int(rec.get("best", 0)), "plays": int(rec.get("plays", 0))})
        previous_passed = passed_on
    return rows


def playable(row):
    return row["state"] in ("passed", "open")


def default_level(rows):
    """The level to offer first: the lowest open level not yet passed, else the highest playable one."""
    fresh = [r["level"] for r in rows if r["state"] == "open"]
    return fresh[0] if fresh else max(r["level"] for r in rows if playable(r))


def record_result(patient, game, level, count, passed, stars, today=None):
    """Save one play of a level; the first pass starts the wait for the next level."""
    today = today or date.today()
    data = _load_all()
    rec = data.setdefault(patient, {}).setdefault(game, {}).setdefault(str(level), {})
    rec["plays"] = int(rec.get("plays", 0)) + 1
    rec["best"] = max(int(rec.get("best", 0)), int(count))
    if passed:
        rec["passes"] = int(rec.get("passes", 0)) + 1
        rec["stars"] = max(int(rec.get("stars", 0)), int(stars))
        rec.setdefault("first_passed", today.isoformat())
    rec["last_played"] = today.isoformat()
    path = progress_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return rec


def opens_text(opens_on, today=None):
    """'tomorrow' or a short date such as 'Tue 28 Oct'."""
    today = today or date.today()
    day = date.fromisoformat(opens_on) if isinstance(opens_on, str) else opens_on
    if day <= today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    return day.strftime("%a %d %b")


def parse_level(value):
    """CLI / API level choice: 'choose' (level screen), 'free' (free play) or 1-7."""
    text = str(value).strip().lower()
    if text in ("choose", "free"):
        return text
    if text.isdigit() and 1 <= int(text) <= LEVEL_COUNT:
        return int(text)
    raise ValueError(f"Level must be choose, free or 1-{LEVEL_COUNT}, not {value!r}")
