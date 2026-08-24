# Camera Hub — Operations

`liveview.py` is the single owner of the camera. Everything else — the browser
page, `snap.sh`, curl, future forklift code — talks to it over HTTP instead of
touching the sensor. It runs as a systemd service, so it comes back on its own
after a reboot.

**Open:** http://jetson:8080 (tailnet, MagicDNS) or http://jetson.local:8080

---

## Everyday commands

```bash
sudo systemctl status liveview     # is it running?
sudo systemctl restart liveview    # after deploying a new liveview.py
sudo systemctl stop liveview       # free the camera for manual work
sudo systemctl start liveview
journalctl -u liveview -f          # live log
journalctl -u liveview -n 50       # last 50 lines
```

Startup takes ~15 s: device wait + Argus settle, then YOLO loads and autofocus
runs once. `/api/status` returning a `focus_dac` means it's fully up.

---

## "The site is down"

Work down this list; each step tells you which layer failed.

| Check | Command | Means |
|---|---|---|
| 1. Is the Jetson up? | `ping -c1 jetson.local` | No reply → power/network, not the hub |
| 2. Is the service up? | `sudo systemctl status liveview` | `failed` → read the journal; `inactive` → someone stopped it |
| 3. Why did it die? | `journalctl -u liveview -n 50` | Python traceback, or Argus errors |
| 4. Is the camera alive? | `curl -s jetson.local:8080/api/status` | `"camera": false` → degraded, see below |

**Historical note:** before this was a service, the hub ran in a tmux session —
and tmux dies with a reboot. The site went silently down twice that way (Aug 8
and Aug 12, 2026) with nothing wrong except that nobody re-ran the command.
That is what this unit exists to prevent. If the site is ever down again, it is
a *real* failure — read the journal.

---

## Only one program can use the camera

Argus allows a single capture session. While the service runs, it holds it, and
`snap.sh` will refuse to start. For manual capture work:

```bash
sudo systemctl stop liveview
~/snap.sh                          # or gst-launch, camcheck.sh, focus sweeps
sudo systemctl start liveview
```

Forgetting the `start` is the easy mistake — the site stays down until you do.

---

## Degraded mode

If the hub cannot get a frame at startup it keeps serving anyway: the gallery
and status page work, the banner reads **NO CAMERA** with a specific reason, and
the camera endpoints return 503. It does not retry, because CSI is not
hot-pluggable — a missing ribbon stays missing until a powered-off reseat.

Two distinct messages, two different problems:

- *"no camera connected — /dev/video0 missing"* → the ribbon or the driver. Power
  off, reseat, reboot. Verify with `docs/camcheck.sh`.
- *"camera present but no frames — another pipeline owns it"* → something else
  holds Argus. Look for a stray `gst-launch` or a second hub instance:
  `pgrep -af "gst-launc[h]|livevie[w]"`.

`isOpened()` is not proof of life — the GStreamer pipeline constructs fine even
when Argus refuses the session. The hub probes for a real frame (6 s) instead.

---

## Endpoints

| Path | Does |
|---|---|
| `/` | The page: stream, controls, vitals, gallery |
| `/stream` | multipart MJPEG (~0.3 s latency) |
| `/frame.jpg` | Single current annotated frame |
| `/snap` | Save the clean current frame → `~/snapshots/live_<ts>.jpg` |
| `/api/status` | fps, detect_every, yolo, focus_dac, camera, error |
| `/api/vitals` | gpu, cpu, ram, temp, watts (parsed from `tegrastats`) |
| `/api/set?detect_every=N` | Run YOLO every Nth frame, 1–60, live |
| `/api/af` | Golden-section autofocus (~6 s), returns best DAC |
| `/api/focus?dac=N` | Move the lens directly, 0–4095 |
| `/api/analyze` | Snap a frame → Claude API as FORK-1, returns text + image |
| `/api/snaps`, `/snaps/<name>`, `/api/delete?name=` | Gallery list, image, delete |

Sensor mode and fps are fixed per pipeline — changing those is a restart (a
"profile"). Focus, detect cadence, and snapshots change live.

---

## Deploying a new version

Edit on the Mac, never in place on the Jetson:

```bash
scp liveview.py paul@jetson.local:~/
ssh -t paul@jetson.local 'sudo systemctl restart liveview'
```

To change the service itself, edit `docs/liveview.service` here, then:

```bash
scp docs/liveview.service paul@jetson.local:/tmp/
ssh -t paul@jetson.local 'sudo install -m 644 /tmp/liveview.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart liveview'
```

---

## Config

- **Claude API key** — `~/.anthropic_key` on the Jetson, mode 600. Required by
  `/api/analyze` only; the button reports the fix if it's missing. Read per
  request, so replacing the file needs no restart.
- **Snapshots** — `~/snapshots/`, served by the gallery, deletable from the page.
- **YOLO weights** — `/home/paul/yolo11n.pt`.

Stdlib HTTP server + system OpenCV + ultralytics. No pip installs, no venv.
There is no authentication — the hub is reachable by anything on the LAN or the
tailnet. Keep it off the public internet.
