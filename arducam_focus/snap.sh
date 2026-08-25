#!/bin/bash
# snap — point-and-shoot: fast autofocus, then a full-16MP still at that focus.
# The whole reason this is one script: the focus motor is only powered while a
# stream runs, and a found DAC transfers between sensor modes (optics don't
# change) — so we AF cheaply at 1080p, then re-apply the DAC inside the 16MP
# capture stream.
#
# Usage on the Jetson:  ~/snap.sh [output.jpg]     (default ~/snapshots/snap_<ts>.jpg)
set -uo pipefail

OUT="${1:-$HOME/snapshots/snap_$(date +%Y%m%d_%H%M%S).jpg}"
STREAM=/tmp/stream

# The hub only owns the camera while its stream is running — if it is up but
# idle, the sensor is released and we can just take the shot.
HUB=$(curl -s --max-time 3 "http://localhost:8080/api/status" 2>/dev/null)
case "$HUB" in
  *'"state": "running"'*|*'"state": "starting"'*)
    echo "*** the hub is streaming and owns the camera."
    echo "*** free it without stopping the service:"
    echo "***   curl -s 'http://localhost:8080/api/camera?on=0'"
    echo "*** then turn it back on with on=1 when you are done."
    exit 1 ;;
  "")
    if pgrep -f "livevie[w]\.py" >/dev/null 2>&1; then
      echo "*** liveview is running but not answering on :8080."
      echo "*** stop it first:  sudo systemctl stop liveview"
      exit 1
    fi ;;
esac

cleanup() { pkill -f "gst-launc[h]-1.0 nvarguscamerasrc" 2>/dev/null; sleep 1; rm -rf "$STREAM"; }
trap cleanup EXIT

echo "=== 1. autofocus (1080p stream) ==="
cleanup; mkdir -p "$STREAM"
nohup gst-launch-1.0 nvarguscamerasrc \
  ! 'video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1' \
  ! nvjpegenc ! multifilesink location="$STREAM/frame-%05d.jpg" \
  > /tmp/snap_af.log 2>&1 < /dev/null & disown
for i in $(seq 1 20); do
  [ "$(ls "$STREAM"/frame-*.jpg 2>/dev/null | wc -l)" -ge 10 ] && break; sleep 1
done
python3 "$HOME/af_fast.py" > /tmp/af_run.log 2>&1
cat /tmp/af_run.log
DAC=$(awk '/^BEST/{print $2}' /tmp/af_run.log)
if [ -z "$DAC" ]; then echo "*** autofocus failed — see above"; exit 1; fi
pkill -f "gst-launc[h]-1.0 nvarguscamerasrc" 2>/dev/null; sleep 2; rm -rf "$STREAM"

echo "=== 2. 16MP capture at DAC $DAC ==="
mkdir -p "$STREAM"
nohup gst-launch-1.0 nvarguscamerasrc sensor-mode=0 \
  ! 'video/x-raw(memory:NVMM),width=4656,height=3496,framerate=9/1' \
  ! nvjpegenc ! multifilesink location="$STREAM/frame-%05d.jpg" \
  > /tmp/snap_cap.log 2>&1 < /dev/null & disown
for i in $(seq 1 25); do
  [ "$(ls "$STREAM"/frame-*.jpg 2>/dev/null | wc -l)" -ge 14 ] && break; sleep 1
done
if [ "$(ls "$STREAM"/frame-*.jpg 2>/dev/null | wc -l)" -lt 3 ]; then
  echo "*** 16MP stream produced nothing:"; tail -4 /tmp/snap_cap.log; exit 1
fi
python3 -c "
import sys, time
sys.path.insert(0, '/home/paul/arducam_focus')
from focuser import Focuser
f = Focuser(); f.init(); f.set_position($DAC); time.sleep(1.0)
print(f'    lens re-applied: DAC {f.get_position()}')
"
BEFORE=$(ls "$STREAM"/frame-*.jpg | wc -l)
while [ "$(ls "$STREAM"/frame-*.jpg | wc -l)" -lt $((BEFORE + 5)) ]; do sleep 0.5; done

mkdir -p "$(dirname "$OUT")"
cp "$(ls "$STREAM"/frame-*.jpg | tail -2 | head -1)" "$OUT"
echo
echo "SAVED $OUT  ($(du -h "$OUT" | cut -f1), focus DAC $DAC)"
