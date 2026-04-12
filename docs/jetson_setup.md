# Jetson Setup Reference

Everything needed to recreate this Jetson's configuration from scratch, or to remember what's installed and why.

---

## Hardware

- **Board:** NVIDIA Jetson Orin Nano Developer Kit (8GB)
- **Storage:** NVMe SSD (238.5 GB), boots from `/dev/nvme0n1p1`
- **Camera:** ArduCam UC-873 Rev D (IMX519, 16MP, CSI)
- **Network:** WiFi (192.168.0.224), USB (192.168.55.1)
- **Hostname:** jetson (`jetson.local` via mDNS)
- **User:** paul

## OS & JetPack

| Component | Version |
|-----------|---------|
| Ubuntu | 22.04.5 LTS (aarch64, tegra kernel 5.15.185) |
| JetPack | 6.2 (L4T R36, Revision 5.0) |
| Flashed via | SDK Manager on ThinkPad T460 (Ubuntu 22.04) |

## What's Installed (and how)

### System packages (apt)

```bash
# CUDA toolkit (nvcc compiler + dev tools)
sudo apt install cuda-toolkit-12-6

# OpenCV with Python bindings + GStreamer support
sudo apt install libopencv-python python3-opencv

# Video tools
sudo apt install v4l-utils

# GStreamer plugins for bayer2rgb
sudo apt install gstreamer1.0-plugins-bad

# ArduCam IMX519 driver
# Downloaded install_full.sh from ArduCAM/MIPI_Camera GitHub releases
sudo ./install_full.sh -m imx519
# Requires reboot after install
```

### Python packages (pip, user-level)

```bash
# PyTorch — must use NVIDIA's Jetson-specific build
pip3 install torch torchvision --index-url https://pypi.jetson-ai-lab.io/jp6/cu126

# YOLO
pip3 install ultralytics

# NumPy — must stay below 2.0 for system OpenCV compatibility
pip3 install "numpy<2"
```

### Manual installs

```bash
# cuDSS (CUDA Direct Sparse Solver) — required by PyTorch 2.11+
# JetPack doesn't include it, but PyTorch imports fail without it
cd /tmp
wget "https://developer.download.nvidia.com/compute/cudss/redist/libcudss/linux-aarch64/libcudss-linux-aarch64-0.7.1.4_cuda12-archive.tar.xz"
tar xf libcudss-linux-aarch64-0.7.1.4_cuda12-archive.tar.xz
sudo cp libcudss-linux-aarch64-0.7.1.4_cuda12-archive/lib/libcudss* /usr/local/cuda/lib64/
```

### Environment variables (~/.bashrc)

```bash
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
```

## Version Matrix

| Package | Version | Source | Notes |
|---------|---------|--------|-------|
| CUDA | 12.6 | JetPack + apt | nvcc added via cuda-toolkit-12-6 |
| cuDNN | 9.3.0 | JetPack | Pre-installed |
| TensorRT | 10.3 | JetPack | Pre-installed, not yet used |
| cuDSS | 0.7.1 | Manual download | Required by PyTorch 2.11 |
| Python | 3.10.12 | System | Do not upgrade |
| PyTorch | 2.11.0 | pypi.jetson-ai-lab.io | ARM64 + CUDA 12.6 build |
| torchvision | 0.26.0 | pypi.jetson-ai-lab.io | Matches PyTorch 2.11 |
| Ultralytics | 8.4.37 | pip | Includes YOLOv11 |
| OpenCV | 4.5.4 | apt (python3-opencv) | System build with GStreamer |
| NumPy | <2.0 | pip | Must stay <2 for OpenCV compat |
| GStreamer | 1.19.90 | System | nvarguscamerasrc available |

## Common Gotchas

1. **Green screen from camera** — using `cv2.VideoCapture(0)` gives raw Bayer data. Must use GStreamer pipeline with `nvarguscamerasrc` for proper color.

2. **`nvcc: command not found`** — CUDA is installed but not on PATH. Add to `~/.bashrc`.

3. **`ImportError: libcudss.so.0`** — PyTorch 2.11 needs cuDSS which JetPack doesn't include. Download from NVIDIA redist server.

4. **`opencv-python` from pip has no GStreamer** — must uninstall pip version and use system `python3-opencv` package instead.

5. **NumPy 2.x breaks system OpenCV** — system OpenCV was compiled against NumPy 1.x. Downgrade with `pip3 install "numpy<2"`.

6. **pip packages override system packages** — `~/.local/lib/python3.10/site-packages` has higher priority than `/usr/lib/python3/dist-packages`. If pip installs a package that also exists as a system package, pip wins.

## SSH Access

```bash
# From MacBook — via mDNS hostname
ssh paul@jetson.local

# Or via IP
ssh paul@192.168.0.224

# Copy files to Jetson
scp localfile.py paul@jetson.local:~/

# Copy files from Jetson
scp paul@jetson.local:~/snapshots/*.jpg ~/Desktop/
```

## Files on the Jetson (~/home/paul/)

```
~/server.py          — YOLO inference server (for network streaming mode)
~/detect_local.py    — Standalone local detection (CSI camera + YOLO)
~/yolo11n.pt         — YOLO model weights (auto-downloaded on first run)
~/snapshots/         — Annotated detection snapshots saved by detect_local.py
```
