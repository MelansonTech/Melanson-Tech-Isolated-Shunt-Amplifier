# Connectors and controls

Quick reference for everything on the outside of the board. Values are from the Rev 2 schematic
and bill of materials; see [`SAFETY.md`](SAFETY.md) before connecting anything to `J2`.

## Connectors

| Ref | Part | What it is | Pins |
|---|---|---|---|
| **J2** | Phoenix Contact 5442002 | **Current input.** 2-position, 5.08 mm pitch, rated 12 A / 400 V. The measured current flows *through* this connector and the shunt. | **1** — shunt low side · **2** — shunt high side, and the local `GND_ISO` reference |
| **J1** | Cinch 142-0701-801 | **Signal output.** 50 Ω SMA jack, edge launch. | **centre** — `IsenseOut` · **shell** — `ISenseRTN`, bonded to chassis |
| **J4** | PJ-002A | **Auxiliary supply, 13–15 V** (15 V nominal). 2.1 mm ID / 5.5 mm OD barrel jack, right angle. | **centre — positive** · sleeve — board 0 V |

Five things about these that are not obvious:

- **`J2` carries the full measured current.** It is not a sense connection. Torque the screws
  properly and use wire rated for the current — at 10 A a loose terminal is the hottest thing on
  the board.
- **The `J1` shell is not ground.** It is `ISenseRTN`, the chassis-bonded 6 V reference. That is
  the intended arrangement, not a fault — see the README.
- **`J4` must be fed from an isolated supply.** The board's 0 V floats ~6 V below chassis. A
  supply with its negative bonded to earth shorts the reference buffer. This is the single most
  common way to get a wrong reading; the README carries the full explanation.
- **Use 15 V if you want the full specification.** The board runs across 13–15 V, but the +12 V
  rail only regulates above about 14.9 V. Below that it sags and output headroom on the 5 A range
  shrinks — 0.32 V of margin at 13 V against 0.85 V at 15 V. Accuracy is unaffected; headroom is.
- **Never exceed 15.6 V.** `Rel1`'s coil is driven directly from the input and that is 130 % of
  its 12 V rating.

## Controls

| Ref | Part | Function |
|---|---|---|
| **SW1** | C&K OS103011MS8QP1, SP3T slide | Range select **and** power switch |
| **R28** | CT94EW103 footprint, **fit 100 Ω** — top adjust | Zero trim. See [`CALIBRATION.md`](CALIBRATION.md) |

### SW1 positions

| Position | Legend | Gain | Max current | Full-scale output | Scale factor |
|---|---|---|---|---|---|
| 1 | Off | — | — | — | board unpowered |
| 2 | 1V/10A | ×10 | **10 A** | 1.0 V | 1 V per 10 A → **100 mV/A** |
| 3 | 1V/1A | ×100 | **5 A** | 5.0 V | 1 V per 1 A → **1 V/A** |

The legends are scale factors, not range limits. Position 3 is the *finer* range over a smaller
span — it stops at 5 A because that is where the 5 V output ceiling is reached
(5 V ÷ 100 ÷ 10 mΩ = 5 A), not because of anything in the input path.

> **Rev 3.1 legends the switch by gain instead — `Off / x10 / x50`.** The `x50` is a silkscreen
> typo: **that position is ×100**, which is what the LED beside it says and what the schematic
> does. There is no ×50 range. Finding 15 in [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md) tracks it
> along with three other Rev 3.1 silkscreen figures that disagree with the schematic.

`SW1` also switches the board's supply, so position 1 genuinely removes power rather than just
muting the output.

> **Note for a future revision:** the switch is a C&K OS103011MS8QP1 rated 100 mA / 12 V, and it
> appears to carry the entire board supply (~90–100 mA at 15 V) as well as selecting the range.
> Confirm against the netlist — see finding 12 in [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md).

## Indicators

| Ref | Part | Meaning |
|---|---|---|
| **D4** | OVLBB4C7, blue 3 mm | Lit on the **5 A range** (×100, switch position 3) |
| **D5** | OVLBB4C7, blue 3 mm | Lit on the **10 A range** (×10, switch position 2) |

Exactly one is lit whenever the board is powered — they are driven complementarily by `Q2` and
`Q4`, so both dark means no supply and both lit means a fault. Each runs at roughly 0.9 mA
through a 10 kΩ resistor, which is visible indoors but not bright; if you want them brighter on a
future revision, drop `R27`/`R19` to about 3.3 kΩ.

## Output loading

The output source impedance is `R4 ∥ R8` = **50 Ω**.

| Load | Effect |
|---|---|
| 1 MΩ (scope, DAQ, DMM) | correct reading — this is the intended load |
| 50 Ω terminated | **reads half** — the source and load divide evenly |
| < 10 kΩ | reads low by more than 0.5 %; avoid |

Measure `IsenseOut` **relative to `ISenseRTN`**, not to your instrument's chassis, unless the SMA
shell is your only ground reference — which it is when the auxiliary supply is properly isolated.

## Board

| | |
|---|---|
| Dimensions | 68.25 × 85.00 mm |
| Layers | 4 (Top, Signal 1, Signal 2, Bottom) |
| Placements | 95 — 79 top side, 16 bottom side |
| Drilled holes | 163 across 10 tools, 0.3 mm to 3.5 mm, including 3 slots |
