import os
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
MODEL_LOCK = threading.Lock()


def channel_url(base_url: str, rtsp_channel: int) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["channel"] = str(rtsp_channel)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


class CameraPanel:
    def __init__(self, parent: tk.Widget, display_channel: int) -> None:
        self.display_channel = display_channel
        self.rtsp_channel = display_channel + 1
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.status = "Đang khởi động..."
        self.people = 0
        self.last_notification = 0.0
        self.stop_event = threading.Event()

        container = ttk.Frame(parent)
        container.grid_propagate(False)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        self.container = container
        ttk.Label(
            container, text=f"Kênh {display_channel}", font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(4, 0))
        self.video = ttk.Label(container, anchor=tk.CENTER)
        self.video.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.info = ttk.Label(container, text=self.status, anchor=tk.W)
        self.info.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 4))

    def start(self, model: YOLO) -> None:
        threading.Thread(
            target=self.camera_worker, args=(model,), daemon=True
        ).start()

    def camera_worker(self, model: YOLO) -> None:
        if not RTSP_URL:
            self.status = "Thiếu RTSP_URL trong .env"
            return

        SNAPSHOT_DIR.mkdir(exist_ok=True)
        url = channel_url(RTSP_URL, self.rtsp_channel)
        camera = None
        try:
            while not self.stop_event.is_set():
                if camera is None or not camera.isOpened():
                    if camera is not None:
                        camera.release()
                    camera = cv2.VideoCapture(url)
                    if not camera.isOpened():
                        self.status = "Không kết nối được; thử lại sau 3 giây"
                        time.sleep(3)
                        continue

                success, frame = camera.read()
                if not success:
                    self.status = "Mất hình; đang kết nối lại..."
                    camera.release()
                    camera = None
                    time.sleep(2)
                    continue

                with MODEL_LOCK:
                    result = model.predict(
                        frame, conf=CONFIDENCE, classes=[0], verbose=False
                    )[0]
                self.people = len(result.boxes)
                annotated = result.plot()
                now = time.time()
                if self.people and now - self.last_notification >= COOLDOWN_SECONDS:
                    snapshot = SNAPSHOT_DIR / (
                        datetime.now().strftime(
                            f"channel_{self.display_channel}_%Y%m%d_%H%M%S.jpg"
                        )
                    )
                    if cv2.imwrite(str(snapshot), annotated):
                        self.notify(snapshot, self.people)
                    self.last_notification = now

                with self.frame_lock:
                    self.latest_frame = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                self.status = f"Đã kết nối | Người: {self.people}"
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
            "channel": self.display_channel,
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

    def refresh(self) -> None:
        with self.frame_lock:
            frame = self.latest_frame
        if frame is not None:
            image = Image.fromarray(frame)
            image.thumbnail((600, 340))
            photo = ImageTk.PhotoImage(image)
            self.video.configure(image=photo)
            self.video.image = photo
        self.info.configure(text=self.status)

    def stop(self) -> None:
        self.stop_event.set()


class CameraApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CamAI - Dahua 4 kênh")
        self.root.geometry("1280x820")
        self.panels = []
        self.model = None

        grid = ttk.Frame(root)
        grid.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for column in range(2):
            grid.columnconfigure(column, weight=1)
        for row in range(2):
            grid.rowconfigure(row, weight=1)

        for display_channel in range(4):
            panel = CameraPanel(grid, display_channel)
            panel.container.grid(
                row=display_channel // 2,
                column=display_channel % 2,
                sticky="nsew",
                padx=4,
                pady=4,
            )
            self.panels.append(panel)

        self.status = ttk.Label(root, text="Đang tải model YOLO...")
        self.status.pack(fill=tk.X, padx=12, pady=(0, 8))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.start_cameras, daemon=True).start()
        self.refresh_display()

    def start_cameras(self) -> None:
        try:
            self.model = YOLO("yolo11n.pt")
            for panel in self.panels:
                panel.start(self.model)
            self.root.after(0, lambda: self.status.configure(text="Đang chạy 4 kênh"))
        except Exception as error:
            self.root.after(
                0, lambda: self.status.configure(text=f"Lỗi tải model: {error}")
            )

    def refresh_display(self) -> None:
        for panel in self.panels:
            panel.refresh()
        if any(not panel.stop_event.is_set() for panel in self.panels):
            self.root.after(100, self.refresh_display)

    def close(self) -> None:
        for panel in self.panels:
            panel.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        CameraApp(root)
        root.mainloop()
    except Exception as error:
        messagebox.showerror("CamAI", str(error))
