import os
import time
import cv2
import logging
from urllib.parse import quote
from flask import Flask, Response, jsonify
from flask_cors import CORS
import camera_service as cs

# --- CẤU HÌNH THÔNG SỐ CAMERA ---
# Bạn có thể thay đổi trực tiếp ở đây hoặc dùng biến môi trường
CAM_IP = os.getenv("CAM_IP", "192.168.137.157")
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

if __name__ == "__main__":
    # Chạy server tại port 5000
    app.run(host="0.0.0.0", port=5000, threaded=True)