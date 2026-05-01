# Autofocus on the ArduCam UC-873 Rev D (IMX519)

## Status

Manual focus control is working as of 2026-04-29 via direct I2C from userspace. No kernel changes, no driver swap, no apt installs.

Continuous autofocus (hill-climb sharpness search) is not yet implemented — the manual control is the building block.

## Hardware involved

- **Sensor**: Sony IMX519 (16MP), I2C bus 10, addr `0x1a`
- **VCM (autofocus actuator)**: AKM AK7375, I2C bus 10, addr `0x0c`
- **Module manufacturer**: Sunny Optical (model A16N17H-1, branded as Arducam UC-873 Rev D)

## Critical facts

- The **VCM only enumerates on the I2C bus while the sensor is streaming** (`nvarguscamerasrc` running). Kill the stream and `0x0c` disappears.
- Argus does not override our I2C writes — readback after 1s confirms our values stay put.
- `paul` is in the `i2c` group, so `i2cset` / `i2cget` / `i2ctransfer` work without sudo.

## The wire protocol (canonical AK7375)

Three things must be right or position writes have no effect:

### 1. Init — once per stream session

```
i2ctransfer -y 10 w2@0x0c 0x02 0x00
```

Writes `0x00` to register `0x02` → AK7375 active mode. Without this, position writes are ignored.

### 2. Position write — single 3-byte raw I2C transaction

```
i2ctransfer -y 10 w3@0x0c 0x00 <high> <low>
```

Where for a 12-bit DAC value `D` in 0..4095:
- `val16 = D << 4`
- `high = (val16 >> 8) & 0xFF`
- `low = val16 & 0xFF`

The leading `0x00` is the position register. The chip auto-increments and latches the new position when the low byte arrives. **It must be one transaction.** Two separate SMBus writes to "register 0x00" then "register 0x01" do not latch reliably — the chip's internal write strobe expects contiguous bytes.

### 3. Ramp — 64-unit steps with ~1.5 ms gaps

Single-shot writes from any current position to a far-away target cause overshoot or no-move. Walk the position in 64-unit increments with 1–2 ms between writes. Arducam's reference driver (`ArduCAM/IMX519_AK7375`) does exactly this.

### Standby — when stopping a stream gracefully

Before killing the stream, ramp the lens down to DAC=0 (no holding current = lens at mechanical rest). Holding the lens at an extreme DAC continuously is bad for the VCM coil.

## DAC range maps to physical focus

Empirically observed on UC-873 Rev D in a typical room:

- **DAC 0**: closest focus (~10–20 cm subjects sharp)
- **DAC ~300–500**: typical YOLO subject distance (~1–2 m)
- **DAC ~2000**: ~3–5 m
- **DAC 4095**: infinity

Lens spans the full range — the I2C protocol confirmed deterministic position with readback matching target exactly (target 1024 → reads 1024, target 4095 → reads 4092 due to 4-LSB rounding).

## Working code

`arducam_focus/run_focus_test_v4.py` is the proven implementation. Sweeps DAC 0–4095, captures a frame at each target, reads back to verify, logs everything. Requires a `gst-launch-1.0 nvarguscamerasrc … multifilesink location=/tmp/stream/frame-%05d.jpg` pipeline running in tmux.

## What does NOT work (don't bother retrying)

These were tried 2026-04-29 and confirmed not to work — preserving the negative results so future investigations don't reopen them:

| Approach | Why it fails |
|---|---|
| Arducam `Focuser.py` (two SMBus byte-data writes) | Two separate transactions, position doesn't latch |
| Single `i2cset` byte-data with `[reg, val]` interpreted as `[high, low]` | Wrong register, wrong layout |
| `i2ctransfer w2@0x0c <high> <low>` (no register byte) | Missing leading `0x00` register address |
| Big single-shot DAC jumps without ramping | Lens overshoots or doesn't move |

## References

- [Mainline Linux `drivers/media/i2c/ak7375.c`](https://github.com/torvalds/linux/blob/master/drivers/media/i2c/ak7375.c)
- [Arducam fork — `IMX519_AK7375/AK7375/ak7375.c`](https://github.com/ArduCAM/IMX519_AK7375/blob/main/AK7375/ak7375.c) (adds the 64-step ramp)
- [Arducam Pi-side focus example](https://github.com/ArduCAM/Jetson_IMX519_Focus_Example) (uses wrong SMBus-byte-data protocol — kept here only for posterity)
