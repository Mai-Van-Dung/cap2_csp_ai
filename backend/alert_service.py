"""
Alert Service - Handle Gemini API integration for two-stage alert logic
Implements silent verification at Zone_A and emergency alerts at Zone_B
"""

import os
import time
import threading
import logging
import json
import base64
import requests
import re
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from db_connector import execute_query

# Load environment variables
BASE_DIR = os.path.dirname(__file__)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Configure logging
logger = logging.getLogger(__name__)

# Gemini API Configuration
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    logger.info("✅ google-generativeai loaded successfully")
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("⚠️ google-generativeai not installed - falling back to safe mode")

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_COOLDOWN = int(os.getenv("GEMINI_API_COOLDOWN", "4"))  # Seconds between API calls
MAX_GEMINI_CALLS_PER_MINUTE = int(os.getenv("MAX_GEMINI_CALLS_PER_MINUTE", "15"))
ZONE_B_CLASSIFICATION_WAIT_SECONDS = float(os.getenv("ZONE_B_CLASSIFICATION_WAIT_SECONDS", "3"))

# Initialize Gemini API
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"✅ Gemini API configured with model: {GEMINI_MODEL}")
else:
    GEMINI_AVAILABLE = False
    logger.warning("⚠️ Gemini API key not configured or library not available")


class GeminiAPIRateLimiter:
    """Rate limiter for Gemini API calls"""
    
    def __init__(self, max_calls_per_minute=15):
        self.max_calls_per_minute = max_calls_per_minute
        self.call_timestamps = []
        self.lock = threading.Lock()
    
    def can_call(self):
        """Check if API call is allowed"""
        now = time.time()
        with self.lock:
            # Remove timestamps older than 1 minute
            self.call_timestamps = [ts for ts in self.call_timestamps if now - ts < 60]
            
            if len(self.call_timestamps) >= self.max_calls_per_minute:
                return False
            
            return True
    
    def record_call(self):
        """Record an API call"""
        with self.lock:
            self.call_timestamps.append(time.time())
    
    def get_remaining_calls(self):
        """Get remaining calls in current minute"""
        now = time.time()
        with self.lock:
            self.call_timestamps = [ts for ts in self.call_timestamps if now - ts < 60]
            return max(0, self.max_calls_per_minute - len(self.call_timestamps))


class PersonTracker:
    """Track detected persons and their Gemini classifications"""
    
    def __init__(self):
        self.persons = {}  # {person_id: {bbox, is_child, timestamp, stage}}
        self.lock = threading.Lock()
    
    def add_or_update_person(self, person_id, bbox, stage="zone_a"):
        """Add or update person tracking"""
        with self.lock:
            if person_id not in self.persons:
                self.persons[person_id] = {
                    "bbox": bbox,
                    "is_child": None,  # Will be set by Gemini after stage 1
                    "timestamp": time.time(),
                    "stage": stage,
                    "gemini_called": False,
                    "classification_pending": False,
                    "alert_sent": False,
                    "classification_retry_ts": 0.0,
                    "last_alert_zone_id": None,
                    "last_alert_ts": 0.0,
                }
            else:
                self.persons[person_id]["bbox"] = bbox
                self.persons[person_id]["stage"] = stage

    def mark_person_classification_pending(self, person_id):
        with self.lock:
            if person_id in self.persons:
                self.persons[person_id]["classification_pending"] = True
                self.persons[person_id]["timestamp"] = time.time()

    def clear_person_classification_pending(self, person_id):
        with self.lock:
            if person_id in self.persons:
                self.persons[person_id]["classification_pending"] = False

    def set_person_classification_retry(self, person_id, retry_after_ts):
        with self.lock:
            if person_id in self.persons:
                self.persons[person_id]["classification_retry_ts"] = float(retry_after_ts)
    
    def mark_person_as_classified(self, person_id, is_child):
        """Mark person as classified by Gemini"""
        with self.lock:
            if person_id in self.persons:
                self.persons[person_id]["is_child"] = is_child
                self.persons[person_id]["gemini_called"] = True
                self.persons[person_id]["classification_pending"] = False
                self.persons[person_id]["timestamp"] = time.time()
                logger.info(f"🎯 Person {person_id} classified as {'CHILD' if is_child else 'ADULT'}")
    
    def mark_person_alert_sent(self, person_id):
        """Mark that alert was sent for this person"""
        with self.lock:
            if person_id in self.persons:
                self.persons[person_id]["alert_sent"] = True
    
    def get_person(self, person_id):
        """Get person data"""
        with self.lock:
            return self.persons.get(person_id)
    
    def remove_old_persons(self, timeout_seconds=300):
        """Remove persons not seen for a while"""
        now = time.time()
        with self.lock:
            expired = [
                pid for pid, data in self.persons.items()
                if now - data["timestamp"] > timeout_seconds
            ]
            for pid in expired:
                del self.persons[pid]
                logger.debug(f"Removed expired person tracking: {pid}")
    
    def cleanup(self):
        """Clean up tracking data"""
        self.remove_old_persons()


# Global instances
rate_limiter = GeminiAPIRateLimiter(MAX_GEMINI_CALLS_PER_MINUTE)
person_tracker = PersonTracker()
last_api_call_time = 0
api_call_lock = threading.Lock()
gemini_backoff_until = 0.0
_alert_event_callback = None
_alert_dispatch_pool = ThreadPoolExecutor(max_workers=4)


def set_alert_event_callback(callback):
    """Register callback for realtime alert events (Socket.IO)."""
    global _alert_event_callback
    _alert_event_callback = callback


def _persist_local_alert(camera_id, zone_id, image_path, confidence):
    """Persist child intrusion alert into DB for Events History page."""
    try:
        execute_query(
            "INSERT INTO alerts (camera_id, zone_id, object_type, confidence, image_path) VALUES (%s, %s, %s, %s, %s)",
            (camera_id, zone_id, "Child", float(confidence), image_path),
        )
        logger.info(f"✅ Local alert persisted: camera={camera_id}, zone={zone_id}, image={image_path}")
    except Exception as e:
        logger.error(f"Failed to persist local alert: {e}")


def _normalize_alert_image_paths(image_path):
    """
    Normalize image path for cross-project transport.

    Returns:
        tuple[str|None, str|None]: (relative_or_url_path, public_image_url)
    """
    if not image_path:
        return None, None

    raw = str(image_path).replace("\\", "/")
    lower_raw = raw.lower()

    if lower_raw.startswith("http://") or lower_raw.startswith("https://"):
        return raw, raw

    marker = "static/alerts/"
    marker_idx = lower_raw.find(marker)

    if marker_idx >= 0:
        relative_path = raw[marker_idx:]
    else:
        relative_path = raw.lstrip("/")

    public_base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    public_url = f"{public_base}/{relative_path}" if public_base else None

    return relative_path, public_url


def _emit_realtime_alert(camera_id, zone_id, image_path, confidence, image_url=None):
    """Emit realtime alert to connected frontend clients."""
    if _alert_event_callback is None:
        return

    try:
        _alert_event_callback({
            "camera_id": camera_id,
            "zone_id": zone_id,
            "image_path": image_path,
            "image_url": image_url,
            "object_type": "Child",
            "confidence": float(confidence),
            "message": "CHILD INTRUSION ALERT",
            "created_at": time.time(),
        })
    except Exception as e:
        logger.error(f"Failed to emit realtime alert event: {e}")


def _post_alert_to_relay(base_url, payload):
    """Post alert payload to external relay endpoint."""
    response = requests.post(
        f"{base_url.rstrip('/')}/api/alerts/notify",
        json=payload,
        timeout=(2, 3),
    )
    response.raise_for_status()
    return response


def _dispatch_external_alert(base_urls, payload):
    """Try relay endpoints without blocking the camera loop."""
    last_error = None
    for base_url in base_urls:
        try:
            response = _post_alert_to_relay(base_url, payload)
            logger.info(f"✅ Alert notification sent successfully to {base_url} ({response.status_code})")
            return True
        except Exception as candidate_error:
            last_error = candidate_error
            logger.warning(f"Notify candidate failed ({base_url}): {candidate_error}")

    if last_error is not None:
        logger.error(f"Failed to send alert notification: {last_error}")
    return False


def encode_image_to_base64(image_path):
    """Convert image file to base64 string"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding image to base64: {e}")
        return None


def analyze_person_with_gemini(image_path, person_id):
    """
    Call Gemini API to analyze if person is child or adult
    Returns: (is_child, confidence) or (None, 0) on failure
    Falls back to safe mode (assume child) on error
    """
    global last_api_call_time, gemini_backoff_until
    
    if not GEMINI_AVAILABLE:
        logger.warning(f"Gemini not available for person {person_id}, assuming CHILD (safe mode)")
        return True, 0.5  # Fallback: assume child for safety

    now_ts = time.time()
    if now_ts < gemini_backoff_until:
        logger.warning(f"Gemini in cooldown/backoff until {gemini_backoff_until:.0f}, skip person {person_id}")
        return None, 0
    
    # Check rate limiting
    if not rate_limiter.can_call():
        logger.warning(f"API rate limit reached, deferring classification for person {person_id}")
        return None, 0
    
    # Check cooldown between API calls
    with api_call_lock:
        now = time.time()
        if now - last_api_call_time < GEMINI_API_COOLDOWN:
            wait_time = GEMINI_API_COOLDOWN - (now - last_api_call_time)
            logger.debug(f"Cooldown in effect, waiting {wait_time:.1f}s for person {person_id}")
            time.sleep(wait_time)
        last_api_call_time = time.time()
    
    try:
        # Verify image exists
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None, 0
        
        # Upload image to Gemini
        logger.info(f"📤 Uploading snapshot for person {person_id} to Gemini...")
        file = genai.upload_file(image_path)
        logger.info(f"✅ File uploaded successfully: {file.uri}")
        
        # Create model instance
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Prepare prompt
        prompt = """Hãy phân tích hình ảnh này. Đối tượng là trẻ em (child) hay người lớn (adult)? 
        Dựa vào các đặc điểm như: chiều cao, kích thước cơ thể, khuôn mặt, tư thế.
        Trả về kết quả JSON ONLY (không có text khác): {"identity": "child" hoặc "adult", "confidence": 0.0 đến 1.0}"""
        
        # Call Gemini API
        logger.info(f"🔍 Analyzing image for person {person_id}...")
        response = model.generate_content([prompt, file])
        
        rate_limiter.record_call()
        
        # Parse response
        try:
            response_text = response.text.strip()
        except Exception:
            response_text = ""

        if not response_text:
            logger.warning(f"Empty/blocked Gemini response for person {person_id}")
            return None, 0

        logger.info(f"📝 Gemini response: {response_text}")
        
        # Extract JSON from response
        try:
            # Try to find JSON in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                identity = result.get("identity", "").lower()
                confidence = float(result.get("confidence", 0.5))
                
                is_child = identity == "child"
                logger.info(f"✅ Gemini Result: {identity.upper()} (confidence: {confidence:.2f}) for person {person_id}")
                
                return is_child, confidence
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e} | Response: {response_text}")
        
        # Fallback on parse error
        return True, 0.5
        
    except Exception as e:
        err_text = str(e)
        retry_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", err_text, flags=re.IGNORECASE)
        if retry_match:
            retry_seconds = float(retry_match.group(1))
            gemini_backoff_until = max(gemini_backoff_until, time.time() + retry_seconds)
            logger.warning(f"Gemini quota backoff {retry_seconds:.1f}s activated")
            logger.warning(f"Gemini temporary failure for person {person_id}, deferring classification")
            return None, 0

        logger.error(f"Gemini API error for person {person_id}: {type(e).__name__}: {str(e)}")
        # FALLBACK: Assume child for safety priority
        logger.warning(f"⚠️ Fallback: Marking person {person_id} as CHILD due to API error (safety priority)")
        return True, 0.5


def async_classify_person(image_path, person_id):
    """
    Asynchronously classify person using Gemini (runs in background thread)
    """
    def _classify_worker():
        is_child, confidence = analyze_person_with_gemini(image_path, person_id)
        if is_child is not None:
            person_tracker.mark_person_as_classified(person_id, is_child)
        else:
            person_tracker.clear_person_classification_pending(person_id)
            retry_after = max(time.time() + GEMINI_API_COOLDOWN, gemini_backoff_until)
            person_tracker.set_person_classification_retry(person_id, retry_after)
            logger.debug(f"Skipped classification for {person_id} due to rate limiting")
    
    # Run classification in background thread to avoid blocking livestream
    thread = threading.Thread(target=_classify_worker, daemon=True)
    thread.start()


def notify_alert(camera_id, zone_id, image_path, person_id, is_child):
    """
    Send alert notification via Telegram (called when child enters Zone_B)
    Only sends alert if person is classified as CHILD
    """
    if not is_child:
        logger.info(f"Skipping alert for person {person_id} - classified as ADULT")
        return

    existing_person = person_tracker.get_person(person_id) or {}
    last_alert_zone = existing_person.get("last_alert_zone_id")
    last_alert_age = existing_person.get("last_alert_ts", 0.0)
    now_ts = time.time()

    # Avoid repeating the same alert while the person remains in the same zone.
    if last_alert_zone == zone_id and now_ts - last_alert_age < 30:
        logger.debug(f"Skipping duplicate alert for person {person_id} in zone {zone_id}")
        return

    relay_image_path, relay_image_url = _normalize_alert_image_paths(image_path)

    # Always keep local audit trail/realtime feed active even if external notifier fails.
    alert_confidence = 0.95
    _persist_local_alert(camera_id, zone_id, relay_image_path, alert_confidence)
    _emit_realtime_alert(camera_id, zone_id, relay_image_path, alert_confidence, image_url=relay_image_url)

    with person_tracker.lock:
        tracked = person_tracker.persons.get(person_id)
        if tracked is not None:
            tracked["last_alert_zone_id"] = zone_id
            tracked["last_alert_ts"] = now_ts

    try:
        preferred_notify_url = os.getenv("ALERT_NOTIFY_URL", "").strip()
        fallback_notify_url = os.getenv("NODE_BACKEND_URL", "http://localhost:5003").strip()
        secret = os.getenv("INTERNAL_SECRET", "")
        notify_candidates = []
        if preferred_notify_url:
            notify_candidates.append(preferred_notify_url)
        if fallback_notify_url and fallback_notify_url not in notify_candidates:
            notify_candidates.append(fallback_notify_url)

        if not notify_candidates:
            raise RuntimeError("No ALERT_NOTIFY_URL/NODE_BACKEND_URL configured")

        if not secret:
            logger.warning("INTERNAL_SECRET is empty; external project may reject alert payload")
        
        alert_message = f"🔴 CHILD INTRUSION ALERT at Zone {zone_id}"
        
        logger.info(f"📢 Sending Telegram alert for CHILD at camera {camera_id}, zone {zone_id}")
        payload = {
            "object_type": "CHILD (HIGH RISK)",
            "camera_name": f"Camera {camera_id}",
            "confidence": alert_confidence,
            "image_path": relay_image_path,
            "image_url": relay_image_url,
            "image_urls": [relay_image_url] if relay_image_url else [],
            "secret": secret,
            "message": alert_message,
            "source": "python-backend",
        }

        # Dispatch in background so slow Telegram delivery cannot block alert processing.
        _alert_dispatch_pool.submit(_dispatch_external_alert, notify_candidates, payload)
    except Exception as e:
        logger.error(f"Failed to send alert notification: {e}")
    finally:
        # Mark as sent to prevent repeated flood while person remains inside Zone_B.
        person_tracker.mark_person_alert_sent(person_id)



def process_two_stage_alert(camera_id, person_id, zone_id, bbox, image_path, zone_name, current_stage):
    """
    Process two-stage alert logic:
    - Stage 1 (Zone_A): Silently classify person using Gemini, save classification
    - Stage 2 (Zone_B): Check classification, send alert if CHILD
    """
    
    # Update person tracking
    person_tracker.add_or_update_person(person_id, bbox, stage=current_stage)
    
    # Stage 1: Zone_A - Silent classification
    if current_stage == "zone_a":
        person_data = person_tracker.get_person(person_id)
        
        retry_ts = float((person_data or {}).get("classification_retry_ts") or 0.0)
        if person_data and not person_data.get("gemini_called") and not person_data.get("classification_pending"):
            if retry_ts and time.time() < retry_ts:
                logger.debug(f"Zone_A classification paused for person {person_id} until {retry_ts:.0f}")
                return
            # First time in Zone_A - classify asynchronously
            logger.info(f"🔵 Stage 1 - Zone_A: Classifying person {person_id} (silent mode)")
            person_tracker.mark_person_classification_pending(person_id)
            async_classify_person(image_path, person_id)
    
    # Stage 2: Zone_B - Emergency alert if child
    elif current_stage == "zone_b":
        person_data = person_tracker.get_person(person_id)
        
        if person_data:
            is_child = person_data.get("is_child")
            alert_sent = person_data.get("alert_sent")
            
            if is_child is None:
                now_ts = time.time()
                first_seen_ts = person_data.get("zone_b_first_seen")
                if first_seen_ts is None:
                    person_data["zone_b_first_seen"] = now_ts
                    logger.warning(f"⚠️ Stage 2 - Zone_B: Waiting classification for person {person_id}")
                    return

                if now_ts - first_seen_ts < ZONE_B_CLASSIFICATION_WAIT_SECONDS:
                    logger.warning(f"⚠️ Stage 2 - Zone_B: Grace wait ({now_ts - first_seen_ts:.1f}s) for person {person_id}")
                    return

                # Classification still not available after grace period -> safe fallback
                logger.warning(f"⚠️ Stage 2 - Zone_B: Classification timeout for person {person_id}, assuming CHILD (safe)")
                is_child = True
            
            if is_child and not alert_sent:
                logger.warning(f"🔴 Stage 2 - Zone_B: CHILD INTRUSION - Person {person_id} entered dangerous zone!")
                notify_alert(camera_id, zone_id, image_path, person_id, is_child=True)
            elif not is_child:
                logger.info(f"✅ Stage 2 - Zone_B: Adult (person {person_id}) - no alert needed")
    
    # Periodic cleanup
    person_tracker.cleanup()


def get_person_classification(person_id):
    person_data = person_tracker.get_person(person_id)
    if person_data:
        return {
            "is_child": person_data.get("is_child"),
            "gemini_called": person_data.get("gemini_called"),
            "stage": person_data.get("stage"),
            "alert_sent": person_data.get("alert_sent"),
        }
    return None


def get_rate_limit_status():
    """Get current rate limit status"""
    return {
        "remaining_calls": rate_limiter.get_remaining_calls(),
        "max_calls_per_minute": MAX_GEMINI_CALLS_PER_MINUTE,
        "total_tracked_persons": len(person_tracker.persons),
    }
