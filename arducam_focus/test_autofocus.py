"""End-to-end one-shot autofocus test.

Requires a gst-launch nvarguscamerasrc pipeline already streaming JPEGs to
/tmp/stream/frame-NNNNN.jpg (e.g. via tmux session 'claude').

Usage on the Jetson:
    python3 -m arducam_focus.test_autofocus
or:
    python3 ~/arducam_focus/test_autofocus.py
"""
import glob
import os
import shutil
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from focuser import Focuser, tenengrad

STREAM_DIR = "/tmp/stream"
OUT_DIR = "/tmp/focus_test_v5"


def latest_frame():
    """Return the second-to-last JPEG to avoid catching half-written files."""
    frames = sorted(glob.glob(os.path.join(STREAM_DIR, "frame-*.jpg")))
    if len(frames) < 3:
        raise RuntimeError(f"need at least 3 frames in {STREAM_DIR}, got {len(frames)}")
    img = cv2.imread(frames[-3])
    if img is None:
        raise RuntimeError(f"cv2 failed to decode {frames[-3]}")
    return img


def snapshot(name):
    frames = sorted(glob.glob(os.path.join(STREAM_DIR, "frame-*.jpg")))
    src = frames[-3]
    dst = os.path.join(OUT_DIR, name)
    shutil.copyfile(src, dst)
    print(f"  saved {name}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(OUT_DIR, "*.jpg")):
        os.remove(f)

    foc = Focuser(verbose=True)
    foc.init()

    # capture a "before" reference at the cold-start position (DAC=0)
    foc.set_position(0)
    time.sleep(0.5)
    print(f"[before] dac=0  score={tenengrad(latest_frame()):.2f}")
    snapshot("before_dac0000.jpg")

    log = []
    best = foc.autofocus(latest_frame, log=log)

    time.sleep(0.5)
    print(f"[after] dac={best}  score={tenengrad(latest_frame()):.2f}")
    snapshot(f"after_dac{best:04d}.jpg")

    with open(os.path.join(OUT_DIR, "search_log.csv"), "w") as f:
        f.write("dac,score\n")
        for dac, score in log:
            f.write(f"{dac},{score:.2f}\n")
    print(f"[log] {len(log)} samples written to search_log.csv")
    print(f"[final] lens parked at DAC={best}")


if __name__ == "__main__":
    main()
