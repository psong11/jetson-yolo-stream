# Jetson YOLO Stream

## Project Summary
Building a portable AI camera on a Jetson Orin Nano that sees and understands the world.
This is an educational project — Paul wants step-by-step explanations of everything.

## Current State (2026-04-29)
- **CSI camera (ArduCam IMX519, UC-873 Rev D) working** via GStreamer + nvarguscamerasrc
- **YOLO11n running locally** at ~23.7 FPS on Jetson GPU at 1920x1080
- **Network streaming mode** also works (MacBook webcam → Jetson → MacBook) at ~5.7 FPS
- **TensorRT not yet used** — could boost FPS further
- **Installed driver: `arducam-nvidia-l4t-kernel`** (custom kernel, Native-Camera path; Feb 7 2026 build for L4T 36.5.0). Stream comes from `/boot/arducam/Image` with the IMX519-Dual dtb overlay. No V4L2 focus controls. `/boot/Image.bak` exists (stock NVIDIA kernel) but no extlinux fallback entry — rollback would currently need HDMI+keyboard console access.
- **Autofocus working** (manual control, Apr 29). VCM is AK7375 at I2C bus 10 addr 0x0c (powered only while streaming). Wire protocol: single 3-byte `i2ctransfer w3@0x0c 0x00 <high> <low>`, init with `w2@0x0c 0x02 0x00`, ramp in 64-unit steps. Full deterministic DAC-0-to-4095 range confirmed visually + via readback. Continuous AF (hill-climb) not yet implemented. Reference: `docs/autofocus.md`, working code at `arducam_focus/run_focus_test_v4.py`.
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
- `docs/autofocus.md` — AK7375 wire protocol, working manual focus, what doesn't work
- `arducam_focus/run_focus_test_v4.py` — proven working manual focus sweep + readback
- `docs/ssh_jetson.md` — **read before any SSH command to the Jetson** (connection, quote-escaping, background processes, sudo scope, safety, tmux, jstatus)
- `docs/jstatus.sh` — one-shot Jetson health snapshot (installed on Jetson at `~/bin/jstatus`); run `ssh paul@jetson.local '~/bin/jstatus'` as first move of any session
- `logs/` — learning journal entries
- `first_observations/` — the machine's first captured images

## GitHub
- Repo: github.com/psong11/jetson-yolo-stream
- Branch: main
