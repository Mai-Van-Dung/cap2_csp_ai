import os
import time
import cv2
import numpy as np
import socket
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from flask import Flask, Response, jsonify, request, session
from flask_cors import CORS
from dotenv import load_dotenv
from db_connector import execute_query, fetch_all, fetch_one
from flask_socketio import SocketIO
from ultralytics import YOLO
import jwt

try:
    import bcrypt
except ImportError:
    bcrypt = None

from werkzeug.security import check_password_hash

BASE_DIR = os.path.dirname(__file__)
load_dotenv(os.path.join(BASE_DIR, ".env"))

import camera_service as cs
import zone_service
import alert_service

# --- CẤU HÌNH THÔNG SỐ CAMERA ---
# Bạn có thể thay đổi trực tiếp ở đây hoặc dùng biến môi trường
CAM_IP = os.getenv("CAM_IP", "192.168.1.50")
CAM_PORT = int(os.getenv("CAM_PORT", "554"))
CAM_USER = os.getenv("CAM_USER", "admin")
CAM_PASS = os.getenv("CAM_PASS", "Dungpro123@") # Verification Code của bạn

# Các đường dẫn RTSP phổ biến của Ezviz
RTSP_PATHS = ["/H.264", "/h264_stream", "/live0", "/Streaming/Channels/101"]

OUTPUT_SIZE = (1280, 720) # Khớp với tỉ lệ 16:9 của Frontend
TARGET_FPS = 15
JPEG_QUALITY = 80
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "1"))
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", os.path.join(BASE_DIR, "yolov8n.pt"))
JWT_SECRET = os.getenv("AUTH_JWT_SECRET") or os.getenv("INTERNAL_SECRET") or os.getenv("FLASK_SECRET_KEY") or "cap2-csp-dev-secret"
USE_TEST_VIDEO = os.getenv("USE_TEST_VIDEO", "false").strip().lower() in ("1", "true", "yes", "on")
TEST_VIDEO_PATH = os.getenv(
    "TEST_VIDEO_PATH",
    os.path.join(BASE_DIR, "videotest", "videotest.mp4"),
)
TEST_VIDEO_FORCE_FPS = float(os.getenv("TEST_VIDEO_FORCE_FPS", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

app = Flask(__name__)
app.secret_key = JWT_SECRET
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
# Cho phép Frontend React truy cập
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173").split(",")
    if origin.strip()
]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


def _detect_local_ipv4_candidates():
    """Detect local IPv4 addresses so clients can auto-probe after Wi-Fi changes."""
    candidates = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                candidates.append(ip)
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = item[4][0]
            if ip and not ip.startswith("127."):
                candidates.append(ip)
    except Exception:
        pass

    unique = []
    for ip in candidates:
        if ip not in unique:
            unique.append(ip)
    return unique


def _build_connection_base_candidates(host_url=None):
    """Build ordered camera/socket base URL candidates for cross-project clients."""
    configured_public_base = (
        os.getenv("CAMERA_PUBLIC_BASE_URL", "").strip().rstrip("/")
        or os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    )
    server_port = int(os.getenv("FLASK_SERVER_PORT", "5000"))

    bases = []
    if configured_public_base:
        bases.append(configured_public_base)

    if host_url:
        bases.append(host_url.rstrip("/"))

    bases.extend([
        f"http://127.0.0.1:{server_port}",
        f"http://localhost:{server_port}",
    ])

    for ip in _detect_local_ipv4_candidates():
        bases.append(f"http://{ip}:{server_port}")

    deduped = []
    for base in bases:
        if base and base not in deduped:
            deduped.append(base)
    return deduped


def emit_new_alert(payload):
    """Broadcast realtime alert event to Socket.IO clients."""
    socketio.emit("new_alert", payload)


_grid_model = None


def _encode_auth_token(user_row):
    user_id = user_row.get("id") if isinstance(user_row, dict) else None
    if user_id is None and isinstance(user_row, dict):
        user_id = user_row.get("user_id")

    payload = {
        "user_id": int(user_id),
        "username": user_row.get("username"),
        "full_name": user_row.get("full_name"),
        "role_id": int(user_row.get("role_id")) if user_row.get("role_id") is not None else None,
        "role_name": user_row.get("role_name"),
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as error:
        logging.info("Invalid auth token: %s", error)
        return None


def _verify_password(password, stored_hash):
    if not stored_hash:
        return False

    if bcrypt is not None and isinstance(stored_hash, str) and stored_hash.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False

    try:
        return check_password_hash(stored_hash, password)
    except Exception:
        return stored_hash == password


def _get_authenticated_identity():
    if isinstance(session.get("user"), dict):
        return session["user"]

    token_payload = _decode_bearer_token()
    if token_payload:
        return token_payload

    return None


def _load_user_identity(user_id):
    try:
        return fetch_one(
            """
            SELECT u.id, u.username, u.full_name, u.role_id, r.role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
            """,
            (user_id,),
        )
    except Exception as error:
        logging.error("Error loading authenticated user %s: %s", user_id, error)
        return None


def _load_default_admin_identity():
    try:
        return fetch_one(
            """
            SELECT u.id, u.username, u.full_name, u.role_id, r.role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE LOWER(COALESCE(r.role_name, '')) = 'admin' OR u.role_id = %s
            ORDER BY u.id ASC
            LIMIT 1
            """,
            (ADMIN_ROLE_ID,),
        )
    except Exception as error:
        logging.error("Error loading fallback admin identity: %s", error)
        return None


def _load_camera_profile(camera_id):
    try:
        return fetch_one(
            """
            SELECT
                c.id AS camera_id,
                c.camera_name,
                c.location_note,
                c.rtsp_url,
                c.status,
                COALESCE(c.is_online, 0) AS is_online,
                COALESCE(c.is_active, 1) AS is_active,
                u.id AS owner_user_id,
                u.username AS owner_username,
                u.email AS owner_email,
                u.full_name AS owner_name,
                u.email AS owner_email
            FROM cameras c
            LEFT JOIN (
                SELECT camera_id, MAX(user_id) AS owner_user_id
                FROM user_camera_access
                WHERE access_level = 'owner'
                GROUP BY camera_id
            ) uca ON uca.camera_id = c.id
            LEFT JOIN users u ON u.id = uca.owner_user_id
            WHERE c.id = %s
            """,
            (camera_id,),
        )
    except Exception as error:
        logging.error("Error loading camera profile %s: %s", camera_id, error)
        return None


def _sync_camera_profile(camera_id, camera_data):
    if not isinstance(camera_data, dict):
        return None

    camera_name = (camera_data.get("camera_name") or camera_data.get("name") or f"Camera {camera_id}").strip()
    location_note = (camera_data.get("location_note") or camera_data.get("location") or "").strip() or None
    rtsp_url = (camera_data.get("rtsp_url") or camera_data.get("stream_url") or "").strip()
    status = (camera_data.get("status") or "offline").strip().lower()
    is_online = 1 if bool(camera_data.get("is_online")) else 0
    is_active = 1 if camera_data.get("is_active", True) else 0

    execute_query(
        """
        INSERT INTO cameras (id, camera_name, location_note, rtsp_url, status, is_online, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            camera_name = VALUES(camera_name),
            location_note = VALUES(location_note),
            rtsp_url = VALUES(rtsp_url),
            status = VALUES(status),
            is_online = VALUES(is_online),
            is_active = VALUES(is_active)
        """,
        (camera_id, camera_name, location_note, rtsp_url, status, is_online, is_active),
    )

    owner_user_id = camera_data.get("owner_user_id") or camera_data.get("owner_id")
    if owner_user_id in (None, "", 0, "0"):
        return _load_camera_profile(camera_id)

    owner_user_id = int(owner_user_id)
    owner_exists = fetch_one("SELECT id FROM users WHERE id = %s", (owner_user_id,))
    if not owner_exists:
        raise ValueError(f"Owner user {owner_user_id} not found")

    execute_query(
        "DELETE FROM user_camera_access WHERE camera_id = %s AND access_level = 'owner'",
        (camera_id,),
    )
    execute_query(
        "INSERT INTO user_camera_access (user_id, camera_id, access_level) VALUES (%s, %s, 'owner')",
        (owner_user_id, camera_id),
    )

    return _load_camera_profile(camera_id)


def _require_admin_identity():
    identity = _get_authenticated_identity()
    if not identity:
        if os.getenv("NODE_ENV", "development").lower() != "production":
            fallback_identity = _load_default_admin_identity()
            if fallback_identity:
                return fallback_identity, None

        return None, ({
            "status": "error",
            "message": "Authentication required",
        }, 401)

    user_id = identity.get("user_id") or identity.get("id")
    if user_id is None:
        return None, ({
            "status": "error",
            "message": "Invalid authentication payload",
        }, 401)

    user_row = _load_user_identity(user_id)
    if not user_row:
        return None, ({
            "status": "error",
            "message": "Authenticated user not found",
        }, 401)

    role_id = user_row.get("role_id")
    role_name = (user_row.get("role_name") or "").strip().lower()
    if role_name != "admin" and role_id != ADMIN_ROLE_ID:
        return None, ({
            "status": "error",
            "message": "Admin access required",
        }, 403)

    return user_row, None


def _get_grid_model():
    global _grid_model
    if _grid_model is not None:
        return _grid_model

    _grid_model = YOLO(YOLO_MODEL_PATH)
    return _grid_model


def _make_placeholder_frame(lines):
    frame = np.zeros((OUTPUT_SIZE[1], OUTPUT_SIZE[0], 3), dtype=np.uint8)
    frame[:] = (10, 17, 27)

    if isinstance(lines, str):
        lines = [lines]

    y = 70
    for line in lines:
        cv2.putText(frame, line, (40, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        y += 42

    return frame


def _encode_frame(frame):
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        return None
    return buf.tobytes()


def _open_test_video_capture():
    cap = cv2.VideoCapture(TEST_VIDEO_PATH)
    if not cap.isOpened():
        return None, 0.0

    source_fps = TEST_VIDEO_FORCE_FPS if TEST_VIDEO_FORCE_FPS > 0 else cap.get(cv2.CAP_PROP_FPS)
    frame_interval = 0.0
    if source_fps and source_fps > 0:
        frame_interval = 1.0 / float(source_fps)
    else:
        frame_interval = 1.0 / float(TARGET_FPS)

    return cap, frame_interval


def _stream_camera_feed(camera_id, camera_row):
    camera_name = camera_row.get("camera_name") or f"Camera {camera_id}"
    location_note = camera_row.get("location_note") or ""
    model = _get_grid_model()

    cap = None
    reconnect_delay = 1.5
    test_frame_interval = 0.0

    while True:
        if cap is None or not cap.isOpened():
            if USE_TEST_VIDEO:
                cap, test_frame_interval = _open_test_video_capture()
                if cap is None:
                    placeholder = _make_placeholder_frame([
                        f"{camera_name} (ID {camera_id})",
                        "Cannot open test video",
                        os.path.basename(TEST_VIDEO_PATH),
                    ])
                    payload = _encode_frame(placeholder)
                    if payload:
                        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"
                    time.sleep(reconnect_delay)
                    continue
            else:
                rtsp_url = camera_row["rtsp_url"]
                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    cap.release()
                    cap = None
                    placeholder = _make_placeholder_frame([
                        f"{camera_name} (ID {camera_id})",
                        "Cannot open RTSP stream",
                        location_note or "No location note",
                    ])
                    payload = _encode_frame(placeholder)
                    if payload:
                        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"
                    time.sleep(reconnect_delay)
                    continue

        ok, frame = cap.read()
        if not ok:
            if USE_TEST_VIDEO:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
                if not ok:
                    cap.release()
                    cap = None
                    time.sleep(reconnect_delay)
                    continue
            else:
                cap.release()
                cap = None
                continue

        try:
            results = model.predict(source=frame, classes=[0], conf=0.25, verbose=False)
            rendered = results[0].plot() if results else frame
        except Exception as infer_error:
            logging.error("YOLO inference failed for camera %s: %s", camera_id, infer_error)
            rendered = frame

        payload = _encode_frame(rendered)
        if payload:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"

        if USE_TEST_VIDEO and test_frame_interval > 0:
            time.sleep(test_frame_interval)


cs.set_alert_event_callback(emit_new_alert)
alert_service.set_alert_event_callback(emit_new_alert)

@app.route("/video_feed")
def video_feed():
    return Response(
        cs.gen_frames(app.logger),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/viewer/camera")
def camera_viewer_page():
        """Render a minimal MJPEG viewer page for React Native WebView embedding."""
        camera_label = request.args.get("label", "Live Camera")
        html = f"""
<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
    <title>{camera_label}</title>
    <style>
        html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; background: #0f172a; }}
        .wrap {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}
        img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
        .badge {{
            position: absolute; top: 10px; right: 10px; z-index: 3;
            background: #ef4444; color: white; font: 600 12px/1.2 Arial, sans-serif;
            border-radius: 999px; padding: 6px 10px;
        }}
    </style>
</head>
<body>
    <div class=\"wrap\">
        <div class=\"badge\">LIVE</div>
        <img src=\"/video_feed\" alt=\"camera-stream\" />
    </div>
</body>
</html>
"""
        return Response(html, mimetype="text/html")

@app.route("/status")
def status():
    return jsonify(cs.stream_status)


@app.route("/api/connection-info", methods=["GET"])
def connection_info():
    """Expose dynamic connection candidates so external apps can auto-connect."""
    base_candidates = _build_connection_base_candidates(request.host_url)
    preferred_base = base_candidates[0] if base_candidates else request.host_url.rstrip("/")

    return jsonify({
        "status": "success",
        "preferred_base_url": preferred_base,
        "base_candidates": base_candidates,
        "camera": {
            "viewer_path": "/viewer/camera",
            "video_feed_path": "/video_feed",
            "status_path": "/status",
            "viewer_url": f"{preferred_base}/viewer/camera",
        },
        "socket": {
            "path": "/socket.io",
            "event": "new_alert",
            "handshake_url": f"{preferred_base}/socket.io/?EIO=4&transport=polling",
        },
    }), 200


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Authenticate a user and issue both session and JWT credentials."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({
            "status": "error",
            "message": "username and password are required",
        }), 400

    try:
        user = fetch_one(
            """
            SELECT u.id, u.username, u.full_name, u.password_hash, u.role_id, r.role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.username = %s OR u.email = %s
            LIMIT 1
            """,
            (username, username),
        )
    except Exception as error:
        logging.error("Login query failed: %s", error)
        return jsonify({
            "status": "error",
            "message": f"Database error while logging in: {str(error)}",
        }), 500

    if not user:
        return jsonify({
            "status": "error",
            "message": "Invalid username or password",
        }), 401

    password_hash = user.get("password_hash") or ""
    if not _verify_password(password, password_hash):
        return jsonify({
            "status": "error",
            "message": "Invalid username or password",
        }), 401

    identity = {
        "user_id": int(user["id"]),
        "username": user.get("username"),
        "full_name": user.get("full_name"),
        "role_id": user.get("role_id"),
        "role_name": user.get("role_name"),
    }
    token = _encode_auth_token(identity)
    session["user"] = identity
    session.permanent = True

    return jsonify({
        "status": "success",
        "token": token,
        "user": identity,
    }), 200


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    identity = _get_authenticated_identity()
    if not identity:
        return jsonify({
            "status": "error",
            "message": "Authentication required",
        }), 401

    return jsonify({
        "status": "success",
        "user": identity,
    }), 200


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.pop("user", None)
    return jsonify({
        "status": "success",
        "message": "Logged out",
    }), 200


@app.route("/api/admin/cameras/grid", methods=["GET"])
def admin_cameras_grid():
    """Return camera grid data for the admin dashboard."""
    _, auth_error = _require_admin_identity()
    if auth_error:
        return auth_error

    try:
        cameras = fetch_all(
            """
            SELECT
                c.id AS camera_id,
                c.camera_name,
                c.location_note,
                c.rtsp_url,
                c.status,
                COALESCE(c.is_online, 0) AS is_online,
                COALESCE(c.is_active, 1) AS is_active,
                u.id AS owner_user_id,
                u.username AS owner_username,
                u.email AS owner_email,
                u.full_name AS owner_name
            FROM cameras c
            LEFT JOIN (
                SELECT camera_id, MAX(user_id) AS owner_user_id
                FROM user_camera_access
                WHERE access_level = 'owner'
                GROUP BY camera_id
            ) uca
                ON uca.camera_id = c.id
            LEFT JOIN users u
                ON u.id = uca.owner_user_id
            ORDER BY c.id DESC
            """
        )

        return jsonify({
            "status": "success",
            "count": len(cameras),
            "data": cameras,
        }), 200
    except Exception as error:
        logging.error("Error fetching admin camera grid: %s", error)
        return jsonify({
            "status": "error",
            "message": f"Failed to load camera grid: {str(error)}",
        }), 500


@app.route("/api/video_feed/<int:camera_id>")
def video_feed_by_camera(camera_id):
    """Stream YOLO-processed MJPEG for a specific camera."""
    _, auth_error = _require_admin_identity()
    if auth_error:
        return auth_error

    try:
        camera = fetch_one(
            """
            SELECT id, camera_name, location_note, rtsp_url, status, is_online
            FROM cameras
            WHERE id = %s
            """,
            (camera_id,),
        )
    except Exception as error:
        logging.error("Error loading camera %s: %s", camera_id, error)
        return jsonify({
            "status": "error",
            "message": f"Database error while loading camera: {str(error)}",
        }), 500

    if not camera:
        return jsonify({
            "status": "error",
            "message": f"Camera {camera_id} not found",
        }), 404

    _, auth_error = _require_admin_identity()
    if auth_error:
        return auth_error

    return Response(
        _stream_camera_feed(camera_id, camera),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/api/cameras/<int:camera_id>", methods=["GET"])
def get_camera_profile(camera_id):
    """Return a camera profile together with its single owner."""
    try:
        camera = _load_camera_profile(camera_id)
        if not camera:
            return jsonify({
                "status": "error",
                "message": f"Camera {camera_id} not found",
            }), 404

        return jsonify({
            "status": "success",
            "camera": camera,
        }), 200
    except Exception as error:
        logging.error("Error fetching camera profile %s: %s", camera_id, error)
        return jsonify({
            "status": "error",
            "message": f"Failed to load camera profile: {str(error)}",
        }), 500


@app.route("/api/alerts/notify", methods=["POST"])
def notify_alert():
    """Accept internal alert notifications from the camera service during local testing."""
    data = request.get_json(silent=True) or {}

    object_type = data.get("object_type")
    camera_name = data.get("camera_name")
    confidence = data.get("confidence")
    image_path = data.get("image_path")

    if not object_type or not camera_name:
        return jsonify({
            "status": "error",
            "message": "object_type and camera_name are required",
        }), 400

    app.logger.info(
        "Internal alert accepted | camera=%s | object_type=%s | confidence=%s | image=%s",
        camera_name,
        object_type,
        confidence,
        image_path,
    )

    return jsonify({
        "status": "success",
        "message": "Alert notification accepted",
    }), 200

@app.route("/api/save_config", methods=["POST"])
def save_config():
    """
    Save zone configuration from React frontend
    Expected JSON structure:
    {
        "camera_id": 1,
        "zones": [
            {
                "id": "DPZ-01",
                "name": "Pool Zone",
                "vertices": [[x1, y1], [x2, y2], ...]
            }
        ],
        "settings": {
            "min_child_height": 50,
            "sensitivity": 0.75
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No JSON data provided"
            }), 400
        
        camera_id = data.get("camera_id")
        zones = data.get("zones", [])
        settings = data.get("settings", {})
        camera_data = data.get("camera", {})
        
        if not camera_id:
            return jsonify({
                "status": "error",
                "message": "camera_id is required"
            }), 400
        
        if not isinstance(zones, list):
            return jsonify({
                "status": "error",
                "message": "zones must be an array"
            }), 400
        
        if camera_data:
            try:
                _sync_camera_profile(int(camera_id), camera_data)
            except ValueError as camera_error:
                return jsonify({
                    "status": "error",
                    "message": str(camera_error),
                }), 400

        result = zone_service.save_zone_config(camera_id, zones, settings)
        status_code = 200 if result["status"] == "success" else 400
        return jsonify(result), status_code
    
    except Exception as e:
        logging.error(f"Error in save_config: {e}")
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500


@app.route("/api/load_zones/<int:camera_id>", methods=["GET"])
def load_zones(camera_id):
    """
    Load all zones for a specific camera
    """
    try:
        zones = zone_service.load_zones(camera_id)
        return jsonify({
            "status": "success",
            "zones": zones,
            "count": len(zones)
        }), 200
    except Exception as e:
        logging.error(f"Error loading zones: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error loading zones: {str(e)}"
        }), 500


@app.route("/api/delete_zone/<zone_id>/<int:camera_id>", methods=["DELETE"])
def delete_zone(zone_id, camera_id):
    """
    Delete a specific zone
    """
    try:
        result = zone_service.delete_zone(zone_id, camera_id)
        status_code = 200 if result["status"] == "success" else 400
        return jsonify(result), status_code
    except Exception as e:
        logging.error(f"Error deleting zone: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error deleting zone: {str(e)}"
        }), 500


@app.route("/api/alerts", methods=["GET"])
def get_alerts_history():
    """Fetch persisted alert history for Events History page."""
    try:
        search = request.args.get("q", "").strip()
        object_type = request.args.get("object_type", "all").strip().lower()
        resolved = request.args.get("resolved", "all").strip().lower()
        limit = request.args.get("limit", default=150, type=int)

        if limit is None or limit <= 0:
            limit = 150
        limit = min(limit, 1000)

        where_clauses = ["1=1"]
        params = []

        if search:
            like_value = f"%{search}%"
            where_clauses.append(
                "(CAST(a.id AS CHAR) LIKE %s OR IFNULL(a.zone_id, '') LIKE %s OR IFNULL(z.zone_name, '') LIKE %s OR IFNULL(c.camera_name, '') LIKE %s)"
            )
            params.extend([like_value, like_value, like_value, like_value])

        if object_type in ("child", "adult"):
            where_clauses.append("LOWER(a.object_type) = %s")
            params.append(object_type)

        if resolved == "resolved":
            where_clauses.append("a.is_resolved = 1")
        elif resolved == "open":
            where_clauses.append("a.is_resolved = 0")

        params.append(limit)

        rows = fetch_all(
            f"""
            SELECT
                a.id,
                a.camera_id,
                a.zone_id,
                a.object_type,
                a.confidence,
                a.image_path,
                a.video_path,
                a.is_resolved,
                a.created_at,
                z.zone_name,
                c.camera_name
            FROM alerts a
            LEFT JOIN zones z ON a.zone_id = z.id AND a.camera_id = z.camera_id
            LEFT JOIN cameras c ON a.camera_id = c.id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY a.created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )

        host_root = request.host_url.rstrip("/")
        public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
        normalized = []

        for row in rows:
            image_path = row.get("image_path")
            image_url = None
            image_urls = []
            if image_path:
                if str(image_path).startswith("http://") or str(image_path).startswith("https://"):
                    image_url = image_path
                    image_urls = [image_path]
                else:
                    relative_path = str(image_path).lstrip('/')
                    if public_base_url:
                        image_urls.append(f"{public_base_url}/{relative_path}")
                    image_urls.append(f"{host_root}/{relative_path}")
                    image_url = image_urls[0]

            normalized.append({
                "id": row.get("id"),
                "camera_id": row.get("camera_id"),
                "camera_name": row.get("camera_name") or f"Camera {row.get('camera_id')}",
                "zone_id": row.get("zone_id"),
                "zone_name": row.get("zone_name") or (row.get("zone_id") or "Unknown Zone"),
                "object_type": row.get("object_type") or "Child",
                "confidence": row.get("confidence"),
                "image_path": image_path,
                "image_url": image_url,
                "image_urls": image_urls,
                "video_path": row.get("video_path"),
                "is_resolved": bool(row.get("is_resolved")),
                "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            })

        return jsonify({
            "status": "success",
            "count": len(normalized),
            "alerts": normalized,
        }), 200
    except Exception as e:
        logging.error(f"Error fetching alerts history: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error fetching alerts history: {str(e)}",
        }), 500


@app.route("/api/alerts/<int:alert_id>/resolve", methods=["PATCH"])
def resolve_alert(alert_id):
    """Mark an alert as resolved."""
    try:
        existing = fetch_one("SELECT id, is_resolved FROM alerts WHERE id = %s", (alert_id,))
        if not existing:
            return jsonify({
                "status": "error",
                "message": "Alert not found",
            }), 404

        execute_query("UPDATE alerts SET is_resolved = 1 WHERE id = %s", (alert_id,))
        return jsonify({
            "status": "success",
            "message": "Alert marked as resolved",
            "alert_id": alert_id,
        }), 200
    except Exception as e:
        logging.error(f"Error resolving alert {alert_id}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error resolving alert: {str(e)}",
        }), 500


@app.route("/api/camera/toggle-supervised", methods=["POST"])
def toggle_supervised_mode():
    """Toggle supervised swimming mode for a camera."""
    try:
        data = request.get_json(silent=True) or {}
        camera_id_raw = data.get("camera_id")
        enabled_raw = data.get("enabled")

        if camera_id_raw is None:
            return jsonify({
                "status": "error",
                "message": "camera_id is required",
            }), 400

        if enabled_raw is None:
            return jsonify({
                "status": "error",
                "message": "enabled is required",
            }), 400

        try:
            camera_id = int(camera_id_raw)
        except (TypeError, ValueError):
            return jsonify({
                "status": "error",
                "message": "camera_id must be an integer",
            }), 400

        enabled_int = None
        if isinstance(enabled_raw, bool):
            enabled_int = 1 if enabled_raw else 0
        elif isinstance(enabled_raw, (int, float)) and int(enabled_raw) in (0, 1):
            enabled_int = int(enabled_raw)
        elif isinstance(enabled_raw, str):
            normalized = enabled_raw.strip().lower()
            if normalized in ("1", "true", "yes", "on"):
                enabled_int = 1
            elif normalized in ("0", "false", "no", "off"):
                enabled_int = 0

        if enabled_int is None:
            return jsonify({
                "status": "error",
                "message": "enabled must be a boolean",
            }), 400

        camera_exists = fetch_one("SELECT id FROM cameras WHERE id = %s", (camera_id,))
        if not camera_exists:
            return jsonify({
                "status": "error",
                "message": f"Camera {camera_id} not found",
            }), 404

        execute_query(
            """
            INSERT INTO ai_settings (camera_id, supervised_mode)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE supervised_mode = VALUES(supervised_mode)
            """,
            (camera_id, enabled_int),
        )

        current_status = alert_service.checkSupervisedStatus(camera_id, force_refresh=True)
        return jsonify({
            "status": "success",
            "message": "Supervised swimming mode updated successfully",
            "camera_id": camera_id,
            "supervised_mode": bool(current_status),
        }), 200
    except Exception as e:
        logging.error("Error toggling supervised mode: %s", e)
        return jsonify({
            "status": "error",
            "message": f"Failed to toggle supervised mode: {str(e)}",
        }), 500

if __name__ == "__main__":
    host = os.getenv("FLASK_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_SERVER_PORT", "5000"))
    socketio.run(app, host=host, port=port, use_reloader=False)