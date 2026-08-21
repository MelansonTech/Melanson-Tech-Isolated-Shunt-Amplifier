"""
The sweep engine: step a supply through a list of voltages, settle, measure,
record.

It is deliberately generic — it drives anything satisfying `PowerSupply` and
knows nothing about the board under test beyond the note strings a profile
hands it. What makes it useful rather than a for-loop is the settling
behaviour: each point waits for the supply's own readback to agree with the
setpoint before any measurement is taken, so a row can never be a measurement
of the previous point taken while the rail was still moving.

Capturing from an instrument at each point is a callback, not a feature of
this module — see `SweepHook` below.
"""
from __future__ import annotations

import csv
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterator, List, Optional, Sequence

from .supply import PowerSupply, ProtectionTripped, SupplyError


def steps(start: float, stop: float, step: float, *, places: int = 4) -> List[float]:
    """
    Inclusive range over floats, without the accumulating error of repeated
    addition and without dropping the endpoint to a representation artefact —
    13.0 to 15.6 in 0.1 V steps must contain 15.6.
    """
    if step <= 0:
        raise ValueError("step must be positive")
    sign = 1.0 if stop >= start else -1.0
    span = abs(stop - start)
    count = int(math.floor(round(span / step, 6))) + 1
    points = [round(start + sign * i * step, places) for i in range(count)]
    if points and abs(points[-1] - stop) > 1e-9:
        points.append(round(stop, places))
    return points


@dataclass
class SweepPoint:
    """One row of the sweep."""

    index: int
    #: What the sweep asked for.
    requested_v: float
    #: What the supply reports as its own setpoint — should equal the above.
    set_v: float
    measured_v: float
    measured_a: float
    measured_w: float
    temperature_c: float
    mode: str
    protection: str
    settle_s: float
    settled: bool
    samples: int
    v_spread: float
    a_spread: float
    timestamp: str
    note: str = ""
    #: Whatever a hook returned for this point — merged into the CSV as extra
    #: columns when every point supplies the same keys.
    extra: dict = field(default_factory=dict)


@dataclass
class SweepPlan:
    """What to sweep and how patiently."""

    points: Sequence[float]
    current_limit: float
    #: Minimum time to hold each point before measuring.
    dwell: float = 0.5
    #: Give up waiting for the readback to reach the setpoint after this long.
    #: Settling is still recorded, and the point is flagged `settled=False`.
    settle_timeout: float = 5.0
    #: How close the readback must come to the setpoint to count as settled.
    settle_tolerance: float = 0.05
    samples: int = 5
    sample_interval: float = 0.05
    #: Retrace the sweep downwards after reaching the top. The knee at 14.9 V
    #: is a regulator dropping in and out, so up and down need not agree.
    bidirectional: bool = False
    #: Voltage to sit at before the first point and after the last.
    idle_voltage: Optional[float] = None
    note_for: Callable[[float], str] = lambda v: ""


#: Called once per point, after settling and measurement. Return a dict to add
#: columns to the CSV. This is the seam for a scope, a DMM, or anything else
#: that should be triggered at each supply voltage:
#:
#:     def capture(point, psu):
#:         return {"vout_mv": my_scope.measure("VPP") * 1000}
#:
#:     run(psu, plan, hook=capture)
SweepHook = Callable[[SweepPoint, PowerSupply], Optional[dict]]


def run(
    psu: PowerSupply,
    plan: SweepPlan,
    *,
    hook: Optional[SweepHook] = None,
    progress: Optional[Callable[[SweepPoint], None]] = None,
) -> List[SweepPoint]:
    """
    Execute `plan` against `psu` and return the rows.

    The output is switched on at the start and off at the end, including if a
    point raises. A protection trip aborts the sweep rather than recording
    rows the supply was not actually producing.
    """
    order: List[float] = list(plan.points)
    if plan.bidirectional:
        order += list(reversed(plan.points))[1:]

    rows: List[SweepPoint] = []
    if not order:
        return rows

    psu.set_current(plan.current_limit)
    psu.set_voltage(plan.idle_voltage if plan.idle_voltage is not None else order[0])
    psu.set_output(True)

    try:
        for index, volts in enumerate(order):
            point = _one_point(psu, plan, index, volts)
            if hook is not None:
                extra = hook(point, psu)
                if extra:
                    point.extra.update(extra)
            rows.append(point)
            if progress is not None:
                progress(point)
            if point.protection != "OK":
                raise ProtectionTripped(
                    f"supply reported {point.protection} at {volts:.3f} V — sweep aborted "
                    f"after {len(rows)} of {len(order)} points"
                )
    finally:
        try:
            if plan.idle_voltage is not None:
                psu.set_voltage(plan.idle_voltage)
        except SupplyError:
            pass
        psu.set_output(False)

    return rows


def _one_point(psu: PowerSupply, plan: SweepPlan, index: int, volts: float) -> SweepPoint:
    started = time.monotonic()
    psu.set_voltage(volts)

    # Hold for the dwell, then keep reading until the output agrees with the
    # setpoint. Both conditions must be met: the dwell covers whatever the
    # board does after the rail moves, the tolerance covers the rail itself.
    settled = False
    while True:
        reading = psu.read()
        elapsed = time.monotonic() - started
        close = abs(reading.voltage - volts) <= plan.settle_tolerance
        if close and elapsed >= plan.dwell:
            settled = True
            break
        if elapsed >= plan.settle_timeout:
            settled = close
            break
        time.sleep(min(plan.sample_interval, 0.1))

    settle_s = time.monotonic() - started
    reading = psu.measure(samples=plan.samples, interval=plan.sample_interval)

    return SweepPoint(
        index=index,
        requested_v=volts,
        set_v=reading.set_voltage,
        measured_v=reading.voltage,
        measured_a=reading.current,
        measured_w=reading.power,
        temperature_c=reading.temperature,
        mode=reading.mode,
        protection=reading.protection,
        settle_s=round(settle_s, 4),
        settled=settled,
        samples=reading.samples,
        v_spread=reading.voltage_spread,
        a_spread=reading.current_spread,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        note=plan.note_for(volts),
    )


# ── output ──────────────────────────────────────────────────────────────────

BASE_COLUMNS = (
    "index", "requested_v", "set_v", "measured_v", "measured_a", "measured_w",
    "temperature_c", "mode", "protection", "settle_s", "settled", "samples",
    "v_spread", "a_spread", "timestamp", "note",
)


def write_csv(rows: Sequence[SweepPoint], path, *, meta: Optional[dict] = None) -> None:
    """
    Write the sweep to CSV, with the run's parameters as leading `#` comments.

    The comments matter: `Revision 1/TestData/BodePlots/` in this repository is
    31 sweeps that nobody can now attribute to specific nodes, because the
    files carry no header and the bench notes are gone. A data file should say
    what it is without them.
    """
    extra_keys: List[str] = []
    for row in rows:
        for key in row.extra:
            if key not in extra_keys:
                extra_keys.append(key)

    handle = open(path, "w", newline="", encoding="utf-8") if not hasattr(path, "write") else path
    close_after = handle is not path
    try:
        for line in _meta_lines(meta or {}):
            handle.write(f"# {line}\n")
        writer = csv.writer(handle)
        writer.writerow(list(BASE_COLUMNS) + extra_keys)
        for row in rows:
            record = asdict(row)
            writer.writerow(
                [_fmt(record[column]) for column in BASE_COLUMNS]
                + [_fmt(row.extra.get(key, "")) for key in extra_keys]
            )
    finally:
        if close_after:
            handle.close()


def _meta_lines(meta: dict) -> Iterator[str]:
    yield "MelansonTech Isolated Shunt Amplifier — supply sweep"
    yield f"written {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    yield f"command  {' '.join(sys.argv)}"
    for key, value in meta.items():
        yield f"{key:<8} {value}"


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)
