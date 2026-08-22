# Supply interface — FNIRSI IPS3608

Software control of the auxiliary supply feeding the Isolated Shunt Amplifier, so a
measurement can be swept across the supply range instead of taken at one voltage with the
knob turned by hand.

The board is specified for **13–15 V**, but its +12 V rail only regulates above about
**14.9 V**, and above **15.6 V** `Rel1`'s coil is over its rating. Between those two numbers
sits the only part of the operating range where every published accuracy figure holds. This
tool steps the supply through that range, waits for each point to settle, and records what
the supply was actually delivering at each one.

```
tools/psu-sweep --simulate sweep --step 0.1        # rehearse, no hardware
tools/psu-sweep ports                              # find the unit
tools/psu-sweep --port /dev/ttyUSB0 probe          # does something answer?
tools/psu-sweep --port /dev/ttyUSB0 --profile bench verify   # is the register map right?
tools/psu-sweep --port /dev/ttyUSB0 sweep -o run.csv         # the real thing
```

Only `pip install pyserial` is needed, and only for real hardware.

---

## On your own machine

The supply is on a USB port, so this has to run where the port is. Nothing here needs a
particular editor, but the repository carries a VS Code configuration for it.

```bash
git clone https://github.com/MelansonTech/Melanson-Tech-Isolated-Shunt-Amplifier.git
cd Melanson-Tech-Isolated-Shunt-Amplifier
git checkout claude/psu-scope-sweep-interface-v6wx93
python3 -m pip install -r tools/requirements.txt      # pyserial, for hardware only
code .
```

On Windows the launcher needs an interpreter in front of it — `python tools\psu-sweep …` —
or run `python -m psu_sweep …` from inside `tools/`. Everything else is identical.

Accept the recommended extensions when VS Code offers them, then:

| | |
|---|---|
| **F5** | four run configurations — simulated sweep, probe a port, verify the register map, sweep the bench supply. The last three prompt for the port and baud rate |
| **Ctrl/Cmd-Shift-P → Run Task** | *Tests*, *List serial ports*, *Sweep (simulated)*, *Install pyserial* |
| **Test explorer** | all 51 tests, discovered automatically. Breakpoints work in them |

The debug configurations run the package as a module with `tools/` on the path, so breakpoints
land in the driver and the simulator as well as in your own code.

### Finding the port

`tools/psu-sweep ports` — or the *List serial ports* task — ranks the candidates. The IPS3608
presents as a generic USB-serial bridge with no distinguishing identity, so the list cannot
identify it; `probe` is the test that answers.

| | |
|---|---|
| **Linux** | `/dev/ttyUSB0` typically. `Permission denied` means you are not in the `dialout` group: `sudo usermod -aG dialout $USER`, then log out and back in |
| **macOS** | `/dev/tty.usbserial-…` or `/dev/tty.wchusbserial…`. A CH340 driver may be needed |
| **Windows** | `COM3`, `COM4` … as shown in Device Manager |

The unit ships at **9600 baud**; if it has been changed, the System menu on the front panel
says which. Close the vendor PC software before connecting — it holds the port open.

---

## Read this before connecting the board

**The supply's negative output must be floating.** `ISenseRTN` — the output return, on the
SMA shell — is bonded to chassis, and the board's 0 V rail floats about 6 V below it. A supply
whose negative terminal is strapped to its earth post shorts the reference buffer to earth:
the measurement collapses and the part overheats, with nothing visible from the outside.
Confirm continuity is **open** between the supply's negative output and its earth pin before
the first run. See [`docs/SAFETY.md`](../../docs/SAFETY.md).

The CLI asks once, on each real connection, and takes `--yes` to skip.

Two limits are enforced in software, before any frame is written:

| | |
|---|---|
| **13.0–15.6 V** | the board's envelope. 15.6 V is Rel1's coil at 130 % of rating |
| **100 mA default CC limit** | the board draws about 20 mA; a mis-wire trips CC instead of cooking something |

A setpoint outside the envelope is **refused, never clamped** — a silently clamped sweep
produces data that looks fine and is wrong. `--profile bench` lifts the envelope to the
supply's own 36 V / 8 A for work with nothing connected.

## The sweep

Each point sets the voltage, holds for `--dwell`, then waits until the supply's own readback
agrees with the setpoint to within `--settle-tolerance` before anything is measured — so a row
can never be the previous point measured while the rail was still moving. A point that never
gets there is recorded with `settled=no` rather than quietly averaged in.

```
tools/psu-sweep --port /dev/ttyUSB0 sweep \
    --start 13.0 --stop 15.6 --step 0.1 \
    --dwell 0.5 --samples 5 \
    --bidirectional \
    -o rev3-supply-sweep.csv
```

`--bidirectional` retraces downwards. The 14.9 V knee is a regulator dropping in and out, and
there is no reason for it to sit at the same voltage in both directions — measuring that is
most of the point.

The CSV carries the run's parameters as leading `#` comments: the command line, the envelope,
the plan, and whether the data is simulated. This is deliberate.
`Revision 1/TestData/BodePlots/` in this repository is 31 real sweeps that nobody can now
attribute to specific nodes, because the files have no header and the bench notes are gone.

| column | |
|---|---|
| `requested_v` | what the sweep asked for |
| `set_v` | what the supply reports as its setpoint — a disagreement means a clamp or a lost write |
| `measured_v`, `measured_a`, `measured_w` | mean across `--samples` readings |
| `v_spread`, `a_spread` | peak-to-peak across those samples |
| `settle_s`, `settled` | how long the point took, and whether it got there |
| `mode` | `CV` or `CC` — anything but `CV` on this board means something is wrong |
| `note` | `+12 V rail unregulated` below 14.9 V, `above 15 V nominal` past nominal |

## Adding an instrument at each point

Capturing from a scope, a DMM or anything else is a callback, not a feature of this module.
`run()` takes a `hook` that is called once per point after settling, and whatever dict it
returns becomes extra CSV columns:

```python
from psu_sweep.profiles import SHUNT_AMP_AUX, annotate, default_points
from psu_sweep.supply import connect_serial
from psu_sweep.sweep import SweepPlan, run, write_csv

def capture(point, psu):
    scope.single()                                  # your instrument, your driver
    return {"isense_mv": scope.measure("MEAN") * 1000}

with connect_serial("/dev/ttyUSB0", SHUNT_AMP_AUX) as psu:
    rows = run(psu, SweepPlan(points=default_points(), current_limit=0.1,
                              note_for=annotate), hook=capture)
write_csv(rows, "sweep.csv")
```

Nothing in the sweep engine knows what a scope is, so the instrument side can be built and
changed without touching any of this.

## Is the register map right?

FNIRSI publishes no protocol document. The framing here — `[0xF1][cmd][reg][len][data][sum]`,
little-endian floats, checksum over everything but the command byte — is consistent across
every source and is confirmed by the one worked example in the community notes (setting 5.0 V
produces `f1 b0 c0 04 00 00 a0 40 a4`, which this code reproduces exactly, and which the test
suite asserts).

Three details are **not** consistent between sources, and are marked `UNVERIFIED` in
[`protocol.py`](protocol.py): which register holds the current setpoint, where the
output-enabled flag sits in the state dump and which way round it reads, and the layout of the
0xC3 live-values frame. None of them can be settled without hardware.

`verify` settles them, with the board disconnected:

```
tools/psu-sweep --port /dev/ttyUSB0 --profile bench verify
```

It writes a distinctive setpoint and reads it back, toggles the output and watches which byte
of the state dump moves and in which direction, and asks you to confirm the current limit
against the front panel — the one item a readback cannot prove on its own. It prints what it
observed against what the map claims. If something disagrees, the fix is a constant in
`protocol.py`; the sweep engine above it does not care.

Run it once per unit and firmware, before a long sweep.

## Layout

| | |
|---|---|
| `protocol.py` | framing, register map, state decoding. Pure functions over bytes |
| `transport.py` | serial port, and a loopback to the simulator |
| `simulator.py` | a model IPS3608 speaking the real framing — what the tests run against |
| `supply.py` | the `PowerSupply` interface, the limit envelope, and the IPS3608 driver |
| `profiles.py` | this board's numbers, traceable to README.md and DESIGN_REVIEW.md |
| `sweep.py` | the sweep engine and CSV writer |
| `verify.py` | register-map confirmation against real hardware |
| `cli.py` | the command line |

```
PYTHONPATH=tools python3 -m unittest discover -s tools/psu_sweep/tests -t tools
```

51 tests, no hardware, no dependencies.

## Troubleshooting

| | |
|---|---|
| `no reply from … within 2.0 s` | wrong port, or the baud does not match the unit's System menu — it ships at **9600**. Close the vendor PC software; it holds the port |
| `undecoded regs 0x…` from `probe` | the firmware answers with registers this map does not know. Run `verify` |
| `voltage setpoint did not take` | frames are reaching the unit but not landing — check the baud rate first |
| points marked `UNSETTLED` | the supply never reached the setpoint. Usually the CC limit is too low, or `--settle-tolerance` is tighter than the supply's own regulation |
| `supply is in OVP …` | the unit's own protection fired; clear it at the front panel |

## Other supplies

`PowerSupply` in `supply.py` is the whole contract — set a voltage, set a current limit, switch
the output, read back. A different FNIRSI model, a SCPI bench supply or a fresh simulator can
be swept by implementing those four methods; the sweep engine, the CSV writer, the limit
envelope and the CLI are all model-agnostic.
