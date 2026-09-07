# Isolated Shunt Amplifier — Product Brief

**Measure current in a circuit that isn't at your ground potential, and get a signal
your scope can read safely.**

An open-hardware isolated current-sense amplifier built around the Skyworks **Si8921**
isolated amplifier and a **10 mΩ Vishay four-terminal Kelvin shunt**. High-side rails,
motor phases, floating battery strings, off-line converters — anywhere the current you
care about sits hundreds of volts away from your instrument's ground.

Every performance number below was **measured on hardware**, not calculated. The raw
data is in this repository.

---

## Why this one

**It hits calibrated accuracy without being calibrated.**

The datasheet promises ±0.9 % on the 5 A range and ±1.0 % on the 10 A range, with
±0.15 % / ±0.25 % available if you calibrate a scale factor into your own system. On the
bench, a production board measured **−0.05 %** and **−0.24 %** with nothing calibrated
at all — inside the *user-calibrated* grade, straight out of the box, and it held across
two independent fixtures and both current directions.

**It works just as well backwards.** Forward and reverse agree to **~0.1 % on both
ranges** — inside the scatter of either sweep. Regenerative braking, bidirectional DC-DC,
battery charge/discharge: one board, one calibration, both directions.

**Its zero stays put.** From cold the offset settles in about 8 minutes and then holds a
**0.6 mV band across a 2 h 23 min soak**, never straying more than 0.5 mV from zero —
under 0.5 mA input-referred against an 8 mA allowance. The board tested didn't need its
offset trim adjusted at all.

**It's genuinely open.** Schematic, layout, BOM, tolerance budget, design review, test
plan, and every raw bench reading — all in this repository. Including the tests that
haven't been run.

---

## Measured performance

Rev 3.1 board, 2026-09-05/06. Full method and per-point data in
[`TEST_REPORT.md`](TEST_REPORT.md).

| | 5 A range (×100) | 10 A range (×10) |
|---|---|---|
| **Sensitivity** | 1 V per A | 1 V per 10 A |
| **DC gain error, uncalibrated** | **−0.05 %** | **−0.24 %** |
| **Zero offset, input-referred** | ~2 mA | ~1.4 mA |
| **Linearity (INL)** | ≤0.09 % FS * | ≤0.09 % FS * |
| **Reverse-direction agreement** | 0.12 % | 0.10 % |
| **Bandwidth (−3 dB)** | **60 kHz** | **≈580 kHz** |
| **Flat to ±0.1 dB** | 13 kHz | 55 kHz |
| **Flat to ±1 dB** | 34 kHz | 470 kHz |
| **Rise time (10–90 %)** | ~6 µs | ~0.6 µs |
| **Transport delay** | ~2.4 µs | ~1.1 µs |
| **Output noise, input-referred** | ~2 mA rms, no dominant spur | 12 mA rms at 108 kHz † |
| **Output impedance** | 50–51 Ω | 50–51 Ω |
| **Supply sensitivity** | ±0.12 % over 13.0–15.5 V | — |

\* Reference-limited — this is the resolution of the meters used, not a floor the board
was found at.
† A switching spur inside the ×10 passband. A 100 kHz output low-pass removes it. See
[`TEST_REPORT.md` §7](TEST_REPORT.md).

**Both ranges are free of slew limiting** — large-signal bandwidth equals small-signal
bandwidth, so a full-scale step is no slower than a small one. The 10 A range's 580 kHz
corner **exceeds** the ~500 kHz the datasheet claims.

---

## Specified from the device datasheets, not yet bench-verified

Stated plainly because a specification nobody has measured should be labelled as one.
These come from the Si8921 and PSU1 datasheets and the connector ratings, and this
bench had no way to test them:

| | Value | Why untested |
|---|---|---|
| Isolation withstand | 4.2 kV | no hipot tester |
| Common-mode range | 400 Vdc | highest available supply is 36 V |
| Temperature coefficient | ±(0.011 % + 0.5 mA)/°C | no thermal chamber |

The 10 A range's top point was measured at **8 A** — the forcing supply's limit — and
10 A full scale is extrapolated from a seven-point fit.

If you need the isolation or common-mode figures qualified for your application, treat
them as manufacturer ratings to verify, not as results.

---

## At a glance

- **Ranges:** 10 A (×10, 1 V/10 A) and 5 A (×100, 1 V/A), front-panel switched
- **Sense element:** 10 mΩ, 3 W, ±0.5 %, ±50 ppm/°C Vishay WSL3637, four-terminal Kelvin
- **Output:** SMA female, 50 Ω source — **use a 1 MΩ input**, a 50 Ω terminated
  instrument reads half
- **Input:** 2-pos 5.08 mm terminal block, 12 A / 400 V
- **Supply:** 13–15 V isolated, ~95 mA (~1.4 W) — measured on the ×100 range, the higher of the two. 2.1 × 5.5 mm barrel, centre positive
- **Operating range:** 0–40 °C, accuracy specified at 23 °C ±5 °C
- **Licence:** open hardware — see [`../LICENSE`](../LICENSE)

> ### ⚠ The supply must be genuinely floating
>
> `ISenseRTN` is bonded to chassis and the board's internal 0 V rail floats ~6 V below
> it. A supply that bonds its negative output to earth shorts the reference buffer: the
> measurement collapses and the part overheats, with nothing visible from outside.
>
> **Fine:** a two-pin double-insulated adapter, or a bench PSU with truly floating
> outputs. **Not fine:** USB- or PoE-derived power, a PSU with its negative terminal
> strapped to earth, or one supply shared between two boards.

---

## Where it fits

**Good for:** high-side current in motor drives and converters; battery pack current in
either direction; floating-node current where a differential probe would be
inconvenient or unsafe; bench and lab work where you want a documented, auditable
measurement path rather than a sealed instrument.

**Look elsewhere if:** you need DC-to-MHz on the high range (580 kHz is the ceiling); you
need the isolation rating formally qualified; or you need better than ~0.5 % accuracy
over a wide temperature range without calibrating.

---

## Short-form copy

*For README headers, listings, and posts. Every claim traces to* [`TEST_REPORT.md`](TEST_REPORT.md).

**One line**
> Open-hardware isolated current-sense amplifier — 10 A and 5 A ranges, bidirectional,
> 580 kHz, and measured at better than 0.25 % uncalibrated.

**One paragraph**
> The MelansonTech Isolated Shunt Amplifier measures current in circuits sitting at up
> to 400 V of common mode and hands you a ground-referenced signal your scope or DAQ can
> read safely. Built on the Skyworks Si8921 and a 10 mΩ Kelvin shunt, it offers
> switch-selected 10 A and 5 A ranges, works equally well in both current directions,
> and reaches 580 kHz on the high range. Bench measurement of a production board found
> DC gain errors of −0.24 % and −0.05 % with no calibration applied — inside the
> accuracy grade the datasheet reserves for calibrated systems. Schematic, BOM, design
> review and every raw bench reading are published.

**Three bullets**
> - **Accurate before you calibrate it** — −0.05 % and −0.24 % measured on a production
>   board, inside the calibrated-grade spec with nothing trimmed
> - **Bidirectional to 0.1 %** — forward and reverse agree within the scatter of either
>   measurement, on both ranges
> - **Open, and honestly documented** — every reading published, including the three
>   specifications the bench could not test
