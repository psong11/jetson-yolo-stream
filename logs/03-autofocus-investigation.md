# Log 03 — Autofocus Investigation (Deferred)

**Date:** 2026-04-16

## What I Did

Sat back down at the Jetson for the first time since first-light. Camera was still connected. Took a test photo. It was dark, washed-out, and blurry. Spent the rest of the session trying to understand why and whether I could fix it.

### Warm-up Problem (Solved)

First photo was `gst-launch-1.0 ... num-buffers=1` — one frame, straight off the sensor. It came out murky and warm-tinted.

**Concept learned: ISP convergence.** The sensor has no idea how bright or what color the scene is when it powers on. The ISP runs an Auto-Exposure (AE) loop — capture → measure → adjust shutter/gain → capture — and needs ~10–30 frames (0.3–1 sec) to settle. Auto-White-Balance (AWB) runs the same way. Asking for frame 1 gets you the result before any of that adjustment has happened.

**Fix:** `num-buffers=30` with `multifilesink`, then keep frame 29 (or 44). Exposure and color instantly looked correct.

### Autofocus Problem (Deferred)

Even warmed up, images were uniformly soft. Not depth-of-field soft (where one plane is sharp and the rest isn't) — *everything* soft. That's a focus issue.

The ArduCam UC-873 has a voice-coil motor (VCM) autofocus. A tiny electromagnet that slides the lens along its optical axis. You can hear the lens element rattle faintly when you shake the module — free-moving mass, not glued down.

**First attempt: V4L2 focus control.** Dead end. Ran `v4l2-ctl -d /dev/video0 --list-ctrls` and the only exposed knobs were `gain`, `exposure`, `sensor_mode`, `frame_rate`, and a pile of sensor metadata. No `focus_absolute`. The driver I installed back on Apr 12 (`install_full.sh -m imx519` from ArduCam) streams video but doesn't expose focus.

**Second attempt: direct I2C to the VCM.** The VCM driver chip lives on the same I2C bus as the sensor, at a different address. Spent a while discovering the map:

- Sensor `imx519` at `bus 10, addr 0x1a` (shows as `UU` in i2cdetect — "kernel driver attached")
- VCM at `bus 10, addr 0x0c` — **but only visible during active streaming** (the chip is power-gated through the sensor's voltage rail)
- EEPROM at `bus 10, addr 0x50` (likely lens calibration data)

**Concept learned: power-gated I2C peripherals.** A slave on an I2C bus can be physically connected but electrically dark. If its VDD comes from a rail that's only enabled when another component is in use, you won't see it on the bus when idle. The VCM needs the sensor's streaming regulator up to talk.

Wrote a sweep script: start a streaming pipeline in the background (so the VCM rail stays hot), then push focus values 50, 150, 300, 450, 600, 750, 900 via `i2cset`, capturing a frame at each. The DW9714 protocol is two bytes — upper 6 bits of the 10-bit value, then lower 4 bits shifted up.

All seven images looked identical. Focus=50 (near infinity) and focus=900 (near macro) should produce dramatically different results at a handheld distance. They didn't.

**Third attempt: read ArduCam's own `Focuser.py` tool to see what they do.** The file is one line of real code:

```python
os.system("v4l2-ctl -d {} -c focus_absolute={}".format(self.dev, value))
```

They don't do direct I2C at all. They assume `focus_absolute` is exposed as a V4L2 control. Which implies: the driver variant they expect (**Jetvariety**) is different from the one I installed (`-m imx519`, specific to IMX519 CSI). The one I have streams but doesn't wire the VCM into the V4L2 control surface.

**Why our I2C writes didn't work: best guess.** NVIDIA's Argus stack (the closed-source ISP layer behind `nvarguscamerasrc`) is probably writing to `0x0c` every frame with its own focus value, overwriting our writes within milliseconds. We couldn't win the race. Or the chip isn't a pure DW9714 and needs some init sequence we don't know. Either way, direct I2C isn't a viable path without the right driver in place.

### The Decision

Proper fix = install ArduCam's Jetvariety driver variant. That means replacing the currently-working driver, `sudo apt`, reboot, real chance of breaking something. For a project where YOLO detection is the goal and detection tolerates soft images, not worth it tonight.

Factory focus is whatever ArduCam parked the lens at at manufacture. For my indoor desk scenes at 1–4 feet it's genuinely bad. For a YOLO camera pointed across a room, it's probably fine.

Deferred. Will come back when sharp capture actually matters.

### Side Milestone: SSH Key Auth

Set up SSH key auth from the MacBook to the Jetson so Claude can run commands directly via `ssh paul@jetson.local '<cmd>'` from its Bash tool. No more copy-pasting terminal commands between two windows. Documented operational rules for this in `docs/ssh_jetson.md` (quote-escaping, backgrounded processes, sudo allowlist, safety confirmations) and wired it into `CLAUDE.md` so future sessions auto-read it.

Also added a narrow `sudoers.d` entry allowing passwordless `i2cset`, `i2cdetect`, `i2cget` — scoped so non-interactive SSH sessions can run I2C diagnostics without hanging on a password prompt.

## Concepts Learned

- **ISP convergence** — first-frame images are always bad; AE and AWB need several frames of feedback before they're tuned
- **VCM autofocus** — a voice-coil motor physically moves the lens element along the optical axis; controlled via an I2C driver IC (DW9714 and variants); needs its power rail up to respond
- **Power-gated I2C peripherals** — slaves can be physically present but electrically invisible when their rail is off
- **V4L2 control surface vs I2C** — the kernel exposes device knobs as "V4L2 controls" (`v4l2-ctl -c <name>=<val>`); what controls get exposed depends entirely on the driver; without the right driver, hardware you can physically reach is still unreachable from user-space
- **Argus** — NVIDIA's closed-source libargus stack sits between GStreamer (`nvarguscamerasrc`) and the sensor, and it owns the I2C channel to the sensor + VCM while streaming; fighting it from user-space is a losing battle
- **Driver variants** — one vendor can ship multiple driver packages for the same hardware with different capability matrices; ArduCam's `-m imx519` (installed) is not the same as their Jetvariety variant (not installed, exposes AF)

## Files Added / Modified

- `docs/ssh_jetson.md` — new: SSH operational playbook
- `CLAUDE.md` — added "Driving the Jetson over SSH (MANDATORY)" section, updated current state
- `/etc/sudoers.d/paul-i2c` on Jetson — NOPASSWD for `i2cset`/`i2cdetect`/`i2cget` only
- `~/.ssh/authorized_keys` on Jetson — Mac's ed25519 public key
