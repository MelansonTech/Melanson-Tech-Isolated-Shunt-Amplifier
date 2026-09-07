# Isolated Shunt Amplifier — ×100 Frequency Response (flatness + −3 dB), AC injection

**DUT:** Melanson Tech Isolated Shunt Amplifier (Si8921 isolated amp + 10 mΩ Kelvin shunt), **×100 range** (SW1 pos 3, 1 V/A)
**Test:** small-signal frequency response — passband flatness and −3 dB corner
**Date:** 2026-09-06
**Operator:** Shawn (MelansonTech)
**Bench:** ScopeSweep + Maelstrom power amp

---

## 1. Rig and provenance

AC current is injected through the DUT shunt and referenced to the **power amp's own current monitor (Imon)** — no separate sense resistor (the available 1 Ω is wirewound/inductive).

| Role | Instrument / element | Notes |
|---|---|---|
| Stimulus | AD2 Network Analyzer **W1** → **Maelstrom power amp** input (×10 gain) | swept sine |
| Injection loop | amp output → **DUT shunt (J2)** in series → **2 Ω load** → amp return | 2 Ω sets the current; its inductance cancels in the ratio |
| **Current reference** | **Imon**, 0.100 V/A → AD2 **Ch1** (1 MΩ) | ×10 diff-amp across a Vishay WSL3637R0100DEA 10 mΩ shunt; flat to ~200 kHz (analysis 2026-08-30) |
| **Response** | **DUT IsenseOut** → AD2 **Ch2** (1 MΩ), diff across J1 centre→shell | |
| Detector | AD2 Network Analyzer, Lock-in, Bode | log sweeps |

Reported quantity is the Ch2/Ch1 magnitude ratio; both flatness and the −3 dB corner are taken from each sweep's own low-frequency plateau, so the absolute scale (and Imon's ±0.6 % gain error) does not enter.

**Why Imon is a valid reference here:** the whole ×100 response (flat band + 60 kHz corner) sits far below every frequency-shaping term in the reference and source — Imon's shunt-inductance zero (>318 kHz), Imon's op-amp pole (8.4 MHz), and the amp's own −3 dB (2.16 MHz). The low-frequency plateau also ties Imon to the DC gain (below).

## 2. Grounding / bias sanity check (passed)

Low-frequency plateau = **19.92–19.94 dB = ×9.9**, versus the expected ×10 (DUT 1.0 V/A ÷ Imon 0.1 V/A = +20 dB); agreement ~1 %, within Imon's ±0.6 % gain tolerance plus the DUT's measured DC gain. Plateau at +20 dB with phase ≈ 0° confirms the DUT is biased correctly with the amp-driven loop — reference buffer intact, injection loop not earthing the floating 0 V.

## 3. Passband flatness (100-point sweep, 100 Hz–60 kHz, 0.2 Vpp / ~0.5 A pk)

Deviation from the DC-band plateau (19.94 dB):

| Flat within | usable to | as gain error |
|---|---|---|
| ±0.03 dB | ~5 kHz | ±0.3 % |
| ±0.05 dB | ~9 kHz | ±0.6 % |
| ±0.1 dB | ~13 kHz | ±1.2 % |
| ±0.25 dB | ~19 kHz | ±2.9 % |
| ±0.5 dB | ~25 kHz | ±5.9 % |
| ±1 dB | ~34 kHz | ±12 % |

The deep-band figure (±0.03 dB to 5 kHz) is **at the measurement floor** — lock-in run scatter plus AD2 two-channel matching (Imon at 0.1 V/A and IsenseOut at 1 V/A sit on 10:1 different AD2 ranges, ~±0.02–0.03 dB). The DUT's true in-band flatness is at least this good; a resistive-loopback calibration would tighten the bound. Above ~5 kHz the roll-off is real DUT, and Imon is flat across all of it.

## 4. −3 dB bandwidth

**×100 −3 dB = 60 kHz (±~2 kHz).** Small-signal, amplitude-independent.

| Freq | Mag (dB) | Phase |
|---|---|---|
| ≤ 5 kHz | 19.94 (flat) | ~0° |
| 20.0 kHz | 19.64 (−0.30) | −35° |
| 34 kHz | 18.95 (−1.0) | −58° |
| 49.6 kHz | 17.88 (−2.0) | −85° |
| **60 kHz** | **16.9 (−3.0)** | ~−99° |
| 120 kHz | 10.07 (−9.9) | −174° |

**Amplitude independence:** zoom sweeps on 40–80 kHz at 0.1 Vpp (0.25 A pk) and 0.2 Vpp (0.5 A pk) gave the same corner (curves differ only by a ~0.15 dB uniform level offset; corner from each own plateau agrees within ~2 kHz) → true small-signal, not slew-limited.

## 5. Character of the roll-off

- **Phase runs well ahead of magnitude:** −90° near 52 kHz, −180° near 120 kHz, where a single pole would be at −45°/−90°. This is the **Si8921's transport delay**, not extra poles — magnitude and phase decoupled by the isolator's group delay.
- **Roll-off ~30 dB/decade** past the corner (amplifier pole + the isolator's internal reconstruction filter).

## 6. Verdict vs declared

| | Declared (repo) | Measured | |
|---|---|---|---|
| ×100 −3 dB | ~30–60 kHz | **60 kHz** | **CONFIRMED** (top of the declared band, on the real board) |
| ×100 passband flatness | (not specified) | **±0.1 dB to 13 kHz, ±1 dB to 34 kHz** | **NEW measured data** |

Closes part of Design-Review Finding 8 (re-measure bandwidth on a real board) for the ×100 range, and adds a flatness spec the repo did not have.

## 7. Deliberately NOT measured / caveats

- **×10 bandwidth (~500 kHz) not measured here.** Imon is unverified above ~200 kHz (its own shunt inductance) and, sharing the same WSL3637 part as the DUT shunt, its shunt-inductance zero would partly cancel the DUT's in the ratio and inflate the apparent corner. The ×10 sweep needs a **flat, non-inductive HF current reference** (foil/metal-film); the available 1 Ω is wirewound.
- **Imon flatness across 0–60 kHz** is validated by analysis (flat to ~200 kHz) and by the flat plateau to ~5 kHz, but not independently cross-checked against a second flat reference — the assumption I am least sure of, though with wide margin.
- Output noise and step response (T7/T8) not yet run.

## 8. Bench notes

- Amp ×10 gain: W1 0.2 Vpp → 2.0 Vpp out → ~0.5 A pk into 2 Ω. Small-signal, far below either range's FS and the amp's ~6 A OCP.
- Lock-in run-to-run level scatter ~0.1–0.15 dB; within a single sweep the passband holds ±0.02–0.03 dB, so flatness and the −3 dB corner (each referenced to that sweep's own plateau) are robust to it.
