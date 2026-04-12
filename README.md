# jetson-yolo-stream

Real-time object detection on a Jetson Orin Nano — building a portable AI camera that sees and understands the world around it.

## What This Is

A standalone AI vision system running entirely on edge hardware. A CSI camera feeds frames to YOLO running on the Jetson's GPU at ~24 FPS. No cloud. No laptop required. Just a small computer with a camera, learning to see.

There's also a network streaming mode that lets you use a MacBook webcam as the camera source over WiFi.

## First Observations

The machine's very first images are in [`first_observations/`](first_observations/first_observations_of_the_world.md).

## Hardware

| Device | Role | Status |
|--------|------|--------|
| NVIDIA Jetson Orin Nano (8GB) | GPU inference + camera capture | Primary — runs everything |
| ArduCam UC-873 Rev D (IMX519) | 16MP CSI camera | Connected, working via GStreamer |
| MacBook Pro (Apple Silicon) | Dev machine, optional streaming client | Used for SSH + code editing |

## Software Stack (on Jetson)

| Component | Version | Role |
|-----------|---------|------|
| JetPack | 6.2 (L4T R36.5) | OS + NVIDIA drivers |
| Ubuntu | 22.04.5 (aarch64) | Base OS |
| CUDA | 12.6 | GPU compute framework |
| cuDNN | 9.3 | Neural network acceleration |
| TensorRT | 10.3 | Model optimization (not yet used) |
| Python | 3.10.12 | Runtime |
| PyTorch | 2.11.0 | ML framework (Jetson ARM64 build from pypi.jetson-ai-lab.io) |
| Ultralytics | 8.4.37 | YOLO object detection |
| OpenCV | 4.5.4 (system) | Image processing + GStreamer capture |
| GStreamer | 1.19.90 | Camera pipeline (nvarguscamerasrc) |
| NumPy | <2.0 | Array operations (must stay <2 for system OpenCV compatibility) |
| YOLO model | YOLOv11n (nano, 5.4MB) | Pre-trained on COCO (80 object classes) |

## Two Modes of Operation

### Mode 1: Local Detection (primary)

Everything runs on the Jetson. No network needed.

```
ArduCam IMX519 → GStreamer (nvarguscamerasrc) → OpenCV → YOLO (GPU) → Console + Snapshots
```

**Performance:** ~23.7 FPS at 1920x1080

### Mode 2: Network Streaming

MacBook captures video, Jetson runs inference, results stream back.

```
MacBook Webcam → JPEG → TCP/WiFi → Jetson YOLO (GPU) → JSON → TCP/WiFi → MacBook Display
```

**Performance:** ~5.7 FPS (bottlenecked by network round-trip)

## How to Run

### Local Detection (on Jetson only)

```bash
ssh paul@jetson.local
python3 detect_local.py
```

Prints detections to console. Saves annotated snapshots to `~/snapshots/` every 10 seconds.

Pull snapshots to your Mac:
```bash
scp paul@jetson.local:~/snapshots/*.jpg ~/Desktop/
```

### Network Streaming (Jetson + MacBook)

**Terminal 1 — Jetson:**
```bash
ssh paul@jetson.local
python3 server.py
```

**Terminal 2 — MacBook:**
```bash
cd ~/Documents/learn/jetson-yolo-stream
source venv/bin/activate
python3 client.py
```

Press `q` to quit.

## Project Structure

```
jetson-yolo-stream/
├── detect_local.py          # Standalone Jetson: CSI camera + YOLO (primary)
├── server.py                # Jetson: receives frames over TCP, runs YOLO
├── client.py                # MacBook: captures webcam, sends to Jetson, displays results
├── docs/
│   ├── architecture.md      # How all the systems and tools connect
│   └── jetson_setup.md      # Full Jetson setup reference
├── first_observations/      # The machine's first images and detections
│   ├── first_observations_of_the_world.md
│   ├── first_light.jpg
│   └── first_detection.jpg
├── logs/                    # Learning journal
│   ├── 01-setup.md          # Jetson setup + first streaming session
│   └── 02-csi-camera.md     # CSI camera setup + local detection
└── .gitignore
```

## Performance Comparison

| Setup | FPS | Bottleneck |
|-------|-----|------------|
| MacBook → WiFi → Jetson → WiFi → MacBook | 5.7 | Network round-trip (~95ms) |
| Jetson + CSI camera (raw 16MP, no GStreamer) | 4.2 | Huge 16MP frame resize |
| Jetson + CSI camera (1080p, GStreamer ISP) | **23.7** | YOLO inference (~42ms) |

## What's Next

- [ ] TensorRT export for faster inference (could push past 30 FPS)
- [ ] Add a display to the Jetson (see detections without SSH)
- [ ] Battery power for full portability
- [ ] Fine-tune YOLO to recognize specific objects
- [ ] Object tracking across frames (not just per-frame detection)

## Key Lessons Learned

See the [learning logs](logs/) for detailed notes. Highlights:

- CSI cameras on Jetson output raw Bayer data — you need NVIDIA's ISP (`nvarguscamerasrc`) to get proper color images
- Use system OpenCV (`python3-opencv`), not pip's `opencv-python`, on Jetson — only the system build has GStreamer support
- PyTorch for Jetson must come from `pypi.jetson-ai-lab.io`, not regular PyPI
- NumPy must stay below 2.0 for compatibility with system OpenCV
- cuDSS (`libcudss.so.0`) isn't included in JetPack but newer PyTorch versions require it
