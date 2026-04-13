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

OUTPUT_SIZE = (1280, 720)
TARGET_FPS = 15
JPEG_QUALITY = 80

# --- YOLO config ---
MODEL_PATH = "yolov8n.pt"
CONF_THRES = float(os.getenv("YOLO_CONF_THRES", "0.45"))  # Slightly lower to catch smaller objects
PERSON_CLASS_ID = 0
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "10"))
ALERT_DIR = os.path.join(os.path.dirname(__file__), "static", "alerts")

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
    node_url = os.getenv("NODE_BACKEND_URL", "http://localhost:5003")
    secret   = os.getenv("INTERNAL_SECRET", "mot_chuoi_bi_mat_bat_ky_vd_abc123xyz")
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
        )
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
            stream_status["connected"] = False
            stream_status["last_error"] = f"Cannot open test video: {video_path}"
            return None

        stream_status["connected"] = True
        stream_status["last_error"] = ""
        stream_status["active_path"] = video_path

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
                app_logger.info(f"Camera connected via {path} (backend={backend})")
                return cap

        stream_status["connected"] = False
        stream_status["last_error"] = "Cannot open RTSP stream (check IP/user/pass/path)"
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
                    stream_status["connected"] = False
                    stream_status["last_error"] = "Cannot read test video frame, retrying..."
                    cap.release()
                    cap = None
                    time.sleep(1)
                    continue
            else:
                stream_status["connected"] = False
                stream_status["last_error"] = "Lost camera frame, reconnecting..."
                cap.release()
                cap = None
                continue

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

    # Load zones from database
    zones = load_zones_from_db(_camera_id)
    app_logger.info(f"Initial zone load: {len(zones)} zones")
    
    last_id = -1
    load_zones_interval = 300  # Reload zones every 5 minutes (300 seconds)
    last_zones_load = time.time()
    
    while True:
        # Periodically reload zones from database
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
            results = model.predict(
                source=frame,
                conf=CONF_THRES,
                classes=[PERSON_CLASS_ID],
                verbose=False
            )

            processed = frame.copy()
            prepared_zones = _prepare_zone_polygons(zones, processed.shape)
            _draw_zone_overlay(processed, prepared_zones)

            intrusion_detected = False
            yolo_result = results[0]
            boxes = yolo_result.boxes

            if boxes is not None and len(boxes) > 0:
                xyxy = boxes.xyxy.cpu().numpy()
                confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.array([0.0] * len(xyxy))

                for idx, bbox in enumerate(xyxy):
                    x1, y1, x2, y2 = bbox.astype(int)
                    x1 = int(np.clip(x1, 0, processed.shape[1] - 1))
                    y1 = int(np.clip(y1, 0, processed.shape[0] - 1))
                    x2 = int(np.clip(x2, 0, processed.shape[1] - 1))
                    y2 = int(np.clip(y2, 0, processed.shape[0] - 1))

                    # ✅ Phân loại tuổi: CHILD vs ADULT
                    person_type, age, age_conf = classify_person_age(processed, (x1, y1, x2, y2))
                    
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
                    
                    # ✅ Color khác nhau cho CHILD (đỏ) vs ADULT (xanh)
                    if person_type == "CHILD":
                        box_color = (0, 0, 255)  # Red for CHILD
                        label_prefix = "CHILD"
                        intrusion_detected = True  # Trẻ em luôn cảnh báo
                    else:
                        box_color = (0, 255, 0)  # Green for ADULT
                        label_prefix = "ADULT"
                    
                    if is_intruding:
                        box_color = (0, 0, 255)  # Red warning for intrusion
                        label_suffix = " WARNING"
                    else:
                        label_suffix = ""
                    
                    # ✅ Build label: "CHILD/ADULT conf [age] ⚠️ WARNING"
                    if age is not None:
                        label = f"{label_prefix} {confs[idx]:.2f} (age:{age}){label_suffix}"
                    else:
                        label = f"{label_prefix} {confs[idx]:.2f}{label_suffix}"

                    cv2.rectangle(processed, (x1, y1), (x2, y2), box_color, 2)
                    cv2.circle(processed, (int(cx), int(cy)), 4, box_color, -1)
                    cv2.putText(
                        processed,
                        label,
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        box_color,
                        2,
                    )

                    if is_intruding:
                        cv2.putText(
                            processed,
                            f"ZONE: {hit_zone['name']} ({person_type})",
                            (x1, min(processed.shape[0] - 10, y2 + 18)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 0, 255),
                            1,
                        )
                        now_ts = time.time()
                        if _should_trigger_alert(_camera_id, hit_zone["id"], now_ts):
                            _persist_alert(processed, _camera_id, hit_zone["id"], person_type, age, float(confs[idx]))

            if intrusion_detected:
                cv2.putText(
                    processed,
                    "⚠️ WARNING: INTRUSION DETECTED",
                    (20, 36),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
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