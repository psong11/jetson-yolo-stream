#!/bin/bash
# camcheck — verify the ArduCam is alive after re-seating the ribbon cable.
# Captures a properly warmed-up frame and confirms the VCM appears on I2C.
#
# Source of truth: docs/camcheck.sh in the repo. Install with:
#   scp docs/camcheck.sh paul@jetson:~/camcheck.sh && ssh paul@jetson 'chmod +x ~/camcheck.sh'
#
# Usage on the Jetson:  ~/camcheck.sh
set -uo pipefail

OUT=/tmp/camcheck
FAIL=0

# NOTE: always capture i2cdetect output into a variable before grepping it.
# Piping straight into `grep -q` makes grep exit on first match, which SIGPIPEs
# i2cdetect; under `set -o pipefail` that poisons the pipeline's exit status and
# produces a false negative. This bit us on 2026-08-06.
scan_bus10() { sudo -n i2cdetect -y -r 10 2>/dev/null; }

echo "=== 1. clearing stale pipelines ==="
pkill -f nvarguscamerasrc 2>/dev/null && echo "  killed a stale pipeline" || echo "  none running"
sleep 1

echo "=== 2. camera node ==="
if ls /dev/video0 >/dev/null 2>&1; then
  echo "  /dev/video0 present"
else
  echo "  *** /dev/video0 MISSING — ribbon not seated, or seated backwards."
  echo "  *** Power off, unplug the barrel jack, re-seat both ends, try again."
  exit 1
fi

echo "=== 3. sensor on I2C bus 10 ==="
SCAN=$(scan_bus10)
if printf '%s\n' "$SCAN" | grep -q 'UU'; then
  echo "  sensor 0x1a detected (UU — kernel driver attached)"
elif printf '%s\n' "$SCAN" | grep -qE '^10:.* 1a '; then
  echo "  sensor 0x1a on the bus, but no kernel driver bound"
  FAIL=1
else
  echo "  *** sensor not on bus 10 — check the camera-board end of the cable"
  FAIL=1
fi

echo "=== 4. warm-up capture (30 frames, keeping the last) ==="
rm -rf "$OUT"; mkdir -p "$OUT"
gst-launch-1.0 nvarguscamerasrc num-buffers=30 \
  ! 'video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1' \
  ! nvjpegenc ! multifilesink location="$OUT/frame-%05d.jpg" \
  > /tmp/camcheck_gst.log 2>&1

LAST=$(ls "$OUT"/frame-*.jpg 2>/dev/null | tail -1)
if [ -n "$LAST" ]; then
  cp "$LAST" "$OUT/first_light.jpg"
  echo "  captured $(ls "$OUT"/frame-*.jpg | wc -l) frames"
  echo "  kept $(basename "$LAST") -> $OUT/first_light.jpg ($(du -h "$OUT/first_light.jpg" | cut -f1))"
else
  echo "  *** capture produced nothing — see /tmp/camcheck_gst.log"
  tail -5 /tmp/camcheck_gst.log | sed 's/^/      /'
  FAIL=1
fi

echo "=== 5. VCM check (streams briefly so 0x0c powers up) ==="
nohup gst-launch-1.0 nvarguscamerasrc \
  ! 'video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1' \
  ! fakesink > /tmp/camcheck_vcm.log 2>&1 < /dev/null & disown
sleep 4
if ! pgrep -f nvarguscamerasrc >/dev/null 2>&1; then
  echo "  *** stream died before the scan — see /tmp/camcheck_vcm.log"
  tail -5 /tmp/camcheck_vcm.log | sed 's/^/      /'
  FAIL=1
else
  SCAN=$(scan_bus10)
  if printf '%s\n' "$SCAN" | grep -qE '^00:.* 0c '; then
    echo "  VCM 0x0c present while streaming — autofocus reachable"
  else
    echo "  *** VCM 0x0c not on the bus even while streaming"
    FAIL=1
  fi
fi
pkill -f nvarguscamerasrc 2>/dev/null
sleep 1

echo
if [ "$FAIL" -eq 0 ]; then
  echo "ALL CHECKS PASSED — pull the image with:"
else
  echo "FINISHED WITH WARNINGS above. Image (if any):"
fi
echo "  scp paul@jetson:/tmp/camcheck/first_light.jpg ~/Desktop/"
