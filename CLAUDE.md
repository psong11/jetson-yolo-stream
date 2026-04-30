# Jetson YOLO Stream

## Project Summary
Building a portable AI camera on a Jetson Orin Nano that sees and understands the world.
This is an educational project — Paul wants step-by-step explanations of everything.

## Current State (2026-04-16)
- **CSI camera (ArduCam IMX519) working** via GStreamer + nvarguscamerasrc
- **YOLO11n running locally** at ~23.7 FPS on Jetson GPU at 1920x1080
- **Network streaming mode** also works (MacBook webcam → Jetson → MacBook) at ~5.7 FPS
- **TensorRT not yet used** — could boost FPS further
- **Autofocus deferred.** Installed ArduCam driver (Apr 12) streams but does not expose `focus_absolute` via V4L2. Direct I2C writes to the VCM at bus 10 addr 0x0c are either silently overridden by NVIDIA Argus or use a wrong protocol variant — focus sweep 50→900 produced visually identical frames. Lens does physically move (audible rattle). Proper fix requires installing ArduCam's **Jetvariety** driver (different variant from what's installed). Deferred — YOLO detection works fine with factory focus; revisit when fine-detail captures actually matter.
- **SSH key auth set up (Apr 16)** — Claude on Mac can run `ssh paul@jetson.local '<cmd>'` directly. See `docs/ssh_jetson.md`.

## How to Guide Paul
- Be concrete and educational: explain concepts, not just commands
- Long commands for the Jetson terminal get line-wrapped — use short commands or quotes around URLs
- Multi-line Python one-liners break due to indentation — use semicolons on one line, or write to a file
- Always SCP files from MacBook to Jetson (Paul edits locally, runs remotely)

## Driving the Jetson over SSH (MANDATORY)
As of 2026-04-16, Paul set up SSH key auth so Claude can run commands on the Jetson directly via `ssh paul@jetson.local '<cmd>'` from the Mac's Bash tool.

**Before running any SSH command to the Jetson, read `docs/ssh_jetson.md`.** It covers the one-shot pattern, quote-escaping, background-process traps, the narrow `sudo` allowlist (i2c tools only), file transfer, and the list of actions that require Paul's explicit confirmation. Failing to read it has caused hangs, stale gst pipelines, and sudo deadlocks in the past.

## Key Architecture Decisions
- CSI camera requires GStreamer pipeline (nvarguscamerasrc) — cv2.VideoCapture(0) gives green images
- Must use system OpenCV (python3-opencv apt package) not pip opencv-python — only system build has GStreamer
- NumPy must stay <2.0 for system OpenCV compatibility
- PyTorch must come from pypi.jetson-ai-lab.io (Jetson ARM64 build)
- cuDSS manually installed to /usr/local/cuda/lib64/ (PyTorch 2.11 dependency)

## Hardware
- Jetson Orin Nano 8GB, JetPack 6.2, SSH: paul@jetson.local
- ArduCam UC-873 Rev D (IMX519 16MP CSI camera)
- MacBook Pro (Apple Silicon) — dev machine

## Files
- `detect_local.py` — primary script, runs on Jetson (CSI camera + YOLO)
- `server.py` — Jetson side of network streaming mode
- `client.py` — MacBook side of network streaming mode
- `docs/architecture.md` — full system architecture with ASCII diagrams
- `docs/jetson_setup.md` — complete setup reference and version matrix
- `docs/ssh_jetson.md` — **read before any SSH command to the Jetson** (connection, quote-escaping, background processes, sudo scope, safety, tmux, jstatus)
- `docs/jstatus.sh` — one-shot Jetson health snapshot (installed on Jetson at `~/bin/jstatus`); run `ssh paul@jetson.local '~/bin/jstatus'` as first move of any session
- `logs/` — learning journal entries
- `first_observations/` — the machine's first captured images

## GitHub
- Repo: github.com/psong11/jetson-yolo-stream
- Branch: main
