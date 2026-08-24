"""Live camera hub — MJPEG stream, YOLO overlay, snapshots, gallery, focus.

This is the single owner of the camera while it runs. Everything else (the
browser page, snap.sh's refusal check, curl, future forklift code) talks to it
over HTTP instead of touching the sensor. It starts at boot via systemd
(docs/liveview.service), which makes it, in the proper sense, a daemon.

Open  http://jetson:8080  (tailnet, via MagicDNS) or  http://jetson.local:8080.

Endpoints
  /                viewer page: stream, snap, autofocus, detect-rate, gallery
  /stream          multipart MJPEG
  /frame.jpg       single current annotated frame
  /snap            save current CLEAN frame -> ~/snapshots/live_<ts>.jpg
  /snaps/<name>    serve a saved snapshot (gallery images)
  /api/delete?name=<name>    delete a snapshot from ~/snapshots
  /api/vitals      JSON telemetry from tegrastats (gpu, cpu, ram, temp, watts)
  /api/analyze     snap a frame, send it to the Claude API in forklift
                   character (FORK-1); needs an API key in ~/.anthropic_key
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
Service (normal):  sudo systemctl {start,stop,restart,status} liveview
Logs:              journalctl -u liveview -f
Ops guide:         docs/camera_hub.md
"""
import argparse
import base64
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
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
grid-template-areas:"stream ctrl" "vitals gal"}
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
#vitals{grid-area:vitals}
h3{margin:0 0 10px;font-size:11px;font-weight:normal;letter-spacing:2px;
text-transform:uppercase;color:#565}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
button,select{font-family:monospace;font-size:14px;padding:8px 16px;
background:#222;color:#9a9;border:1px solid #444;cursor:pointer}
button:hover:not(:disabled){background:#2c2c2c}
button:disabled{opacity:.35;cursor:default}
label{font-size:13px;color:#686;min-width:48px}
#status{font-size:13px;color:#686;margin:0 0 14px;min-height:1.2em}
input[type=range]{flex:1;min-width:80px;accent-color:#9a9}
#drive{border-top:1px dashed #333;padding-top:12px;margin-top:4px}
#drive .off{font-size:12px;color:#565;margin:0 0 10px}
#pad{display:grid;grid-template-columns:repeat(3,44px) 24px 44px;
grid-auto-rows:38px;gap:6px}
#pad button{padding:0;font-size:15px}
#thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:6px}
#thumbs .th{position:relative}
#thumbs img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;
border:1px solid #333;cursor:pointer}
#thumbs .x{position:absolute;top:3px;right:3px;display:none;padding:0 6px;
font-size:13px;line-height:18px;background:rgba(0,0,0,.75);color:#e66;
border:1px solid #444;cursor:pointer}
#thumbs .th:hover .x{display:block}
.vrow{display:flex;gap:8px;align-items:center;margin-bottom:9px;font-size:13px}
.vrow label{min-width:44px}
.vbar{flex:1;height:10px;border:1px solid #333;background:#181818}
.vbar>div{height:100%;width:0%;background:#7a7;transition:width .5s}
.vbar>div.warn{background:#ca5}
.vbar>div.bad{background:#e66}
.vrow span{min-width:76px;text-align:right;color:#686}
#nominal{margin:12px 0 0;font-size:12px;letter-spacing:2px;color:#7a7}
#nominal.warn{color:#ca5}#nominal.bad{color:#e66}
#lb{display:none;position:fixed;inset:0;z-index:9;background:rgba(0,0,0,.88);
align-items:center;justify-content:center;cursor:pointer}
#lb.on{display:flex}
#lbc{max-width:82vw;max-height:88vh;display:flex;flex-direction:column;gap:12px}
#lbi{max-width:82vw;max-height:66vh;object-fit:contain;border:1px solid #444}
#lbt{margin:0;font-size:14px;line-height:1.55;color:#ab9;white-space:pre-wrap;
overflow:auto;max-width:70ch}
@media(max-width:800px){
body{height:auto;display:flex;flex-direction:column}
#stream .pad{min-height:220px}#vitals{order:9}}
</style></head><body>
<div class="panel" id="stream"><h2>live</h2>
<div class="pad"><img src="/stream"></div></div>
<div class="panel" id="ctrl"><h2>control</h2><div class="pad">
<p id="status">connecting...</p>
<h3>camera</h3>
<div class="row">
<button onclick="hit('/snap')">snap</button>
<button onclick="hit('/api/af')">autofocus</button>
<button onclick="analyze()">analyze</button>
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
<div id="drive"><h3>drive</h3>
<p class="off">forklift offline &mdash; controls reserved</p>
<div id="pad">
<span></span><button disabled>&#9650;</button><span></span><span></span><button disabled title="fork up">&#8613;</button>
<button disabled>&#9664;</button><button disabled>&#9632;</button><button disabled>&#9654;</button><span></span><button disabled title="fork down">&#8615;</button>
<span></span><button disabled>&#9660;</button><span></span><span></span><span></span>
</div></div>
</div></div>
<div class="panel" id="vitals"><h2>vitals</h2><div class="pad">
<div class="vrow"><label>gpu</label><div class="vbar"><div id="b_gpu"></div></div><span id="v_gpu">--</span></div>
<div class="vrow"><label>cpu</label><div class="vbar"><div id="b_cpu"></div></div><span id="v_cpu">--</span></div>
<div class="vrow"><label>ram</label><div class="vbar"><div id="b_ram"></div></div><span id="v_ram">--</span></div>
<div class="vrow"><label>temp</label><div class="vbar"><div id="b_temp"></div></div><span id="v_temp">--</span></div>
<div class="vrow"><label>power</label><div class="vbar"><div id="b_watts"></div></div><span id="v_watts">--</span></div>
<p id="nominal">AWAITING TELEMETRY</p>
</div></div>
<div class="panel" id="gal"><h2>gallery</h2>
<div class="pad"><div id="thumbs"></div></div></div>
<div id="lb" onclick="lbClose()"><div id="lbc">
<img id="lbi"><p id="lbt"></p></div></div>
<script>
const S=document.getElementById('status'),G=document.getElementById('thumbs'),
D=document.getElementById('dac'),DV=document.getElementById('dacv'),
LB=document.getElementById('lb'),LBI=document.getElementById('lbi'),
LBT=document.getElementById('lbt');
function lbShow(src,txt){LBI.style.display=src?'':'none';if(src)LBI.src=src;
LBT.textContent=txt||'';LB.classList.add('on');}
function lbClose(){LB.classList.remove('on');}
document.addEventListener('keydown',e=>{if(e.key==='Escape')lbClose();});
function hit(u){S.textContent='...';fetch(u).then(r=>r.text()).then(t=>{S.textContent=t;gallery();});}
function analyze(){lbShow(null,'FORK-1 assessing the scene...');
 fetch('/api/analyze').then(r=>{if(!r.ok)return r.text().then(t=>{throw t;});return r.json();})
 .then(j=>{lbShow(j.image,j.text);gallery();})
 .catch(t=>lbShow(null,'analyze failed: '+t));}
function gallery(){fetch('/api/snaps').then(r=>r.json()).then(l=>{
 G.innerHTML='';l.forEach(n=>{const d=document.createElement('div');d.className='th';
 const i=document.createElement('img');
 i.src='/snaps/'+n;i.onclick=()=>lbShow('/snaps/'+n,'');
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
function vbar(k,pct,txt,warn,bad){const b=document.getElementById('b_'+k),
v=document.getElementById('v_'+k);if(pct==null){v.textContent='--';return;}
b.style.width=Math.min(pct,100)+'%';
b.className=pct>=bad?'bad':pct>=warn?'warn':'';v.textContent=txt;}
function vitals(){fetch('/api/vitals').then(r=>r.json()).then(v=>{
 vbar('gpu',v.gpu,v.gpu!=null?v.gpu+'%':'--',80,95);
 vbar('cpu',v.cpu,v.cpu!=null?v.cpu+'%':'--',80,95);
 if(v.ram_used!=null)vbar('ram',100*v.ram_used/v.ram_total,
  (v.ram_used/1024).toFixed(1)+'/'+(v.ram_total/1024).toFixed(1)+'G',85,95);
 if(v.temp!=null)vbar('temp',100*v.temp/90,v.temp.toFixed(0)+'\\u00b0C',78,94);
 if(v.watts!=null)vbar('watts',100*v.watts/15,v.watts.toFixed(1)+'W',67,93);
 const N=document.getElementById('nominal');
 if(v.error){N.textContent='TELEMETRY OFFLINE: '+v.error;N.className='bad';}
 else if(v.temp>=85){N.textContent='THERMAL ALERT';N.className='bad';}
 else if(v.temp>=70){N.textContent='THERMALS ELEVATED';N.className='warn';}
 else{N.textContent='ALL SYSTEMS NOMINAL';N.className='';}
}).catch(()=>{});}
D.addEventListener('input',()=>DV.textContent=D.value);
setInterval(poll,2000);setInterval(vitals,2000);poll();vitals();gallery();
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
                                  "pipeline owns it (systemctl status liveview, "
                                  "or a stray gst-launch)")
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


class Vitals:
    """Board telemetry, parsed from a long-running tegrastats process."""

    def __init__(self):
        self.data = {}
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            p = subprocess.Popen(["tegrastats", "--interval", "2000"],
                                 stdout=subprocess.PIPE, text=True)
        except FileNotFoundError:
            self.data = {"error": "tegrastats not found"}
            return
        for line in p.stdout:
            d = {}
            m = re.search(r"RAM (\d+)/(\d+)MB", line)
            if m:
                d["ram_used"], d["ram_total"] = int(m[1]), int(m[2])
            m = re.search(r"CPU \[(.*?)\]", line)
            if m:  # cores can read "off" — count only live ones
                loads = [int(x) for x in re.findall(r"(\d+)%@", m[1])]
                if loads:
                    d["cpu"] = sum(loads) // len(loads)
            m = re.search(r"GR3D_FREQ (\d+)%", line)
            if m:
                d["gpu"] = int(m[1])
            m = re.search(r"tj@([\d.]+)C", line)
            if m:
                d["temp"] = float(m[1])
            m = re.search(r"VDD_IN (\d+)mW", line)
            if m:
                d["watts"] = int(m[1]) / 1000
            self.data = d


KEYFILE = os.path.expanduser("~/.anthropic_key")
ANALYZE_MODEL = "claude-sonnet-5"
ANALYZE_PROMPT = (
    "You are FORK-1, the onboard AI of a small warehouse forklift. Your camera "
    "is not mounted on a forklift yet, so you are LARPing: assess the scene as "
    "if you were fully deployed. In character, give (1) a deadpan tactical "
    "read of what you see, (2) what you, a forklift, would do in this "
    "scenario, (3) one blunt safety note. You take pallet logistics extremely "
    "seriously; the absence of pallets troubles you. Dry, overly formal "
    "mission-log humor. Under 110 words. No emoji, no markdown."
)


def analyze_scene():
    """Snap a clean frame, send it to the Claude API in forklift character.

    Returns (text, snapshot_basename). The full-res frame is saved to the
    gallery; a 720p copy goes over the wire to keep tokens cheap.
    """
    if not os.path.isfile(KEYFILE):
        raise RuntimeError(
            "no API key — on the jetson run: echo 'sk-ant-...' > "
            "~/.anthropic_key && chmod 600 ~/.anthropic_key")
    key = open(KEYFILE).read().strip()
    frame = CAM.fresh_raw()
    if frame is None:
        raise RuntimeError("no frame available")
    os.makedirs(SNAPDIR, exist_ok=True)
    path = os.path.join(SNAPDIR, time.strftime("analyze_%Y%m%d_%H%M%S.jpg"))
    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    ok, buf = cv2.imencode(".jpg", cv2.resize(frame, (1280, 720)),
                           [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    body = json.dumps({
        "model": ANALYZE_MODEL,
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg",
                "data": base64.b64encode(buf).decode()}},
            {"type": "text", "text": ANALYZE_PROMPT},
        ]}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        out = json.loads(r.read())
    # content may lead with a thinking block — take every text block, not [0]
    text = "\n".join(b.get("text", "") for b in out.get("content", [])
                     if b.get("type") == "text").strip()
    if not text:
        raise RuntimeError(
            f"API returned no text (stop_reason: {out.get('stop_reason')})")
    return text, os.path.basename(path)


CAM = None
VIT = None


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

        elif path == "/api/vitals":
            self._send(200, "application/json", json.dumps(VIT.data).encode())

        elif path == "/api/analyze":
            if CAM.cam_error:
                return self._send(503, "text/plain", CAM.cam_error.encode())
            try:
                text, name = analyze_scene()
                self._send(200, "application/json", json.dumps(
                    {"text": text, "image": "/snaps/" + name}).encode())
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode(errors="replace")
                self._send(502, "text/plain", f"API {e.code}: {detail}".encode())
            except Exception as e:
                self._send(503, "text/plain", str(e).encode())

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
    global CAM, VIT
    ap = argparse.ArgumentParser()
    ap.add_argument("--yolo", action="store_true")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    CAM = Camera(args.yolo)
    VIT = Vitals()
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"[hub] http://jetson:{args.port}  (yolo={'on' if args.yolo else 'off'})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
