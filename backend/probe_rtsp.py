import os
import cv2
from urllib.parse import quote

CAM_IP = os.getenv("CAM_IP", "192.168.137.157")
CAM_USER = os.getenv("CAM_USER", "admin")
CAM_PASS = os.getenv("CAM_PASS", "")
PATHS = [p.strip() for p in os.getenv(
    "RTSP_PATHS",
    "/live0,/live1,/h264/ch1/main/av_stream,/h264/ch1/sub/av_stream,/cam/realmonitor?channel=1&subtype=0,/Streaming/Channels/101,/Streaming/Channels/102,/H.264"
).split(",") if p.strip()]

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|max_delay;500000"

user = quote(CAM_USER, safe="")
pwd = quote(CAM_PASS, safe="")

for p in PATHS:
    path = p if p.startswith("/") else f"/{p}"
    url = f"rtsp://{user}:{pwd}@{CAM_IP}:554{path}"
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
    ok, frame = cap.read()
    cap.release()
    print(f"{'OK  ' if ok and frame is not None else 'FAIL'} {path}")