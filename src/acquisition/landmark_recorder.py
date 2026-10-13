import csv, sys, time
from pathlib import Path
import cv2
from src.utils.config import ROOT, load_settings

def main():
    if len(sys.argv) != 4: raise SystemExit("Usage: python src/acquisition/landmark_recorder.py SUBJECT SESSION LABEL")
    try: import mediapipe as mp
    except ImportError: raise SystemExit("Install the optional mediapipe dependency first")
    subject, session, label = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    cap = cv2.VideoCapture(load_settings()["camera_index"]); hands = mp.solutions.hands.Hands(max_num_hands=1)
    out = ROOT / "data/raw/vision" / f"{subject}_session{session}_{label}.csv"; out.parent.mkdir(parents=True, exist_ok=True)
    fields = [f"{a}{i}" for i in range(21) for a in "xyz"]
    try:
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f); writer.writerow(["frame_id", "timestamp_ms", "subject_id", "session_id", *fields, "label"])
            recording = False; frame_id = 0; start = time.monotonic()
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok: break
                frame = cv2.flip(frame, 1); result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                cv2.putText(frame, f"{label} REC={recording} SPACE toggle Q quit", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, .6, (0,255,0), 2)
                cv2.imshow("Landmark recorder", frame); key = cv2.waitKey(1) & 255
                if key == ord("q"): break
                if key == ord(" "): recording = not recording
                if recording and result.multi_hand_landmarks:
                    lm = result.multi_hand_landmarks[0].landmark
                    writer.writerow([frame_id, int((time.monotonic()-start)*1000), subject, session, *[v for p in lm for v in (p.x,p.y,p.z)], label]); frame_id += 1
    finally: cap.release(); hands.close(); cv2.destroyAllWindows()

if __name__ == "__main__": main()
