# Safety

This board is designed to sit across a shunt in a circuit that may be at a **high potential
relative to earth**. That is the whole point of it. Read this before connecting `J2` to anything
energised.

> **This document is written by the designer for people building and using the design. It is not
> a compliance assessment.** No third-party safety testing has been done, no standard has been
> certified against, and nothing here should be read as a claim of conformity to IEC 61010,
> IEC 60664, or any other standard. If you are putting this into a product, or using it anywhere
> that someone else's safety depends on it, get it assessed properly.

## What the isolation does and does not do

The Si8921 and the NXJ1S0505 isolated DC-DC form a barrier between the **input side** (the shunt,
`GND_ISO`, the `+5_ISO` rail) and the **output side** (the amplifier chain, the 15 V supply, the
SMA output, chassis).

**It does** let you measure a shunt sitting hundreds of volts above your instrument's ground
without that voltage appearing at the SMA output.

**It does not:**

- **Protect you from touching the input side.** `J2` and everything on the input side of the
  barrier sit at whatever potential the measured circuit is at. The barrier protects the *output
  side*, not your hands.
- **Provide reinforced or double insulation in the regulatory sense.** The 4.2 kV figures on the
  Si8921 and the DC-DC module are component withstand ratings from their datasheets. Whether the
  *assembly* achieves a given insulation class depends on PCB creepage and clearance, the
  enclosure, and pollution degree — none of which has been assessed here.
- **Survive a fault on the input side.** Nothing on this board limits fault current at `J2`. The
  measured circuit needs its own protection.

## Working voltage

**The published common-mode limit is 400 Vdc, and it is set by the input connector, not by the
isolator.** `J2` is a Phoenix Contact 5442002 rated 12 A / 400 V. The Si8921 and the DC-DC module
carry higher withstand numbers, but a barrier is only as good as its weakest element and the
connector is it.

Do not exceed 400 Vdc between the input side and the output side, and treat that as a limit with
no assessed margin.

## Two unresolved items

Both are flagged in [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md) and neither has been checked on the
physical board. They are stated here because they bear directly on safety.

### 1. There is no design rule enforcing the isolation gap

The exported rule set for the Rev 2 layout contains four rules, all board-scoped:

```
ShortCircuit          Scope=Board  Allowed=0
SolderMaskExpansion   Scope=Board  Minimum=4.00 mil
Width                 Scope=Board  Minimum=5.12 mil  (0.130 mm)
Clearance             Scope=Board  Minimum=7.87 mil  (0.200 mm)
```

There is **no clearance rule scoped to the isolation barrier**. The only clearance the DRC
enforces anywhere on this board is 0.200 mm — which is a normal signal clearance and is around an
order of magnitude below what a 400 Vdc working voltage would typically require for creepage.

This does not mean the gap is wrong. The barrier region may well be laid out with several
millimetres of clearance by hand, and the DRC would not complain either way. It means **nothing
is checking it**, so a future edit could close the gap silently.

**Before building or shipping this board:** measure the actual copper-to-copper and
copper-to-plane gap across the barrier on every layer, on both the top and inner layers, and
compare it against the creepage and clearance your application's standard requires for 400 Vdc at
your pollution degree and material group. Then add a clearance rule scoped to the barrier net
classes so it stays enforced.

### 2. The barrier region has not been reviewed

The design review that accompanies this project was **schematic-level only**. The PCB layout and
Gerbers were not examined, so nothing has verified:

- creepage and clearance across the barrier, including under the Si8921 and the DC-DC module
- whether any slot or cut-out reinforces the barrier
- whether inner-layer copper or planes cross the barrier
- clearance from the barrier to mounting holes and the enclosure

## Handling

- **Assume `J2` and the input side are live** whenever the measured circuit is energised —
  including after you switch `SW1` off. `SW1` removes the board's auxiliary supply; it does
  nothing to the input.
- **De-energise the measured circuit before connecting or disconnecting `J2`.** The terminal
  block is a screw terminal with exposed metal.
- **Do not probe the input side while it is at potential.** Your probe ground is almost certainly
  earthed; the input side is not.
- **The board is not enclosed by default.** The 3D-printed panels in [`../3d Models/`](../3d%20Models/)
  are the only barrier between a user and the input side, and they were designed for mechanical
  fit, not as a safety enclosure. If the input side will be above touch-safe voltages, put the
  board in a properly rated enclosure.
- **Mind the auxiliary supply.** It must be isolated (see the README). Beyond the accuracy
  consequence, a non-isolated supply ties the board's 0 V to earth, which is not what the rest of
  the design assumes.

## Thermal

Two parts run warm and are worth keeping fingers off, and worth giving airflow:

| Part | Dissipation | Note |
|---|---|---|
| `U6` HT7550-1, SOT-89 | ~0.55–0.6 W | Drops ~14.6 V to 5 V. See finding 5 in the design review — this is the hottest part on the board. |
| `R5` shunt, WSL3637 | 1.0 W at 10 A | ~33 °C rise above ambient at full current. Also the reason accuracy drifts with load. |

Neither is a hazard at room temperature, but both are hot enough to be unpleasant to touch and
`U6` is close enough to its limits that a still-air enclosure is worth checking.

## If you are building this into something

The honest summary: this is an open-source instrument front end that has been reviewed on paper
and not on a bench, with a stated 400 Vdc limit that rests on a connector rating and an
un-verified PCB gap. It is entirely suitable for lab and development work by someone who
understands the above. It is not ready to be dropped into a product without a proper layout
review, a creepage and clearance assessment, and testing against whatever standard applies to
you.
