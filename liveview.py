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
  /api/delete?name=<name>    delete a snapshot from ~/snapshots
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
*{box-sizing:border-box}
body{margin:0;background:#111;color:#9a9;font-family:monospace;height:100vh;
display:grid;gap:10px;padding:10px;
grid-template-columns:minmax(0,3fr) minmax(0,2fr);
grid-template-rows:minmax(0,3fr) minmax(0,2fr);
grid-template-areas:"stream ctrl" "tbd gal"}
.panel{border:1px solid #333;display:flex;flex-direction:column;min-width:0;min-height:0}
.panel>h2{margin:0;padding:6px 10px;font-size:11px;font-weight:normal;
letter-spacing:2px;text-transform:uppercase;color:#686;border-bottom:1px solid #333}
.panel>.pad{flex:1;min-height:0;overflow:auto;padding:12px}
#stream{grid-area:stream}
#stream .pad{display:flex;align-items:center;justify-content:center;
padding:0;overflow:hidden;background:#000}
#stream img{max-width:100%;max-height:100%}
#ctrl{grid-area:ctrl}
#gal{grid-area:gal}
#tbd{grid-area:tbd;border-style:dashed}
#tbd .pad{display:flex;align-items:center;justify-content:center;
color:#454;letter-spacing:4px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
button,select{font-family:monospace;font-size:14px;padding:8px 16px;
background:#222;color:#9a9;border:1px solid #444;cursor:pointer}
button:hover{background:#2c2c2c}
label{font-size:13px;color:#686;min-width:48px}
#status{font-size:13px;color:#686;margin:0 0 14px;min-height:1.2em}
input[type=range]{flex:1;min-width:80px;accent-color:#9a9}
#thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:6px}
#thumbs .th{position:relative}
#thumbs img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;
border:1px solid #333;cursor:pointer}
#thumbs .x{position:absolute;top:3px;right:3px;display:none;padding:0 6px;
font-size:13px;line-height:18px;background:rgba(0,0,0,.75);color:#e66;
border:1px solid #444;cursor:pointer}
#thumbs .th:hover .x{display:block}
@media(max-width:800px){
body{height:auto;display:flex;flex-direction:column}
#stream .pad{min-height:220px}#tbd{order:9}}
</style></head><body>
<div class="panel" id="stream"><h2>live</h2>
<div class="pad"><img src="/stream"></div></div>
<div class="panel" id="ctrl"><h2>control</h2><div class="pad">
<p id="status">connecting...</p>
<div class="row">
<button onclick="hit('/snap')">snap</button>
<button onclick="hit('/api/af')">autofocus</button>
</div>
<div class="row"><label>detect</label>
<select id="rate" onchange="hit('/api/set?detect_every='+this.value)">
<option value="1">every frame</option><option value="2">every 2nd</option>
<option value="5">every 5th</option><option value="10">every 10th</option>
<option value="30">~1 per second</option></select></div>
<div class="row"><label>focus</label>
<input type="range" id="dac" min="0" max="4095" step="16"
 onchange="hit('/api/focus?dac='+this.value)">
<span id="dacv">?</span></div>
</div></div>
<div class="panel" id="tbd"><h2>tbd</h2><div class="pad">&mdash;</div></div>
<div class="panel" id="gal"><h2>gallery</h2>
<div class="pad"><div id="thumbs"></div></div></div>
<script>
const S=document.getElementById('status'),G=document.getElementById('thumbs'),
D=document.getElementById('dac'),DV=document.getElementById('dacv');
function hit(u){S.textContent='...';fetch(u).then(r=>r.text()).then(t=>{S.textContent=t;gallery();});}
function gallery(){fetch('/api/snaps').then(r=>r.json()).then(l=>{
 G.innerHTML='';l.forEach(n=>{const d=document.createElement('div');d.className='th';
 const i=document.createElement('img');
 i.src='/snaps/'+n;i.onclick=()=>window.open('/snaps/'+n);
 const x=document.createElement('button');x.className='x';x.textContent='\\u00d7';
 x.title='delete';x.onclick=e=>{e.stopPropagation();
 if(confirm('delete '+n+'?'))hit('/api/delete?name='+encodeURIComponent(n));};
 d.append(i,x);G.appendChild(d);});});}
function poll(){fetch('/api/status').then(r=>r.json()).then(s=>{
 if(!s.camera){S.textContent='NO CAMERA: '+s.error;S.style.color='#e66';return;}
 S.style.color='';
 S.textContent=`${s.fps.toFixed(1)} fps | yolo ${s.yolo?('every '+s.detect_every):'off'} | focus dac ${s.focus_dac??'?'}`;
 document.getElementById('rate').value=s.detect_every;
 if(s.focus_dac!=null&&document.activeElement!==D){D.value=s.focus_dac;DV.textContent=s.focus_dac;}
}).catch(()=>{});}
D.addEventListener('input',()=>DV.textContent=D.value);
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
        self.cam_error = None     # set => degraded mode: gallery/status only
        self.af_lock = threading.Lock()
        self._af_started = False
        threading.Thread(target=self._run, daemon=True).start()

    # ---------- capture loop ----------

    def _run(self):
        # Open the camera FIRST — fail fast and explicitly, before the slow
        # model import. isOpened() is NOT the test: the GStreamer pipeline
        # constructs fine even when Argus refuses the capture session (seen
        # 2026-08-07: "Failed to create CaptureSession" with isOpened()==True).
        # The only honest signal is a real frame arriving. CSI is not
        # hot-pluggable, so a missing camera stays missing until a powered-off
        # reconnect: degrade, don't retry.
        cap = cv2.VideoCapture(GST, cv2.CAP_GSTREAMER)
        got_frame = False
        if cap.isOpened():
            t0 = time.time()
            while time.time() - t0 < 6:
                ok, _ = cap.read()
                if ok:
                    got_frame = True
                    break
                time.sleep(0.2)
        if not got_frame:
            cap.release()
            if os.path.exists("/dev/video0"):
                self.cam_error = ("camera present but no frames — another "
                                  "pipeline owns it (check tmux / gst-launch)")
            else:
                self.cam_error = ("no camera connected — /dev/video0 missing. "
                                  "Power off to reconnect the CSI ribbon, "
                                  "then reboot.")
            print(f"[hub] DEGRADED: {self.cam_error}")
            return  # server keeps serving gallery + status
        if self.use_yolo:
            from ultralytics import YOLO  # slow import — keep off main thread
            self.model = YOLO("/home/paul/yolo11n.pt")
            print("[hub] YOLO loaded")
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
        if self.focuser is None:
            return None  # degraded mode — no camera, no VCM rail
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
        except RuntimeError as e:
            print(f"[hub] AF failed: {e}")
            return None
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
            if CAM.cam_error:
                return self._send(503, "text/plain", CAM.cam_error.encode())
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
                "camera": CAM.cam_error is None,
                "error": CAM.cam_error,
            }).encode())

        elif path == "/api/set":
            try:
                n = max(1, min(60, int(q["detect_every"][0])))
                CAM.detect_every = n
                self._send(200, "text/plain", f"detect every {n}".encode())
            except (KeyError, ValueError):
                self._send(400, "text/plain", b"?detect_every=1..60")

        elif path == "/api/af":
            if CAM.cam_error:
                return self._send(503, "text/plain", CAM.cam_error.encode())
            best = CAM.autofocus()
            self._send(200, "text/plain",
                       f"focused: dac {best}".encode() if best is not None
                       else b"autofocus already running")

        elif path == "/api/focus":
            if CAM.cam_error:
                return self._send(503, "text/plain", CAM.cam_error.encode())
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

        elif path == "/api/delete":
            name = os.path.basename(q.get("name", [""])[0])
            full = os.path.join(SNAPDIR, name)
            if not (name.endswith(".jpg") and os.path.isfile(full)):
                return self._send(404, "text/plain", b"not found")
            os.remove(full)
            self._send(200, "text/plain", f"deleted {name}".encode())

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
