# Building one

Everything here is derived from the Rev 2 fabrication outputs in
[`../Default Configuration/Outputs/`](../Default%20Configuration/Outputs/). Read
[`SAFETY.md`](SAFETY.md) before the board goes anywhere near an energised circuit.

## Ordering the bare board

| Parameter | Value | Source |
|---|---|---|
| Dimensions | **68.25 × 85.00 mm** | Outline layer |
| Layers | **4** — Top, Signal 1, Signal 2, Bottom | Gerber extension report |
| Minimum track width | **0.130 mm** (5.12 mil) | design rules |
| Minimum clearance | **0.200 mm** (7.87 mil) | design rules |
| Solder mask expansion | 4 mil | design rules |
| Drilled holes | **163** across 10 tools | drill report |
| Smallest drill | **0.3 mm** (133 of them — the via size) | drill report |
| Largest drill | 3.5 mm | drill report |
| Slots | **3**, 0.75 mm | drill report |

Every one of those is inside any standard 4-layer process, so this is a cheap board to have made.

**Not specified by the outputs, and you must choose:** finishing (ENIG is worth it for the fine-
pitch parts and the shunt pads), copper weight, board thickness, and solder mask and silkscreen
colour. The design does not depend on any of them — but see the note on copper weight below.

> **Confirm the isolation gap before ordering.** The design rules contain no clearance rule
> scoped to the barrier, so the only clearance the DRC enforced anywhere is 0.200 mm.
> [`SAFETY.md`](SAFETY.md) explains why this matters and what to check.

### Gerber and drill files

| Layer | File extension |
|---|---|
| Top copper | `.GTL` |
| Inner signal 1 | `.G1` |
| Inner signal 2 | `.G2` |
| Bottom copper | `.GBL` |
| Top / bottom solder mask | `.GTS` / `.GBS` |
| Top / bottom silkscreen | `.GTO` / `.GBO` |
| Top / bottom paste | `.GTP` / `.GBP` |
| Board outline | `.Outline` (Mechanical 1) |
| Drill | `.DRL` (Excellon), plus the plated round-hole and slot-hole ASCII files |
| Drill drawing / guide | `.GD1` / `.GG1` |

`.Assembly Top`/`.Bottom`, `.Courtyard *` and `.3D *` are documentation layers — do not send
them to the fab as copper.

> The output-job file that generates all of this is published as
> `Revision 2/MelansonTech Isolated Current Sense Rev 2.OutJob`. Revision 3 does not carry its
> own copy — its project references an OutJob one directory above the working folder — so if you
> are regenerating Revision 3's outputs, point it at the Revision 2 job file or supply your own.

## Assembly

**95 placements: 79 on the top side, 16 on the bottom.** It is a double-sided assembly — worth
knowing before you commit to a process, because it means two reflow passes or reflow-plus-hand
for the bottom side.

Bottom side includes `Rel1` (the G6L relay) and `D2` (its flyback diode), so the bottom is not
just passives.

A stencil is worth it: the Si8921 is a wide-body SOIC-8 and there are several SOT-23-5s. The
bill of materials in
[`../Default Configuration/Outputs/BOM/`](../Default%20Configuration/Outputs/BOM/) has
manufacturer part numbers and distributor references for every line.

### Three BOM lines you must resolve before ordering parts

These are placeholders in the generated BOM, and none of them is optional — see finding 13 in
[`DESIGN_REVIEW.md`](DESIGN_REVIEW.md):

| Ref | Fit | Why it matters |
|---|---|---|
| `C8` | **680 pF** | Sets the ×100 bandwidth |
| `C43` | **680 pF** | Sets the ×100 bandwidth |
| `R23` | **1 Ω** | Damps the input LC — without it the supply rail rings |

### And one BOM line that is wrong

| Ref | BOM says | **Fit** |
|---|---|---|
| `R28` | CT94EW103 — a 10 kΩ trimmer | **100 Ω** |

The schematic value is the correct one. A 10 kΩ trimmer resolves to about 5.7 % of full scale on
the ×100 range and cannot set zero usefully. Finding 4 in the design review has the arithmetic.

### Precision parts — do not substitute casually

Several resistors are specified far tighter than they look, and the accuracy spec depends on
them:

| Refs | Spec | Role |
|---|---|---|
| `R2`, `R9` | 8.2 kΩ **±0.05 %, ±10 ppm/°C** | Difference amplifier input ratio |
| `R3`, `R20` | 10 kΩ ±0.1 %, ±25 ppm/°C | Difference amplifier feedback |
| `R7`, `R10`, `R11`, `R14`, `R16`, `R18` | 470 Ω ±0.1 %, ±25 ppm/°C | ×10 second stage |
| `R17`, `R22`, `R26`, `R29` | 100 kΩ ±0.1 %, ±25 ppm/°C | The two 6 V reference dividers |
| `R5` | 10 mΩ **3 W, ±0.5 %, ±50 ppm/°C, 4-terminal** | The shunt |

Fitting 1 % parts anywhere in that table will not stop the board working — it will quietly cost
you the specification.

`R5` deserves particular care: it is a **4-terminal Kelvin device**, and the benefit only exists
if the sense pads are soldered separately from the current pads. It also carries 10 A and
dissipates 1 W at full current, so give it whatever copper the layout provides and consider
heavier copper if you are ordering the board anyway.

## First power-on

Do this with **`J2` disconnected** and an isolated 15 V supply.

1. **Inspect before applying power.** Check `J2`, `J4` and `J1` for solder bridges, and check the
   Si8921 and DC-DC module orientation.
2. **Current-limit the supply** to about 200 mA for the first application. Expected draw is
   roughly 90–100 mA at 15 V.
3. **`SW1` to position 1 (Off).** Confirm the board draws nothing.
4. **`SW1` to position 2 (10 A range).** Check:
   - **`D5` lights, `D4` stays dark.** Exactly one LED lit is the correct state.
   - Supply current settles around 90–100 mA.
   - Nothing gets hot fast. `U6` will become warm within a minute — that is expected, it
     dissipates about 0.6 W.
5. **Check the rails** against the table below.
6. **`SW1` to position 3 (5 A range).** Check:
   - **`D4` lights, `D5` goes dark.**
   - You can hear or feel `Rel1` operate.
7. **Check the output sits near zero** — `IsenseOut` to `ISenseRTN`, before trimming, should be
   within a few tens of millivolts. A volt or more means something is wrong; a few hundred
   millivolts means it just needs trimming.
8. **Warm up 30 minutes, then run the zero trim** — [`CALIBRATION.md`](CALIBRATION.md).

### Rail check

| Rail | Expected | Where it comes from |
|---|---|---|
| `VregIn` | ≈ 14.6 V from a 15.0 V supply | after the choke, `L1` and a Schottky drop |
| `+12` | 12 V ±4 % | `U1`, UA78L12 |
| `+5` | 5 V | `U6`, HT7550-1 |
| `+5_ISO` | 5 V, isolated side | `PSU1`, NXJ1S0505 |
| `ISenseRTN` | ≈ 6 V above board 0 V | `U5` buffering the `R22`/`R17` divider |
| `DiffAmpRef` | ≈ 6 V, adjustable by `R28` | `U9` buffering the `R26`/`R29` divider |

> **`+12` is the one to watch.** `U1` needs roughly 14.5 V in to regulate, and `VregIn` is only
> about 14.6 V from a nominal 15 V supply. If your supply reads low, or you see `+12` sagging
> below about 11.5 V, the regulator is in dropout — the reference and full scale move with it.
> Feed the board from a supply you have actually measured. Finding 2 in the design review covers
> this in detail.

Record the results in [`TEST_RECORD.xlsx`](TEST_RECORD.xlsx).

## Enclosure

STL and STEP models for the board, two enclosure panels and bumpers are in
[`../3d Models/`](../3d%20Models/).

These were drawn for mechanical fit and have not been characterised as a safety enclosure. No
print settings, material recommendation or assembly order is documented yet — if you print a set
and find something that works, a pull request adding it would be genuinely useful.

If the input side will run above touch-safe voltages, do not rely on these panels — see
[`SAFETY.md`](SAFETY.md).
