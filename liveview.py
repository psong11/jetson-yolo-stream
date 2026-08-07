"""Live MJPEG view of the CSI camera, with optional YOLO overlay.

Open  http://jetson:8080  (tailnet) or  http://jetson.local:8080  (LAN).
Endpoints:  /            viewer page (with a snap button)
            /stream      multipart MJPEG (what the <img> tag consumes)
            /frame.jpg   single current frame (handy for scripts / control hub)
            /snap        save the current CLEAN frame (no YOLO boxes) to
                         ~/snapshots/live_<ts>.jpg — iPhone-style photo-while-
                         recording; stream-resolution, the sensor mode can't
                         switch to 16MP without restarting the pipeline

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
align-items:center;font-family:monospace;color:#9a9}
button{margin:8px;padding:10px 24px;font-family:monospace;font-size:16px}
</style></head>
<body><p id="s">jetson liveview</p><img src="/stream" style="max-width:100%">
<button onclick="fetch('/snap').then(r=>r.text()).then(t=>s.textContent=t)">
snap</button>
</body></html>"""


class Camera:
    def __init__(self, use_yolo):
        self.jpeg = None
        self.raw = None  # latest clean frame (no overlay), for /snap
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
            raw = frame
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
                self.raw = raw
                self.lock.notify_all()

    def next_jpeg(self):
        with self.lock:
            self.lock.wait(timeout=2.0)
            return self.jpeg

    def snap(self):
        """Save the current clean frame to ~/snapshots. Returns the path."""
        import os

        with self.lock:
            frame = None if self.raw is None else self.raw.copy()
        if frame is None:
            return None
        path = os.path.expanduser(
            time.strftime("~/snapshots/live_%Y%m%d_%H%M%S.jpg")
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return path


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
        elif self.path == "/snap":
            path = CAM.snap()
            self.send_response(200 if path else 503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(
                f"saved {path}".encode() if path else b"no frame yet"
            )
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
