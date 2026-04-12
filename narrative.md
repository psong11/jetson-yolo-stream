# The Build Log

Teaching a small computer to see.

---

## April 12, 2026 — First Light

There's a small computer sitting on my desk that I haven't touched in six weeks. Eight gigabytes of RAM, a thousand CUDA cores, an ARM processor the size of a postage stamp. The Jetson Orin Nano. I flashed it with an operating system back in February — connected it to WiFi, confirmed I could SSH into it from my MacBook, and then set it aside while life moved forward without it.

Today I came back to it. Not because anything changed, but because I was ready.

The whole idea is to build something that can see. Not a webcam that records — something that perceives. That takes in light and names what it finds. A manufactured eye.

The second law of thermodynamics says everything tends toward disorder. Entropy always wins. Heat dissipates, structures decay, signals dissolve into noise. And yet here I am, trying to move in the opposite direction — taking raw silicon and copper and ribbon cable and arranging it into something that can look at a room and say *person, laptop, chair.* Order from chaos. Which, if you think about it, is the oldest story there is.

---

The first thing you do with any machine is ask if it's alive. SSH from the MacBook. Password. A blinking cursor on a dark terminal. Ubuntu 22.04, kernel intact, 209 gigabytes of empty NVMe drive waiting for purpose.

CUDA was installed but the shell couldn't find it. The compiler existed somewhere on disk, but the system had never been told where to look. I added one line to `.bashrc` — a PATH variable pointing to the right directory — and suddenly the machine knew what it was capable of. The tools were always there. It just needed to be shown where they were.

PyTorch was harder. On any normal computer you install it with a single command. On the Jetson you can't, because the chip is ARM — a different architecture than the x86 processors that power almost every laptop and desktop in the world. The binaries that work everywhere else are useless here. You need a special build, compiled by NVIDIA specifically for this hardware, hosted on a server most people will never visit.

I tried two wrong URLs before finding the right one. `pypi.jetson-ai-lab.dev` — doesn't exist. `.com` — doesn't exist. `.io` — that's the one. Forty-five minutes of debugging for three characters of domain name.

Then PyTorch installed, and immediately crashed on import. A missing library called `libcudss.so.0` — a sparse math solver that JetPack doesn't include but that PyTorch 2.11 quietly demands. I downloaded a tarball from NVIDIA's redistribution server, extracted the shared object files, and copied them into the CUDA library path by hand.

```
python3 -c "import torch; print(torch.cuda.is_available())"
True
```

True.

There's a disproportionality in this work that I'm learning to sit with. Ninety minutes of troubleshooting libraries and paths and missing dependencies, and the payoff is a single boolean. But that boolean means the GPU is awake. It means a thousand cores are listening. Everything that comes after depends on this word.

---

I tested YOLO on a stock image first — a bus on a street somewhere. The model found four people and one bus in 203 milliseconds. All the tensors lived on `cuda:0`, which is the system's way of saying the computation happened on the GPU, not the CPU. The brain was working.

Then I built a streaming pipeline. Two scripts — one runs on the Jetson and waits for frames, the other runs on my MacBook, captures the webcam, compresses each frame to JPEG, and sends it across the room over WiFi. The Jetson runs YOLO on every frame and sends back a list of what it found. The MacBook draws bounding boxes around the objects and displays the feed.

Two machines. One sees, the other thinks. They communicate through a TCP socket on port 9999 — an arbitrary number, chosen for no reason, that both sides agree on. That's all a protocol really is. An agreement.

5.7 frames per second. Not fast. But real. My webcam was being perceived by a computer across the room, and names were appearing on things — person, TV, laptop — objects it had never encountered in my specific apartment but recognized anyway because someone, somewhere, trained this model on thousands of images of thousands of objects, and the patterns generalized.

That's the strange miracle of neural networks. They don't memorize. They abstract. They see enough couches to learn what couch-ness looks like, and then they find it in rooms they've never been in.

---

Then I plugged in the camera.

ArduCam UC-873 Rev D. An IMX519 sensor — 16 megapixels of Sony silicon connected to the Jetson through a CSI ribbon cable thinner than a shoelace. I powered the Jetson down, seated the cable into the connector, flipped the latch, and booted back up.

`/dev/video0` appeared in the filesystem. The system recognized that something new was attached. I took a picture.

The image was entirely green.

Not green like grass. Not green like anything in the physical world. A flat, pure, emerald void. Every pixel, every channel.

What happened: the IMX519 outputs raw Bayer data. This is the native language of a camera sensor — a mosaic of tiny color filters arranged in a repeating pattern of red, green, green, blue across millions of pixels. Half of them are green, because human eyes are most sensitive to green light, so camera engineers allocate more pixels to it. When software reads that mosaic without processing it, all it sees is green.

The camera was capturing reality just fine. The software was looking at the data and had no idea what it meant.

This is the part that made me pause. A sensor that can resolve 16 million pixels of light was producing perfect data, and it came out as a wall of green because the thing reading it didn't have the right framework to interpret what it was receiving. The information was all there. The understanding was not.

I think about how often that's true in general.

---

The fix took four green screens to find.

The answer was NVIDIA's ISP — the Image Signal Processor. Dedicated hardware on the Jetson that takes raw sensor data and does what biology does behind your cornea. Debayering — interpolating full color from the partial mosaic. White balance — adjusting for the color temperature of ambient light. Exposure correction. The entire pipeline that converts a grid of filtered photon counts into something that looks like the world.

`nvarguscamerasrc` is the GStreamer element that invokes the ISP. I chained it into a pipeline — sensor to ISP to format converter to color space converter to OpenCV — each stage transforming the data from one representation to another. Raw Bayer becomes NV12 becomes BGRx becomes BGR. Four translations before the image arrives in a language that YOLO can read.

But the OpenCV I had installed from pip didn't support GStreamer. It was a generic build, compiled for generic hardware, with no knowledge of the NVIDIA-specific tools on this board. I had to uninstall it and use the system OpenCV that shipped with JetPack — an older version, but one that was built here, for this hardware, with the right integrations. Then NumPy was too new for the old OpenCV. Downgraded that too.

Every layer in this stack was written by different engineers, in different years, with different assumptions about what would be running beneath and above them. The work of edge computing is not just making things run. It's making things agree.

---

And then, after all of that, the pipeline produced an image.

A lamp. Warm amber light spilling against a ceiling. Soft, out of focus — the autofocus hadn't settled yet, the ISP was still calibrating its exposure. But the colors were real. Not green. Not raw. Real.

Photons had traveled from a tungsten filament through a glass shade, through a plastic lens, onto a 16-megapixel sensor where they were converted into electrons, read as 10-bit Bayer values, passed through dedicated silicon that interpolated color and corrected for light temperature, piped through four software format conversions, and written as a JPEG to an NVMe drive bolted to a board the size of my palm.

From light to meaning. That's what an eye does.

![First Light](first_observations/first_light.jpg)

I connected YOLO. The detections started.

```
[FPS: 22.1] person (0.92)
[FPS: 23.4] person (0.92)
[FPS: 23.6] tv (0.87)
[FPS: 24.0] laptop (0.84)
[FPS: 24.8] laptop (0.69), mouse (0.57)
```

23.7 frames per second. Four times faster than the WiFi streaming setup. No network. No MacBook. No middleman. Just a camera and a GPU and a model trained on 80 classes of objects, running inference on a room it's never been in.

![First Detection](first_observations/first_detection.jpg)

I pointed it around the room. It found me — person, 92% confidence. It found my laptop, my TV, my mouse. When I held up my phone it hesitated. Sometimes "cell phone," sometimes nothing. The model has 80 categories and not everything in my life maps neatly onto them.

But it was seeing. Blurry, imperfect, confident about some things and genuinely uncertain about others. Naming what it could. Staying silent about what it couldn't.

---

### What's on the desk now

A Jetson Orin Nano with a 16-megapixel CSI camera, running YOLO at 24 frames per second, detecting objects in real time with no internet connection, no cloud API, no laptop in the loop. A self-contained eye.

It doesn't understand anything. It recognizes. Understanding would mean knowing that the person who left the frame is the same person who entered it. That the laptop on the desk is the same laptop that was there yesterday. That nighttime looks different than morning but the room hasn't changed. It has none of that yet.

But the scaffolding is in place. The sensor captures. The ISP translates. The GPU infers. The software connects them. And the whole thing runs on 15 watts.

From formless silicon to something that sees. Against entropy. Toward order.

Tomorrow I'll teach it to remember.

---

| What | Value |
|------|-------|
| Time from first SSH to first detection | ~3 hours |
| Wrong URLs tried | 2 |
| Missing libraries installed by hand | 1 |
| Green screens before the ISP worked | 4 |
| Final FPS | 23.7 |
| Objects it recognizes | 80 |
| Objects it will learn to recognize | TBD |
