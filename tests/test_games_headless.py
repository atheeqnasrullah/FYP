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
