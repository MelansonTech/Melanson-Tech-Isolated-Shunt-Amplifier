# Isolated Shunt Amplifier — ×10 Dynamic Characterization (Bandwidth, Step, Noise)

**DUT:** Melanson Tech Isolated Shunt Amplifier, **×10 range** (SW1 pos 2, 0.1 V/A, 10 A FS)
**Date:** 2026-09-06
**Operator:** Shawn (MelansonTech)
**Bench:** ScopeSweep + Maelstrom power amp
**Companion to:** `shunt-amp-bandwidth-x100-2026-09-06.md`, `shunt-amp-transient-noise-x100-2026-09-06.md`

---

## 1. Rig and reference caveat

Same rig as ×100: AD2 NA **W1 → power amp (×10) → DUT shunt (J2) in series → 2 Ω load**; current reference = **Imon** (0.1 V/A) on AD2 Ch1; response = **IsenseOut** on AD2 Ch2; both 1 MΩ.

On ×10 the DUT (0.1 V/A) and Imon (0.1 V/A) are equal, so the plateau is ~0 dB with matched channel amplitudes. **Reference caveat:** at the ~500 kHz corner, both Imon and the DUT sense through WSL3637 shunts whose inductance zero lies at 318 kHz (5 nH) to 3.2 MHz (0.5 nH); the zeros cancel in the ratio if the two parts match. **The measured response is monotonic with no peaking**, which is the evidence that the shunts are well-behaved and the cancellation is clean — so the corner below is the real one, with only a small shunt-matching uncertainty. A flat non-inductive reference would remove even that.

Amplitude 0.4 Vpp → ~1 A pk (10% of ×10 FS, small-signal).

## 2. Bandwidth

Plateau −0.08 dB (= DC gain, ×10/Imon ≈ 1). Roll-off:

| Freq | Mag (dB) | Phase |
|---|---|---|
| ≤ 350 kHz | −0.3 (gentle shelf) | — |
| 520 kHz | −1.84 | +150° |
| 573 kHz | −2.82 | +128° |
| **~583 kHz** | **−3.0** | ~+120° |
| 630 kHz | −4.20 | +104° |
| 1.0 MHz | −14.6 | — |
| 2.0 MHz | −40.2 | — |

**×10 −3 dB bandwidth ≈ 580 kHz — above the declared ~500 kHz.**

- **Roll-off ~70 dB/decade** past the corner (−3 dB at 583 kHz to −40 dB at 2 MHz over 0.53 decade) — far steeper than a simple pole: the **Si8921 output reconstruction filter**.
- **Transport delay ≈ 1.1 µs** (phase −43° at 112 kHz; about half the ×100's 2.4 µs — one fewer gain stage).
- Monotonic magnitude, no peaking.

## 3. Passband flatness (from the same sweep)

Deviation from the −0.08 dB plateau:

| Flat within | usable to |
|---|---|
| ±0.1 dB | ~55 kHz |
| ±0.35 dB | ~390 kHz (wide gentle shelf) |
| ±0.5 dB | ~410 kHz |
| ±1 dB | ~470 kHz |

Much wider flat region than ×100, as expected (10× less gain).

## 4. Step response & large-signal bandwidth (derived)

| Quantity | Value | Basis |
|---|---|---|
| 10–90% rise time | **≈ 0.6 µs** | 0.35 / 580 kHz |
| Transport delay | **≈ 1.1 µs** | phase slope |
| Overshoot | small | monotonic magnitude |
| Large-signal BW | **= 580 kHz** | ×10 FS out is only 1 V; 580 kHz needs 3.6 V/µs vs OPA197 20 V/µs; corner set by isolator filter, not slew |

(Direct time-domain capture not taken — AD2 Oscilloscope panel blocked by NA device ownership; derived from measured mag+phase.)

## 5. Output noise — switching-spur family (Spectrum Analyzer, generator off)

Unlike ×100 (broadband, no dominant spur), ×10 shows a clear **switching/clock spur family**:

| Freq | Level (Vrms) | Note |
|---|---|---|
| 54.2 kHz | 0.6 m | fundamental |
| **108.3 kHz** | **1.2 m** | **strongest → ~12 mA rms input-referred** |
| 162.5 kHz | 0.8 m | harmonic |
| 217 / 326 / 540 kHz | 0.1–0.2 m | 2nd / 3rd / 5th harmonics of 108 kHz |

- **Strongest spur ~1.2 mVrms at 108 kHz = ~12 mA rms input-referred** (÷0.1 V/A).
- **Likely source:** the DUT's isolated DC-DC (NXJ1S0505) or the Si8921 modulator clock, coupling on the output side.
- **Why ×100 looked clean:** these spurs (54–540 kHz) fall inside the ×10 passband (580 kHz) but are **filtered by the ×100 range's 60 kHz roll-off**. Being an output-side coupling (same absolute mV on either range), the narrow ×100 bandwidth rejects it.
- *Caveats:* measured with the injection loop connected (not J2-open); the harmonic structure points to the DUT, but a J2-open capture would confirm attribution. Informational only (no declared noise spec). RBW 2.03 kHz; MCP read returns peaks, not the full trace.

## 6. Summary — ×10 dynamic

| Parameter | Result | vs declared |
|---|---|---|
| −3 dB bandwidth | **580 kHz** | above ~500 kHz declared |
| Passband flatness | ±0.1 dB to 55 kHz; ±1 dB to 470 kHz | (new) |
| Rise time / delay | ~0.6 µs / ~1.1 µs | (new) |
| Large-signal BW | 580 kHz (not slew-limited) | (new) |
| Output noise | 108 kHz switching spur ~1.2 mVrms / ~12 mA in-ref + harmonics; passed by ×10 BW, filtered by ×100 | (new finding) |

Closes Design-Review Finding 8's ×10 bandwidth re-measurement (Imon-referenced; a flat HF reference would remove the residual shunt-matching uncertainty).
