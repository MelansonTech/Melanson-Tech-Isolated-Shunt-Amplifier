# Bench test data — 2026-09-05/06 campaign

Raw records behind [`../TEST_REPORT.md`](../TEST_REPORT.md). Published so every figure
in the report and the datasheet can be traced to the reading that produced it, and so
anyone repeating the work has the method as well as the answer.

Board under test: **Rev 3.1**. Bench: ScopeSweep.

## Start here

| File | What it holds |
|---|---|
| `shunt-amp-results-register.csv` | **The master record.** Every test point: condition, measured value, reference instrument, date, acceptance criterion, verdict, notes. If a number appears in the report, its row is here. |
| `shunt-amp-test-plan.md` | The plan the campaign followed — T1 through T8, with pass criteria set before measuring. |
| `shunt-amp-test-matrix.csv` | Test matrix: what was to be covered on each range. |

## Per-test records

| File | Covers |
|---|---|
| `shunt-amp-dc-transfer-report-2026-09-06.md` | DC transfer on both ranges, and the shared-COM burden error that had to be found first |
| `shunt-amp-rerun-2meter-2026-09-06.md` | Independent re-run with the meter roles exchanged, plus low-current detail |
| `shunt-amp-negative-current-2026-09-06.md` | Reverse-direction sweeps, both ranges |
| `shunt-amp-offset-drift.md` | Warm-up settling and the 2 h 23 min zero-drift soak |
| `shunt-amp-bandwidth-x100-2026-09-06.md` | ×100 frequency response, flatness, roll-off character |
| `shunt-amp-bandwidth-x10-2026-09-06.md` | ×10 frequency response, and the reference caveat on its corner |
| `shunt-amp-transient-noise-x100-2026-09-06.md` | Step response derivation and output noise spectra |

## Session records

| File | What it holds |
|---|---|
| `shunt-amp-bench-session-2026-09-06.md` / `.pdf` | Narrative log of the session as it happened |
| `shunt-amp-bench-session-2026-09-06-notes.csv` | Timestamped bench notes |
| `shunt-amp-bench-session-2026-09-06-instruments.csv` | Instruments as configured during the session |
| `shunt-amp-equipment.csv` | Equipment list with roles |
| `shunt-amp-test-record.csv` | Per-point test record |

## Reading these honestly

- **The electronic load is an actuator, never a reference.** Its current readback runs
  about 20 mA high against the Fluke meters. Every current figure is a meter reading.
- **Two isolated meters are mandatory on this board.** One meter reading both voltage
  and current ties `ISenseRTN` into the injection loop and corrupts the output by
  ~22 mV/A through its own shunt burden. This was found the hard way — see the DC
  transfer report.
- **Isolation, common-mode range and temperature coefficient were not measured** — no
  hipot tester, no 400 V source, no thermal chamber. Those specifications remain
  derived from the datasheets. §9 of the report says so explicitly.
- Historic Rev 1 Bode sweeps live separately, in `Revision 1/TestData/BodePlots/`.
