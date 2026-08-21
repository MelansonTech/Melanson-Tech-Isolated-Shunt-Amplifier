# Changelog

## Rev 2 — current

The project file is `MelansonTech Isolated Current Sense Rev 2.PrjPcb`. Read out of the project
files themselves, Rev 2 consists of:

| | Rev 2 | Rev 1 |
|---|---|---|
| Amplifier sheet | `MelansonTech Isolated Shunt Amplifier rev 2 alt shunt.SchDoc` | `MelansonTech Isolated Shunt Amplifier rev 2.SchDoc` |
| PSU sheet | `MelansonTech PSU_IsolatedShuntAmp Rev2.SchDoc` | `MelansonTech PSU_IsolatedShuntAmp.SchDoc` |
| PCB layout | `MelansonTech Isolated Shunt Amplifier.CSPcbDoc` | *same file* |

So Rev 2 changed both schematic sheets — the amplifier sheet to an "alt shunt" variant, and the
PSU sheet to a Rev 2 version. **Both revisions point at the same PCB file**, which means Rev 1's
project no longer opens the board it was originally drawn against.

> **What actually changed electrically is not documented anywhere, and this file is a
> placeholder for it.** The schematic documents are binary CircuitStudio files, so the change
> cannot be recovered by diffing them, and the Rev 1 BOM
> (`BOM_PartType-MelansonTech Isolated Current Sense.xls`) is referenced by the Rev 1 project but
> is not present in the repository. Only the designer can fill this in.
>
> Worth capturing, when someone gets to it:
> - what the "alt shunt" variant changed, and why
> - what changed on the PSU sheet between the two versions
> - whether the Rev 1 layout still exists anywhere, or whether Rev 2 reused it deliberately
> - what prompted the revision

### Known open items in Rev 2

Full detail in [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md). Summarised, in the order worth fixing:

| # | Item | Severity |
|---|---|---|
| 1 | The isolated-auxiliary-supply requirement is not on the board or the enclosure, only in the documentation | high (documentation) |
| 4 | `R28` BOM line specifies 10 kΩ where the board needs the schematic's 100 Ω | high (BOM error) |
| 13 | `C8`, `C43` and `R23` are generic placeholder BOM lines with no value or part number | low (documentation) |
| 6 | Published common-mode figure was 500 Vdc against a 400 V connector rating — now corrected to 400 Vdc | medium |
| 2 | `U1` sits ~100 mV above its dropout threshold on a 15 V supply | high |
| 5 | `U6` dissipates ~0.6 W in a SOT-89 | medium |
| — | No clearance rule scoped to the isolation barrier; the only board clearance rule is 0.200 mm | see [`SAFETY.md`](SAFETY.md) |
| 8 | The ×100 bandwidth figure is not obviously set by any RC in the schematic | medium (verify) |
| 12 | `SW1` may be carrying the whole board supply at ~100 % of its rated current | low/medium (verify) |
| 3 | `R21` at 10 kΩ leaves a source-impedance asymmetry between the two reference buffers; 100 Ω would fix it | medium |

Nothing in that list stops the board working. Items 1, 4 and 13 cost nothing to fix and should
go into the next revision regardless.

### Documentation added, August 2026

The design files were unchanged; this was a documentation pass on the existing Rev 2 hardware.

- **Corrected specifications throughout.** The earlier project description carried a "2 V to 9 V
  input voltage range" that corresponds to nothing on the board, a ±6 V output, and named the
  Si8920 where the Si8921 is fitted. Ranges are 10 A (×10, 1.0 V full scale) and 5 A (×100, 5.0 V
  full scale).
- **A published accuracy specification** in instrument form, on a stated statistical basis:
  ±(1.0 % of reading + 12 mA) on the 10 A range and ±(0.9 % + 8 mA) on the 5 A range, at
  23 °C ± 5 °C after the zero trim.
- **[`DESIGN_REVIEW.md`](DESIGN_REVIEW.md)** — 14 findings from the schematic set, BOM and
  LTspice model, with a full tolerance stack-up.
- **[`Tolerance Budget - Isolated Shunt Amplifier Rev 2.xlsx`](Tolerance%20Budget%20-%20Isolated%20Shunt%20Amplifier%20Rev%202.xlsx)**
  — the live model behind those numbers, with every datasheet figure as an editable input.
- **[`tolerance_monte_carlo.py`](tolerance_monte_carlo.py)** and
  **[`plot_drift.py`](plot_drift.py)** — reproduce the statistics and the drift plot.
- **[`SAFETY.md`](SAFETY.md)**, **[`CALIBRATION.md`](CALIBRATION.md)**,
  **[`ASSEMBLY.md`](ASSEMBLY.md)**, **[`CONNECTORS.md`](CONNECTORS.md)** — the
  build-and-use documentation, which did not previously exist.
- **[`TEST_RECORD.xlsx`](TEST_RECORD.xlsx)** — a per-board record for capturing the nominal data
  that all of the above still lacks.
- **Licensed CERN-OHL-S v2**, and the repository reorganised — superseded files moved to
  `archive/`, documentation into `docs/`.

Every performance figure in this documentation is **derived from schematics and datasheets, not
measured**. Filling in a `TEST_RECORD.xlsx` for a real board is the outstanding work.

## Rev 1

Project file `MelansonTech Isolated Current Sense.PrjPcb`. Retained for history. Its BOM output
is referenced by the project but absent from the repository, and it shares Rev 2's PCB file.

## Earlier

The parent directory of this repository contains an `SI8920 JLC Order 27-Mar-2022` folder,
suggesting an earlier build around the Si8920 rather than the Si8921 now fitted. Not captured
here.
