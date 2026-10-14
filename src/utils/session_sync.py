"""Upload sessions that games saved to data/logs/pending_sessions.jsonl while the API was down."""
import json
from src.utils.config import ROOT

PENDING = ROOT / "data/logs/pending_sessions.jsonl"


def upload_session(base, payload, timeout=3):
    import requests
    patients = requests.get(f"{base}/patients", timeout=timeout); patients.raise_for_status()
    if payload["patient_id"] not in [p["patient_id"] for p in patients.json()]:
        requests.post(f"{base}/patients", json={"patient_id": payload["patient_id"]}, timeout=timeout).raise_for_status()
    response = requests.post(f"{base}/sessions", json=payload, timeout=timeout); response.raise_for_status()
    return response.json()


def sync_pending_sessions(base, path=PENDING):
    """Upload queued sessions; keep only the ones that still fail. Returns (uploaded, remaining)."""
    if not path.exists(): return 0, 0
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    failed, uploaded = [], 0
    for line in lines:
        try: payload = json.loads(line)
        except ValueError: continue  # unreadable line: drop it rather than retry forever
        try: upload_session(base, payload); uploaded += 1
        except Exception: failed.append(line)
    if failed: path.write_text("\n".join(failed) + "\n", encoding="utf-8")
    else: path.unlink()
    return uploaded, len(failed)
