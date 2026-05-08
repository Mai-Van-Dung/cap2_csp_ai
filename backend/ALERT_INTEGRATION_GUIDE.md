# Alert Integration Guide - Web Admin & User App Sync

Hướng dẫn toàn bộ kiến trúc cảnh báo để user app đồng bộ và nhận cảnh báo realtime từ web admin.

---

## 1. Kiến Trúc Hệ Thống

```
┌─────────────────────┐
│  Python Backend     │
│  (Flask + YOLO)     │
│  Port: 5000         │
│  IP: 192.168.1.10   │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │ Hai luồng   │
    └──────┬──────┘
           │
    ┌──────┴─────────────────┐
    │                        │
    ▼                        ▼
┌─────────────────┐   ┌──────────────────┐
│ Web Admin       │   │ User App Alert   │
│ (React)         │   │ (Relay Node)     │
│ Port: 5173      │   │ Port: 5003       │
│ IP: 192.168.1.X │   │ IP: 192.168.1.10 │
└─────────────────┘   └──────────┬───────┘
                                 │
                        ┌────────┴────────┐
                        │                 │
                        ▼                 ▼
                   Socket.IO        Telegram Bot
                   (Realtime)       (Notification)
                        │
                        ▼
                  User App Mobile
                  (React Native)
```

---

## 2. Các Port & URL Hiện Tại

### 2.1 Python Backend (Flask)

- **Host**: `0.0.0.0` (listen all interfaces)
- **Port**: `5000`
- **URL Công Khai**: `http://192.168.1.10:5000`
- **Localhost**: `http://127.0.0.1:5000`

**Endpoints quan trọng:**

```
GET  /api/connection-info              → Lấy dynamic base URL
GET  /video_feed                       → Stream video
GET  /api/alerts                       → Lịch sử alert
POST /api/alerts/notify                → Nhận alert từ relay
GET  /socket.io/?EIO=4&transport=...  → Socket.IO handshake (🚨 CÓ LỖI - xem mục 5)
```

### 2.2 Web Admin (React - Vite)

- **Port**: `5173`
- **URL**: `http://localhost:5173` (dev) hoặc `http://192.168.1.X:5173`
- **Backend Base**: `http://192.168.1.10:5000`

**Tính năng:**

- Zone config
- Events History (fetch `/api/alerts`)
- Camera live view

### 2.3 Relay Node (Alert Notification)

- **Port**: `5003`
- **URL**: `http://192.168.1.10:5003`
- **Localhost**: `http://localhost:5003`

**Endpoints:**

```
POST /api/alerts/notify    → Nhận từ Python, relay sang user app
GET  /api/health           → Health check
```

**Tính năng:**

- Validate `INTERNAL_SECRET`
- Normalize `image_url`
- Emit `new_alert` event qua Socket.IO
- Gửi Telegram (chưa implement)

---

## 3. Alert Flow (Cảnh báo hoàn chỉnh)

### 3.1 Giai đoạn 1: Detection (Python Backend)

```
Video Frame → YOLO Detection → Zone Check
    ↓
Zone_B detected → Save snapshot → Call alert endpoint
```

**Endpoint gọi:**

```bash
POST http://192.168.1.10:5003/api/alerts/notify
Content-Type: application/json

{
  "object_type": "CHILD (HIGH RISK)",
  "camera_name": "Camera 1",
  "confidence": 0.95,
  "image_path": "static/alerts/snapshot_cam1_zone_b_xxx.jpg",
  "image_url": "http://192.168.1.10:5000/static/alerts/snapshot_cam1_zone_b_xxx.jpg",
  "image_urls": ["http://192.168.1.10:5000/static/alerts/snapshot_cam1_zone_b_xxx.jpg"],
  "message": "CHILD INTRUSION ALERT at Zone zone_b",
  "secret": "your_internal_secret",
  "source": "python-backend"
}
```

### 3.2 Giai đoạn 2: Relay (Node Backend)

```
Receive POST /api/alerts/notify
    ↓
Validate secret
    ↓
Normalize image_url
    ↓
io.emit("new_alert", payload)  ← Socket.IO realtime
    ↓
Send Telegram (TODO)
    ↓
Return 200 {status: success}
```

### 3.3 Giai đoạn 3: User App Realtime

```
Socket.IO connect to http://192.168.1.10:5003
    ↓
Listen event "new_alert"
    ↓
Receive alert payload
    ↓
Display image from image_url
    ↓
Update UI realtime
```

---

## 4. User App Integration Checklist

### 4.1 Environment Variables Required

```env
# Flask Backend (web admin dùng)
VITE_BACKEND_BASE_URL=http://192.168.1.10:5000

# Relay Node (user app dùng cho realtime)
VITE_RELAY_BASE_URL=http://192.168.1.10:5003

# Socket.IO
VITE_SOCKET_IO_URL=http://192.168.1.10:5003
VITE_SOCKET_IO_PATH=/socket.io/
```

### 4.2 Socket.IO Connection

**Example (React/React Native):**

```javascript
import { io } from "socket.io-client";

const socket = io("http://192.168.1.10:5003", {
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  reconnectionAttempts: 5,
});

socket.on("connect", () => {
  console.log("✅ Connected to relay");
});

socket.on("new_alert", (payload) => {
  console.log("🚨 Alert received:", payload);
  // {
  //   object_type: "CHILD (HIGH RISK)",
  //   camera_name: "Camera 1",
  //   image_url: "http://192.168.1.10:5000/static/alerts/...",
  //   message: "CHILD INTRUSION ALERT",
  //   created_at: "2026-05-07T22:21:00.000Z"
  // }

  // Display alert immediately
  displayAlertNotification(payload);
});

socket.on("disconnect", () => {
  console.log("❌ Disconnected from relay");
});
```

### 4.3 Fetch Alert History

**Endpoint:**

```
GET http://192.168.1.10:5000/api/alerts?page=1&limit=20&search=...
```

**Response:**

```json
{
  "status": "success",
  "alerts": [
    {
      "id": 1,
      "camera_id": 1,
      "camera_name": "Camera 1",
      "zone_id": "zone_b",
      "zone_name": "Zone_B (Danger)",
      "object_type": "Child",
      "confidence": 0.95,
      "image_path": "static/alerts/snapshot_cam1_zone_b_xxx.jpg",
      "image_url": "http://192.168.1.10:5000/static/alerts/snapshot_cam1_zone_b_xxx.jpg",
      "is_resolved": 0,
      "created_at": "2026-05-07T22:21:00Z"
    }
  ],
  "total": 15,
  "page": 1
}
```

---

## 5. Current Issues & Solutions

### ❌ Issue 1: Socket.IO Returns 500

**Error:** `GET /socket.io/?EIO=4&transport=websocket HTTP/1.1" 500`

**Root Cause:** client đang nối nhầm vào Flask backend `5000` thay vì relay Node `5003`, hoặc đang mở websocket vào Flask Socket.IO endpoint không đúng transport.

**Solution:**

- User app realtime phải connect tới `http://192.168.1.10:5003`.
- Event phải là `new_alert`.
- Admin web chỉ đọc lịch sử từ `http://192.168.1.10:5000/api/alerts`.
- Nếu vẫn muốn nghe socket từ Flask, phải bảo đảm client và server cùng transport và môi trường có websocket support đầy đủ.

### ❌ Issue 2: User App Không Nhận Alert

**Dấu hiệu thực tế từ log hiện tại:**

1. `GET /alerts HTTP/1.1" 404` nghĩa là user app đang gọi sai endpoint. Backend chỉ có `/api/alerts`.
2. `GET /socket.io/?EIO=4&transport=websocket HTTP/1.1" 500` nghĩa là user app đang connect sai server/port hoặc sai transport.
3. Python backend đã log `STAGE 2 - Zone_B escalated`, nên detection ở backend vẫn chạy.

**Khả năng lỗi:**

1. User app không kết nối Socket.IO đúng port (5003).
2. User app không listen event name `new_alert`.
3. Relay Node không emit `new_alert` (chỉ log request).
4. `INTERNAL_SECRET` không match giữa Python & Relay.
5. Telegram chưa được cấu hình ở relay Node.

**Debugging:**

```bash
# Kiểm tra relay nhận được request
curl -X POST http://192.168.1.10:5003/api/alerts/notify \
  -H "Content-Type: application/json" \
  -d '{
    "object_type": "CHILD",
    "camera_name": "Test",
    "confidence": 1.0,
    "image_path": "test.jpg",
    "secret": "your_internal_secret"
  }'

# Phản hồi phải là:
# {"status": "success", "socket_emitted": true}
```

**Endpoint đúng cần dùng:**

```bash
GET  http://192.168.1.10:5000/api/alerts
GET  http://192.168.1.10:5000/api/connection-info
POST http://192.168.1.10:5003/api/alerts/notify
Socket.IO http://192.168.1.10:5003 event=new_alert
```

### ❌ Issue 3: Zone_B Detection Không Bắn Alert

**Khả năng lỗi:**

1. Zone config sai: Zone B name không chứa `zone_b`, `danger`, `inner`, `risk`.
2. `supervised_mode = 1` bị enable ở database `ai_settings`.
3. Cooldown còn chưa hết (default 10 giây per zone).

**Debugging:**

```bash
# Kiểm tra Zone config
curl http://192.168.1.10:5000/api/load_zones/1

# Kiểm tra supervised mode
SELECT supervised_mode FROM ai_settings WHERE camera_id = 1;
```

### ❌ Issue 4: Alert Image 404

**Error:** `GET /static/alerts/snapshot_cam1_zone_b_xxx.jpg HTTP/1.1" 404`

**Root Cause:** Ảnh không tồn tại hoặc path sai.

**Solution:**

- Kiểm tra `/backend/static/alerts/` thực tế có file không.
- Kiểm tra `PUBLIC_BASE_URL` trong `.env` khớp với IP/port hiện tại.
- Nếu chạy test video, chắc test video có object để phát hiện.

---

## 6. Configuration Checklist

### Backend `.env`

```env
FLASK_SERVER_HOST=0.0.0.0
FLASK_SERVER_PORT=5000
PUBLIC_BASE_URL=http://192.168.1.10:5000
NODE_BACKEND_URL=http://localhost:5003
ALERT_NOTIFY_URL=http://localhost:5003
INTERNAL_SECRET=your_internal_secret
CORS_ORIGIN=http://localhost:5173,http://192.168.1.10:5173
```

### Frontend `.env.local`

```env
VITE_BACKEND_BASE_URL=http://192.168.1.10:5000
VITE_ALERTS_API_URL=http://192.168.1.10:5000/api/alerts
```

### Relay Node `.env`

```env
PORT=5003
PUBLIC_BASE_URL=http://192.168.1.10:5003
ALERT_IMAGE_PUBLIC_BASE_URL=http://192.168.1.10:5000
INTERNAL_SECRET=your_internal_secret
TELEGRAM_BOT_TOKEN=your_token (optional)
TELEGRAM_CHAT_ID=your_chat_id (optional)
```

---

## 7. Quick Start for User App

### 7.1 Install Dependencies

```bash
npm install socket.io-client
```

### 7.2 Setup Alert Service

```javascript
// services/alertService.js
import { io } from "socket.io-client";

class AlertService {
  constructor() {
    this.socket = null;
    this.listeners = [];
  }

  connect(relayBaseUrl = "http://192.168.1.10:5003") {
    this.socket = io(relayBaseUrl, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    });

    this.socket.on("new_alert", (payload) => {
      this.listeners.forEach((cb) => cb(payload));
    });

    this.socket.on("connect", () => console.log("Alert service connected"));
    this.socket.on("disconnect", () =>
      console.log("Alert service disconnected"),
    );
  }

  subscribe(callback) {
    this.listeners.push(callback);
  }

  disconnect() {
    if (this.socket) this.socket.disconnect();
  }
}

export default new AlertService();
```

### 7.3 Use in Component

```javascript
import alertService from "./services/alertService";

useEffect(() => {
  alertService.connect("http://192.168.1.10:5003");

  alertService.subscribe((alert) => {
    // Handle alert
    console.log("New alert:", alert);
    showNotification(alert);
  });

  return () => alertService.disconnect();
}, []);
```

---

## 8. Summary

| Layer          | Port | Role                       |
| -------------- | ---- | -------------------------- |
| Python Backend | 5000 | Detection + History API    |
| Relay Node     | 5003 | Socket.IO + Telegram relay |
| Web Admin      | 5173 | Admin dashboard            |
| User App       | Any  | Realtime consumer          |

**Key Points:**

- User app phải connect Socket.IO tới port 5003, không phải 5000.
- Image URL phải truy cập được từ internet (không dùng localhost từ mobile).
- `INTERNAL_SECRET` phải giống nhau ở Python & Relay Node.
- Zone tên phải chứa keyword để hệ thống nhận diện Zone_B.

---

## 9. Support

Nếu cảnh báo vẫn không hoạt động:

1. Kiểm tra Python log có "Stage 2" message không (Zone_B detect).
2. Kiểm tra Relay Node nhận được POST request không.
3. Kiểm tra User App connect được Socket.IO không (browser console).
4. Kiểm tra network tab xem image URL load được không.
