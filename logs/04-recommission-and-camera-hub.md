# Log 04 — Recommission, Real Resolution & the Camera Hub

**Date:** 2026-08-06 → 2026-08-07

## What I Did

### Recommissioning After the Move (Aug 6, night)

The Jetson sat dark for ~8 weeks through an apartment move. Getting it back:

- **USB-C device mode was the way in** — no monitor, no WiFi needed. Plug the
  cable, the Jetson appears as a network interface, `ssh paul@192.168.55.1`.
- **The new apartment's WiFi is a hidden SSID (A-510).** The Jetson scanned 54
  APs and couldn't see it — hidden networks don't beacon their name, so
  connecting requires `802-11-wireless.hidden yes` in the NetworkManager
  profile to send a directed probe. This will bite every future device here.
- **Installed Tailscale** (signed apt repo, jammy). The Jetson is now `jetson`
  on the tailnet from anywhere, same as the Pis. No IP pinning anywhere — the
  wy2z 15-day outage was caused by exactly that.
- Camera ribbon was re-seated after the move; wrote `docs/camcheck.sh` to
  verify the full chain (video node → sensor on I2C → warmed-up capture → VCM
  enumerating) in one command.

### Two Measurement Traps (Aug 6, night)

Autofocus "worked" but landed on DAC 896 with photos still soft. Two lessons:

1. **Single-frame sharpness scores are garbage on flickering subjects.** A
   laptop screen's PWM + refresh beat made Tenengrad swing 35% at a *fixed*
   lens position. The hill-climb was chasing noise. Fix: median-of-N frames
   per position (`focus_median.py`) — spreads dropped under 1%.
2. **Variance-of-Laplacian rises with noise, not just detail.** Turning the
   ISP denoiser off scored 80× "sharper" while only adding grain. Never trust
   a sharpness number without looking at a 1:1 crop.

Also: `pkill -f nvarguscamerasrc` over SSH matches its own command line and
kills the shell. Use `nvargusc[a]merasrc`.

### The Resolution Discovery (Aug 7, daylight)

The camera never took bad photos — it was being asked for small ones. Every
script since the YOLO days requested 1920×1080: **2.1 MP, an 8× pixel
discount, and a 16:9 crop of the sensor's wider 4:3 field.** Full mode 0
(4656×3496 @ 9 fps) resolves box text and logos across a room.

Two rules that made 16MP stills actually work:
- **The VCM loses power when the stream stops** — focus must be set inside
  the same pipeline that captures. Focus-then-shoot as two pipelines silently
  reverts the lens to DAC 0.
- **A found DAC transfers between sensor modes** (the optics don't change),
  so AF can run cheap at 1080p and be re-applied in the 16MP stream.

### Fast Autofocus (Aug 7)

Replaced the 33-step grid sweep with **golden-section search**: 13
measurements, ~5 s (`arducam_focus/af_fast.py`). Why not one-shot like an
iPhone: phones use phase-detect pixels that report direction *and* distance of
defocus from a single frame; the IMX519 has PD pixels but this driver path
doesn't expose them, and a defocused frame alone can't tell near from far
(blur is symmetric). Contrast search is the honest option — it just needed to
be a smart search. `arducam_focus/snap.sh` = point-and-shoot: AF, then a
focused 16MP still, one command.

### The Camera Hub (Aug 7)

`liveview.py` grew from "MJPEG stream" into the camera's single owner with an
HTTP surface — the seed of the control hub and the forklift stack:

- Live MJPEG at `http://jetson:8080` (tailnet-wide via MagicDNS), YOLO overlay
- **Detection cadence decoupled from video**: YOLO runs every Nth frame
  (live-adjustable from the page), last boxes redrawn on every frame — video
  holds ~30 fps while GPU load drops
- **Snap-while-streaming** (iPhone-style): saves the clean current frame
  without touching the stream; gallery of `~/snapshots` on the page
- Autofocus as an endpoint + runs automatically at startup
- **Graceful degradation, tested**: `isOpened()` returns true even when Argus
  refuses the capture session — the only honest liveness check is a real
  frame arriving. Without a camera the server stays up: gallery works, page
  banner says NO CAMERA with the specific reason, camera endpoints 503.

Deferred: the systemd unit (true daemon-hood). Cons that deferred it: the hub
would own the camera at every boot (blocking snap.sh & manual work), sudo
friction on every redeploy while iterating, always-on YOLO wattage, and
Restart=always masking crash loops. It earns systemd when it rides the
forklift.

## Concepts Learned

| Concept | What It Means |
|---------|---------------|
| Hidden SSID | No beacon → invisible to scans; client must probe by name (`hidden yes`) |
| MagicDNS | Tailscale resolves machine names (`jetson`) tailnet-wide — URLs beat IPs |
| Median-of-N focus metric | Kills flicker noise that makes single-frame scores lie by 35% |
| Sensor modes | 1080p is a cropped 2.1MP window; mode 0 is the full 16.3MP 4:3 sensor |
| VCM power gating | Focus motor lives on the sensor's streaming rail; focus dies with the stream |
| PDAF vs contrast AF | Phase-detect pixels give direction+distance in one frame; contrast AF must search — golden-section makes the search ~13 probes |
| Argus single consumer | One capture session per sensor; a second pipeline builds fine, then gets no frames |
| `isOpened()` false positive | Pipeline construction ≠ frames flowing; probe for a real frame |
| Daemon | A program that stays alive and owns a resource; everything else sends requests (the hub is one, minus auto-start) |

## Files Added

- `docs/camcheck.sh` — one-command camera verification after re-seating
- `arducam_focus/af_fast.py` — golden-section AF (~5 s)
- `arducam_focus/snap.sh` — point-and-shoot 16MP still
- `arducam_focus/autofocus_run.sh` — stream + hill-climb + park wrapper
- `liveview.py` — the camera hub (stream, YOLO, snap, gallery, focus API)
