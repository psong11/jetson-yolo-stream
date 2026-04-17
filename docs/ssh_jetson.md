# SSH Playbook — Running Commands on the Jetson from Claude

**IMPORTANT for Claude:** Read this file *before* running any `ssh paul@jetson.local` commands. It documents how to drive the Jetson remotely without causing hangs, hidden state, or destructive surprises.

---

## 1. Connection basics

- **Host:** `paul@jetson.local` (mDNS; falls back via router DHCP if `.local` fails)
- **Auth:** SSH key `~/.ssh/id_ed25519` (set up 2026-04-16). No password prompts expected.
- **Quick health check pattern:**
  ```bash
  ssh paul@jetson.local 'uptime; df -h / | tail -1; ls /dev/video0 2>&1'
  ```

If SSH fails:
1. Verify the Mac can resolve `jetson.local` (`ping -c 1 jetson.local`).
2. If mDNS is broken, ask Paul for the Jetson's IP (`ip addr` on the Jetson).
3. Don't try `StrictHostKeyChecking=no` or other auth bypasses without asking.

---

## 2. Running commands — the one-shot pattern

**Always use the `ssh host 'command'` form** inside the `Bash` tool. Do not open interactive shells — my `Bash` tool has no TTY.

```bash
ssh paul@jetson.local 'ls -lh /dev/video*'
```

For multiple commands, chain them inside the quotes with `&&` or `;`:

```bash
ssh paul@jetson.local 'cd ~/snapshots && ls -lh | tail -5'
```

**For long or multi-line commands → write a script, SCP it, then execute it.** Inline multi-line commands break under quote-escaping and have no good recovery when they fail mid-way.

```bash
# On Mac — author locally
cat > /tmp/sweep.sh <<'EOF'
#!/bin/bash
set -e
# ... whatever
EOF

# Ship it
scp /tmp/sweep.sh paul@jetson.local:~/
ssh paul@jetson.local 'chmod +x ~/sweep.sh && ~/sweep.sh'
```

---

## 3. Quote-escaping (the #1 foot-gun)

GStreamer pipelines contain single quotes, parentheses, and `!` — all of which zsh/bash interpret. Rules:

- **Wrap the whole SSH command in single quotes.** Inside, use double quotes for GStreamer caps:
  ```bash
  ssh paul@jetson.local 'gst-launch-1.0 nvarguscamerasrc num-buffers=30 ! "video/x-raw(memory:NVMM),width=1920,height=1080" ! nvjpegenc ! filesink location=/tmp/out.jpg'
  ```
- **If a command is complex enough to need nested quotes,** write a script and SCP it instead. Don't try to be clever.
- **Never use `!` inside double-quoted strings in bash history mode** — it triggers history expansion. Single-quote the outer shell, or escape.

---

## 4. Background processes — a trap

A naked `&` over SSH will sometimes hang the SSH session because SSH waits for the background process's stdout/stderr to close. Use this pattern instead:

```bash
ssh paul@jetson.local 'nohup gst-launch-1.0 ... > /tmp/gst.log 2>&1 < /dev/null & disown; echo started'
```

The critical pieces:
- `nohup` — survives SSH disconnect
- `> /tmp/gst.log 2>&1` — redirect both stdout + stderr to a file
- `< /dev/null` — close stdin so SSH doesn't wait on it
- `& disown` — detach from the shell's job table
- `echo started` — gives SSH something to return so it exits cleanly

To stop a backgrounded process later, track it by name:

```bash
ssh paul@jetson.local 'pkill -f nvarguscamerasrc'
```

**Never leave a background gst pipeline running across commands without an explicit kill.** The camera has one ISP channel — a stale pipeline blocks the next one.

---

## 5. `sudo` — narrow allowlist

Paul has `NOPASSWD` configured **only for these commands** (see `/etc/sudoers.d/paul-i2c` on the Jetson):

- `/usr/sbin/i2cset`
- `/usr/sbin/i2cdetect`
- `/usr/sbin/i2cget`

**Anything else requiring `sudo` will hang forever** waiting for a password over non-interactive SSH. If you need other `sudo`, either:
1. Ask Paul to run it himself in his terminal, **or**
2. Use `sudo -n <cmd>` (non-interactive) so it fails immediately with a clear error instead of hanging.

Do NOT expand the NOPASSWD list without asking Paul.

---

## 6. File transfer

- **Pull from Jetson → Mac:** `scp paul@jetson.local:~/file ~/Desktop/`
- **Push Mac → Jetson:** `scp ~/file paul@jetson.local:~/`
- **Recursive:** add `-r`
- **Glob patterns:** quote the remote side — `scp 'paul@jetson.local:~/focus_*.jpg' ~/Desktop/`

Paul's convention from CLAUDE.md: **edit locally on Mac, run remotely on Jetson.** Never edit source files in place on the Jetson.

---

## 7. Output management

`gst-launch-1.0` is chatty — every run prints ~30 lines of NvArgus status. That clutters my tool results and eats context. Defaults:

- Redirect noisy tools to a logfile: `> /tmp/gst.log 2>&1`
- Pull only the last N lines if you need to check it: `tail -20 /tmp/gst.log`
- For loops with per-iteration output, echo one summary line per iteration rather than raw tool output

---

## 8. Project-specific quick reference

Facts that come up repeatedly. Confirm with `v4l2-ctl` / `i2cdetect` before trusting these if it's been a while.

| Thing | Value |
|---|---|
| Camera node | `/dev/video0` |
| Sensor I2C | bus 10, addr `0x1a` (and mirrored on bus 2) |
| VCM (autofocus) I2C | bus 10, addr `0x0c` — **only powered while sensor is streaming** |
| Focus EEPROM | bus 10, addr `0x50` |
| VCM protocol | DW9714: 2 bytes, `(f>>4)&0x3F` and `(f&0x0F)<<4`, range 0–1023 |
| GStreamer source | `nvarguscamerasrc` (never `cv2.VideoCapture(0)` — green frames) |
| HW JPEG encoder | `nvjpegenc` |
| Snapshot dir | `~/snapshots/` |
| Project repo on Mac | `/Users/paulsong/Documents/learn/jetson-yolo-stream` |
| Docs | `docs/architecture.md`, `docs/jetson_setup.md`, `docs/ssh_jetson.md` (this) |

---

## 9. Things that require explicit confirmation from Paul

Never do these silently, even if they'd solve the problem:

- `rm -rf` anything outside `/tmp/` or a file I just created this session
- Modify `/etc/`, `/boot/`, device tree, udev rules, systemd units
- Install or upgrade system packages (`apt`)
- `pip install` into the system Python — always ask; venvs only
- Edit `sudoers` / `sudoers.d/*`
- Flash, rebuild, or modify kernel modules
- Touch the JetPack base image or anything under `/usr/src/nvidia/`
- Power / reboot the Jetson (`reboot`, `shutdown`, `systemctl isolate`)
- Git operations that rewrite published history (force-push, rebase onto pushed branch)

When in doubt, ask. Blast radius on an SBC is high — bricking the SD card means a full JetPack reflash.

---

## 10. When not to SSH at all

- **Interactive tools** (vim, htop, menuconfig, `python` REPL, `sudo apt` confirmations). Ask Paul to run these himself.
- **Anything requiring a display.** The Jetson is headless — no `$DISPLAY`, no GUI preview. Use file + SCP to see images.
- **Multi-step workflows that should survive crashes.** Write a script and execute it as a unit; don't orchestrate step-by-step over SSH.

---

## 11. First-move checklist for any Jetson session

Before running real work, confirm the environment:

```bash
ssh paul@jetson.local 'whoami && uname -r && uptime && df -h / | tail -1 && ls /dev/video0 /dev/i2c-10 2>&1'
```

That single line verifies: SSH+key works, correct kernel, load average reasonable, disk not full, camera node present, I2C bus present. One tool call, one clear signal.
