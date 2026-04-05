import os
import time
import cv2
import logging
from urllib.parse import quote
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from db_connector import execute_query, fetch_all, fetch_one

BASE_DIR = os.path.dirname(__file__)
load_dotenv(os.path.join(BASE_DIR, ".env"))

import camera_service as cs
import zone_service

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

app = Flask(__name__)
# Cho phép Frontend React truy cập
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/video_feed")
def video_feed():
    return Response(
        cs.gen_frames(app.logger),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/status")
def status():
    return jsonify(cs.stream_status)

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
        normalized = []

        for row in rows:
            image_path = row.get("image_path")
            image_url = None
            if image_path:
                if str(image_path).startswith("http://") or str(image_path).startswith("https://"):
                    image_url = image_path
                else:
                    image_url = f"{host_root}/{str(image_path).lstrip('/')}"

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

if __name__ == "__main__":
    host = os.getenv("FLASK_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_SERVER_PORT", "5000"))
    app.run(host=host, port=port, threaded=True)