# Camera Disconnect Alert Sync (Python -> Node -> Telegram -> User App)

Tài liệu này hướng dẫn đồng bộ tính năng mới: cảnh báo khi camera bị mất kết nối sau khi đang hoạt động ổn định.

Luồng chuẩn:

1. Python backend phát hiện camera offline sau giai đoạn online ổn định.
2. Python gửi relay payload tới Node project qua `POST /api/alerts/notify`.
3. Node project gửi Telegram cho user, đồng thời có thể emit realtime event cho user app.
4. User app hiển thị trạng thái camera mất kết nối.

## 1) Những gì đã được thêm ở Python backend (project này)

File chính: `backend/camera_service.py`

- Theo dõi trạng thái online ổn định bằng `CAMERA_ONLINE_STABLE_SECONDS`.
- Chỉ gửi cảnh báo khi camera chuyển từ trạng thái ổn định sang offline.
- Chống spam bằng `CAMERA_DISCONNECT_ALERT_COOLDOWN_SECONDS`.
- Có thể bật/tắt bằng `CAMERA_DISCONNECT_ALERT_ENABLED`.

File relay: `backend/alert_service.py`

- Thêm `notify_camera_disconnect(...)` để gửi payload sang Node relay.

## 2) Payload contract mới gửi sang Node

Python sẽ gửi payload dạng:

```json
{
  "object_type": "CAMERA_OFFLINE",
  "camera_name": "Camera 1",
  "confidence": 1.0,
  "image_path": null,
  "image_url": null,
  "image_urls": [],
  "secret": "your_internal_secret",
  "message": "🚨 CAMERA DISCONNECTED: Camera 1. Reason: Lost camera frame, reconnecting...",
  "source": "python-backend-camera-health",
  "event_type": "camera_disconnect",
  "camera_id": 1,
  "status": "offline",
  "reason": "Lost camera frame, reconnecting...",
  "created_at": "2026-05-08T10:10:10.000Z"
}
```

## 3) Node project cần hỗ trợ gì

Trong Node `alertsController.receiveAlert` (project user app), cần:

1. Chấp nhận payload không có image.
2. Ưu tiên `message` nếu `object_type === "CAMERA_OFFLINE"`.
3. Gửi Telegram text-only khi không có ảnh.
4. Emit realtime event cho app với `event_type: "camera_disconnect"`.

Gợi ý xử lý:

```js
const isCameraDisconnect =
  object_type === "CAMERA_OFFLINE" || event_type === "camera_disconnect";

const socketPayload = {
  object_type: object_type || "unknown",
  camera_name: camera_name || "Camera",
  confidence: confidence ?? null,
  message: message || null,
  created_at: new Date().toISOString(),
  source: source || "python-backend",
  event_type: isCameraDisconnect ? "camera_disconnect" : "intrusion",
  status: status || (isCameraDisconnect ? "offline" : null),
  reason: reason || null,
};
```

## 4) AI user app project khác cần làm gì

### 4.1 Realtime

Trong màn Alerts (hoặc Notification center), khi nhận socket event `new_alert`:

- Nếu `payload.event_type === "camera_disconnect"` hoặc `payload.object_type === "CAMERA_OFFLINE"`:
  - Hiển thị thẻ cảnh báo hạ tầng (không yêu cầu ảnh).
  - Nhấn mạnh camera name + reason + timestamp.

### 4.2 History API

Nếu muốn camera disconnect có trong lịch sử lâu dài:

1. Node backend tạo bảng event infra (hoặc reuse alerts table có cột type).
2. Lưu event offline vào DB khi nhận payload trên.
3. Mở rộng API `GET /alerts` để trả cả intrusion + disconnect event.

Nếu chưa cần lưu DB, user app vẫn nhận realtime qua socket + Telegram.

## 5) Environment variables

### Python backend `.env`

```env
CAMERA_DISCONNECT_ALERT_ENABLED=true
CAMERA_ONLINE_STABLE_SECONDS=20
CAMERA_DISCONNECT_ALERT_COOLDOWN_SECONDS=180

ALERT_NOTIFY_URL=http://localhost:5003
NODE_BACKEND_URL=http://localhost:5003
INTERNAL_SECRET=your_internal_secret
```

### Node project `.env`

```env
INTERNAL_SECRET=your_internal_secret
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

`INTERNAL_SECRET` phải giống nhau giữa Python và Node.

## 6) Kiểm thử nhanh

1. Chạy Python backend + Node relay.
2. Đảm bảo camera vào trạng thái online ổn định (> `CAMERA_ONLINE_STABLE_SECONDS`).
3. Ngắt camera hoặc sai RTSP tạm thời.
4. Kiểm tra log Python có dòng dispatch camera disconnect alert.
5. Kiểm tra Node nhận `object_type=CAMERA_OFFLINE`.
6. Kiểm tra Telegram nhận message offline.

## 7) Lưu ý vận hành

- Tính năng chỉ bắn alert sau khi camera đã online ổn định để tránh false positive lúc boot.
- Cooldown ngăn spam khi camera chập chờn.
- Với môi trường nhiều camera, mở rộng camera_id động trước khi scale sản xuất.
