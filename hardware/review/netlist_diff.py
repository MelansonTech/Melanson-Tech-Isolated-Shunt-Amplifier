# -*- coding: utf-8 -*-
"""Gate: does the saved board carry the same connectivity as the schematic?

Compares the union of the project's sheets against the board pad by pad. Net
names are not compared - partitions are: two pins that share a net on the
sheet must share a net on the board and vice versa. That catches a sheet fix
that was never synchronised (J5 pins 5/6 on the FTCAN board), an unrouted pin,
and a part drawn on a sheet that never reached the board (C112), without
caring what either side calls the net.

    python netlist_diff.py BOARD.CSPcbDoc SHEET.SchDoc [SHEET ...] [--hier]
                           [--git-ref REF --repo DIR] [--json OUT]

--git-ref compares the board against the sheets as committed at REF instead
of the files on disk (needs --repo, the git root the sheet paths are under).
Exit code 1 when any pin disagrees.
"""
import argparse
import collections
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netlist_tools import sheet_union, board_map, from_git, sheet_label_of   # noqa: E402


def compare(S, B):
    common = [p for p in B if p in S["pins"]]
    on_board = set(common)
    bnet = collections.defaultdict(set)
    for p in common:
        bnet[B[p]].add(p)
    mism = []
    for p in common:
        r = S["pins"][p]
        s_part = {q for q in S["members"][r] if q in on_board}
        b_part = bnet[B[p]] if B[p] is not None else {p}
        if s_part != b_part:
            mism.append(dict(pin="%s.%s" % p, sheet_net=sheet_label_of(S, p), board_net=B[p],
                             sheet_only=sorted("%s.%s" % q for q in (s_part - b_part))[:8],
                             board_only=sorted("%s.%s" % q for q in (b_part - s_part))[:8]))
    sheet_comps = {d for d, _ in S["pins"] if d}
    board_comps = {d for d, _ in B if d}          # free pads (no component) have comp None
    return dict(n_common=len(common), mismatches=sorted(mism, key=lambda m: m["pin"]),
                sheet_only_components=sorted(sheet_comps - board_comps),
                board_only_components=sorted(board_comps - sheet_comps),
                board_only_pins=sorted("%s.%s" % p for p in B if p not in S["pins"] and p[0] in sheet_comps)[:40])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("board"); ap.add_argument("sheets", nargs="+")
    ap.add_argument("--hier", action="store_true", help="net labels are sheet-local; only ports and power ports join sheets")
    ap.add_argument("--git-ref"); ap.add_argument("--repo")
    ap.add_argument("--json")
    a = ap.parse_args()
    sheets = a.sheets
    label = "sheets on disk"
    if a.git_ref:
        rels = [os.path.relpath(s, a.repo) for s in a.sheets]
        sheets = [p for p in from_git(a.repo, rels, a.git_ref) if p]
        label = "sheets at %s" % a.git_ref
    S = sheet_union(sheets, hier=a.hier)
    B, b = board_map(a.board)
    res = compare(S, B)
    res["board"] = os.path.basename(a.board); res["sheets"] = [os.path.basename(s) for s in a.sheets]; res["sheet_source"] = label
    print("board %s (%d pads) vs %s (%d sheets): %d pins compared" % (res["board"], len(B), label, len(sheets), res["n_common"]))
    if res["mismatches"]:
        print("\n%d pin(s) connected differently:" % len(res["mismatches"]))
        for m in res["mismatches"]:
            print("  %-10s sheet net %-16s board net %-16s sheet also has %s | board also has %s"
                  % (m["pin"], str(m["sheet_net"])[:16], str(m["board_net"])[:16], ", ".join(m["sheet_only"]) or "-", ", ".join(m["board_only"]) or "-"))
    else:
        print("\nevery compared pin sits in the same net on both: the board matches the sheets")
    if res["sheet_only_components"]:
        print("\non the sheets, not on the board: %s" % ", ".join(res["sheet_only_components"]))
    if res["board_only_components"]:
        print("on the board, not on the sheets: %s" % ", ".join(res["board_only_components"]))
    if res["board_only_pins"]:
        print("board pads with no sheet pin (shells, pegs, thermal pads): %s%s" % (", ".join(res["board_only_pins"][:12]), " ..." if len(res["board_only_pins"]) > 12 else ""))
    if a.json:
        io.open(a.json, "w", encoding="utf-8", newline="\n").write(json.dumps(res, indent=1))
        print("\nwritten -> %s" % a.json)
    sys.exit(1 if res["mismatches"] else 0)
