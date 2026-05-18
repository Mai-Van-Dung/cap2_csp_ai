"""
Video Service - Handle two-stage alert detection and zone management
Manages Zone_A (buffer) and Zone_B (dangerous) zones for child safety
"""

import os
import cv2
import logging
import hashlib
from datetime import datetime
from dotenv import load_dotenv
import alert_service

# Load environment variables
BASE_DIR = os.path.dirname(__file__)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Configure logging
logger = logging.getLogger(__name__)

# Zone configuration
ZONE_A_ID = os.getenv("ZONE_A_ID", "zone_a")  # Buffer zone
ZONE_B_ID = os.getenv("ZONE_B_ID", "zone_b")  # Dangerous zone
ALERT_DIR = os.path.join(os.path.dirname(__file__), "static", "alerts")
_ZONE_A_HINTS = ("zone_a", "zone-a", "zone a", "buffer", "outer", "safe")
_ZONE_B_HINTS = ("zone_b", "zone-b", "zone b", "danger", "dangerous", "inner", "risk")
PERSON_MATCH_MAX_DIST = float(os.getenv("PERSON_MATCH_MAX_DIST", "0.10"))
PERSON_MATCH_MAX_FRAME_GAP = int(os.getenv("PERSON_MATCH_MAX_FRAME_GAP", "20"))
STAGE_A_SNAPSHOT_COOLDOWN = float(os.getenv("STAGE_A_SNAPSHOT_COOLDOWN", "3"))
STAGE_B_SNAPSHOT_COOLDOWN = float(os.getenv("STAGE_B_SNAPSHOT_COOLDOWN", "8"))
ONLY_ALERT_WHEN_SINGLE_PERSON = os.getenv("ONLY_ALERT_WHEN_SINGLE_PERSON", "true").strip().lower() in ("1", "true", "yes", "on")
ACTIVE_ZONE_COUNT_MAX_FRAME_AGE = int(os.getenv("ACTIVE_ZONE_COUNT_MAX_FRAME_AGE", "3"))

# Frame tracking for person detection
_person_frame_history = {}  # {person_hash: {frame_count, last_seen, position}}
_frame_counter = 0
_tracking_lock = None
_stage_snapshot_cooldowns = {}


def initialize_video_service():
    """Initialize video service components"""
    import threading
    global _tracking_lock
    _tracking_lock = threading.Lock()
    
    # Create alert directory if not exists
    os.makedirs(ALERT_DIR, exist_ok=True)
    logger.info("✅ Video Service initialized")


def _create_person_hash(bbox, frame_width, frame_height):
    """
    Create a unique hash for a detected person based on position
    Hash is location-sensitive to track movement between zones
    """
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0 / frame_width  # Normalized center X
    cy = (y1 + y2) / 2.0 / frame_height  # Normalized center Y
    height = (y2 - y1) / frame_height  # Normalized height
    
    # Create hash based on position and size (with tolerance for movement)
    # Round to 1 decimal place to keep the id stable across small frame jitter
    position_string = f"{round(cx, 1)}_{round(cy, 1)}_{round(height, 1)}"
    return hashlib.md5(position_string.encode()).hexdigest()[:12]


def _bbox_center_normalized(bbox, frame_width, frame_height):
    x1, y1, x2, y2 = bbox
    cx = ((x1 + x2) / 2.0) / max(1.0, float(frame_width))
    cy = ((y1 + y2) / 2.0) / max(1.0, float(frame_height))
    return cx, cy


def _match_existing_person_id(cx, cy):
    now_frame = _frame_counter
    best_id = None
    best_dist = 999.0

    for pid, data in _person_frame_history.items():
        if now_frame - data.get("last_seen", -9999) > PERSON_MATCH_MAX_FRAME_GAP:
            continue

        last_center = data.get("last_center")
        if not last_center:
            continue

        dx = float(last_center[0]) - float(cx)
        dy = float(last_center[1]) - float(cy)
        dist = (dx * dx + dy * dy) ** 0.5

        if dist < PERSON_MATCH_MAX_DIST and dist < best_dist:
            best_dist = dist
            best_id = pid

    return best_id


def get_tracked_person_id(bbox, frame_width, frame_height):
    """
    Resolve the current tracked person ID for a bbox without mutating tracking state.
    Returns None if no matching tracked person exists yet.
    """
    if _tracking_lock is None:
        return None

    cx, cy = _bbox_center_normalized(bbox, frame_width, frame_height)
    with _tracking_lock:
        return _match_existing_person_id(cx, cy)


def _count_recent_persons_in_zone(zone_id):
    if _tracking_lock is None:
        return 0

    count = 0
    now_frame = _frame_counter
    with _tracking_lock:
        for data in _person_frame_history.values():
            if now_frame - int(data.get("last_seen", -9999)) > ACTIVE_ZONE_COUNT_MAX_FRAME_AGE:
                continue
            if data.get("active_zone_roles", {}).get(zone_id):
                count += 1

    return count


def _allow_stage_snapshot(camera_id, stage_key, person_id=None):
    now_ts = datetime.now().timestamp()
    cooldown = STAGE_A_SNAPSHOT_COOLDOWN if stage_key == "zone_a" else STAGE_B_SNAPSHOT_COOLDOWN
    keys = [f"{camera_id}:{stage_key}:{person_id or 'global'}"]

    if stage_key == "zone_b":
        keys.insert(0, f"{camera_id}:{stage_key}:global")

    for key in keys:
        last_ts = _stage_snapshot_cooldowns.get(key, 0.0)
        if now_ts - last_ts < cooldown:
            return False

    for key in keys:
        _stage_snapshot_cooldowns[key] = now_ts

    return True


def _save_snapshot(frame, camera_id, zone_id, person_id):
    """Save snapshot of detected person to file"""
    try:
        os.makedirs(ALERT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        safe_zone = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(zone_id))
        filename = f"snapshot_cam{camera_id}_{safe_zone}_{person_id}_{timestamp}.jpg"
        filepath = os.path.join(ALERT_DIR, filename)
        
        if cv2.imwrite(filepath, frame):
            rel_path = os.path.join("static", "alerts", filename).replace("\\", "/")
            logger.info(f"📸 Snapshot saved: {rel_path}")
            return rel_path
        else:
            logger.error(f"Failed to save snapshot: {filepath}")
            return None
    except Exception as e:
        logger.error(f"Error saving snapshot: {e}")
        return None


def _get_zone_name(zone_id):
    """Get friendly name for zone"""
    zone_map = {
        ZONE_A_ID: "🔵 Zone_A (Buffer)",
        ZONE_B_ID: "🔴 Zone_B (Danger)",
    }
    return zone_map.get(zone_id, f"Zone_{zone_id}")


def _normalize_zone_text(value):
    return "".join(ch.lower() if ch.isalnum() else " " for ch in str(value)).strip()


def _infer_zone_role(zone):
    zone_id = str(zone.get("id", ""))
    zone_name = str(zone.get("name", zone_id))
    zone_text = f"{_normalize_zone_text(zone_id)} {_normalize_zone_text(zone_name)}"

    if any(hint in zone_text for hint in _ZONE_A_HINTS):
        return ZONE_A_ID
    if any(hint in zone_text for hint in _ZONE_B_HINTS):
        return ZONE_B_ID
    return None


def _resolve_zone_roles(prepared_zones):
    resolved = {}
    unresolved = []

    for zone in prepared_zones:
        role = _infer_zone_role(zone)
        if role in (ZONE_A_ID, ZONE_B_ID) and role not in resolved.values():
            resolved[zone["id"]] = role
        else:
            unresolved.append(zone)

    if len(prepared_zones) == 1 and unresolved and ZONE_B_ID not in resolved.values():
        # Safety-first: with only one configured zone, treat it as dangerous zone.
        zone = unresolved.pop(0)
        resolved[zone["id"]] = ZONE_B_ID

    if ZONE_A_ID not in resolved.values() and unresolved:
        zone = unresolved.pop(0)
        resolved[zone["id"]] = ZONE_A_ID

    if ZONE_B_ID not in resolved.values() and unresolved:
        zone = unresolved.pop(0)
        resolved[zone["id"]] = ZONE_B_ID

    return resolved


def detect_zone_entry(bbox, zone_polygon_pixels, frame_width, frame_height):
    """
    Detect if a person bbox overlaps with a zone polygon
    Returns True if person's foot point is inside zone
    """
    try:
        x1, y1, x2, y2 = bbox
        # Use foot point (center bottom) for zone detection
        cx = float(x1 + x2) / 2.0
        cy = float(y2)  # Foot point
        
        collision = cv2.pointPolygonTest(zone_polygon_pixels, (cx, cy), False)
        return collision >= 0
    except Exception as e:
        logger.debug(f"Zone detection error: {e}")
        return False


def process_detection(frame, camera_id, bbox, zones_by_id, frame_width, frame_height):
    """
    Process a single YOLO detection and apply two-stage alert logic
    
    Args:
        frame: Current video frame
        camera_id: Camera identifier
        bbox: YOLO bounding box [x1, y1, x2, y2]
        zones_by_id: Dictionary of zones indexed by ID {zone_id: zone_data}
        frame_width: Frame width in pixels
        frame_height: Frame height in pixels
    """
    if _tracking_lock is None:
        return
    
    # Create or reuse person identifier based on nearest tracked center.
    cx_norm, cy_norm = _bbox_center_normalized(bbox, frame_width, frame_height)
    
    with _tracking_lock:
        person_id = _match_existing_person_id(cx_norm, cy_norm)
        if person_id is None:
            person_id = _create_person_hash(bbox, frame_width, frame_height)

        # Update person tracking
        if person_id not in _person_frame_history:
            _person_frame_history[person_id] = {
                "first_seen": _frame_counter,
                "last_seen": _frame_counter,
                "last_center": (cx_norm, cy_norm),
                "zones_entered": {},
                "active_zone_roles": {},
                "classification_sent": False,
            }
        
        _person_frame_history[person_id]["last_seen"] = _frame_counter
        _person_frame_history[person_id]["last_center"] = (cx_norm, cy_norm)
    
    # Extract person crop for Gemini classification
    x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame_width - 1, x2)
    y2 = min(frame_height - 1, y2)
    
    person_crop = frame[y1:y2, x1:x2].copy()

    zone_roles = _resolve_zone_roles(list(zones_by_id.values())) if zones_by_id else {}
    
    # Check zone entry
    for zone_id, zone_data in zones_by_id.items():
        polygon_pixels = zone_data.get("polygon_pixels")
        zone_name = zone_data.get("name", zone_id)
        zone_role = zone_roles.get(zone_id)
        
        if polygon_pixels is None:
            continue
        
        is_in_zone = detect_zone_entry(bbox, polygon_pixels, frame_width, frame_height)
        
        with _tracking_lock:
            person_data = _person_frame_history[person_id]
            was_in_zone = person_data["active_zone_roles"].get(zone_id, False)
            person_data["active_zone_roles"][zone_id] = is_in_zone

        zone_entered = is_in_zone and not was_in_zone
        zone_exited = (not is_in_zone) and was_in_zone

        if zone_exited:
            with _tracking_lock:
                person_data = _person_frame_history.get(person_id)
                if person_data:
                    person_data["zones_entered"].pop(zone_id, None)
        
        if zone_entered:
            with _tracking_lock:
                person_data = _person_frame_history[person_id]
                person_data["zones_entered"][zone_id] = {
                    "frame": _frame_counter,
                    "alert_sent": False,
                    "zone_a_snapshot_sent": False,
                    "zone_b_snapshot_sent": False,
                }

        # TWO-STAGE LOGIC (processed while person remains inside zone, not only on first enter)
        if not is_in_zone:
            continue

        if zone_role == ZONE_A_ID:
            if zone_entered:
                logger.info(f"🔵 STAGE 1 - {_get_zone_name(zone_id)}: Person {person_id} detected")

            person_state = alert_service.get_person_classification(person_id) or {}
            if person_state.get("gemini_called"):
                continue

            with _tracking_lock:
                zone_state = (_person_frame_history.get(person_id, {}).get("zones_entered", {}).get(zone_id) or {})
                if zone_state.get("zone_a_snapshot_sent"):
                    continue

            if not _allow_stage_snapshot(camera_id, "zone_a", person_id=person_id):
                continue

            snapshot_path = _save_snapshot(person_crop, camera_id, zone_id, person_id)
            if snapshot_path:
                with _tracking_lock:
                    tracked = _person_frame_history.get(person_id, {}).get("zones_entered", {}).get(zone_id)
                    if tracked is not None:
                        tracked["zone_a_snapshot_sent"] = True
                alert_service.process_two_stage_alert(
                    camera_id=camera_id,
                    person_id=person_id,
                    zone_id=zone_id,
                    bbox=bbox,
                    image_path=os.path.join(BASE_DIR, snapshot_path),
                    zone_name=zone_name,
                    current_stage="zone_a"
                )

        elif zone_role == ZONE_B_ID:
            if zone_entered:
                logger.warning(f"🔴 STAGE 2 - {_get_zone_name(zone_id)}: Person {person_id} escalated")

            if alert_service.checkSupervisedStatus(camera_id):
                logger.info(
                    "Supervised mode enabled for camera %s: skip Zone_B snapshot/alert for person %s",
                    camera_id,
                    person_id,
                )
                continue

            if ONLY_ALERT_WHEN_SINGLE_PERSON:
                persons_in_zone = _count_recent_persons_in_zone(zone_id)
                if persons_in_zone != 1:
                    logger.info(
                        "Zone_B alert suppressed for person %s in zone %s because persons_in_zone=%s",
                        person_id,
                        zone_id,
                        persons_in_zone,
                    )
                    continue

            with _tracking_lock:
                zone_state = (_person_frame_history.get(person_id, {}).get("zones_entered", {}).get(zone_id) or {})
                if zone_state.get("zone_b_snapshot_sent"):
                    continue

            if not _allow_stage_snapshot(camera_id, "zone_b", person_id=person_id):
                continue

            snapshot_path = _save_snapshot(person_crop, camera_id, zone_id, person_id)
            if snapshot_path:
                with _tracking_lock:
                    tracked = _person_frame_history.get(person_id, {}).get("zones_entered", {}).get(zone_id)
                    if tracked is not None:
                        tracked["zone_b_snapshot_sent"] = True
                alert_service.process_two_stage_alert(
                    camera_id=camera_id,
                    person_id=person_id,
                    zone_id=zone_id,
                    bbox=bbox,
                    image_path=os.path.join(BASE_DIR, snapshot_path),
                    zone_name=zone_name,
                    current_stage="zone_b"
                )


def draw_zone_visualization(frame, zones_by_id):
    """
    Draw zone polygons on frame for overlaid visualization
    Zone_A in blue, Zone_B in red
    """
    for zone_id, zone_data in zones_by_id.items():
        polygon_pixels = zone_data.get("polygon_pixels")
        if polygon_pixels is None:
            continue
        
        # Color: Blue for Zone_A, Red for Zone_B
        if zone_id == ZONE_A_ID:
            color = (255, 165, 0)  # Blue
            alpha = 0.2
        elif zone_id == ZONE_B_ID:
            color = (0, 0, 255)  # Red
            alpha = 0.3
        else:
            color = (0, 165, 255)  # Orange
            alpha = 0.15
        
        # Draw filled polygon with transparency
        overlay = frame.copy()
        cv2.polylines(overlay, [polygon_pixels], True, color, 2)
        cv2.fillPoly(overlay, [polygon_pixels], color)
        
        # Blend with original frame
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        # Add zone label
        zone_name = zone_data.get("name", zone_id)
        top_point = tuple(polygon_pixels[polygon_pixels[:, :, 1].argmin()][0])
        tx = max(0, int(top_point[0]) - 40)
        ty = max(20, int(top_point[1]) - 10)
        cv2.putText(frame, zone_name, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def cleanup_old_persons(max_frames_without_detection=150):
    """
    Remove persons not detected for a while to prevent memory bloat
    
    Args:
        max_frames_without_detection: Frames before removing person from tracking
    """
    if _tracking_lock is None:
        return
    
    global _frame_counter
    
    with _tracking_lock:
        expired = []
        for person_id, data in _person_frame_history.items():
            frames_since_seen = _frame_counter - data["last_seen"]
            if frames_since_seen > max_frames_without_detection:
                expired.append(person_id)
        
        for person_id in expired:
            del _person_frame_history[person_id]
            logger.debug(f"Cleaned up tracking for person {person_id}")


def increment_frame_counter():
    """Increment the global frame counter"""
    global _frame_counter
    _frame_counter += 1
    
    # Cleanup every 300 frames (~20 seconds at 15 FPS)
    if _frame_counter % 300 == 0:
        cleanup_old_persons()


def get_tracking_status():
    """Get current tracking status"""
    if _tracking_lock is None:
        return {"error": "Video service not initialized"}
    
    with _tracking_lock:
        return {
            "frame_count": _frame_counter,
            "persons_tracked": len(_person_frame_history),
            "rate_limit_status": alert_service.get_rate_limit_status(),
        }


def reset_tracking():
    """Reset all tracking data"""
    if _tracking_lock is None:
        return
    
    global _frame_counter, _person_frame_history
    with _tracking_lock:
        _person_frame_history.clear()
        _frame_counter = 0
    logger.info("✅ Tracking data reset")
