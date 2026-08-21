"""
Confirm the register map against a real unit.

`protocol.py` is assembled from community reverse-engineering, and three of its
details disagree between sources: the current-setpoint register, the offset and
polarity of the output-enabled flag, and the layout of the 0xC3 live-values
frame. Everything in this package is built so that being wrong about them is
recoverable — but you want to *know*, once, before a long sweep.

This walks a connected supply through each doubtful item and reports what it
observed. Run it with the board disconnected: it writes setpoints and toggles
the output.

    python3 -m psu_sweep --port /dev/ttyUSB0 --profile bench verify
"""
from __future__ import annotations

import struct
import sys
import time
from typing import List, Optional, Tuple

from . import protocol as pr

PASS, FAIL, CHECK = "pass", "FAIL", "check"


def verify(psu, *, interactive: bool = True) -> int:
    """Returns 0 if nothing contradicted the map, 1 if something did."""
    results: List[Tuple[str, str, str]] = []

    print(__doc__.strip().split("\n\n")[0])
    print()
    if interactive and sys.stdin.isatty():
        print("This writes setpoints and toggles the output. Disconnect the board first.")
        if input("Nothing connected to the supply output? [y/N] ").strip().lower() not in ("y", "yes"):
            print("aborted")
            return 1
        print()

    state = psu.refresh()
    results.append(_framing(state))
    results.append(_voltage_setpoint(psu))
    results.append(_current_setpoint(psu, interactive))
    results.append(_output_flag(psu))
    results.append(_live_frame(psu))

    print()
    width = max(len(name) for name, _, _ in results)
    for name, verdict, detail in results:
        print(f"  [{verdict:^5}] {name:<{width}}  {detail}")

    failures = [r for r in results if r[1] == FAIL]
    checks = [r for r in results if r[1] == CHECK]
    print()
    if failures:
        print(f"{len(failures)} item(s) contradict protocol.py — correct the constants there "
              "before trusting a sweep.")
    elif checks:
        print(f"{len(checks)} item(s) could not be settled automatically — compare against the "
              "front panel yourself.")
    else:
        print("The register map matches this unit.")
    return 1 if failures else 0


def _framing(state: pr.DeviceState) -> Tuple[str, str, str]:
    if not state.last_all:
        return ("frame decode", FAIL, "no 0xFF state dump arrived — framing or baud is wrong")
    size = len(state.last_all)
    expected = max(off + (4 if kind == "f" else 1) for _, off, kind in pr.ALL_LAYOUT)
    if size < expected:
        return ("frame decode", FAIL,
                f"0xFF payload is {size} bytes, the layout table needs {expected}")
    plausible = 0.0 <= state.max_voltage <= 100.0 and 0.0 <= state.max_current <= 30.0
    return ("frame decode", PASS if plausible else FAIL,
            f"{size}-byte dump, device limits read as "
            f"{state.max_voltage:.2f} V / {state.max_current:.2f} A")


def _voltage_setpoint(psu) -> Tuple[str, str, str]:
    """0xC0 is the least doubtful register — this mostly proves the link works."""
    target = _inside(psu.limits, 0.37)
    restore = psu.state.set_voltage
    try:
        psu.set_voltage(target)
        time.sleep(0.2)
        got = psu.refresh().set_voltage
    finally:
        _quietly(psu.set_voltage, restore)
    ok = abs(got - target) <= 0.05
    return ("0xC0 voltage setpoint", PASS if ok else FAIL,
            f"wrote {target:.3f} V, read back {got:.3f} V")


def _current_setpoint(psu, interactive: bool) -> Tuple[str, str, str]:
    """
    0xDE is the doubtful one — it is cited both as the current setpoint and as
    a model-string register, so a readback alone cannot settle it. If the write
    lands somewhere else entirely, the readback may still echo the old value.
    """
    target = round(min(psu.limits.max_current, 8.0) * 0.41, 3)
    restore = psu.state.set_current
    try:
        psu.set_current(target)
        time.sleep(0.2)
        got = psu.refresh().set_current
        if abs(got - target) > 0.02:
            return ("0xDE current setpoint", FAIL,
                    f"wrote {target:.3f} A, supply reports {got:.3f} A — wrong register")
        if interactive and sys.stdin.isatty():
            answer = input(f"  Front panel current limit — does it read {target:.3f} A? [y/N] ")
            if answer.strip().lower() in ("y", "yes"):
                return ("0xDE current setpoint", PASS, f"panel confirms {target:.3f} A")
            return ("0xDE current setpoint", FAIL,
                    "readback agrees but the panel does not — 0xDE is not the CC limit here")
        return ("0xDE current setpoint", CHECK,
                f"readback agrees ({got:.3f} A); confirm against the panel")
    finally:
        _quietly(psu.set_current, restore)


def _output_flag(psu) -> Tuple[str, str, str]:
    """
    Toggle the output and watch byte 107 of the 0xFF dump. This settles both
    the offset and the polarity without asking anyone anything: whichever byte
    changes with the output is the flag.
    """
    before = psu.refresh().last_all
    psu.set_output(True)
    time.sleep(0.3)
    on = psu.refresh().last_all
    psu.set_output(False)
    time.sleep(0.3)
    off = psu.refresh().last_all

    if not (before and on and off):
        return ("0xFF output flag", FAIL, "no state dump to compare")

    changed = [i for i in range(min(len(on), len(off))) if on[i] != off[i]]
    offset = next((off_ for name, off_, _ in pr.ALL_LAYOUT if name == "_output_flag"), None)

    if offset in changed:
        active_low = on[offset] == 0
        matches = active_low == pr.OUTPUT_FLAG_ACTIVE_LOW
        return ("0xFF output flag", PASS if matches else FAIL,
                f"byte {offset} reads {on[offset]} on / {off[offset]} off — "
                f"active-{'low' if active_low else 'high'}, "
                f"map says active-{'low' if pr.OUTPUT_FLAG_ACTIVE_LOW else 'high'}")

    candidates = [i for i in changed if on[i] in (0, 1) and off[i] in (0, 1)]
    return ("0xFF output flag", FAIL,
            f"byte {offset} did not change; candidate flag bytes: "
            + (", ".join(str(i) for i in candidates[:8]) or "none"))


def _live_frame(psu) -> Tuple[str, str, str]:
    """
    Ask for 0xC3 directly and see whether the payload reads as
    (set V, measured V, measured A) or as (V, A, W). With the output off and a
    known setpoint the two are easy to tell apart: the first field should be
    the setpoint under one reading and a near-zero measurement under the other.
    """
    setpoint = _inside(psu.limits, 0.53)
    restore = psu.state.set_voltage
    try:
        psu.set_voltage(setpoint)
        time.sleep(0.2)
        psu.transport.write(pr.read(pr.Reg.LIVE))
        time.sleep(0.3)
        psu.refresh()
        payload = _last_live(psu)
    finally:
        _quietly(psu.set_voltage, restore)

    if payload is None or len(payload) < 12:
        return ("0xC3 live frame", CHECK, "no 0xC3 frame came back; the 0xFF dump is enough anyway")

    first, second, third = struct.unpack_from("<fff", payload, 0)
    if abs(first - setpoint) < 0.1 and setpoint > 0.5:
        return ("0xC3 live frame", PASS,
                f"[{first:.3f}, {second:.3f}, {third:.4f}] — first field is the setpoint, as mapped")
    return ("0xC3 live frame", FAIL,
            f"[{first:.3f}, {second:.3f}, {third:.4f}] with setpoint {setpoint:.3f} V — "
            "the mapped layout does not fit")


def _last_live(psu) -> Optional[bytes]:
    """The most recent 0xC3 payload, if one has arrived at all."""
    return psu.state.last_live or None


def _inside(limits, fraction: float) -> float:
    span = limits.max_voltage - limits.min_voltage
    return round(limits.min_voltage + span * fraction, 3)


def _quietly(fn, *args) -> None:
    try:
        fn(*args)
    except Exception:
        pass
