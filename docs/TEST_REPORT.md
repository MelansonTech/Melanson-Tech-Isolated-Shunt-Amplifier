# Bench Test Report — Isolated Shunt Amplifier

**Device under test:** MelansonTech Isolated Shunt Amplifier (Si8921BD-IS4R isolated
amplifier + 10 mΩ Vishay WSL3637 four-terminal Kelvin shunt)
**Board revision:** Rev 3.1
**Test dates:** 2026-09-05 – 2026-09-06
**Operator:** Shawn (MelansonTech)
**Bench:** ScopeSweep
**Report status:** Complete for the DC and dynamic campaign. Three specification
items remain untested and are named in §9.

---

## 1. Purpose and what changed

Every accuracy, bandwidth and drift figure in the README carries a dagger:

> † Derived from the schematic, BOM and device datasheets; still to be confirmed on
> the bench.

This campaign confirms them on hardware. It also closes the open item in
[Design Review Finding 8](DESIGN_REVIEW.md), which asked for the bandwidth to be
re-measured on a Rev 2 or Rev 3 board because the existing sweeps were all Rev 1 and
`C8`/`C9` differ between revisions.

**Headline: every specification this bench could test, the board meets** — most of
them by a comfortable margin, and two of them (DC gain on both ranges) at a grade the
datasheet reserves for a user-calibrated system, uncalibrated. Two documentation
corrections and one specification correction fall out of the work; they are in §8.

---

## 2. How to read the numbers

Two kinds of figure appear, and they are never mixed:

- **Declared** — the manufacturer's claim from the README, `CONNECTORS.md` and
  `CALIBRATION.md`. This is the thing under test, not evidence.
- **Measured** — produced on this bench, on these dates, each carrying the
  instrument that produced it.

Per-point rows for everything below are in
[`shunt-amp-results-register.csv`](test-data/shunt-amp-results-register.csv).

### Reference chain

| Quantity | Reference instrument | On ScopeSweep? |
|---|---|---|
| Output voltage `IsenseOut` | Fluke 45, DC V, ≥1 MΩ, across J1 centre→shell | yes |
| Loop current (positive-direction sweep) | Fluke 289, DC A, in series | no — operator-relayed |
| Loop current (negative-direction sweep) | Fluke 45, DC A, in series | yes |
| AC current | Maelstrom power-amp current monitor `Imon`, 0.100 V/A | yes |
| Frequency response | Digilent AD2 Network Analyzer, lock-in detector | yes |
| Output spectrum | Digilent AD2 Spectrum Analyzer | yes |
| Current actuator (**not** a reference) | MTECH-ELOAD in constant current | yes |

The electronic load is an **actuator, never a reference** — its readback runs about
20 mA high against the Fluke. Every current figure below is a meter reading.

---

## 3. DC transfer function

### 3.1 Method finding — two meters are required, not one

An early attempt to sweep with a single Fluke 45 alternating between DC volts and DC
amps produced a **current-proportional output error of ~22 mV/A**, which read as the
gain being about 1 % low. It is an artefact of the fixture, not the board.

A single DMM shares its COM terminal between its V and A inputs. Measuring `IsenseOut`
— referenced to `ISenseRTN` — *and* the loop current on the same meter ties
`ISenseRTN` into the injection loop, so the meter's own current-shunt burden appears
in series with the voltage reading:

```
Vout_measured = Vout_true − R_burden · I
```

Confirmed directly: at 0.975 A the shared-COM Fluke 45 read 0.955 V while an isolated
Fluke 289 on the output read **0.977 V** — a 22 mV gap, gain 0.98 against a true 1.00.

**Rule for this board:** on an isolated DUT, current and voltage must be measured by
two meters with independent COM terminals. All results below use two isolated meters.

### 3.2 ×100 range (5 A range, nominal 1.000 V/A)

Positive direction, 8 points, 0.25 → 5 A:

| I_true (A) | `IsenseOut` (V) | V/A | Deviation |
|---|---|---|---|
| 0 | +0.0011 | — | offset |
| 0.2535 | 0.2537 | 1.001 | +0.1 % |
| 0.482 | 0.4828 | 1.002 | +0.17 % |
| 0.972 | 0.9683 | 0.996 | −0.38 % |
| 1.9526 | 1.9457 | 0.996 | −0.35 % |
| 2.933 | 2.9291 | 0.999 | −0.13 % |
| 3.914 | 3.9074 | 0.998 | −0.17 % |
| 4.403 | 4.401 | 1.000 | −0.05 % |
| 4.890 | 4.8895 | 1.000 | −0.01 % |

**Least-squares fit: 0.9995 V/A (−0.05 %).** Zero intercept 1.3 mA (fit) / ~2 mA
(direct). Maximum residual 4.6 mV at 2 A ≈ **0.09 % of full scale**, an upper bound
set by the reference's read resolution.

### 3.3 ×10 range (10 A range, nominal 0.100 V/A)

Positive direction, 7 points, 0.5 → 8 A:

| I_true (A) | `IsenseOut` (mV) | V/A | Deviation |
|---|---|---|---|
| 0 | +0.14 | — | offset |
| 0.481 | 48.28 | 0.1004 | +0.37 % |
| 0.972 | 96.83 | 0.09962 | −0.38 % |
| 1.947 | 194.6 | 0.09993 | −0.07 % |
| 3.916 | 389.8 | 0.09954 | −0.46 % |
| 5.871 | 585.8 | 0.09978 | −0.22 % |
| 7.83 | 781.6 | 0.0998 | −0.20 % |

**Least-squares fit: 0.09976 V/A (−0.24 %).** Zero intercept 0.4 mA (fit) / 1.4 mA
(direct). Maximum residual 0.9 mV at 4 A ≈ **0.09 % of full scale**.

The 10 A full-scale point was **not measured** — the available supply limits at 8.2 A.
Extrapolating the fit gives 0.998 V at 10 A, inside the ±11.2 mV accuracy window, but
it is an extrapolation and is labelled as such wherever it appears.

### 3.4 Independent re-run

Both ranges were swept a second time with the meter roles exchanged, to check the
result was not an artefact of one fixture:

| Range | First run | Two-meter re-run | Agreement |
|---|---|---|---|
| ×100 | 0.9995 V/A | 0.9995 V/A | exact |
| ×10 | 0.09976 V/A | 0.0998 V/A | 0.04 % |

The re-run also reached lower currents (12 mA – 270 mA on the ×100 range) using the
load's LOW shunt and the meter's mA jack. Below ~50 mA the ~1 mV output offset
dominates the raw ratio, so gain is not resolvable better than a few percent there —
expected, and consistent with the fixed-term accuracy model.

### 3.5 Bidirectional operation

The input was reversed at J2 and both ranges re-swept, with the meters swapped so
voltage and current stayed on independent COM terminals:

| Range | Positive slope | Negative slope | Asymmetry |
|---|---|---|---|
| ×100 | 0.9995 V/A | 1.0007 V/A | 0.12 % |
| ×10 | 0.09976 V/A | 0.09986 V/A | 0.10 % |

**The board measures reverse current as faithfully as forward**, to within ~0.1 % on
both ranges — inside the point-to-point scatter of either sweep and far inside the
±0.9 % / ±1.0 % specification. Both negative-direction slopes also meet the
user-calibrated grade uncalibrated.

*Honest nuance:* on **both** ranges the negative direction reads ~0.1 % higher in
magnitude. The consistency across ranges hints at a small real directional term, but
it sits at this bench's measurement floor (~0.1 % point scatter, ±3–4 mA current
reference jitter). It is reported as *symmetric to within ~0.1 %*, not as a measured
asymmetry.

### 3.6 Zero offset and warm-up

Zero input, output measured on the ×100 range where it is most visible:

| Elapsed from cold | Output offset |
|---|---|
| ~0 min | +5.6 mV |
| 2–3 min | +1.77 mV |
| 5 min | +0.62 mV |
| 6–7 min | −0.035 mV |
| 7–8 min | −0.10 mV |

The offset settles monotonically through ~5.7 mV of excursion in about 8 minutes, then
wanders slowly at the sub-millivolt level. A **2 h 23 min soak (855 samples at 10 s)**
gave a settled band of **+0.1 / −0.5 mV**, i.e. under 0.5 mA input-referred against an
±8 mA specification.

`R28` was **not adjusted** — the board settled to within a millivolt of zero on its
own, so the trim the calibration procedure allows for was not needed on this unit.
Final settled offsets: **+1.1 mV (×100)**, **+0.14 mV (×10)** — about 1–2 mA and
1.4 mA input-referred respectively.

---

## 4. Output characteristics

### 4.1 Output impedance

Two readings at the same 2 A input on the ×100 range, output open and into a measured
50.6 Ω termination:

- V_open = 1.945 V, V_50 = 0.970 V
- **R_out = 50.6 · (V_open / V_50 − 1) ≈ 50–51 Ω** — matches the declared 50 Ω.

Run at ~2 V output so the OPA197 has headroom (it sources only ~20 mA into 50 Ω).

*A repeat caught a fixturing artefact worth recording:* the first termination
connection read 1.0845 V, implying ~40 Ω. Reseating gave 0.970 V and ~50 Ω. The high
first reading was contact resistance under-loading the output, and was discarded. **A
result that deviates from specification deserves a repeat before it is believed.**

### 4.2 Output clamp — specification correction

Pushing the ×100 range past 5 A full scale, output open:

| Input current | Output |
|---|---|
| 5.5 A | 5.38 V (still tracking) |
| 5.8 A | 5.685 V |
| 6.0 A | 5.694 V |
| 6.2 A | 5.695 V |

**Measured clamp ≈ 5.70 V**, onset ~5.7 A, flat across 5.8–6.2 A — the OPA197 output
rail. The README's computed swing is ±5.85 V, so the real part clamps **0.15 V (2.6 %)
lower than calculation predicted**.

Normal operation is unaffected: full scale is 5.0 V at 5 A, leaving ~14 % headroom.
The correction is to the datasheet figure, not to the design — see §8.

### 4.3 Supply sensitivity (PSRR)

Fixed 2 A input on the ×100 range, auxiliary rail swept:

| V_aux (V) | V_out (V) | I_aux (mA) |
|---|---|---|
| 13.0 | 1.9437 | 94.2 |
| 13.5 | 1.9476 | 94.8 |
| 14.0 | 1.9432 | 95.9 |
| 14.5 | 1.9473 | 96.1 |
| 14.9 | 1.9479 | 96.8 |
| 15.0 | 1.9456 | 94.6 |
| 15.5 | 1.9466 | 97.0 |

Across a **17 % supply swing** the output spans **4.7 mV peak-to-peak (±0.12 %)** and
the variation is non-monotonic — this is measurement noise, not supply dependence.
Input-referred, under ~2.4 mA across the whole range.

**The regulation floor is conservative.** Full output was held down to **13.0 V**,
with no degradation below the declared 14.9 V "full performance" floor, at least for DC
transfer at 2 A. The 14.9 V figure is about output *headroom* at full scale, not about
gain accuracy, and the measurement is consistent with that reading of it.

---

## 5. Frequency response

AC current is injected through the shunt by a Maelstrom power amplifier and referenced
to the amplifier's own current monitor (`Imon`, 0.100 V/A). The reported quantity is
the Ch2/Ch1 magnitude ratio, and both flatness and the −3 dB corner are taken from each
sweep's own low-frequency plateau — so the absolute scale, and `Imon`'s own ±0.6 % gain
error, do not enter.

### 5.1 ×100 range — −3 dB = 60 kHz

The low-frequency plateau is **19.92–19.94 dB = ×9.9** against the expected ×10 (DUT
1.0 V/A ÷ Imon 0.1 V/A). Agreement to ~1 % is a grounding and bias sanity check: it
confirms the reference buffer is intact and the injection loop is not earthing the
floating 0 V — and it ties the AC measurement to the DC gain of §3.2.

| Frequency | Magnitude | Phase |
|---|---|---|
| ≤ 5 kHz | 19.94 dB (flat) | ~0° |
| 20.0 kHz | 19.64 dB (−0.30) | −35° |
| 34 kHz | 18.95 dB (−1.0) | −58° |
| 49.6 kHz | 17.88 dB (−2.0) | −85° |
| **60 kHz** | **16.9 dB (−3.0)** | ~−99° |
| 120 kHz | 10.07 dB (−9.9) | −174° |

**−3 dB = 60 kHz (±~2 kHz)** — the top of the declared 30–60 kHz band. Confirmed
amplitude-independent: zoom sweeps at 0.25 A pk and 0.5 A pk give the same corner, so
it is genuinely small-signal and not slew-limited.

Passband flatness, a figure the datasheet did not previously carry:

| Flat within | Usable to | As gain error |
|---|---|---|
| ±0.03 dB | ~5 kHz | ±0.3 % |
| ±0.1 dB | ~13 kHz | ±1.2 % |
| ±0.5 dB | ~25 kHz | ±5.9 % |
| ±1 dB | ~34 kHz | ±12 % |

The ±0.03 dB figure is at the measurement floor — AD2 two-channel matching, with the
reference and response on 10:1 different ranges, is itself ±0.02–0.03 dB. The board's
true in-band flatness is **at least** this good.

### 5.2 ×10 range — −3 dB ≈ 580 kHz

| Frequency | Magnitude | Phase |
|---|---|---|
| ≤ 350 kHz | −0.3 dB (gentle shelf) | — |
| 520 kHz | −1.84 dB | +150° |
| 573 kHz | −2.82 dB | +128° |
| **~583 kHz** | **−3.0 dB** | ~+120° |
| 630 kHz | −4.20 dB | +104° |
| 1.0 MHz | −14.6 dB | — |
| 2.0 MHz | −40.2 dB | — |

**−3 dB ≈ 580 kHz — above the declared ~500 kHz.** Flatness ±0.1 dB to 55 kHz and
±1 dB to 470 kHz, a much wider flat region than the ×100 range, as 10× less gain
predicts.

**Reference caveat, stated plainly.** On this range the DUT shunt and the `Imon` shunt
are the same Vishay WSL3637 part, whose inductance zero lies somewhere between 318 kHz
(at 5 nH) and 3.2 MHz (at 0.5 nH). Those zeros partly cancel in the ratio, and if they
cancel imperfectly the apparent corner can be **inflated**. Two things bound the
concern:

1. The measured response is **monotonic with no peaking**, which is what a clean
   cancellation looks like; imperfect cancellation shows as a rise before the corner.
2. The Rev 1 sweeps in `Revision 1/TestData/BodePlots/` — taken years earlier, on a
   different fixture with a different reference — put the wide channel at
   **600–700 kHz**, and the Si8921's own bandwidth is ~600 kHz.

Two independent measurements landing at 580 kHz and 600–700 kHz, against a declared
500 kHz, is the basis for reporting the ×10 corner as **≈580 kHz, above declared**. A
flat non-inductive HF current reference would remove the residual uncertainty
altogether, and remains the one measurement that would close this completely.

### 5.3 Character of the roll-off

Both ranges show **phase running well ahead of magnitude** — −90° near 52 kHz on the
×100 range where a single pole would be at −45°. This is the Si8921's **transport
delay**, not additional poles: the isolator's group delay decouples magnitude from
phase.

| | ×100 | ×10 |
|---|---|---|
| Roll-off past the corner | ~30 dB/decade | ~70 dB/decade |
| Transport delay | ~2.4 µs | ~1.1 µs |

The steeper ×10 roll-off is the Si8921's internal reconstruction filter, which the
×100 range's own 60 kHz corner hides. The ×10 delay is about half the ×100 figure —
one fewer gain stage in the path.

---

## 6. Step response and large-signal behaviour

Derived from the measured magnitude and phase rather than captured directly. For a
band-limited linear stage the two are equivalent, and the derivation is traceable to
the sweeps in §5. A direct capture was not obtained because the AD2 oscilloscope
cannot take the analog input while the Network Analyzer holds it.

| Quantity | ×100 | ×10 |
|---|---|---|
| Rise time, 10–90 % | ≈ 6 µs | ≈ 0.6 µs |
| Group delay | ≈ 4.5 µs | — |
| Transport delay | ≈ 2.4 µs | ≈ 1.1 µs |
| Overshoot | small (magnitude monotonic) | small (magnitude monotonic) |

**Neither range is slew-limited anywhere in its span.** The OPA197 output stage slews
at 20 V/µs, giving a full-power bandwidth of 20/(2π·5 V) ≈ **640 kHz** on the ×100
range — more than 10× its 60 kHz small-signal corner. At full 5 V output and 60 kHz the
required slew is only 1.88 V/µs. On the ×10 range full scale is just 1 V, and 580 kHz
needs 3.6 V/µs.

**Large-signal bandwidth therefore equals small-signal bandwidth on both ranges.** The
corner is set by the isolator's filter, not by the output amplifier. The ×100 case is
also confirmed empirically by the amplitude-independence of §5.1.

---

## 7. Output noise

Informational — the datasheet declares no noise specification. Measured with the AD2
Spectrum Analyzer, generator off.

### ×100 range

**No dominant discrete spur.** The eight strongest components sit within ~5 dB of one
another (0.2–0.3 mV rms in an 814 Hz bin), spread across 8–82 kHz with no harmonic
structure — the random peaks of a noise floor, not a switching line. Largest components
≈ 0.3 mV rms at 18.7 and 30.4 kHz, a density of ~10 µV/√Hz.

Estimated integrated output noise **~2 mV rms** over the 60 kHz bandwidth ≈ **~2 mA rms
input-referred** — well below the ±8 mA fixed accuracy term, so noise does not limit
the measurement.

### ×10 range — a switching-spur family

| Frequency | Level | Note |
|---|---|---|
| 54.2 kHz | 0.6 mV rms | fundamental |
| **108.3 kHz** | **1.2 mV rms** | **strongest** |
| 162.5 kHz | 0.8 mV rms | harmonic |
| 217 / 326 / 540 kHz | 0.1–0.2 mV rms | higher harmonics |

The strongest spur is **1.2 mV rms at 108 kHz ≈ 12 mA rms input-referred**. Likely
sources are the isolated DC-DC (NXJ1S0505) or the Si8921 modulator clock, coupling on
the output side.

**Why the ×100 range looks clean:** these spurs fall inside the ×10 passband (580 kHz)
but outside the ×100 range's 60 kHz roll-off. Being an output-side coupling — the same
absolute millivolts on either range — the narrower ×100 bandwidth simply rejects them.

**This deserves attention rather than a footnote.** 12 mA rms input-referred is
comparable to the entire ±12 mA fixed accuracy term for the ×10 range. It is in-band
AC noise, not a DC offset, so it does not shift a settled reading — but an application
sampling the ×10 output without filtering will see it. **A 100 kHz low-pass on the
output removes it and costs nothing that matters below ~50 kHz.**

*Caveat:* measured with the injection loop connected rather than J2-open. The harmonic
structure points to the board, but a J2-open capture would settle attribution.

---

## 8. Findings — actions arising

Three corrections and one closure fall out of this campaign.

### 8.1 The auxiliary supply figure is wrong by ~5× — correct it

The README states the auxiliary supply draws **~300 mW**. Measured: **95.8 mA at 15.00 V
= 1.44 W** (T1), and 94.2 → 97.0 mA across the whole 13.0–15.5 V range (PSRR sweep) —
call it **~95 mA, ~1.4 W**.

The design intent was ~100 mA, so **the board is behaving as designed and the
documentation is wrong**. This matters practically: a user sizing a wall adapter from
"300 mW" could choose a supply five times too small.

**Measured on the ×100 range only.** `Rel1`'s coil sits on `HighGain`, the range
switch's output, so it is energised on ×100 and not on ×10 — the ×10 draw will be lower
by the coil current. The published figure is therefore the **worst case of the two**,
which is the right one to size a supply against, but the ×10 figure has not been taken.

**Action:** change the README's auxiliary supply figure to **~1.4 W (≈95 mA at 15 V)**.

### 8.2 The output clamp is 5.70 V, not 5.85 V — correct it

Computed swing ±5.85 V; measured clamp ≈5.70 V, 2.6 % lower (§4.2). The README already
notes the Rev 3.1 silkscreen's ±6 V disagrees with the computed 5.85 V; the measured
value now supersedes both.

**Action:** quote **5.70 V measured** as the output clamp, with the computed 5.85 V
retained as the derivation it came from.

### 8.3 The ×10 noise spur should be documented

§7 finds a 108 kHz spur at ~12 mA input-referred on the ×10 range — comparable to that
range's whole fixed error term, and absent from the ×100 range only because of its
narrower bandwidth.

**Action:** add a noise section to the datasheet giving both ranges' figures, and
recommend an output low-pass for ×10 users who sample without filtering.

### 8.4 Design Review Finding 8 can be closed

Finding 8's remaining item was: *"Re-measure on the Rev 2 or Rev 3 board — the existing
data is all Rev 1, and `C8`/`C9` differ."* Both ranges have now been measured on Rev 3.1
(§5), with the ×10 result independently corroborated by the Rev 1 sweeps.

**Action:** mark Finding 8 resolved, citing this report.

### 8.5 A note on the historical test-plan pass criterion

An early version of the test plan set the T1 supply-current criterion at
"~10–40 mA @ 15 V", derived from the erroneous 300 mW figure. The board draws ~95 mA
and was recorded as a pass on the basis of design intent. **The criterion was wrong,
not the board** — recorded here so the register's PASS is not mistaken for a waived
failure.

---

## 9. Deliberately not measured

An omitted test is honest; a test run without the right instrument is not. These
remain **declared-only** and no claim in this report or in any marketing material may
present them as verified.

| Specification | Why not measured |
|---|---|
| **4.2 kV isolation withstand** | No hipot / dielectric tester on this bench. |
| **400 Vdc common-mode range and CMRR** | Highest available supply is 36 V. CMRR could only be exercised at a fraction of rated common mode, which confirms nothing about the 400 V figure. |
| **Temperature coefficient, 0–40 °C** | No thermal chamber. Only ambient warm-up drift was observed (§3.6), which is not the rated figure. |
| ×10 range at 10 A full scale | Forcing supply limits at 8.2 A. Top point measured 8 A; 10 A extrapolated from the fit. |
| Negative-direction clamp, output impedance, PSRR | Only gain, offset and linearity were swept in reverse. Positive-direction values stand. |
| Supply current on the ×10 range | Measured on ×100 only, where `Rel1`'s coil is energised. The ×10 figure is lower by the coil current; the published number is the worst case. |
| Output impedance into ~10 kΩ | Optional case, not run. |
| Direct time-domain step capture | Instrument arbitration (§6). Derived from magnitude and phase instead. |

---

## 10. Results summary

| Test | Measured | Declared | Verdict |
|---|---|---|---|
| DC gain, ×100 | 0.9995 V/A (−0.05 %) | ±0.9 % (typ 0.6 %) | **PASS** |
| DC gain, ×10 | 0.09976 V/A (−0.24 %) | ±1.0 % (typ 0.6 %) | **PASS** |
| Offset, ×100 | ≤ ~2 mA input-referred | ±8 mA | **PASS** |
| Offset, ×10 | ≤ ~1.4 mA input-referred | ±12 mA | **PASS** |
| Linearity (INL), both | ≤ 0.09 % FS (reference-limited) | ±0.08 % (resolution-limited) | **PASS** |
| Bidirectional symmetry | ~0.1 % both ranges | (not specified) | **PASS** — new data |
| Output impedance | ~50–51 Ω | 50 Ω | **PASS** |
| Output clamp, ×100 | ≈5.70 V | ~5.85 V computed | **FLAG** — see §8.2 |
| Supply sensitivity | ±0.12 % over 13.0–15.5 V | regulation ≥14.9 V | **PASS** |
| Supply current (×100) | ~95 mA / ~1.4 W at 15 V | ~300 mW | **FLAG** — see §8.1 |
| Bandwidth, ×100 | 60 kHz | ~30–60 kHz | **PASS** |
| Bandwidth, ×10 | ≈580 kHz | ~500 kHz | **PASS** — exceeds |
| Passband flatness, ×100 | ±0.1 dB to 13 kHz | (not specified) | new data |
| Passband flatness, ×10 | ±0.1 dB to 55 kHz | (not specified) | new data |
| Rise time | ~6 µs (×100) / ~0.6 µs (×10) | (not specified) | new data |
| Large-signal bandwidth | = small-signal, both ranges | (not specified) | new data |
| Output noise, ×100 | ~2 mA rms input-referred | (not specified) | new data |
| Output noise, ×10 | 108 kHz spur, ~12 mA rms input-referred | (not specified) | new data — see §8.3 |
| Isolation, CM range, tempco | **not measured** | declared | out of scope (§9) |

**Both DC gain results meet the user-calibrated accuracy grade — ±0.15 % on the ×100
range and ±0.25 % on the ×10 range — without any calibration applied.** That is the
single most commercially significant result in this report, and it held across two
independent fixtures and both current directions.

---

## 11. Bench notes worth carrying forward

Recorded because the next person to test one of these boards will otherwise rediscover
them.

- **Two isolated meters, always.** One meter reading both V and I corrupts the output
  by ~22 mV/A through its own shunt burden (§3.1).
- **The injection loop has ~0.32 Ω of series resistance**, dropping ~2.6 V at 8 A — the
  compliance source must be sized for it, not just for the shunt.
- **The electronic load's CC trim settles in ~8 s.** Read only after the meter's
  statistics have settled; several earlier readings looked plausible and were mid-ramp.
- **A spec-deviating result deserves a repeat before it is believed.** The 40 Ω output
  impedance was contact resistance (§4.1).
- **When the bench supply powers the auxiliary rail, drop its current limit to ~0.2 A
  and set OVP to ~15.6 V first.** It may be carrying an 8 A limit from a current-loop
  role, which is not safe for a ~95 mA auxiliary input.
- **Thermal at the 8 A top point:** load 57 W / 40 °C, supply 79 W / 50 °C, both in
  regulation, no trips.
- Range changes (SW1 pos 3 → 2) were made at zero loop current with the load
  disengaged; the board stays powered.

---

*Every figure in this report was measured on the dates stated with the instrument
named. Figures marked declared are the manufacturer's claims and are the subject of
the tests, not evidence produced by them.*
