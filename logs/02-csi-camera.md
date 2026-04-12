# Log 02 — CSI Camera Setup & Local Detection

**Date:** 2026-04-12

## What I Did

### ArduCam IMX519 Driver Installation
- Camera: ArduCam UC-873 Rev D (IMX519 sensor, 16MP autofocus)
- Connected via CSI ribbon cable to the Jetson
- Ran ArduCam's install script: `sudo ./install_full.sh -m imx519`
- It found a matching driver for L4T 36.5.0 and installed successfully
- Rebooted, camera appeared at `/dev/video0`

### The Green Screen Problem
- `cv2.VideoCapture(0)` captured frames, but they were entirely green
- Root cause: the IMX519 outputs **10-bit raw Bayer data** (format: RG10)
- OpenCV was reading the raw Bayer mosaic as a regular color image
- In a Bayer mosaic, half the pixels are green (2G per 1R and 1B), so raw data looks green
- **Concept learned: Bayer pattern** — camera sensors don't see color directly. Each pixel has a tiny color filter (R, G, or B). A "debayering" algorithm interpolates the missing colors to create a full-color image.

### The Fix: nvarguscamerasrc
- NVIDIA provides `nvarguscamerasrc`, a GStreamer element that captures from CSI cameras through NVIDIA's **ISP (Image Signal Processor)**
- The ISP handles debayering, white balance, exposure — all the raw-to-color processing
- GStreamer pipeline: `nvarguscamerasrc ! video/x-raw(memory:NVMM),width=1920,height=1080 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink`
- **Concept learned: ISP** — the Image Signal Processor is dedicated hardware on the Jetson that converts raw sensor data to usable images. Without it, you get garbage.

### OpenCV GStreamer Saga
- pip-installed OpenCV (4.13) didn't have GStreamer support
- NVIDIA's system OpenCV (4.5.4 via `libopencv`) does have GStreamer
- Had to: uninstall pip OpenCV, install `python3-opencv` system package
- NumPy conflict: system OpenCV built against NumPy 1.x, but we had NumPy 2.2.6
- Fixed by downgrading: `pip3 install "numpy<2"`
- **Lesson learned:** on Jetson, prefer system packages over pip when they need hardware integration (GStreamer, CUDA). pip packages are generic builds without Jetson-specific features.

### Built detect_local.py
- Standalone script: CSI camera → YOLO → console output + periodic snapshots
- No MacBook needed — fully self-contained on the Jetson
- Saves annotated snapshots to `~/snapshots/` every 10 seconds

### Camera Supported Modes
| Resolution | FPS | Use Case |
|-----------|-----|----------|
| 4656x3496 | 9 | Full 16MP stills |
| 3840x2160 | 17 | 4K video |
| 1920x1080 | 60 | Our detection mode |
| 1280x720 | 120 | High-speed tracking |

## Performance Results

| Setup | FPS |
|-------|-----|
| MacBook webcam → WiFi → Jetson → WiFi → MacBook | 5.7 |
| Jetson + CSI camera (raw 16MP, no GStreamer) | 4.2 |
| Jetson + CSI camera (1080p via GStreamer) | **23.7** |

## Concepts Learned

| Concept | What It Means |
|---------|---------------|
| Bayer pattern | Camera sensors use a mosaic of R/G/B filters; software interpolates full color |
| ISP (Image Signal Processor) | Dedicated hardware that converts raw sensor data → usable images |
| nvarguscamerasrc | NVIDIA's GStreamer element that captures CSI cameras through the ISP |
| GStreamer pipeline | A chain of processing elements connected with `!` — like Unix pipes for video |
| System vs pip packages on Jetson | System packages have hardware integration; pip packages are generic |
| RG10 format | 10-bit raw Bayer with RGRG/GBGB pattern — 2 bytes per pixel |

## What's Next
- Pull snapshots to MacBook to verify image quality
- Explore TensorRT for faster inference
- Work toward a fully portable setup
