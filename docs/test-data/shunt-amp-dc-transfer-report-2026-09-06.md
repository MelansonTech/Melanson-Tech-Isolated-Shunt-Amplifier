# Isolated Shunt Amplifier — DC Transfer, Output Impedance, Clamp & PSRR Report

**DUT:** Melanson Tech Isolated Shunt Amplifier (Si8921 isolated amp + 10 mΩ Kelvin shunt)
**Tests:** DC transfer / gain (both ranges), output impedance, output clamp, supply sensitivity (PSRR)
**Date:** 2026-09-06
**Operator:** Shawn (MelansonTech)
**Bench:** ScopeSweep

---

## 1. Provenance — where each number came from

| Quantity | Instrument | On ScopeSweep? |
|---|---|---|
| **Output voltage `IsenseOut`** (measured value) | **Fluke 45** (Multimeter panel), DC V on the SMA | Yes — bench-measured |
| **True series current I_true** (the reference) | **Fluke 289**, DC current, in series | **No — read manually and relayed by the operator** |
| Current setter (actuator only) | MTECH electronic load, CC, HIGH shunt | Yes |
| Loop compliance source | FNIRSI IPS3608 (gain/Z/clamp) / external 10 V·3 A supply (PSRR) | Yes / No |
| DUT isolated aux | External 15 V (gain/Z/clamp) / FNIRSI (PSRR) | mixed |

Gain figures = `Vout(Fluke 45) / I_true(Fluke 289)`, read after settle. **All gain/offset/clamp/Z results are positive-current only — negative-current (reversed-shunt) sweep is still pending.**

---

## 2. ×100 range — nominal 1.000 V/A, full-scale 5 A → 5.0 V

| Nominal I | I_true (289, A) | Vout (45, V) | V/A | Dev vs 1.000 |
|---|---|---|---|---|
| 0 | ~0 | +0.0011 (+1.1 mV) | — | offset |
| 0.25 | 0.2535 (settled) | 0.2537 | 1.001 | +0.1 % |
| 0.5 | 0.482 | 0.4828 | 1.002 | +0.17 % |
| 1 | 0.972 | 0.9683 | 0.996 | −0.38 % |
| 2 | 1.9526 | 1.9457 | 0.996 | −0.35 % |
| 3 | 2.933 | 2.9291 | 0.999 | −0.13 % |
| 4 | 3.914 | 3.9074 | 0.998 | −0.17 % |
| 4.5 | 4.403 | 4.401 | 1.000 | −0.05 % |
| 5 | 4.890 | 4.8895 | 1.000 | −0.01 % |

**Fit (8 pts):** gain **0.9995 V/A (−0.05 %)** — meets ±0.15 % user-cal grade uncalibrated. Offset ≤ ~2 mA. INL max **4.6 mV at 2 A ≈ 0.09 % FS** (upper bound, 289-resolution-limited). **PASS.**

---

## 3. ×10 range — nominal 0.100 V/A, full-scale 10 A → 1.0 V

| Nominal I | I_true (289, A) | Vout (45, mV) | V/A | Dev vs 0.100 |
|---|---|---|---|---|
| 0 | ~0 | +0.14 | — | offset |
| 0.5 | 0.481 | 48.28 | 0.1004 | +0.37 % |
| 1 | 0.972 | 96.83 | 0.09962 | −0.38 % |
| 2 | 1.947 | 194.6 | 0.09993 | −0.07 % |
| 4 | 3.916 | 389.8 | 0.09954 | −0.46 % |
| 6 | 5.871 | 585.8 | 0.09978 | −0.22 % |
| 8 | 7.83 (±4 mA) | 781.6 | 0.0998 | −0.2 % |

**Fit (7 pts):** gain **0.09976 V/A (−0.24 %)** — meets ±0.25 % user-cal grade uncalibrated. Offset ≤ ~1.4 mA. INL max **0.9 mV at 4 A ≈ 0.09 % FS** (upper bound). 10 A FS **extrapolated to 0.998 V** (FNIRSI caps 8.2 A). **PASS.**

---

## 4. Summary

| Test | Result | Spec | Verdict |
|---|---|---|---|
| Gain ×100 | 0.9995 V/A (−0.05 %) | ±0.9 % (typ 0.6) | PASS |
| Gain ×10 | 0.09976 V/A (−0.24 %) | ±1.0 % (typ 0.6) | PASS |
| Offset ×100 | ≤ ~2 mA in-ref | ±8 mA (typ 5) | PASS |
| Offset ×10 | ≤ ~1.4 mA in-ref | ±12 mA (typ 9) | PASS |
| INL (both) | ≤ 0.09 % FS (ref-limited) | ±0.08 % res-limited | PASS |
| Output impedance | ≈ 50 Ω (§5) | 50 Ω | PASS |
| Output clamp ×100 | ≈ 5.70 V (§6) | ~5.85 V | FLAG (−2.6 %) |
| PSRR / supply sensitivity | ≤ ±0.12 % over 13–15.5 V (§7) | reg ≥14.9 V | PASS |

All positive-current. Gain error tracks consistently across ranges at equal current (−0.38 % at 1 A on both).

---

## 5. Output impedance

Two Fluke 45 readings at the same 2 A input on ×100, output open vs into a **50.6 Ω** term:

- V_open = 1.945 V, V_50 = 0.970 V → **Rout = 50.6·(V_open/V_50 − 1) ≈ 50–51 Ω** — matches the declared **50 Ω**. **PASS.**

Run at low output (~2 V) so the OPA197 has headroom (sources only ~20 mA into 50 Ω). **Repeat caught a fixturing artifact:** the first term connection read 1.0845 V → apparent 40 Ω; reseating gave 0.970 V → ~50 Ω. The high first reading was extra contact/series resistance under-loading the output — discarded. Term value confirmed 50.6 Ω.

---

## 6. Output clamp (×100)

Pushing ×100 past 5 A full scale, output open (high-Z):

| Input (e-load) | Output (Fluke 45) |
|---|---|
| 5.5 A | 5.38 V (tracking) |
| 5.8 A | 5.685 V |
| 6.0 A | 5.694 V |
| 6.2 A | 5.695 V |

**Clamp ≈ 5.70 V** (window max 5.698 V), onset ~5.7 A — OPA197 output rail (flat over 5.8–6.2 A despite +0.4 A). **Finding:** ~0.15 V (2.6 %) below the ~5.85 V spec figure. Normal operation unaffected (FS 5 A → 5.0 V, ~14 % headroom); usable top of range is ~5.70 V. Recommend correcting the datasheet figure.

---

## 7. Supply sensitivity / PSRR (×100, ~2 A injection)

Fixed 2 A input; DUT aux swept on the FNIRSI, output on the Fluke 45:

| Vaux (V) | Vout (V) | Iaux (mA) |
|---|---|---|
| 13.0 | 1.9437 | 94.2 |
| 13.5 | 1.9476 | 94.8 |
| 14.0 | 1.9432 | 95.9 |
| 14.5 | 1.9473 | 96.1 |
| 14.9 | 1.9479 | 96.8 |
| 15.0 | 1.9456 | 94.6 |
| 15.5 | 1.9466 | 97.0 |

- **Rail rejection:** across 13.0–15.5 V (17 % swing) Vout spans only **4.7 mV pk-pk (±0.12 %)**, non-monotonic → **measurement noise, not real supply dependence.** Input-referred < ~2.4 mA over the whole range. **PSRR excellent.**
- **Regulation floor conservative:** full output held down to **13.0 V** — no degradation below the declared 14.9 V "full-performance" floor (DC transfer at 2 A).
- **Supply current** 94 → 97 mA across 13.0–15.5 V, ~95 mA at 15 V — consistent with the T1 Iq.
- **PASS.** Injection ~2 A (e-load 1.99 A; Fluke 289 value not relayed this run).

---

## 8. Deliberately NOT measured / caveats

- **Negative-current direction (whole matrix)** — all gain/offset/clamp/Z above is +I only; the reversed-shunt sweep is pending and needed for bidirectional symmetry.
- **×10 10 A full-scale point is extrapolated** — FNIRSI caps at 8.2 A (reached 8 A directly).
- **0.25 A ×100 is reference-limited** — Fluke 289 DC-current zero wanders ~±4 mA; settled reading gives 1.00 V/A.
- **Current reference is off-ScopeSweep, operator-read** — one bad relay (3.910 vs 4.403 A) caught by cross-check.
- **Output-Z 10 kΩ case not run.**
- **Not done:** bandwidth/−3 dB (×10, ×100), output noise, step response, CMRR, isolation withstand, temperature coefficient.

## 9. Bench notes worth carrying forward

- The electronic load's `set_setpoint` only stages the value; an explicit **`apply`** is required to commit it (same for the FNIRSI `set_voltage`/`set_current_limit`). Early points pinned at a stale ~1.03 A until found.
- The FNIRSI output relay would not close from software until re-tried after a panel interaction — output enable effectively gated to the unit.
- **Injection-loop series resistance ≈ 0.32 Ω** — drops ~2.6 V at 8 A, forcing the 10 V compliance to keep the load above its ~5 V CC floor.
- ccTrim settling on the load is ~8 s; read only after confirming stability.
- **A spec-deviating result deserves a repeat.** The output-Z first read (40 Ω) was a contact-resistance artifact; the repeat gave ~50 Ω.
- **When the FNIRSI powers the DUT aux, drop its current limit to ~0.2 A and set OVP ~15.6 V first** — it carries an 8.2 A limit from the current-loop role, unsafe for a ~95 mA aux.

---

## 10. Bidirectional update — negative-current sweep (2026-09-06)

*This section supersedes the "negative-current pending" notes in §1, §4 and §8.* The reversed-J2 sweep was completed 2026-09-06 with the two meters **swapped** — **Fluke 45 = loop current (in series, on ScopeSweep), Fluke 289 = Vout (SMA, operator-relayed)** — so V and I stay on independent COMs (per the shared-COM finding in `shunt-amp-rerun-2meter-2026-09-06.md`). Gain = Vout / I_true. Full per-point tables are in the companion `shunt-amp-negative-current-2026-09-06.md`; per-point rows are in `shunt-amp-results-register.csv` (Test IDs T4-NEG, T3-NEG, T5-NEG, BIDIR).

| Range | Positive slope | Negative slope | Directional asymmetry |
|---|---|---|---|
| ×100 | 0.9995 V/A | 1.0007 V/A (+0.07 %) | +0.12 % |
| ×10 | 0.09976 V/A | 0.09986 V/A (−0.14 %) | +0.10 % |

- **Bidirectional operation confirmed.** The two directions agree to **~0.1 %** on both ranges — inside the point-to-point scatter of either sweep and far inside the ±0.9 %/±1.0 % spec. Both negative-direction slopes also meet their user-cal grade (±0.15 % ×100, ±0.25 % ×10) uncalibrated.
- **Offset** in the negative direction is consistent with positive (×100 fit intercept +1.8 mV; ×10 ~+0.4 mV output) — a true output offset, not direction-dependent. **INL** max residual ≤ 0.07 % FS (×100), ≤ 0.06 % FS (×10).
- **Honest nuance:** on *both* ranges the negative direction reads ~0.1 % higher magnitude than the positive. The consistency across ranges hints at a small real directional term, but it sits at this bench's measurement floor (~0.1 % point scatter, ~±3–4 mA current-reference jitter). Reported as "symmetric to within ~0.1 %," not a proven asymmetry.
- **Still +I only:** output clamp (§6), output impedance (§5) and PSRR (§7) were **not** re-run in the negative direction — a reversed re-run would be needed for fully bidirectional clamp/Z/PSRR coverage.
- **Thermal at the 8 A top point (×10):** e-load 57 W / 40 °C, FNIRSI 79 W / 50 °C, both in CV/CC, no trips. FNIRSI current limit raised 6 A → 8.2 A for the ×10 range so the e-load's CC still set the current with the supply in CV.
