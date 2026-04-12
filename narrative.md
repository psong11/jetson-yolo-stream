# The Build Log

A running account of teaching a small computer to see.

---

## April 12, 2026 — First Light

There's a little computer sitting on my desk. Eight gigabytes of RAM, a thousand CUDA cores, and an ARM chip the size of a postage stamp. The Jetson Orin Nano. I flashed it with an operating system back in February and then left it alone for six weeks while life happened.

Today I plugged it back in.

---

The first thing you do with any machine is ask if it's alive. SSH from the MacBook, password, and there it is — a blinking cursor on a black terminal. Ubuntu 22.04, kernel intact, 209 gigs of empty NVMe waiting for something to do.

The plan was simple: get YOLO running on this thing. Object detection. Feed it video, it tells you what it sees. Person. Car. Dog. The fundamental act of machine perception — taking raw light and turning it into names.

But nothing is simple when you're working at the edge of what a small computer can do.

---

CUDA was installed but invisible. The compiler existed on disk but the shell didn't know where to find it. So you learn about PATH — the list of places a computer looks when you ask it to do something. If you never tell it where to look, it'll tell you it can't find what you're asking for. Even if it's right there.

There's a metaphor in that, but I'll leave it alone.

PyTorch was next. On a normal computer you just run `pip install torch` and walk away. On a Jetson, you can't. The chip is ARM, not x86. The binaries that work on every other computer in the world don't work here. You need a special build, compiled by NVIDIA, hosted on their own server, purpose-built for this exact hardware. The address is `pypi.jetson-ai-lab.io` — I burned through two wrong URLs before I found the right one. `.dev` doesn't exist. `.com` doesn't exist. `.io` does.

Then PyTorch imported but immediately crashed. Missing library: `libcudss.so.0`. A sparse solver library that JetPack doesn't ship but PyTorch 2.11 demands. Downloaded a tarball from NVIDIA's redistribution server, extracted it, copied the `.so` files into the CUDA lib directory by hand.

```
python3 -c "import torch; print(torch.cuda.is_available())"
True
```

True. One word. An hour and a half of work compressed into four characters.

---

I tested YOLO on a stock image first. A bus on a street. Four persons, one bus, 203 milliseconds. All tensors on `cuda:0`. The GPU was awake.

Then I built the streaming pipeline. Two scripts — a server on the Jetson that receives image frames and runs YOLO, a client on the MacBook that captures the webcam and sends frames over WiFi. TCP sockets, length-prefixed messages, JPEG compression to keep the packets small enough for real-time transfer. The MacBook sees with its camera. The Jetson thinks with its GPU. They talk through the air between them.

5.7 frames per second. Not fast. But it worked. My MacBook's webcam was being interpreted by a computer across the room, and bounding boxes were appearing on objects it had never been trained to find in my specific apartment. Person. TV. Laptop.

---

Then I plugged in the camera.

ArduCam UC-873 Rev D. IMX519 sensor. 16 megapixels through a CSI ribbon cable thinner than a shoelace. I powered down the Jetson, seated the cable, booted back up.

`/dev/video0` appeared. The system saw the hardware.

I took a picture.

Green.

The entire image was green. Not green like a forest — green like a wall of pure emerald nothing. Every pixel, every channel. The camera was outputting raw Bayer data — the sensor's native mosaic of red, green, and blue filter elements — and OpenCV was reading it as if it were already a finished image. It wasn't. It was ingredients, not a dish.

Half the pixels on any camera sensor are green. That's the Bayer pattern — two greens for every red and blue, because human eyes are most sensitive to green light. When you read that raw data without processing it, you get a green screen. The camera was seeing fine. The software was just illiterate.

---

The fix was NVIDIA's ISP — the Image Signal Processor. Dedicated hardware on the Jetson that takes raw sensor data and does what biology does in your retina: debayering, white balance, exposure correction. The translation from photons to meaning.

`nvarguscamerasrc` — that's the GStreamer element that talks to the ISP. I threaded it into a pipeline: camera sensor to ISP to format converter to color space converter to OpenCV. Each step transforms the data — from raw Bayer to NV12 to BGRx to BGR — like a sentence being translated through four languages before it arrives in one you can read.

But OpenCV, the version I'd installed from pip, didn't speak GStreamer. It was compiled without it. A generic build for generic hardware. I had to throw it away and use the system OpenCV that came with JetPack — version 4.5.4, older, but built with the right integrations. Then NumPy was too new for the old OpenCV. Downgraded.

Every layer in this stack was built by different people, at different times, for different assumptions about what hardware it would run on. Getting them to agree is the actual work.

---

Then it worked.

I ran `gst-launch-1.0` with `nvarguscamerasrc` piped through the full conversion chain, and for the first time, the Jetson captured a real image.

A lamp. Warm amber light against a ceiling. Soft, out of focus. The ISP had just woken up, the autofocus hadn't settled, and the exposure was still adjusting. But the colors were real. The photons had traveled from a lightbulb through a lens onto a 16-megapixel sensor, been read as 10-bit Bayer, processed through dedicated silicon, converted through four format stages, and arrived as a JPEG on an NVMe drive.

The machine's first properly seen image.

I saved it as `first_light.jpg`.

---

Then I connected YOLO, and the detections started streaming.

```
[FPS: 22.1] person (0.92)
[FPS: 23.4] person (0.92)
[FPS: 23.6] tv (0.87)
[FPS: 24.0] laptop (0.84)
[FPS: 24.8] laptop (0.69), mouse (0.57)
```

23.7 frames per second. Four times faster than the WiFi streaming. No network, no MacBook, no middleman. Just a camera, a GPU, and 80 classes of objects it learned to recognize from a dataset it's never seen my apartment in.

Person. TV. Laptop. Mouse.

It doesn't know what these things are. It knows what they look like. That's a different thing entirely. But it's a start.

I pointed the camera around the room. It tracked me as I moved. It found my laptop with 90% confidence. It saw the TV on the wall. When I held up my phone it wasn't sure — sometimes it said "cell phone," sometimes it said nothing. The model was trained on COCO, 80 classes of common objects, and not everything in my room maps neatly onto those 80 categories.

But it was seeing. Blurry, imperfect, confident in some things and uncertain about others. Like anything that just opened its eyes for the first time.

---

### What's on the desk now

A Jetson Orin Nano with a CSI camera, running YOLOv11 at 24 frames per second, detecting objects in real time with no internet connection, no cloud, no laptop. A self-contained eye.

It doesn't understand yet. It recognizes. Understanding comes later — tracking objects over time, learning that a person who leaves a room is the same person who entered it, noticing that certain things happen at certain times. Right now it sees each frame as a standalone photograph with no memory of the one before it.

But the scaffolding is there. The camera works. The ISP processes. The GPU infers. The software connects them all.

Tomorrow I'll teach it to remember.

---

### Numbers

| What | Value |
|------|-------|
| Time from first SSH to first detection | ~3 hours |
| Wrong URLs tried for PyTorch | 2 |
| Missing libraries manually installed | 1 (cuDSS) |
| Green screens before ISP pipeline worked | 4 |
| Final FPS (local, 1080p, YOLO11n) | 23.7 |
| Objects it can recognize | 80 (COCO dataset) |
| Objects it will learn to recognize | TBD |
