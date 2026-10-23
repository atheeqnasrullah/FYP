"""Run each game for a few frames on SDL's dummy video driver with scripted input."""
import queue
import pytest
import src.games.game_engine as engine


def run_game(game_cls, script, monkeypatch, mode="keyboard", frames=60):
    saved = {}
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: saved.update(payload))
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = game_cls(queue.Queue(), "P01")
    game.control_mode = mode
    original = game.read_input
    state = {"frame": 0}
    def scripted():
        original()
        frame = state["frame"]; state["frame"] += 1
        game.cmd = script(frame)
        if frame >= frames: game.running = False
    game.read_input = scripted
    game.run()
    return game, saved


def every(n, command):
    return lambda frame: command if frame % n < n // 2 else "Rest"


def test_car_driving_logs_steering(monkeypatch):
    from src.games.car_driving import CarDriving
    game, saved = run_game(CarDriving, lambda f: ["Left", "Rest", "Right", "Rest"][(f // 15) % 4], monkeypatch, frames=90)
    assert saved["game_name"] == "Car_Driving" and saved["patient_id"] == "P01"
    assert {a["detected_movement"] for a in saved["attempts"]} <= {"Left", "Right"} and saved["attempts"]


def test_balloon_pop_keyboard_can_pop(monkeypatch):
    import src.games.balloon_pop as balloon
    monkeypatch.setattr(balloon.random, "randint", lambda a, b: (a + b) // 2)
    script = lambda f: "Down" if f < 70 else every(10, "Hand_Close")(f)
    game, saved = run_game(balloon.BalloonPop, script, monkeypatch, frames=180)
    assert saved["game_name"] == "Balloon_Pop" and saved["total_score"] > 0


def test_treasure_hunt_following_prompts_collects_chests(monkeypatch):
    import random
    from src.games.treasure_hunt import TreasureHunt
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: saved.update(payload))
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    saved = {}
    game = TreasureHunt(queue.Queue(), "P01")
    game.rng = random.Random(7)
    original = game.read_input
    frame = {"n": 0}
    def follow_prompt():
        # Perform whatever the prompt asks, releasing between gestures like a patient would.
        original()
        n = frame["n"]; frame["n"] += 1
        game.cmd = game.target if n % 8 < 4 and game.phase != "cleared" else "Rest"
        if n >= 900 or game.islands >= 1: game.running = False
    game.read_input = follow_prompt
    game.run()
    assert saved["game_name"] == "Treasure_Hunt" and game.islands == 1
    targets = {a["target_movement"] for a in saved["attempts"]}
    assert {"Hand_Open", "Hand_Close"} <= targets and targets & {"Left", "Right", "Up", "Down"}
    assert all(a["correct"] for a in saved["attempts"])


def test_treasure_hunt_blocked_move_counts_as_incorrect(monkeypatch):
    from src.games.treasure_hunt import TreasureHunt
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: None)
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = TreasureHunt(queue.Queue(), "P01")
    game.islands = 0; game.coins = []; game.move_started = game.bump_until = game.settle_until = 0
    game.player = (0, 0); game.obstacles = {(1, 0): "rock"}; game.chests = {(4, 4): "closed"}
    game.set_explore_target()
    game.handle("Right", 1000)
    assert game.player == (0, 0) and game.attempts[-1]["correct"] is False
    import pygame; pygame.quit()


def test_shape_matching_round_scores(monkeypatch):
    from src.games.shape_matching import ShapeMatching
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: None)
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = ShapeMatching(queue.Queue(), "P01")
    names, targets, homes = game.new_round(1)
    assert 3 <= len(names) <= 6 and set(targets) == set(names) == set(homes)
    assert len(set(targets.values())) == len(names)
    import pygame; pygame.quit()


def test_time_limit_ends_session(monkeypatch):
    from src.games.car_driving import CarDriving
    saved = {}
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: saved.update(payload))
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = CarDriving(queue.Queue(), "P01")
    game.session_seconds = 0.5
    game.run()
    assert game.time_up and saved["duration_s"] <= 2


def test_shape_matching_runs(monkeypatch):
    from src.games.shape_matching import ShapeMatching
    game, saved = run_game(ShapeMatching, lambda f: "Rest", monkeypatch, frames=20)
    assert saved["game_name"] == "Shape_Matching" and saved["duration_s"] >= 0


def test_latency_recorded_from_vision_commands(monkeypatch):
    import time
    from src.games.car_driving import CarDriving
    bus = queue.Queue()
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: None)
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = CarDriving(bus, "P01")
    bus.put({"command": "Left", "confidence": .9, "vision_ts_ms": time.time() * 1000 - 50})
    game.read_input()
    assert game.latencies and 45 <= game.latencies[0][1] < 1000
    import pygame; pygame.quit()


def test_car_hand_position_picks_lane(monkeypatch):
    from src.games.car_driving import CarDriving
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: None)
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = CarDriving(queue.Queue(), "P01")
    left, right = game.zone_edges()
    assert game.zone_lane(left - 0.05, 1) == 0 and game.zone_lane(right + 0.05, 1) == 2
    assert game.zone_lane(0.5, 0) == 1 and game.zone_lane(0.5, 2) == 1
    # Inside the dead band next to an edge the car keeps its lane instead of flickering.
    assert game.zone_lane(left, 0) == 0 and game.zone_lane(left, 1) == 1
    import pygame; pygame.quit()


def test_car_vision_mode_follows_hand(monkeypatch):
    from src.games.car_driving import CarDriving
    from src.realtime import pipeline
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: None)
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = CarDriving(queue.Queue(), "P01")
    game.control_mode = "vision"
    seen = []
    original = game.read_input
    state = {"n": 0}
    def hand_left_then_right():
        original()
        n = state["n"]; state["n"] += 1
        with pipeline.lock:
            pipeline.latest["pointer"] = (0.1, 0.5) if n < 20 else (0.9, 0.5)
            pipeline.latest["vis"] = ("Hand_Open", 0.9)
        seen.append(game.lane)
        if n >= 40: game.running = False
    game.read_input = hand_left_then_right
    try:
        game.run()
    finally:
        with pipeline.lock:
            pipeline.latest["pointer"] = None; pipeline.latest["vis"] = None
    assert 0 in seen[5:20] and seen[-1] == 2


def test_shape_matching_pick_and_drop_by_hand(monkeypatch):
    from src.games.shape_matching import ShapeMatching
    from src.realtime import pipeline
    saved = {}
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: saved.update(payload))
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = ShapeMatching(queue.Queue(), "P01")
    game.control_mode = "vision"
    layout = (["Circle", "Square", "Triangle"],
              {"Circle": (230, 200), "Square": (450, 200), "Triangle": (670, 200)},
              {"Circle": (260, 480), "Square": (450, 480), "Triangle": (640, 480)})
    monkeypatch.setattr(game, "new_round", lambda round_no: layout)
    gain = game.reach_gain()
    to_camera = lambda x, y: ((x / game.W - .5) / gain + .5, (y / game.H - .5) / gain + .5)
    # Square to the circle hole (wrong), then square to its own hole (right).
    plan = [((450, 480), False)] * 8 + [((450, 480), True)] * 6 + [((230, 200), True)] * 12 + [((230, 200), False)] * 20 \
         + [((450, 480), False)] * 6 + [((450, 480), True)] * 6 + [((450, 200), True)] * 12 + [((450, 200), False)] * 10
    original = game.read_input
    state = {"n": 0}
    def scripted():
        original()
        n = state["n"]; state["n"] += 1
        (x, y), fist = plan[min(n, len(plan) - 1)]
        with pipeline.lock:
            pipeline.latest["pointer"] = to_camera(x, y)
            pipeline.latest["vis"] = ("Hand_Close" if fist else "Hand_Open", .9)
        if n >= len(plan): game.running = False
    game.read_input = scripted
    try:
        game.run()
    finally:
        with pipeline.lock:
            pipeline.latest["pointer"] = None; pipeline.latest["vis"] = None
    results = [(a["target_movement"], a["detected_movement"], a["correct"]) for a in saved["attempts"]]
    assert results == [("Square", "Wrong hole (Circle)", False), ("Square", "Square", True)]
    assert saved["total_score"] == 10


def test_treasure_hunt_hand_joystick_needs_return_to_centre():
    from src.games.treasure_hunt import TreasureHunt
    game = TreasureHunt(queue.Queue(), "P01")
    reach = game.joystick_radius()
    assert game.joystick((0.5, 0.5)) is None
    assert game.joystick((0.5 - reach - 0.05, 0.5)) == "Left"
    # Holding the hand out, or swinging it back through the centre, does not step again.
    assert game.joystick((0.5 - reach - 0.08, 0.5)) is None
    assert game.joystick((0.5 + reach * 0.4, 0.5)) is None
    assert game.joystick((0.5, 0.5)) is None
    assert game.joystick((0.5, 0.5 + (reach + 0.05) / 0.75)) == "Down"
    import pygame; pygame.quit()


def test_balloon_pop_shows_what_triggered_it(monkeypatch):
    import src.games.balloon_pop as balloon
    monkeypatch.setattr(balloon.random, "randint", lambda a, b: (a + b) // 2)
    shown = []
    original = engine.BaseGame.action_card
    monkeypatch.setattr(engine.BaseGame, "action_card", lambda self, *a, **k: (shown.append(a), original(self, *a, **k)))
    script = lambda f: "Down" if f < 70 else every(10, "Hand_Close")(f)
    game, saved = run_game(balloon.BalloonPop, script, monkeypatch, frames=180)
    pops = [a for a in saved["attempts"] if a["correct"]]
    assert pops and all(a["input_source"] == "Keyboard" and a["emg_activity_pct"] is None for a in pops)
    assert shown and shown[0][0] in ("Balloon popped!", "Golden balloon popped!")


def test_input_feedback_reports_source_gesture_and_relative_activity(monkeypatch):
    from src.games.car_driving import CarDriving
    game = CarDriving(queue.Queue(), "P01")
    game.control_mode = "live"; game.emg_source = "replay"
    game.cmd, game.confidence = "Hand_Close", 0.9
    game.emg_rms = 400.0; first = game.input_snapshot()
    game.emg_rms = 200.0; second = game.input_snapshot()
    assert first["source"] == "Camera + EMG replay" and first["gesture"] == "Close hand"
    assert first["activity"] == 100 and second["activity"] == 50       # relative to the session's strongest
    assert engine.activity_level(80) == "High" and engine.activity_level(50) == "Medium" and engine.activity_level(10) == "Low"
    game.emg_rms = 0.0
    assert game.input_snapshot()["activity"] is None                   # no EMG reading -> no activity shown
    game.action_card("Steered left", (300, 400), True)
    game.draw_input_strip(); game.draw_action_cards()                  # draws without errors
    assert game.cards and game.cards[0]["title"] == "Steered left"
    import pygame; pygame.quit()


def run_live_balloon(monkeypatch, rms, effort=50, frames=200):
    """Balloon Pop in Webcam + EMG mode: hand still at the centre, fist closing and opening, a fixed EMG RMS."""
    import src.games.balloon_pop as balloon
    import src.realtime.pipeline as pipeline
    monkeypatch.setattr(balloon.random, "randint", lambda a, b: (a + b) // 2)
    monkeypatch.setattr(pipeline, "emg_is_ready", lambda now=None: True)
    monkeypatch.setattr(engine, "load_calibration", lambda patient: {"rest_rms": 100.0, "max_rms": 1100.0})
    for key, value in {"pointer": (0.5, 0.5), "emg_features": {"RMS": rms, "MAV": rms}, "fist": False}.items():
        monkeypatch.setitem(pipeline.latest, key, value)
    def script(frame):
        pipeline.latest["fist"] = frame % 20 < 10
        return "Rest"
    saved = {}
    monkeypatch.setattr(engine, "upload_session", lambda base, payload: saved.update(payload))
    monkeypatch.setattr(engine, "sync_pending_sessions", lambda base: (0, 0))
    game = balloon.BalloonPop(queue.Queue(), "P01")
    game.control_mode = "live"; game.effort_setting = effort
    original = game.read_input
    state = {"frame": 0}
    def scripted():
        original()
        frame = state["frame"]; state["frame"] += 1
        game.cmd = script(frame)
        if frame >= frames: game.running = False
    game.read_input = scripted
    game.run()
    return saved


def test_live_balloon_weak_grip_does_not_pop(monkeypatch):
    # RMS 300 with rest 100 and strongest 1100 is 20% effort, below the 50% required.
    saved = run_live_balloon(monkeypatch, rms=300.0)
    assert not any(a["correct"] for a in saved["attempts"]) and saved["total_score"] == 0
    weak = [a for a in saved["attempts"] if a["detected_movement"] == "Weak_Grip"]
    assert weak and all(a["effort_ok"] is False and a["effort_required_pct"] == 50 and a["emg_activity_pct"] == 20 for a in weak)


def test_live_balloon_strong_grip_pops(monkeypatch):
    # RMS 900 is 80% effort, above the 50% required.
    saved = run_live_balloon(monkeypatch, rms=900.0)
    pops = [a for a in saved["attempts"] if a["correct"]]
    assert pops and all(a["effort_ok"] is True and a["emg_activity_pct"] == 80 for a in pops)
    assert not any(a["detected_movement"] == "Weak_Grip" for a in saved["attempts"])


def test_effort_threshold_off_lets_any_grip_pop(monkeypatch):
    saved = run_live_balloon(monkeypatch, rms=300.0, effort=0)
    assert any(a["correct"] for a in saved["attempts"])
    assert all(a["effort_ok"] is None for a in saved["attempts"])


def test_grip_fires_once_per_fist_and_only_when_strong_enough():
    from src.games.car_driving import CarDriving
    game = CarDriving(queue.Queue(), "P01")
    game.control_mode = "live"; game.effort_setting = 40
    game.calibration = {"rest_rms": 0.0, "max_rms": 1000.0}
    game.emg_rms = 200.0
    assert game.grip(True) is None                      # 20%: not yet
    game.emg_rms = 450.0
    assert game.grip(True) == "fire"                    # 45%: fires once
    assert game.grip(True) is None                      # still the same fist
    assert game.grip(False) is None                     # opened after firing: not weak
    game.emg_rms = 300.0
    game.grip(True)
    assert game.grip(False) == "weak" and game.weak_grip["best"] == 30
    assert game.grip(True, ready=False) is None and game.grip(False) is None   # nothing to act on: neither
    game.control_mode = "vision"; game.emg_rms = 0.0
    assert game.grip(True) == "fire"                    # no EMG in vision mode: the camera fist is enough
    import pygame; pygame.quit()


def test_calibration_and_required_effort(tmp_path, monkeypatch):
    from src.games import effort
    from src.games.difficulty import Difficulty
    assert effort.calibrate([100, 110, 90], [900, 1000, 1100, 950]) == (100.0, pytest.approx(1070.0))
    assert effort.calibrate([500, 500], [505, 510]) is None             # no real squeeze
    assert effort.effort_pct(600, 100, 1100) == 50 and effort.effort_pct(50, 100, 1100) == 0 and effort.effort_pct(2000, 100, 1100) == 100
    assert effort.parse_required("auto") == "auto" and effort.parse_required("35%") == 35
    with pytest.raises(ValueError): effort.parse_required(150)
    easy, hard = Difficulty("easy", "P01", "T"), Difficulty("hard", "P01", "T")
    assert effort.required_effort("auto", easy) < effort.required_effort("auto", hard) and effort.required_effort(30, hard) == 30
    monkeypatch.setenv("REHAB_EMG_CALIBRATION", str(tmp_path / "cal.json"))
    assert effort.load_calibration("P07") is None
    effort.save_calibration("P07", 120, 980, "sensor")
    assert effort.load_calibration("P07")["max_rms"] == 980 and effort.load_calibration("P08") is None


def test_replay_calibration_uses_the_recordings_rest_and_fist():
    from src.realtime.emg_replay import replay_calibration
    rest, peak = replay_calibration("healthy", "S02")
    assert 0 < rest < peak


def test_level_ends_when_goal_reached_and_opens_next_level_tomorrow(monkeypatch):
    import src.games.balloon_pop as balloon
    from src.games import levels
    monkeypatch.setattr(balloon.random, "randint", lambda a, b: (a + b) // 2)
    original_init = balloon.BalloonPop.__init__
    def level_one(self, *a, **k):
        original_init(self, *a, **k); self.level_request = 1; self.session_seconds = 0
    monkeypatch.setattr(balloon.BalloonPop, "__init__", level_one)
    script = lambda f: "Down" if f < 70 else every(10, "Hand_Close")(f)
    game, saved = run_game(balloon.BalloonPop, script, monkeypatch, frames=2000)
    assert game.level == 1 and game.level_goal == 6 and game.difficulty.level == 1.0
    assert saved["level"] == 1 and saved["level_passed"] is True
    assert sum(a["correct"] for a in saved["attempts"]) == 6                 # stopped soon after the goal
    rows = levels.level_status("P01", "Balloon_Pop")
    assert rows[0]["state"] == "passed" and rows[1]["state"] == "waiting"
    assert game.level_message()[0] == "Level 1 complete!" and "tomorrow" in game.level_message()[1]


def test_level_panel_picks_with_keys_and_refuses_locked_levels(monkeypatch, tmp_path):
    import pygame
    from datetime import date, timedelta
    from src.games import levels
    from src.games.car_driving import CarDriving
    monkeypatch.setenv("REHAB_LEVEL_PROGRESS", str(tmp_path / "levels.json"))
    levels.record_result("P01", "Car_Driving", 1, 4, True, 3, today=date.today() - timedelta(days=1))
    game = CarDriving(queue.Queue(), "P01")
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert game.level_select_screen() == 2                                      # level 2 opened today: offered first
    for key in (pygame.K_5, pygame.K_RETURN, pygame.K_f, pygame.K_RETURN):      # 5 is locked, then free play
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    assert game.level_select_screen() == "free"
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert game.level_select_screen() is None and not game.running
    pygame.quit()
