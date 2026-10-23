import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REHAB_DB", str(tmp_path / "test.db"))
    import backend.app as app_module
    app_module = importlib.reload(app_module)
    return TestClient(app_module.app)


ATTEMPT = {"target_movement": "Left", "detected_movement": "Left", "vision_label": "Left", "correct": True,
           "reaction_time_ms": 420, "emg_rms": 12.5, "emg_mav": 9.1, "confidence": .92}


def test_health_and_patient_validation(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/patients", json={"patient_id": "bad id"}).status_code == 422
    assert client.post("/patients", json={"patient_id": "P01"}).status_code == 200
    assert client.post("/patients", json={"patient_id": "P01"}).status_code == 409


def test_session_progress_and_export(client):
    client.post("/patients", json={"patient_id": "P02"})
    wrong = {**ATTEMPT, "detected_movement": "Right", "correct": False}
    r = client.post("/sessions", json={"patient_id": "P02", "game_name": "Car_Driving", "total_score": 10, "duration_s": 30, "attempts": [ATTEMPT, wrong]})
    assert r.status_code == 200 and r.json()["accuracy"] == .5
    progress = client.get("/patients/P02/progress").json()
    assert len(progress["sessions"]) == 1
    assert progress["emg_activity_by_movement"][0]["movement"] == "Left"
    export = client.get("/patients/P02/export.csv")
    assert export.status_code == 200 and "target_movement" in export.text.splitlines()[0]


def test_incremental_session_flow(client):
    client.post("/patients", json={"patient_id": "P03"})
    sid = client.post("/sessions/start", json={"patient_id": "P03", "game_name": "Balloon_Pop"}).json()["session_id"]
    assert client.post(f"/sessions/{sid}/attempts", json={"attempts": [ATTEMPT]}).json()["uploaded"] == 1
    assert client.patch(f"/sessions/{sid}", json={"total_score": 10, "duration_s": 5}).json()["status"] == "closed"
    assert client.patch(f"/sessions/{sid}", json={"total_score": 10, "duration_s": 5}).status_code == 409
    assert client.post(f"/sessions/{sid}/attempts", json={"attempts": [ATTEMPT]}).status_code == 409
    assert len(client.get(f"/sessions/{sid}/attempts").json()) == 1


def test_unknown_patient_rejected(client):
    assert client.post("/sessions", json={"patient_id": "P99", "game_name": "x", "total_score": 0, "duration_s": 0}).status_code == 404
    assert client.get("/patients/P99/progress").status_code == 404


def test_web_launcher_offers_emg_replay(client):
    info = client.get("/games").json()
    assert "replay" in info["modes"]
    assert all("replay" in game["modes"] for game in info["games"])


def test_grip_effort_is_stored_and_exported(client):
    client.post("/patients", json={"patient_id": "P04"})
    weak = {**ATTEMPT, "target_movement": "Hand_Close", "detected_movement": "Weak_Grip", "correct": False,
            "input_source": "Camera + EMG sensor", "emg_activity_pct": 22.0, "effort_required_pct": 45.0, "effort_ok": False}
    sid = client.post("/sessions", json={"patient_id": "P04", "game_name": "Balloon_Pop", "total_score": 0, "duration_s": 5, "attempts": [weak, ATTEMPT]}).json()["session_id"]
    rows = client.get(f"/sessions/{sid}/attempts").json()
    assert rows[0]["effort_required_pct"] == 45 and rows[0]["effort_ok"] == 0 and rows[0]["input_source"] == "Camera + EMG sensor"
    assert rows[1]["effort_ok"] is None                        # not a grip action
    assert "effort_required_pct" in client.get("/patients/P04/export.csv").text.splitlines()[0]


def test_web_launcher_rejects_bad_effort(client):
    r = client.post("/games/launch", json={"game": "balloon", "mode": "live", "patient_id": "P01", "effort": "150"})
    assert r.status_code == 400 and "0 to 100" in r.json()["detail"]
