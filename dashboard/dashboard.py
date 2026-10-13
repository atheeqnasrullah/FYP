import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
GAMES = {
    "Balloon Pop": "balloon",
    "Car Driving": "car",
    "Treasure Hunt": "treasure",
    "Hand Gesture Shape Matching": "shape",
}
INPUT_MODES = {
    "Webcam only (turn camera on)": "vision",
    "Webcam + EMG sensor": "live",
    "Keyboard controls": "keyboard",
    "Simulator": "sim",
}

st.set_page_config(page_title="Rehabilitation Dashboard", layout="wide")
st.title("Stroke Rehabilitation Dashboard")
api = st.sidebar.text_input("API URL", "http://127.0.0.1:8000").rstrip("/")

try:
    patient_rows = requests.get(f"{api}/patients", timeout=3).json()
    patient_codes = [row["patient_id"] for row in patient_rows]
    api_error = None
except (requests.RequestException, ValueError) as exc:
    patient_rows = []
    patient_codes = []
    api_error = exc

st.header("Start a rehabilitation game")
with st.container(border=True):
    game_col, mode_col, patient_col = st.columns(3)
    with game_col:
        game_name = st.selectbox("Choose a game", list(GAMES), key="game_choice")
    with mode_col:
        game_slug = GAMES[game_name]
        input_options = list(INPUT_MODES)
        if game_slug == "car":
            input_options = input_options[:2]
        input_label = st.selectbox("Input method", input_options, key=f"input_mode_{game_slug}", index=0)
        if INPUT_MODES[input_label] in ("vision", "live"):
            st.caption("The webcam identifies hand gestures and movement direction; its video appears behind the game objects.")
        else:
            st.caption("Camera stays off in this mode.")
        if game_slug == "car":
            st.caption("Move your hand left/right to steer; close your hand to brake. Webcam + EMG also displays RMS/MAV activity features.")
        elif game_slug == "shape":
            st.caption("The webcam pointer and hand-close/open gestures control shape pickup and drop. Webcam + EMG also displays muscle-activity features; mouse/Space is available if the camera is off.")
        if INPUT_MODES[input_label] == "live":
            st.caption("The game window opens immediately and waits there until fresh EMG data arrives. Camera labels control actions; EMG RMS/MAV provides activity feedback.")
    with patient_col:
        if patient_codes:
            patient_id = st.selectbox("Patient code", patient_codes, key="game_patient")
        else:
            patient_id = st.text_input("Patient code", "P01", key="new_game_patient")

    start_col, stop_col = st.columns(2)
    with start_col:
        start_clicked = st.button("Start selected game", type="primary", width="stretch")
    with stop_col:
        stop_clicked = st.button("Stop running game", width="stretch")

if "game_process" not in st.session_state:
    st.session_state.game_process = None

process = st.session_state.game_process
if process is not None and process.poll() is not None:
    st.session_state.game_process = None
    process = None

if start_clicked:
    if not re.fullmatch(r"P[A-Za-z0-9_-]{1,20}", patient_id.strip()):
        st.error("Patient code must start with P and contain only letters, numbers, _ or - (up to 21 characters).")
    elif process is not None:
        st.warning("A game is already running. Stop it before starting another.")
    else:
        command = [
            sys.executable,
            "-u",
            str(ROOT / "main.py"),
            INPUT_MODES[input_label],
            "--game",
            GAMES[game_name],
            "--patient",
            patient_id.strip(),
        ]
        try:
            options = {
                "cwd": str(ROOT),
                "stdin": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                # Give SDL/Pygame an interactive Windows console/desktop session of its own.
                options["creationflags"] = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                options["start_new_session"] = True
            log_dir = ROOT / "data" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "dashboard_game.log"
            with log_path.open("w", encoding="utf-8") as log_file:
                log_file.write(f"Dashboard launch command: {subprocess.list2cmdline(command)}\n")
                log_file.flush()
                st.session_state.game_process = subprocess.Popen(command, stdout=log_file, stderr=log_file, **options)
            process = st.session_state.game_process
            st.success(f"{game_name} started in {input_label} mode. Use the game window to play; close it with Esc.")
            if INPUT_MODES[input_label] in ("vision", "live"):
                st.caption(f"If the camera does not open, check camera permissions and see `{log_path.relative_to(ROOT)}`.")
        except OSError as exc:
            st.error(f"Could not start the game. Check that pygame is installed in this environment. Details: {exc}")

if stop_clicked:
    process = st.session_state.game_process
    if process is not None and process.poll() is None:
        process.terminate()
        st.session_state.game_process = None
        st.info("Game stopped.")
    else:
        st.info("No game is currently running.")

process = st.session_state.game_process
if process is not None and process.poll() is None:
    st.caption(f"Game process running (PID {process.pid}).")

st.divider()
st.header("Progress")
if api_error:
    st.error(f"Cannot reach API at {api}. Start it with `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`. Details: {api_error}")
elif not patient_codes:
    st.info("No patient records yet. A coded patient record is created when the first game session is saved.")
else:
    pid = st.sidebar.selectbox("Progress patient", patient_codes, key="progress_patient")
    try:
        response = requests.get(f"{api}/patients/{pid}/progress", timeout=3)
        response.raise_for_status()
        data = response.json()
        sessions = data["sessions"]
        if not sessions:
            st.info("No sessions recorded yet. Start a game above; its session is saved when you close the game.")
        else:
            df = pd.DataFrame(sessions)
            a, b, c = st.columns(3)
            a.metric("Sessions", len(df))
            b.metric("Latest score", int(df.iloc[-1].total_score))
            c.metric("Latest accuracy", f"{df.iloc[-1].accuracy:.0%}")
            st.plotly_chart(px.line(df, x="started_at", y="total_score", color="game_name", markers=True, title="Score by session"), width="stretch", alt="Patient score across game sessions")
            st.plotly_chart(px.line(df, x="started_at", y="accuracy", markers=True, title="Accuracy by session"), width="stretch", alt="Patient accuracy across game sessions")
            movement = pd.DataFrame(data["movement_accuracy"])
            if not movement.empty:
                st.plotly_chart(px.bar(movement, x="target_movement", y="accuracy", title="Accuracy by target movement"), width="stretch", alt="Accuracy for each target movement")
            emg_activity = pd.DataFrame(data.get("emg_activity_by_movement", []))
            if not emg_activity.empty:
                st.plotly_chart(px.bar(emg_activity, x="movement", y=["mean_rms", "mean_mav"], barmode="group", title="EMG activity features by camera-detected movement"), width="stretch", alt="Average EMG RMS and MAV values grouped by camera-detected movement")
            st.dataframe(df, width="stretch", hide_index=True, alt="Patient rehabilitation session history")
            st.link_button("Download session and attempt CSV", f"{api}/patients/{pid}/export.csv")
    except (requests.RequestException, ValueError, KeyError) as exc:
        st.error(f"Could not load progress for {pid}. Details: {exc}")
