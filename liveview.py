"""Live MJPEG view of the CSI camera, with optional YOLO overlay.

Open  http://jetson:8080  (tailnet) or  http://jetson.local:8080  (LAN).
Endpoints:  /            viewer page
            /stream      multipart MJPEG (what the <img> tag consumes)
            /frame.jpg   single current frame (handy for scripts / control hub)

No third-party web framework — stdlib http.server + system OpenCV (GStreamer
build) + ultralytics, all already installed. Owns the camera while running:
snap.sh and the sweeps will refuse to start until this is stopped.

Usage:  python3 liveview.py [--yolo] [--port 8080]
Run it in tmux:  tmux new -d -s live "python3 ~/liveview.py --yolo 2>&1 | tee /tmp/liveview.log"
Stop:            tmux kill-session -t live
"""
import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

GST = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1 ! "
    "nvvidconv ! video/x-raw,format=BGRx ! "
    "videoconvert ! video/x-raw,format=BGR ! "
    "appsink drop=1 max-buffers=1"
)

PAGE = b"""<!doctype html><html><head><title>jetson liveview</title>
<style>body{margin:0;background:#111;display:flex;flex-direction:column;
align-items:center;font-family:monospace;color:#9a9}</style></head>
<body><p id="s">jetson liveview</p><img src="/stream" style="max-width:100%">
</body></html>"""


class Camera:
    def __init__(self, use_yolo):
        self.jpeg = None
        self.lock = threading.Condition()
        self.fps = 0.0
        self.use_yolo = use_yolo
        self.model = None
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        if self.use_yolo:
            from ultralytics import YOLO  # slow import — do it in-thread
            self.model = YOLO("/home/paul/yolo11n.pt")
            print("[liveview] YOLO loaded")
        cap = cv2.VideoCapture(GST, cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            raise SystemExit("[liveview] camera failed to open — already in use?")
        print("[liveview] camera open, serving")
        t_last = time.time()
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            if self.model is not None:
                frame = self.model.predict(frame, verbose=False)[0].plot()
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                continue
            now = time.time()
            self.fps = 0.9 * self.fps + 0.1 / max(now - t_last, 1e-3)
            t_last = now
            with self.lock:
                self.jpeg = buf.tobytes()
                self.lock.notify_all()

    def next_jpeg(self):
        with self.lock:
            self.lock.wait(timeout=2.0)
            return self.jpeg


CAM = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(PAGE)
        elif self.path == "/frame.jpg":
            data = CAM.next_jpeg()
            if data is None:
                self.send_error(503, "no frame yet")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=frame"
            )
            self.end_headers()
            try:
                while True:
                    data = CAM.next_jpeg()
                    if data is None:
                        continue
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                    self.wfile.write(data)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_error(404)


def main():
    global CAM
    ap = argparse.ArgumentParser()
    ap.add_argument("--yolo", action="store_true")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    CAM = Camera(args.yolo)
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"[liveview] http://jetson:{args.port}  (yolo={'on' if args.yolo else 'off'})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
