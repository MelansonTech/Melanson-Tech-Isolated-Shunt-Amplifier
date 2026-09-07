# Isolated Shunt Amplifier — Negative-Current (Reversed-J2) DC Transfer

**DUT:** Melanson Tech Isolated Shunt Amplifier (Si8921 isolated amp + 10 mΩ Kelvin shunt)
**Test:** DC transfer / gain, both ranges, **negative current direction** (J2 reversed)
**Date:** 2026-09-06
**Operator:** Shawn (MelansonTech)
**Bench:** ScopeSweep
**Companion to:** `shunt-amp-dc-transfer-report-2026-09-06.md`, `shunt-amp-rerun-2meter-2026-09-06.md`, `shunt-amp-results-register.csv`

---

## 1. Purpose

Complete the DC transfer function in the direction the prior work left open. Every gain/offset/INL/clamp/Z figure recorded before this run was **positive-current only**; the reports flagged the reversed-shunt sweep as the top pending item. This run reverses the current through the shunt (J2 leads swapped) and re-sweeps both ranges to confirm the board measures reverse current as faithfully as forward.

## 2. Provenance — where each number came from

| Quantity | Instrument | On ScopeSweep? |
|---|---|---|
| **Loop current I_true** (the reference) | **Fluke 45** (Multimeter panel), DC current, in series in the loop, 10 A jack | Yes — bench-measured, read directly |
| **Output voltage Vout** (measured value) | **Fluke 289**, DC volts on the SMA (centre→shell) | No — read manually and relayed by the operator |
| Current setter (actuator only) | MTECH electronic load, CC, HIGH shunt | Yes |
| Loop compliance source | FNIRSI IPS3608, 10 V CV | Yes |
| DUT isolated aux | External isolated 15 V on J4 | No |

Two isolated meters, per the method finding in `shunt-amp-rerun-2meter-2026-09-06.md`: V and I must be on independent COMs, or the meter's own shunt burden corrupts Vout (~22 mV/A) on this isolated DUT. Fluke 45 = current in the loop, Fluke 289 = Vout on the output. Gain = Vout / I_true.

## 3. ×100 range — nominal 1.000 V/A, negative direction

| I_true (Fluke 45, A) | Vout (Fluke 289, V) | V/A | Dev vs 1.000 |
|---|---|---|---|
| 0.4840 | −0.4837 | −0.9994 | −0.06% |
| 0.9719 | −0.9714 | −0.9995 | −0.05% |
| 1.9536 | −1.9520 | −0.9992 | −0.08% |
| 2.9357 | −2.9356 | −1.0000 | 0.00% |
| 3.9191 | −3.9163 | −0.9993 | −0.07% |
| 4.8979 | −4.9029 | −1.0010 | +0.10% |

**Fit (6 pts, magnitude):** slope **1.0007 V/A (+0.07%)**, zero intercept **+1.8 mV** (≈1.8 mA input-referred, positive output offset — same sign/size as the +1.1 mV measured on the positive run, so it is a true output offset, not a direction-dependent term). Max residual **~3.7 mV ≈ 0.07% FS** (upper bound, Fluke-289-read-resolution-limited). Every point inside the ±0.9% spec and inside the ±0.15% user-cal grade. **PASS.**

## 4. ×10 range — nominal 0.100 V/A, negative direction

| I_true (Fluke 45, A) | Vout (Fluke 289, mV) | V/A | Dev vs 0.100 |
|---|---|---|---|
| 0.4841 | −48.18 | −0.09952 | −0.48% |
| 0.9734 | −96.93 | −0.09958 | −0.42% |
| 1.9510 | −194.70 | −0.09980 | −0.20% |
| 3.9176 | −390.26 | −0.09962 | −0.38% |
| 5.8797 | −586.50 | −0.09975 | −0.25% |
| 7.8313 | −782.20 | −0.09988 | −0.12% |

**Fit (6 pts, magnitude):** slope **0.09986 V/A (−0.14%)**, zero intercept ~+0.4 mV (few mA input-referred, small). Max residual **~0.6 mV ≈ 0.06% FS**. Every point inside the ±1.0% spec and inside the ±0.25% user-cal grade. 10 A full-scale not reached (FNIRSI caps 8.2 A; top point 8 A, as on the positive run). **PASS.**

## 5. Bidirectional summary

| Range | Positive slope | Negative slope | Directional asymmetry |
|---|---|---|---|
| ×100 | 0.9995 V/A | 1.0007 V/A | +0.12% |
| ×10 | 0.09976 V/A | 0.09986 V/A | +0.10% |

**Bidirectional operation confirmed.** The two directions agree to **~0.1%** on both ranges — inside the point-to-point scatter of either sweep and far inside the ±0.9%/±1.0% spec. The board reads reverse current as accurately as forward.

**Honest nuance:** on *both* ranges the negative direction reads ~0.1% higher magnitude than the positive. The consistency across ranges hints at a small real directional term, but it sits at this bench's measurement floor (~0.1% point scatter, ~±4 mA Fluke-289 current jitter on the positive run, ~±3 mA settled current jitter here). Reported as "symmetric to within ~0.1%," not a proven asymmetry.

## 6. Deliberately NOT measured / caveats

- **×10 10 A full-scale point** — extrapolated; FNIRSI caps 8.2 A (top measured point 8 A).
- **Negative clamp / output-Z / PSRR** — not re-run in the negative direction (positive-direction values stand from the DC transfer report). Only gain/offset/INL were swept negative.
- **Vout reference is off-ScopeSweep, operator-relayed** (Fluke 289) — same provenance as the positive DC transfer report.
- **Still pending overall:** bandwidth/−3 dB (both ranges), output noise, step response — all need the AC current-injection rig (custom power amp + series-R sense). Isolation withstand and temperature coefficient remain out of scope on this bench.

## 7. Bench notes from this run

- Confirmed again: the eload's current readback runs ~20 mA high vs the Fluke 45 (e.g. 0.505 A readback vs 0.484 A true at the 0.5 A point) — the Fluke in series is the reference, the eload is the actuator.
- eload CC trim settles in ~8 s; each point was read only after the Fluke 45 statistics settled to a sub-few-mA span.
- Range change ×100→×10 done at zero loop current (load disengaged) — SW1 pos 3→2 is an adjacent slide, board stays powered.
- Thermal at the 8 A top point: eload 57 W / 40 °C, FNIRSI 79 W / 50 °C, both in CV/CC as intended, no trips. FNIRSI current limit raised 6 A→8.2 A for the ×10 range so the eload's CC still set the current with the supply in CV.
- Loop de-energized at end: eload disengaged, FNIRSI output off.
