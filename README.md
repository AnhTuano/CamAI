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

## Mở web để test

Sau khi đã điền đúng `RTSP_URL` trong `.env`:

```powershell
py -m pip install -r requirements.txt
py web_app.py
```

Mở trình duyệt trên máy chạy server tại `http://127.0.0.1:5000`.
Trang sẽ hiển thị video có khung nhận diện người và trạng thái kết nối.

Nếu truy cập từ máy khác trong cùng LAN hoặc qua Tailscale, đặt trong `.env`:

```env
WEB_HOST=0.0.0.0
WEB_PORT=5000
```

Sau đó mở `http://IP_MAY_CHAY_SERVER:5000`. Chỉ mở cổng này trong LAN/VPN,
không mở trực tiếp ra Internet.
