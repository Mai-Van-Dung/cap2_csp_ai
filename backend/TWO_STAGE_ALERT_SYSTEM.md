# Two-Stage Alert System - Detailed Documentation

## Overview

The Two-Stage Alert System is an advanced child safety detection system that uses **Gemini AI** to classify persons as children or adults in a two-phase process:

1. **Stage 1 (Zone_A - Buffer Zone)**: Silent classification using Gemini AI
2. **Stage 2 (Zone_B - Danger Zone)**: Emergency alerts only for classified children

This design prioritizes **safety** by defaulting to treat unclassified persons as children if any error occurs.

---

## System Architecture

### Component 1: `alert_service.py`

**Purpose**: Handles Gemini API integration, person tracking, and alert notifications.

#### Key Classes

**GeminiAPIRateLimiter**

- Implements token bucket rate limiting (15 calls/minute)
- Prevents API throttling and quota exhaustion
- Methods: `can_call()`, `record_call()`, `get_remaining_calls()`

**PersonTracker**

- Maintains state of detected persons across frames
- Tracks classification status, detection history, alert status
- Thread-safe with lock-based synchronization
- Methods:
  - `add_or_update_person()`: Create or update person entry
  - `mark_person_as_classified()`: Store Gemini result
  - `mark_person_alert_sent()`: Track alert delivery
  - `remove_old_persons()`: Cleanup old entries (>5 minutes old)

#### Key Functions

**analyze_person_with_gemini(image_path, person_id)**

```
Purpose: Call Gemini API to classify if person is child/adult
Input: Image file path and person ID
Output: (is_child: bool, confidence: float)

Procedure:
1. Check rate limit - if exceeded, return None
2. Wait for cooldown (4 seconds min between calls)
3. Upload image to Gemini
4. Send classification prompt
5. Parse JSON response
6. Fallback: Return (True, 0.5) on any error - SAFETY PRIORITY

Prompt Used:
"Hãy phân tích hình ảnh này. Đối tượng là trẻ em (child) hay người lớn (adult)?
Trả về JSON: {"identity": "child/adult", "confidence": 0.0-1.0}"
```

**async_classify_person(image_path, person_id)**

- Runs `analyze_person_with_gemini()` in background thread
- Non-blocking - returns immediately
- Result stored in PersonTracker when complete

**notify_alert(camera_id, zone_id, image_path, person_id, is_child)**

- Sends Telegram notification via Node.js backend
- Only sends if `is_child=True`
- Includes image snapshot and metadata

**process_two_stage_alert(camera_id, person_id, zone_id, image_path, current_stage)**

- Main orchestrator function
- Routes to Stage 1 or Stage 2 handling
- Thread-safe person state management

---

### Component 2: `video_service.py`

**Purpose**: Handles detection, zone management, and two-stage trigger logic.

#### Key Functions

**process_detection(frame, camera_id, bbox, zones_by_id, frame_width, frame_height)**

```
Main detection processor called for each YOLO detection

Procedure:
1. Create person_id hash from normalized position
2. Check zone overlap using cv2.pointPolygonTest
3. If Zone_A detected:
   - Save snapshot
   - Call async_classify_person() (non-blocking)
   - Wait for classification result (will be ready by Stage 2)
4. If Zone_B detected:
   - Check stored classification from Stage 1
   - If CHILD or pending → Call notify_alert()
   - If ADULT → Skip alert
```

**\_create_person_hash(bbox, frame_width, frame_height)**

- Creates location-sensitive hash for person identification
- Normalizes coordinates (0-1 range)
- Groups nearby detections as same person within tolerance

**detect_zone_entry(bbox, zone_polygon_pixels, frame_width, frame_height)**

- Detects polygon overlap using `cv2.pointPolygonTest()`
- Uses person's "foot point" (center-bottom) for detection
- Returns: True if person overlaps with zone

**\_save_snapshot(frame, camera_id, zone_id, person_id)**

- Saves cropped person image to `static/alerts/`
- Filename format: `snapshot_cam{cam_id}_{zone_id}_{person_id}_{timestamp}.jpg`
- Returns relative path for database storage

**increment_frame_counter()**

- Called once per frame
- Triggers cleanup every 300 frames (>20 seconds at 15 FPS)
- Removes persons not seen for >150 frames

---

### Component 3: Modified `camera_service.py`

**Changes Made:**

1. **Imports**

   ```python
   import video_service
   import alert_service
   ```

2. **Initialization in `_infer_worker()`**

   ```python
   video_service.initialize_video_service()
   ```

3. **Detection Loop Integration**

   ```python
   # For each YOLO detection:
   video_service.process_detection(
       frame=processed,
       camera_id=_camera_id,
       bbox=(x1, y1, x2, y2),
       zones_by_id=zones_by_id,
       frame_width=processed.shape[1],
       frame_height=processed.shape[0]
   )

   # Increment frame counter
   video_service.increment_frame_counter()
   ```

---

## Execution Flow

### Frame-by-Frame Processing

```
Frame N arrives
    ↓
YOLO inference (person detection)
    ↓
For each detected bbox:
    ├─ Create person_id from position hash
    ├─ Check Zone_A overlap
    │   ├─ YES: Stage 1 triggered
    │   │   ├─ Save snapshot
    │   │   └─ Async call to Gemini (background thread)
    │   │       └─ Result stored in PersonTracker
    │   └─ NO: Continue
    │
    ├─ Check Zone_B overlap
    │   ├─ YES: Stage 2 triggered
    │   │   ├─ Retrieve classification from PersonTracker
    │   │   └─ If CHILD or pending:
    │   │       ├─ Save latest snapshot
    │   │       └─ Send Telegram alert
    │   └─ NO: Continue
    │
    ├─ Existing visualization (person type, age, etc.)
    └─ Continue to next detection

Increment frame counter
    ↓
Output processed frame
```

---

## Safety Mechanisms

### 1. **Fallback to Safe Mode**

If Gemini API fails for any reason:

- Classification defaults to `is_child=True`
- Alerts are sent (better safe than sorry)
- Logged with warning: `"⚠️ Fallback: Marking person {id} as CHILD due to API error"`

### 2. **Rate Limiting**

- Max 15 API calls per minute
- 4-second minimum between calls
- If limit reached: defer classification until next minute

### 3. **Redundant Snapshot Saves**

- Stage 1: Initial snapshot for classification
- Stage 2: Latest snapshot included in alert
- All saved with unique timestamps

### 4. **Automatic Cleanup**

- Person tracking entries expire after 300 seconds
- Memory released automatically
- Prevents memory bloat in long-running streams

---

## Configuration

### Environment Variables (.env)

```env
# Gemini API
GEMINI_API_KEY=AIzaSyDo0a9MM9jBnleaPeYGspqYt2Buk7xLW1Q
GEMINI_MODEL=gemini-1.5-flash

# Zone IDs
ZONE_A_ID=zone_a          # Buffer zone
ZONE_B_ID=zone_b          # Danger zone

# Rate Limiting
GEMINI_API_COOLDOWN=4                  # Seconds between API calls
MAX_GEMINI_CALLS_PER_MINUTE=15         # Rate limit

# Telegram Notification
NODE_BACKEND_URL=http://localhost:5003 # Node backend URL
INTERNAL_SECRET=mot_chuoi_bi_mat_...  # Authentication secret
```

### Gemini API Prompt

```
"Hãy phân tích hình ảnh này. Đối tượng là trẻ em (child) hay người lớn (adult)?
Dựa vào các đặc điểm như: chiều cao, kích thước cơ thể, khuôn mặt, tư thế.
Trả về kết quả JSON ONLY (không có text khác):
{"identity": "child" hoặc "adult", "confidence": 0.0 đến 1.0}"
```

---

## Performance Considerations

### CPU/Memory Impact

- **Minimal**: Most processing is async
- **Livestream**: Never blocked by API calls
- **Person Tracking**: Hash-based, O(1) lookup

### Latency

- **Stage 1 Classification**: 2-5 seconds (async, non-blocking)
- **Stage 2 Alert Decision**: Immediate (<100ms)
- **Telegram Notification**: 1-2 seconds (async, separate thread)

### Scaling Considerations

- **Per Camera**: Independent rate limiter per camera
- **API Calls**: Shared global rate limiter (15/min total)
- **Person Capacity**: Unlimited (auto-cleanup every 300 frames)

---

## Logging

### Log Levels

**INFO Level**

```
✅ Video Service initialized
🔵 STAGE 1 - Zone_A (Buffer): Person {id} detected
🎯 Person {id} classified as CHILD
🔴 STAGE 2 - Zone_B (Danger): Person {id} escalated
📢 Sending Telegram alert for CHILD
✅ Alert notification sent successfully
```

**WARNING Level**

```
⚠️ API rate limit reached, deferring classification
⚠️ Stage 2 - Zone_B: Classification not ready for person, assuming CHILD (safe)
⚠️ Fallback: Marking person {id} as CHILD due to API error
```

**DEBUG Level**

```
Cleaned up tracking for person {id}
Skipping alert for person {id} - classified as ADULT
Zone detection error: {error}
```

---

## Troubleshooting

### Issue: No Alerts are Being Sent

**Check:**

1. Verify `GEMINI_API_KEY` is valid in `.env`
2. Verify `NODE_BACKEND_URL` is correct and accessible
3. Check logs for: `API rate limit reached`
4. Ensure Zone_B is properly configured in database

**Solution:**

```bash
# Test Gemini API
python -c "import google.generativeai as genai; print('API OK')"

# Test Telegram endpoint
curl http://localhost:5003/api/alerts/notify -X POST

# Check person classification
python -c "import alert_service; print(alert_service.get_rate_limit_status())"
```

### Issue: Livestream is Lagging

**Likely Cause:** Gemini API calls blocking thread
**Check:**

- Logs should show all calls are async (only `async_classify_person()` is called)
- If blocking detected, increase `GEMINI_API_COOLDOWN`

**Solution:**

1. Ensure `async_classify_person()` is used (not `analyze_person_with_gemini()`)
2. Lower `YOLO_CONF_THRES` to reduce false positives
3. Check network latency to Gemini API

### Issue: Person Not Being Classified

**Possible Reasons:**

1. **Zone_A not configured**: Person never enters Zone_A
2. **Image quality**: Snapshot too dark/blurry for Gemini
3. **API error**: Check logs for error messages

**Debug:**

```python
# Check person tracking status
import video_service
status = video_service.get_tracking_status()
print(f"Tracked persons: {status['persons_tracked']}")

# Check classification result
person_data = alert_service.person_tracker.get_person(person_id)
print(f"Classification: {person_data['is_child']}")
```

---

## Future Improvements

1. **Multi-Camera Support**
   - Per-camera rate limiters
   - Isolated person tracking per camera

2. **Confidence Threshold**
   - Only send alerts if Gemini confidence > threshold
   - Adjustable per environment

3. **Custom Prompts**
   - Support multiple Gemini prompts for different scenarios
   - Age-specific classification (e.g., <12 vs 12-18)

4. **Webhook Notifications**
   - Support additional alert backends
   - JSON webhook event streaming

5. **Analytics Dashboard**
   - Track classifications over time
   - False positive/negative analysis

---

## References

- [Gemini API Documentation](https://ai.google.dev/docs)
- [google-generativeai Python Package](https://github.com/google/generative-ai-python)
- [OpenCV Point Polygon Test](https://docs.opencv.org/master/d3/dc0/group__imgproc__shape.html#ga1a539e8db2135af2566103705d7a5722)
