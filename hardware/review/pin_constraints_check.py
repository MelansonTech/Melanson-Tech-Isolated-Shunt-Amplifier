# -*- coding: utf-8 -*-
"""Gate: the FPGA / MCU pin-constraint file against the schematic.

The gateware's pin file is the firmware's picture of the board; the sheet is
the hardware's. They drift. For every LOCATE in a Lattice .lpf (and the
equivalent lines of a Xilinx .xdc or Intel .qsf, see parse_*), the sheet net
on that package pin is compared with the constrained signal name.

    python pin_constraints_check.py PINFILE SHEET.SchDoc [SHEET ...] --fpga U2
                                    [--board BOARD.CSPcbDoc] [--hier] [--json OUT]

Names are compared after normalising case, separators and bus brackets, so
`can_rx`, `CAN_RX`, `can_rx[0]` and `CAN_RX0` match. A site with no net on the
sheet, a net whose name shares nothing with the signal, or a sheet signal on
the FPGA with no LOCATE at all are each listed. Exit code 1 on a mismatch.
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netlist_tools import sheet_union, board_map, sheet_label_of   # noqa: E402


def parse_lpf(text):
    out = []
    for m in re.finditer(r'LOCATE\s+COMP\s+"([^"]+)"\s+SITE\s+"([^"]+)"\s*;', text, re.I):
        out.append((m.group(1), m.group(2)))
    return out


def parse_xdc(text):
    out = []
    for m in re.finditer(r'set_property\s+PACKAGE_PIN\s+(\S+)\s+\[get_ports\s+\{?\s*([^\]\}\s]+)', text, re.I):
        out.append((m.group(2), m.group(1)))
    return out


def parse_qsf(text):
    out = []
    for m in re.finditer(r'set_location_assignment\s+PIN_(\S+)\s+-to\s+(\S+)', text, re.I):
        out.append((m.group(2), m.group(1)))
    return out


def norm(s):
    s = s.lower()
    s = re.sub(r"\[(\d+)\]", r"\1", s)
    s = re.sub(r"\\", "", s)                    # Altium active-low overbars  SPI_C\S\
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def tokens(s):
    s = re.sub(r"\[(\d+)\]", r"\1", s.lower()).replace("\\", "")
    return [t for t in re.split(r"[^a-z0-9]+", s) if t]


def names_match(sig, net):
    """True when the names agree outright, or agree once each side's leading
    block prefix is dropped (hr_dq[0] vs RAM_DQ0, usb_wr_n vs WR_N): the
    common suffix must be at least three characters so hr_ck vs RAM_CK stays
    unverified and goes to --map."""
    a, b = norm(sig), norm(net)
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = tokens(sig), tokens(net)
    for da in (0, 1):
        for db_ in (0, 1):
            sa, sb = ta[da:], tb[db_:]
            if sa and sb and sa == sb and len("".join(sa)) >= 3:
                return True
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pinfile"); ap.add_argument("sheets", nargs="+"); ap.add_argument("--fpga", required=True)
    ap.add_argument("--board"); ap.add_argument("--hier", action="store_true"); ap.add_argument("--json")
    ap.add_argument("--map", help="JSON {signal: sheet net} for signals whose names share nothing with the net (led_n[0] -> FPGA_Rdy_RED)")
    a = ap.parse_args()
    text = io.open(a.pinfile, encoding="utf-8", errors="replace").read()
    ext = os.path.splitext(a.pinfile)[1].lower()
    locs = {".lpf": parse_lpf, ".xdc": parse_xdc, ".qsf": parse_qsf}.get(ext, parse_lpf)(text)
    S = sheet_union(a.sheets, hier=a.hier)
    B = board_map(a.board)[0] if a.board else None
    smap = json.load(io.open(a.map, encoding="utf-8")) if a.map else {}
    rows, used = [], set()
    # three outcomes: "ok" (the name or the map confirms it), "unverified" (the site carries a
    # named net the heuristic cannot tie to the signal - a map entry settles it), "fail" (no net
    # on the sheet, the map disagrees, or the board net differs from the sheet net at that site).
    for sig, site in locs:
        pin = (a.fpga, str(site))
        net = sheet_label_of(S, pin)
        bnet = B.get(pin) if B else None
        if net is None:
            st, ok = ("site %s is not a pin of %s on the sheet" % (site, a.fpga), "fail")
        elif net == "(unnamed)":
            st, ok = ("the site is wired but its net has no label; name it or map it", "unverified")
        elif sig in smap:
            ok = "ok" if norm(smap[sig]) == norm(net) else "fail"
            st = "map says %s" % smap[sig] + ("" if ok == "ok" else ", sheet has %s" % net)
        elif names_match(sig, net):
            st, ok = "ok", "ok"
        else:
            st, ok = "name shares nothing with the sheet net; add it to --map", "unverified"
        if B is not None and net not in (None, "(unnamed)") and bnet is not None and norm(bnet) != norm(net):
            st += "; board net %s differs from the sheet" % bnet; ok = "fail"
        rows.append(dict(signal=sig, site=str(site), sheet_net=net, board_net=bnet, ok=ok, status=st))
        used.add(str(site))
    # sheet signals on the FPGA with no constraint
    unconstrained = []
    for (d, p), r in S["pins"].items():
        if d == a.fpga and p not in used:
            lab = S["label"].get(r)
            if lab and not re.match(r"^(gnd|vcc|vss|3v3|1v1|2v5|\+|vcc)", lab.lower()) and len(S["members"][r]) > 1:
                unconstrained.append((p, lab))
    bad = [r for r in rows if r["ok"] == "fail"]
    unv = [r for r in rows if r["ok"] == "unverified"]
    print("%s: %d LOCATEs against %s on %d sheet(s)%s: %d confirmed, %d unverified, %d wrong"
          % (os.path.basename(a.pinfile), len(locs), a.fpga, len(a.sheets), " and the board" if B else "", len(rows) - len(bad) - len(unv), len(unv), len(bad)))
    if bad:
        print("\n%d constraint(s) disagree with the sheet:" % len(bad))
        for r in bad:
            print("  %-24s site %-5s sheet net %-20s %s" % (r["signal"], r["site"], str(r["sheet_net"]), r["status"]))
    if unv:
        print("\n%d constraint(s) the name heuristic cannot confirm (settle each with --map):" % len(unv))
        for r in unv:
            print("  %-24s site %-5s sheet net %-20s %s" % (r["signal"], r["site"], str(r["sheet_net"]), r["status"]))
    if not bad and not unv:
        print("\nevery LOCATE lands on the sheet net it names")
    if unconstrained:
        print("\n%d named sheet nets on %s with no LOCATE (power excluded): %s%s" % (
            len(unconstrained), a.fpga, ", ".join("%s=%s" % x for x in sorted(unconstrained, key=lambda t: int(re.sub(r"\D", "", t[0]) or 0))[:20]), " ..." if len(unconstrained) > 20 else ""))
    if a.json:
        io.open(a.json, "w", encoding="utf-8", newline="\n").write(json.dumps(dict(pinfile=os.path.basename(a.pinfile), fpga=a.fpga, rows=rows, unconstrained=unconstrained), indent=1))
        print("\nwritten -> %s" % a.json)
    sys.exit(1 if bad else 0)
