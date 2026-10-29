# -*- coding: utf-8 -*-
"""Gate: the pick-and-place output against the placed components.

CircuitStudio writes the P&P from the in-memory document and offsets it by
the output origin, so a straight comparison reads every part as moved by the
same vector. The offset is taken as the median displacement and removed;
what is left is real movement, rotation or a side change, plus parts that
exist on only one side of the comparison.

    python pnp_vs_board.py "Pick Place.csv" BOARD.CSPcbDoc [--tol 0.025] [--json OUT]

Exit code 1 when any part moved, rotated, changed side or is missing.
"""
import argparse
import csv
import io
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board_model import Board   # noqa: E402


def read_pnp(path):
    rows = []
    with io.open(path, encoding="utf-8-sig", errors="replace") as f:
        txt = f.read()
    # CircuitStudio P&P csv has a few header lines before the column row
    lines = txt.splitlines()
    start = next((i for i, l in enumerate(lines) if l.lower().startswith('"designator"') or l.lower().startswith("designator")), 0)
    for r in csv.DictReader(lines[start:]):
        d = (r.get("Designator") or "").strip()
        if not d:
            continue
        def num(k):
            v = (r.get(k) or "").strip().replace("mm", "").replace("mil", "")
            try:
                return float(v)
            except ValueError:
                return None
        # The board component position is its REFERENCE point; CircuitStudio
        # writes both "Ref X/Y" and the pad centroid "Mid X/Y". Compare the
        # reference, or every through-hole part whose origin is off its pad
        # centroid (SW1, J4) reads as moved.
        x = num("Ref X") if num("Ref X") is not None else (num("Mid X") if num("Mid X") is not None else num("Center-X(mm)"))
        y = num("Ref Y") if num("Ref Y") is not None else (num("Mid Y") if num("Mid Y") is not None else num("Center-Y(mm)"))
        rot = num("Rotation")
        layer = (r.get("Layer") or "").strip().upper()
        rows.append(dict(designator=d, x=x, y=y, rot=rot, side="TOP" if layer.startswith("T") else ("BOTTOM" if layer.startswith("B") else layer)))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pnp"); ap.add_argument("board"); ap.add_argument("--tol", type=float, default=0.025); ap.add_argument("--json")
    a = ap.parse_args()
    pnp = {r["designator"]: r for r in read_pnp(a.pnp)}
    b = Board(a.board)
    brd = {c["designator"]: c for c in b.components}
    common = [d for d in pnp if d in brd and pnp[d]["x"] is not None]
    dx = statistics.median(pnp[d]["x"] - brd[d]["x"] for d in common) if common else 0.0
    dy = statistics.median(pnp[d]["y"] - brd[d]["y"] for d in common) if common else 0.0
    moved, rotated, flipped = [], [], []
    for d in common:
        p, c = pnp[d], brd[d]
        if abs(p["x"] - dx - c["x"]) > a.tol or abs(p["y"] - dy - c["y"]) > a.tol:
            moved.append((d, round(p["x"] - dx - c["x"], 3), round(p["y"] - dy - c["y"], 3)))
        if p["rot"] is not None and abs(((p["rot"] - c["rot"]) + 180) % 360 - 180) > 0.5:
            rotated.append((d, p["rot"], c["rot"]))
        if p["side"] in ("TOP", "BOTTOM") and p["side"] != c["side"]:
            flipped.append(d)
    only_out = sorted(set(pnp) - set(brd)); only_brd = sorted(set(brd) - set(pnp))
    print("%s: %d rows; board: %d parts; output origin offset (%.3f, %.3f) mm" % (os.path.basename(a.pnp), len(pnp), len(brd), dx, dy))
    print("moved > %.3f mm: %d %s" % (a.tol, len(moved), moved[:8]))
    print("rotated: %d %s" % (len(rotated), rotated[:8]))
    print("side changed: %d %s" % (len(flipped), flipped[:8]))
    print("only in the output: %d %s" % (len(only_out), only_out[:12]))
    print("only on the board: %d %s" % (len(only_brd), only_brd[:12]))
    bad = bool(moved or rotated or flipped or only_out or only_brd)
    print("\n-> %s" % ("placement differs from the board" if bad else "placement identical to the board"))
    if a.json:
        io.open(a.json, "w", encoding="utf-8", newline="\n").write(json.dumps(dict(pnp=os.path.basename(a.pnp), n_pnp=len(pnp), n_board=len(brd), offset=[dx, dy], moved=moved, rotated=rotated, flipped=flipped, only_output=only_out, only_board=only_brd), indent=1))
        print("written -> %s" % a.json)
    sys.exit(1 if bad else 0)
