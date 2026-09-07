# Test Plan — Melanson Tech Isolated Shunt Amplifier

**DUT:** Melanson Tech Isolated Shunt Amplifier (Si8921 isolated amp + 10 mΩ Kelvin shunt)
**Repository:** github.com/MelansonTech/Melanson-Tech-Isolated-Shunt-Amplifier
**Test bench:** ScopeSweep
**Plan authored:** 2026-09-05
**Operator of record:** Shawn (MelansonTech)

---

## 1. How to read this plan

Two kinds of number appear here and they must never be confused:

- **Declared / datasheet** figures come from the DUT's own repository docs
  (README, CONNECTORS.md, CALIBRATION.md, SAFETY.md). They are the
  manufacturer's claims — the thing under test — **not measurements**.
- **Measured** figures are produced on this bench, this session, and each one
  is recorded with the instrument that produced it and the date, in the
  results register. No cell in the register is filled from a declared value.

As of this writing **no DUT measurement has been taken** — the Fluke 45 reads
`nan` (open leads) and the FNIRSI supply is off. The register is a template
with the planned setpoints filled in; readings are added during execution.

---

## 2. Device summary (declared)

| Item | Declared value | Source |
|---|---|---|
| Topology | Si8921 isolated amplifier + 10 mΩ Kelvin shunt (Vishay WSL3637) | README |
| Range ×10 (SW1 pos 2) | 100 mV/A, 10 A full-scale → 1.0 V, ~500 kHz BW | CONNECTORS.md |
| Range ×100 (SW1 pos 3) | 1 V/A, 5 A full-scale → 5.0 V, ~30–60 kHz BW | CONNECTORS.md |
| Accuracy ×10 @23±5 °C | ±(1.0 % rdg + 12 mA); typ ±(0.6 % + 9 mA) | README |
| Accuracy ×100 @23±5 °C | ±(0.9 % rdg + 8 mA); typ ±(0.6 % + 5 mA) | README |
| Accuracy w/ user gain cal | ×10 ±(0.25 %+12 mA); ×100 ±(0.15 %+8 mA) | README |
| Tempco (outside 23±5 °C) | ±(0.011 % rdg + 0.5 mA)/°C | README |
| Output | SMA J1, `IsenseOut` signal, 50 Ω source impedance | CONNECTORS.md |
| Output reference | SMA shell `ISenseRTN` = 6 V ref (board 0 V floats ~6 V below chassis) | CONNECTORS.md |
| Read the output with | ≥1 MΩ input; 50 Ω term reads half; <10 kΩ load → >0.5 % error | CONNECTORS.md |
| Aux supply J4 | Isolated 13–15 V barrel (centre +, sleeve board-0 V), ~300 mW, use 15.0 V, never >15.6 V | CONNECTORS.md |
| Input J2 | Phoenix 5442002 terminal block, 12 A / 400 V; **carries full current, not a sense connection**. Pin1 shunt-low, Pin2 shunt-high/GND_ISO | CONNECTORS.md |
| Range LEDs | D5 lit = ×10, D4 lit = ×100; both dark = no supply; both lit = fault | CONNECTORS.md |
| Zero trim | R28 100 Ω pot; 30 min warm-up; untrimmed 2.9–4.5 % FS offset | CALIBRATION.md |

---

## 3. Safety and ground rules (read before energizing)

1. **The aux supply must be isolated/floating.** Board 0 V floats ~6 V below
   chassis; the SMA shell (`ISenseRTN`) is a 6 V reference, not ground. A
   supply whose negative is bonded to earth shorts the reference buffer →
   wrong readings **and** a hazard. The FNIRSI IPS3608 benchtop outputs are
   floating; confirm its negative is not tied to earth or to any scope ground.
2. **Never exceed 15.6 V on J4.** Set FNIRSI OVP to ~15.5 V. Aux current limit
   modest (≈0.2 A) — the board draws only ~20–40 mA.
3. **Do NOT test common-mode / isolation on this bench.** The 400 V CM and
   4.2 kV isolation figures are declared-only and explicitly **out of scope** —
   the board has unverified creepage/clearance (SAFETY.md) and no rated
   enclosure. Keep the input near chassis potential throughout.
4. **J2 carries the full measured current.** Torque the terminals, use wire
   rated for the current; at 10 A a loose terminal is the hottest thing on the
   board. Treat J2 as energized whenever the measured loop is live.
5. **Thermal.** U6 (HT7550 regulator) is the hottest part; the shunt rises
   ~33 °C at 10 A. Limit continuous full-current dwell; let it settle between
   points.
6. **Fluke 45 current fuse.** Its top current range opens a fuse if exceeded —
   do not push the meter past its rated current (see fixturing note F1).

---

## 4. Reference selection (what each number is worth)

| Quantity | Reference on this bench | Note |
|---|---|---|
| Output voltage `IsenseOut` | **Fluke 45** (Multimeter), DC V, ≥1 MΩ, measured **across J1 centre→shell** | The accuracy reference here |
| Aux supply voltage at J4 | **Fluke 45** at the barrel | FNIRSI readback ≈ its setpoint at no load — not independent |
| Input current through shunt | **Fluke 45 in series** up to its safe range, **or** the MTECH load current *after* it is corrected against the Fluke (`correct_readback`) | One meter can't read V and I at once — see §6 |
| Frequency response | **AD2 Network Analyzer** (Bode) | Watch the AD2 large-range artifact — see T6 |
| Output noise/spurs | **AD2 Spectrum Analyzer** | Input-referred = output ÷ gain |
| Transients | **Rigol DS1104Z** or AD2 scope on the SMA | Output measured directly, so the 500 kHz current-probe limit does not apply |

---

## 5. Bench instrument assignments (read this session)

| Role | Instrument | ScopeSweep panel | State read 2026-09-05 |
|---|---|---|---|
| Output voltage / current reference | Fluke 45 | Multimeter | connected, DC V, reads nan (open) |
| Aux 15 V isolated supply → J4 | FNIRSI IPS3608 | FNIRSI IPS3608 — Power Supply | connected, output OFF, 0 V |
| DC current sink (injection loop) | MTECH-ELOAD | Electronic Load | connected, CC, not engaged, shows ~44 mA zero-offset |
| Frequency response | Analog Discovery 2 | Network Analyzer | connected, 100 Hz–100 kHz, 31 pts, Bode |
| Output noise / spectrum | Analog Discovery 2 | Spectrum Analyzer | connected |
| Transient / waveform | Rigol DS1104Z, AD2 | Oscilloscope / Rigol panel | connected |
| AC current injection source | FeelTech FY3224S or AD2 AWG | Function Generator | connected |

---

## 6. Fixturing decisions (need Shawn) 

**F1 — Which source is the aux supply and which drives the current loop?**
There is one benchtop supply (FNIRSI) that can both hold 15 V and pass amps,
but it can only do one job at a time; the AD2 supplies max out near ±5 V and
cannot pass the test current. The DC current loop needs a compliance source
(a few volts at up to 5–8 A) **plus** the load to set the current. Pick one:

- **F1-a:** Power the DUT aux from your own isolated 15 V wall/bench source, and
  free the FNIRSI to be the current-loop compliance source (FNIRSI → J2 shunt →
  MTECH load(CC) → back). This lets the whole DC sweep run through ScopeSweep.
- **F1-b:** Use the FNIRSI as the aux supply, and provide a separate
  bench supply (not in ScopeSweep) for the current loop. Then the current
  value comes from the Fluke-in-series (≤ its fuse limit) and I log it by hand.

**F2 — Current reference for the DC sweep.** One Fluke can read either
`IsenseOut` **or** series current, not both. Preferred: first run
`correct_readback` on the MTECH load against the Fluke (Fluke in series, ≤ its
top current range) to make the load's current traceable, then during the DUT
sweep use the **corrected load current** as I_true and the **Fluke** on
`IsenseOut`. Alternative: alternate the Fluke between V and I at each point
(manual lead swap, slower, more error-prone).

**F3 — AC current injection network (for T6/T8).** Injecting AC current through
a 10 mΩ shunt needs a transconductance path: AWG → power buffer / series
resistor → J2, with a current-sense (series R voltage) as the Bode reference.
Keep the AC current well below full-scale. Confirm what you have to build this.

---

## 7. Test procedures

### T1 — Supply and quiescent current
- **DUT config:** SW1 pos 2 (×10), then pos 3 (×100). Aux = FNIRSI 15.00 V.
- **Steps:** Enable aux. Confirm exactly one range LED (D5 on ×10 / D4 on ×100).
  Read aux current (FNIRSI readback; cross-check Fluke-in-series if available).
- **Record:** I_supply each range, LED state, any fault (both LEDs).
- **Pass:** one LED lit, no fault, I_supply in a sane band (≈10–40 mA @15 V,
  ~300 mW declared).

### T2 — Zero offset and warm-up drift (R28)
- **DUT config:** J2 open (no current). SW1 pos 3 (×100 — the sensitive range
  the cal doc uses). Aux 15.00 V.
- **Steps:** Log `IsenseOut` (Fluke, J1 centre→shell) via Data Logger, ~1
  sample/10 s for 30 min → warm-up curve. Repeat spot reading on pos 2 (×10).
  If offset is large, Shawn adjusts R28 (physical trim); record before/after.
- **Record:** offset vs time, final offset each range, R28 before/after.
- **Pass:** post-trim within a few mV of zero (CALIBRATION.md); i.e. input-
  referred offset within the spec fixed term (12 mA ×10, 8 mA ×100).

### T3 — DC transfer function / gain accuracy, ×10
- **DUT config:** SW1 pos 2. Current loop per F1.
- **Setpoints (A):** 0, 1, 2, 4, 6, 8. (10 A full-scale is **extrapolated** from
  the fit — held below the Fluke's fuse limit; state this in the report.)
- **Steps:** At each I_true, read `IsenseOut` (Fluke). Compute gain (V/A), fit
  a line, extract slope, zero intercept, residuals.
- **Record:** per-point I_true / IsenseOut / instrument / time; slope, offset,
  max residual.
- **Pass:** error ≤ ±(1.0 % rdg + 12 mA) referred to input; nominal 100 mV/A.

### T4 — DC transfer function / gain accuracy, ×100
- **DUT config:** SW1 pos 3. Current loop per F1.
- **Setpoints (A):** 0, 0.5, 1, 2, 3, 4, 5 (full range — within the Fluke).
- **Steps/record:** as T3; nominal 1 V/A → up to 5.0 V out.
- **Pass:** error ≤ ±(0.9 % rdg + 8 mA) referred to input.

### T5 — Linearity and offset (derived from T3/T4)
- **Compute:** max deviation from best-fit line (% of full-scale), gain error
  (%), input-referred offset (zero intercept).
- **Pass:** within the reading-proportional and fixed spec terms above.

### T6 — Frequency response / bandwidth (Bode)
- **DUT config:** ×10 then ×100. AC current injection per F3.
- **Setup:** AD2 Network Analyzer; reference probe = injection current-sense,
  response probe = `IsenseOut`. Small-signal (current well below FS). Magnitude
  reference at low frequency ties to the DC gain from T3/T4.
- **Sweep:** ×10 → 100 Hz–2 MHz; ×100 → 100 Hz–200 kHz. Extract −3 dB.
- **⚠ Honesty flag:** the AD2's large voltage ranges fake an audio-band pole
  (~0.35 % divider mismatch reads as a roll-off). The ×100 corner (~30–60 kHz)
  sits exactly where that artifact bites. **Before trusting the ×100 corner,
  validate AD2 flatness with a resistive loopback**, use matched/small AD2
  ranges, and cross-check the ×100 corner with a manual FeelTech + Rigol sweep.
- **Record:** −3 dB each range, gain flatness, phase; the flatness-validation result.
- **Pass:** ×10 corner ≈ 500 kHz; ×100 corner in 30–60 kHz (declared), with the
  AD2 artifact ruled out.

### T7 — Output noise and spectrum
- **DUT config:** J2 open (no current). ×10 then ×100. Aux 15.00 V.
- **Setup:** AD2 Spectrum Analyzer on `IsenseOut`. Note the DC-DC (NXJ1S0505)
  switching and any isolator chopper spur.
- **Record:** broadband noise, notable spurs (freq/level), input-referred noise
  (= output ÷ gain).
- **Pass:** informational (no declared limit) — report values with provenance.

### T8 — Step response (optional cross-check of ×10 BW)
- **DUT config:** SW1 pos 2. MTECH load step (dynamic mode) drives a fast
  current step; observe `IsenseOut` settling on the Rigol (output measured
  directly, so the 500 kHz current-probe limit does not apply).
- **Record:** rise time, settling; cross-check against T6 ×10 corner.

### T9 — Output termination sensitivity (optional)
- **Steps:** Read `IsenseOut` at a fixed current into ≥1 MΩ, then into a 50 Ω
  term (expect half) and a ~10 kΩ load (expect >0.5 % error, per docs).
- **Pass:** matches the declared 50 Ω-source behaviour.

---

## 8. Deliberately NOT measured (state in every report)

- **400 V common-mode / 4.2 kV isolation withstand** — out of scope; unsafe on
  this bench and creepage/clearance is unverified (SAFETY.md).
- **Temperature coefficient (0–40 °C)** — no thermal chamber on this bench.
- **Absolute traceable current at the ×10 10 A full-scale point** — held below
  the Fluke fuse limit; top decade extrapolated from the linear fit.
- **Long-term / lifetime drift** beyond the T2 30 min warm-up window.

---

## 9. Records produced

- This plan: `shunt-amp-test-plan.md`
- Excel/CSV test matrix: `shunt-amp-test-matrix.csv`
- Excel/CSV results register (filled during execution): `shunt-amp-results-register.csv`
- Excel/CSV equipment & setup: `shunt-amp-equipment.csv`
- At session end: a provenance-carrying session record via ScopeSweep
  (`export_document session` → CSV + DOCX + PDF), every measured number tagged
  with its instrument and date.

*CSV is used because the bench's document exporter emits Excel-native CSV (and
DOCX/PDF), not multi-sheet .xlsx. Each CSV opens directly in Excel as one sheet
and can be pasted into the repo's `docs/TEST_RECORD.xlsx`.*
