#!/bin/bash
# jstatus — one-shot Jetson state snapshot for remote sessions.
# Replaces ~6 separate SSH round-trips with a single call.
# Usage: ssh paul@jetson.local '~/bin/jstatus'

divider() { printf '\n=== %s ===\n' "$1"; }

divider host
echo "user=$(whoami) host=$(hostname) kernel=$(uname -r)"
uptime

divider disk
df -h / | tail -1

divider thermal
for f in /sys/class/thermal/thermal_zone*/type; do
  zone=$(dirname "$f")
  type=$(cat "$f" 2>/dev/null)
  temp=$(cat "$zone/temp" 2>/dev/null)
  [ -n "$temp" ] && printf '  %-24s %s°C\n' "$type" "$((temp/1000))"
done

divider gpu
if command -v tegrastats >/dev/null 2>&1; then
  timeout 1 tegrastats --interval 500 2>/dev/null | head -1 || echo "(tegrastats unresponsive)"
else
  echo "(tegrastats not installed)"
fi

divider camera
ls /dev/video* /dev/v4l-subdev* 2>/dev/null | head -10
echo "--- active camera/stream procs ---"
pgrep -af 'nvargus|gst-launch|detect_local|server\.py|client\.py' | head -10
[ $? -ne 0 ] && echo "(none)"

divider i2c
printf 'buses: '; ls /dev/i2c-* 2>/dev/null | tr '\n' ' '; echo
echo "--- bus 10 (sensor=0x1a, VCM=0x0c only when streaming) ---"
sudo -n i2cdetect -y -r 10 2>/dev/null | tail -9 || echo "(i2cdetect failed — try again)"

divider tmux
if command -v tmux >/dev/null 2>&1; then
  tmux ls 2>/dev/null || echo "(no sessions)"
else
  echo "(tmux not installed — run: sudo apt install tmux -y)"
fi

divider recent-captures
echo "~/snapshots/:"
ls -lht ~/snapshots/ 2>/dev/null | head -5 | sed 's/^/  /'
echo "/tmp (images):"
ls -lht /tmp/ 2>/dev/null | grep -iE '\.(jpg|jpeg|png|mp4|h264)$' | head -5 | sed 's/^/  /'

divider done
date
