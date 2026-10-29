import os
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2
import requests
from dotenv import load_dotenv
from PIL import Image, ImageTk
from ultralytics import YOLO


load_dotenv()

RTSP_URL = os.getenv("RTSP_URL", "")
CONFIDENCE = float(os.getenv("CONFIDENCE", "0.55"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "30"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")
SNAPSHOT_DIR = Path("snapshots")


class CameraApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CamAI - Dahua")
        self.root.geometry("960x640")
        self.stop_event = threading.Event()
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.status = "Đang khởi động..."
        self.people = 0
        self.last_notification = 0.0

        self.video = ttk.Label(root)
        self.video.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.info = ttk.Label(root, text=self.status, anchor=tk.W)
        self.info.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.camera_worker, daemon=True).start()
        self.refresh_display()

    def camera_worker(self) -> None:
        if not RTSP_URL:
            self.status = "Thiếu RTSP_URL trong file .env"
            return

        SNAPSHOT_DIR.mkdir(exist_ok=True)
        self.status = "Đang tải model YOLO..."
        model = YOLO("yolo11n.pt")
        camera = None
        try:
            while not self.stop_event.is_set():
                if camera is None or not camera.isOpened():
                    if camera is not None:
                        camera.release()
                    camera = cv2.VideoCapture(RTSP_URL)
                    if not camera.isOpened():
                        self.status = "Không mở được RTSP; thử lại sau 3 giây"
                        time.sleep(3)
                        continue

                success, frame = camera.read()
                if not success:
                    self.status = "Mất hình; đang kết nối lại..."
                    camera.release()
                    camera = None
                    time.sleep(2)
                    continue

                result = model.predict(
                    frame, conf=CONFIDENCE, classes=[0], verbose=False
                )[0]
                self.people = len(result.boxes)
                annotated = result.plot()
                now = time.time()
                if self.people and now - self.last_notification >= COOLDOWN_SECONDS:
                    snapshot = SNAPSHOT_DIR / (
                        datetime.now().strftime("person_%Y%m%d_%H%M%S.jpg")
                    )
                    if cv2.imwrite(str(snapshot), annotated):
                        self.notify(snapshot, self.people)
                    self.last_notification = now

                with self.frame_lock:
                    self.latest_frame = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                self.status = f"Đã kết nối | Phát hiện: {self.people} người"
        finally:
            if camera is not None:
                camera.release()

    def notify(self, snapshot: Path, count: int) -> None:
        if not WEBHOOK_URL:
            return
        headers = {"Content-Type": "application/json"}
        if WEBHOOK_TOKEN:
            headers["Authorization"] = f"Bearer {WEBHOOK_TOKEN}"
        payload = {
            "event": "person_detected",
            "count": count,
            "detected_at": datetime.now().astimezone().isoformat(),
            "snapshot": str(snapshot.resolve()),
        }
        try:
            response = requests.post(
                WEBHOOK_URL, json=payload, headers=headers, timeout=10
            )
            response.raise_for_status()
        except requests.RequestException as error:
            self.status = f"Gửi cảnh báo thất bại: {error}"

    def refresh_display(self) -> None:
        with self.frame_lock:
            frame = self.latest_frame
        if frame is not None:
            image = Image.fromarray(frame)
            image.thumbnail((940, 560))
            photo = ImageTk.PhotoImage(image)
            self.video.configure(image=photo)
            self.video.image = photo
        self.info.configure(text=self.status)
        if not self.stop_event.is_set():
            self.root.after(100, self.refresh_display)

    def close(self) -> None:
        self.stop_event.set()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        CameraApp(root)
        root.mainloop()
    except Exception as error:
        messagebox.showerror("CamAI", str(error))
