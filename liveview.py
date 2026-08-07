"""Live camera hub — MJPEG stream, YOLO overlay, snapshots, gallery, focus.

This is the single owner of the camera while it runs. Everything else (the
browser page, snap.sh's refusal check, curl, future forklift code) talks to it
over HTTP instead of touching the sensor. Make it start at boot via systemd
and it is, in the proper sense, a daemon.

Open  http://jetson:8080  (tailnet, via MagicDNS) or  http://jetson.local:8080.

Endpoints
  /                viewer page: stream, snap, autofocus, detect-rate, gallery
  /stream          multipart MJPEG
  /frame.jpg       single current annotated frame
  /snap            save current CLEAN frame -> ~/snapshots/live_<ts>.jpg
  /snaps/<name>    serve a saved snapshot (gallery images)
  /api/status      JSON: fps, detect_every, focus dac, yolo state
  /api/set?detect_every=N    run YOLO every Nth frame (1..60), live
  /api/af          run golden-section autofocus (~6 s), returns best dac
  /api/focus?dac=N move the lens directly

Design notes
  - Sensor mode/fps are fixed per pipeline (restart = a "profile" change);
    YOLO cadence, focus, and snapshots are per-frame and change live.
  - Detection boxes are drawn manually on every frame, so at low detect rates
    the video stays smooth 30fps and only the boxes go stale between runs.
  - Runs autofocus automatically once at startup (lens boots at DAC 0 / 20cm).
  - Stdlib http.server + system OpenCV + ultralytics only. No pip installs.

Usage:  python3 liveview.py [--yolo] [--port 8080]
tmux:   tmux new -d -s live "python3 ~/liveview.py --yolo 2>&1 | tee /tmp/liveview.log"
Stop:   tmux kill-session -t live
"""
import argparse
import glob
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2

sys.path.insert(0, "/home/paul/arducam_focus")
from focuser import Focuser, tenengrad

SNAPDIR = os.path.expanduser("~/snapshots")
PHI = 0.6180339887

GST = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1 ! "
    "nvvidconv ! video/x-raw,format=BGRx ! "
    "videoconvert ! video/x-raw,format=BGR ! "
    "appsink drop=1 max-buffers=1"
)

PAGE = """<!doctype html><html><head><title>jetson cam hub</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{margin:0;background:#111;color:#9a9;font-family:monospace;
display:flex;flex-direction:column;align-items:center;gap:8px;padding:8px}
img.live{max-width:100%;border:1px solid #333}
#bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
button,select{font-family:monospace;font-size:15px;padding:8px 18px;
background:#222;color:#9a9;border:1px solid #444}
#gal{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;max-width:960px}
#gal img{height:84px;border:1px solid #333;cursor:pointer}
#status{font-size:13px;color:#686}
</style></head><body>
<p id="status">connecting...</p>
<img class="live" src="/stream">
<div id="bar">
<button onclick="hit('/snap')">snap</button>
<button onclick="hit('/api/af')">autofocus</button>
<label>detect:
<select id="rate" onchange="hit('/api/set?detect_every='+this.value)">
<option value="1">every frame</option><option value="2">every 2nd</option>
<option value="5">every 5th</option><option value="10">every 10th</option>
<option value="30">~1 per second</option></select></label>
</div>
<div id="gal"></div>
<script>
const S=document.getElementById('status'),G=document.getElementById('gal');
function hit(u){S.textContent='...';fetch(u).then(r=>r.text()).then(t=>{S.textContent=t;gallery();});}
function gallery(){fetch('/api/snaps').then(r=>r.json()).then(l=>{
 G.innerHTML='';l.forEach(n=>{const i=document.createElement('img');
 i.src='/snaps/'+n;i.onclick=()=>window.open('/snaps/'+n);G.appendChild(i);});});}
function poll(){fetch('/api/status').then(r=>r.json()).then(s=>{
 S.textContent=`${s.fps.toFixed(1)} fps | yolo ${s.yolo?('every '+s.detect_every):'off'} | focus dac ${s.focus_dac??'?'}`;
 document.getElementById('rate').value=s.detect_every;}).catch(()=>{});}
setInterval(poll,2000);poll();gallery();
</script></body></html>"""


class Camera:
    def __init__(self, use_yolo):
        self.jpeg = None          # latest annotated frame, encoded
        self.raw = None           # latest clean frame (numpy)
        self.lock = threading.Condition()
        self.fps = 0.0
        self.use_yolo = use_yolo
        self.model = None
        self.detect_every = 2
        self.boxes = []           # [(x1,y1,x2,y2,label)] from last detection
        self.focuser = None
        self.focus_dac = None
        self.af_lock = threading.Lock()
        self._af_started = False
        threading.Thread(target=self._run, daemon=True).start()

    # ---------- capture loop ----------

    def _run(self):
        if self.use_yolo:
            from ultralytics import YOLO  # slow import — keep off main thread
            self.model = YOLO("/home/paul/yolo11n.pt")
            print("[hub] YOLO loaded")
        cap = cv2.VideoCapture(GST, cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            raise SystemExit("[hub] camera failed to open — already in use?")
        self.focuser = Focuser()
        self.focuser.init()
        print("[hub] camera open, serving")
        n = 0
        t_last = time.time()
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            n += 1
            if n == 15 and not self._af_started:  # startup AF, once frames flow
                self._af_started = True
                threading.Thread(target=self.autofocus, daemon=True).start()

            if self.model is not None and n % max(self.detect_every, 1) == 0:
                r = self.model.predict(frame, verbose=False)[0]
                self.boxes = [
                    (*map(int, b.xyxy[0].tolist()),
                     f"{r.names[int(b.cls)]} {float(b.conf):.2f}")
                    for b in r.boxes
                ]
            disp = frame
            if self.boxes:
                disp = frame.copy()
                for x1, y1, x2, y2, label in self.boxes:
                    cv2.rectangle(disp, (x1, y1), (x2, y2), (255, 200, 0), 2)
                    cv2.putText(disp, label, (x1, max(y1 - 8, 14)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            ok, buf = cv2.imencode(".jpg", disp, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                continue
            now = time.time()
            self.fps = 0.9 * self.fps + 0.1 / max(now - t_last, 1e-3)
            t_last = now
            with self.lock:
                self.jpeg = buf.tobytes()
                self.raw = frame
                self.lock.notify_all()

    # ---------- frame access ----------

    def next_jpeg(self):
        with self.lock:
            self.lock.wait(timeout=2.0)
            return self.jpeg

    def fresh_raw(self):
        """A clean frame captured strictly after this call (2 frame waits)."""
        with self.lock:
            self.lock.wait(timeout=2.0)
            self.lock.wait(timeout=2.0)
            return None if self.raw is None else self.raw.copy()

    # ---------- actions ----------

    def snap(self):
        with self.lock:
            frame = None if self.raw is None else self.raw.copy()
        if frame is None:
            return None
        os.makedirs(SNAPDIR, exist_ok=True)
        path = os.path.join(SNAPDIR, time.strftime("live_%Y%m%d_%H%M%S.jpg"))
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return path

    def set_focus(self, dac):
        self.focuser.set_position(int(dac))
        self.focus_dac = int(dac)
        return self.focus_dac

    def autofocus(self):
        """Golden-section search on live frames. Returns best DAC, or None."""
        if not self.af_lock.acquire(blocking=False):
            return None  # already running
        try:
            t0 = time.time()
            cache = {}

            def roi(img):
                h, w = img.shape[:2]
                return img[h // 4: 3 * h // 4, w // 4: 3 * w // 4]

            def measure(dac):
                dac = int(dac)
                if dac in cache:
                    return cache[dac]
                self.focuser.set_position(dac)
                time.sleep(0.25)
                frame = self.fresh_raw()
                if frame is None:
                    raise RuntimeError("no frames during AF")
                cache[dac] = tenengrad(roi(frame))
                return cache[dac]

            a, b = 0, 4095
            c, d = int(b - PHI * (b - a)), int(a + PHI * (b - a))
            fc, fd = measure(c), measure(d)
            while b - a > 24:
                if fc < fd:
                    a, c, fc = c, d, fd
                    d = int(a + PHI * (b - a))
                    fd = measure(d)
                else:
                    b, d, fd = d, c, fc
                    c = int(b - PHI * (b - a))
                    fc = measure(c)
            best = c if fc >= fd else d
            self.set_focus(best)
            print(f"[hub] AF: dac={best} ({len(cache)} probes, "
                  f"{time.time() - t0:.1f}s)")
            return best
        finally:
            self.af_lock.release()


CAM = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        path = url.path

        if path == "/":
            self._send(200, "text/html", PAGE.encode())

        elif path == "/frame.jpg":
            data = CAM.next_jpeg()
            if data is None:
                return self._send(503, "text/plain", b"no frame yet")
            self._send(200, "image/jpeg", data)

        elif path == "/snap":
            p = CAM.snap()
            self._send(200 if p else 503, "text/plain",
                       f"saved {os.path.basename(p)}".encode() if p
                       else b"no frame yet")

        elif path == "/api/status":
            self._send(200, "application/json", json.dumps({
                "fps": CAM.fps,
                "detect_every": CAM.detect_every,
                "yolo": CAM.model is not None,
                "focus_dac": CAM.focus_dac,
            }).encode())

        elif path == "/api/set":
            try:
                n = max(1, min(60, int(q["detect_every"][0])))
                CAM.detect_every = n
                self._send(200, "text/plain", f"detect every {n}".encode())
            except (KeyError, ValueError):
                self._send(400, "text/plain", b"?detect_every=1..60")

        elif path == "/api/af":
            best = CAM.autofocus()
            self._send(200, "text/plain",
                       f"focused: dac {best}".encode() if best is not None
                       else b"autofocus already running")

        elif path == "/api/focus":
            try:
                dac = max(0, min(4095, int(q["dac"][0])))
                self._send(200, "text/plain",
                           f"dac {CAM.set_focus(dac)}".encode())
            except (KeyError, ValueError):
                self._send(400, "text/plain", b"?dac=0..4095")

        elif path == "/api/snaps":
            files = sorted(glob.glob(os.path.join(SNAPDIR, "*.jpg")),
                           key=os.path.getmtime, reverse=True)[:24]
            self._send(200, "application/json",
                       json.dumps([os.path.basename(f) for f in files]).encode())

        elif path.startswith("/snaps/"):
            name = os.path.basename(path)  # basename() defeats ../ traversal
            full = os.path.join(SNAPDIR, name)
            if not (name.endswith(".jpg") and os.path.isfile(full)):
                return self._send(404, "text/plain", b"not found")
            with open(full, "rb") as f:
                self._send(200, "image/jpeg", f.read())

        elif path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=frame")
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
    print(f"[hub] http://jetson:{args.port}  (yolo={'on' if args.yolo else 'off'})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
