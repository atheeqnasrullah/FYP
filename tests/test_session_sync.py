import json
import src.utils.session_sync as sync


def test_sync_keeps_only_failed_sessions(tmp_path, monkeypatch):
    path = tmp_path / "pending.jsonl"
    path.write_text("\n".join([json.dumps({"patient_id": "P01"}), "not json", json.dumps({"patient_id": "FAIL"})]) + "\n")
    def fake_upload(base, payload):
        if payload["patient_id"] == "FAIL": raise ConnectionError("down")
    monkeypatch.setattr(sync, "upload_session", fake_upload)
    assert sync.sync_pending_sessions("http://x", path) == (1, 1)
    assert json.loads(path.read_text().strip())["patient_id"] == "FAIL"
    monkeypatch.setattr(sync, "upload_session", lambda base, payload: None)
    assert sync.sync_pending_sessions("http://x", path) == (1, 0) and not path.exists()


def test_sync_without_file(tmp_path):
    assert sync.sync_pending_sessions("http://x", tmp_path / "missing.jsonl") == (0, 0)
