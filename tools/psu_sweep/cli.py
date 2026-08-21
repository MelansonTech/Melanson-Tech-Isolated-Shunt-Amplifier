"""
Command line for the FNIRSI IPS3608 supply interface.

    psu-sweep ports                       list candidate serial ports
    psu-sweep probe  --port /dev/ttyUSB0  open a port and see if a supply answers
    psu-sweep status --port ...           one state dump, formatted
    psu-sweep set    --volts 15 --amps 0.1
    psu-sweep on | off
    psu-sweep sweep  --port ... -o run.csv
    psu-sweep verify --port ...           check the register map against the panel

Every command takes `--simulate` instead of `--port`, which runs the whole
thing against the built-in model. Rehearse there first.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import List, Optional

from . import profiles, protocol as pr
from .supply import LimitError, PowerSupply, SupplyError
from .sweep import SweepPlan, run, steps, write_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="psu-sweep",
        description="Drive a FNIRSI IPS3608 as the auxiliary supply for a swept measurement.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=profiles.ISOLATION_WARNING,
    )
    parser.add_argument("--port", help="serial port, e.g. /dev/ttyUSB0 or COM4")
    parser.add_argument("--baud", type=int, default=pr.DEFAULT_BAUD,
                        choices=pr.BAUD_RATES,
                        help=f"must match the unit's System menu (default {pr.DEFAULT_BAUD})")
    parser.add_argument("--simulate", action="store_true",
                        help="run against the built-in model instead of hardware")
    parser.add_argument("--profile", default="shunt-amp", choices=sorted(profiles.PROFILES),
                        help="limit envelope to enforce (default: shunt-amp)")
    parser.add_argument("--timeout", type=float, default=2.0, help="reply timeout, seconds")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="skip the isolated-supply confirmation")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ports", help="list candidate serial ports")
    sub.add_parser("probe", help="connect and report what answered")
    sub.add_parser("status", help="print the supply's current state")
    sub.add_parser("on", help="enable the output")
    sub.add_parser("off", help="disable the output")
    sub.add_parser("verify", help="check the register map against the front panel")

    p_set = sub.add_parser("set", help="set voltage and/or current limit")
    p_set.add_argument("--volts", type=float)
    p_set.add_argument("--amps", type=float)

    p_sweep = sub.add_parser("sweep", help="step the supply and record each point")
    p_sweep.add_argument("--start", type=float, help=f"default {profiles.AUX_MIN} V")
    p_sweep.add_argument("--stop", type=float, help=f"default {profiles.ABSOLUTE_MAX} V")
    p_sweep.add_argument("--step", type=float, default=0.1, help="volts (default 0.1)")
    p_sweep.add_argument("--points", help="explicit comma-separated list, overrides start/stop/step")
    p_sweep.add_argument("--current-limit", type=float, default=profiles.DEFAULT_CURRENT_LIMIT,
                         help=f"amps (default {profiles.DEFAULT_CURRENT_LIMIT})")
    p_sweep.add_argument("--dwell", type=float, default=0.5, help="seconds held per point")
    p_sweep.add_argument("--samples", type=int, default=5, help="readings averaged per point")
    p_sweep.add_argument("--sample-interval", type=float, default=0.05)
    p_sweep.add_argument("--settle-tolerance", type=float, default=0.05,
                         help="volts; readback must come this close to the setpoint")
    p_sweep.add_argument("--settle-timeout", type=float, default=5.0, help="seconds per point")
    p_sweep.add_argument("--bidirectional", action="store_true",
                         help="retrace downwards — the 14.9 V knee need not be symmetric")
    p_sweep.add_argument("--idle-voltage", type=float,
                         help="volts to sit at before and after the sweep")
    p_sweep.add_argument("-o", "--output", help="CSV file to write (default: stdout summary only)")
    p_sweep.add_argument("--list", action="store_true",
                         help="print the points that would be visited and exit")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "ports":
            return cmd_ports()
        if args.command == "sweep" and args.list:
            for volts in sweep_points(args):
                print(f"{volts:7.3f} V  {profiles.annotate(volts)}")
            return 0

        with open_supply(args) as psu:
            return DISPATCH[args.command](args, psu)

    except LimitError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except SupplyError as exc:
        print(f"supply error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted — output switched off", file=sys.stderr)
        return 130


# ── plumbing ────────────────────────────────────────────────────────────────

def open_supply(args) -> PowerSupply:
    limits = profiles.PROFILES[args.profile]

    if args.simulate:
        from .supply import connect_simulated
        print(f"[simulated supply — no hardware] envelope: {limits.name}", file=sys.stderr)
        return connect_simulated(limits, timeout=args.timeout)

    if not args.port:
        raise SupplyError("no port given. Use --port, or --simulate to run without hardware "
                          "(`psu-sweep ports` lists candidates).")

    confirm_isolation(args)
    from .supply import connect_serial
    return connect_serial(args.port, limits, baud=args.baud, timeout=args.timeout)


def confirm_isolation(args) -> None:
    """
    Ask once, before the first real connection, that the supply is floating.

    Refusing to make this skippable would be worse than useless — it would get
    scripted around. `--yes` is the supported way past it.
    """
    if args.yes or args.command in ("ports", "probe", "status", "off"):
        return
    print(profiles.ISOLATION_WARNING, file=sys.stderr)
    if not sys.stdin.isatty():
        raise SupplyError("not a terminal, and --yes was not given — refusing to energise the board")
    if input("\nIs the supply's negative output floating? [y/N] ").strip().lower() not in ("y", "yes"):
        raise SupplyError("aborted — connect a floating supply, or pass --yes if you are sure")


def sweep_points(args) -> List[float]:
    if args.points:
        return [float(chunk) for chunk in args.points.replace(",", " ").split()]
    start = args.start if args.start is not None else profiles.AUX_MIN
    stop = args.stop if args.stop is not None else profiles.ABSOLUTE_MAX
    return steps(start, stop, args.step)


# ── commands ────────────────────────────────────────────────────────────────

def cmd_ports() -> int:
    from .transport import find_ports
    found = find_ports()
    if not found:
        print("no serial ports found (is pyserial installed, and the unit plugged in?)")
        return 1
    print("candidate ports, likeliest first:")
    for port in found:
        print(f"  {port}")
    print("\nThe IPS3608 has no distinguishing USB identity — try each with `psu-sweep probe`.")
    return 0


def cmd_probe(args, psu: PowerSupply) -> int:
    state = psu.refresh()
    print(f"connected on {psu.transport.name} at {args.baud if not args.simulate else '—'} baud")
    print(f"  frames decoded   {state.frames_seen}")
    print(f"  device limits    {state.max_voltage:.2f} V / {state.max_current:.2f} A")
    print(f"  reading          {state.output_voltage:.3f} V  {state.output_current:.4f} A  "
          f"{state.output_power:.3f} W")
    if state.unknown_registers:
        print("  undecoded regs   " + " ".join(f"0x{r:02X}" for r in state.unknown_registers)
              + "   (the map in protocol.py may not match this firmware)")
    return 0


def cmd_status(args, psu: PowerSupply) -> int:
    state = psu.refresh()
    rows = [
        ("setpoint", f"{state.set_voltage:.3f} V   {state.set_current:.4f} A"),
        ("output", f"{state.output_voltage:.3f} V   {state.output_current:.4f} A   "
                   f"{state.output_power:.3f} W"),
        ("mode", f"{state.mode_label}   output {'ON' if state.output_enabled else 'off'}"),
        ("protection", state.protection_label),
        ("temperature", f"{state.temperature:.1f} °C"),
        ("limits", f"{state.max_voltage:.2f} V / {state.max_current:.2f} A"),
        ("counters", f"{state.capacity_ah:.4f} Ah   {state.capacity_wh:.4f} Wh"),
    ]
    for name, value in rows:
        print(f"{name:<12} {value}")
    return 0


def cmd_set(args, psu: PowerSupply) -> int:
    if args.amps is not None:
        psu.set_current(args.amps)
        print(f"current limit {args.amps:.4f} A")
    if args.volts is not None:
        psu.set_voltage(args.volts)
        note = profiles.annotate(args.volts)
        print(f"voltage {args.volts:.3f} V" + (f"   ({note})" if note else ""))
    if args.amps is None and args.volts is None:
        print("nothing to set — pass --volts and/or --amps", file=sys.stderr)
        return 2
    return 0


def cmd_on(args, psu: PowerSupply) -> int:
    psu.set_output(True)
    time.sleep(0.2)
    reading = psu.read()
    print(f"output ON — {reading.voltage:.3f} V  {reading.current:.4f} A  {reading.mode}")
    return 0


def cmd_off(args, psu: PowerSupply) -> int:
    psu.set_output(False)
    print("output off")
    return 0


def cmd_sweep(args, psu: PowerSupply) -> int:
    points = sweep_points(args)
    plan = SweepPlan(
        points=points,
        current_limit=args.current_limit,
        dwell=args.dwell,
        settle_timeout=args.settle_timeout,
        settle_tolerance=args.settle_tolerance,
        samples=args.samples,
        sample_interval=args.sample_interval,
        bidirectional=args.bidirectional,
        idle_voltage=args.idle_voltage,
        note_for=profiles.annotate,
    )

    total = len(points) * (2 if args.bidirectional else 1) - (1 if args.bidirectional else 0)
    print(f"{total} points, {points[0]:.3f}–{points[-1]:.3f} V, "
          f"CC limit {args.current_limit:.3f} A, {args.dwell:.2f} s dwell")
    print(f"{'#':>3}  {'set':>7}  {'measured':>9}  {'current':>9}  {'mode':>4}  {'settle':>7}  note")

    def show(point) -> None:
        flag = "" if point.settled else "  UNSETTLED"
        print(f"{point.index:>3}  {point.set_v:7.3f}  {point.measured_v:9.4f}  "
              f"{point.measured_a * 1000:8.2f}m  {point.mode:>4}  {point.settle_s:6.2f}s  "
              f"{point.note}{flag}")

    rows = run(psu, plan, progress=show)

    if args.output:
        write_csv(rows, args.output, meta={
            "supply": f"FNIRSI IPS3608 on {psu.transport.name}",
            "profile": f"{psu.limits.name} ({psu.limits.min_voltage}–{psu.limits.max_voltage} V, "
                       f"max {psu.limits.max_current} A)",
            "plan": f"{len(rows)} points, dwell {args.dwell} s, {args.samples} samples/point, "
                    f"CC limit {args.current_limit} A"
                    + (", bidirectional" if args.bidirectional else ""),
            "sim": "yes — SIMULATED DATA, not measured" if args.simulate else "no",
        })
        print(f"\nwrote {len(rows)} rows to {args.output}")

    unsettled = [row for row in rows if not row.settled]
    if unsettled:
        print(f"\n{len(unsettled)} point(s) never reached the setpoint within "
              f"{args.settle_timeout:.1f} s — check the load and the settle tolerance",
              file=sys.stderr)
    return 0


def cmd_verify(args, psu: PowerSupply) -> int:
    from .verify import verify
    return verify(psu, interactive=not args.yes)


DISPATCH = {
    "probe": cmd_probe,
    "status": cmd_status,
    "set": cmd_set,
    "on": cmd_on,
    "off": cmd_off,
    "sweep": cmd_sweep,
    "verify": cmd_verify,
}


if __name__ == "__main__":
    raise SystemExit(main())
