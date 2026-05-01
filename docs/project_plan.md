# Project Plan & Roadmap

> **Master plan for the project as a whole.** Read alongside `docs/site_plan.md` (which covers the portfolio website) and `CLAUDE.md` (which covers the basics).

## Why this project exists

Paul is preparing to apply to a **physical-AI / computer-vision team at Walmart** that uses cameras for store operations. The portfolio piece for that interview is this project: a self-contained edge-AI camera that tracks people, computes per-zone analytics, runs reliably on a Jetson Orin Nano, and is documented as a build journey on a public website.

What Walmart-style CV teams actually care about (the patterns the project is built to demonstrate):
- **Footfall analytics** — people entering/exiting zones, counts over time
- **Queue/wait analysis** — how many people in a queue, how long each waits
- **Shelf-state monitoring** — stocked / disturbed / empty
- **Loss prevention** — anomaly patterns (dwell-time, restricted zones)
- **Worker safety** — PPE compliance, no-go zone breaches

All of these share a common shape:
1. **Detection** of generic classes (person, etc.)
2. **Tracking** — same identity across frames
3. **Spatial reasoning** — image-space polygons mapped to scene meaning
4. **Aggregation** — counts, durations, rates, events
5. **Reliability** — runs at edge for hours/days, not just demos

What Walmart specifically *avoids*: face recognition, identifiable footage storage. The system is built to produce **anonymous metrics only**.

## Current state (2026-04-30, end of session)

- Jetson Orin Nano 8GB, JetPack 6.2 (L4T 36.5.0), kernel 5.15.185-tegra — provisioned and stable
- ArduCam UC-873 Rev D (Sony IMX519, 16MP) on CSI — streaming via GStreamer at 23.7 FPS
- YOLO11n running on GPU at 23.7 FPS @ 1080p, ~80 COCO classes
- Network streaming mode (Mac → Jetson → Mac) working at 5.7 FPS
- **Manual autofocus working** — direct AK7375 wire protocol via `i2ctransfer` (committed in `aa42f0b`)
- **One-shot autofocus working** — Tenengrad hill-climb, converges in ~9s, parks at peak (committed in `ed169cf`)
- SSH key auth from Mac → Jetson (Apr 16). Read `docs/ssh_jetson.md` before any SSH commands.
- 2 commits ahead of `origin/main`, working tree has uncommitted handoff docs and tonight's media assets

**Step 1 of 15 (continuous AF) is complete.** Steps 2–15 still ahead.

## The 15-evening plan

Each evening produces something demonstrable. Talking points are interview-ready one-liners.

| # | Goal | Deliverable | Talking point |
|---|---|---|---|
| 1 ✅ | Continuous AF | Tenengrad hill-climb, one-shot AF | "I implemented autofocus from scratch via direct I2C control on a chip whose protocol wasn't exposed by the installed driver." |
| 2 | Object tracking | Persistent track IDs via Ultralytics `model.track(persist=True)` (ByteTrack/BoT-SORT under the hood) | "I added multi-object tracking; ByteTrack runs on CPU in parallel with GPU inference, no extra latency." |
| 3 | Zones + people counter | Polygon zones in image coords, entry/exit events on boundary crossing | "I built scene-aware analytics — events tied to spatial zones, not just frame-level detections." |
| 4 | Dwell time + restricted zone | Per-track time-in-zone tracking, alert event on no-go zone breach | "Three Walmart-shape metrics on one detection+tracking backbone." |
| 5 | SQLite persistence | Events table + per-second-summarized counts, ~7-day retention with rotation | "Local SQLite store — you can ask 'how many entered between 6 and 7 PM' without re-running the model." |
| 6 | Dashboard v1 | Flask/FastAPI on Jetson serving `/stream.mjpeg` (annotated live) + `/` (counter + 5-min chart via Chart.js) | "Analytics served from the Jetson itself — no cloud round-trip, no external dependencies." |
| 7 | Hardware: Arduino + OLED | Arduino Uno driving GME12864-11 OLED (SSD1306 128×64) over USB serial; Jetson POSTs stats; physical display shows "PEOPLE IN ZONE: 3 / TOTAL: 47" | "Edge analytics with a physical readout — same pattern as in-store kiosks." |
| 8 | Hardware: PIR wake-on-motion | HC-SR501 PIR triggers Jetson to start inference; idles when scene empty | "PIR + camera mirrors real edge-cam architectures — always-on motion sensor, wakeable GPU." |
| 9 | TensorRT | `model.export(format='engine')`, re-time, document the FPS bump | "Optimized YOLO11n with TensorRT — went from X FPS to Y FPS, headroom for multi-camera." |
| 10 | Soak test | 4-hour run with structured logging; catalog every failure mode observed | "Ran a 4-hour soak test and characterized failure modes." |
| 11 | Robustness fixes | Fix top 2–3 issues from soak (e.g., ID-flicker buffer tuning, AF re-trigger logic, AE settle handling) | "Documented 8 failure modes, fixed the 3 worst, listed the rest as future work." |
| 12 | systemd service + healthcheck | `/etc/systemd/system/jetson-analytics.service`, auto-restart, `/health` endpoint exposing FPS / uptime / last-event ts | "Deployed as a systemd unit — runs unattended, restarts on crash, healthcheck for monitoring." |
| 13 | Honest evaluation | Hand-label 30 min of recorded video, compute precision/recall on entry counter, document the misses | "On a 30-min validation slice: 92% precision, 87% recall — main failure mode was overlapping people at the threshold." |
| 14 | README + site polish | Final README, architecture diagram, screenshots, mobile responsive, OG-image | "Polished portfolio surface — paulsong-jetson.vercel.app." |
| 15 | Demo video | 90-second video — scene → annotated stream → dashboard → physical OLED → SQLite query | "Linkable artifact for resume." |

**Site work is interleaved**, not bolted on at the end. Each Jetson-side evening also gets 30–60 minutes for site updates (narrative entry + new media + chart). See `docs/site_plan.md` for site-specific details.

## Use cases — chosen for v1

**People counter + dwell time + restricted zone** — three Walmart-shape metrics in one demo, all sharing the same detection+tracking backbone. One scene with three polygons:

- **Entry zone** — count crossings (footfall analog)
- **Dwell zone** — measure per-track time inside (engagement analog)
- **No-go zone** — emit event on entry (restricted-area / loss-prevention analog)

The system produces all three metrics simultaneously from the same frame stream.

If priorities shift toward fine-tuning or shelf monitoring, the alternative is a **shelf-state monitor** (stocked/disturbed/empty) — but that requires labeling 200+ shelf images and is more work.

## Hardware loadout

### In v1 (chosen)

- **Arduino Uno** — driving the OLED. USB serial from Jetson. Deterministic, easy to debug.
- **GME12864-11 OLED** — 128×64 monochrome, SSD1306-class. Physical stats display. Use the `Adafruit_SSD1306` or `u8g2` Arduino library — the GME12864 is a standard SSD1306 module, common addresses `0x3C` or `0x3D`.
- **HC-SR501 PIR motion sensor** — wake-on-motion gating. Two trim pots on back for sensitivity and time delay.
- **Breadboard + jumper wires** — for the OLED + PIR wiring.
- **USB cable** — Jetson ↔ Arduino.

### On hand but not used in v1

These are available for future extensions but explicitly **not part of the 15-evening plan** — don't pull them in without explicit scope change:

- Raspberry Pi — could be a second camera node later (Wi-Fi multi-camera demo)
- ESP32 — could replace Arduino if Wi-Fi is wanted instead of USB tether
- Servo (small, ~9g) — could become a camera pan-tilt mount that auto-tracks the most prominent detected person (good extension #1 if time allows)
- Stepper motor — overkill for camera pan; not used
- 2-channel relay module — could fire a buzzer/light on no-go-zone breach (good extension #2)
- Photoresistor (LDR) — sensor fusion: trigger AF re-run when ambient light changes
- DHT temp/humidity — fun mashup but not Walmart-shape; skip
- Obstacle avoidance / ultrasonic — duplicates camera with worse data; skip

## Explicitly out of scope for v1

Don't build these even if tempting:
- Custom YOLO fine-tuning (only if a stock-class genuinely fails *and* labeled data is available)
- Multi-camera (mention as future work; don't build)
- Cloud sync / database in the cloud (defeats the edge story)
- DeepSORT or fancy ReID (ByteTrack is plenty)
- Face recognition (Walmart specifically avoids this)
- Audio
- Public-facing live demo from Jetson (use recorded videos in the site instead)

## Known problems and mitigations (foresight)

Anticipated issues, ordered by probability of biting us. Document the failure mode in evening 10 when we hit them; fix the top three in evening 11.

| Problem | Mitigation |
|---|---|
| **Track ID flicker** — same person gets new ID after 0.5s occlusion. Wrecks dwell-time and entry counts. | Tune ByteTrack `track_buffer` to 30–60 frames. Smooth dwell metrics over rolling windows. Accept ±10% error. |
| **Continuous AF fights detection** — moving lens blurs frames mid-capture, detection drops. | Make AF event-driven, not periodic. Trigger only on scene change (histogram delta over threshold). Hold focus stable otherwise. |
| **Jetson thermal throttle** — sustained TensorRT + tracking + dashboard heats the SoC. | `tegrastats` log it. Add a fan if needed. Throttle FPS to 30 in software if temp > 70°C. |
| **MJPEG over Wi-Fi is bandwidth-heavy** — ~50Mbps at 1080p kills Wi-Fi. | Downscale dashboard stream to 720p or 480p. Keep full-res only for inference. |
| **SQLite grows forever** | Daily aggregation: roll fine-grained events to hourly buckets, prune originals after 7 days. |
| **Frame timestamp drift** — `time.time()` at log-time vs actual capture time differs 50–200ms. | Capture frame_number → timestamp at the very first read, propagate through pipeline. |
| **Low-light mis-detects** — fluorescent moiré, dim-image noise. | Document, don't paper over. Honest failure mode. |
| **AF drift over hours** — VCM coil drift, thermal expansion. | Periodic re-AF every N min if scene-change detected. |
| **Memory leak in long runs** | 6-hour soak + watch RSS. Fix worst offender (usually a numpy view not released). |
| **Dashboard breaks soak test** — Flask request handling stutters main loop. | Run dashboard server in separate thread/process, communicate via queue. |
| **Privacy in published demo video** — recording yourself or guests publicly. | Blur faces in the published video. Mention as deliberate choice in README. |
| **Walmart-style privacy expectations** — interviewers will ask. | Anonymous metrics only. Don't store frames, only events. Document this as an explicit design decision. |

## How the website interleaves

The site is built **alongside** the project, not after. See `docs/site_plan.md` for stack and structural decisions.

- **Site evening 1**: scaffold Next.js + Tailwind + Recharts, deploy hello-world to Vercel from `site/` subfolder
- **Project evenings 2–13**: each evening, 30–60 min added to the site — write the narrative entry for what was built, add any new media (photos, charts), update status
- **Project evening 14**: dedicated polish day — typography, mobile responsiveness, OG-image, final QA
- **Project evening 15**: 90-second demo video, embed in site

Total project: ~17–18 evenings (15 Jetson-side + 3 site-equivalent spread across them).

## How Paul works

- Wants concept-first explanations, not just commands
- Edits locally on Mac, runs on Jetson — for site work, both are local on Mac
- Confirm before destructive or hard-to-reverse actions (installs, deploys, pushes, restructures)
- He'll push back when something feels off — take it seriously, don't defend the original plan
- Often asks for "explain like I'm 15" — storytelling explanations welcome
- Likes commits with substantive messages (see recent git log for style — em-dashes, body paragraphs, file-by-file notes)

## Where to find things

- Master code: this monorepo
- Working camera code: `detect_local.py`, `arducam_focus/`
- Technical references: `docs/architecture.md`, `docs/autofocus.md`, `docs/jetson_setup.md`, `docs/ssh_jetson.md`
- Build journal: `narrative.md` (prose), `logs/01-setup.md`, `logs/02-csi-camera.md`, `logs/03-autofocus-investigation.md`
- First images: `first_observations/`
- Tonight's autofocus media: `media/autofocus_2026-04-30/`
- Site plan: `docs/site_plan.md`
- This roadmap: `docs/project_plan.md`
