# User App Manual Snapshot Integration Guide

Mục tiêu: thêm một nút để user chụp snapshot thủ công từ camera hiện tại mà không cần chờ alert.
Mặc định API này cũng sẽ thử gửi ảnh đó sang Telegram cho user.

## Backend API đã có sẵn

- Method: `POST`
- URL: `/api/cameras/:cameraId/snapshot`
- Query/body tùy chọn:
  - `mode=processed` hoặc `mode=raw`
  - `send_telegram=true|false`
  - `telegram_chat_id` nếu muốn chỉ định chat id đích trực tiếp

Ví dụ:

```http
POST /api/cameras/1/snapshot?mode=processed&send_telegram=true
```

Hoặc:

```json
{
  "mode": "raw",
  "send_telegram": true
}
```

## Ý nghĩa mode

- `processed`: ảnh hiện tại có overlay zone, bbox, label
- `raw`: ảnh gốc từ camera, không overlay

## Response mẫu

```json
{
  "status": "success",
  "camera_id": 1,
  "snapshot": {
    "mode": "processed",
    "filename": "manual_snapshot_cam1_processed_20260519_153000.jpg",
    "image_path": "static/manual_snapshots/manual_snapshot_cam1_processed_20260519_153000.jpg",
    "image_url": "http://192.168.1.10:5000/static/manual_snapshots/manual_snapshot_cam1_processed_20260519_153000.jpg",
    "image_urls": [
      "http://192.168.1.10:5000/static/manual_snapshots/manual_snapshot_cam1_processed_20260519_153000.jpg"
    ],
    "captured_at": "2026-05-19T08:30:00+00:00"
  },
  "telegram": {
    "sent": true,
    "chat_id": "6333686779"
  }
}
```

## Error cases

- `400`: mode không hợp lệ
- `503`: chưa có frame camera để chụp
- `500`: lỗi nội bộ khi ghi file

Lưu ý:
- Snapshot vẫn có thể chụp thành công dù Telegram gửi thất bại
- Khi đó `telegram.sent = false` và `telegram.reason` sẽ cho biết lý do

## Hướng tích hợp cho user app

1. Thêm một nút `Capture Snapshot` ở màn hình xem camera.
2. Khi user bấm nút, gọi API:
   - `POST ${BACKEND_BASE_URL}/api/cameras/${cameraId}/snapshot?mode=processed&send_telegram=true`
3. Nếu thành công:
   - lấy `snapshot.image_url`
   - hiển thị preview
   - cho phép user mở full ảnh hoặc lưu local nếu app có chức năng đó
   - nếu `telegram.sent === true`, hiển thị thông báo "Snapshot sent to Telegram"
   - nếu `telegram.sent === false`, vẫn giữ snapshot preview và báo lý do gửi Telegram thất bại
4. Nếu lỗi:
   - hiển thị toast/dialog với `message` từ response

## Prompt gợi ý cho AI ở user app

```text
Bạn đang chỉnh sửa user app để thêm chức năng chụp snapshot thủ công từ camera backend.

Yêu cầu:
1. Thêm một action/button "Capture Snapshot" ở màn hình camera hoặc camera detail.
2. Khi bấm nút, gọi API:
   POST {BACKEND_BASE_URL}/api/cameras/{cameraId}/snapshot?mode=processed&send_telegram=true
3. Parse response JSON theo cấu trúc:
   {
     status,
     camera_id,
     snapshot: {
       mode,
       filename,
       image_path,
       image_url,
       image_urls,
       captured_at
     },
     telegram: {
       sent,
       chat_id?,
       reason?
     }
   }
4. Nếu thành công:
   - hiển thị ảnh snapshot mới chụp
   - hiển thị thời gian chụp
   - lưu snapshot mới nhất vào state hiện tại
   - nếu `telegram.sent` là true, hiện success toast
   - nếu `telegram.sent` là false, vẫn coi snapshot thành công nhưng hiện warning toast về Telegram
5. Nếu lỗi:
   - hiển thị thông báo lỗi thân thiện cho user
6. Không làm ảnh hưởng luồng realtime alert, video feed, hoặc socket hiện có.

Ưu tiên:
- tái sử dụng service layer / API client hiện có
- code đơn giản, dễ maintain
- loading state rõ ràng khi đang chụp
- xử lý trường hợp backend trả 503 khi camera chưa có frame
```

## Ghi chú

- Nếu user app muốn ảnh không có overlay, đổi `mode=raw`
- Nếu muốn gửi đến đúng Telegram của user đang đăng nhập, backend sẽ thử lấy `telegram_chat_id` từ bảng `users`
- Nếu không có `telegram_chat_id` trong DB, backend sẽ fallback sang biến môi trường `TELEGRAM_CHAT_ID`
- Nếu muốn lưu lịch sử snapshot thủ công trong tương lai, có thể thêm bảng DB riêng sau
