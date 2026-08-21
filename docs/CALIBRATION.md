# Calibration

Two adjustments matter, and only one of them is on the board.

| | What it does | Where | Effect on the spec |
|---|---|---|---|
| **Zero trim** | Nulls every static offset in the chain | `R28` on the board | **Required.** Without it the board is several percent out — see below |
| **Gain correction** | Removes shunt and isolator initial tolerance | **In your DAQ or software** — there is no gain trim on the board | Optional. Takes ±1.0 % to ±0.25 % |

Read [`SAFETY.md`](SAFETY.md) first if the input will be connected to anything energised. All of
the procedures below are done with the input at low voltage and low current — no part of
calibration requires the board to be at high common-mode potential.

## Why the zero trim is not optional

`R28` nulls the *entire* chain's input-referred offset in one adjustment — the two reference
divider tolerances, both LM7321 input offsets, `U3`'s offset, the Si8921's input offset, and the
bias-current terms. Untrimmed, those add up to:

| | 10 A range | 5 A range |
|---|---|---|
| Static offset, untrimmed, worst case | **2.9 % of full scale** | **4.5 % of full scale** |
| After the `R28` trim | 0 | 0 |

A board that has not been trimmed is not slightly out, it is unusable. The trim takes about two
minutes.

Because the trim acts ahead of `U8`, **a null on one range holds on the other** — you do not
trim twice.

## Equipment

| For | You need |
|---|---|
| Zero trim | A DMM with ≥ 1 mV resolution, or a scope on a ≥ 10 mV/div range. A small trimmer screwdriver. |
| Gain correction | A known current source or a reference ammeter, able to hit at least 50 % of the range you care about |
| Either | An **isolated** 15 V supply — see the README |

The output is measured **`IsenseOut` (SMA centre) relative to `ISenseRTN` (SMA shell)**, not to
your instrument's chassis. Use a 1 MΩ input; a 50 Ω terminated input reads half.

---

## Procedure 1 — zero trim

Do this at the temperature the board will be used at. The residual drift after trimming is what
limits zero stability, so trimming at 23 °C and then operating at 40 °C gives up most of the
benefit — see the drift plot in [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md).

1. **Leave `J2` open, or short it.** Either is fine — with no current flowing the shunt develops
   no voltage. Shorting it is slightly better because it also shorts out any stray pickup.
2. **Power the board** from the isolated 15 V supply. Set `SW1` to position 3 — the **5 A range,
   ×100**. Trim on the high-gain range: its ten-times gain makes the null ten times easier to see,
   and the result holds on the other range.
3. **Let it warm up.** Thirty minutes. `U6` and the shunt both settle, and the reference nodes
   move while they do. Trimming cold and re-checking warm is the commonest way to waste the
   adjustment.
4. **Measure `IsenseOut` relative to `ISenseRTN`.**
5. **Adjust `R28`** until the reading is as close to zero as you can hold it.
6. **Record the residual** in the test record. It should land within a few millivolts of zero.

### What "good" looks like

`R28` is a **100 Ω** trimmer (fit 100 Ω — the BOM's 10 kΩ line is an error, see finding 4 in the
design review). That gives ±3.0 mV of adjustment at `DiffAmpRef` with a settable step of about
60 µV, which is 0.06 % of full scale at the output on the ×100 range.

| Observation | What it means |
|---|---|
| Nulls comfortably, well inside the pot's travel | Normal. Your parts are near typical. |
| Nulls only near one end of travel | Acceptable but marginal — note it in the test record |
| **Will not null at either extreme** | The chain's offset exceeds ±3 mV. Fit a 200 Ω trimmer, which doubles the range and still resolves to 0.12 % of full scale. See the **R28 sizing** and **Trim range** tabs of the tolerance budget. |

That last case is not a fault, it is a tolerance stack. At datasheet limits the chain's static
offset can reach ±24 mV, well beyond ±3 mV of trim range — the 100 Ω value works because real
parts sit far inside their limits. In a production run, expect the occasional board that needs
the larger trimmer.

### Re-trimming

Worth doing whenever the board has moved temperature and you care about small readings. The
fixed error term roughly halves:

| Excursion from the trim temperature | Fixed term, 10 A range | Fixed term, 5 A range |
|---|---|---|
| ±20 °C | 17.9 mA | 13.9 mA |
| ±5 °C | 11.3 mA | 7.3 mA |
| Re-trimmed at the working temperature | **9.1 mA** | **5.1 mA** |

Below that floor there is no point adjusting further — what remains is Si8921 nonlinearity, which
no trim can reach.

---

## Procedure 2 — gain correction

Optional, done in your own system, and worth roughly a factor of four:

| | As shipped | With gain correction |
|---|---|---|
| 10 A range | ±(1.0 % of reading + 12 mA) | ±(0.25 % of reading + 12 mA) |
| 5 A range | ±(0.9 % of reading + 8 mA) | ±(0.15 % of reading + 8 mA) |

The proportional term is dominated by the shunt's ±0.5 % initial tolerance and the Si8921's
±0.2 % gain error. Both are **systematic per board** — the same on every reading, every day — so
a single measured constant removes them. The fixed term is drift and nonlinearity and does not
improve.

1. **Zero-trim first** (procedure 1). Gain correction on an untrimmed board measures the offset,
   not the gain.
2. **Apply a known current** through `J2`. Use at least 50 % of range, ideally full scale — the
   fixed error term is a much smaller fraction of the reading up there, so the constant comes out
   cleaner. Measure the true current with a reference ammeter in series, or use a source you
   trust.
3. **Record the output voltage** and the true current.
4. **Compute the constant:**

   ```
   nominal    10 A range (×10) : 100 mV/A     →  I = Vout / 0.100
                5 A range (×100): 1 V/A       →  I = Vout / 1.000

   k = I_true / I_indicated
   ```

5. **Apply `k`** in whatever reads the output. A value within about ±1 % of 1.000 is expected; if
   it is further out than ±2 %, something else is wrong — check the load impedance first (a 50 Ω
   terminated input gives k ≈ 2.0).
6. **Repeat on the other range.** The two ranges share the shunt but not the second gain stage,
   so they need separate constants. Expect them to differ by a few tenths of a percent.
7. **Record both constants** in the test record, and write them on the board or its label. A
   calibration nobody can find is a calibration nobody uses.

### How often

The gain constant is set by resistors and the isolator, none of which age quickly. Re-checking
annually is ample for lab use. The zero trim is the one that moves — with temperature, not with
time.

---

## Recording it

Use [`TEST_RECORD.xlsx`](TEST_RECORD.xlsx) — it has the bring-up checks, the trim result, gain
points across both ranges with automatic pass/fail against the published spec, and space for the
two calibration constants. One filled-in copy per board.
