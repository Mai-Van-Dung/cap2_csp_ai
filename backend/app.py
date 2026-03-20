import os
import time
import cv2
import logging
from urllib.parse import quote
from flask import Flask, Response, jsonify
from flask_cors import CORS

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

stream_status = {
    "connected": False,
    "last_error": "",
    "active_path": "",
    "camera_ip": CAM_IP
}

def build_rtsp_url(path):
    user = quote(CAM_USER, safe="")
    pwd = quote(CAM_PASS, safe="")
    return f"rtsp://{user}:{pwd}@{CAM_IP}:{CAM_PORT}{path}"

def open_capture():
    """Hàm chẩn đoán lỗi chi tiết khi kết nối camera"""
    for path in RTSP_PATHS:
        url = build_rtsp_url(path)
        app.logger.info(f"Trying to connect: {CAM_IP} via {path}...")
        
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

        if not cap.isOpened():
            app.logger.warning(f"NETWORK ERROR: Could not open socket at {CAM_IP}:{CAM_PORT}")
            cap.release()
            continue

        # Bước quan trọng: Thử đọc 1 khung hình để xác thực User/Pass
        ok, frame = cap.read()
        if not ok:
            # Nếu mở được nhưng không đọc được frame -> Thường là lỗi 401
            err_msg = "AUTH ERROR: 401 Unauthorized. Check Verification Code or Image Encryption on App."
            app.logger.error(err_msg)
            stream_status["connected"] = False
            stream_status["last_error"] = err_msg
            cap.release()
            continue

        # Kết nối thành công
        stream_status["connected"] = True
        stream_status["last_error"] = ""
        stream_status["active_path"] = path
        app.logger.info(f"SUCCESS: Camera connected via {path}")
        return cap

    return None

def gen_frames():
    cap = open_capture()
    
    while True:
        if cap is None or not cap.isOpened():
            app.logger.warning("Camera connection lost. Reconnecting...")
            time.sleep(2)
            cap = open_capture()
            if cap is None: continue

        success, frame = cap.read()
        if not success:
            cap.release()
            cap = None
            continue

        # Resize để khớp với vùng vẽ ROI trên Web
        frame = cv2.resize(frame, OUTPUT_SIZE)
        
        # Nén thành JPEG để stream qua Web
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify(stream_status)

if __name__ == "__main__":
    # Chạy server tại port 5000
    app.run(host="0.0.0.0", port=5000, threaded=True)