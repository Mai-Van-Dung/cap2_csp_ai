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
CONF_THRES = 0.5
PERSON_CLASS_ID = 0
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "10"))
ALERT_DIR = os.path.join(os.path.dirname(__file__), "static", "alerts")

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


def _sanitize_file_token(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)


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


def _persist_alert(frame, camera_id, zone_id):
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
        logging.info(f"Alert saved for camera={camera_id}, zone={zone_id}, image={rel_path}")
    except Exception as e:
        logging.error(f"Error persisting alert for camera={camera_id}, zone={zone_id}: {e}")


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
                    if is_intruding:
                        intrusion_detected = True
                        box_color = (0, 0, 255)
                        label = f"person {confs[idx]:.2f} WARNING"
                    else:
                        box_color = (0, 255, 0)
                        label = f"person {confs[idx]:.2f}"

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
                            f"ZONE: {hit_zone['name']}",
                            (x1, min(processed.shape[0] - 10, y2 + 18)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 0, 255),
                            1,
                        )
                        now_ts = time.time()
                        if _should_trigger_alert(_camera_id, hit_zone["id"], now_ts):
                            _persist_alert(processed, _camera_id, hit_zone["id"])

            if intrusion_detected:
                cv2.putText(
                    processed,
                    "WARNING: Person intrusion detected",
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