# Cross-Project Alert Sync

This document describes the working contract between the Python detection backend and the separate Node/Telegram/User App project.

The goal is simple: one detected intrusion should become one realtime alert, one Telegram message, and one user-app event with a valid image URL.

## 1. Working flow

1. Python backend detects a person entering Zone_B.
2. Python saves a snapshot to `backend/static/alerts/`.
3. Python sends a relay payload to the Node project at `POST /api/alerts/notify`.
4. Node project validates the secret, builds the image URL, sends Telegram, and emits an event to the user app.
5. User app loads the image from the public URL and renders the alert instantly.

The key design change is this: do not hardcode the Python server IP in the user app. Instead, ask the Python backend for connection candidates.

## 2. Dynamic connection discovery

Python now exposes:

- `GET /api/connection-info`

Example response fields:

- `preferred_base_url`
- `base_candidates`
- `camera.viewer_url`
- `socket.handshake_url`

Use `base_candidates` to auto-probe the correct address for the current network.

Recommended client behavior:

1. Start with a known working seed URL.
2. Call `GET /api/connection-info`.
3. Try the returned `base_candidates` in order.
4. Use the first base that responds for both camera and socket.

This avoids the exact failure shown in the log where the user app tried `http://192.168.1.8:5000/...` but the Python backend was actually reachable at `http://192.168.1.14:5000/...`.

## 3. Required environment variables

### Python backend `.env`

Use placeholders that match your current machine and network:

```env
FLASK_SERVER_HOST=0.0.0.0
FLASK_SERVER_PORT=5000
PUBLIC_BASE_URL=http://192.168.1.14:5000
NODE_BACKEND_URL=http://localhost:5003
ALERT_NOTIFY_URL=http://localhost:5003
INTERNAL_SECRET=your_internal_secret
```

Notes:

- Set `PUBLIC_BASE_URL` to the address the Node project and user app can actually reach.
- If everything runs on one machine, `http://localhost:5000` is the easiest stable value.
- If the user app runs on a phone, use the LAN IP of the Python machine, not `localhost`.

### Node notification project `.env`

```env
PORT=5003
PUBLIC_BASE_URL=http://localhost:5003
ALERT_IMAGE_PUBLIC_BASE_URL=http://192.168.1.14:5000
INTERNAL_SECRET=your_internal_secret
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Notes:

- `ALERT_IMAGE_PUBLIC_BASE_URL` must point to the Python backend address that serves `/static/alerts/...`.
- If the Node project is on the same machine as Python, `http://localhost:5000` is fine.
- If it is on another machine, use the Python machine LAN IP and make sure port `5000` is reachable.

## 4. Alert payload contract

Python sends this shape to the Node relay:

```json
{
  "object_type": "CHILD (HIGH RISK)",
  "camera_name": "Camera 1",
  "confidence": 0.95,
  "image_path": "static/alerts/snapshot_cam1_zone_b_xxx.jpg",
  "image_url": "http://192.168.1.14:5000/static/alerts/snapshot_cam1_zone_b_xxx.jpg",
  "image_urls": [
    "http://192.168.1.14:5000/static/alerts/snapshot_cam1_zone_b_xxx.jpg"
  ],
  "secret": "your_internal_secret",
  "message": "🔴 CHILD INTRUSION ALERT at Zone zone_b",
  "source": "python-backend"
}
```

The Node project should:

1. Validate `secret`.
2. Use `image_url` if present.
3. Fall back to constructing the image URL from `ALERT_IMAGE_PUBLIC_BASE_URL + image_path`.
4. Send Telegram.
5. Emit the realtime event to the user app.

## 5. Fast realtime setup

For best latency and reliability:

1. Run Python backend on the machine that owns the camera stream.
2. Run Node notification service either on the same machine or on a host that can reach Python over the LAN.
3. Keep `INTERNAL_SECRET` identical in both projects.
4. Make sure the Node project can fetch the image URL from Python before enabling Telegram delivery.
5. In the user app, read image URLs from the alert event instead of reconstructing them manually.

Recommended event fields for the user app:

- `image_url`
- `camera_name`
- `zone_id`
- `object_type`
- `confidence`
- `created_at`

## 6. Troubleshooting matrix

### A. Image fetch timeout in Node logs

Symptom:

- `Failed to fetch image from public URL ... connect ETIMEDOUT`

Cause:

- Wrong `ALERT_IMAGE_PUBLIC_BASE_URL`
- Python backend IP changed
- Port `5000` blocked
- Python backend not reachable from Node host

Fix:

1. Verify the Python backend address from `GET /api/connection-info`.
2. Open the image URL in a browser from the Node machine.
3. Replace the hardcoded IP with the current reachable IP or `localhost` if both services run on the same machine.

### B. Telegram works slowly or not at all

Cause:

- Node project is slow to process the alert.
- Telegram send path is blocked by image fetch or network issues.
- Secrets mismatch.

Fix:

1. Confirm the Node `/api/alerts/notify` endpoint returns quickly.
2. Confirm the image is reachable before Telegram send.
3. Check Telegram token and chat ID.
4. Confirm `INTERNAL_SECRET` matches exactly.

### C. User app does not receive image

Cause:

- User app is listening to the wrong host.
- The event payload does not include `image_url`.
- The user app reconstructs the URL using the wrong IP.

Fix:

1. Subscribe to the socket event emitted by the Node project.
2. Use `image_url` from the event payload.
3. If missing, use `ALERT_IMAGE_PUBLIC_BASE_URL + image_path`.
4. Do not hardcode `192.168.1.8` or any old address.

### D. Python log shows alert timeout to Node

Cause:

- Node service is not reachable at the configured host.

Fix:

1. Use `http://localhost:5003` if Node is on the same machine.
2. Use the actual LAN IP if Node is on another machine.
3. Test with `curl` or a browser before restarting Python.

## 7. Minimal verification steps

From the Python machine:

```bash
curl http://127.0.0.1:5000/api/connection-info
curl http://localhost:5003/api/health
```

From the Node machine, test the image URL directly:

```bash
curl http://192.168.1.14:5000/static/alerts/test.jpg
```

If that works, Telegram can usually fetch the same image too.

## 8. Practical recommendation for your current setup

If you are developing on one Windows machine, use these values first:

```env
PUBLIC_BASE_URL=http://localhost:5000
ALERT_NOTIFY_URL=http://localhost:5003
NODE_BACKEND_URL=http://localhost:5003
```

If the user app runs on a phone, replace `localhost` with the LAN IP of the machine running the backend.

If the IP changes often, keep using `/api/connection-info` to discover the live base URL instead of editing every app manually.
