# Shunt Amp DC Transfer — Bench Session Log (2026-09-06)

*Written 2026-09-06 08:10*

## Instruments

| Instrument | Model | Where |
|---|---|---|
| Function Generator | Digilent Analog Discovery 2 | SN:210321AD5D31 |
| Oscilloscope | Digilent Analog Discovery 2 | SN:210321AD5D31 |
| Power Supply | Digilent Analog Discovery positive supply | SN:210321AD5D31 |
| Power Supply | Digilent Analog Discovery negative supply | SN:210321AD5D31 |
| Electronic Load | MelansonTech MTECH-ELOAD | COM10 |
| Multimeter | Fluke 45 | COM13 |
| Function Generator | FeelTech FY3224S | COM5 |
| Oscilloscope | Rigol DS1104Z | USB0::6833::1230::DS1ZA195021923::0::INSTR |
| Power Supply | FNIRSI IPS3608 | COM12 |

*What was connected while this session ran.*

## Results

No procedure ran in this session, so there is nothing measured to report. Anything below is what was done, not what was found.

## Appendix — everything the bench was asked to do

Included because a conclusion that turns out wrong is only debuggable if what was actually done is recoverable — and what was done is not the same as what was said about it. Refusals are here too, for the same reason.

```
    done  Multimeter.reset_statistics() — reset_statistics pressed
    done  FNIRSI IPS3608 — Power Supply.set_voltage(value=4) — set_voltage -> 4
    done  FNIRSI IPS3608 — Power Supply.set_current_limit(value=6) — set_current_limit -> 6
    done  Electronic Load.set_range(value='HIGH — up to ~10 A') — set_range -> HIGH — up to ~10 A
    done  Electronic Load.set_setpoint(value=0.25) — set_setpoint -> 0.25
    done  FNIRSI IPS3608 — Power Supply.set_output_enabled(on=True) — set_output_enabled -> off
    done  FNIRSI IPS3608 — Power Supply.set_output_enabled(on=True) — set_output_enabled -> on
    done  Electronic Load.set_engaged(on=True) — set_engaged -> on
    done  Electronic Load.set_setpoint(value=0.25) — set_setpoint -> 0.25
    done  Electronic Load.set_engaged(on=False) — set_engaged -> off
    done  Electronic Load.set_setpoint(value=0.5) — set_setpoint -> 0.5
    done  Electronic Load.set_engaged(on=True) — set_engaged -> on
    done  Electronic Load.set_engaged(on=False) — set_engaged -> off
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_engaged(on=True) — set_engaged -> on
    done  FNIRSI IPS3608 — Power Supply.set_voltage(value=10) — set_voltage -> 10
    done  FNIRSI IPS3608 — Power Supply.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=1) — set_setpoint -> 1
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=2) — set_setpoint -> 2
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=3) — set_setpoint -> 3
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=4) — set_setpoint -> 4
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=4.5) — set_setpoint -> 4.5
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=5) — set_setpoint -> 5
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=0.25) — set_setpoint -> 0.25
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_engaged(on=False) — set_engaged -> off
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_engaged(on=True) — set_engaged -> on
    done  Electronic Load.set_engaged(on=False) — set_engaged -> off
    done  Multimeter.reset_statistics() — reset_statistics pressed
    done  Electronic Load.set_setpoint(value=0.5) — set_setpoint -> 0.5
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_engaged(on=True) — set_engaged -> on
    done  Electronic Load.set_setpoint(value=1) — set_setpoint -> 1
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=2) — set_setpoint -> 2
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=4) — set_setpoint -> 4
    done  Electronic Load.apply() — apply pressed
    done  FNIRSI IPS3608 — Power Supply.set_current_limit(value=8.2) — set_current_limit -> 8.2
    done  FNIRSI IPS3608 — Power Supply.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=6) — set_setpoint -> 6
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_setpoint(value=8) — set_setpoint -> 8
    done  Electronic Load.apply() — apply pressed
    done  Electronic Load.set_engaged(on=False) — set_engaged -> off
```
