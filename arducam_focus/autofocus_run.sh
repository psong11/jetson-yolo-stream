#!/bin/bash
# autofocus_run — start a stream, run the two-pass hill-climb, park the lens, clean up.
# Wraps arducam_focus/test_autofocus.py, which needs a live /tmp/stream feed.
#
# Source of truth: arducam_focus/autofocus_run.sh in the repo. Install with:
#   scp arducam_focus/autofocus_run.sh paul@jetson:~/ && ssh paul@jetson 'chmod +x ~/autofocus_run.sh'
#
# Usage on the Jetson:  ~/autofocus_run.sh
set -uo pipefail

STREAM=/tmp/stream

cleanup() {
  echo "=== parking lens + stopping stream ==="
  python3 -c "
import sys
sys.path.insert(0, '/home/paul/arducam_focus')
from focuser import Focuser
f = Focuser()
f.init()
f.park()
print('  lens parked at DAC 0')
" 2>/dev/null || echo "  (park skipped)"
  pkill -f nvarguscamerasrc 2>/dev/null
  sleep 1
  rm -rf "$STREAM"
  echo "  stream dir removed"
}
trap cleanup EXIT

echo "=== clearing any stale pipeline ==="
pkill -f nvarguscamerasrc 2>/dev/null && sleep 2 || true
rm -rf "$STREAM"; mkdir -p "$STREAM"

echo "=== starting stream ==="
nohup gst-launch-1.0 nvarguscamerasrc \
  ! 'video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1' \
  ! nvjpegenc ! multifilesink location="$STREAM/frame-%05d.jpg" \
  > /tmp/af_gst.log 2>&1 < /dev/null & disown

for i in $(seq 1 20); do
  n=$(ls "$STREAM"/frame-*.jpg 2>/dev/null | wc -l)
  [ "$n" -ge 10 ] && break
  sleep 1
done
n=$(ls "$STREAM"/frame-*.jpg 2>/dev/null | wc -l)
if [ "$n" -lt 10 ]; then
  echo "*** stream never produced frames — tail of /tmp/af_gst.log:"
  tail -8 /tmp/af_gst.log | sed 's/^/    /'
  exit 1
fi
echo "  streaming ($n frames buffered)"

echo "=== VCM presence on bus 10 (should show 0c while streaming) ==="
vcm=$(sudo -n i2cdetect -y -r 10 2>/dev/null | sed -n '2p')
echo "  $vcm"

echo "=== two-pass hill-climb ==="
python3 /home/paul/arducam_focus/test_autofocus.py

echo "=== results in /tmp/focus_test_v5 ==="
ls -lh /tmp/focus_test_v5/ 2>/dev/null | tail -5
