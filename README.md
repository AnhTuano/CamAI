# AI cảnh báo camera Dahua

## Cài đặt trên Windows

```powershell
cd D:\CamAI
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
py app.py
```

Trong `.env`, thay `RTSP_URL` bằng IP, tài khoản và mật khẩu camera.

URL thường dùng:

```text
rtsp://USER:PASSWORD@CAMERA_IP:554/cam/realmonitor?channel=1&subtype=0
```

`subtype=0` là luồng chính; dùng `subtype=1` nếu máy yếu. Model `yolo11n.pt`
sẽ được tải tự động ở lần chạy đầu.

## Gửi cảnh báo Zalo

Zalo cá nhân không có API bot phổ thông để nhận tin trực tiếp. Cách an toàn là
dùng Zalo Official Account hoặc webhook qua n8n/Make, sau đó điền `WEBHOOK_URL`
và tùy chọn `WEBHOOK_TOKEN`. Webhook nhận JSON gồm `event`, `count`,
`detected_at` và đường dẫn ảnh snapshot.

Không mở RTSP trực tiếp ra Internet; chỉ cho máy AI truy cập camera trong mạng
LAN hoặc dùng VPN.

## Chạy ứng dụng cửa sổ

Sau khi đã điền đúng `RTSP_URL` trong `.env`, cài thư viện và chạy:

```powershell
py -m pip install -r requirements.txt
py desktop_app.py
```

Ứng dụng sẽ mở cửa sổ xem camera, vẽ khung người, lưu snapshot và gửi webhook
khi phát hiện người. Không cần Flask hoặc trình duyệt.
