import os
import time
import urllib.request
from pathlib import Path

import numpy as np
from src.utils.config import ROOT

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
MODEL_PATH = ROOT / "data/models/hand_landmarker.task"
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)

def _ensure_task_model():
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        return MODEL_PATH
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = MODEL_PATH.with_suffix(".task.download")
    try:
        request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "Stroke-Rehab-FYP/1.0"})
        with urllib.request.urlopen(request, timeout=45) as response, temporary.open("wb") as out:
            total = 0
            while chunk := response.read(1024 * 1024):
                out.write(chunk); total += len(chunk)
        if total <= 1_000_000:
            raise RuntimeError(f"Downloaded hand model is unexpectedly small ({total} bytes)")
        os.replace(temporary, MODEL_PATH)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Could not get the MediaPipe hand model. Check internet access and retry. Details: {exc}") from exc
    return MODEL_PATH

def _angle(a, b, c):
    ba, bc = a-b, c-b
    return np.degrees(np.arccos(np.clip(np.dot(ba,bc)/(np.linalg.norm(ba)*np.linalg.norm(bc)+1e-9),-1,1)))

class HandTracker:
    def __init__(self):
        try: import mediapipe as mp
        except ImportError as e: raise RuntimeError("Live vision requires mediapipe") from e
        self.cv2 = __import__("cv2"); self.mp = mp; self.last_timestamp = 0
        if hasattr(mp, "solutions"):
            self.backend = "solutions"
            self.hands = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=.6, min_tracking_confidence=.6)
        elif hasattr(mp, "tasks") and hasattr(mp.tasks, "vision"):
            self.backend = "tasks"
            vision = mp.tasks.vision
            options = vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(_ensure_task_model())),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=.6,
                min_hand_presence_confidence=.6,
                min_tracking_confidence=.6,
            )
            self.hands = vision.HandLandmarker.create_from_options(options)
        else:
            raise RuntimeError("Unsupported MediaPipe install: expected Solutions or Tasks HandLandmarker API")

    def process(self, frame_bgr):
        frame = self.cv2.flip(frame_bgr, 1)
        rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        if self.backend == "solutions":
            result = self.hands.process(rgb)
            if not result.multi_hand_landmarks: return None
            landmarks = result.multi_hand_landmarks[0].landmark
        else:
            timestamp = max(time.monotonic_ns() // 1_000_000, self.last_timestamp + 1)
            self.last_timestamp = timestamp
            image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
            result = self.hands.detect_for_video(image, timestamp)
            if not result.hand_landmarks: return None
            landmarks = result.hand_landmarks[0]
        return np.array([[p.x,p.y,p.z] for p in landmarks])

    def draw_landmarks(self, frame_bgr, landmarks):
        """Draw the hand skeleton over the mirrored webcam frame."""
        height, width = frame_bgr.shape[:2]
        points = [
            (max(0, min(width - 1, int(point[0] * width))),
             max(0, min(height - 1, int(point[1] * height))))
            for point in landmarks
        ]
        for start, end in HAND_CONNECTIONS:
            self.cv2.line(frame_bgr, points[start], points[end], (235, 235, 235), 2, self.cv2.LINE_AA)
        for point in points:
            self.cv2.circle(frame_bgr, point, 6, (255, 255, 255), -1, self.cv2.LINE_AA)
            self.cv2.circle(frame_bgr, point, 4, (0, 0, 255), -1, self.cv2.LINE_AA)
        return frame_bgr

    @staticmethod
    def features(lm):
        palm = np.linalg.norm(lm[0] - lm[9]) + 1e-9
        curls = [
            _angle(lm[mcp], lm[pip], lm[tip])
            for tip, pip, mcp in zip((8, 12, 16, 20), (6, 10, 14, 18), (5, 9, 13, 17))
        ]
        # Normalize fingertip reach by palm size, so the same rule works at
        # different camera distances. Count fingers using both joint angle and
        # reach; either measure alone is unreliable for rotated hands.
        reach = [
            float(np.linalg.norm(lm[tip] - lm[0]) / (np.linalg.norm(lm[mcp] - lm[0]) + 1e-9))
            for tip, mcp in zip((8, 12, 16, 20), (5, 9, 13, 17))
        ]
        extended = [angle >= 145 and distance >= 1.12 for angle, distance in zip(curls, reach)]
        fingers_closed = all(angle < 135 and distance < 1.20 for angle, distance in zip(curls, reach))
        thumb_to_palm = min(np.linalg.norm(lm[4] - lm[index]) for index in (5, 9, 13)) / palm
        full_fist = fingers_closed and thumb_to_palm < .72
        v1, v2 = lm[5] - lm[0], lm[17] - lm[0]
        return {
            "curl": curls,
            "reach": reach,
            "pinch_ratio": float(np.linalg.norm(lm[4] - lm[8]) / palm),
            "full_fist": bool(full_fist),
            "extended_count": sum(extended),
            # Palm landmarks move less than the whole-hand mean when fingers open.
            "cx": float(lm[[0, 5, 9, 13, 17], 0].mean()),
            "cy": float(lm[:, 1].mean()),
            "palm_nz": float(np.cross(v1, v2)[2]),
            "wrist_angle": float(np.degrees(np.arctan2(lm[9, 1] - lm[0, 1], lm[9, 0] - lm[0, 0]))),
            "palm": palm,
        }

    def close(self): self.hands.close()

def rule_classify(f):
    extended = f["extended_count"]
    # Thumb-to-index pinch is a deliberate pick/pop gesture even if the other
    # fingers remain extended. Normalize by palm size for different camera distances.
    if f.get("pinch_ratio", 1.0) < 0.34:
        return "Hand_Close", .92
    if extended >= 3:
        return "Hand_Open", min(.96, .78 + .06 * (extended - 3))
    if extended <= 1:
        # Avoid calling a partially curled or poorly tracked hand a firm close.
        mean_curl = float(np.mean(f["curl"]))
        mean_reach = float(np.mean(f["reach"]))
        if mean_curl < 135 and mean_reach < 1.48:
            return "Hand_Close", min(.94, .76 + max(0, 125 - mean_curl) / 100)
    return "Rest",.65
