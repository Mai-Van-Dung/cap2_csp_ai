# User App Alert History Guide

Tài liệu này mô tả cách để user app lấy được lịch sử cảnh báo từ backend Node.js của project `cap2_csp_ai_app`.

## 1. Endpoint đúng

User app phải gọi API lịch sử cảnh báo qua:

- `GET /alerts`
- `PATCH /alerts/:id/resolve`

Không gọi nhầm sang Flask backend ở port `5000` nếu mục tiêu là dữ liệu lịch sử của user app.

## 2. API client phải ưu tiên Node backend

Trong `frontend/src/services/api.js`, hàm `alertsAPI.getAll()` hiện dùng:

```js
getAll: () => request("/alerts", "GET", null, true),
```

Đây là đúng, nhưng hàm `request()` phải resolve base URL về Node backend có route `/alerts`, thường là port `5003` hoặc endpoint được discover từ `connection-info`.

Checklist:

- `getApiBaseCandidates()` phải trả về Node API base trước Python/Flask base khi gọi `alertsAPI`.
- Nếu đã discover được Flask base ở `5000`, không được map nó làm base chính cho `/alerts` vì Flask project này không phải nguồn dữ liệu của user app.
- Nếu app web chạy trên `localhost:8081`, vẫn phải cho phép origin đó ở backend Node.

## 3. Backend Node phải trả dữ liệu đúng quyền

Route lấy alerts trong backend Node hiện dùng bảo vệ JWT:

- `router.get("/", protect, getAlerts)`

Điều đó có nghĩa là token phải có trong `AsyncStorage` với một trong các key:

- `token`
- `authToken`
- `accessToken`

Nếu không có token hợp lệ, API sẽ trả `401` và user app phải chuyển về màn đăng nhập.

## 4. User phải có quyền camera

Query alerts ở backend Node chỉ lấy alert của camera mà user có trong bảng `user_camera_access`:

```sql
FROM alerts a
JOIN cameras c ON a.camera_id = c.id
JOIN user_camera_access uca ON uca.camera_id = c.id
WHERE uca.user_id = ?
```

Vì vậy, nếu UI chỉ hiện "Không có cảnh báo nào được ghi nhận" thì có 3 khả năng phổ biến:

- User chưa được cấp quyền xem camera nào.
- DB chưa có alert cho camera mà user được cấp quyền.
- Token đang thuộc user khác không có mapping tới camera đó.

## 5. CORS cho web

Nếu chạy trên web, backend Node phải cho phép origin của app, ví dụ:

- `http://localhost:8081`
- `http://127.0.0.1:8081`

Nếu preflight bị chặn, cần đảm bảo backend trả đủ:

- `Access-Control-Allow-Origin`
- `Access-Control-Allow-Headers: Authorization, Content-Type`
- `Access-Control-Allow-Methods: GET, POST, PATCH, OPTIONS`

## 6. Socket và alerts history là hai luồng khác nhau

`AlertsScreen` dùng hai nguồn dữ liệu khác nhau:

- `alertsAPI.getAll()` để tải lịch sử cảnh báo
- Socket.IO để nhận alert realtime `new_alert`

Nếu realtime chạy mà lịch sử vẫn trống, lỗi thường nằm ở:

- API history trỏ sai base URL
- user không có quyền truy vấn lịch sử
- DB không có bản ghi alerts tương ứng

## 7. Cấu hình khuyến nghị cho user app

Để tránh nhầm endpoint Flask và Node, nên set các biến môi trường sau cho user app:

- `EXPO_PUBLIC_BACKEND_URL` hoặc `VITE_BACKEND_BASE_URL` trỏ tới Node API
- `EXPO_PUBLIC_SOCKET_BASE_URL` hoặc `VITE_SOCKET_BASE_URL` trỏ tới Node socket relay
- `EXPO_PUBLIC_ALERTS_API_URL` nếu muốn cố định endpoint alerts

Ví dụ:

```env
EXPO_PUBLIC_BACKEND_URL=http://192.168.1.10:5003
EXPO_PUBLIC_SOCKET_BASE_URL=http://192.168.1.10:5003
EXPO_PUBLIC_ALERTS_API_URL=http://192.168.1.10:5003/alerts
```

## 8. Debug nhanh

1. Đăng nhập lại để chắc chắn token còn hợp lệ.
2. Gọi thử `GET /alerts` bằng token của user hiện tại.
3. Kiểm tra user đó có record trong `user_camera_access`.
4. Kiểm tra bảng `alerts` có dữ liệu cho camera đó.
5. Nếu chạy web, kiểm tra backend Node đã bật CORS cho origin đang dùng.

## 9. Kết luận

Nếu user app chỉ hiển thị empty state như ảnh, nguyên nhân thường không phải do màn `AlertsScreen` tự nó lỗi, mà là một trong ba điểm sau:

- base URL đang trỏ sai backend
- token không đúng user
- user không có quyền camera nên query trả rỗng

Tài liệu này có thể dùng làm checklist để chỉnh lại project user app mà không cần đụng vào Flask project.
