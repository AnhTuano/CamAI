import os
import threading
import time
from datetime import datetime

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template_string
from ultralytics import YOLO


load_dotenv()

RTSP_URL = os.getenv("RTSP_URL", "")
CONFIDENCE = float(os.getenv("CONFIDENCE", "0.55"))
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
app = Flask(__name__)

state = {
    "connected": False,
    "people": 0,
    "last_frame": None,
    "last_error": "",
    "updated_at": None,
}
state_lock = threading.Lock()


PAGE = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Test camera AI</title>
  <style>
    body { font-family: sans-serif; max-width: 1000px; margin: 24px auto; padding: 0 16px; }
    img { width: 100%; background: #222; border-radius: 8px; }
    .status { margin: 12px 0; padding: 12px; background: #eee; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>Test camera Dahua + AI</h1>
  <div id="status" class="status">Đang kết nối...</div>
  <img src="/video" alt="Luồng camera">
  <script>
    async function updateStatus() {
      const response = await fetch('/status');
      const data = await response.json();
      document.getElementById('status').textContent =
        (data.connected ? 'Đã kết nối' : 'Mất kết nối') +
        ' | Người: ' + data.people +
        (data.last_error ? ' | ' + data.last_error : '');
    }
    updateStatus();
    setInterval(updateStatus, 2000);
  </script>
</body>
</html>
"""


def camera_worker() -> None:
    if not RTSP_URL:
        with state_lock:
            state["last_error"] = "Thiếu RTSP_URL trong file .env"
        return

    model = YOLO("yolo11n.pt")
    camera = None
    try:
        while True:
            if camera is None or not camera.isOpened():
                if camera is not None:
                    camera.release()
                camera = cv2.VideoCapture(RTSP_URL)
                if not camera.isOpened():
                    with state_lock:
                        state["connected"] = False
                        state["last_error"] = "Không mở được RTSP"
                    time.sleep(3)
                    continue

            success, frame = camera.read()
            if not success:
                with state_lock:
                    state["connected"] = False
                    state["last_error"] = "Không nhận được hình ảnh"
                camera.release()
                camera = None
                time.sleep(2)
                continue

            result = model.predict(frame, conf=CONFIDENCE, classes=[0], verbose=False)[0]
            people = len(result.boxes)
            annotated = result.plot()
            success, encoded = cv2.imencode(".jpg", annotated)
            if not success:
                continue
            with state_lock:
                state["connected"] = True
                state["people"] = people
                state["last_frame"] = encoded.tobytes()
                state["last_error"] = ""
                state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    finally:
        if camera is not None:
            camera.release()


def frames():
    while True:
        with state_lock:
            frame = state["last_frame"]
        if frame is not None:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        time.sleep(0.05)


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/video")
def video():
    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.get("/status")
def status():
    with state_lock:
        return jsonify(
            connected=state["connected"],
            people=state["people"],
            last_error=state["last_error"],
            updated_at=state["updated_at"],
        )


if __name__ == "__main__":
    threading.Thread(target=camera_worker, daemon=True).start()
    app.run(host=WEB_HOST, port=WEB_PORT, threaded=True)
