"""Hardware endpoints for the web app: find the ESP32 EMG board and the webcam,
check that they deliver data, stream them live to the browser, and choose
which serial port / camera index the games use (config/settings.yaml).

Only one user of each device at a time: a check or stream holds the device
lock, a new stream asks the previous one to stop, and launching a game calls
release_all() so the game can open the port and camera itself.
"""
import asyncio, base64, json, queue, re, sys, threading, time

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.utils.config import ROOT, load_settings

router = APIRouter(prefix="/hardware")

SETTINGS = ROOT / "config/settings.yaml"
# USB-to-UART bridges used on ESP32 dev boards, plus Espressif's native USB.
ESP32_VIDS = {0x10C4: "Silicon Labs CP210x", 0x1A86: "WCH CH340/CH9102", 0x0403: "FTDI", 0x303A: "Espressif USB"}
PORT_RE = re.compile(r"^(COM\d{1,3}|/dev/[\w./-]{1,60})$")
STREAM_LIMIT_S = 600   # live streams close themselves after 10 minutes
CHART_HZ = 200         # live EMG is thinned to this rate for the browser


class _Device:
    """Lock plus a generation counter so a new user can ask the current one to stop."""
    def __init__(self):
        self.lock = threading.Lock()
        self.generation = 0

    def acquire(self, timeout=3.0) -> int:
        self.generation += 1  # asks any running stream to finish
        if not self.lock.acquire(timeout=timeout):
            raise HTTPException(409, "The device is busy with another check. Try again in a moment.")
        return self.generation

    def wanted(self, generation: int) -> bool:
        return self.generation == generation


EMG, CAMERA = _Device(), _Device()


def release_all(timeout=3.0):
    """Stop browser streams and wait until both devices are closed (called before a game starts)."""
    for device in (EMG, CAMERA):
        device.generation += 1
        if device.lock.acquire(timeout=timeout):
            device.lock.release()


def _game_using(device: str):
    from backend.webapi import _status
    status = _status()
    mode = (status.get("last") or {}).get("mode")
    if not status["running"]:
        return None
    if device == "emg" and mode == "live":
        return status["last"]
    if device == "camera" and mode in ("vision", "live", "replay"):
        return status["last"]
    return None


def _refuse_if_game(device: str):
    game = _game_using(device)
    if game:
        what = "EMG sensor" if device == "emg" else "webcam"
        raise HTTPException(409, f"The {what} is in use by the running game ({game['game_name']}). Stop the game to test it here.")


# ---------------------------------------------------------------- settings
def _set_setting(key: str, value: str):
    """Replace one top-level key in settings.yaml, keeping the rest of the file and its comments."""
    text = SETTINGS.read_text(encoding="utf-8")
    pattern = re.compile(rf"^({re.escape(key)}:[ \t]*)([^#\n]*?)([ \t]*#.*)?$", re.M)
    if pattern.search(text):
        text = pattern.sub(lambda m: m.group(1) + value + (m.group(3) or ""), text, count=1)
    else:
        text = text.rstrip("\n") + f"\n{key}: {value}\n"
    SETTINGS.write_text(text, encoding="utf-8")


class HardwareConfig(BaseModel):
    serial_port: str | None = None
    camera_index: int | None = Field(default=None, ge=0, le=9)


@router.put("/config")
def save_config(body: HardwareConfig):
    if body.serial_port is not None:
        if not PORT_RE.match(body.serial_port):
            raise HTTPException(400, "Serial port must look like COM3 or /dev/ttyUSB0")
        _set_setting("serial_port", f'"{body.serial_port}"')
    if body.camera_index is not None:
        _set_setting("camera_index", str(body.camera_index))
    return ports()


# ---------------------------------------------------------------- serial ports
@router.get("/ports")
def ports():
    from serial.tools import list_ports
    cfg = load_settings()
    configured = str(cfg.get("serial_port", ""))
    found = []
    for p in sorted(list_ports.comports(), key=lambda p: p.device):
        chip = ESP32_VIDS.get(p.vid) if p.vid is not None else None
        found.append({"device": p.device, "description": p.description, "manufacturer": p.manufacturer,
                      "chip": chip, "likely_esp32": chip is not None})
    present = any(p["device"].lower() == configured.lower() for p in found)
    suggestion = None
    if not present:
        suggestion = next((p["device"] for p in found if p["likely_esp32"]), None)
    return {"configured_port": configured, "configured_present": present, "suggested_port": suggestion,
            "baud_rate": int(cfg.get("baud_rate", 921600)), "fs": int(cfg.get("fs", 1000)),
            "camera_index": int(cfg.get("camera_index", 0)), "ports": found,
            "game_using_emg": bool(_game_using("emg")), "game_using_camera": bool(_game_using("camera"))}


# ---------------------------------------------------------------- EMG
def _open_serial(port: str, baud: int):
    import serial
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = port, baud, 0.1
    # Keep DTR/RTS released so opening the port does not reset the ESP32.
    s.dtr = False
    s.rts = False
    try:
        s.open()
    except serial.SerialException as exc:
        text = str(exc)
        if "PermissionError" in text or "Access is denied" in text or "busy" in text.lower():
            raise HTTPException(409, f"{port} is open in another program (Arduino Serial Monitor, a logger or a game). Close it and try again.")
        if "FileNotFoundError" in text or "could not open port" in text or "No such file" in text:
            raise HTTPException(404, f"{port} was not found. Plug in the ESP32 or pick another port.")
        raise HTTPException(500, f"Could not open {port}: {text}")
    s.reset_input_buffer()
    return s


class _Parser:
    """Turns the ESP32 byte stream into samples, keeping '#' status lines and counting junk."""
    def __init__(self):
        self.tail = b""
        self.first = True  # the first line after opening may be cut in half
        self.bytes = 0
        self.bad = 0
        self.bad_examples: list[str] = []
        self.messages: list[str] = []

    def feed(self, chunk: bytes):
        self.bytes += len(chunk)
        lines = (self.tail + chunk).split(b"\n")
        self.tail = lines.pop()
        ts, values = [], []
        for raw in lines:
            if self.first:
                self.first = False
                continue
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            if line.startswith("#"):
                self.messages = (self.messages + [line[1:].strip()])[-6:]
                continue
            parts = line.split(",")
            try:
                t, v = int(parts[0]), int(parts[1])
                if len(parts) != 2 or not 0 <= v <= 4095:
                    raise ValueError
            except (ValueError, IndexError):
                self.bad += 1
                if len(self.bad_examples) < 3:
                    self.bad_examples.append(line[:60])
                continue
            ts.append(t); values.append(v)
        return ts, values


def _assess(parser: _Parser, ts: list, values: list, fs: int, port: str, baud: int):
    """Plain-language verdict on a stretch of EMG data."""
    n = len(values)
    rate = round((n - 1) * 1000 / (ts[-1] - ts[0])) if n > 1 and ts[-1] > ts[0] else None
    out = {"port": port, "baud_rate": baud, "expected_hz": fs, "samples": n, "bytes": parser.bytes, "rate_hz": rate,
           "bad_lines": parser.bad, "bad_examples": parser.bad_examples, "messages": parser.messages,
           "min": int(min(values)) if n else None, "max": int(max(values)) if n else None,
           "mean": round(float(np.mean(values)), 1) if n else None, "warnings": []}
    if parser.bytes == 0:
        out.update(status="no_data", message=f"{port} opened, but the board sent nothing. Check that the EMG sketch is flashed, then press EN/RESET on the ESP32.")
    elif n == 0 and parser.messages:
        out.update(status="no_data", message="The board is running but no EMG samples arrived, only status messages.")
    elif n == 0:
        out.update(status="wrong_format", message=f"Data arrived but not as 'timestamp,value' lines. Check that the sketch's baud rate matches {baud}.")
    else:
        out.update(status="streaming", message=f"EMG sensor connected: {n} samples received.")
        if rate and rate < 0.8 * fs:
            out["warnings"].append(f"The board sends about {rate} Hz but settings expect {fs} Hz. Flash the 1000 Hz sketch or change fs.")
        if out["max"] == 0:
            out["warnings"].append("The signal is stuck at 0. Check the sensor's power, ground and SIG wire on GPIO34.")
        elif out["min"] >= 4095:
            out["warnings"].append("The signal is stuck at 4095 (saturated). Check the sensor ground and output.")
        elif out["max"] - out["min"] < 8:
            out["warnings"].append("The signal is almost flat. Check the electrodes, or ask the patient to contract the muscle.")
        if parser.bad > max(5, n // 50):
            out["warnings"].append(f"{parser.bad} malformed lines. Check the cable, or try a lower baud rate.")
    return out


def _thin(values: list, every: int) -> list:
    return values[::every] if every > 1 else values


def _resolve_port(port: str | None) -> tuple[str, int, int]:
    cfg = load_settings()
    port = port or str(cfg.get("serial_port", ""))
    if not PORT_RE.match(port):
        raise HTTPException(400, "Serial port must look like COM3 or /dev/ttyUSB0")
    return port, int(cfg.get("baud_rate", 921600)), int(cfg.get("fs", 1000))


@router.get("/emg/check")
def emg_check(port: str | None = None, seconds: float = Query(1.5, ge=0.5, le=5)):
    """Open the port for a moment and report whether valid EMG samples arrive."""
    _refuse_if_game("emg")
    port, baud, fs = _resolve_port(port)
    EMG.acquire()
    try:
        s = _open_serial(port, baud)
        parser, ts, values = _Parser(), [], []
        try:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                t, v = parser.feed(s.read(max(1, s.in_waiting)))
                ts += t; values += v
        finally:
            s.close()
    finally:
        EMG.lock.release()
    out = _assess(parser, ts, values, fs, port, baud)
    out["signal"] = _thin(values, max(1, len(values) // 600))
    return out


def _sse(event: str, data) -> str:
    return (f"event: {event}\n" if event != "samples" else "") + f"data: {json.dumps(data)}\n\n"


async def _drain(worker, *args):
    """Run a device worker in its own thread and yield what it produces.

    The worker owns the device from open to close. This generator never awaits
    device I/O, so when the client disconnects (and the stream task is cancelled)
    the finally only sets a flag and the worker closes the device itself.
    """
    out, stop = queue.Queue(maxsize=50), threading.Event()
    pulled = [time.monotonic()]
    threading.Thread(target=worker, args=(*args, out, stop, pulled), daemon=True).start()
    try:
        while True:
            try:
                item = out.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.03)
                continue
            pulled[0] = time.monotonic()
            if item is None:  # worker finished and released the device
                return
            yield item
    finally:
        stop.set()


def _put(out: queue.Queue, item):
    """Queue an item, dropping the oldest one if the browser is not keeping up."""
    try:
        out.put_nowait(item)
    except queue.Full:
        try:
            out.get_nowait()
        except queue.Empty:
            pass
        out.put_nowait(item)


def _alive(device: _Device, generation: int, stop: threading.Event, pulled: list, started: float) -> bool:
    now = time.monotonic()
    return (not stop.is_set() and device.wanted(generation) and now - started < STREAM_LIMIT_S
            and now - pulled[0] < 5)  # nobody reading for 5 s: the page is gone


def _emg_worker(port, baud, fs, every, out, stop, pulled):
    try:
        generation = EMG.acquire()
    except HTTPException as exc:
        _put(out, _sse("failure", {"message": exc.detail})); _put(out, None); return
    try:
        try:
            s = _open_serial(port, baud)
        except HTTPException as exc:
            _put(out, _sse("failure", {"message": exc.detail})); return
        try:
            _put(out, _sse("ready", {"port": port, "baud_rate": baud, "expected_hz": fs, "chart_hz": fs / every}))
            parser, window_ts, window_v, batch = _Parser(), [], [], []
            started = last_report = last_batch = time.monotonic()
            while _alive(EMG, generation, stop, pulled, started):
                t, v = parser.feed(s.read(max(1, s.in_waiting)))
                window_ts += t; window_v += v; batch += v
                now = time.monotonic()
                if now - last_batch >= 0.1:
                    _put(out, _sse("samples", {"samples": _thin(batch, every)}))
                    batch, last_batch = [], now
                if now - last_report >= 1.0:
                    _put(out, _sse("status", _assess(parser, window_ts, window_v, fs, port, baud)))
                    window_ts, window_v, last_report = [], [], now
                    parser.bytes = parser.bad = 0
                    parser.bad_examples = []
            _put(out, _sse("end", {}))
        except Exception as exc:  # unplugged mid-stream, etc.
            _put(out, _sse("failure", {"message": f"Lost connection to {port}: {exc}"}))
        finally:
            s.close()
    finally:
        EMG.lock.release()
        _put(out, None)


@router.get("/emg/stream")
def emg_stream(port: str | None = None):
    """Server-sent events: a batch of thinned samples every ~100 ms plus a verdict every second."""
    _refuse_if_game("emg")
    port, baud, fs = _resolve_port(port)
    every = max(1, round(fs / CHART_HZ))
    return StreamingResponse(_drain(_emg_worker, port, baud, fs, every), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- webcam
def _open_camera(index: int):
    import cv2
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap, cap.getBackendName()
        cap.release()
    raise HTTPException(404, f"No webcam at index {index}. Check that it is plugged in, that no other app (Zoom, Teams, Camera) is using it, and that camera access is allowed in Windows privacy settings.")


def _jpeg(frame, width=640, quality=75) -> bytes:
    import cv2
    h, w = frame.shape[:2]
    if w > width:
        frame = cv2.resize(frame, (width, round(h * width / w)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()


@router.get("/camera/check")
def camera_check(index: int | None = Query(None, ge=0, le=9)):
    """Open the webcam, grab a frame and return it as a snapshot."""
    _refuse_if_game("camera")
    index = int(load_settings().get("camera_index", 0)) if index is None else index
    CAMERA.acquire()
    try:
        cap, backend = _open_camera(index)
        try:
            frame = None
            for _ in range(8):  # the first frames are often black while exposure settles
                ok, f = cap.read()
                if ok:
                    frame = f
            if frame is None:
                raise HTTPException(500, f"The webcam at index {index} opened but returned no picture. Another app may be using it.")
            h, w = frame.shape[:2]
            brightness = float(frame.mean())
        finally:
            cap.release()
    finally:
        CAMERA.lock.release()
    return {"status": "ok", "index": index, "backend": backend, "width": w, "height": h,
            "dark": brightness < 15, "image": "data:image/jpeg;base64," + base64.b64encode(_jpeg(frame)).decode()}


def _camera_worker(index, out, stop, pulled):
    # On failure the stream just ends; the page then calls /camera/check to show the reason.
    try:
        generation = CAMERA.acquire()
    except HTTPException:
        _put(out, None); return
    try:
        try:
            cap, _ = _open_camera(index)
        except HTTPException:
            return
        try:
            started = time.monotonic()
            while _alive(CAMERA, generation, stop, pulled, started):
                ok, frame = cap.read()
                if not ok:
                    break
                data = _jpeg(frame)
                _put(out, b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
        finally:
            cap.release()
    finally:
        CAMERA.lock.release()
        _put(out, None)


@router.get("/camera/stream")
def camera_stream(index: int | None = Query(None, ge=0, le=9)):
    """Live MJPEG preview for an <img> tag. Closes when the page goes away or another user needs the camera."""
    _refuse_if_game("camera")
    index = int(load_settings().get("camera_index", 0)) if index is None else index
    return StreamingResponse(_drain(_camera_worker, index), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-cache"})
