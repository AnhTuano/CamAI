import os
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2
import requests
from dotenv import load_dotenv
from ultralytics import YOLO


load_dotenv()

RTSP_URL = os.getenv("RTSP_URL", "")
CONFIDENCE = float(os.getenv("CONFIDENCE", "0.55"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "30"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")
SNAPSHOT_DIR = Path("snapshots")


def notify(snapshot_path: Path, count: int) -> None:
    """Send an event to a configured Zalo-compatible webhook."""
    if not WEBHOOK_URL:
        print("WEBHOOK_URL chưa được cấu hình; bỏ qua gửi thông báo.")
        return

    payload = {
        "event": "person_detected",
        "count": count,
        "detected_at": datetime.now().astimezone().isoformat(),
        "snapshot": str(snapshot_path.resolve()),
    }
    headers = {"Content-Type": "application/json"}
    if WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {WEBHOOK_TOKEN}"

    try:
        response = requests.post(
            WEBHOOK_URL, json=payload, headers=headers, timeout=10
        )
        response.raise_for_status()
        print("Đã gửi cảnh báo.")
    except requests.RequestException as error:
        print(f"Gửi cảnh báo thất bại: {error}")


def main() -> None:
    if not RTSP_URL:
        raise SystemExit(
            "Thiếu RTSP_URL. Hãy sao chép .env.example thành .env và điền thông tin camera."
        )

    SNAPSHOT_DIR.mkdir(exist_ok=True)
    print("Đang tải model YOLO...")
    model = YOLO("yolo11n.pt")
    camera = cv2.VideoCapture(RTSP_URL)
    if not camera.isOpened():
        raise SystemExit(
            "Không mở được RTSP. Kiểm tra IP, tài khoản, mật khẩu và camera cùng mạng LAN."
        )

    last_notification = 0.0
    print("Đã kết nối camera. Nhấn Ctrl+C để dừng.")
    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Mất khung hình, đang kết nối lại...")
                camera.release()
                time.sleep(3)
                camera = cv2.VideoCapture(RTSP_URL)
                continue

            result = model.predict(frame, conf=CONFIDENCE, classes=[0], verbose=False)[0]
            person_count = len(result.boxes)
            now = time.time()
            if person_count and now - last_notification >= COOLDOWN_SECONDS:
                annotated = result.plot()
                snapshot_path = SNAPSHOT_DIR / (
                    datetime.now().strftime("person_%Y%m%d_%H%M%S.jpg")
                )
                if not cv2.imwrite(str(snapshot_path), annotated):
                    print(f"Không lưu được ảnh: {snapshot_path}")
                    continue
                print(f"Phát hiện {person_count} người: {snapshot_path}")
                notify(snapshot_path, person_count)
                last_notification = now
    except KeyboardInterrupt:
        print("\nĐã dừng.")
    finally:
        camera.release()


if __name__ == "__main__":
    main()
