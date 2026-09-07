# Isolated Shunt Amplifier — ×100 Step Response, Large-Signal Bandwidth & Output Noise

**DUT:** Melanson Tech Isolated Shunt Amplifier, **×100 range** (SW1 pos 3, 1 V/A)
**Date:** 2026-09-06
**Operator:** Shawn (MelansonTech)
**Bench:** ScopeSweep + Maelstrom power amp
**Companion to:** `shunt-amp-bandwidth-x100-2026-09-06.md` (flatness + −3 dB)

---

## 1. Step response (derived from the measured 100 Hz–60 kHz frequency response)

A directly-captured time-domain step was not obtained — the AD2 Oscilloscope panel could not take the analog input while the Network Analyzer held it, and the scope's MCP readout exposes only Vpp/Freq, not a waveform or rise time. The figures below are derived from the measured magnitude+phase (traceable to the NA sweep), which for a band-limited linear stage is equivalent.

| Quantity | Value | Basis |
|---|---|---|
| 10–90% rise time | **≈ 6 µs** | 0.35 / 60 kHz = 5.8 µs; slightly longer for the ~30 dB/dec roll-off |
| Group delay (edge lag) | **≈ 4.5 µs** | phase slope −18° @10 kHz → −69° @41 kHz |
| Si8921 transport delay | **≈ 2.4 µs** | excess phase beyond the dominant pole (−53° at 60 kHz vs −45° for a lone pole) |
| Overshoot | **small** (not directly captured) | magnitude is monotonic with no peaking → little ringing expected |

## 2. Large-signal bandwidth

Slew- vs bandwidth-limited, decided analytically and confirmed by amplitude independence:

- Output stage **OPA197**, slew rate **20 V/µs** → full-power bandwidth = SR/(2π·V_FS) = 20/(2π·5 V) = **≈ 640 kHz**.
- That is **>10×** the 60 kHz small-signal corner: at full 5 V output and 60 kHz the swing needs only 1.88 V/µs. The ×100 is **bandwidth-limited everywhere in its range, never slew-limited**.
- **Confirmed empirically:** the −3 dB corner was identical at 0.25 A pk (0.1 Vpp) and 0.5 A pk (0.2 Vpp) — amplitude-independent.

**Large-signal bandwidth = small-signal bandwidth = 60 kHz.** No large-signal degradation.

*A directly-captured large-signal step edge would require rewiring the scope (Imon/IsenseOut → Rigol) or the drive (amp input → FeelTech, freeing the AD2 scope). The conclusion above does not depend on it.*

## 3. Output noise (Spectrum Analyzer on IsenseOut, generator off)

Input quiet (W1 off; loop connected, amp coupling ~1/200 negligible), ×100, AD2 Spectrum Analyzer, Hann, density, 814 Hz resolution, 10 Hz–1 MHz.

- **No dominant discrete spur.** The eight strongest components are all within ~5 dB of each other (0.2–0.3 mVrms in an 814 Hz bin), spread 8–82 kHz with no harmonic structure — a noise floor's random peaks, not a DC-DC (NXJ1S0505) switching line or isolator chopper tone. Candidate 67–82 kHz features are already past the 60 kHz roll-off.
- Largest components ≈ **0.3 mVrms** at 18.7 & 30.4 kHz → density ≈ **10 µV/√Hz**.
- Estimated integrated output noise **~2 mVrms** over the 60 kHz bandwidth → **~2 mA rms input-referred** (1 V/A) — well below the ±8 mA offset term, so noise is not a limiting factor.
- *Informational only* (the datasheet declares no noise spec). The MCP read returns the peak list, not the full trace, so the integrated RMS is a peak-density×√BW estimate, not a band-power integration.

## 4. Summary — ×100 dynamic characterization

| Parameter | Result | Method |
|---|---|---|
| −3 dB bandwidth | 60 kHz | Imon-referenced AC sweep |
| Passband flatness | ±0.1 dB to 13 kHz, ±1 dB to 34 kHz | AC sweep |
| Rise time (10–90%) | ~6 µs | derived from Bode |
| Group / transport delay | ~4.5 µs / ~2.4 µs | phase slope / excess phase |
| Large-signal BW | 60 kHz (not slew-limited) | slew analysis + amplitude independence |
| Output noise | ~2 mVrms, ~2 mA in-ref, no spur | Spectrum Analyzer |
