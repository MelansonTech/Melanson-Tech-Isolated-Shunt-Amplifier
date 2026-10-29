# -*- coding: utf-8 -*-
"""Gate: connectivity against FUNCTION. For every connector, socket, header
and interface in a spec, each pin is checked against what the device on the
other end needs it to reach - not against another connector, not against the
net name, but against the role the driver gives that pin (an FT2232H MPSSE
channel makes socket pin "SDO" an INPUT, so it must carry TDO out of the
FPGA). Checked three ways, because the three disagree in practice: the sheets
on disk, the saved board, and the sheets as committed.

    python connectivity_check.py SPEC.json --board BOARD.CSPcbDoc --sheets S1.SchDoc [S2 ...]
                                 [--repo DIR --git-ref HEAD] [--hier] [--json OUT]

Spec (see assets/connectivity-spec-example.json):
{
  "interfaces": [
    {"name": "J5 JTAG (FT2232H MPSSE channel B)", "connector": "J5",
     "pins": {
       "3": {"label": "CS",  "driver": "BDBUS3", "dir": "out", "role": "TMS", "must_reach": ["U2", "64"]},
       "5": {"label": "SDO", "driver": "BDBUS2", "dir": "in",  "role": "TDO", "must_reach": ["U2", "60"]}
     }}
  ]
}
"dir" is the direction at the DRIVER: a pin that is an input there must reach
the target's output. Exit code 1 when any pin is wrong anywhere.
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netlist_tools import sheet_union, board_map, from_git, sheet_label_of   # noqa: E402


def check_iface(iface, pin_net, tgt_pins_of):
    """pin_net: (desig, pin) -> net key; tgt_pins_of(net_key, desig) -> pins of desig on that net."""
    rows = []
    conn = iface["connector"]
    for pin, spec in iface["pins"].items():
        tgt, tpin = spec["must_reach"]
        net = pin_net.get((conn, str(pin)))
        reach = pin_net.get((tgt, str(tpin)))
        ok = net is not None and net == reach
        actual = tgt_pins_of(net, tgt) if net is not None else []
        rows.append(dict(connector=conn, pin=str(pin), label=spec.get("label", ""), driver=spec.get("driver", ""), dir=spec.get("dir", ""),
                         role=spec.get("role", ""), must_reach="%s.%s" % (tgt, tpin),
                         reaches="%s.%s" % (tgt, ",".join(sorted(actual))) if actual else "nothing on %s" % tgt, ok=ok))
    return rows


def sheet_view(S):
    pin_net = dict(S["pins"])
    def tgt_pins_of(root, desig):
        return [p for d, p in S["members"].get(root, ()) if d == desig]
    return pin_net, tgt_pins_of, (lambda p: sheet_label_of(S, p))


def board_view(B):
    def tgt_pins_of(net, desig):
        return [p for (d, p), n in B.items() if d == desig and n == net]
    return B, tgt_pins_of


def run(spec, sheets, board, repo=None, ref=None, hier=False):
    out = dict(sources={}, interfaces=[])
    views = {}
    S = sheet_union(sheets, hier=hier); views["sheet"] = sheet_view(S)[:2]; out["sources"]["sheet"] = "sheets on disk"
    if board:
        B, _ = board_map(board); views["board"] = board_view(B); out["sources"]["board"] = os.path.basename(board)
    if repo and ref:
        got = [p for p in from_git(repo, [os.path.relpath(s, repo) for s in sheets], ref) if p]
        if got:
            Sg = sheet_union(got, hier=hier); views["committed"] = sheet_view(Sg)[:2]; out["sources"]["committed"] = "sheets at %s" % ref
    for iface in spec["interfaces"]:
        res = dict(name=iface["name"], connector=iface["connector"], results={})
        for src, (pin_net, tp) in views.items():
            rows = check_iface(iface, pin_net, tp)
            # replace net keys with readable names
            for r in rows:
                pass
            res["results"][src] = rows
        out["interfaces"].append(res)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--board"); ap.add_argument("--sheets", nargs="+", required=True)
    ap.add_argument("--repo"); ap.add_argument("--git-ref"); ap.add_argument("--hier", action="store_true"); ap.add_argument("--json")
    a = ap.parse_args()
    spec = json.load(io.open(a.spec, encoding="utf-8"))
    out = run(spec, a.sheets, a.board, a.repo, a.git_ref, a.hier)
    bad_any = False
    for iface in out["interfaces"]:
        print("\n%s" % iface["name"])
        for src, rows in iface["results"].items():
            bad = [r for r in rows if not r["ok"]]
            bad_any |= bool(bad)
            print("  %-10s %s" % (src, "all %d pins reach the right place" % len(rows) if not bad else "; ".join(
                "pin %s %s (%s %s, %s) reaches %s, must reach %s" % (r["pin"], r["label"], r["driver"], r["dir"], r["role"], r["reaches"], r["must_reach"]) for r in bad)))
    if a.json:
        io.open(a.json, "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
        print("\nwritten -> %s" % a.json)
    sys.exit(1 if bad_any else 0)
