# Building one

Everything here is derived from the fabrication outputs in
[`Revision 3/Default Configuration/Outputs/`](../Revision%203/Default%20Configuration/Outputs/). Read
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

> Each revision publishes the output-job file that generates all of this:
> `Revision 2/MelansonTech Isolated Current Sense Rev 2.OutJob` and
> `Revision 3/MelansonTech Isolated Current Sense Rev 3.OutJob`. As of August 2026 the Revision 3
> project carries its own copy and references nothing outside its folder, so its outputs can be
> regenerated from a clean checkout.

## Assembly

**95 placements: 79 on the top side, 16 on the bottom.** It is a double-sided assembly — worth
knowing before you commit to a process, because it means two reflow passes or reflow-plus-hand
for the bottom side.

Bottom side includes `Rel1` (the G6L relay) and `D2` (its flyback diode), so the bottom is not
just passives.

A stencil is worth it: the Si8921 is a wide-body SOIC-8 and there are several SOT-23-5s. The
bill of materials in
[`Revision 3/Default Configuration/Outputs/BOM/`](../Revision%203/Default%20Configuration/Outputs/BOM/) has
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

Do this with **`J2` disconnected** and an isolated supply set to **15 V** — the top of the
13–15 V range, where the +12 rail regulates.

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
| `VregIn` | ≈ Vin − 0.37 V (14.63 V from 15.0 V) | after the choke, `L1` and a Schottky drop |
| `+12` | 12 V ±4 % | `U1`, UA78L12 |
| `+5` | 5 V | `U6`, HT7550-1 |
| `+5_ISO` | 5 V, isolated side | `PSU1`, NXJ1S0505 |
| `ISenseRTN` | ≈ 6 V above board 0 V | `U5` buffering the `R22`/`R17` divider |
| `DiffAmpRef` | ≈ 6 V, adjustable by `R28` | `U9` buffering the `R26`/`R29` divider |

> **`+12` is the one to watch, and it depends on your supply.** `U1` needs 14.5 V in to regulate,
> and there is a 0.37 V drop ahead of it, so the rail only holds 12 V above about **14.9 V at the
> jack**. Below that it follows the input down — at 13 V in, expect roughly **10.9 V**, not 12 V.
>
> That is not a fault: both 6 V references derive from the same rail and track together, so zero
> and gain are preserved. What shrinks is output headroom on the 5 A range. But it does mean a
> `+12` reading of 10.9 V is *correct* for a 13 V supply and a *fault* for a 15 V one — so measure
> your supply at the jack before judging the rail. Finding 2 has the full table.

Record the results in [`TEST_RECORD.xlsx`](TEST_RECORD.xlsx).

## Enclosure

The board is built for a **generic 50 × 58 × 24 mm split extruded-aluminium PCB case** — the
kind sold under a dozen white-label names with no manufacturer part number worth quoting. Its
stock end plates are replaced by the two printed panels in
[`Revision 3/3d Models/`](../Revision%203/3d%20Models/), which carry the cutouts for this board's connectors.

| | |
|---|---|
| Case | Split extruded aluminium, two half-shells with internal PCB rails |
| Outside | **50 × 58 × 24 mm** (1.97 × 2.28 × 0.94 in) — 50 mm along the rails |
| Board | 50.00 × 49.995 mm, slides into the rails; connectors protrude through the end panels |
| End plates | Stock plates **discarded**; print `Enclosure Panel A.stl` and `Enclosure Panel B.stl` |
| Panel size | 58.000 × 24.000 × 1.646 mm each, measured from the meshes |
| Panel fixings | 2 × Ø2.75 mm holes on **52.00 mm centres**, at mid-height (Y = 12.00 mm) |
| Screws | M2.5 self-tapping, into the shell's corner bosses |
| Sleeve | `Shunt Amp BumperV2.stl`, 62 × 28 × 12 mm — slips over the assembled case |

**Search on the dimensions, not on a brand.** No two sellers call this case the same thing, and
the listings come and go; `50x58x24` or `1.97 x 2.28 x 0.94 inch` finds it where a part number
will not.

### Where to buy

| Source | Reference | Note |
|---|---|---|
| AliExpress | [a.aliexpress.com/_mNXWsaf](https://a.aliexpress.com/_mNXWsaf) | **Used for the Rev 3.1 build**, ~US$6 |
| AliExpress | item `4000939266131`, seller part `XDM05-40` | ~US$5.85 each in a 2-pack |
| AliExpress | [a.aliexpress.com/_mMyxcPp](https://a.aliexpress.com/_mMyxcPp) | |
| eBay | item `276716687470` | US$4.39 + US$15 shipping |
| Amazon.com | `B0DLBNYR1Y`, `B014RSCFZI` | ~US$8–12, also listed on Amazon.ca |
| Amazon.co.uk | `B0DM18PJG3`, `B0DLB95WVW` | |
| JLCMC | aluminium box catalogue | 58 × 24 section and 50 mm length both appear in the filters, but **no matching split product page was found** — confirm on their quote page before relying on it |

Prices are **indicative, September 2026**.

**Hammond 1455 and Polycase EX are not substitutes.** Neither offers a 58 × 24 mm section or a
50 mm length, so the panels below will not fit them and the board will not meet the rails.

### Panel A — output end

`Enclosure Panel A.stl`, 58.000 × 24.000 × 1.646 mm. Centres are from the panel's bottom-left
corner, measured at mid-thickness.

| Cutout | Size (mm) | Centre (mm) | Part |
|---|---|---|---|
| Round | Ø2.75 | (3.00, 12.00) | Fixing screw |
| Round | Ø6.50 | (14.00, 8.75) | **J1** SMA jack |
| Round | Ø3.15 | (24.95, 18.00) | **D5** — 10 A range LED |
| Slot | 9.00 × 2.50 | (28.95, 10.90) | **SW1** slide switch |
| Round | Ø3.15 | (32.95, 18.00) | **D4** — 5 A range LED |
| Rectangle | 9.41 × 11.41 | (43.00, 13.85) | **J4** barrel jack |
| Round | Ø2.75 | (55.00, 12.00) | Fixing screw |

### Panel B — input end

`Enclosure Panel B.stl`, 58.000 × 24.000 × 1.646 mm.

| Cutout | Size (mm) | Centre (mm) | Part |
|---|---|---|---|
| Round | Ø2.75 | (3.00, 12.00) | Fixing screw |
| Rectangle | 12.50 × 9.50 | (29.00, 12.50) | **J2** terminal block, 5.08 mm pitch |
| Round | Ø2.75 | (55.00, 12.00) | Fixing screw |

Part assignments are read from the Rev 3 pick-and-place, not inferred: J1, SW1, D5, D4 and J2 all
land within 0.05 mm of their cutouts under a single constant offset, which is what makes the
mapping a check rather than a guess.

### The shell is bonded to `ISenseRTN`, not to earth

`J1`'s SMA nut clamps the shell to the connector body, so **the aluminium becomes `ISenseRTN`** —
the chassis-bonded 6 V reference, not ground. Everything
[`SAFETY.md`](SAFETY.md) says about not treating that shell as earth applies to the whole case
once it is assembled.

**Do not assume the halves and end plates are electrically continuous.** These shells are
anodised, and anodising is an insulator: two halves screwed together can read open. If the
enclosure is to be bonded deliberately, scrape the anodising at the screw bosses and verify
continuity with a meter rather than trusting the joint.

### What is still missing

These panels were drawn for mechanical fit and have **not** been characterised as a safety
enclosure. No print settings, material recommendation or assembly order is documented yet — if
you print a set and find something that works, a pull request adding it would be genuinely
useful.

If the input side will run above touch-safe voltages, do not rely on these panels — see
[`SAFETY.md`](SAFETY.md).
