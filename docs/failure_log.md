# Failure Log — Mistakes Claude Has Made On This Project

Every entry here cost real time. Read this before working on the Jetson.
Format is deliberate: **symptom → cause → rule**. The rule is the point.

Marked **[REPEAT]** where the same mistake was made twice. Those are the
expensive ones.

---

## 1. Remote execution

**Killed my own SSH session with `pkill`.** **[REPEAT — happened 2026-04, again
2026-08-24]**
`pkill -f nvarguscamerasrc` matches the SSH command's *own* command line and
kills the shell. The bracket trick (`nvargusc[a]merasrc`) fixes that — but on
2026-08-24 I wrote `pkill -f "livevie[w]\.py --yolo --port 8081"` and still
died, because the literal text `liveview.py --yolo --port 8081` appeared
*earlier in the same command* (in the `nohup` that started it).
→ **Rule:** bracket the pattern *and* never put the plain target string
anywhere else in the same command line. Safest: `pkill -F` a pidfile, or kill
by PID captured at launch. Verify with `pgrep -af` before assuming it worked.

**Gave Paul commands he ran on the wrong machine.** Twice he pasted `nmcli` /
`curl` into his Mac and got `command not found` — my instructions didn't make
the target obvious.
→ **Rule:** every command for the Jetson starts with `ssh` in the same block,
or explicitly says "your prompt must read `paul@jetson`". Never hand over a
bare command that only makes sense remotely.

**`grep -q` under `set -o pipefail` broke camcheck.** `grep -q` exits at the
first match and SIGPIPEs `i2cdetect` upstream; `pipefail` then reports failure,
producing false "no VCM found" results.
→ **Rule:** capture command output into a variable first, then grep the
variable. Never pipe a slow producer into an early-exiting consumer under
`pipefail`.

**`tee /dev/stderr` — Permission denied.** Fine on a TTY, fails over
non-interactive SSH.
→ **Rule:** write to a real file in `/tmp`, then `cat` it.

**Multi-line and long inline commands break.** Quote-escaping and terminal
line-wrapping have caused hangs and half-run commands.
→ **Rule:** anything longer than one line: write a script locally, `scp` it,
execute it as a unit. Already in `ssh_jetson.md` §2 — follow it.

---

## 2. Measuring things

**Autofocus locked onto noise.** Hill-climb landed at DAC 896 and the photo was
soft. A laptop screen's flicker made a single-frame Tenengrad score swing 35%
at a *fixed* lens position — the search was chasing PWM beat, not focus.
→ **Rule:** never focus-score on a single frame. Median-of-N (≥5). Verify the
spread is under a few percent before trusting any peak.

**Declared the denoiser-off image "80× sharper." It was grain.**
Variance-of-Laplacian rises with noise as well as detail. I also compared
full-res shots that were out of focus, making the whole test void. I had to
retract the conclusion.
→ **Rule:** a sharpness number is a hypothesis, not evidence. Look at a 1:1
crop before claiming anything. Hold focus and lighting constant or the
comparison is worthless.

**Wrong crop math across sensor modes.** Compared a 16:9 1080p crop against the
full 4:3 sensor as if they framed the same scene.
→ **Rule:** when the sensor mode changes, the field of view changes. Derive the
mapping from landmarks in the actual images before comparing anything.

**Trusted `isOpened()`.** The GStreamer pipeline constructs successfully even
when Argus refuses the capture session.
→ **Rule:** the only proof a camera is alive is a frame arriving. Probe for
one, with a timeout.

---

## 3. Claiming things are done

**Declared the cold-boot test passed, then stopped watching.** On 2026-08-23 I
verified the hub auto-started, saw frames and autofocus, called it proven, and
moved on. The camera died four minutes later. Nobody noticed **for 23 hours**.
The test itself was valid; announcing victory and looking away was not.
→ **Rule:** verifying a system starts is not verifying it runs. For anything
meant to survive unattended, check again after minutes, not seconds — or build
the monitoring first so you don't have to.

**Shipped a hub that could not detect its own failure.** It checked the camera
once at startup and never again, so `/api/status` happily reported 30 fps off a
frozen frame for a day.
→ **Rule:** any status a human will trust must be derived from something
*current*. Report frame age, not the last number you happened to compute.

**Logged to `/tmp`.** `systemd-tmpfiles` swept the log, so when the hub went
down there was no evidence left to read.
→ **Rule:** service logs go to the journal. `/tmp` is for scratch you can
afford to lose.

**Predicted repo state instead of checking.** Claimed several unpushed commits;
there was one.
→ **Rule:** run the command. Never narrate the state of something you haven't
just looked at.

**Told Paul to restart while my deploy was still in flight.** He ran it at
22:20, my `scp` landed at 22:28, and he got the old code with no sign anything
was wrong.
→ **Rule:** finish deploying, verify the file is in place, *then* ask for the
restart. If a restart needs his password, hand it over as the last step, not
the first.

---

## 4. Writing code

**State machine clobbered its own error.** The idle branch unconditionally set
`state = "off"`, erasing `"error"` — so a failed camera reported as merely
switched off. Found by testing, not by reading.
→ **Rule:** when one field means several things, check every path that writes
it. "Stopped on purpose" and "broken" must never collapse into the same value.

**Autofocus crashed when the watchdog restarted the pipeline underneath it.**
AF held a reference to a focuser that became `None` mid-search.
→ **Rule:** anything long-running that touches the camera must re-check that
the pipeline still exists between steps, and fail cleanly when it doesn't.

**Mojibake in the UI.** A `—` escape became a literal em-dash inside the
Python page string, and the server never declared a charset — so browsers
guessed latin-1 and rendered `â€"`.
→ **Rule:** always send `charset=utf-8` and put `<meta charset="utf-8">` in the
page. Prefer ASCII in code that will be embedded in another language's string
literal; escapes get consumed by whichever layer parses first.

---

## 5. Explaining things

**"Word soup."** My explanation of camera image quality was dense enough that
Paul asked for the whole thing again.
**"Explain that like you're not a damn AI bot."** Same failure, different day.
**"Simplify how you worded the proposed plan, it doesn't make sense to me."**
Same failure, third time.
→ **Rule:** lead with the answer in plain words. One idea per sentence. Analogy
before jargon. Tables and headers are for reference docs, not for explaining a
thing to someone who just asked a question. If it needs a glossary, it's wrong.

---

## The pattern underneath

Most of these are the same two errors wearing different clothes:

1. **Trusting a proxy instead of the thing itself** — `isOpened()` instead of a
   frame, a sharpness score instead of a crop, a prediction instead of `git
   status`, a successful start instead of a running system.
2. **Stopping at the first green light.** The failures that cost the most time
   were all cases where something worked once and I stopped looking.
