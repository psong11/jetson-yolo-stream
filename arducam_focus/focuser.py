"""AK7375 voice-coil motor driver for the ArduCam UC-873 Rev D (IMX519).

See docs/autofocus.md for the wire-protocol derivation. The chip enumerates
on I2C bus 10 at 0x0c only while nvarguscamerasrc is actively streaming.
"""
from __future__ import annotations

import subprocess
import time
from typing import Callable, Optional

import cv2
import numpy as np


DAC_MIN = 0
DAC_MAX = 4095
RAMP_STEP = 64
RAMP_DELAY_S = 0.0015
SETTLE_S = 0.25


def tenengrad(img: np.ndarray) -> float:
    """Sobel gradient energy on center 50% — robust focus metric."""
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape
    crop = img[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
    gx = cv2.Sobel(crop, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(crop, cv2.CV_64F, 0, 1, ksize=3)
    return float(np.mean(gx * gx + gy * gy))


class Focuser:
    def __init__(self, bus: int = 10, addr: int = 0x0c, verbose: bool = False):
        self.bus = bus
        self.addr = addr
        self.verbose = verbose
        self._current = 0

    def _i2c(self, *args: str) -> bool:
        cmd = ["i2ctransfer", "-y", str(self.bus), *args]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and self.verbose:
            print(f"  i2c err: {r.stderr.strip()}")
        return r.returncode == 0

    def init(self) -> None:
        """AK7375 active-mode: register 0x02 = 0x00. Call once per stream session."""
        self._i2c(f"w2@0x{self.addr:02x}", "0x02", "0x00")
        time.sleep(0.05)
        # sync internal cursor with chip state
        self._current = self.get_position() or 0

    def _write_dac(self, dac: int) -> None:
        dac = max(DAC_MIN, min(DAC_MAX, int(dac)))
        v16 = (dac & 0xFFF) << 4
        high = (v16 >> 8) & 0xFF
        low = v16 & 0xFF
        self._i2c(f"w3@0x{self.addr:02x}", "0x00",
                  f"0x{high:02x}", f"0x{low:02x}")

    def get_position(self) -> Optional[int]:
        """Read DAC[11:0] back from registers 0x00 / 0x01."""
        h = subprocess.run(["i2cget", "-y", str(self.bus), f"0x{self.addr:02x}", "0x00"],
                           capture_output=True, text=True)
        l = subprocess.run(["i2cget", "-y", str(self.bus), f"0x{self.addr:02x}", "0x01"],
                           capture_output=True, text=True)
        if h.returncode or l.returncode:
            return None
        return ((int(h.stdout.strip(), 16) << 8) | int(l.stdout.strip(), 16)) >> 4

    def set_position(self, target: int) -> int:
        """Ramp from current DAC to target in 64-unit steps. Returns final DAC."""
        target = max(DAC_MIN, min(DAC_MAX, int(target)))
        step = RAMP_STEP if target > self._current else -RAMP_STEP
        pos = self._current
        while (step > 0 and pos < target) or (step < 0 and pos > target):
            pos += step
            if (step > 0 and pos > target) or (step < 0 and pos < target):
                pos = target
            self._write_dac(pos)
            time.sleep(RAMP_DELAY_S)
        self._write_dac(target)
        self._current = target
        return target

    def autofocus(self,
                  frame_provider: Callable[[], np.ndarray],
                  metric: Callable[[np.ndarray], float] = tenengrad,
                  coarse_step: int = 256,
                  fine_step: int = 32,
                  fine_window: int = 256,
                  log: Optional[list] = None) -> int:
        """Coarse + fine hill-climb. Returns the DAC of peak sharpness."""

        def measure(dac: int) -> float:
            self.set_position(dac)
            time.sleep(SETTLE_S)
            frame = frame_provider()
            score = metric(frame)
            if log is not None:
                log.append((dac, score))
            if self.verbose:
                print(f"  dac={dac:4d}  score={score:8.2f}")
            return score

        if self.verbose:
            print("[coarse]")
        coarse_targets = list(range(DAC_MIN, DAC_MAX + 1, coarse_step))
        if coarse_targets[-1] != DAC_MAX:
            coarse_targets.append(DAC_MAX)
        coarse = [(d, measure(d)) for d in coarse_targets]
        peak_dac, _ = max(coarse, key=lambda x: x[1])

        lo = max(DAC_MIN, peak_dac - fine_window)
        hi = min(DAC_MAX, peak_dac + fine_window)
        if self.verbose:
            print(f"[fine] window {lo}..{hi}")
        fine_targets = list(range(lo, hi + 1, fine_step))
        fine = [(d, measure(d)) for d in fine_targets]
        best_dac, best_score = max(fine, key=lambda x: x[1])

        if self.verbose:
            print(f"[done] best dac={best_dac}  score={best_score:.2f}")
        self.set_position(best_dac)
        return best_dac

    def park(self) -> None:
        """Ramp to DAC=0 (no holding current). Call before stopping the stream."""
        self.set_position(0)
