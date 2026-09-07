# Isolated Shunt Amplifier — Two-Meter Gain Re-run & Measurement-Method Finding

**DUT:** Melanson Tech Isolated Shunt Amplifier
**Date:** 2026-09-06
**Operator:** Shawn (MelansonTech)
**Companion to:** `shunt-amp-dc-transfer-report-2026-09-06.md`, `shunt-amp-results-register.csv`

---

## 1. Purpose

Re-run the ×100 and ×10 DC gain with a **two isolated-meter** rig — **Fluke 45 measuring the injection current in the loop, Fluke 289 measuring Vout on the output** — to (a) validate the original single-current-reference data and (b) add low-current detail. This grew out of a measurement-method finding, below.

## 2. Method finding — do NOT use one meter for both V and I on this isolated DUT

An attempt to automate the sweep with a single Fluke 45 (toggling DC voltage ↔ DC current) produced a **current-proportional Vout error of ~22 mV/A**, dragging the apparent gain ~1 % low.

**Cause:** a single DMM shares its COM between the V and A inputs. Measuring Vout (referenced to the isolated output node `ISenseRTN`) *and* the loop current on the same meter ties `ISenseRTN` into the injection loop, so the meter's own current-shunt burden appears in series with the Vout reading: **Vout_meas = Vout_true − R_burden·I**.

**Confirmed directly:** at 0.975 A, Fluke 45 (shared COM) read 0.955 V while the Fluke 289 (isolated, on the output) read **0.977 V** — a 22 mV gap, i.e. gain 0.98 vs the true 1.00.

**Rule:** on an isolated DUT, current and voltage must be on **two separate meters with independent COMs**. The Fluke 45's ~1 % droop was entirely this artifact — the DUT gain is nominal.

## 3. ×100 re-run — Fluke 45 (current) + Fluke 289 (Vout), isolated

| I_inj (A) | Vout | V/A | Note |
|---|---|---|---|
| 0.01211 | 12.8 mV | 1.057 | offset-inflated (×100 offset ~1 mV is ~8 % of 13 mV) |
| 0.05262 | 52.97 mV | 1.007 | offset-inflated |
| 0.2668 | 262.4 mV | 0.983 | |
| 0.4834 | 0.482 V | 0.997 | |
| 0.9731 | 0.9691 V | 0.996 | |
| 1.9523 | 1.9475 V | 0.998 | |
| 2.9352 | 2.9280 V | 0.998 | |
| 4.8984 | 4.8946 V | 0.999 | |

**Fit slope = 0.9995 V/A — identical to the original run.** Low-current points (10–270 mA) scatter ±~3 mV about the line (the ~1 mV offset dominates the raw ratio below ~50 mA); consistent with ~1.0, not resolvable better than a few % down there.

Low-current current reference notes: the e-load floors at ~0.27 A on the HIGH shunt and ~12 mA on the LOW shunt; sub-100 mA current must be read on the Fluke 45's **mA jack** (0.1 A range) — the 10 A jack over-reads by ~1.4 mA at 12 mA (negligible by 50 mA).

## 4. ×10 re-run — same rig

| I_inj (A) | Vout | V/A |
|---|---|---|
| 0.4824 | 48.2 mV | 0.09992 |
| 0.9737 | 96.97 mV | 0.09959 |
| 1.9519 | 194.65 mV | 0.09973 |
| 3.9135 | 390 mV | 0.09966 |
| 5.8728 | 586.3 mV | 0.09983 |

**Fit slope ≈ 0.0998 V/A — matches the original ×10 (0.09976).**

## 5. Conclusion

| Range | Original | Two-meter re-run | Agree? |
|---|---|---|---|
| ×100 | 0.9995 V/A | 0.9995 V/A | ✓ |
| ×10 | 0.09976 V/A | 0.0998 V/A | ✓ |

Both ranges' recorded gains are **validated** by the independent two-meter method, and the single-meter ~1 % droop is fully explained as the shared-COM burden. No change to the recorded gain results.

## 6. Bench notes from this run

- **Single-meter V+I corrupts Vout ~22 mV/A on an isolated DUT** (shared COM). Use two isolated meters. (§2)
- The Fluke 45's low current ranges (0.01/0.1 A) read the **mA jack**; the 10 A range reads the **10 A jack**. Leads must match the range, and moving them can leave the loop open — verify continuity after a jack move.
- The e-load's **engage control is intermittently stuck** (reads/holds disengaged, or drops on a setpoint step); recovered only by a power cycle. Control the current via setpoint and confirm with the in-loop meter, not the engage flag.
- Not re-captured: ×10 above 6 A (engage dropped; the original covers 8 A). Still pending overall: **negative-current sweep** (reverse J2) and **AC bandwidth/noise/step** (power-amp + AD2).
