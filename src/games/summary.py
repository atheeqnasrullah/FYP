"""Session results shown on the end-of-game screen."""
from collections import OrderedDict

FRIENDLY = {
    "Hand_Close": "Close hand",
    "Hand_Open": "Open hand",
    "Left": "Move left",
    "Right": "Move right",
    "Up": "Move up",
    "Down": "Move down",
    "Supination": "Turn palm up",
    "Pronation": "Turn palm down",
    "Rest": "Rest",
    "Weak_Grip": "Grip too weak",
}


def friendly(label):
    return FRIENDLY.get(label, str(label).replace("_", " "))


def summarize(attempts):
    correct = [a for a in attempts if a.get("correct")]
    streak = best = 0
    for a in attempts:
        streak = streak + 1 if a.get("correct") else 0
        best = max(best, streak)
    movements = OrderedDict()
    for a in attempts:
        m = movements.setdefault(a.get("target_movement"), {"correct": 0, "total": 0})
        m["total"] += 1
        m["correct"] += 1 if a.get("correct") else 0
    times = [a["reaction_time_ms"] for a in correct if a.get("reaction_time_ms") is not None]
    return {
        "attempts": len(attempts),
        "correct": len(correct),
        "accuracy": len(correct) / len(attempts) if attempts else 0.0,
        "best_streak": best,
        "avg_reaction_ms": sum(times) / len(times) if times else None,
        "movements": movements,
    }


def stars(summary):
    if not summary["attempts"]:
        return 0
    acc = summary["accuracy"]
    return 3 if acc >= 0.8 else 2 if acc >= 0.5 else 1


def encouragement(summary):
    count = stars(summary)
    if count == 0:
        return "No movements recorded this time. Let's try again!"
    return {3: "Excellent work! Keep it up.", 2: "Good effort! You're making progress.", 1: "Well done for practising. Every rep counts."}[count]
