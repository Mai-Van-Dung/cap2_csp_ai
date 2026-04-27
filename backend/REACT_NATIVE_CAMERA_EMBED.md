# React Native Camera Embed (User App)

This backend exposes WebView camera routes and a dynamic bootstrap endpoint so User App can reconnect when Wi-Fi changes.

- `GET /viewer/camera`
- `GET /video_feed` (MJPEG)
- `GET /api/connection-info` (dynamic base URL candidates)

## 1) Why dynamic connection is needed

If you hardcode one LAN IP (example `192.168.1.x`), changing Wi-Fi often changes backend IP and breaks both camera and Socket.IO.

Use these priorities in User App:

1. Stable public URL from env (best):
- Example: `https://camera-your-team.trycloudflare.com`

2. Bootstrap endpoint from backend:
- `GET {seedBase}/api/connection-info`
- Read `base_candidates` and auto-probe.

3. Local fallback list:
- Android emulator: `http://10.0.2.2:5000`
- Local browser: `http://localhost:5000`, `http://127.0.0.1:5000`

## 2) Backend env for flexible networking

Set these values in backend `.env`:

- `FLASK_SERVER_HOST=0.0.0.0`
- `FLASK_SERVER_PORT=5000`
- `CAMERA_PUBLIC_BASE_URL=` optional stable URL (cloud tunnel/domain)

When `CAMERA_PUBLIC_BASE_URL` is set, `GET /api/connection-info` will prioritize it in `base_candidates`.

## 3) User App endpoint strategy (recommended)

Use one seed URL list, then expand dynamically:

```js
const SEED_BASES = [
  process.env.EXPO_PUBLIC_CAMERA_PUBLIC_BASE_URL, // stable domain/tunnel if available
  "http://10.0.2.2:5000",
  "http://127.0.0.1:5000",
  "http://localhost:5000",
].filter(Boolean);

async function getCameraCandidates() {
  const merged = [];

  for (const seed of SEED_BASES) {
    if (!merged.includes(seed)) merged.push(seed);

    try {
      const res = await fetch(`${seed.replace(/\/+$/, "")}/api/connection-info`, { method: "GET" });
      if (!res.ok) continue;
      const data = await res.json();
      for (const candidate of data?.base_candidates || []) {
        if (!merged.includes(candidate)) merged.push(candidate);
      }
    } catch {
      // ignore this seed and continue
    }
  }

  return merged;
}
```

Then probe in order:

1. `GET {base}/viewer/camera` for camera.
2. Socket connect to same `{base}`, listen `new_alert`.
3. On fail, continue next candidate.

## 4) Minimal runbook when changing Wi-Fi

1. Start backend normally on port 5000.
2. Open one reachable seed base (public URL or LAN URL).
3. User App calls `/api/connection-info` and receives updated IP candidates.
4. User App auto-probes and reconnects camera + socket.

## 5) Stable option for moving between networks

Best long-term: use one fixed domain/tunnel instead of LAN IP.

Examples:
- Cloudflare Tunnel
- Tailscale Funnel
- Reverse proxy with public DNS

Put that URL in `CAMERA_PUBLIC_BASE_URL` and `EXPO_PUBLIC_CAMERA_PUBLIC_BASE_URL`.

## 6) Quick checks

From mobile browser, verify:

- `{base}/status`
- `{base}/viewer/camera`
- `{base}/socket.io/?EIO=4&transport=polling`

If these work, User App WebView + realtime alerts should connect.

