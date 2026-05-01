#!/usr/bin/env python3
"""Phase B v4: canonical AK7375 protocol.

- Position write: SINGLE 3-byte i2c transaction [0x00, high, low] via i2ctransfer.
- Init: register 0x02 = 0x00 (active mode).
- Ramp moves in 64-unit DAC steps with 1ms delays between writes.
- Readback after each target to confirm chip state.
- Captures one frame per target from /tmp/stream rolling buffer.
"""
import os, sys, time, glob, shutil, subprocess

STREAM_DIR = '/tmp/stream'
OUT_DIR = '/tmp/focus_test_v4'
LOG_PATH = os.path.join(OUT_DIR, 'log.txt')
BUS = 10
ADDR = 0x0c
STEP = 64
STEP_DELAY_S = 0.0015        # 1.5ms between ramp steps (datasheet calls for ~1ms)
SETTLE_S = 0.7               # post-arrival wait for AE + lens settle
TARGETS = [0, 1024, 2048, 3072, 4095]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def i2c_w3(reg, b1, b2):
    return run(['i2ctransfer', '-y', str(BUS), f'w3@0x{ADDR:02x}',
                f'0x{reg:02x}', f'0x{b1:02x}', f'0x{b2:02x}'])


def i2c_w2(reg, val):
    return run(['i2ctransfer', '-y', str(BUS), f'w2@0x{ADDR:02x}',
                f'0x{reg:02x}', f'0x{val:02x}'])


def i2c_read(reg):
    r = run(['i2cget', '-y', str(BUS), f'0x{ADDR:02x}', f'0x{reg:02x}'])
    if r.returncode != 0:
        return None
    return int(r.stdout.strip(), 16)


def write_position(dac):
    """Single canonical AK7375 write: [0x00, high, low]."""
    val16 = (dac & 0xFFF) << 4
    high = (val16 >> 8) & 0xFF
    low = val16 & 0xFF
    return i2c_w3(0x00, high, low)


def ramp_to(current, target, log):
    """Walk position in STEP-sized increments toward target."""
    step = STEP if target > current else -STEP
    pos = current
    while (step > 0 and pos < target) or (step < 0 and pos > target):
        pos += step
        if (step > 0 and pos > target) or (step < 0 and pos < target):
            pos = target
        write_position(pos)
        time.sleep(STEP_DELAY_S)
    # Final settle write at exact target (no-op if already exact, harmless)
    write_position(target)
    log.write(f"  ramped to {target}\n")
    return target


def read_position():
    h = i2c_read(0x00)
    l = i2c_read(0x01)
    if h is None or l is None:
        return None
    val16 = (h << 8) | l
    dac = (val16 >> 4) & 0xFFF
    return dac, h, l


def grab_latest_as(name, log):
    frames = sorted(glob.glob(os.path.join(STREAM_DIR, 'frame-*.jpg')))
    if len(frames) < 3:
        log.write(f"  ERROR: only {len(frames)} frames available\n")
        return None
    src = frames[-3]
    dst = os.path.join(OUT_DIR, name)
    shutil.copyfile(src, dst)
    sz = os.path.getsize(dst)
    log.write(f"  saved {name} from {os.path.basename(src)} ({sz} bytes)\n")
    return dst


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(OUT_DIR, '*.jpg')):
        os.remove(f)

    with open(LOG_PATH, 'w') as log:
        log.write("=== AK7375 canonical protocol test ===\n")

        log.write("\n[init] register 0x02 := 0x00 (active mode)\n")
        r = i2c_w2(0x02, 0x00)
        log.write(f"  rc={r.returncode}\n")
        time.sleep(0.1)

        log.write("\n[probe] readback before any position write\n")
        rp = read_position()
        if rp:
            dac, h, l = rp
            log.write(f"  current dac=0x{dac:03x}={dac}  reg00=0x{h:02x}  reg01=0x{l:02x}\n")
            current = dac
        else:
            log.write("  readback failed; assuming pos=0\n")
            current = 0

        log.write("\n[home] ramp to 0\n")
        current = ramp_to(current, 0, log)
        time.sleep(SETTLE_S)
        rp = read_position()
        log.write(f"  readback after home: dac=0x{rp[0]:03x}={rp[0]} (reg00=0x{rp[1]:02x} reg01=0x{rp[2]:02x})\n" if rp else "  readback failed\n")
        grab_latest_as('pos_0000_home.jpg', log)

        for target in TARGETS:
            log.write(f"\n[sweep] target dac={target}\n")
            current = ramp_to(current, target, log)
            time.sleep(SETTLE_S)
            rp = read_position()
            if rp:
                dac, h, l = rp
                log.write(f"  readback: dac=0x{dac:03x}={dac} (reg00=0x{h:02x} reg01=0x{l:02x})\n")
            grab_latest_as(f'pos_{target:04d}.jpg', log)

        log.write("\n[done]\n")

    print(open(LOG_PATH).read())


if __name__ == '__main__':
    main()
