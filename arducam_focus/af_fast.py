"""Fast autofocus — golden-section search instead of an exhaustive sweep.

Why not binary search on one photo: a defocused frame can't tell you WHICH WAY
to move (blur is symmetric near/far). True one-shot AF needs phase-detect pixel
data, which our driver doesn't expose. Second best: the sharpness-vs-DAC curve
is unimodal, so golden-section search finds its peak in ~13 measurements
(~5 s) instead of a 33-step grid (~minutes).

Needs a live 1080p stream writing to /tmp/stream (snap.sh orchestrates this).
Prints "BEST <dac>" on the last line for callers to parse.
"""
import glob
import os
import sys
import time

import cv2

sys.path.insert(0, "/home/paul/arducam_focus")
from focuser import Focuser, tenengrad

STREAM = "/tmp/stream"
SETTLE_S = 0.3
PHI = 0.6180339887


def latest_frame():
    fs = sorted(glob.glob(os.path.join(STREAM, "frame-*.jpg")))
    if len(fs) < 3:
        raise RuntimeError(f"need frames in {STREAM} — is the stream running?")
    img = cv2.imread(fs[-3])
    if img is None:
        raise RuntimeError("failed to decode frame")
    return img


def center_roi(img):
    h, w = img.shape[:2]
    return img[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]


def main():
    t0 = time.time()
    foc = Focuser()
    foc.init()
    cache = {}

    def measure(dac):
        dac = int(dac)
        if dac in cache:
            return cache[dac]
        foc.set_position(dac)
        time.sleep(SETTLE_S)
        score = tenengrad(center_roi(latest_frame()))
        cache[dac] = score
        print(f"  dac={dac:4d}  score={score:9.1f}")
        return score

    a, b = 0, 4095
    c = int(b - PHI * (b - a))
    d = int(a + PHI * (b - a))
    fc, fd = measure(c), measure(d)
    while b - a > 24:
        if fc < fd:
            a, c, fc = c, d, fd
            d = int(a + PHI * (b - a))
            fd = measure(d)
        else:
            b, d, fd = d, c, fc
            c = int(b - PHI * (b - a))
            fc = measure(c)

    best = c if fc >= fd else d
    foc.set_position(best)
    print(f"[done] {len(cache)} measurements in {time.time() - t0:.1f}s")
    print(f"BEST {best}")


if __name__ == "__main__":
    main()
