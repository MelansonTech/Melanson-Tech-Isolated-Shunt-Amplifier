# -*- coding: utf-8 -*-
"""Gate helper: the part each designator IS on the sheets against the part the
board carries for it.

The BOM is generated from the compiled sheets and the pick-and-place from the
board; both carry the component Comment. When a value or part is changed on a
sheet after the last ECO the two disagree, and the board - the thing that was
built - keeps the old part while the BOM orders the new one. On the shunt
amplifier Rev 3.1 the sheets say R21 is a 0 ohm link and the board says it is
10 k; the review that recommended changing it never saw either.

    python comment_diff.py SHEET.SchDoc [SHEET ...] --pnp "Pick Place.csv" [--json OUT]

Exit code 1 when any designator differs.
"""
import argparse
import collections
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sheet_netlist import records, u8    # noqa: E402


def sheet_parts(path):
    """designator -> dict(comment, libref, value, footprint, sheet, params)."""
    recs = records(path)
    comps = {}
    for i, r in enumerate(recs):
        if r.get("RECORD") == "1":
            comps[i] = dict(libref=u8(r, "LIBREFERENCE"), desig="?", params={},
                            sheet=os.path.basename(path), footprint="")
    for i, r in enumerate(recs):
        oi = r.get("OWNERINDEX")
        # OWNERINDEX counts from the record after the header, hence the +1
        if oi and int(oi) + 1 in comps:
            c = comps[int(oi) + 1]
            if r.get("RECORD") == "34":
                c["desig"] = u8(r, "TEXT")
            elif r.get("RECORD") == "41":
                c["params"][u8(r, "NAME")] = u8(r, "TEXT")
            elif r.get("RECORD") == "45" and not c["footprint"]:
                c["footprint"] = u8(r, "MODELNAME")
    out = {}
    for c in comps.values():
        out[c["desig"]] = dict(comment=c["params"].get("Comment", ""), libref=c["libref"],
                               value=c["params"].get("Value", ""), footprint=c["footprint"],
                               sheet=c["sheet"])
    return out


def pnp_parts(path):
    out = {}
    with io.open(path, encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            d = (row.get("Designator") or "").strip()
            if d:
                out[d] = dict(comment=(row.get("Comment") or "").strip(),
                              footprint=(row.get("Footprint") or "").strip(),
                              layer=(row.get("Layer") or "").strip())
    return out


def dkey(s):
    return (s.rstrip("0123456789"), int("".join(ch for ch in s if ch.isdigit()) or 0))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sheets", nargs="+")
    ap.add_argument("--pnp", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    sheet = {}
    for s in a.sheets:
        sheet.update(sheet_parts(s))
    board = pnp_parts(a.pnp)
    rows, diffs = [], []
    for d in sorted(set(sheet) | set(board), key=dkey):
        sc = sheet.get(d, {}).get("comment", "<not on sheets>")
        bc = board.get(d, {}).get("comment", "<not on board>")
        sf = sheet.get(d, {}).get("footprint", "")
        bf = board.get(d, {}).get("footprint", "")
        same = (sc == bc)
        rows.append(dict(designator=d, sheet_comment=sc, board_comment=bc, sheet_libref=sheet.get(d, {}).get("libref", ""),
                         sheet_value=sheet.get(d, {}).get("value", ""), sheet_footprint=sf, board_footprint=bf,
                         sheet=sheet.get(d, {}).get("sheet", ""), same=same))
        if not same:
            diffs.append(rows[-1])
    print("%d designators on the sheets, %d on the board; %d differ in Comment" % (len(sheet), len(board), len(diffs)))
    print("%-7s %-34s %-34s %s" % ("desig", "sheet Comment", "board Comment", "sheet LibRef"))
    for r in diffs:
        print("%-7s %-34s %-34s %s" % (r["designator"], r["sheet_comment"][:34], r["board_comment"][:34], r["sheet_libref"][:60]))
    if a.json:
        io.open(a.json, "w", encoding="utf-8", newline="\n").write(json.dumps(dict(rows=rows, diffs=diffs), indent=1, ensure_ascii=False))
        print("written -> %s" % a.json)
    sys.exit(1 if diffs else 0)
