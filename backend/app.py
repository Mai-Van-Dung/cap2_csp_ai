import os
import time
import cv2
import logging
from urllib.parse import quote
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import camera_service as cs
import zone_service

BASE_DIR = os.path.dirname(__file__)
load_dotenv(os.path.join(BASE_DIR, ".env"))

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
        
        if not zones:
            return jsonify({
                "status": "error",
                "message": "zones array is required"
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

if __name__ == "__main__":
    host = os.getenv("FLASK_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_SERVER_PORT", "5000"))
    app.run(host=host, port=port, threaded=True)