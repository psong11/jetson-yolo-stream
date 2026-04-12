# Log 01 — Jetson Setup & First Streaming Session

**Date:** 2026-04-12

## What I Did

### Jetson Health Check
- SSH'd into the Jetson (flashed with JetPack 6.2 back in February, still working)
- Confirmed: Python 3.10.12, pip, 209GB free disk space
- CUDA 12.6 was installed but `nvcc` wasn't on PATH

### Fixed CUDA PATH
- CUDA was at `/usr/local/cuda/bin/` but the shell didn't know where to find it
- Added to `~/.bashrc`:
  ```bash
  export PATH=/usr/local/cuda/bin:$PATH
  export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
  ```
- **Concept learned: PATH** — a list of directories the shell searches when you type a command. If a program isn't in one of those directories, the shell says "command not found" even though the program exists.

### Installed CUDA Toolkit
- JetPack had the CUDA runtime (for running GPU code) but not the full toolkit (for building GPU code)
- `sudo apt install cuda-toolkit-12-6` added the compiler (`nvcc`) and dev tools

### Installed PyTorch (the Jetson way)
- Can't just `pip install torch` on Jetson — ARM processor needs a special build
- NVIDIA hosts Jetson-specific wheels at `pypi.jetson-ai-lab.io`
- Installed: `pip3 install torch torchvision --index-url https://pypi.jetson-ai-lab.io/jp6/cu126`
- Got PyTorch 2.11.0 + torchvision 0.26.0

### Fixed Missing cuDSS Library
- PyTorch 2.11 needs `libcudss.so.0` (CUDA Direct Sparse Solver) which JetPack doesn't include
- Downloaded the tarball from NVIDIA's redistribution server
- Copied the `.so` files into `/usr/local/cuda/lib64/`
- **Lesson learned:** newer PyTorch versions depend on libraries that JetPack doesn't pre-install. Check the NVIDIA forums when you hit import errors.

### Installed Ultralytics (YOLO)
- `pip3 install ultralytics` — straightforward after PyTorch was working
- Tested with a static image: detected 4 persons + 1 bus, running on `cuda:0`

### Built the Streaming Pipeline
- **server.py** (Jetson): listens on TCP port 9999, receives JPEG frames, runs YOLO, sends back JSON
- **client.py** (MacBook): captures webcam, sends frames to Jetson, draws bounding boxes, displays feed
- Uses length-prefixed TCP messages (4-byte header + payload)
- **Concept learned: TCP sockets** — TCP is a byte stream with no message boundaries. Length-prefixing solves this: send 4 bytes saying "the next message is X bytes long", then send X bytes.

### Performance Baseline
- End-to-end: ~5.7 FPS
- YOLO inference on Jetson GPU: ~60ms per frame
- JPEG decode: ~20ms
- Rest (network + capture + display): ~95ms

## Concepts Learned

| Concept | What It Means |
|---------|---------------|
| PATH | Shell searches these directories for commands. No PATH entry = "command not found" |
| CUDA runtime vs toolkit | Runtime = run GPU code. Toolkit = compile GPU code. Both needed. |
| Jetson PyTorch wheels | ARM processors need specially compiled packages — can't use normal PyPI |
| TCP length-prefixing | Send message size before message data so receiver knows how much to read |
| `recv_exact()` | TCP may deliver data in chunks — loop until you have all bytes |
| JPEG compression for streaming | Raw frames are ~1MB, JPEG ~50KB — 20x smaller for faster network transfer |
| Model warmup | First GPU inference is slow (CUDA initialization). Warm up with a dummy frame. |
| `SO_REUSEADDR` | Lets you restart a server immediately without "Address already in use" errors |

## What's Next
- Explore TensorRT export to speed up inference
- Consider plugging a camera directly into the Jetson
