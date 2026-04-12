# jetson-yolo-stream

Real-time object detection on a Jetson Orin Nano — building a portable AI camera that sees and understands the world around it.

## What This Is

A two-machine system that splits computer vision work across a network:

- **MacBook** captures webcam video and displays results
- **Jetson Orin Nano** runs YOLO object detection on its GPU
- Frames stream over WiFi, detections come back in real time

```
MacBook (webcam)  ──frame──>  Jetson Orin Nano (YOLO on GPU)  ──detections──>  MacBook (display)
```

This is the first step toward a fully portable AI camera that can see and understand its environment.

## Hardware

| Device | Role |
|--------|------|
| NVIDIA Jetson Orin Nano (8GB) | GPU inference — runs YOLO |
| MacBook Pro (Apple Silicon) | Webcam capture + display |

## Software Stack

| Component | Version | Where |
|-----------|---------|-------|
| JetPack | 6.2 (L4T R36.5) | Jetson |
| CUDA | 12.6 | Jetson |
| Python | 3.10.12 | Jetson |
| PyTorch | 2.11.0 | Jetson |
| Ultralytics (YOLO) | 8.4.37 | Jetson |
| YOLO model | YOLOv11n (nano) | Jetson |
| OpenCV | 4.13 | Both |

## Performance

| Metric | Value |
|--------|-------|
| End-to-end FPS | ~5.7 |
| YOLO inference | ~60ms |
| JPEG decode | ~20ms |
| Network + capture + display | ~95ms |

## How to Run

### 1. Start the server (on Jetson)

```bash
ssh paul@192.168.0.224
python3 server.py
```

### 2. Start the client (on MacBook)

```bash
cd ~/Documents/learn/jetson-yolo-stream
source venv/bin/activate
python3 client.py
```

Press `q` to quit.

## Project Structure

```
jetson-yolo-stream/
├── server.py       # Runs on Jetson — receives frames, runs YOLO, sends results
├── client.py       # Runs on MacBook — captures webcam, sends frames, displays results
└── logs/           # Learning journal
    └── 01-setup.md # Jetson setup + first streaming session
```

## What's Next

- [ ] TensorRT export for faster inference
- [ ] Plug a USB camera directly into the Jetson (no MacBook needed)
- [ ] Make it portable — battery power + onboard camera + onboard display
- [ ] Teach it to recognize specific things (fine-tuned models)
