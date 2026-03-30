import os
import time
import cv2
import threading
import numpy as np
from urllib.parse import quote
from ultralytics import YOLO
import zone_service
import logging

# --- Camera config ---
CAM_IP = os.getenv("CAM_IP", "192.168.1.50")
CAM_PORT = int(os.getenv("CAM_PORT", "554"))
CAM_USER = os.getenv("CAM_USER", "admin")
CAM_PASS = os.getenv("CAM_PASS", "Dungpro123@")
RTSP_PATHS = ["/H.264", "/h264_stream", "/live0", "/Streaming/Channels/101"]

OUTPUT_SIZE = (1280, 720)
TARGET_FPS = 15
JPEG_QUALITY = 80

# --- YOLO config ---
MODEL_PATH = "yolov8n.pt"
CONF_THRES = 0.5
PERSON_CLASS_ID = 0

stream_status = {
    "connected": False,
    "last_error": "",
    "active_path": "",
    "camera_ip": CAM_IP,
    "ai_ready": False,
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


def draw_zones_on_frame(frame, zones):
    """
    Draw zones on the video frame
    
    Args:
        frame: OpenCV frame
        zones: List of zone objects with coordinates and zone_name
    
    Returns:
        Modified frame with zones drawn
    """
    if not zones:
        return frame
    
    frame_height, frame_width = frame.shape[:2]
    orange_color = (0, 165, 255)  # BGR format
    
    for zone in zones:
        vertices = zone.get("coordinates", [])
        zone_name = zone.get("zone_name", "Unknown")
        
        if not vertices or len(vertices) < 2:
            continue
        
        try:
            # Convert normalized coordinates (0-1) to pixel coordinates
            pixel_vertices = []
            for vertex in vertices:
                if isinstance(vertex, (list, tuple)) and len(vertex) >= 2:
                    x = int(float(vertex[0]) * frame_width)
                    y = int(float(vertex[1]) * frame_height)
                    pixel_vertices.append([x, y])
                elif isinstance(vertex, dict) and "x" in vertex and "y" in vertex:
                    x = int(float(vertex["x"]) * frame_width)
                    y = int(float(vertex["y"]) * frame_height)
                    pixel_vertices.append([x, y])
            
            if len(pixel_vertices) >= 2:
                # Draw polygon with thin lines
                pts = np.array(pixel_vertices, dtype=np.int32)
                cv2.polylines(frame, [pts], True, orange_color, 1)
                
                # Draw zone name text above the polygon
                if pixel_vertices:
                    # Find top point for text placement
                    avg_x = sum(v[0] for v in pixel_vertices) // len(pixel_vertices)
                    min_y = min(v[1] for v in pixel_vertices)
                    text_pos = (max(0, avg_x - 40), max(20, min_y - 10))
                    
                    cv2.putText(
                        frame,
                        zone_name,
                        text_pos,
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        orange_color,
                        1
                    )
        except Exception as e:
            logging.warning(f"Error drawing zone {zone_name}: {e}")
            continue
    
    return frame


def open_capture(app_logger):
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
        if cap is None or not cap.isOpened():
            cap = open_capture(app_logger)
            if cap is None:
                time.sleep(2)
                continue

        ok, frame = cap.read()
        if not ok:
            stream_status["connected"] = False
            stream_status["last_error"] = "Lost camera frame, reconnecting..."
            cap.release()
            cap = None
            continue

        frame = cv2.resize(frame, OUTPUT_SIZE)
        with _frame_lock:
            _raw_frame = frame
            _raw_id += 1


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
            plotted = results[0].plot()
            
            # Draw zones on the processed frame
            plotted = draw_zones_on_frame(plotted, zones)

            with _frame_lock:
                _processed_frame = plotted
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