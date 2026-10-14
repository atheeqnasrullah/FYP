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
    monkeypatch.setattr(balloon.BalloonPop, "make_pop_sound", staticmethod(lambda: None))
    script = lambda f: "Down" if f < 70 else every(10, "Hand_Close")(f)
    game, saved = run_game(balloon.BalloonPop, script, monkeypatch, frames=180)
    assert saved["game_name"] == "Balloon_Pop" and saved["total_score"] > 0


def test_treasure_hunt_keyboard_up_down_move(monkeypatch):
    from src.games.treasure_hunt import TreasureHunt
    game, saved = run_game(TreasureHunt, lambda f: "Up" if f < 20 else every(10, "Hand_Open")(f), monkeypatch, frames=60)
    assert saved["game_name"] == "Treasure_Hunt"
    assert any(a["target_movement"] == "Hand_Open" for a in saved["attempts"])


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
