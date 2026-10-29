# -*- coding: utf-8 -*-
"""Shared helpers for the connectivity gates: the union of a project's sheets
as one netlist, the saved board's pad-to-net map, and the same two for a git
revision. Both come out as the same shape so every gate can compare them.

    from netlist_tools import sheet_union, board_map, from_git

    S = sheet_union([SHEET1, SHEET2, ...])     # pins -> class, class -> label
    B = board_map(BOARD)                        # (desig, pin) -> net name

A "pin" is the tuple (designator, pin number) as strings. Sheet net labels,
power ports and ports with the same name on different sheets are joined, which
is the flat-design convention this project family uses; pass hier=True to
keep net labels sheet-local and join only ports and power ports.
"""
import collections
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sheet_netlist import netlist, records, u8   # noqa: E402


class UF(object):
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _label_kinds(path):
    """Which net names on a sheet come from ports / power ports (global even in
    a hierarchical design) and which from plain net labels."""
    glob = set()
    for r in records(path):
        if r.get("RECORD") == "18":
            glob.add(u8(r, "NAME"))
        elif r.get("RECORD") == "17":
            glob.add(u8(r, "TEXT"))
    return glob


def sheet_union(paths, hier=False):
    """Union of several sheets. Returns dict(pins={pin: root}, label={root: 'name'},
    members={root: set(pins)}, comps={desig: libref/comment}, by_sheet={desig: sheet})."""
    uf = UF()
    names = collections.defaultdict(set)      # root -> candidate labels
    comps, by_sheet = {}, {}
    for path in paths:
        cps, desig, nets = netlist(path)
        glob = _label_kinds(path) if hier else None
        for i, c in cps.items():
            d = desig.get(i, "?")
            comps[d] = dict(libref=c["libref"], comment=c["comment"])
            by_sheet[d] = os.path.basename(path)
        for label, pins in nets:
            key = ("net", path, label)
            for d, p, nm in pins:
                uf.union(("pin", d, p), key)
            parts = [x for x in label.split("/") if not x.startswith("Net_")]
            for x in parts:
                if hier and x not in glob:
                    continue
                uf.union(key, ("label", x))
            if parts:
                names[key].update(parts)
    pins, members = {}, collections.defaultdict(set)
    for k in list(uf.p.keys()):
        if k[0] == "pin":
            r = uf.find(k)
            pins[(k[1], k[2])] = r
            members[r].add((k[1], k[2]))
    label = {}
    for k, ls in names.items():
        r = uf.find(k)
        label.setdefault(r, set()).update(ls)
    label = {r: "/".join(sorted(v)) for r, v in label.items()}
    return dict(pins=pins, label=label, members=members, comps=comps, by_sheet=by_sheet)


def board_map(board_path):
    """(designator, pin) -> net name (None when the pad has no net)."""
    from board_model import Board
    b = Board(board_path)
    out = {}
    for p in b.pads:
        pin = str(p.get("name") or p.get("designator") or p.get("pin") or "")
        out[(p["comp"], pin)] = p.get("net")
    return out, b


def from_git(repo, rel_paths, ref="HEAD"):
    """Extract files at a git ref into a temp dir; returns the temp paths (or None per file)."""
    tmp = tempfile.mkdtemp(prefix="review_git_")
    out = []
    for rel in rel_paths:
        rel = rel.replace("\\", "/")
        data = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (ref, rel)], capture_output=True).stdout
        if not data:
            out.append(None)
            continue
        p = os.path.join(tmp, os.path.basename(rel))
        open(p, "wb").write(data)
        out.append(p)
    return out


def sheet_label_of(S, pin):
    r = S["pins"].get(pin)
    if r is None:
        return None
    return S["label"].get(r) or "(unnamed)"
