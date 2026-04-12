# System Architecture

How every piece of hardware, software, and data flow connects.

---

## The Big Picture

```
                         JETSON ORIN NANO
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   ┌───────────┐    ┌───────────┐    ┌───────────────┐   │
    │   │  ArduCam   │───>│    ISP    │───>│   GStreamer    │   │
    │   │  IMX519    │    │ (NVIDIA)  │    │   Pipeline     │   │
    │   │  (sensor)  │    │           │    │                │   │
    │   └───────────┘    └───────────┘    └──────┬────────┘   │
    │     CSI ribbon       Hardware              │             │
    │     cable             debayer            BGR frames      │
    │                       + color              │             │
    │                       balance              v             │
    │                                     ┌──────────────┐    │
    │                                     │   OpenCV      │    │
    │                                     │ (VideoCapture)│    │
    │                                     └──────┬───────┘    │
    │                                            │             │
    │                                       numpy array        │
    │                                      (1920x1080x3)       │
    │                                            │             │
    │                                            v             │
    │   ┌──────────┐    ┌───────────┐    ┌──────────────┐     │
    │   │  CUDA    │<───│  PyTorch  │<───│ Ultralytics  │     │
    │   │  12.6    │    │  2.11.0   │    │  (YOLO11n)   │     │
    │   │  (GPU)   │───>│           │───>│              │     │
    │   └──────────┘    └───────────┘    └──────┬───────┘     │
    │     GPU cores       Tensor ops          Detections       │
    │     do the math     on GPU              (class, conf,    │
    │                                          bbox)           │
    │                                            │             │
    │                                            v             │
    │                                     ┌──────────────┐    │
    │                                     │   Output     │    │
    │                                     │ - Console    │    │
    │                                     │ - Snapshots  │    │
    │                                     └──────────────┘    │
    └─────────────────────────────────────────────────────────┘
```

---

## Mode 1: Local Detection (detect_local.py)

Everything on the Jetson. This is the primary mode.

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Camera  │────>│   ISP    │────>│ GStreamer │────>│  OpenCV  │────>│   YOLO   │
│  IMX519  │     │ debayer  │     │ pipeline  │     │  frame   │     │ inference│
│  (16MP)  │     │ + color  │     │ resize to │     │ as numpy │     │ on GPU   │
│          │     │ + expose │     │ 1080p BGR │     │  array   │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └─────┬────┘
   CSI bus         Hardware         Software          Python              │
                   on Jetson        pipeline                         detections
                                                                         │
                                                                         v
                                                                  ┌──────────┐
                                                                  │  Output  │
                                                                  │ console +│
                                                                  │ .jpg snap│
                                                                  └──────────┘
```

### Data transformation at each stage:

| Stage | Input | Output | Where it runs |
|-------|-------|--------|---------------|
| Camera sensor | Photons | Raw 10-bit Bayer (RG10) | IMX519 sensor |
| ISP | Raw Bayer | Debayered NV12 video | Jetson ISP hardware |
| GStreamer | NV12 (NVMM memory) | BGR pixels (CPU memory) | nvvidconv (GPU) + videoconvert |
| OpenCV | GStreamer appsink | numpy array (1920, 1080, 3) | CPU |
| YOLO | numpy array | Detections list | GPU (CUDA) |

---

## Mode 2: Network Streaming (server.py + client.py)

```
       MACBOOK                           WIFI                         JETSON
┌───────────────────┐                                        ┌───────────────────┐
│                   │                                        │                   │
│  ┌─────────────┐  │         TCP Socket (port 9999)         │  ┌─────────────┐  │
│  │   Webcam    │  │                                        │  │   YOLO      │  │
│  │   capture   │  │    ┌──────────────────────────┐        │  │   on GPU    │  │
│  └──────┬──────┘  │    │  Length-prefixed protocol │        │  └──────┬──────┘  │
│         │         │    │                          │        │         │         │
│    raw frame      │    │  [4 bytes: msg length]   │        │    detections     │
│         │         │    │  [N bytes: payload   ]   │        │         │         │
│         v         │    │                          │        │         v         │
│  ┌─────────────┐  │    └──────────────────────────┘        │  ┌─────────────┐  │
│  │ JPEG encode │──┼──── JPEG bytes (~50KB) ───────────────>│──│ JPEG decode │  │
│  └─────────────┘  │                                        │  └─────────────┘  │
│                   │                                        │                   │
│  ┌─────────────┐  │                                        │  ┌─────────────┐  │
│  │  Draw boxes │<─┼──── JSON results (~200B) <────────────┼──│  Extract    │  │
│  │  + display  │  │                                        │  │  boxes      │  │
│  └─────────────┘  │                                        │  └─────────────┘  │
│                   │                                        │                   │
└───────────────────┘                                        └───────────────────┘

Timeline for one frame:
├── capture (~5ms)
├── JPEG encode (~5ms)
├── send over WiFi (~15ms)
├── JPEG decode on Jetson (~20ms)
├── YOLO inference on GPU (~60ms)
├── JSON encode + send back (~5ms)
├── receive + draw + display (~15ms)
└── total: ~125-175ms = 5.7-8 FPS
```

---

## The GStreamer Pipeline (decoded)

The pipeline string in detect_local.py:

```
nvarguscamerasrc ! video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink
```

Broken down piece by piece:

```
nvarguscamerasrc
│   NVIDIA's camera capture element. Talks to the ISP hardware
│   which handles raw Bayer → color conversion, auto-exposure,
│   auto-white-balance. Without this, you get a green image.
│
├──> video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1
│    "Caps filter" — tells the pipeline what format to use.
│    memory:NVMM means the data stays in GPU memory (fast).
│    The ISP outputs NV12 color format at our requested resolution.
│
├──> nvvidconv
│    NVIDIA's hardware-accelerated format converter.
│    Converts NV12 → BGRx (adds a dummy alpha channel).
│    Runs on the GPU, so it's fast.
│
├──> video/x-raw,format=BGRx
│    Data is now in regular CPU memory as BGRx pixels.
│
├──> videoconvert
│    Software converter: BGRx → BGR (strips the alpha channel).
│    OpenCV expects BGR format.
│
├──> video/x-raw,format=BGR
│    Pure BGR pixels — what OpenCV and YOLO want.
│
└──> appsink
     The "exit" of the pipeline. OpenCV's VideoCapture reads
     frames from here via the GStreamer backend.
```

---

## The YOLO Inference Stack

```
┌─────────────────────────────────────────────────────┐
│                    Ultralytics                       │
│              (Python API for YOLO)                   │
│                                                     │
│   model = YOLO("yolo11n.pt")                        │
│   results = model(frame)                            │
├─────────────────────────────────────────────────────┤
│                    PyTorch 2.11                      │
│             (tensor operations, autograd)            │
│                                                     │
│   Manages model weights, runs forward pass,         │
│   handles GPU memory allocation                     │
├─────────────────────────────────────────────────────┤
│                    CUDA 12.6                         │
│              (GPU compute framework)                 │
│                                                     │
│   cuDNN 9.3 — accelerates neural net operations     │
│   cuDSS 0.7.1 — sparse solver (PyTorch dependency)  │
├─────────────────────────────────────────────────────┤
│              Jetson Orin Nano GPU                    │
│            (1024 CUDA cores, 8GB RAM)               │
│                                                     │
│   Actually runs the matrix multiplications          │
│   that make object detection work                   │
└─────────────────────────────────────────────────────┘
```

---

## Network Layout

```
┌──────────────┐        WiFi (192.168.0.x)       ┌──────────────┐
│              │                                  │              │
│   MacBook    │◄────────────────────────────────►│   Jetson     │
│   Pro        │     192.168.0.106                │   Orin Nano  │
│              │                                  │              │
│   SSH client │─── ssh paul@jetson.local ───────>│   SSH server │
│   SCP client │─── scp files ──────────────────>│   port 22    │
│   client.py  │─── TCP :9999 ─────────────────>│   server.py  │
│              │                                  │              │
└──────────────┘                                  └──────────────┘
                                                   IP: 192.168.0.224
                                                   Hostname: jetson
                                                   mDNS: jetson.local
                                                   User: paul
```

---

## Camera Capabilities (ArduCam IMX519)

```
┌──────────────────────────────────────────────────┐
│              ArduCam UC-873 Rev D                 │
│              Sensor: Sony IMX519                  │
│              16MP, Autofocus                      │
│              Interface: CSI (MIPI)                │
├──────────────────────────────────────────────────┤
│  Mode  │  Resolution  │  FPS  │  Use Case        │
│────────┼──────────────┼───────┼──────────────────│
│  0     │  4656 x 3496 │  9    │  Full 16MP stills│
│  1     │  3840 x 2160 │  17   │  4K video        │
│  2     │  1920 x 1080 │  60   │  Detection mode  │  <-- we use this
│  3     │  1280 x 720  │  120  │  High-speed      │
└──────────────────────────────────────────────────┘

Driver: ArduCam kernel module (install_full.sh -m imx519)
Raw format: RG10 (10-bit Bayer RGRG/GBGB)
Requires ISP for color output (nvarguscamerasrc)
```
