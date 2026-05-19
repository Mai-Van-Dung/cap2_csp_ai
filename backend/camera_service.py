import requests 
import os
import time
import cv2
import threading
import numpy as np
from urllib.parse import quote
from ultralytics import YOLO
import zone_service
import logging
from db_connector import execute_query
import video_service
import alert_service

# ✅ Age/Gender Detection (Proper initialization)
DEEPFACE_AVAILABLE = False
MEDIAPIPE_AVAILABLE = False
FACE_CASCADE = None

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    logging.info("✅ DeepFace loaded successfully")
except ImportError:
    logging.warning("⚠️ DeepFace not installed - age detection will use heuristics only")

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
    logging.info("✅ MediaPipe loaded successfully")
except ImportError:
    logging.warning("⚠️ MediaPipe not installed")

# Load OpenCV Haar Cascade for face detection
try:
    FACE_CASCADE = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml'
    )
    if FACE_CASCADE.empty():
        FACE_CASCADE = None
        logging.warning("⚠️ Face cascade classifier not found")
    else:
        logging.info("✅ Face cascade classifier loaded")
except Exception as e:
    logging.warning(f"⚠️ Could not load face cascade: {e}")

# --- Camera config ---
CAM_IP = os.getenv("CAM_IP", "192.168.1.50")
CAM_PORT = int(os.getenv("CAM_PORT", "554"))
CAM_USER = os.getenv("CAM_USER", "admin")
CAM_PASS = os.getenv("CAM_PASS", "Dungpro123@")
RTSP_PATHS = ["/H.264", "/h264_stream", "/live0", "/Streaming/Channels/101"]
USE_TEST_VIDEO = os.getenv("USE_TEST_VIDEO", "false").strip().lower() in ("1", "true", "yes", "on")
TEST_VIDEO_PATH = os.getenv(
    "TEST_VIDEO_PATH",
    os.path.join(os.path.dirname(__file__), "videotest", "videotest.mp4"),
)
TEST_VIDEO_FORCE_FPS = float(os.getenv("TEST_VIDEO_FORCE_FPS", "0"))

OUTPUT_WIDTH = int(os.getenv("OUTPUT_WIDTH", "960"))
OUTPUT_HEIGHT = int(os.getenv("OUTPUT_HEIGHT", "540"))
OUTPUT_SIZE = (OUTPUT_WIDTH, OUTPUT_HEIGHT)
TARGET_FPS = int(os.getenv("TARGET_FPS", "12"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "65"))
INFERENCE_EVERY_N_FRAMES = max(1, int(os.getenv("INFERENCE_EVERY_N_FRAMES", "2")))
CLASSIFICATION_REFRESH_FRAMES = max(1, int(os.getenv("CLASSIFICATION_REFRESH_FRAMES", "10")))

# --- YOLO config ---
MODEL_PATH = "yolov8n.pt"
CONF_THRES = float(os.getenv("YOLO_CONF_THRES", "0.45"))  # Slightly lower to catch smaller objects
PERSON_CLASS_ID = 0
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "10"))
ALERT_DIR = os.path.join(os.path.dirname(__file__), "static", "alerts")
MANUAL_SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "static", "manual_snapshots")

# --- Age Detection Optimization params ---
# Pool-specific thresholds (can be overridden via environment)
CHILD_HEIGHT_THRESHOLD_EXTREME = float(os.getenv("CHILD_HEIGHT_EXTREME", "0.18"))   # height < 18% = CHILD
CHILD_HEIGHT_THRESHOLD_VERY_SMALL = float(os.getenv("CHILD_HEIGHT_VERY_SMALL", "0.25"))  # height < 25% = CHILD
CHILD_HEIGHT_THRESHOLD_SMALL = float(os.getenv("CHILD_HEIGHT_SMALL", "0.32"))  # height < 32% = medium
DEEPFACE_CONFIDENCE_THRESHOLD = float(os.getenv("DEEPFACE_CONF_THRES", "0.80"))  # Use DeepFace if confidence >= 80%
FACE_EXPAND_RATIO = float(os.getenv("FACE_EXPAND_RATIO", "1.2"))  # Expand bbox for face detection
CASCADE_MIN_FACE_SIZE = int(os.getenv("CASCADE_MIN_FACE_SIZE", "20"))  # Minimum face size for cascade detector

stream_status = {
    "connected": False,
    "last_error": "",
    "active_path": "",
    "camera_ip": CAM_IP,
    "ai_ready": False,
    "source": "test_video" if USE_TEST_VIDEO else "rtsp",
}

CAMERA_DISCONNECT_ALERT_ENABLED = os.getenv(
    "CAMERA_DISCONNECT_ALERT_ENABLED",
    "false" if USE_TEST_VIDEO else "true",
).strip().lower() in ("1", "true", "yes", "on")
CAMERA_ONLINE_STABLE_SECONDS = float(os.getenv("CAMERA_ONLINE_STABLE_SECONDS", "20"))
CAMERA_DISCONNECT_ALERT_COOLDOWN_SECONDS = float(
    os.getenv("CAMERA_DISCONNECT_ALERT_COOLDOWN_SECONDS", "180")
)

_connection_state_lock = threading.Lock()
_connection_state = {
    "stable_online_since": None,
    "was_stable_online": False,
    "offline_since": None,
    "last_disconnect_alert_ts": 0.0,
}

_frame_lock = threading.Lock()
_raw_frame = None
_processed_frame = None
_raw_id = 0
_workers_started = False

# Zone configuration cache (will be loaded from database)
_zones_cache = []
_zones_lock = threading.Lock()
_camera_id = 1  # Default camera ID, can be configured via environment or API
_last_alert_ts = {}
_test_video_frame_interval = 0.0
_alert_event_callback = None
_classification_lock = threading.Lock()
_classification_history = {}
_CLASSIFICATION_DECAY = float(os.getenv("CLASSIFICATION_DECAY", "0.82"))
_MIN_STABLE_CLASSIFICATION_FRAMES = int(os.getenv("MIN_STABLE_CLASSIFICATION_FRAMES", "4"))
_MAX_CLASSIFICATION_IDLE_SECONDS = float(os.getenv("MAX_CLASSIFICATION_IDLE_SECONDS", "12"))


def _mark_camera_connected():
    """Track online stability so we only alert when camera drops after normal operation."""
    now_ts = time.time()
    with _connection_state_lock:
        if _connection_state["stable_online_since"] is None:
            _connection_state["stable_online_since"] = now_ts

        if now_ts - _connection_state["stable_online_since"] >= CAMERA_ONLINE_STABLE_SECONDS:
            _connection_state["was_stable_online"] = True

        _connection_state["offline_since"] = None


def _handle_camera_disconnected(app_logger, reason):
    """Emit one offline alert per outage window (with cooldown) after camera was stable online."""
    stream_status["connected"] = False
    stream_status["last_error"] = str(reason or "Lost camera frame, reconnecting...")

    if not CAMERA_DISCONNECT_ALERT_ENABLED:
        return

    now_ts = time.time()
    should_notify = False

    with _connection_state_lock:
        if _connection_state["offline_since"] is None:
            _connection_state["offline_since"] = now_ts

        cooldown_ok = (
            now_ts - float(_connection_state["last_disconnect_alert_ts"])
            >= CAMERA_DISCONNECT_ALERT_COOLDOWN_SECONDS
        )

        if _connection_state["was_stable_online"] and cooldown_ok:
            should_notify = True
            _connection_state["last_disconnect_alert_ts"] = now_ts
            # Require the camera to become stable again before next disconnect alert.
            _connection_state["was_stable_online"] = False
            _connection_state["stable_online_since"] = None

    if should_notify:
        app_logger.warning("Camera connection lost after stable run. Dispatching Telegram alert...")
        alert_service.notify_camera_disconnect(
            camera_id=_camera_id,
            reason=stream_status["last_error"],
            camera_name=f"Camera {_camera_id}",
        )


def set_alert_event_callback(callback):
    """Register a callback to publish realtime alert events."""
    global _alert_event_callback
    _alert_event_callback = callback


def _sanitize_file_token(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)


def _detect_faces_in_bbox(frame, bbox, expand_ratio=None):
    """
    Detect faces within a YOLO bounding box using cascade classifier.
    Tries to extract face regions for better age detection.
    
    Returns: List of face regions (numpy arrays) or empty list if no faces found.
    """
    if FACE_CASCADE is None:
        return []
    
    if expand_ratio is None:
        expand_ratio = FACE_EXPAND_RATIO
    
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1] - 1, x2)
        y2 = min(frame.shape[0] - 1, y2)
        
        # Expand box slightly to catch partial faces
        w = x2 - x1
        h = y2 - y1
        exp_x = int(w * (expand_ratio - 1) / 2)
        exp_y = int(h * (expand_ratio - 1) / 2)
        
        x1_exp = max(0, x1 - exp_x)
        y1_exp = max(0, y1 - exp_y)
        x2_exp = min(frame.shape[1] - 1, x2 + exp_x)
        y2_exp = min(frame.shape[0] - 1, y2 + exp_y)
        
        roi = frame[y1_exp:y2_exp, x1_exp:x2_exp]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Detect faces in ROI with optimized parameters
        faces = FACE_CASCADE.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(CASCADE_MIN_FACE_SIZE, CASCADE_MIN_FACE_SIZE),
            maxSize=(roi.shape[1], roi.shape[0])
        )
        
        if len(faces) == 0:
            return []
        
        # Get the largest face (most likely the person in bbox)
        face_rects = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        largest_face = face_rects[0]
        
        x_f, y_f, w_f, h_f = largest_face
        face_region = roi[y_f:y_f+h_f, x_f:x_f+w_f]
        
        if face_region.size == 0:
            return []
        
        return [face_region]
    except Exception as e:
        logging.debug(f"Face detection error: {e}")
        return []


def _estimate_face_metrics(frame, bbox, expand_ratio=None):
    """
    Estimate face-to-body proportions for child/adult discrimination.
    Returns None when no face can be detected reliably.
    """
    if FACE_CASCADE is None:
        return None

    if expand_ratio is None:
        expand_ratio = FACE_EXPAND_RATIO

    try:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1] - 1, x2)
        y2 = min(frame.shape[0] - 1, y2)

        body_w = max(1, x2 - x1)
        body_h = max(1, y2 - y1)
        exp_x = int(body_w * (expand_ratio - 1) / 2)
        exp_y = int(body_h * (expand_ratio - 1) / 2)

        x1_exp = max(0, x1 - exp_x)
        y1_exp = max(0, y1 - exp_y)
        x2_exp = min(frame.shape[1] - 1, x2 + exp_x)
        y2_exp = min(frame.shape[0] - 1, y2 + exp_y)

        roi = frame[y1_exp:y2_exp, x1_exp:x2_exp]
        if roi.size == 0:
            return None

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        faces = FACE_CASCADE.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(CASCADE_MIN_FACE_SIZE, CASCADE_MIN_FACE_SIZE),
            maxSize=(roi.shape[1], roi.shape[0]),
        )

        if len(faces) == 0:
            return None

        x_f, y_f, w_f, h_f = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]
        face_region = roi[y_f:y_f + h_f, x_f:x_f + w_f]
        if face_region.size == 0:
            return None

        face_height_ratio = h_f / float(body_h)
        face_width_ratio = w_f / float(body_w)
        face_area_ratio = (w_f * h_f) / float(body_w * body_h)

        return {
            "face_region": face_region,
            "face_height_ratio": face_height_ratio,
            "face_width_ratio": face_width_ratio,
            "face_area_ratio": face_area_ratio,
        }
    except Exception as e:
        logging.debug(f"Face metrics error: {e}")
        return None


def _clamp(value, low, high):
    return max(low, min(high, value))


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_classifier_thresholds(frame_height, zone_settings=None):
    """
    Derive size thresholds from the current camera/zone instead of relying only on global constants.
    """
    extreme = CHILD_HEIGHT_THRESHOLD_EXTREME
    very_small = CHILD_HEIGHT_THRESHOLD_VERY_SMALL
    small = CHILD_HEIGHT_THRESHOLD_SMALL
    sensitivity = 0.75

    if zone_settings:
        sensitivity = _safe_float(zone_settings.get("sensitivity"), sensitivity)
        min_child_height_px = _safe_float(zone_settings.get("min_child_height"), 0.0)

        if frame_height > 0 and min_child_height_px > 0:
            calibrated_small = _clamp(min_child_height_px / float(frame_height), 0.16, 0.42)
            small = _clamp((small * 0.45) + (calibrated_small * 0.55), 0.18, 0.45)
            very_small = _clamp(small * 0.80, 0.14, small - 0.02)
            extreme = _clamp(very_small * 0.76, 0.10, very_small - 0.02)

    sensitivity_bias = _clamp((sensitivity - 0.75) * 0.10, -0.04, 0.05)
    small = _clamp(small + sensitivity_bias, 0.18, 0.48)
    very_small = _clamp(very_small + sensitivity_bias * 0.75, 0.14, small - 0.02)
    extreme = _clamp(extreme + sensitivity_bias * 0.55, 0.10, very_small - 0.02)

    return {
        "extreme": extreme,
        "very_small": very_small,
        "small": small,
        "sensitivity": sensitivity,
    }


def _expected_adult_height_ratio_for_foot(foot_y_ratio):
    """
    Approximate expected adult bbox height for a fixed pool camera based on
    where the person's feet land in the image. Lower in the frame means closer
    to the camera, so adults should appear taller there.
    """
    foot_y_ratio = _clamp(float(foot_y_ratio), 0.0, 1.0)
    return 0.16 + 0.54 * (foot_y_ratio ** 1.65)


def _cleanup_classification_history(now_ts=None):
    if now_ts is None:
        now_ts = time.time()

    with _classification_lock:
        expired_ids = [
            person_id
            for person_id, state in _classification_history.items()
            if now_ts - state.get("last_seen_ts", now_ts) > _MAX_CLASSIFICATION_IDLE_SECONDS
        ]
        for person_id in expired_ids:
            del _classification_history[person_id]


def _get_cached_instant_classification(person_id, frame_index):
    if not person_id:
        return None

    with _classification_lock:
        state = _classification_history.get(person_id)
        if not state:
            return None

        cached = state.get("cached_instant_result")
        cached_frame = int(state.get("cached_instant_frame", -9999))
        if cached and frame_index - cached_frame < CLASSIFICATION_REFRESH_FRAMES:
            return cached

    return None


def _store_cached_instant_classification(person_id, frame_index, result):
    if not person_id:
        return

    with _classification_lock:
        state = _classification_history.get(person_id)
        if state is None:
            state = {
                "child_votes": 0.0,
                "adult_votes": 0.0,
                "frames_seen": 0,
                "stable_label": result[0],
                "stable_confidence": float(result[2]),
                "best_age": result[1],
                "best_age_confidence": float(result[2] if result[1] is not None else 0.0),
                "last_seen_ts": time.time(),
            }
            _classification_history[person_id] = state

        state["cached_instant_result"] = result
        state["cached_instant_frame"] = int(frame_index)


def _update_temporal_classification(person_id, instant_type, instant_age, instant_confidence, details):
    """
    Smooth per-frame predictions across the same tracked person to reduce label flicker.
    """
    if not person_id:
        return instant_type, instant_age, instant_confidence

    now_ts = time.time()
    gemini_state = alert_service.get_person_classification(person_id) or {}

    with _classification_lock:
        state = _classification_history.get(person_id)
        if state is None:
            state = {
                "child_votes": 0.0,
                "adult_votes": 0.0,
                "frames_seen": 0,
                "stable_label": instant_type,
                "stable_confidence": float(instant_confidence),
                "best_age": instant_age,
                "best_age_confidence": float(instant_confidence if instant_age is not None else 0.0),
                "last_seen_ts": now_ts,
            }
            _classification_history[person_id] = state

        state["child_votes"] *= _CLASSIFICATION_DECAY
        state["adult_votes"] *= _CLASSIFICATION_DECAY
        state["frames_seen"] += 1
        state["last_seen_ts"] = now_ts

        vote_weight = _clamp(float(instant_confidence), 0.35, 1.15)
        if details.get("deepface_age") is not None:
            vote_weight += 0.18
        if details.get("height_ratio", 1.0) < details.get("small_threshold", CHILD_HEIGHT_THRESHOLD_SMALL):
            vote_weight += 0.08

        if instant_type == "CHILD":
            state["child_votes"] += vote_weight
        else:
            state["adult_votes"] += vote_weight

        if instant_age is not None and float(instant_confidence) >= state.get("best_age_confidence", 0.0):
            state["best_age"] = instant_age
            state["best_age_confidence"] = float(instant_confidence)

        gemini_called = bool(gemini_state.get("gemini_called"))
        gemini_is_child = gemini_state.get("is_child")
        if gemini_called and gemini_is_child is not None:
            if gemini_is_child:
                state["child_votes"] += 1.35
            else:
                state["adult_votes"] += 1.35

        score_gap = abs(state["child_votes"] - state["adult_votes"])
        total_votes = max(0.01, state["child_votes"] + state["adult_votes"])
        enough_history = state["frames_seen"] >= _MIN_STABLE_CLASSIFICATION_FRAMES

        if gemini_called and gemini_is_child is not None and enough_history:
            stable_label = "CHILD" if gemini_is_child else "ADULT"
        elif enough_history and score_gap >= 0.55:
            stable_label = "CHILD" if state["child_votes"] >= state["adult_votes"] else "ADULT"
        else:
            stable_label = state.get("stable_label", instant_type)

        stable_confidence = _clamp(0.52 + (score_gap / total_votes) * 0.38, 0.52, 0.97)

        if gemini_called and gemini_is_child is not None:
            stable_confidence = max(stable_confidence, 0.84)

        if not enough_history:
            stable_label = instant_type
            stable_confidence = max(stable_confidence * 0.85, float(instant_confidence))

        state["stable_label"] = stable_label
        state["stable_confidence"] = stable_confidence

        smoothed_age = state.get("best_age")
        if stable_label == "ADULT" and smoothed_age is not None and smoothed_age < 18:
            smoothed_age = None

        return stable_label, smoothed_age, stable_confidence


def _preprocess_image_for_deepface(img):
    """
    Preprocess image for better DeepFace accuracy.
    Applies CLAHE (Contrast Limited Adaptive Histogram Equalization) for better results.
    """
    if img.size == 0:
        return img
    
    try:
        # Convert to RGB if needed
        if len(img.shape) == 3 and img.shape[2] == 3:
            # BGR to RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img
        
        # Apply CLAHE for better contrast
        if len(img_rgb.shape) == 3:
            lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_clahe = clahe.apply(l)
            lab_clahe = cv2.merge([l_clahe, a, b])
            img_enhanced = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2RGB)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img_enhanced = clahe.apply(img_rgb)
        
        return img_enhanced
    except Exception as e:
        logging.debug(f"Preprocessing error: {e}")
        return img


def _get_deepface_age(face_img):
    """
    Extract age from face image using DeepFace.
    
    Returns: (age, confidence) or (None, 0) if detection fails
    """
    if not DEEPFACE_AVAILABLE or face_img is None or face_img.size == 0:
        return None, 0
    
    try:
        # Preprocess image
        face_enhanced = _preprocess_image_for_deepface(face_img)
        
        # Ensure proper size
        if face_enhanced.shape[0] < 20 or face_enhanced.shape[1] < 20:
            return None, 0
        
        # DeepFace analysis
        analysis = DeepFace.analyze(
            img_path=face_enhanced,
            actions=['age'],
            enforce_detection=False,
            silent=True
        )
        
        if analysis and len(analysis) > 0:
            age_value = analysis[0].get('age', None)
            if age_value is not None and isinstance(age_value, (int, float)):
                age = int(age_value)
                # DeepFace confidence is implicit (it tried and succeeded)
                confidence = 0.85
                logging.debug(f"DeepFace detected age: {age} (conf: {confidence})")
                return age, confidence
    except Exception as e:
        logging.debug(f"DeepFace analysis error: {type(e).__name__}: {str(e)[:100]}")
    
    return None, 0


def _prepare_zone_polygons(zones, frame_shape):
    frame_height, frame_width = frame_shape[:2]
    prepared = []

    for zone in zones:
        polygon_pixels = zone_service.build_zone_polygon_pixels(zone, frame_width, frame_height)
        if polygon_pixels is None:
            continue

        top_point = tuple(polygon_pixels[polygon_pixels[:, :, 1].argmin()][0])
        prepared.append({
            "id": zone.get("id", "UNKNOWN"),
            "name": zone.get("zone_name", zone.get("id", "Unknown Zone")),
            "polygon_pixels": polygon_pixels,
            "top_point": top_point,
            "min_child_height": zone.get("min_child_height"),
            "sensitivity": zone.get("sensitivity"),
        })

    return prepared


def _draw_zone_overlay(frame, prepared_zones):
    zone_color = (0, 165, 255)
    for zone in prepared_zones:
        cv2.polylines(frame, [zone["polygon_pixels"]], True, zone_color, 1)
        tx = max(0, int(zone["top_point"][0]) - 40)
        ty = max(20, int(zone["top_point"][1]) - 10)
        cv2.putText(frame, zone["name"], (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55, zone_color, 1)


def _should_trigger_alert(camera_id, zone_id, now_ts):
    key = f"{camera_id}:{zone_id}"
    last_ts = _last_alert_ts.get(key, 0.0)
    if now_ts - last_ts < ALERT_COOLDOWN_SECONDS:
        return False
    _last_alert_ts[key] = now_ts
    return True


def _persist_alert(frame, camera_id, zone_id, person_type="UNKNOWN", age=None, confidence=0.0):
    try:
        os.makedirs(ALERT_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe_zone = _sanitize_file_token(str(zone_id))
        filename = f"alert_cam{camera_id}_{safe_zone}_{stamp}.jpg"
        abs_path = os.path.join(ALERT_DIR, filename)
        rel_path = os.path.join("static", "alerts", filename).replace("\\", "/")

        if not cv2.imwrite(abs_path, frame):
            logging.warning(f"Failed to write alert image: {abs_path}")
            return

        execute_query(
            "INSERT INTO alerts (camera_id, zone_id, image_path) VALUES (%s, %s, %s)",
            (camera_id, zone_id, rel_path),
        )
        logging.info(f"Alert saved for camera={camera_id}, zone={zone_id}, person_type={person_type}, image={rel_path}")

        # ✅ Gửi Telegram với thông tin person_type + tuổi
        _notify_telegram(camera_id, zone_id, rel_path, person_type, age, confidence)

        if _alert_event_callback is not None:
            try:
                alert_msg = f"PHAT HIEN {person_type} XAM NHAP!"
                if age is not None:
                    alert_msg += f" (tuoi:{age})"
                
                _alert_event_callback({
                    "camera_id": camera_id,
                    "zone_id": zone_id,
                    "image_path": rel_path,
                    "person_type": person_type,
                    "age": age,
                    "message": alert_msg,
                    "created_at": time.time(),
                })
            except Exception as callback_error:
                logging.error(f"Error emitting realtime alert event: {callback_error}")
    except Exception as e:
        logging.error(f"Error persisting alert for camera={camera_id}, zone={zone_id}: {e}")


def _notify_telegram(camera_id, zone_id, image_path="", person_type="UNKNOWN", age=None, confidence=0.0):
    """Gọi Node backend để gửi Telegram notification"""
    node_url = os.getenv("ALERT_NOTIFY_URL", os.getenv("NODE_BACKEND_URL", "http://127.0.0.1:5000"))
    secret   = os.getenv("INTERNAL_SECRET", "your_internal_secret")
    try:
        # ✅ Tạo object_type rõ ràng với tuổi (nếu có)
        object_type = person_type
        if age is not None:
            object_type = f"{person_type} (tuoi:{age})"
        
        requests.post(
            f"{node_url}/api/alerts/notify",
            json={
                "object_type": object_type,
                "camera_name": f"Camera {camera_id}",
                "confidence":  float(confidence),
                "image_path":  image_path,
                "secret":      secret,
            },
            timeout=5
        ).raise_for_status()
        logging.info(f"Telegram notification sent for {person_type}")
    except Exception as e:
        logging.error(f"[Telegram notify error] {e}")


def classify_person_age(frame, bbox):
    """
    Phân loại tuổi: CHILD (<18), ADULT (>=18)
    ✨ Optimized Multi-Model: Face Detection + DeepFace + Morphology + Physical validation
    
    Strategy:
    1. Face Detection: Detect face region within YOLO bbox for better age estimation
    2. DeepFace: Extract age from detected face
    3. Physical: Height ratio, aspect ratio, body proportions as fallback
    4. Conflict resolution: Multi-source validation
    
    Returns: (person_type, age, confidence)
    """
    x1, y1, x2, y2 = bbox
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame.shape[1]-1, x2)
    y2 = min(frame.shape[0]-1, y2)
    
    crop_height = max(1, y2 - y1)
    crop_width = max(1, x2 - x1)
    frame_height = frame.shape[0]
    frame_width = frame.shape[1]
    
    height_ratio = crop_height / frame_height
    area_ratio = (crop_width * crop_height) / (frame_width * frame_height)
    aspect_ratio = crop_width / max(1, crop_height)
    
    detected_age = None
    deepface_age = None
    deepface_confidence = 0
    person_type = "ADULT"
    confidence = 0.5
    
    # ======== STEP 1: Try Face Detection + DeepFace ========
    face_regions = _detect_faces_in_bbox(frame, (x1, y1, x2, y2))
    
    if face_regions:
        # We found a face - use it for better age detection
        face_img = face_regions[0]
        deepface_age, deepface_confidence = _get_deepface_age(face_img)
        
        if deepface_age is not None:
            logging.info(f"✅ Face detected & analyzed: age={deepface_age}, conf={deepface_confidence:.2f}")
    else:
        # No face detected - try full body crop as fallback
        if height_ratio > 0.15:  # Only try on reasonably large detections
            body_crop = frame[y1:y2, x1:x2].copy()
            if body_crop.size > 0:
                deepface_age, deepface_confidence = _get_deepface_age(body_crop)
                if deepface_age is not None:
                    logging.debug(f"DeepFace from body crop: age={deepface_age}")
    
    # ======== STEP 2: Physical Heuristics (Optimized for pool scenarios) ========
    child_score = 0.0
    adult_score = 0.0
    
    # === HEIGHT RATIO (Most reliable indicator) ===
    # Pool scenario specific calibration:
    # - Children: typically 0.12-0.35 (they're smaller, closer to camera horizontally)
    # - Adults: typically 0.25-0.70 (full body visible, varying distances)
    
    if height_ratio < CHILD_HEIGHT_THRESHOLD_EXTREME:
        # Very small - ALMOST CERTAINLY CHILD
        child_score += 3.5
        logging.debug(f"  → height<{CHILD_HEIGHT_THRESHOLD_EXTREME}%: +3.5 CHILD (EXTREME SIZE)")
    elif height_ratio < CHILD_HEIGHT_THRESHOLD_VERY_SMALL:
        # Small - HIGH CONFIDENCE CHILD
        child_score += 2.5
        logging.debug(f"  → height<{CHILD_HEIGHT_THRESHOLD_VERY_SMALL}%: +2.5 CHILD (VERY SMALL)")
    elif height_ratio < CHILD_HEIGHT_THRESHOLD_SMALL:
        # Below average - likely CHILD
        child_score += 1.5
        logging.debug(f"  → height<{CHILD_HEIGHT_THRESHOLD_SMALL}%: +1.5 CHILD (SMALL-MED)")
    elif height_ratio < 0.40:
        # Medium - ambiguous, slight CHILD bias for safety
        child_score += 0.5
        logging.debug(f"  → height<40%: +0.5 CHILD (neutral)")
    elif height_ratio < 0.55:
        # Medium-large - neutral
        pass
    else:
        # Large - likely ADULT
        adult_score += 1.5
        logging.debug(f"  → height>=55%: +1.5 ADULT")
    
    # === AREA RATIO (Secondary indicator) ===
    if area_ratio < 0.015:
        child_score += 1.0
        logging.debug(f"  → area<1.5%: +1.0 CHILD (tiny)")
    elif area_ratio < 0.025:
        child_score += 0.5
        logging.debug(f"  → area<2.5%: +0.5 CHILD")
    elif area_ratio > 0.30:
        adult_score += 1.2
        logging.debug(f"  → area>30%: +1.2 ADULT (large)")
    elif area_ratio > 0.20:
        adult_score += 0.5
        logging.debug(f"  → area>20%: +0.5 ADULT")
    
    # === ASPECT RATIO (Body shape) ===
    # Children typically have wider shoulders relative to height when fully visible
    # But this varies, so lower weight
    if 0.35 < aspect_ratio < 0.55:  # Normal body width ratio
        if height_ratio < 0.32:
            child_score += 0.3
            logging.debug(f"  → aspect {aspect_ratio:.2f} + short: +0.3 CHILD")
        elif height_ratio > 0.50:
            adult_score += 0.2
            logging.debug(f"  → aspect {aspect_ratio:.2f} + tall: +0.2 ADULT")
    elif aspect_ratio < 0.3:
        # Very thin - could be posture
        pass
    elif aspect_ratio > 0.70:
        # Very wide - probably sitting/cropped, less reliable
        pass
    
    physical_is_child = child_score > adult_score
    
    logging.debug(f"Physical scoring: CHILD={child_score:.1f}, ADULT={adult_score:.1f}, is_child={physical_is_child}")
    
    # ======== STEP 3: Intelligent Fusion (DeepFace + Physical) ========
    
    # ✅ RULE 1: Extreme size = ALWAYS CHILD (override everything)
    if height_ratio < CHILD_HEIGHT_THRESHOLD_EXTREME:
        person_type = "CHILD"
        detected_age = None
        confidence = 0.92
        logging.info(f"🎯 EXTREME SIZE CHILD: height={height_ratio:.3f}")
        return person_type, detected_age, confidence
    
    # ✅ RULE 2: Very small -> Strong CHILD bias
    if CHILD_HEIGHT_THRESHOLD_EXTREME <= height_ratio < CHILD_HEIGHT_THRESHOLD_VERY_SMALL:
        person_type = "CHILD"
        detected_age = deepface_age if deepface_age and deepface_age < 18 else None
        confidence = 0.88
        logging.info(f"🎯 VERY SMALL CHILD: height={height_ratio:.3f}, df_age={deepface_age}")
        return person_type, detected_age, confidence
    
    # ✅ RULE 3: DeepFace is very reliable when available and high confidence
    if deepface_age is not None and deepface_confidence >= DEEPFACE_CONFIDENCE_THRESHOLD:
        deepface_is_child = deepface_age < 18
        
        # Age < 18 = CHILD (no exceptions)
        if deepface_is_child:
            person_type = "CHILD"
            detected_age = deepface_age
            confidence = 0.94  # Very high confidence
            logging.info(f"✅ DeepFace CHILD: age={deepface_age}, high confidence")
            return person_type, detected_age, confidence
        
        # Age >= 18 = ADULT (unless severe size conflict)
        if height_ratio < CHILD_HEIGHT_THRESHOLD_SMALL and physical_is_child:
            # Conflict: DeepFace says ADULT but size says CHILD (very small)
            logging.info(f"⚠️ CONFLICT: DeepFace age={deepface_age} vs tiny height={height_ratio:.3f}")
            # Trust size for safety in child detection
            if height_ratio < CHILD_HEIGHT_THRESHOLD_VERY_SMALL:
                person_type = "CHILD"
                detected_age = None
                confidence = 0.80
                logging.info(f"🔧 Override to CHILD due to extreme size")
                return person_type, detected_age, confidence
        
        # No conflict - trust DeepFace
        person_type = "ADULT"
        detected_age = deepface_age
        confidence = 0.91
        logging.info(f"✅ DeepFace ADULT: age={deepface_age}")
        return person_type, detected_age, confidence
    
    # ✅ RULE 4: Medium-sized (0.25-0.40) Use physical scoring
    if CHILD_HEIGHT_THRESHOLD_VERY_SMALL <= height_ratio < 0.40:
        if physical_is_child and child_score >= 2.0:
            # Strong physical evidence
            person_type = "CHILD"
            detected_age = deepface_age if deepface_age else None
            confidence = 0.78 if deepface_age else 0.72
            logging.info(f"💪 Physical CHILD (medium size): height={height_ratio:.3f}, score={child_score:.1f}")
            return person_type, detected_age, confidence
        elif adult_score >= 1.5:
            person_type = "ADULT"
            detected_age = deepface_age
            confidence = 0.75
            logging.info(f"💪 Physical ADULT (medium size): height={height_ratio:.3f}, score={adult_score:.1f}")
            return person_type, detected_age, confidence
    
    # ✅ RULE 5: Fallback for larger sizes - trust physical + DeepFace
    if deepface_age is not None:
        person_type = "CHILD" if deepface_age < 18 else "ADULT"
        detected_age = deepface_age
        confidence = 0.82
        logging.info(f"📊 Medium-confidence DeepFace: {person_type}, age={deepface_age}")
    else:
        # Pure physical heuristics
        if physical_is_child:
            person_type = "CHILD"
            confidence = 0.68
        else:
            person_type = "ADULT"
            confidence = 0.65
        logging.info(f"📊 Physical fallback: {person_type} (height={height_ratio:.3f}, score diff={abs(child_score-adult_score):.1f})")
    
    logging.info(f"✅ FINAL: {person_type} (h={height_ratio:.3f}, a={area_ratio:.4f}, age={detected_age}, conf={confidence:.2f})")
    
    return person_type, detected_age, confidence

def classify_person_age_v2(frame, bbox, zone_settings=None):
    """
    Updated classifier that keeps the original signal sources but calibrates size thresholds
    per zone and exposes metadata for temporal smoothing.
    """
    x1, y1, x2, y2 = bbox
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame.shape[1] - 1, x2)
    y2 = min(frame.shape[0] - 1, y2)

    crop_height = max(1, y2 - y1)
    crop_width = max(1, x2 - x1)
    frame_height = frame.shape[0]
    frame_width = frame.shape[1]

    height_ratio = crop_height / max(1, frame_height)
    area_ratio = (crop_width * crop_height) / max(1, (frame_width * frame_height))
    width_ratio = crop_width / max(1, frame_width)
    aspect_ratio = crop_width / max(1, crop_height)
    foot_y_ratio = y2 / max(1, frame_height)
    thresholds = _resolve_classifier_thresholds(frame_height, zone_settings)

    extreme_threshold = thresholds["extreme"]
    very_small_threshold = thresholds["very_small"]
    small_threshold = thresholds["small"]

    detected_age = None
    deepface_age = None
    deepface_confidence = 0.0
    deepface_source = None
    person_type = "ADULT"
    confidence = 0.5

    face_metrics = _estimate_face_metrics(frame, (x1, y1, x2, y2))
    if face_metrics:
        deepface_age, deepface_confidence = _get_deepface_age(face_metrics["face_region"])
        if deepface_age is not None:
            deepface_source = "face"
    elif height_ratio > 0.15:
        body_crop = frame[y1:y2, x1:x2].copy()
        if body_crop.size > 0:
            deepface_age, deepface_confidence = _get_deepface_age(body_crop)
            if deepface_age is not None:
                deepface_source = "body"

    child_score = 0.0
    adult_score = 0.0
    expected_adult_height_ratio = _expected_adult_height_ratio_for_foot(foot_y_ratio)
    relative_height_ratio = height_ratio / max(0.01, expected_adult_height_ratio)

    if height_ratio < extreme_threshold:
        child_score += 3.5
    elif height_ratio < very_small_threshold:
        child_score += 2.5
    elif height_ratio < small_threshold:
        child_score += 1.5
    elif height_ratio < 0.40:
        child_score += 0.5
    elif height_ratio >= 0.55:
        adult_score += 1.5

    # Perspective-aware height check: compare against an adult's expected apparent
    # size at the same foot position in the frame.
    if relative_height_ratio < 0.62:
        child_score += 2.2
    elif relative_height_ratio < 0.74:
        child_score += 1.4
    elif relative_height_ratio < 0.86:
        child_score += 0.6
    elif relative_height_ratio > 1.08:
        adult_score += 0.9
    elif relative_height_ratio > 0.96:
        adult_score += 0.3

    if area_ratio < 0.015:
        child_score += 1.0
    elif area_ratio < 0.025:
        child_score += 0.5
    elif area_ratio > 0.30:
        adult_score += 1.2
    elif area_ratio > 0.20:
        adult_score += 0.5

    if 0.35 < aspect_ratio < 0.55:
        if height_ratio < small_threshold:
            child_score += 0.3
        elif height_ratio > 0.50:
            adult_score += 0.2

    # A larger head-to-body ratio is a strong child cue, especially in close-camera pool scenes.
    if face_metrics:
        face_height_ratio = face_metrics["face_height_ratio"]
        face_area_ratio = face_metrics["face_area_ratio"]

        if face_height_ratio >= 0.25:
            child_score += 1.4
        elif face_height_ratio >= 0.18:
            child_score += 0.8
        elif face_height_ratio <= 0.16 and height_ratio >= 0.45:
            adult_score += 0.5

        if face_area_ratio >= 0.050:
            child_score += 0.6

        # Strong child prototype from body/face proportions.
        if (
            face_height_ratio >= 0.18
            and aspect_ratio < 0.50
            and area_ratio < 0.12
        ):
            child_score += 1.8
            adult_score = max(0.0, adult_score - 0.3)

    # Strong child prototype for this fixed pool camera:
    # lower-frame foot position + relatively short expected adult-normalized height
    # + narrow body shape should bias heavily toward CHILD.
    if (
        foot_y_ratio >= 0.70
        and relative_height_ratio < 0.98
        and aspect_ratio < 0.46
    ):
        child_score += 1.9
        adult_score = max(0.0, adult_score - 0.25)

    if (
        foot_y_ratio >= 0.74
        and relative_height_ratio < 0.90
    ):
        child_score += 1.2

    # Narrow body width is a strong cue for children in this fixed camera.
    if width_ratio < 0.12 and aspect_ratio < 0.40:
        child_score += 1.1
    elif width_ratio < 0.145 and foot_y_ratio >= 0.68 and aspect_ratio < 0.42:
        child_score += 0.7

    # Hard child prototype: close to camera, still narrow, and not visually tall enough
    # for an adult at the same foot position.
    if (
        foot_y_ratio >= 0.72
        and width_ratio < 0.125
        and aspect_ratio < 0.40
        and relative_height_ratio < 1.02
        and area_ratio < 0.11
    ):
        child_score += 2.1
        adult_score = max(0.0, adult_score - 0.5)

    # Prevent a near-camera child with a tall bbox from being pushed to ADULT too early.
    if height_ratio >= 0.50 and aspect_ratio < 0.40 and deepface_age is None:
        child_score += 0.7
        adult_score = max(0.0, adult_score - 0.4)

    physical_is_child = child_score > adult_score
    child_margin = child_score - adult_score

    deepface_adult_reliable = True
    if deepface_age is not None and deepface_age >= 18:
        face_height_ratio = face_metrics["face_height_ratio"] if face_metrics else None
        face_area_ratio = face_metrics["face_area_ratio"] if face_metrics else None

        if deepface_source != "face":
            deepface_adult_reliable = False
        if face_height_ratio is not None and face_height_ratio >= 0.18:
            deepface_adult_reliable = False
        if face_area_ratio is not None and face_area_ratio >= 0.045:
            deepface_adult_reliable = False
        if physical_is_child and child_margin >= 0.65:
            deepface_adult_reliable = False
        if height_ratio < max(small_threshold + 0.03, 0.34):
            deepface_adult_reliable = False
        if child_score >= 2.2:
            deepface_adult_reliable = False
        if foot_y_ratio >= 0.70 and relative_height_ratio < 0.98:
            deepface_adult_reliable = False

    if (
        face_metrics
        and face_metrics["face_height_ratio"] >= 0.18
        and aspect_ratio < 0.50
        and area_ratio < 0.12
        and child_score >= adult_score
    ):
        person_type = "CHILD"
        detected_age = deepface_age if deepface_age is not None and deepface_age < 18 else None
        confidence = 0.91
        details = {
            "height_ratio": height_ratio,
            "area_ratio": area_ratio,
            "aspect_ratio": aspect_ratio,
            "foot_y_ratio": foot_y_ratio,
            "expected_adult_height_ratio": expected_adult_height_ratio,
            "relative_height_ratio": relative_height_ratio,
            "deepface_age": deepface_age,
            "deepface_confidence": deepface_confidence,
            "deepface_source": deepface_source,
            "face_height_ratio": face_metrics["face_height_ratio"] if face_metrics else None,
            "face_area_ratio": face_metrics["face_area_ratio"] if face_metrics else None,
            "child_score": child_score,
            "adult_score": adult_score,
            "child_margin": child_margin,
            "deepface_adult_reliable": False,
            "small_threshold": small_threshold,
            "very_small_threshold": very_small_threshold,
            "extreme_threshold": extreme_threshold,
        }
        return person_type, detected_age, confidence, details

    if height_ratio < extreme_threshold:
        person_type = "CHILD"
        confidence = 0.92
    elif height_ratio < very_small_threshold:
        person_type = "CHILD"
        detected_age = deepface_age if deepface_age is not None and deepface_age < 18 else None
        confidence = 0.88
    elif deepface_age is not None and deepface_confidence >= DEEPFACE_CONFIDENCE_THRESHOLD:
        if deepface_age < 18:
            person_type = "CHILD"
            detected_age = deepface_age
            confidence = 0.94
        elif not deepface_adult_reliable:
            if physical_is_child:
                person_type = "CHILD"
                detected_age = None
                confidence = max(0.79, min(0.9, 0.72 + child_margin * 0.08))
            else:
                person_type = "ADULT"
                detected_age = None
                confidence = 0.60
        elif height_ratio < small_threshold and physical_is_child and height_ratio < very_small_threshold:
            person_type = "CHILD"
            confidence = 0.80
        else:
            person_type = "ADULT"
            detected_age = deepface_age
            confidence = 0.91
    elif very_small_threshold <= height_ratio < 0.40:
        if physical_is_child and child_score >= 2.0:
            person_type = "CHILD"
            detected_age = deepface_age if deepface_age is not None and deepface_age < 18 else None
            confidence = 0.78 if deepface_age is not None else 0.72
        elif adult_score >= 1.5:
            person_type = "ADULT"
            detected_age = deepface_age
            confidence = 0.75
    elif deepface_age is not None:
        if deepface_age >= 18 and not deepface_adult_reliable:
            person_type = "CHILD"
            detected_age = None
            confidence = 0.76 if child_score >= 1.8 else 0.66
        else:
            person_type = "CHILD" if deepface_age < 18 else "ADULT"
            detected_age = deepface_age if deepface_source == "face" or deepface_age < 18 else None
            confidence = 0.82 if deepface_source == "face" else 0.68
    else:
        person_type = "CHILD" if physical_is_child else "ADULT"
        confidence = 0.68 if physical_is_child else 0.65

    if (
        person_type == "ADULT"
        and deepface_age is None
        and foot_y_ratio >= 0.72
        and width_ratio < 0.125
        and aspect_ratio < 0.40
        and relative_height_ratio < 1.02
    ):
        person_type = "CHILD"
        detected_age = None
        confidence = max(confidence, 0.82)

    details = {
        "height_ratio": height_ratio,
        "area_ratio": area_ratio,
        "width_ratio": width_ratio,
        "aspect_ratio": aspect_ratio,
        "foot_y_ratio": foot_y_ratio,
        "expected_adult_height_ratio": expected_adult_height_ratio,
        "relative_height_ratio": relative_height_ratio,
        "deepface_age": deepface_age,
        "deepface_confidence": deepface_confidence,
        "deepface_source": deepface_source,
        "face_height_ratio": face_metrics["face_height_ratio"] if face_metrics else None,
        "face_area_ratio": face_metrics["face_area_ratio"] if face_metrics else None,
        "child_score": child_score,
        "adult_score": adult_score,
        "child_margin": child_margin,
        "deepface_adult_reliable": deepface_adult_reliable,
        "small_threshold": small_threshold,
        "very_small_threshold": very_small_threshold,
        "extreme_threshold": extreme_threshold,
    }

    return person_type, detected_age, confidence, details


def _draw_person_annotations(frame, detections, intrusion_detected=False):
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        box_color = det["box_color"]
        label = det["label"]
        person_type = det["person_type"]
        hit_zone_name = det.get("hit_zone_name")

        cx = float(x1 + x2) / 2.0
        cy = float(y2)

        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
        cv2.circle(frame, (int(cx), int(cy)), 4, box_color, -1)
        cv2.putText(
            frame,
            label,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            box_color,
            2,
        )

        if hit_zone_name:
            cv2.putText(
                frame,
                f"ZONE: {hit_zone_name} ({person_type})",
                (x1, min(frame.shape[0] - 10, y2 + 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
            )

    if intrusion_detected:
        cv2.putText(
            frame,
            "WARNING: INTRUSION DETECTED",
            (20, 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )


def build_rtsp_url(path: str) -> str:
    user = quote(CAM_USER, safe="")
    pwd = quote(CAM_PASS, safe="")
    return f"rtsp://{user}:{pwd}@{CAM_IP}:{CAM_PORT}{path}"


def load_zones_from_db(camera_id):
    """Load zones from database and cache them"""
    global _zones_cache
    try:
        zones = zone_service.load_zones(camera_id)
        with _zones_lock:
            _zones_cache = zones
        logging.info(f"Loaded {len(zones)} zones from database for camera {camera_id}")
        return zones
    except Exception as e:
        logging.error(f"Error loading zones from database: {e}")
        return []


def open_capture(app_logger):
    global _test_video_frame_interval
    if USE_TEST_VIDEO:
        video_path = TEST_VIDEO_PATH
        app_logger.info(f"Using test video source: {video_path}")
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            _handle_camera_disconnected(app_logger, f"Cannot open test video: {video_path}")
            return None

        stream_status["connected"] = True
        stream_status["last_error"] = ""
        stream_status["active_path"] = video_path
        _mark_camera_connected()

        source_fps = TEST_VIDEO_FORCE_FPS if TEST_VIDEO_FORCE_FPS > 0 else cap.get(cv2.CAP_PROP_FPS)
        if source_fps and source_fps > 0:
            _test_video_frame_interval = 1.0 / float(source_fps)
        else:
            _test_video_frame_interval = 1.0 / float(TARGET_FPS)

        app_logger.info(
            f"Test video playback FPS={source_fps:.2f} | frame_interval={_test_video_frame_interval:.4f}s"
        )
        return cap
    else:
        # Preserve RTSP connection logic for production camera mode.
        backends = [cv2.CAP_FFMPEG, cv2.CAP_ANY]

        for path in RTSP_PATHS:
            url = build_rtsp_url(path)

            for backend in backends:
                app_logger.info(f"Trying {url} with backend={backend}")
                cap = cv2.VideoCapture(url, backend)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not cap.isOpened():
                    cap.release()
                    continue

                ok, _ = cap.read()
                if not ok:
                    cap.release()
                    continue

                stream_status["connected"] = True
                stream_status["last_error"] = ""
                stream_status["active_path"] = path
                _mark_camera_connected()
                app_logger.info(f"Camera connected via {path} (backend={backend})")
                return cap

        _handle_camera_disconnected(app_logger, "Cannot open RTSP stream (check IP/user/pass/path)")
        return None


def _capture_worker(app_logger):
    global _raw_frame, _raw_id
    cap = None

    while True:
        loop_start = time.time()
        if cap is None or not cap.isOpened():
            cap = open_capture(app_logger)
            if cap is None:
                time.sleep(2)
                continue

        ok, frame = cap.read()
        if not ok:
            if USE_TEST_VIDEO:
                # Loop test video when EOF is reached to keep testing continuously.
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
                if not ok:
                    _handle_camera_disconnected(app_logger, "Cannot read test video frame, retrying...")
                    cap.release()
                    cap = None
                    time.sleep(1)
                    continue
            else:
                _handle_camera_disconnected(app_logger, "Lost camera frame, reconnecting...")
                cap.release()
                cap = None
                continue

        if stream_status.get("connected") is not True:
            stream_status["connected"] = True
            stream_status["last_error"] = ""
        _mark_camera_connected()

        frame = cv2.resize(frame, OUTPUT_SIZE)
        with _frame_lock:
            _raw_frame = frame
            _raw_id += 1

        if USE_TEST_VIDEO and _test_video_frame_interval > 0:
            elapsed = time.time() - loop_start
            if elapsed < _test_video_frame_interval:
                time.sleep(_test_video_frame_interval - elapsed)


def _infer_worker(app_logger):
    global _processed_frame
    try:
        model = YOLO(MODEL_PATH)
        stream_status["ai_ready"] = True
        app_logger.info("YOLO loaded")
    except Exception as e:
        stream_status["ai_ready"] = False
        stream_status["last_error"] = f"YOLO load error: {e}"
        app_logger.error(stream_status["last_error"])
        return

    # Initialize video and alert services
    video_service.initialize_video_service()
    app_logger.info("✅ Video Service initialized")

    # Load zones from database
    zones = load_zones_from_db(_camera_id)
    app_logger.info(f"Initial zone load: {len(zones)} zones")
    
    last_id = -1
    infer_cycle = 0
    last_visual_detections = []
    last_intrusion_detected = False
    load_zones_interval = 300  # Reload zones every 5 minutes (300 seconds)
    last_zones_load = time.time()
    
    while True:
        current_time = time.time()
        if current_time - last_zones_load > load_zones_interval:
            zones = load_zones_from_db(_camera_id)
            last_zones_load = current_time
        
        with _frame_lock:
            if _raw_frame is None or _raw_id == last_id:
                frame = None
                fid = last_id
            else:
                frame = _raw_frame.copy()
                fid = _raw_id

        if frame is None:
            time.sleep(0.005)
            continue

        try:
            infer_cycle += 1
            processed = frame.copy()
            prepared_zones = _prepare_zone_polygons(zones, processed.shape)

            # Prepare zones by ID for two-stage detection logic
            zones_by_id = {}
            for zone in prepared_zones:
                zones_by_id[zone["id"]] = zone

            if zones_by_id:
                video_service.draw_zone_visualization(processed, zones_by_id)

            should_run_inference = (
                infer_cycle == 1
                or infer_cycle % INFERENCE_EVERY_N_FRAMES == 0
                or not last_visual_detections
            )

            if should_run_inference:
                results = model.predict(
                    source=frame,
                    conf=CONF_THRES,
                    classes=[PERSON_CLASS_ID],
                    verbose=False
                )

                intrusion_detected = False
                visual_detections = []
                yolo_result = results[0]
                boxes = yolo_result.boxes
            else:
                boxes = None

            if should_run_inference and boxes is not None and len(boxes) > 0:
                xyxy = boxes.xyxy.cpu().numpy()
                confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.array([0.0] * len(xyxy))
                analysis_frame = frame.copy()

                for idx, bbox in enumerate(xyxy):
                    x1, y1, x2, y2 = bbox.astype(int)
                    x1 = int(np.clip(x1, 0, processed.shape[1] - 1))
                    y1 = int(np.clip(y1, 0, processed.shape[0] - 1))
                    x2 = int(np.clip(x2, 0, processed.shape[1] - 1))
                    y2 = int(np.clip(y2, 0, processed.shape[0] - 1))

                    # ========================================
                    # TWO-STAGE ALERT DETECTION (NEW)
                    # ========================================
                    try:
                        video_service.process_detection(
                            frame=analysis_frame,
                            camera_id=_camera_id,
                            bbox=(x1, y1, x2, y2),
                            zones_by_id=zones_by_id,
                            frame_width=processed.shape[1],
                            frame_height=processed.shape[0]
                        )
                    except Exception as e:
                        app_logger.warning(f"Two-stage detection error: {e}")
                    # ========================================

                    # ✅ Phân loại tuổi: CHILD vs ADULT
                    # Foot-point for intrusion logic.
                    cx = float(x1 + x2) / 2.0
                    cy = float(y2)

                    hit_zone = None
                    for zone in prepared_zones:
                        collision = cv2.pointPolygonTest(zone["polygon_pixels"], (cx, cy), False)
                        if collision >= 0:
                            hit_zone = zone
                            break

                    is_intruding = hit_zone is not None
                    person_id = video_service.get_tracked_person_id(
                        (x1, y1, x2, y2),
                        processed.shape[1],
                        processed.shape[0],
                    )
                    cached_result = _get_cached_instant_classification(person_id, infer_cycle)
                    if cached_result is None:
                        cached_result = classify_person_age_v2(
                            analysis_frame,
                            (x1, y1, x2, y2),
                            zone_settings=hit_zone,
                        )
                        _store_cached_instant_classification(person_id, infer_cycle, cached_result)

                    instant_type, instant_age, instant_conf, classify_details = cached_result
                    person_type, age, age_conf = _update_temporal_classification(
                        person_id,
                        instant_type,
                        instant_age,
                        instant_conf,
                        classify_details,
                    )
                    alert_service.set_person_local_classification(person_id, person_type, age_conf)
                    
                    # ✅ Color khác nhau cho CHILD (đỏ) vs ADULT (xanh)
                    if person_type == "CHILD":
                        box_color = (0, 0, 255)  # Red for CHILD
                        label_prefix = "CHILD"
                    else:
                        box_color = (0, 255, 0)  # Green for ADULT
                        label_prefix = "ADULT"
                    
                    if is_intruding and person_type == "CHILD":
                        box_color = (0, 0, 255)  # Red warning for intrusion
                        label_suffix = " WARNING"
                        intrusion_detected = True
                    elif is_intruding:
                        box_color = (0, 255, 0)
                        label_suffix = ""
                    else:
                        label_suffix = ""
                    
                    # ✅ Build label: "CHILD/ADULT conf [age] ⚠️ WARNING"
                    if age is not None:
                        label = f"{label_prefix} {confs[idx]:.2f} (age:{age}){label_suffix}"
                    else:
                        label = f"{label_prefix} {confs[idx]:.2f}{label_suffix}"

                    visual_detections.append(
                        {
                            "bbox": (x1, y1, x2, y2),
                            "box_color": box_color,
                            "label": label,
                            "person_type": person_type,
                            "hit_zone_name": hit_zone["name"] if is_intruding else None,
                        }
                    )

            # Increment frame counter for video service
            if should_run_inference:
                last_visual_detections = visual_detections
                last_intrusion_detected = intrusion_detected
                video_service.increment_frame_counter()
                _cleanup_classification_history()

            _draw_person_annotations(
                processed,
                last_visual_detections,
                intrusion_detected=last_intrusion_detected,
            )

            with _frame_lock:
                _processed_frame = processed
            last_id = fid
        except Exception as e:
            stream_status["last_error"] = f"Inference error: {e}"
            app_logger.error(stream_status["last_error"])
            time.sleep(0.1)


def start_workers(app_logger):
    global _workers_started
    if _workers_started:
        return

    t1 = threading.Thread(target=_capture_worker, args=(app_logger,), daemon=True, name="capture_worker")
    t2 = threading.Thread(target=_infer_worker, args=(app_logger,), daemon=True, name="infer_worker")
    t1.start()
    t2.start()
    _workers_started = True


def _placeholder_frame(text: str):
    img = np.zeros((OUTPUT_SIZE[1], OUTPUT_SIZE[0], 3), dtype=np.uint8)
    cv2.putText(img, text, (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    return img


def capture_manual_snapshot(camera_id=1, mode="processed"):
    snapshot_mode = str(mode or "processed").strip().lower()
    if snapshot_mode not in ("processed", "raw"):
        raise ValueError("mode must be 'processed' or 'raw'")

    with _frame_lock:
        if snapshot_mode == "processed" and _processed_frame is not None:
            frame = _processed_frame.copy()
        elif _raw_frame is not None:
            frame = _raw_frame.copy()
        else:
            frame = None

    if frame is None:
        raise RuntimeError("No camera frame available")

    os.makedirs(MANUAL_SNAPSHOT_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"manual_snapshot_cam{int(camera_id)}_{snapshot_mode}_{stamp}.jpg"
    abs_path = os.path.join(MANUAL_SNAPSHOT_DIR, filename)
    rel_path = os.path.join("static", "manual_snapshots", filename).replace("\\", "/")

    if not cv2.imwrite(abs_path, frame):
        raise RuntimeError(f"Failed to save snapshot to {abs_path}")

    return {
        "mode": snapshot_mode,
        "filename": filename,
        "absolute_path": abs_path,
        "relative_path": rel_path,
    }


def gen_frames(app_logger):
    start_workers(app_logger)
    frame_interval = 1.0 / TARGET_FPS

    while True:
        t0 = time.time()

        with _frame_lock:
            frame = _processed_frame.copy() if _processed_frame is not None else (
                _raw_frame.copy() if _raw_frame is not None else None
            )

        if frame is None:
            frame = _placeholder_frame(f"No camera frame | {stream_status.get('last_error', '')}")

        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

        dt = time.time() - t0
        if dt < frame_interval:
            time.sleep(frame_interval - dt)
