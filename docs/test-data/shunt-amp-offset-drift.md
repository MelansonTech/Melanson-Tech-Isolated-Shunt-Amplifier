# Isolated Shunt Amplifier — Output Offset Drift (×100 / 5 A range)

**DUT:** Melanson Tech Isolated Shunt Amplifier, ×100 range (1.0 V/A, full-scale 5 V), zero input current.
**Date:** 2026-09-05.
**Aux supply:** FNIRSI IPS3608 at 15.0 V; measured draw ~95 mA / ~1.43 W, CV (note: ~5× the README's "~300 mW").
**Output measured by:** Fluke 45 multimeter — DC voltage, high-Z input on the SMA output, fixed 0.1 V range, Slow conversion rate.
**Input current:** 0 A (all loop supplies off) — the reading is pure output offset.

## Warm-up settling (from aux power-up)

Measured by the Fluke 45. Elapsed times are approximate — see Limitations.

| Approx. elapsed | Output offset |
|---|---|
| ~0 min (cold, at aux enable) | +5.6 mV |
| ~2-3 min | +1.77 mV |
| ~5 min | +0.62 mV |
| ~6-7 min | -0.035 mV |
| ~7-8 min | -0.10 mV (+/-~0.01 mV, 4 consecutive reads) |

**Finding:** the offset settles monotonically from +5.6 mV to about -0.1 mV over ~7-8 min (total excursion ~5.7 mV), then keeps up a slow negative wander at the sub-mV level (reached -0.70 mV by the start of the multi-hour window). It stayed inside the +/-8 mV uncalibrated offset limit for this range at every point, including cold.

## Multi-hour monitoring

- **t0:** panel statistics reset 2026-09-05; baseline offset **-0.70 mV** (Fluke 45).
- Meter parked on fixed 0.1 V range, Slow rate; the Multimeter panel accumulates min / max / average across the window.
- **Envelope over the window (completed):** **855 samples over ~2 h 23 min at 10 s.** Settled band **min = -0.5 mV, max = +0.1 mV, peak-to-peak = 0.6 mV**. A running mean was not recorded separately, so none is quoted. The last ~13 samples are excluded -- they are the current-loop rewire, not the DUT.
- **Acceptance:** remain within the +/-8 mV uncalibrated offset limit for the ×100 range.
- **Result: PASS.** The settled band never reaches more than 0.5 mV from zero -- under 0.5 mA input-referred against an 8 mA fixed term, better than a factor of ten inside the limit.

## Limitations / not measured

- **No logged time axis and no autonomous sampling over hours.** ScopeSweep's Data Logger MCP surface is non-functional here (`sources: []` after refresh; `select_signal.signal` is typed *boolean* in the tool schema — it must be a *string* key). No scheduler/cron/wakeup tools are available in this session. So elapsed times above come from turn spacing, not a clock, and I cannot self-sample across the multi-hour window.
- The panel's min/max/average are **not returned over MCP** (the reading exposes only the instantaneous value). The final envelope must therefore be read off the Multimeter panel, or captured by a working Data Logger.
- Temperature-coefficient drift not measured (no chamber). The ×10 (10 A) range was not tested. Input-referred gain/transfer accuracy not yet measured (needs a controlled current source into the input with the Fluke moved into series as the current reference).

## How the final result gets captured (pick one)

1. **Fix the Data Logger** (string key on `select_signal`; `refresh_sources` populating), then it logs the full series in-app and I read/export it via MCP — the proper tool for an hours-long record.
2. **Read the panel's min/max/average** back at the end of the run and I fill the envelope above.
3. **Periodic point samples** whenever prompted, appended to a table here.
