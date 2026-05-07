# Supervised Swimming Mode - Backend and Cross-Project Sync Guide

This document explains how to integrate the new backend feature:

- API route: `POST /api/camera/toggle-supervised`
- DB column: `ai_settings.supervised_mode` (0/1)
- Runtime check: `checkSupervisedStatus(camera_id)` in Python alert flow

It also provides React Native guidance to add a toggle button in your Home screen (the screen you shared).

## 1) Backend behavior summary

When child intrusion is detected in Zone_B:

- `supervised_mode = 0` (normal): keep existing emergency behavior (external notify relay, Telegram/siren chain).
- `supervised_mode = 1` (supervised): still persist local alert + realtime event, but skip emergency notify relay (no siren trigger path).

This check is implemented in `backend/alert_service.py` using:

- `checkSupervisedStatus(camera_id)`
- Short TTL cache (`SUPERVISED_CACHE_TTL_SECONDS`, default 2s) to avoid frequent DB reads.

## 2) API contract

### Endpoint

`POST /api/camera/toggle-supervised`

### Request body

```json
{
  "camera_id": 1,
  "enabled": true
}
```

### Success response

```json
{
  "status": "success",
  "message": "Supervised swimming mode updated successfully",
  "camera_id": 1,
  "supervised_mode": true
}
```

### Validation notes

- `camera_id` is required and must be integer.
- `enabled` is required and accepts boolean (also supports `0/1`, `"true"/"false"`).
- Returns 404 if camera does not exist.

## 3) Quick test with curl

Enable supervised mode:

```bash
curl -X POST http://localhost:5000/api/camera/toggle-supervised \
	-H "Content-Type: application/json" \
	-d "{\"camera_id\":1,\"enabled\":true}"
```

Disable supervised mode:

```bash
curl -X POST http://localhost:5000/api/camera/toggle-supervised \
	-H "Content-Type: application/json" \
	-d "{\"camera_id\":1,\"enabled\":false}"
```

## 4) React Native integration (other project)

Use your existing Home screen and add one toggle control. Suggested camera id default is `1` if your app is single-camera.

### 4.1 Add API helper

Create or update your API service file (example: `services/api.js`):

```javascript
export const cameraModeAPI = {
  async toggleSupervised(cameraId, enabled) {
    const res = await fetch(`${BASE_URL}/api/camera/toggle-supervised`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_id: cameraId, enabled }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok || data?.status !== "success") {
      throw new Error(data?.message || "Toggle supervised mode failed");
    }
    return data;
  },
};
```

If your project already has Axios wrapper, keep the same pattern.

### 4.2 Add state in Home screen

In your Home component, add:

```javascript
const CAMERA_ID = 1;
const [supervisedMode, setSupervisedMode] = useState(false);
const [supervisedLoading, setSupervisedLoading] = useState(false);
```

### 4.3 Add toggle handler

```javascript
const toggleSupervisedMode = useCallback(async () => {
  if (supervisedLoading) return;
  try {
    setSupervisedLoading(true);
    const next = !supervisedMode;
    const result = await cameraModeAPI.toggleSupervised(CAMERA_ID, next);
    setSupervisedMode(Boolean(result?.supervised_mode));
    Alert.alert(
      "Che do boi co giam sat",
      result?.supervised_mode
        ? "Da BAT che do co giam sat"
        : "Da TAT che do co giam sat",
    );
  } catch (err) {
    Alert.alert("Loi", err?.message || "Khong cap nhat duoc che do");
  } finally {
    setSupervisedLoading(false);
  }
}, [supervisedLoading, supervisedMode]);
```

### 4.4 Add button to UI

Place this under camera card or above status button:

```jsx
<TouchableOpacity
  activeOpacity={0.88}
  style={[
    styles.supervisedToggleBtn,
    { backgroundColor: supervisedMode ? "#0EA5A4" : "#64748B" },
  ]}
  onPress={toggleSupervisedMode}
  disabled={supervisedLoading}
>
  <Text style={styles.supervisedToggleText}>
    {supervisedLoading
      ? "Dang cap nhat..."
      : supervisedMode
        ? "CHE DO BOI CO GIAM SAT: DANG BAT"
        : "CHE DO BOI CO GIAM SAT: DANG TAT"}
  </Text>
</TouchableOpacity>
```

### 4.5 Add styles

```javascript
supervisedToggleBtn: {
	marginHorizontal: 16,
	marginTop: 10,
	borderRadius: 12,
	paddingVertical: 12,
	alignItems: "center",
},
supervisedToggleText: {
	color: "#FFFFFF",
	fontSize: 12,
	fontWeight: "800",
	letterSpacing: 0.6,
},
```

## 5) Optional startup sync (recommended)

For full consistency after app restart, add a read-status endpoint later (example: `GET /api/camera/supervised-status/<camera_id>`), then call it in `useEffect` when Home screen mounts.

Current backend now guarantees toggle/write path and runtime behavior in alert processing.

## 6) End-to-end expected result

1. User taps toggle ON in React Native app.
2. Backend writes `ai_settings.supervised_mode = 1`.
3. YOLO + Gemini detection continues normally.
4. On child intrusion, local alert history and realtime feed still work.
5. Emergency relay path is skipped, so siren chain is not triggered.
