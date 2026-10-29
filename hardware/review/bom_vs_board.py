# -*- coding: utf-8 -*-
"""Gate: the BOM output against the placed components.

The BOM is generated from the compiled sheets, the board from the ECO sync;
they can disagree, and a BOM that silently lacks a sheet (FTCAN 2026-10-14
18:56: 153 of 221 parts, the whole FPGA sheet) gets ordered as it is. Every
designator on the board must appear in the BOM and vice versa; fiducials,
logos and other DNP rows are listed separately, not counted as misses.

    python bom_vs_board.py BOM.xlsx|BOM.csv BOARD.CSPcbDoc [--dnp FD,LOGO,TP] [--json OUT]

Exit code 1 when a placed part is missing from the BOM.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board_model import Board   # noqa: E402

DESIG = re.compile(r"^[A-Z]{1,4}\d{1,3}$")      # C1546 is an LCSC code, not a designator


def bom_designators(path):
    out = set()
    if path.lower().endswith(".xlsx"):
        z = zipfile.ZipFile(path)
        strings = re.findall(r"<t[^>]*>(.*?)</t>", z.read("xl/sharedStrings.xml").decode("utf-8"), re.S)
        for s in strings:
            toks = [t.strip() for t in re.split(r"[,\s]+", s) if t.strip()]
            if toks and all(DESIG.match(t) for t in toks):
                out.update(toks)
    else:
        for r in csv.DictReader(io.open(path, encoding="utf-8-sig")):
            for t in re.split(r"[,\s]+", r.get("Designator") or ""):
                if t:
                    out.add(t)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bom"); ap.add_argument("board"); ap.add_argument("--dnp", default="FD,LOGO,TP"); ap.add_argument("--json")
    a = ap.parse_args()
    dnp = tuple(x.strip() for x in a.dnp.split(",") if x.strip())
    bom = bom_designators(a.bom)
    board = {c["designator"] for c in Board(a.board).components}
    key = lambda s_: (re.sub(r"\d", "", s_), int(re.sub(r"\D", "", s_) or 0))
    missing = sorted((board - bom), key=key)
    missing_real = [d for d in missing if not d.startswith(dnp)]
    missing_dnp = [d for d in missing if d.startswith(dnp)]
    extra = sorted(bom - board, key=key)
    print("%s: %d designators; board: %d placed parts" % (os.path.basename(a.bom), len(bom), len(board)))
    if missing_real:
        print("\nON THE BOARD, NOT IN THE BOM (%d): %s" % (len(missing_real), ", ".join(missing_real)))
    if missing_dnp:
        print("not in the BOM, expected (%s): %s" % ("/".join(dnp), ", ".join(missing_dnp)))
    if extra:
        print("in the BOM, not on the board (%d): %s" % (len(extra), ", ".join(extra)))
    if not missing_real and not extra:
        print("\nevery placed part is in the BOM and nothing in the BOM is unplaced")
    if a.json:
        io.open(a.json, "w", encoding="utf-8", newline="\n").write(json.dumps(dict(bom=os.path.basename(a.bom), n_bom=len(bom), n_board=len(board), missing=missing_real, missing_dnp=missing_dnp, extra=extra), indent=1))
        print("written -> %s" % a.json)
    sys.exit(1 if missing_real else 0)
