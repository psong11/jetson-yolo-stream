# Jetson YOLO Stream

## Project Summary
Building a portable AI camera on a Jetson Orin Nano that sees and understands the world.
This is an educational project — Paul wants step-by-step explanations of everything.

## Current State (2026-04-12)
- **CSI camera (ArduCam IMX519) working** via GStreamer + nvarguscamerasrc
- **YOLO11n running locally** at ~23.7 FPS on Jetson GPU at 1920x1080
- **Network streaming mode** also works (MacBook webcam → Jetson → MacBook) at ~5.7 FPS
- **TensorRT not yet used** — could boost FPS further

## How to Guide Paul
- Be concrete and educational: explain concepts, not just commands
- Long commands for the Jetson terminal get line-wrapped — use short commands or quotes around URLs
- Multi-line Python one-liners break due to indentation — use semicolons on one line, or write to a file
- Always SCP files from MacBook to Jetson (Paul edits locally, runs remotely)

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
- `logs/` — learning journal entries
- `first_observations/` — the machine's first captured images

## GitHub
- Repo: github.com/psong11/jetson-yolo-stream
- Branch: main
